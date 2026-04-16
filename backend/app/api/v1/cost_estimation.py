import uuid
from typing import List
from fastapi import APIRouter, Depends, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.cost_calculation import CostCalculationService
from app.schemas.cost_estimation import (
    CostEstimateCreateRequest, CostEstimateResponse,
    CostEstimateListResponse, CostEstimateItem, CostEstimateSummary
)
from app.models.cost_estimate import CostEstimate

router = APIRouter(prefix="/projects/{project_id}/cost-estimates", tags=["cost_estimation"])


@router.post("", response_model=CostEstimateResponse)
async def create_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    request: CostEstimateCreateRequest = ...,
    db: AsyncSession = Depends(get_db)
):
    """
    创建工程量估算

    根据设计参数和计算规则，自动统计工程量并估算费用
    """
    service = CostCalculationService(db)
    estimate = await service.calculate(request)

    return CostEstimateResponse(
        id=estimate.id,
        project_id=estimate.project_id,
        version=estimate.version,
        status=estimate.status,
        design_params=estimate.design_params,
        summary=[CostEstimateSummary(**s) for s in estimate.summary],
        details=[CostEstimateItem(**d) for d in estimate.details],
        total_cost=float(estimate.total_cost),
        cost_per_km=float(estimate.cost_per_km) if estimate.cost_per_km else None,
        created_at=estimate.created_at
    )


@router.get("", response_model=CostEstimateListResponse)
async def list_cost_estimates(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取项目的所有估算"""
    service = CostCalculationService(db)
    estimates = await service.get_estimates(project_id)

    return CostEstimateListResponse(
        estimates=[
            CostEstimateResponse(
                id=e.id,
                project_id=e.project_id,
                version=e.version,
                status=e.status,
                design_params=e.design_params,
                summary=[CostEstimateSummary(**s) for s in e.summary],
                details=[CostEstimateItem(**d) for d in e.details],
                total_cost=float(e.total_cost),
                cost_per_km=float(e.cost_per_km) if e.cost_per_km else None,
                created_at=e.created_at
            )
            for e in estimates
        ],
        total=len(estimates)
    )


@router.get("/{estimate_id}", response_model=CostEstimateResponse)
async def get_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    estimate_id: uuid.UUID = Path(..., description="估算ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取单条估算详情"""
    service = CostCalculationService(db)
    estimate = await service.get_estimate(estimate_id)

    if not estimate or estimate.project_id != project_id:
        raise HTTPException(status_code=404, detail="估算不存在")

    return CostEstimateResponse(
        id=estimate.id,
        project_id=estimate.project_id,
        version=estimate.version,
        status=estimate.status,
        design_params=estimate.design_params,
        summary=[CostEstimateSummary(**s) for s in estimate.summary],
        details=[CostEstimateItem(**d) for d in estimate.details],
        total_cost=float(estimate.total_cost),
        cost_per_km=float(estimate.cost_per_km) if estimate.cost_per_km else None,
        created_at=estimate.created_at
    )


@router.post("/{estimate_id}/recalculate", response_model=CostEstimateResponse)
async def recalculate_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    estimate_id: uuid.UUID = Path(..., description="估算ID"),
    db: AsyncSession = Depends(get_db)
):
    """重新计算估算"""
    service = CostCalculationService(db)
    old_estimate = await service.get_estimate(estimate_id)

    if not old_estimate or old_estimate.project_id != project_id:
        raise HTTPException(status_code=404, detail="估算不存在")

    # 使用相同参数重新计算
    request = CostEstimateCreateRequest(
        project_id=project_id,
        project_type="堤防",
        design_params=old_estimate.design_params
    )
    new_estimate = await service.calculate(request)

    return CostEstimateResponse(
        id=new_estimate.id,
        project_id=new_estimate.project_id,
        version=new_estimate.version,
        status=new_estimate.status,
        design_params=new_estimate.design_params,
        summary=[CostEstimateSummary(**s) for s in new_estimate.summary],
        details=[CostEstimateItem(**d) for d in new_estimate.details],
        total_cost=float(new_estimate.total_cost),
        cost_per_km=float(new_estimate.cost_per_km) if new_estimate.cost_per_km else None,
        created_at=new_estimate.created_at
    )