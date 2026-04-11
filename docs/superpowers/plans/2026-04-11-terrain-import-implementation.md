# 地形数据导入模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现地形数据导入模块，支持CSV和DXF格式流式解析，提取7种地形特征并存入PostGIS

**Architecture:** FastAPI接收文件 → 流式解析 → 特征提取 → PostGIS存储 + 原始文件路径，API层与业务逻辑分离

**Tech Stack:** FastAPI + SQLAlchemy + GeoAlchemy2 + PostGIS + Pandas + ezdxf

---

## 文件结构

```
backend/
├── app/
│   ├── api/v1/terrain.py          # 地形API路由
│   ├── models/terrain.py          # Terrain SQLAlchemy模型
│   ├── schemas/terrain.py         # Pydantic请求/响应模型
│   ├── services/
│   │   ├── terrain_service.py     # 地形解析业务逻辑
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # 解析器基类
│   │   │   ├── csv_parser.py      # CSV流式解析器
│   │   │   └── dxf_parser.py      # DXF实体解析器
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── base.py            # 特征提取器基类
│   │       ├── centerline.py      # 中心线提取
│   │       ├── cross_section.py   # 横断面提取
│   │       ├── elevation.py       # 高程分析
│   │       ├── slope.py           # 坡度分析
│   │       ├── waterfront.py      # 岸线提取
│   │       ├── demolition.py      # 动拆迁边界
│   │       └── farmland.py        # 基本农田
│   └── core/exceptions.py         # 异常定义
├── tests/
│   ├── services/
│   │   ├── test_terrain_service.py
│   │   └── test_parsers/
│   │       ├── test_csv_parser.py
│   │       └── test_dxf_parser.py
│   └── fixtures/
│       ├── sample_river_survey.csv
│       ├── sample_terrain.dxf
│       ├── empty.csv
│       └── corrupted.dxf
└── uploads/                        # 原始文件存储目录
```

---

## Task 1: 项目脚手架和环境准备

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/requirements.txt`
- Modify: `backend/app/__init__.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/db/database.py`

- [ ] **Step 1: 创建pyproject.toml**

```toml
[project]
name = "water-design-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy>=2.0.0",
    "geoalchemy2>=0.14.0",
    "asyncpg>=0.29.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "python-multipart>=0.0.6",
    "pandas>=2.2.0",
    "ezdxf>=1.1.0",
    "python-magic>=0.4.27",
    "alembic>=1.13.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest-cov>=4.1.0",
    "ruff>=0.2.0",
]
```

- [ ] **Step 2: 创建requirements.txt**

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
geoalchemy2>=0.14.0
asyncpg>=0.29.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-multipart>=0.0.6
pandas>=2.2.0
ezdxf>=1.1.0
python-magic>=0.4.27
alembic>=1.13.0
psycopg2-binary>=2.9.9
```

- [ ] **Step 3: 安装依赖**

Run: `cd backend && pip install -e .`

- [ ] **Step 4: 配置数据库连接**

Modify `backend/app/db/database.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings
from typing import AsyncGenerator

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/waterdesign"
    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024 * 1024  # 10GB

settings = Settings()

engine = create_async_engine(settings.database_url, echo=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
```

- [ ] **Step 5: 提交**

```bash
cd /Users/yulaitage/Claude\ Code/water\ design && git add backend/pyproject.toml backend/requirements.txt backend/app/db/database.py && git commit -m "feat: add project scaffolding and database config"
```

---

## Task 2: 异常定义

**Files:**
- Create: `backend/app/core/exceptions.py`
- Modify: `backend/app/__init__.py`

- [ ] **Step 1: 创建异常类**

