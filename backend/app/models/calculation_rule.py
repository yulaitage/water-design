import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CalculationRule(Base):
    __tablename__ = "calculation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # "堤防" | "河道整治"
    item_category: Mapped[str] = mapped_column(String(50), nullable=False)  # "土方工程" | "护岸工程"
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "土方开挖" | "土方填筑"
    formula: Mapped[str] = mapped_column(Text, nullable=False)  # "length * height * slope_ratio * coefficient"
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # "m³" | "m²"
    params: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # 参数定义 {"length": {"type": "design_param"}, "coefficient": {"type": "constant", "value": 1.05}}
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CalculationRule {self.project_type}/{self.item_category}/{self.item_name}>"