import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)      # 项目名称
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 工程类型
    location: Mapped[str] = mapped_column(String(100), nullable=False)    # 地理位置
    owner: Mapped[str] = mapped_column(String(200), nullable=True)       # 业主单位
    report_path: Mapped[str] = mapped_column(String(500), nullable=True)  # 原始报告Markdown路径
    summary: Mapped[str] = mapped_column(Text, nullable=True)            # AI设计摘要
    summary_embedding: Mapped[Vector] = mapped_column(Vector(1536), nullable=True)
    design_params: Mapped[dict] = mapped_column(JSON, default={})       # 设计参数
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_case_location", "location"),
        Index("ix_case_project_type", "project_type"),
    )