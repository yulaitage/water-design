import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.terrain_service import TerrainService
from app.schemas.terrain import TerrainUploadResponse, TerrainResponse, TerrainStatus

router = APIRouter(prefix="/projects/{project_id}/terrain", tags=["terrain"])


@router.post("", response_model=TerrainUploadResponse)
async def upload_terrain(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    file: UploadFile = File(..., description="地形文件(CSV/DXF)"),
    db: AsyncSession = Depends(get_db)
):
    """
    上传并解析地形文件

    - 支持CSV和DXF格式
    - 流式处理，无文件大小限制
    - 提取7种地形特征
    """
    content = await file.read()
    service = TerrainService(db)
    return await service.upload_and_parse(project_id, content, file.filename)


@router.get("", response_model=TerrainResponse | None)
async def get_terrain(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取项目地形数据"""
    service = TerrainService(db)
    terrain = await service.get_terrain_status(project_id)
    if not terrain:
        return None
    return TerrainResponse(
        id=terrain.id,
        project_id=terrain.project_id,
        file_type=terrain.file_type,
        status=terrain.status,
        bounds=None,
        feature_count=terrain.feature_count
    )


@router.get("/status", response_model=TerrainStatus)
async def get_terrain_status(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取地形解析状态"""
    service = TerrainService(db)
    terrain = await service.get_terrain_status(project_id)

    if not terrain:
        return TerrainStatus(status="pending", progress=0)

    progress_map = {
        "pending": 0,
        "processing": 50,
        "completed": 100,
        "failed": 0
    }

    return TerrainStatus(
        status=terrain.status,
        progress=progress_map.get(terrain.status, 0)
    )


@router.post("/reparse", response_model=TerrainUploadResponse)
async def reparse_terrain(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_db)
):
    """重新解析地形文件"""
    service = TerrainService(db)
    return await service.reparse(project_id)