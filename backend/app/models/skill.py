import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.core.utils import utc_now
from sqlalchemy import String, Text, DateTime, JSON, Integer, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # 技能名称，如 "堤防造价估算"
    description: Mapped[str] = mapped_column(Text, nullable=False)  # 技能描述
    trigger_patterns: Mapped[List[str]] = mapped_column(ARRAY(String), default=[])  # 触发关键词/模式
    parameters: Mapped[List[dict]] = mapped_column(JSON, default=[])  # 参数定义 [{"name": "project_type", "type": "string", "required": true}]
    solution_steps: Mapped[List[dict]] = mapped_column(JSON, default=[])  # 解决步骤 [{"step": 1, "action": "search_specs", "params": {...}}]
    examples: Mapped[List[dict]] = mapped_column(JSON, default=[])  # 示例 [{"query": "...", "solution": "..."}]
    success_rate: Mapped[float] = mapped_column(default=0.0)  # 成功率
    usage_count: Mapped[int] = mapped_column(default=0)  # 使用次数
    is_verified: Mapped[bool] = mapped_column(default=False)  # 是否已验证
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_skill_name", "name"),
    )


class SkillExecutionLog(Base):
    __tablename__ = "skill_execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)  # 用户查询
    matched_pattern: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # 匹配到的触发模式
    execution_result: Mapped[str] = mapped_column(Text, nullable=True)  # 执行结果
    success: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否成功
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 用户反馈
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0)  # 执行时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)