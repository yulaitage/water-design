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