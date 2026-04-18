import uuid
from datetime import datetime
from app.core.utils import utc_now
from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class Specification(Base):
    __tablename__ = "specifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)      # 规范名称
    code: Mapped[str] = mapped_column(String(50), nullable=False)       # 规范编号 GB/T 502xx-2018
    chapter: Mapped[str] = mapped_column(String(100), nullable=False)   # 章节 "3.1 基本规定"
    section: Mapped[str] = mapped_column(String(50), nullable=True)    # 条款编号 "3.1.2"
    content: Mapped[str] = mapped_column(Text, nullable=False)          # Markdown条款内容
    content_embedding: Mapped[Vector] = mapped_column(Vector(1536), nullable=True)
    project_types: Mapped[list] = mapped_column(ARRAY(String), default=[])  # 适用工程类型
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_spec_project_types", "project_types", postgresql_using="gin"),
    )