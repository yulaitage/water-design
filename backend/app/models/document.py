import uuid
from datetime import datetime
from app.core.utils import utc_now
from sqlalchemy import String, Text, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class Document(Base):
    """上传的文档（PDF、Word等）"""
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # 文件名
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)   # 存储路径
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)    # 文件类型 pdf/docx/txt
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)        # 文件大小（字节）

    # 解析后的内容
    full_text: Mapped[str] = mapped_column(Text, nullable=True)           # 完整文本内容
    text_embedding: Mapped[Vector] = mapped_column(Vector(1024), nullable=True)  # 文本向量
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=True)    # 元数据（页数、章节等）

    # 文档信息
    title: Mapped[str] = mapped_column(String(255), nullable=True)       # 文档标题
    project_type: Mapped[str] = mapped_column(String(50), nullable=True)  # 关联项目类型
    category: Mapped[str] = mapped_column(String(50), nullable=True)    # 分类：规范/案例/报告

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_doc_project_type", "project_type"),
        Index("ix_doc_category", "category"),
    )


class DocumentChunk(Base):
    """文档文本块 - 用于语义检索"""
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)   # 块索引

    # 块内容
    text: Mapped[str] = mapped_column(Text, nullable=False)               # 文本内容
    page: Mapped[int] = mapped_column(Integer, nullable=True)           # 所在页码
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=True)  # text/table/figure
    embedding: Mapped[Vector] = mapped_column(Vector(1024), nullable=True)

    # 图片相关字段（figure 类型专用）
    image_path: Mapped[str] = mapped_column(String(500), nullable=True)
    image_description: Mapped[str] = mapped_column(Text, nullable=True)
    context_before: Mapped[str] = mapped_column(Text, nullable=True)
    context_after: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_chunk_doc_idx", "document_id", "chunk_index"),
    )