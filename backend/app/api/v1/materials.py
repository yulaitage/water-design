import asyncio
import logging
import re
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from pathlib import Path

from app.db.database import get_db
from app.models.document import Document, DocumentChunk
from app.models.document_image import DocumentImage
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/materials", tags=["materials"])

UPLOAD_DIR = Path("uploads/knowledge_base")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _delete_document_cascade(doc_id: uuid.UUID, db: AsyncSession):
    """Delete document and all related records."""
    # Delete chunks (no FK cascade)
    await db.execute(text("DELETE FROM document_chunks WHERE document_id = :did"), {"did": str(doc_id)})
    await db.flush()
    # Delete images (has FK cascade, but delete explicitly for clarity)
    await db.execute(text("DELETE FROM document_images WHERE document_id = :did"), {"did": str(doc_id)})
    await db.flush()


@router.post("/upload")
async def upload_material(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    vision_model: Optional[str] = Form(None),
    vision_api_key: Optional[str] = Form(None),
    vision_base_url: Optional[str] = Form(None),
    embedding_model: Optional[str] = Form(None),
    embedding_api_key: Optional[str] = Form(None),
    embedding_base_url: Optional[str] = Form(None),
):
    """上传素材到项目素材库"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Import shared upload machinery from knowledge_base
    from app.api.v1.knowledge_base import (
        _upload_tasks, _write_file, _run_background_upload,
    )

    task_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    safe_filename = f"{task_id}{ext}"
    file_path = UPLOAD_DIR / safe_filename

    content = await file.read()
    await asyncio.to_thread(_write_file, file_path, content)
    logger.info("Material upload: %s (%d bytes), project=%s, task=%s", file.filename, len(content), project_id, task_id)

    asyncio.create_task(_run_background_upload(
        task_id, file_path, file.filename, len(content), "material", None,
        project_id=str(project_id),
        vision_model=vision_model, vision_api_key=vision_api_key, vision_base_url=vision_base_url,
        embedding_model=embedding_model, embedding_api_key=embedding_api_key, embedding_base_url=embedding_base_url,
    ))

    return {
        "status": "accepted",
        "taskId": task_id,
        "message": f'素材 "{file.filename}" 已接收，正在后台处理...',
        "filename": file.filename,
        "size": len(content),
    }


@router.get("/upload/status/{task_id}")
async def get_material_upload_status(task_id: str):
    """查询素材上传任务状态"""
    from app.api.v1.knowledge_base import _upload_tasks
    task = _upload_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/")
async def list_materials(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """列出项目素材"""
    stmt = (
        select(Document)
        .where(Document.project_id == project_id, Document.category == "material")
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()

    return {
        "materials": [
            {
                "id": str(d.id),
                "filename": d.filename,
                "title": d.title,
                "size": d.file_size,
                "page_count": (d.metadata_json or {}).get("page_count") if d.metadata_json else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
        "total": len(docs),
    }


@router.delete("/{document_id}")
async def delete_material(document_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """删除项目素材"""
    doc = await db.get(Document, document_id)
    if not doc or doc.project_id != project_id or doc.category != "material":
        raise HTTPException(status_code=404, detail="Material not found")

    await _delete_document_cascade(document_id, db)
    await db.delete(doc)

    # Delete disk files
    try:
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()
        image_dir = file_path.parent / "images" / str(document_id)
        if image_dir.exists():
            import shutil
            shutil.rmtree(image_dir, ignore_errors=True)
    except Exception as e:
        logger.warning("Failed to delete disk files: %s", e)

    await db.commit()
    return {"status": "ok"}


@router.get("/{document_id}/preview")
async def preview_material(document_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取素材文本预览"""
    doc = await db.get(Document, document_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status_code=404, detail="Material not found")

    full_text = doc.full_text or ""
    page_count = (doc.metadata_json or {}).get("page_count") if doc.metadata_json else None

    if not full_text.strip():
        return {"title": doc.title, "filename": doc.filename, "page_count": page_count, "pages": []}

    parts = re.split(r"\n---\s*第\s*(\d+)\s*页\s*---\n", full_text)
    pages = []
    for i in range(1, len(parts), 2):
        page_num = int(parts[i]) if i < len(parts) else len(pages) + 1
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        pages.append({"page_num": page_num, "text": text})

    if not pages and full_text.strip():
        pages.append({"page_num": 1, "text": full_text.strip()})

    return {"title": doc.title, "filename": doc.filename, "page_count": page_count, "pages": pages}


@router.get("/{document_id}/images")
async def list_material_images(document_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """列出素材中的图片"""
    doc = await db.get(Document, document_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status_code=404, detail="Material not found")

    stmt = select(DocumentImage).where(DocumentImage.document_id == document_id).order_by(DocumentImage.page, DocumentImage.image_index)
    result = await db.execute(stmt)
    images = result.scalars().all()
    return [
        {
            "id": str(img.id),
            "page": img.page,
            "image_index": img.image_index,
            "description": img.description,
        }
        for img in images
    ]


@router.get("/search")
async def search_materials(
    project_id: uuid.UUID,
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(10, description="返回数量"),
    db: AsyncSession = Depends(get_db),
):
    """在项目素材中搜索"""
    vs = VectorStoreService(db)
    results = await vs.search_material_chunks(q, project_id, top_k)
    return {"results": results, "total": len(results)}
