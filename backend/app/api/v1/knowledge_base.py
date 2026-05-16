import asyncio
import io
import logging
import os
import time
import shutil
import traceback
import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

from PIL import Image as PILImage

from app.db.database import get_db
from app.schemas.knowledge_base import (
    SpecificationIngestRequest,
    CaseIngestRequest,
    SpecificationResponse,
    CaseResponse,
    RetrievalResult,
    WikiItemResponse,
    WikiExportResponse,
)
from app.config import settings
from app.core.vector_store import VectorStoreService
from app.services.knowledge_mining_service import KnowledgeMiningService
from app.models.document_image import DocumentImage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge_base"])

UPLOAD_DIR = Path("uploads/knowledge_base")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_CONCURRENT_VISION = 3

# Background task registry: task_id -> status dict
_upload_tasks: Dict[str, dict] = {}


def _write_file(path: Path, data: bytes):
    with open(path, "wb") as f:
        f.write(data)


def _save_pil_image(path: Path, img_bytes: bytes):
    pil_img = PILImage.open(io.BytesIO(img_bytes))
    pil_img = pil_img.convert("RGB")
    pil_img.save(str(path), "PNG")


async def _save_document_images(
    parsed_data: dict,
    doc_id: uuid.UUID,
    file_id: str,
    chunk_db_records: Dict[int, uuid.UUID],
    db: AsyncSession,
    vision_model: Optional[str] = None,
    vision_api_key: Optional[str] = None,
    vision_base_url: Optional[str] = None,
    embedding_model: Optional[str] = None,
    embedding_api_key: Optional[str] = None,
    embedding_base_url: Optional[str] = None,
) -> dict:
    """保存文档中的图片到磁盘和数据库，生成视觉描述，创建 figure chunks 并嵌入向量"""
    if not parsed_data or not parsed_data.get("images"):
        return {"saved": 0, "described": 0, "embeddings": 0}

    image_dir = UPLOAD_DIR / "images" / file_id
    image_dir.mkdir(parents=True, exist_ok=True)

    vision = None
    if vision_model or vision_api_key or vision_base_url or settings.vision_model or settings.vision_api_key:
        from app.services.vision_service import VisionService
        vision = VisionService(
            model_name=vision_model,
            api_key=vision_api_key,
            base_url=vision_base_url,
        )

    sem = asyncio.Semaphore(MAX_CONCURRENT_VISION)

    # Phase 1: save all PIL images to disk in parallel (off-thread)
    img_entries: list[dict] = []
    save_tasks = []
    for img_data in parsed_data["images"]:
        img_bytes = img_data.get("_image_bytes")
        if not img_bytes:
            continue
        img_filename = f"page{img_data['page']}_img{img_data['image_index']}.png"
        img_path = image_dir / img_filename
        img_entries.append({"img_data": img_data, "img_path": img_path, "img_bytes": img_bytes})
        save_tasks.append(asyncio.to_thread(_save_pil_image, img_path, img_bytes))

    if save_tasks:
        await asyncio.gather(*save_tasks, return_exceptions=True)

    # Phase 2: call vision API in parallel with semaphore
    async def describe_one(entry: dict) -> Optional[str]:
        if not vision:
            return None
        async with sem:
            try:
                img_data = entry["img_data"]
                context_text = (img_data.get("context_text") or "")[:2000]
                return await vision.describe_image(entry["img_bytes"], context_text)
            except Exception as e:
                logger.warning("Vision failed for page%s_img%s: %s",
                               entry["img_data"].get("page"), entry["img_data"].get("image_index"), e)
                return None

    description_results = await asyncio.gather(*[describe_one(e) for e in img_entries], return_exceptions=True)

    # Phase 3: create DB records
    saved = 0
    described = 0
    from app.models.document import DocumentChunk

    for entry, desc in zip(img_entries, description_results):
        try:
            img_data = entry["img_data"]
            if isinstance(desc, BaseException):
                desc = None
            if desc:
                described += 1

            linked_chunk_id = img_data.get("linked_chunk_id")
            if not linked_chunk_id:
                linked_chunk_id = chunk_db_records.get(img_data["page"])

            context_text = (img_data.get("context_text") or "")[:2000]
            context_before = img_data.get("context_before")
            context_after = img_data.get("context_after")

            img_record = DocumentImage(
                document_id=doc_id,
                page=img_data["page"],
                image_index=img_data["image_index"],
                file_path=str(entry["img_path"]),
                x=img_data.get("x"),
                y=img_data.get("y"),
                width=img_data.get("width"),
                height=img_data.get("height"),
                image_type="png",
                context_text=context_text,
                description=desc,
                linked_chunk_id=linked_chunk_id,
            )
            db.add(img_record)

            if desc:
                figure_chunk = DocumentChunk(
                    document_id=doc_id,
                    chunk_index=9990 + img_data["image_index"],
                    text=f"[图 {img_data['page']}-{img_data['image_index']}] {desc}",
                    page=img_data["page"],
                    chunk_type="figure",
                    image_path=str(entry["img_path"]),
                    image_description=desc,
                    context_before=context_before,
                    context_after=context_after,
                )
                db.add(figure_chunk)

            saved += 1
        except Exception as e:
            logger.warning("Failed to create image record page%s_img%s: %s",
                           entry["img_data"].get("page"), entry["img_data"].get("image_index"), e)

    # Single flush for all image + figure chunk records
    if saved > 0:
        await db.flush()

    # Phase 4: batch embed figure chunks
    embeddings_count = 0
    if described > 0:
        try:
            vs = VectorStoreService(
                db,
                embedding_model=embedding_model,
                embedding_api_key=embedding_api_key,
                embedding_base_url=embedding_base_url,
            )
            embeddings_count = await vs.store_chunk_embeddings(doc_id)
        except Exception as e:
            logger.warning("Figure chunk embedding failed: %s", e)
            await db.rollback()

    return {"saved": saved, "described": described, "embeddings": embeddings_count}