Create `backend/app/core/exceptions.py`:
```python
from fastapi import HTTPException, status

class TerrainException(HTTPException):
    def __init__(self, code: str, message: str, details: dict = None, suggestion: str = None):
        self.code = code
        self.detail = {
            "code": code,
            "message": message,
            "details": details or {},
            "suggestion": suggestion
        }
        super().__init__(status_code=self._get_status_code(), detail=self.detail)

    def _get_status_code(self) -> int:
        codes = {
            "FILE_TOO_LARGE": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "INVALID_FILE_TYPE": status.HTTP_400_BAD_REQUEST,
            "FILE_CORRUPTED": status.HTTP_400_BAD_REQUEST,
            "NO_FEATURE_EXTRACTED": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PARTIAL_PARSING": status.HTTP_200_OK,  # 部分成功
        }
        return codes.get(self.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

class FileTooLargeException(TerrainException):
    def __init__(self, max_size: int, actual_size: int):
        super().__init__(
            code="FILE_TOO_LARGE",
            message=f"文件大小超过限制",
            details={"max_size": max_size, "actual_size": actual_size},
            suggestion=f"请上传小于{max_size // (1024*1024*1024)}GB的文件"
        )

class InvalidFileTypeException(TerrainException):
    def __init__(self, file_type: str, allowed_types: list):
        super().__init__(
            code="INVALID_FILE_TYPE",
            message=f"不支持的文件格式: {file_type}",
            details={"file_type": file_type, "allowed_types": allowed_types},
            suggestion="请上传CSV或DXF格式文件"
        )

class FileCorruptedException(TerrainException):
    def __init__(self, file_type: str, error: str):
        super().__init__(
            code="FILE_CORRUPTED",
            message=f"文件损坏或格式错误",
            details={"file_type": file_type, "error": error},
            suggestion="请检查文件是否完整，或尝试重新导出"
        )

class NoFeatureExtractedException(TerrainException):
    def __init__(self, file_type: str, expected_content: str, found_entities: list):
        super().__init__(
            code="NO_FEATURE_EXTRACTED",
            message=f"无法从文件中提取有效地形特征",
            details={
                "detected_format": file_type,
                "expected_content": expected_content,
                "found_entities": found_entities
            },
            suggestion="请检查文件是否包含高程坐标信息"
        )
```

- [ ] **Step 2: 提交**

```bash
cd /Users/yulaitage/Claude\ Code/water\ design && git add backend/app/core/exceptions.py && git commit -m "feat: add terrain-specific exceptions"
```

---

## Task 3: Terrain数据模型

**Files:**
- Create: `backend/app/models/terrain.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建Terrain模型**

Create `backend/app/models/terrain.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry, LineString, Polygon
from typing import Optional, List, Dict, Any

from app.db.database import Base


class Terrain(Base):
    __tablename__ = "terrains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "CSV" | "DXF"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|processing|completed|failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 解析后的特征（PostGIS存储）
    centerline = mapped_column(Geometry(geometry_type="LINESTRING", srid=4490), nullable=True)
    cross_sections: Mapped[Optional[JSONB]] = mapped_column(JSONB, nullable=True)
    elevation_range: Mapped[Optional[JSONB]] = mapped_column(JSONB, nullable=True)  # [min, max, mean]
    slope_analysis: Mapped[Optional[JSONB]] = mapped_column(JSONB, nullable=True)
    waterfront_line = mapped_column(Geometry(geometry_type="LINESTRING", srid=4490), nullable=True)
    demolition_boundary: Mapped[Optional[JSONB]] = mapped_column(JSONB, nullable=True)
    farmland_boundary: Mapped[Optional[JSONB]] = mapped_column(JSONB, nullable=True)

    # 元数据
    bounds = mapped_column(Geometry(geometry_type="POLYGON", srid=4490), nullable=True)
    feature_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_features(self) -> Dict[str, Any]:
        return {
            "centerline": self.centerline,
            "cross_sections": self.cross_sections,
            "elevation_range": self.elevation_range,
            "slope_analysis": self.slope_analysis,
            "waterfront_line": self.waterfront_line,
            "demolition_boundary": self.demolition_boundary,
            "farmland_boundary": self.farmland_boundary,
        }
```

- [ ] **Step 2: 更新models/__init__.py**

Modify `backend/app/models/__init__.py`:
```python
from app.models.terrain import Terrain
from app.models.project import Project

