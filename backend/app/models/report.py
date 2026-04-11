import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class ReportTask(Base):
    __tablename__ = "report_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "feasibility" | "preliminary_design"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    chapters: Mapped[dict] = mapped_column(JSONB, default={})  # 各章节内容
    output_path: Mapped[str] = mapped_column(String(500), nullable=True)  # Word文件路径
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    current_chapter: Mapped[str] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    revisions: Mapped[list["ReportRevision"]] = relationship(back_populates="report_task")

    __table_args__ = (
        Index("ix_report_project", "project_id"),
    )


class ReportRevision(Base):
    __tablename__ = "report_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("report_tasks.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_type: Mapped[str] = mapped_column(String(20), nullable=True)  # "form" | "natural_language"
    user_input: Mapped[str] = mapped_column(Text, nullable=True)           # 原始修改意见
    modified_chapters: Mapped[list] = mapped_column(JSONB, default=[])     # 被修改的章节
    ai_interpretation: Mapped[str] = mapped_column(Text, nullable=True)    # AI理解
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    report_task: Mapped["ReportTask"] = relationship(back_populates="revisions")