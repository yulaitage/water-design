import uuid
from datetime import datetime
from typing import Optional, List
from app.core.utils import utc_now
from sqlalchemy import String, Text, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class WikiItem(Base):
    __tablename__ = "wiki_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)      # 知识标题
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 分类：design_standard/case_summary/calculation_rule/design_tip
    content: Mapped[str] = mapped_column(Text, nullable=False)          # 知识内容（Markdown）
    source_report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)  # 来源报告ID
    source_chapter: Mapped[str] = mapped_column(String(100), nullable=True)  # 来源章节
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=[])   # 标签
    project_types: Mapped[List[str]] = mapped_column(ARRAY(String), default=[])  # 适用工程类型
    content_embedding: Mapped[Vector] = mapped_column(Vector(1024), nullable=True)
    usage_count: Mapped[int] = mapped_column(default=0)                  # 被引用次数
    is_verified: Mapped[bool] = mapped_column(default=False)            # 是否已验证
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_wiki_category", "category"),
        Index("ix_wiki_project_types", "project_types", postgresql_using="gin"),
    )