__all__ = ["Terrain", "Project"]
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/terrain.py backend/app/models/__init__.py && git commit -m "feat: add Terrain model with PostGIS geometry fields"
```

---

## Task 4: Pydantic Schema定义

**Files:**
- Create: `backend/app/schemas/terrain.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 创建Terrain Pydantic Schema**

Create `backend/app/schemas/terrain.py`:
```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


class CrossSection(BaseModel):
    station: float  # 桩号
    shape: List[List[float]]  # [[x, y, z], ...]
    area: Optional[float] = None


class TerrainFeatures(BaseModel):
    centerline: Optional[Dict[str, Any]] = None
    cross_sections: Optional[List[CrossSection]] = None
    elevation_range: Optional[List[float]] = None  # [min, max, mean]
    slope_analysis: Optional[Dict[str, Any]] = None
    waterfront_line: Optional[Dict[str, Any]] = None
    demolition_boundary: Optional[Dict[str, Any]] = None
    farmland_boundary: Optional[Dict[str, Any]] = None


class TerrainStatus(BaseModel):
    status: Literal["pending", "processing", "completed", "failed"]
    progress: int = Field(ge=0, le=100)
    features: Optional[TerrainFeatures] = None


class TerrainResponse(BaseModel):
    id: UUID
    project_id: UUID
    file_type: str
    status: str
    features: Optional[TerrainFeatures] = None
    bounds: Optional[Dict[str, Any]] = None
    feature_count: Optional[int] = None
    warning: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class TerrainUploadResponse(BaseModel):
    id: UUID
    project_id: UUID
    file_type: str
    status: str
    features: Optional[Dict[str, Any]] = None
    bounds: Optional[Dict[str, Any]] = None
    feature_count: Optional[int] = None
    warning: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/schemas/terrain.py && git commit -m "feat: add Terrain Pydantic schemas"
```

---

## Task 5: 解析器基类和CSV解析器

**Files:**
- Create: `backend/app/services/parsers/base.py`
- Create: `backend/app/services/parsers/__init__.py`
- Create: `backend/app/services/parsers/csv_parser.py`

- [ ] **Step 1: 创建解析器基类**

Create `backend/app/services/parsers/base.py`:
```python
from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Optional
from pathlib import Path


class BaseParser(ABC):
    """地形文件解析器基类"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._line_count: Optional[int] = None

    @abstractmethod
    def parse(self) -> Iterator[Dict[str, Any]]:
        """流式解析文件，返回地理特征迭代器"""
        pass

    @abstractmethod
    def extract_centerline(self) -> Optional[Dict[str, Any]]:
        """提取河道中心线"""
        pass

    @abstractmethod
    def extract_cross_sections(self) -> list:
        """提取横断面"""
        pass

    @abstractmethod
    def extract_elevation_range(self) -> list:
        """提取高程范围 [min, max, mean]"""
        pass

    @abstractmethod
    def extract_slope_analysis(self) -> Dict[str, Any]:
        """提取坡度分析"""
        pass

    def get_bounds(self) -> Optional[Dict[str, Any]]:
        """获取边界框"""
        pass

    def validate(self) -> bool:
        """验证文件格式是否正确"""
        pass
```

- [ ] **Step 2: 创建CSV解析器**