async def _embed_text_chunks(
    doc_id: uuid.UUID,
    db: AsyncSession,
    embedding_model: Optional[str] = None,
    embedding_api_key: Optional[str] = None,
    embedding_base_url: Optional[str] = None,
) -> int:
    """为文档的文本 chunk 生成向量嵌入"""
    try:
        vs = VectorStoreService(
            db,
            embedding_model=embedding_model,
            embedding_api_key=embedding_api_key,
            embedding_base_url=embedding_base_url,
        )
        return await vs.store_chunk_embeddings(doc_id)
    except Exception as e:
        logger.warning("Text chunk embedding failed: %s", e)
        return 0


def _get_first_section_title(parsed_data: dict | None) -> str:
    if not parsed_data:
        return ""
    metadata = parsed_data.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    sections = metadata.get("sections")
    if isinstance(sections, list) and sections:
        first = sections[0]
        if isinstance(first, dict):
            return first.get("title", "") or ""
    return ""


async def _create_chunks_and_get_records(
    doc_id: uuid.UUID,
    parsed_data: dict | None,
    db: AsyncSession,
) -> Dict[int, uuid.UUID]:
    """Create DocumentChunk records with batch flush, return page->chunk_id mapping."""
    from app.models.document import DocumentChunk
    chunk_db_records: Dict[int, uuid.UUID] = {}
    if not parsed_data or not parsed_data.get("chunks"):
        return chunk_db_records

    chunk_records = []
    for idx, chunk in enumerate(parsed_data["chunks"][:100]):
        chunk_records.append(DocumentChunk(
            document_id=doc_id,
            chunk_index=idx,
            text=chunk["text"][:2000],
            page=chunk.get("page"),
            chunk_type=chunk.get("type", "text"),
        ))

    for cr in chunk_records:
        db.add(cr)

    if chunk_records:
        await db.flush()
        # Build page->first_chunk_id mapping after flush (IDs are now populated)
        for cr in chunk_records:
            page = cr.page
            if page and page not in chunk_db_records:
                chunk_db_records[page] = cr.id

    return chunk_db_records


