from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Literal
from uuid import UUID
from datetime import datetime


class DesignParamItem(BaseModel):
    """单个设计参数"""
    value: float
    unit: str
    description: Optional[str] = None


class CostEstimateItem(BaseModel):
    """分项估算明细"""
    category: str  # "土方工程"
    item: str  # "土方开挖"
    quantity: float
    unit: str  # "m³"
    unit_price: float
    subtotal: float


class CostEstimateSummary(BaseModel):
    """分类汇总"""
    category: str
    total_quantity: float
    total_amount: float


class CostEstimateCreateRequest(BaseModel):
    project_type: Literal["堤防", "河道整治"] = "堤防"
    design_params: Dict[str, float]


class CostEstimateResponse(BaseModel):
    """估算响应"""
    id: UUID
    project_id: UUID
    project_type: str
    version: int
    status: str
    design_params: Dict[str, float]
    summary: List[CostEstimateSummary]
    details: List[CostEstimateItem]
    total_cost: float
    cost_per_km: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CostEstimateListResponse(BaseModel):
    """估算列表响应"""
    estimates: List[CostEstimateResponse]
    total: int