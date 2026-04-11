import uuid
import magic
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.terrain import Terrain
from app.schemas.terrain import TerrainUploadResponse
from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.dxf_parser import DXFParser
from app.core.exceptions import (
    FileTooLargeException,
    InvalidFileTypeException,
    NoFeatureExtractedException
)


ALLOWED_FILE_TYPES = {"csv", "dxf"}
ALLOWED_MAGIC_NUMBERS = {
    "csv": None,  # CSV无魔数
    "dxf": b"AutoCAD",  # DXF文件头
}
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB


class TerrainService:
    """地形数据解析服务"""

    def __init__(self, db: AsyncSession, upload_dir: str = "uploads"):
        self.db = db
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_and_parse(
        self,
        project_id: uuid.UUID,
        file_content: bytes,
        filename: str
    ) -> TerrainUploadResponse:
        """上传并解析地形文件"""
        # 1. 验证文件
        self._validate_file(file_content, filename)

        # 2. 保存原始文件
        file_path = await self._save_file(project_id, filename, file_content)

        # 3. 创建Terrain记录
        terrain = Terrain(
            project_id=project_id,
            file_path=str(file_path),
            file_type=filename.rsplit(".", 1)[-1].upper(),
            status="processing"
        )
        self.db.add(terrain)
        await self.db.commit()
        await self.db.refresh(terrain)

        # 4. 解析文件
        features = {}
        try:
            features = await self._parse_file(file_path, terrain.file_type)
            await self._update_terrain_features(terrain, features)
            terrain.status = "completed"
        except Exception as e:
            terrain.status = "failed"
            terrain.error_message = str(e)
        finally:
            await self.db.commit()
            await self.db.refresh(terrain)

        return self._build_response(terrain, features)

    def _validate_file(self, content: bytes, filename: str) -> None:
        """验证文件大小、类型和魔数"""
        # 大小检查
        if len(content) > MAX_FILE_SIZE:
            raise FileTooLargeException(max_size=MAX_FILE_SIZE, actual_size=len(content))

        # 类型检查
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_FILE_TYPES:
            raise InvalidFileTypeException(file_type=ext, allowed_types=list(ALLOWED_FILE_TYPES))

        # 魔数检查（针对DXF）
        if ext == "dxf":
            if not content.startswith(ALLOWED_MAGIC_NUMBERS["dxf"]):
                raise InvalidFileTypeException(file_type="DXF", allowed_types=["DXF"])

    async def _save_file(
        self,
        project_id: uuid.UUID,
        filename: str,
        content: bytes
    ) -> Path:
        """保存文件到上传目录"""
        project_dir = self.upload_dir / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        file_path = project_dir / unique_name

        with open(file_path, "wb") as f:
            f.write(content)

        return file_path

    async def _parse_file(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """解析文件提取特征"""
        if file_type.upper() == "CSV":
            parser = CSVParser(file_path)
        elif file_type.upper() == "DXF":
            parser = DXFParser(file_path)
        else:
            raise InvalidFileTypeException(file_type=file_type, allowed_types=["CSV", "DXF"])

        # 流式解析
        list(parser.parse())

        # 提取特征
        features = {
            "centerline": parser.extract_centerline(),
            "cross_sections": parser.extract_cross_sections(),
            "elevation_range": parser.extract_elevation_range(),
            "slope_analysis": parser.extract_slope_analysis(),
            "waterfront_line": None,
            "demolition_boundary": None,
            "farmland_boundary": None,
        }

        return features

    async def _update_terrain_features(
        self,
        terrain: Terrain,
        features: Dict[str, Any]
    ) -> None:
        """更新Terrain记录的特征"""
        terrain.cross_sections = features["cross_sections"]
        terrain.elevation_range = features["elevation_range"]
        terrain.slope_analysis = features["slope_analysis"]
        terrain.feature_count = sum(
            len(f) for f in features.values()
            if f and isinstance(f, (list, dict))
        )

    def _build_response(
        self,
        terrain: Terrain,
        features: Optional[Dict[str, Any]] = None
    ) -> TerrainUploadResponse:
        """构建响应"""
        warning = None
        if terrain.status == "completed" and features:
            # 检查是否有缺失特征
            missing = [
                k for k, v in features.items()
                if v is None and k not in ["waterfront_line", "demolition_boundary", "farmland_boundary"]
            ]
            if missing:
                warning = {
                    "code": "PARTIAL_PARSING",
                    "message": "部分特征提取成功，以下特征缺失",
                    "missing_features": missing,
                    "extracted_features": [k for k, v in features.items() if v is not None]
                }

        return TerrainUploadResponse(
            id=terrain.id,
            project_id=terrain.project_id,
            file_type=terrain.file_type,
            status=terrain.status,
            features=features,
            bounds=None,
            feature_count=terrain.feature_count,
            warning=warning
        )

    async def get_terrain_status(self, project_id: uuid.UUID) -> Optional[Terrain]:
        """获取项目地形状态"""
        result = await self.db.execute(
            select(Terrain).where(Terrain.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def reparse(self, project_id: uuid.UUID) -> TerrainUploadResponse:
        """重新解析地形文件"""
        terrain = await self.get_terrain_status(project_id)
        if not terrain:
            raise NoFeatureExtractedException(
                file_type="unknown",
                expected_content="Terrain record",
                found_entities=[]
            )

        if not Path(terrain.file_path).exists():
            raise FileNotFoundError(f"原始文件不存在: {terrain.file_path}")

        # 重新解析
        terrain.status = "processing"
        await self.db.commit()

        features = {}
        try:
            features = await self._parse_file(Path(terrain.file_path), terrain.file_type)
            await self._update_terrain_features(terrain, features)
            terrain.status = "completed"
        except Exception as e:
            terrain.status = "failed"
            terrain.error_message = str(e)

        await self.db.commit()
        await self.db.refresh(terrain)

        return self._build_response(terrain, features)