async def _run_background_upload(task_id: str, file_path: Path, filename: str, content_len: int, category: str, project_type: Optional[str], vision_model: Optional[str], vision_api_key: Optional[str], vision_base_url: Optional[str], embedding_model: Optional[str], embedding_api_key: Optional[str], embedding_base_url: Optional[str]):
    """Run the heavy upload processing in the background."""
    _upload_tasks[task_id] = {"status": "processing", "step": "parsing", "message": "正在解析文档...", "started_at": time.time()}
    from app.db.database import async_session_maker

    try:
        async with async_session_maker() as db:
            _upload_tasks[task_id]["step"] = "parsing"
            _upload_tasks[task_id]["message"] = "正在解析文档..."

            # Create a fake UploadFile-like object for _process_upload
            class _FileObj:
                def __init__(self):
                    self.filename = filename

            file_obj = _FileObj()

            # PDF parsing (sync, off-thread)
            parsed_data = None
            ext = file_path.suffix.lower()
            if ext == ".pdf":
                try:
                    from app.services.pdf_parsing_service import PDFParsingService
                    pdf_service = PDFParsingService()
                    _upload_tasks[task_id]["message"] = "正在解析 PDF..."
                    parsed_data = await asyncio.to_thread(pdf_service.parse_pdf, str(file_path))
                    logger.info("PDF parsed: %s, pages: %s", filename, parsed_data['metadata']['page_count'])
                except Exception as e:
                    logger.warning("Failed to parse PDF: %s", e)

            title = parsed_data["metadata"].get("title") if parsed_data else filename
            full_text = parsed_data["text"] if parsed_data else None
            category_clean = category.strip().lower() if isinstance(category, str) else category
            file_id_str = task_id

            from app.models.document import Document, DocumentChunk

            # Create Document record
            doc = Document(
                id=uuid.UUID(file_id_str),
                filename=filename,
                file_path=str(file_path),
                file_type=ext.replace(".", ""),
                file_size=content_len,
                title=title,
                project_type=project_type,
                category=category_clean,
                full_text=full_text if full_text else None,
                metadata_json=(parsed_data and parsed_data.get("metadata")) if parsed_data else None,
            )
            db.add(doc)
            await db.flush()

            # Batch-create chunks
            chunk_db_records = await _create_chunks_and_get_records(doc.id, parsed_data, db)

            # Category-specific record
            spec_or_case = None
            if category_clean == "spec":
                from app.models.specification import Specification
                spec_or_case = Specification(
                    name=title,
                    code=f"SPC-{file_id_str[:8]}",
                    chapter=_get_first_section_title(parsed_data),
                    section="",
                    content=full_text[:50000] if full_text else "",
                    project_types=[project_type] if project_type else None,
                )
                db.add(spec_or_case)
                await db.flush()
            elif category_clean == "case":
                from app.models.case import Case
                spec_or_case = Case(
                    name=title,
                    project_type=project_type or "未分类",
                    location=(parsed_data and parsed_data.get("metadata", {}).get("location", "")) if parsed_data else "",
                    owner="",
                    summary=full_text[:2000] if full_text else "",
                    design_params=(parsed_data and parsed_data.get("metadata")) if parsed_data else None,
                )
                db.add(spec_or_case)
                await db.flush()

            # Commit the basic record so it's visible even if vision/embedding fails
            await db.commit()
            spec_id = str(spec_or_case.id) if spec_or_case else None

            # --- Phase: Vision ---
            if parsed_data and parsed_data.get("images"):
                _upload_tasks[task_id]["step"] = "vision"
                _upload_tasks[task_id]["message"] = f"正在分析 {len(parsed_data['images'])} 张图片..."
                images_result = await _save_document_images(
                    parsed_data, doc.id, file_id_str, chunk_db_records, db,
                    vision_model=vision_model, vision_api_key=vision_api_key,
                    vision_base_url=vision_base_url,
                    embedding_model=embedding_model, embedding_api_key=embedding_api_key,
                    embedding_base_url=embedding_base_url,
                )
                await db.commit()
            else:
                images_result = {"saved": 0, "described": 0, "embeddings": 0}

            # --- Phase: Embedding ---
            _upload_tasks[task_id]["step"] = "embedding"
            _upload_tasks[task_id]["message"] = "正在生成向量嵌入..."
            text_chunks_embedded = await _embed_text_chunks(
                doc.id, db,
                embedding_model=embedding_model,
                embedding_api_key=embedding_api_key,
                embedding_base_url=embedding_base_url,
            )
            await db.commit()

            # Query actual counts from DB
            from sqlalchemy import func as sa_func
            from app.models.document import DocumentChunk
            total_stmt = select(sa_func.count()).where(DocumentChunk.document_id == doc.id)
            emb_stmt = select(sa_func.count()).where(DocumentChunk.document_id == doc.id, DocumentChunk.embedding.isnot(None))
            total_chunks = (await db.execute(total_stmt)).scalar() or 0
            embedded_chunks = (await db.execute(emb_stmt)).scalar() or 0

            # Done
            result = {
                "status": "success",
                "message": f'文件 "{filename}" 已上传并解析成功。',
                "fileId": file_id_str,
                "filename": filename,
                "size": content_len,
                "page_count": parsed_data["metadata"].get("page_count") if parsed_data else None,
                "chunks_stored": total_chunks,
                "images_extracted": images_result["saved"],
                "images_described": images_result["described"],
                "images_embedded": images_result["embeddings"],
                "text_chunks_embedded": embedded_chunks - images_result["embeddings"],
                "total_embedded": embedded_chunks,
                "type": category_clean,
            }
            if category_clean == "spec" and spec_id:
                result["specId"] = spec_id
            elif category_clean == "case" and spec_id:
                result["caseId"] = spec_id

            _upload_tasks[task_id] = {
                "status": "done",
                "step": "done",
                "message": "处理完成",
                "result": result,
                "started_at": _upload_tasks[task_id]["started_at"],
                "finished_at": time.time(),
            }

    except Exception as e:
        logger.error("Background upload failed for %s: %s\n%s", task_id, e, traceback.format_exc())
        _upload_tasks[task_id] = {
            "status": "error",
            "step": "error",
            "message": f"处理失败: {str(e)}",
            "started_at": _upload_tasks[task_id].get("started_at", time.time()),
            "finished_at": time.time(),
        }