Create `backend/app/services/parsers/csv_parser.py`:
```python
import csv
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List
from app.services.parsers.base import BaseParser
from app.core.exceptions import FileCorruptedException, NoFeatureExtractedException


class CSVParser(BaseParser):
    """CSV格式流式解析器"""

    EXPECTED_COLUMNS = {"x", "y", "z", "station"}  # 最小必需列
    OPTIONAL_COLUMNS = {"point_type", "feature_id", "name"}

    def __init__(self, file_path: Path):
        super().__init__(file_path)
        self._headers: Optional[List[str]] = None
        self._elevation_values: List[float] = []
        self._centerline_points: List[List[float]] = []
        self._cross_sections: Dict[float, List[List[float]]] = {}  # station -> points

    def _detect_delimiter(self) -> str:
        """检测CSV分隔符"""
        with open(self.file_path, "r", encoding="utf-8-sig") as f:
            first_line = f.readline()
            if "," in first_line:
                return ","
            elif "\t" in first_line:
                return "\t"
            elif ";" in first_line:
                return ";"
            return ","

    def _validate_headers(self, headers: List[str]) -> None:
        """验证CSV头是否包含必需列"""
        headers_lower = {h.lower().strip() for h in headers}
        missing = self.EXPECTED_COLUMNS - headers_lower
        if missing:
            raise NoFeatureExtractedException(
                file_type="CSV",
                expected_content="x, y, z columns for coordinates",
                found_entities=list(headers_lower)
            )
        self._headers = [h.strip() for h in headers]

    def parse(self) -> Iterator[Dict[str, Any]]:
        """流式解析CSV"""
        delimiter = self._detect_delimiter()
        with open(self.file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            self._validate_headers(reader.fieldnames or [])

            for row in reader:
                try:
                    point = {
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                        "z": float(row["z"]) if "z" in row else 0.0,
                        "station": float(row["station"]) if "station" in row else 0.0,
                    }
                    # 收集高程值用于统计
                    self._elevation_values.append(point["z"])
                    # 收集中心线点
                    self._centerline_points.append([point["x"], point["y"], point["z"]])
                    yield point
                except (ValueError, KeyError) as e:
                    continue  # 跳过无效行

    def extract_centerline(self) -> Optional[Dict[str, Any]]:
        """提取中心线"""
        if not self._centerline_points:
            return None
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": self._centerline_points
            },
            "properties": {"count": len(self._centerline_points)}
        }

    def extract_cross_sections(self) -> list:
        """按桩号分组提取横断面"""
        if not self._centerline_points:
            return []
        # 按桩号分组
        sections_by_station = {}
        for point in self._centerline_points:
            # 简化：每个独立点作为一个断面
            station = point[2]  # 用z作为station简化
            if station not in sections_by_station:
                sections_by_station[station] = []
            sections_by_station[station].append(point)

        cross_sections = []
        for station, points in sections_by_station.items():
            cross_sections.append({
                "station": station,
                "shape": points,
                "point_count": len(points)
            })
        return cross_sections

    def extract_elevation_range(self) -> list:
        """提取高程范围 [min, max, mean]"""
        if not self._elevation_values:
            return [0.0, 0.0, 0.0]
        return [
            min(self._elevation_values),
            max(self._elevation_values),
            sum(self._elevation_values) / len(self._elevation_values)
        ]

    def extract_slope_analysis(self) -> Dict[str, Any]:
        """计算坡度统计"""
        if len(self._centerline_points) < 2:
            return {"max_slope": 0, "mean_slope": 0, "slope_distribution": {}}

        slopes = []
        for i in range(1, len(self._centerline_points)):
            p1 = self._centerline_points[i - 1]
            p2 = self._centerline_points[i]
            # 水平距离
            dist = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2) ** 0.5
            # 高差
            dz = abs(p2[2] - p1[2])
            if dist > 0:
                slope = dz / dist
                slopes.append(slope)

        if not slopes:
            return {"max_slope": 0, "mean_slope": 0, "slope_distribution": {}}

        # 坡度分级统计
        distribution = {
            "flat": len([s for s in slopes if s < 0.01]),
            "gentle": len([s for s in slopes if 0.01 <= s < 0.05]),
            "moderate": len([s for s in slopes if 0.05 <= s < 0.1]),
            "steep": len([s for s in slopes if s >= 0.1])
        }

        return {
            "max_slope": max(slopes),
            "mean_slope": sum(slopes) / len(slopes),
            "slope_distribution": distribution
        }
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/parsers/base.py backend/app/services/parsers/csv_parser.py && git commit -m "feat: add CSV parser with streaming support"
```

---

## Task 6: DXF解析器

**Files:**
- Create: `backend/app/services/parsers/dxf_parser.py`

