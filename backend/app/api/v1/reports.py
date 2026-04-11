import uuid
from fastapi import APIRouter, Depends, Path, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.report_service import ReportService
from app.schemas.report import (
    ReportCreateRequest,
    ReportTaskResponse,
    ReportStatusResponse,
    RevisionRequest,
    RevisionResponse,
    RevisionHistoryResponse,
    RevisionHistoryItem
)
from app.core.task_queue import task_queue

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])


@router.post("", response_model=ReportTaskResponse, status_code=202)
async def create_report(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    request: ReportCreateRequest = ...,
    db: AsyncSession = Depends(get_db)
):
    """创建报告生成任务"""
    service = ReportService(db)
    task = await service.create_report_task(project_id, request)

    # 启动后台生成
    # 注意：实际需要任务队列处理，这里简化
    return ReportTaskResponse(
        task_id=task.id,
        status=task.status,
        report_type=task.report_type,
        version=task.version
    )


@router.get("/{task_id}/status", response_model=ReportStatusResponse)
async def get_report_status(
    project_id: uuid.UUID = Path(...),
    task_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db)
):
    """查询报告生成状态"""
    # 先查任务队列
    task_info = task_queue.get_task(task_id)
    if task_info:
        return ReportStatusResponse(
            task_id=task_id,
            status=task_info.status.value,
            progress=task_info.progress,
            current_chapter=task_info.current_step,
            version=1,
            error=task_info.error
        )

    # 查数据库
    service = ReportService(db)
    from app.models.report import ReportTask
    from sqlalchemy import select
    stmt = select(ReportTask).where(ReportTask.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        return ReportStatusResponse(
            task_id=task_id,
            status="not_found",
            progress=0,
            version=1
        )

    return ReportStatusResponse(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        current_chapter=task.current_chapter,
        version=task.version,
        error=task.error_message
    )


@router.get("/{task_id}/download")
async def download_report(
    project_id: uuid.UUID = Path(...),
    task_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db)
):
    """下载报告Word文档"""
    service = ReportService(db)
    from app.models.report import ReportTask
    from sqlalchemy import select
    stmt = select(ReportTask).where(ReportTask.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task or not task.output_path:
        return {"error": "报告尚未生成"}

    return FileResponse(
        path=task.output_path,
        filename=f"report_{task_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.post("/{task_id}/revisions", response_model=RevisionResponse, status_code=202)
async def submit_revision(
    project_id: uuid.UUID = Path(...),
    task_id: uuid.UUID = Path(...),
    request: RevisionRequest = ...,
    db: AsyncSession = Depends(get_db)
):
    """提交修订意见"""
    service = ReportService(db)
    revision = await service.submit_revision(task_id, request)
    return RevisionResponse(
        revision_id=revision.id,
        version=revision.version,
        status="pending"
    )


@router.get("/{task_id}/revisions", response_model=RevisionHistoryResponse)
async def get_revision_history(
    project_id: uuid.UUID = Path(...),
    task_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db)
):
    """获取修订历史"""
    service = ReportService(db)
    revisions = await service.get_revision_history(task_id)
    return RevisionHistoryResponse(
        revisions=[
            RevisionHistoryItem(
                version=r.version,
                created_at=r.created_at,
                revision_type=r.revision_type,
                user_input=r.user_input
            )
            for r in revisions
        ]
    )