async def _process_upload(
    file: UploadFile,
    category: str,
    project_type: Optional[str],
    vision_model: Optional[str],
    vision_api_key: Optional[str],
    vision_base_url: Optional[str],
    embedding_model: Optional[str],
    embedding_api_key: Optional[str],
    embedding_base_url: Optional[str],
    db: AsyncSession,
):
    """Core upload logic shared by all category branches."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    from app.models.document import Document, DocumentChunk
    from app.services.pdf_parsing_service import PDFParsingService

    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    safe_filename = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_filename

    try:
        content = await file.read()
        await asyncio.to_thread(_write_file, file_path, content)
    except Exception as e:
        logger.error("Failed to save uploaded file: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save file")

    # Parse PDF (sync method, run off-thread)
    parsed_data = None
    if ext == ".pdf":
        try:
            pdf_service = PDFParsingService()
            parsed_data = await asyncio.to_thread(pdf_service.parse_pdf, str(file_path))
            logger.info("PDF parsed: %s, pages: %s", file.filename, parsed_data['metadata']['page_count'])
        except Exception as e:
            logger.warning("Failed to parse PDF: %s", e)

    title = parsed_data["metadata"].get("title") if parsed_data else file.filename
    full_text = parsed_data["text"] if parsed_data else None

    category_clean = category.strip().lower() if isinstance(category, str) else category

    # Create Document record (shared for all categories)
    doc = Document(
        id=uuid.UUID(file_id),
        filename=file.filename,
        file_path=str(file_path),
        file_type=ext.replace(".", ""),
        file_size=len(content),
        title=title,
        project_type=project_type,
        category=category_clean,
        full_text=full_text if full_text else None,
        metadata_json=(parsed_data and parsed_data.get("metadata")) if parsed_data else None,
    )
    db.add(doc)
    await db.flush()

    # Batch-create chunks with single flush
    chunk_db_records = await _create_chunks_and_get_records(doc.id, parsed_data, db)

    # Category-specific record
    spec_or_case = None
    if category_clean == "spec":
        from app.models.specification import Specification
        spec_or_case = Specification(
            name=title,
            code=f"SPC-{file_id[:8]}",
            chapter=_get_first_section_title(parsed_data),
            section="",
            content=full_text[:50000] if full_text else "",
            project_types=[project_type] if project_type else None,
        )
        db.add(spec_or_case)
        await db.flush()
    elif category_clean == "case":
        from app.models.case import Case
        spec_or_case = Case(
            name=title,
            project_type=project_type or "未分类",
            location=(parsed_data and parsed_data.get("metadata", {}).get("location", "")) if parsed_data else "",
            owner="",
            summary=full_text[:2000] if full_text else "",
            design_params=(parsed_data and parsed_data.get("metadata")) if parsed_data else None,
        )
        db.add(spec_or_case)
        await db.flush()

    # Save images + vision descriptions + figure embeddings (parallelized)
    images_result = await _save_document_images(
        parsed_data, doc.id, file_id, chunk_db_records, db,
        vision_model=vision_model,
        vision_api_key=vision_api_key,
        vision_base_url=vision_base_url,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
    )

    # Text chunk embeddings (batch)
    text_chunks_embedded = await _embed_text_chunks(
        doc.id, db,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
    )

    # Single commit for everything
    await db.commit()

    spec_id = str(spec_or_case.id) if spec_or_case else None

    result = {
        "status": "success",
        "message": f'文件 "{file.filename}" 已上传并解析成功。',
        "fileId": file_id,
        "filename": file.filename,
        "size": len(content),
        "page_count": parsed_data["metadata"].get("page_count") if parsed_data else None,
        "chunks_stored": len(parsed_data["chunks"]) if parsed_data else 0,
        "images_extracted": images_result["saved"],
        "images_described": images_result["described"],
        "images_embedded": images_result["embeddings"],
        "text_chunks_embedded": text_chunks_embedded,
        "type": category_clean,
    }
    if category_clean == "spec" and spec_id:
        result["specId"] = spec_id
    elif category_clean == "case" and spec_id:
        result["caseId"] = spec_id

    return result


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form(default="planning", description="文档分类: planning/spec/case (规划/规范/案例)"),
    project_type: Optional[str] = Query(None, description="项目类型"),
    vision_model: Optional[str] = Form(None, description="视觉模型名称"),
    vision_api_key: Optional[str] = Form(None, description="视觉模型API密钥"),
    vision_base_url: Optional[str] = Form(None, description="视觉模型API地址"),
    embedding_model: Optional[str] = Form(None, description="Embedding模型名称"),
    embedding_api_key: Optional[str] = Form(None, description="Embedding API密钥"),
    embedding_base_url: Optional[str] = Form(None, description="Embedding API地址"),
    db: AsyncSession = Depends(get_db),
):
    """上传文件到知识库 — 立即返回 task_id，后台异步处理"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    task_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    safe_filename = f"{task_id}{ext}"
    file_path = UPLOAD_DIR / safe_filename

    content = await file.read()
    await asyncio.to_thread(_write_file, file_path, content)
    logger.info("Upload received: %s (%d bytes), task=%s", file.filename, len(content), task_id)

    # Fire-and-forget background task
    asyncio.create_task(_run_background_upload(
        task_id, file_path, file.filename, len(content), category, project_type,
        vision_model, vision_api_key, vision_base_url,
        embedding_model, embedding_api_key, embedding_base_url,
    ))

    return {
        "status": "accepted",
        "taskId": task_id,
        "message": f'文件 "{file.filename}" 已接收，正在后台处理...',
        "filename": file.filename,
        "size": len(content),
    }


