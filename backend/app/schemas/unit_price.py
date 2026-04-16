from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class UnitPriceCreateRequest(BaseModel):
    """创建单价请求"""
    item_name: str
    unit: str
    price: float
    region: Optional[str] = None
    year: Optional[int] = None
    source: str = "user_import"


class UnitPriceResponse(BaseModel):
    """单价响应"""
    id: UUID
    item_name: str
    unit: str
    price: float
    region: Optional[str] = None
    year: Optional[int] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class UnitPriceImportRequest(BaseModel):
    """批量导入单价请求"""
    items: List[UnitPriceCreateRequest]


class UnitPriceListResponse(BaseModel):
    """单价列表响应"""
    items: List[UnitPriceResponse]
    total: int