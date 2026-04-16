import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CostEstimate(Base):
    __tablename__ = "cost_estimates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "堤防" | "河道整治"
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # "draft" | "confirmed"

    # 设计参数
    design_params: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # {"length": 1000, "height": 5, ...}

    # 分类汇总
    summary: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # {"土方工程": {"quantity": 125000, "unit": "m³", "total": 1562500}, ...}

    # 分项明细
    details: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # [{"category": "土方工程", "item": "土方开挖", ...}, ...]

    # 总价
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    cost_per_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)  # 万元/km

    # 输出文件路径
    output_excel_path: Mapped[str] = mapped_column(String(500), nullable=True)
    output_word_path: Mapped[str] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CostEstimate {self.project_id} v{self.version} {self.total_cost}万元>"