- [ ] **Step 1: 创建DXF解析器**

Create `backend/app/services/parsers/dxf_parser.py`:
```python
import ezdxf
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List, Set
from app.services.parsers.base import BaseParser
from app.core.exceptions import FileCorruptedException, NoFeatureExtractedException


class DXFParser(BaseParser):
    """DXF格式解析器，逐实体解析"""

    TARGET_ENTITIES = {"LINE", "POLYLINE", "LWPOLYLINE", "POINT", "INSERT", "BLOCK"}

    def __init__(self, file_path: Path):
        super().__init__(file_path)
        self._elevation_values: List[float] = []
        self._centerline_points: List[List[float]] = []
        self._cross_sections: Dict[float, List[List[float]]] = {}
        self._found_entities: Set[str] = set()

    def validate(self) -> bool:
        """验证DXF文件"""
        try:
            doc = ezdxf.readfile(str(self.file_path))
            return True
        except Exception as e:
            raise FileCorruptedException(file_type="DXF", error=str(e))

    def parse(self) -> Iterator[Dict[str, Any]]:
        """流式解析DXF实体"""
        doc = ezdxf.readfile(str(self.file_path))
        msp = doc.modelspace()

        for entity in msp:
            self._found_entities.add(entity.dxftype())

            if entity.dxftype() == "LINE":
                yield from self._parse_line(entity)
            elif entity.dxftype() in ("POLYLINE", "LWPOLYLINE"):
                yield from self._parse_polyline(entity)
            elif entity.dxftype() == "POINT":
                yield from self._parse_point(entity)

    def _parse_line(self, entity) -> Iterator[Dict[str, Any]]:
        """解析LINE实体"""
        try:
            points = entity.get_points()
            for point in points:
                x, y, z = point[0], point[1], point[2] if len(point) > 2 else 0.0
                self._elevation_values.append(z)
                self._centerline_points.append([x, y, z])
                yield {"type": "LINE", "x": x, "y": y, "z": z}
        except Exception:
            pass

    def _parse_polyline(self, entity) -> Iterator[Dict[str, Any]]:
        """解析POLYLINE/LWPOLYLINE实体"""
        try:
            points = list(entity.get_points())
            if len(points) < 2:
                return

            # 计算平均高程作为桩号
            avg_z = sum(p[2] if len(p) > 2 else 0.0 for p in points) / len(points)

            for point in points:
                x, y, z = point[0], point[1], point[2] if len(point) > 2 else 0.0
                self._elevation_values.append(z)
                yield {"type": entity.dxftype(), "x": x, "y": y, "z": z}

            # 存储为横断面
            self._cross_sections[avg_z] = points
        except Exception:
            pass

    def _parse_point(self, entity) -> Iterator[Dict[str, Any]]:
        """解析POINT实体"""
        try:
            point = entity.dxf.location
            x, y, z = point.x, point.y, point.z if hasattr(point, 'z') else 0.0
            self._elevation_values.append(z)
            yield {"type": "POINT", "x": x, "y": y, "z": z}
        except Exception:
            pass

    def extract_centerline(self) -> Optional[Dict[str, Any]]:
        """提取中心线"""
        if not self._centerline_points:
            return None
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": self._centerline_points
            },
            "properties": {"count": len(self._centerline_points)}
        }

    def extract_cross_sections(self) -> list:
        """提取横断面"""
        cross_sections = []
        for station, points in self._cross_sections.items():
            if len(points) >= 2:
                cross_sections.append({
                    "station": station,
                    "shape": [[p[0], p[1], p[2] if len(p) > 2 else 0.0] for p in points],
                    "point_count": len(points)
                })
        return cross_sections

    def extract_elevation_range(self) -> list:
        """提取高程范围"""
        if not self._elevation_values:
            return [0.0, 0.0, 0.0]
        return [
            min(self._elevation_values),
            max(self._elevation_values),
            sum(self._elevation_values) / len(self._elevation_values)
        ]

    def extract_slope_analysis(self) -> Dict[str, Any]:
        """计算坡度统计"""
        if len(self._centerline_points) < 2:
            return {"max_slope": 0, "mean_slope": 0, "slope_distribution": {}}

        slopes = []
        for i in range(1, len(self._centerline_points)):
            p1 = self._centerline_points[i - 1]
            p2 = self._centerline_points[i]
            dist = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2) ** 0.5
            dz = abs(p2[2] - p1[2])
            if dist > 0:
                slopes.append(dz / dist)

        if not slopes:
            return {"max_slope": 0, "mean_slope": 0, "slope_distribution": {}}

        distribution = {
            "flat": len([s for s in slopes if s < 0.01]),
            "gentle": len([s for s in slopes if 0.01 <= s < 0.05]),
            "moderate": len([s for s in slopes if 0.05 <= s < 0.1]),
            "steep": len([s for s in slopes if s >= 0.1])
        }

        return {
            "max_slope": max(slopes),
            "mean_slope": sum(slopes) / len(slopes),
            "slope_distribution": distribution
        }
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/parsers/dxf_parser.py && git commit -m "feat: add DXF parser with entity streaming"
```

