import uuid
from datetime import datetime
from app.core.utils import utc_now
from sqlalchemy import String, Text, DateTime, Integer, Float, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DocumentImage(Base):
    """PDF文档中提取的图片，关联到周围文字"""
    __tablename__ = "document_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    image_index: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # 图片在页面上的位置和尺寸（单位：point）
    x: Mapped[float] = mapped_column(Float, nullable=True)
    y: Mapped[float] = mapped_column(Float, nullable=True)
    width: Mapped[float] = mapped_column(Float, nullable=True)
    height: Mapped[float] = mapped_column(Float, nullable=True)

    image_type: Mapped[str] = mapped_column(String(20), nullable=False, default="png")

    # 关联的文字上下文
    context_text: Mapped[str] = mapped_column(Text, nullable=True)
    # AI视觉模型生成的图片描述
    description: Mapped[str] = mapped_column(Text, nullable=True)
    linked_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_docimg_doc_page_img", "document_id", "page", "image_index"),
    )
