import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from typing import Optional, Dict, Any

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
    cross_sections: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    elevation_range: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # [min, max, mean]
    slope_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    waterfront_line = mapped_column(Geometry(geometry_type="LINESTRING", srid=4490), nullable=True)
    demolition_boundary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    farmland_boundary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

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