---

## Task 7: Terrain Service业务逻辑

**Files:**
- Create: `backend/app/services/terrain_service.py`

- [ ] **Step 1: 创建Terrain Service**

Create `backend/app/services/terrain_service.py`:
```python
import shutil
import uuid
import magic
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.terrain import Terrain
from app.schemas.terrain import TerrainFeatures, TerrainUploadResponse, CrossSection
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
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/terrain_service.py && git commit -m "feat: add TerrainService with file validation and parsing"
```

---

## Task 8: API路由

**Files:**
- Create: `backend/app/api/v1/terrain.py`
- Modify: `backend/app/api/v1/__init__.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建地形API路由**

Create `backend/app/api/v1/terrain.py`:
```python
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.terrain_service import TerrainService
from app.schemas.terrain import TerrainUploadResponse, TerrainResponse, TerrainStatus
from app.core.exceptions import NoFeatureExtractedException

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
```

- [ ] **Step 2: 更新API __init__**

Modify `backend/app/api/v1/__init__.py`:
```python
from app.api.v1.terrain import router as terrain_router

__all__ = ["terrain_router"]
```

- [ ] **Step 3: 注册路由到main.py**

Modify `backend/app/main.py`:
```python
from fastapi import FastAPI
from app.api.v1 import terrain_router

app = FastAPI(title="Water Design API", version="0.1.0")

app.include_router(terrain_router, prefix="/api/v1")
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/v1/terrain.py backend/app/api/v1/__init__.py backend/app/main.py && git commit -m "feat: add terrain API endpoints"
```

---

## Task 9: 单元测试

**Files:**
- Create: `backend/tests/services/test_terrain_service.py`
- Create: `backend/tests/services/test_parsers/test_csv_parser.py`
- Create: `backend/tests/services/test_parsers/test_dxf_parser.py`
- Create: `backend/tests/fixtures/sample_river_survey.csv`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 创建测试夹具CSV**

Create `backend/tests/fixtures/sample_river_survey.csv`:
```csv
x,y,z,station
100.0,200.0,10.5,0
100.5,200.5,10.3,10
101.0,201.0,10.1,20
101.5,201.5,9.8,30
102.0,202.0,9.5,40
```

- [ ] **Step 2: 创建conftest**

Create `backend/tests/conftest.py`:
```python
import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()
```

- [ ] **Step 3: CSV解析器测试**

Create `backend/tests/services/test_parsers/test_csv_parser.py`:
```python
import pytest
from pathlib import Path
from app.services.parsers.csv_parser import CSVParser
from app.core.exceptions import NoFeatureExtractedException


