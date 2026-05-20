import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.report import (
    InteractiveReportStartRequest,
    InteractiveReportStartResponse,
    InteractiveReportStatusResponse,
    ChapterConfirmRequest,
    ChapterConfirmResponse,
    SupplyInfoRequest,
    SupplyInfoResponse,
    ProjectInfo,
)
from app.services.report_service import ReportService
from app.core.interactive_task_queue import interactive_task_queue
from app.core.report_state import ReportPhase, InputRequestType, ChapterState

router = APIRouter(prefix="/projects/{project_id}/interactive", tags=["interactive_report"])


@router.post("/start", response_model=InteractiveReportStartResponse)
async def start_interactive_report(
    project_id: uuid.UUID,
    request: InteractiveReportStartRequest,
    db: AsyncSession = Depends(get_db)
):
    """启动交互式报告生成"""
    service = ReportService(db)

    task_id = await service.start_interactive_report(
        project_id=project_id,
        report_type=request.report_type,
        project_info=request.project_info
    )

    return InteractiveReportStartResponse(
        task_id=task_id,
        phase=ReportPhase.RETRIEVING.value,
        total_chapters=len(ReportService.CHAPTER_ORDER),
        chapter_names=ReportService.CHAPTER_ORDER
    )


@router.get("/{task_id}/chapter-stream")
async def stream_chapter(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """SSE流式输出章节生成内容"""
    service = ReportService(db)
    itask = interactive_task_queue.get_task(task_id)

    if not itask:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        try:
            # 获取项目ID
            itask = interactive_task_queue.get_task(task_id)
            proj_id = itask.project_id if itask else None

            # 第一阶段：检索知识库
            specs, cases, materials = [], [], []

            async for retrieval_event in service.interactive_retrieve_knowledge(task_id, ProjectInfo(
                name="项目",
                location="",
                owner="",
                scale="",
                description=""
            ), proj_id):
                yield f"data: {json.dumps(retrieval_event, ensure_ascii=False)}\n\n"

                if retrieval_event.get("type") == "retrieving_progress" and retrieval_event.get("progress", 0) == 100:
                    itask = interactive_task_queue.get_task(task_id)
                    if itask:
                        specs = itask.retrieved_specs
                        cases = itask.retrieved_cases
                        materials = getattr(itask, "retrieved_materials", [])

            # 第二阶段：按章节生成
            current_chapter_index = itask.current_chapter_index if itask else 0
            project_info = ProjectInfo(
                name="水利工程项目",
                location="",
                owner="",
                scale="",
                description=""
            )

            while current_chapter_index < len(ReportService.CHAPTER_ORDER):
                # 检查是否所有章节都完成
                itask = interactive_task_queue.get_task(task_id)
                if not itask:
                    break

                chapter_name = ReportService.CHAPTER_ORDER[current_chapter_index]
                chapter_ctx = itask.chapters.get(chapter_name)

                # 如果章节已完成或确认过，跳到下一章
                if chapter_ctx and chapter_ctx.status.value in ["complete", "confirmed"]:
                    current_chapter_index += 1
                    continue

                # 获取可能的修订备注
                revision_note = chapter_ctx.revision_note if chapter_ctx else None

                # 流式生成章节
                async for gen_event in service.interactive_generate_chapter_stream(
                    task_id=task_id,
                    chapter_index=current_chapter_index,
                    specs=specs,
                    cases=cases,
                    materials=materials,
                    project_info=project_info,
                    revision_note=revision_note
                ):
                    yield f"data: {json.dumps(gen_event, ensure_ascii=False)}\n\n"

                    # 检查是否所有章节完成
                    if gen_event.get("type") == "all_chapters_complete":
                        # 渲染Word文档
                        try:
                            output_path = await service.render_interactive_report(task_id, project_info)
                            yield f"data: {json.dumps({'type': 'report_rendered', 'output_path': output_path}, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            yield f"data: {json.dumps({'type': 'error', 'message': f'渲染失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                        return

                    # 检查是否需要用户输入
                    if gen_event.get("type") == "need_input":
                        # 等待用户提供输入
                        pass

                    # 更新章节索引（当章节完成且用户确认后）
                    if gen_event.get("type") == "awaiting_confirmation":
                        itask = interactive_task_queue.get_task(task_id)
                        if itask:
                            itask.current_chapter_index = current_chapter_index + 1
                        break

                # 更新当前章节索引
                itask = interactive_task_queue.get_task(task_id)
                if itask:
                    itask.current_chapter_index = current_chapter_index + 1
                current_chapter_index += 1

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@router.get("/{task_id}/status", response_model=InteractiveReportStatusResponse)
async def get_interactive_status(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取交互式报告生成状态"""
    status = interactive_task_queue.get_status(task_id)

    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="任务不存在")

    return InteractiveReportStatusResponse(
        task_id=uuid.UUID(status["task_id"]),
        phase=status["phase"],
        current_chapter_index=status["current_chapter_index"],
        current_chapter=status.get("current_chapter"),
        chapters=status.get("chapters", {}),
        progress=0,  # TODO: 计算实际进度
        error=status.get("error")
    )


@router.post("/{task_id}/confirm", response_model=ChapterConfirmResponse)
async def confirm_chapter(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    request: ChapterConfirmRequest,
    db: AsyncSession = Depends(get_db)
):
    """确认或修改当前章节"""
    itask = interactive_task_queue.get_task(task_id)

    if not itask:
        raise HTTPException(status_code=404, detail="任务不存在")

    if request.action == "confirm":
        interactive_task_queue.confirm_chapter(task_id, request.revision_note)
        next_chapter = None
        if itask.current_chapter_index < len(ReportService.CHAPTER_ORDER) - 1:
            next_chapter = ReportService.CHAPTER_ORDER[itask.current_chapter_index + 1]

        return ChapterConfirmResponse(
            status="continued",
            next_chapter=next_chapter,
            all_completed=False
        )
    else:
        interactive_task_queue.request_revision(task_id, request.revision_note or "")
        return ChapterConfirmResponse(
            status="revision_requested",
            next_chapter=ReportService.CHAPTER_ORDER[itask.current_chapter_index],
            all_completed=False
        )


@router.post("/{task_id}/supply-info", response_model=SupplyInfoResponse)
async def supply_info(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    request: SupplyInfoRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户提供补充资料"""
    itask = interactive_task_queue.get_task(task_id)

    if not itask:
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        info_type = InputRequestType(request.info_type)
    except ValueError:
        info_type = InputRequestType.OTHER

    interactive_task_queue.provide_input(task_id, info_type, request.content or "")

    return SupplyInfoResponse(
        status="received",
        continue_generation=True
    )


@router.get("/{task_id}/chapters")
async def get_chapters_status(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取所有章节状态"""
    itask = interactive_task_queue.get_task(task_id)

    if not itask:
        raise HTTPException(status_code=404, detail="任务不存在")

    chapters = []
    for name, ctx in itask.chapters.items():
        chapters.append({
            "name": name,
            "index": ctx.index,
            "status": ctx.status.value,
            "confirmed": ctx.confirmed,
            "revision_count": ctx.revision_count,
            "content": ctx.content if ctx.status == ChapterState.COMPLETE else "",
            "pending_inputs": [
                {"type": inp.info_type.value, "description": inp.description, "provided": inp.provided}
                for inp in ctx.pending_inputs
            ]
        })

    return {
        "current_chapter_index": itask.current_chapter_index,
        "phase": itask.phase.value,
        "chapters": chapters
    }


@router.post("/{task_id}/render")
async def render_report(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """手动渲染报告为Word文档"""
    itask = interactive_task_queue.get_task(task_id)

    if not itask:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查所有章节是否完成
    incomplete = [
        name for name, ctx in itask.chapters.items()
        if not ctx.confirmed
    ]

    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"以下章节尚未确认: {', '.join(incomplete)}"
        )

    service = ReportService(db)
    project_info = ProjectInfo(
        name="水利工程项目",
        location="",
        owner="",
        scale="",
        description=""
    )

    try:
        output_path = await service.render_interactive_report(task_id, project_info)
        return {"status": "success", "output_path": output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))