import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UnitPrice(Base):
    __tablename__ = "unit_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # 12.5 元/m³
    region: Mapped[str] = mapped_column(String(50), nullable=True)  # "浙江省"
    year: Mapped[int] = mapped_column(Integer, nullable=True)  # 2024
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="user_import")  # "user_import" | "knowledge_base"
    description: Mapped[Text] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UnitPrice {self.item_name} {self.price}{self.unit}>"