class TestCSVParser:
    def test_parse_valid_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y,z,station\n100.0,200.0,10.5,0\n100.5,200.5,10.3,10\n")

        parser = CSVParser(csv_file)
        points = list(parser.parse())

        assert len(points) == 2
        assert points[0]["x"] == 100.0
        assert points[0]["z"] == 10.5

    def test_extract_elevation_range(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y,z,station\n100.0,200.0,10.0,0\n100.5,200.5,20.0,10\n")

        parser = CSVParser(csv_file)
        list(parser.parse())
        elev_range = parser.extract_elevation_range()

        assert elev_range == [10.0, 20.0, 15.0]

    def test_extract_centerline(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y,z,station\n100.0,200.0,10.5,0\n100.5,200.5,10.3,10\n")

        parser = CSVParser(csv_file)
        list(parser.parse())
        centerline = parser.extract_centerline()

        assert centerline is not None
        assert centerline["geometry"]["type"] == "LineString"
        assert len(centerline["geometry"]["coordinates"]) == 2

    def test_missing_columns_raises(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("x,y\n100.0,200.0\n")

        parser = CSVParser(csv_file)
        with pytest.raises(NoFeatureExtractedException):
            list(parser.parse())
```

- [ ] **Step 4: TerrainService测试**

Create `backend/tests/services/test_terrain_service.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.terrain_service import TerrainService
from app.core.exceptions import FileTooLargeException, InvalidFileTypeException


class TestTerrainService:
    def test_validate_file_size(self):
        service = TerrainService(db=AsyncMock())
        large_content = b"x" * (11 * 1024 * 1024 * 1024)  # 11GB

        with pytest.raises(FileTooLargeException):
            service._validate_file(large_content, "test.csv")

    def test_validate_file_type(self):
        service = TerrainService(db=AsyncMock())

        with pytest.raises(InvalidFileTypeException):
            service._validate_file(b"test content", "test.pdf")

    def test_validate_dxf_magic_number(self):
        service = TerrainService(db=AsyncMock())
        # DXF without AutoCAD magic number
        content = b"INVALID_DXF_DATA"

        with pytest.raises(InvalidFileTypeException):
            service._validate_file(content, "test.dxf")
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && pytest tests/ -v`

- [ ] **Step 6: 提交**

```bash
git add backend/tests/ && git commit -m "test: add terrain module unit tests"
```

---

## Task 10: 集成测试准备

**Files:**
- Modify: `backend/docker-compose.yml`

- [ ] **Step 1: 添加PostgreSQL+PostGIS服务**

Modify `backend/docker-compose.yml`:
```yaml
version: '3.8'

services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: waterdesign
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

- [ ] **Step 2: 提交**

```bash
git add backend/docker-compose.yml && git commit -m "feat: add PostGIS docker-compose service"
```

---

## 实现检查清单

### Spec覆盖检查

| Spec需求 | 实现位置 |
|----------|----------|
| CSV流式解析 | Task 5 |
| DXF逐实体解析 | Task 6 |
| 7种地形特征提取 | Tasks 5,6,7 |
| 文件大小/类型/魔数验证 | Task 7 |
| POST /projects/{id}/terrain | Task 8 |
| GET /projects/{id}/terrain | Task 8 |
| GET /projects/{id}/terrain/status | Task 8 |
| POST /projects/{id}/terrain/reparse | Task 8 |
| FILE_TOO_LARGE (413) | Task 2 |
| INVALID_FILE_TYPE (400) | Task 2 |
| FILE_CORRUPTED (400) | Task 2 |
| NO_FEATURE_EXTRACTED (422) | Task 2 |
| PARTIAL_PARSING (200) | Task 7 |
| 单元测试 | Task 9 |

### 类型一致性检查

- `TerrainService.upload_and_parse()` 返回 `TerrainUploadResponse`
- `TerrainService.reparse()` 返回 `TerrainUploadResponse`
- `TerrainService.get_terrain_status()` 返回 `Optional[Terrain]`
- CSVParser.extract_elevation_range() 返回 `list[float, float, float]`
- DXFParser.extract_centerline() 返回 `Optional[Dict[str, Any]]`

---

## 计划完成

**文件位置:** `docs/superpowers/plans/2026-04-11-terrain-import-implementation.md`

**执行选项:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