@router.get("/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    """查询上传任务处理状态"""
    task = _upload_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/documents")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """获取已上传文档列表"""
    from app.models.document import Document
    stmt = select(Document).order_by(Document.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "category": doc.category,
            "size": doc.file_size,
            "page_count": (doc.metadata_json or {}).get("page_count") if doc.metadata_json else None,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in docs
    ]


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """删除文档及其所有关联数据（chunks、images、磁盘文件）"""
    import shutil
    from app.models.document import Document, DocumentChunk

    # 1. Get document record
    doc = await db.get(Document, uuid.UUID(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. Delete DocumentChunks (no FK cascade)
    await db.execute(
        DocumentChunk.__table__.delete().where(DocumentChunk.document_id == uuid.UUID(document_id))
    )

    # 3. Delete related Specification (code pattern: SPC-{first8})
    from app.models.specification import Specification
    await db.execute(
        Specification.__table__.delete().where(Specification.code == f"SPC-{document_id[:8]}")
    )

    # 4. Delete Document — DocumentImage cascades automatically via FK
    await db.delete(doc)
    await db.commit()

    # 5. Delete disk files
    if doc.file_path:
        fp = Path(doc.file_path)
        if fp.exists():
            fp.unlink()
    img_dir = UPLOAD_DIR / "images" / document_id
    if img_dir.exists():
        shutil.rmtree(img_dir, ignore_errors=True)

    logger.info("Document deleted: %s (%s)", doc.filename, document_id)
    return {"status": "success", "message": f'文件 "{doc.filename}" 已删除'}


@router.get("/documents/{document_id}/preview")
async def preview_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """获取文档文本预览（按页拆分）"""
    from app.models.document import Document
    doc = await db.get(Document, uuid.UUID(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    full_text = doc.full_text or ""
    page_count = (doc.metadata_json or {}).get("page_count") if doc.metadata_json else None

    if not full_text.strip():
        return {"title": doc.title, "filename": doc.filename, "page_count": page_count, "pages": []}

    import re
    parts = re.split(r"\n---\s*第\s*(\d+)\s*页\s*---\n", full_text)
    pages = []
    for i in range(1, len(parts), 2):
        page_num = int(parts[i]) if i < len(parts) else len(pages) + 1
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        pages.append({"page_num": page_num, "text": text})

    if not pages and full_text.strip():
        pages.append({"page_num": 1, "text": full_text.strip()})

    return {"title": doc.title, "filename": doc.filename, "page_count": page_count, "pages": pages}


@router.get("/documents/{document_id}/file")
async def download_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """下载/打开原始文件"""
    from app.models.document import Document
    doc = await db.get(Document, uuid.UUID(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    media_types = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "doc": "application/msword", "txt": "text/plain"}
    media_type = media_types.get(doc.file_type, "application/octet-stream")

    return FileResponse(path=str(file_path), media_type=media_type, filename=doc.filename)


@router.post("/specifications", response_model=SpecificationResponse, status_code=201)
async def ingest_specification(
    request: SpecificationIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.models.specification import Specification

    spec = Specification(
        name=request.name,
        code=request.code,
        chapter=request.chapter,
        section=request.section,
        content=request.content,
        project_types=request.project_types,
    )
    db.add(spec)
    await db.commit()
    await db.refresh(spec)

    try:
        vector_service = VectorStoreService(db)
        await vector_service.store_specification_embedding(spec.id)
    except Exception as e:
        logger.warning("Failed to generate specification embedding: %s", e)

    return SpecificationResponse.model_validate(spec)


@router.post("/cases", response_model=CaseResponse, status_code=201)
async def ingest_case(
    request: CaseIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.models.case import Case

    case = Case(
        name=request.name,
        project_type=request.project_type,
        location=request.location,
        owner=request.owner,
        summary=request.summary,
        design_params=request.design_params,
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)

    try:
        vector_service = VectorStoreService(db)
        await vector_service.store_case_embedding(case.id)
    except Exception as e:
        logger.warning("Failed to generate case embedding: %s", e)

    return CaseResponse.model_validate(case)


@router.get("/specifications", response_model=List[SpecificationResponse])
async def list_specifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.models.specification import Specification

    stmt = select(Specification).offset(skip).limit(limit).order_by(Specification.created_at.desc())
    result = await db.execute(stmt)
    specs = result.scalars().all()
    return [SpecificationResponse.model_validate(s) for s in specs]


@router.get("/cases", response_model=List[CaseResponse])
async def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.models.case import Case

    stmt = select(Case).offset(skip).limit(limit).order_by(Case.created_at.desc())
    result = await db.execute(stmt)
    cases = result.scalars().all()
    return [CaseResponse.model_validate(c) for c in cases]


@router.get("/search", response_model=List[RetrievalResult])
async def search_knowledge(
    query: str = Query(..., min_length=1),
    project_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    vector_service = VectorStoreService(db)
    specs, cases, chunks = await asyncio.gather(
        vector_service.search_similar_specifications(query=query, top_k=5, project_type=project_type),
        vector_service.search_similar_cases(query=query, top_k=5, project_type=project_type),
        vector_service.search_document_chunks(query=query, top_k=5),
    )
    results = []
    for s in specs:
        results.append(RetrievalResult(
            source="specification",
            title=f"{s['code']} {s['name']}",
            content=s["content"][:500],
            relevance_score=s["similarity"],
            metadata={"chapter": s["chapter"], "section": s.get("section", "")},
        ))
    for c in cases:
        results.append(RetrievalResult(
            source="case",
            title=c["name"],
            content=c.get("summary", ""),
            relevance_score=c["similarity"],
            metadata={"project_type": c["project_type"], "location": c["location"]},
        ))
    for ch in chunks:
        metadata: dict = {
            "document_id": ch["document_id"],
            "page": ch["page"],
            "chunk_type": ch.get("chunk_type", ""),
            "filename": ch.get("filename", ""),
            "doc_title": ch.get("doc_title", ""),
        }
        if ch.get("image_path"):
            metadata["image_path"] = ch["image_path"]
            metadata["image_description"] = ch.get("image_description", "")
            img_rel = ch["image_path"].replace("\\", "/")
            if img_rel.startswith("uploads/"):
                img_rel = img_rel[len("uploads/"):]
            metadata["image_url"] = f"/api/v1/knowledge-base/images/{ch['document_id']}/page/{ch['page']}/img/{ch['chunk_index'] - 9990}"
        results.append(RetrievalResult(
            source=ch.get("chunk_type", "document_chunk"),
            title=ch.get("doc_title") or ch.get("filename", ""),
            content=ch["text"][:500],
            relevance_score=ch["similarity"],
            metadata=metadata,
        ))
    results.sort(key=lambda r: r.relevance_score, reverse=True)
    return results


@router.get("/wiki", response_model=List[WikiItemResponse])
async def list_wiki_items(
    category: Optional[str] = Query(None),
    project_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    mining_service = KnowledgeMiningService(db)
    items = await mining_service.get_wiki_items(category=category, project_type=project_type, limit=limit)
    return [WikiItemResponse.model_validate(item) for item in items]


@router.get("/wiki/search", response_model=List[RetrievalResult])
async def search_wiki(
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    mining_service = KnowledgeMiningService(db)
    results = await mining_service.search_wiki(query=query, top_k=top_k)

    return [
        RetrievalResult(
            source="wiki",
            title=r.get("title", ""),
            content=r.get("content", "")[:500],
            relevance_score=r.get("similarity", 0),
            metadata={
                "category": r.get("category", ""),
                "tags": r.get("tags", []),
                "source_chapter": r.get("source_chapter", ""),
            },
        )
        for r in results
    ]


@router.post("/wiki/{item_id}/verify")
async def verify_wiki_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from app.models.wiki import WikiItem

    stmt = select(WikiItem).where(WikiItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Wiki item not found")

    item.is_verified = True
    await db.commit()

    return {"status": "success", "message": "Wiki item verified"}


@router.get("/wiki/export", response_model=WikiExportResponse)
async def export_wiki(
    category: Optional[str] = Query(None),
    project_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    mining_service = KnowledgeMiningService(db)
    items = await mining_service.get_wiki_items(category=category, project_type=project_type, limit=1000)

    categories = list(set(item.category for item in items))

    return WikiExportResponse(
        items=[WikiItemResponse.model_validate(item) for item in items],
        total_count=len(items),
        categories=categories
    )


# ========== 文档图片接口 ==========

@router.get("/images/{document_id}")
async def list_document_images(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(DocumentImage)
        .where(DocumentImage.document_id == document_id)
        .order_by(DocumentImage.page, DocumentImage.image_index)
    )
    result = await db.execute(stmt)
    images = result.scalars().all()

    return [
        {
            "id": str(img.id),
            "page": img.page,
            "image_index": img.image_index,
            "x": img.x,
            "y": img.y,
            "width": img.width,
            "height": img.height,
            "context_text": img.context_text[:500] if img.context_text else None,
            "description": img.description,
            "linked_chunk_id": str(img.linked_chunk_id) if img.linked_chunk_id else None,
        }
        for img in images
    ]


@router.get("/images/{document_id}/page/{page}/img/{image_index}")
async def serve_document_image(
    document_id: uuid.UUID,
    page: int,
    image_index: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DocumentImage).where(
        DocumentImage.document_id == document_id,
        DocumentImage.page == page,
        DocumentImage.image_index == image_index,
    )
    result = await db.execute(stmt)
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = Path(img.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type="image/png",
        filename=f"doc_{document_id}_page{page}_img{image_index}.png",
    )
