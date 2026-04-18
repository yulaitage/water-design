import uuid
from fastapi import APIRouter, Depends, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.cost_calculation import CostCalculationService
from app.schemas.cost_estimation import (
    CostEstimateCreateRequest, CostEstimateResponse,
    CostEstimateListResponse, CostEstimateItem, CostEstimateSummary
)

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
    request.project_id = project_id
    service = CostCalculationService(db)
    estimate = await service.calculate(request)

    return _build_response(estimate)


@router.get("", response_model=CostEstimateListResponse)
async def list_cost_estimates(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_db)
):
    service = CostCalculationService(db)
    estimates = await service.get_estimates(project_id)
    return CostEstimateListResponse(
        estimates=[_build_response(e) for e in estimates],
        total=len(estimates),
    )


@router.get("/{estimate_id}", response_model=CostEstimateResponse)
async def get_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    estimate_id: uuid.UUID = Path(..., description="估算ID"),
    db: AsyncSession = Depends(get_db)
):
    service = CostCalculationService(db)
    estimate = await service.get_estimate(estimate_id)
    if not estimate or estimate.project_id != project_id:
        raise HTTPException(status_code=404, detail="估算不存在")
    return _build_response(estimate)


@router.post("/{estimate_id}/recalculate", response_model=CostEstimateResponse)
async def recalculate_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    estimate_id: uuid.UUID = Path(..., description="估算ID"),
    db: AsyncSession = Depends(get_db)
):
    service = CostCalculationService(db)
    old_estimate = await service.get_estimate(estimate_id)
    if not old_estimate or old_estimate.project_id != project_id:
        raise HTTPException(status_code=404, detail="估算不存在")

    request = CostEstimateCreateRequest(
        project_type=old_estimate.project_type,
        design_params=old_estimate.design_params,
    )
    request.project_id = project_id
    new_estimate = await service.calculate(request)
    return _build_response(new_estimate)


def _build_response(estimate) -> CostEstimateResponse:
    return CostEstimateResponse(
        id=estimate.id,
        project_id=estimate.project_id,
        project_type=estimate.project_type,
        version=estimate.version,
        status=estimate.status,
        design_params=estimate.design_params,
        summary=[CostEstimateSummary(**s) for s in estimate.summary],
        details=[CostEstimateItem(**d) for d in estimate.details],
        total_cost=float(estimate.total_cost),
        cost_per_km=float(estimate.cost_per_km) if estimate.cost_per_km else None,
        created_at=estimate.created_at,
    )