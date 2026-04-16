import uuid
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.unit_price import UnitPrice
from app.schemas.unit_price import (
    UnitPriceCreateRequest, UnitPriceResponse,
    UnitPriceListResponse, UnitPriceImportRequest
)

router = APIRouter(prefix="/unit-prices", tags=["unit_prices"])


@router.post("", response_model=UnitPriceResponse)
async def create_unit_price(
    request: UnitPriceCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """创建单价"""
    unit_price = UnitPrice(
        item_name=request.item_name,
        unit=request.unit,
        price=request.price,
        region=request.region,
        year=request.year,
        source=request.source
    )
    db.add(unit_price)
    await db.commit()
    await db.refresh(unit_price)

    return UnitPriceResponse(
        id=unit_price.id,
        item_name=unit_price.item_name,
        unit=unit_price.unit,
        price=float(unit_price.price),
        region=unit_price.region,
        year=unit_price.year,
        source=unit_price.source,
        created_at=unit_price.created_at
    )


@router.post("/import", response_model=UnitPriceListResponse)
async def import_unit_prices(
    request: UnitPriceImportRequest,
    db: AsyncSession = Depends(get_db)
):
    """批量导入单价"""
    created = []
    for item in request.items:
        unit_price = UnitPrice(
            item_name=item.item_name,
            unit=item.unit,
            price=item.price,
            region=item.region,
            year=item.year,
            source=item.source
        )
        db.add(unit_price)
        created.append(unit_price)

    await db.commit()

    return UnitPriceListResponse(
        items=[
            UnitPriceResponse(
                id=u.id,
                item_name=u.item_name,
                unit=u.unit,
                price=float(u.price),
                region=u.region,
                year=u.year,
                source=u.source,
                created_at=u.created_at
            )
            for u in created
        ],
        total=len(created)
    )


@router.get("", response_model=UnitPriceListResponse)
async def list_unit_prices(
    item_name: str = Query(None, description="按名称筛选"),
    region: str = Query(None, description="按地区筛选"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """获取单价列表"""
    query = select(UnitPrice)

    if item_name:
        query = query.where(UnitPrice.item_name.contains(item_name))
    if region:
        query = query.where(UnitPrice.region == region)

    query = query.order_by(UnitPrice.year.desc()).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()

    return UnitPriceListResponse(
        items=[
            UnitPriceResponse(
                id=u.id,
                item_name=u.item_name,
                unit=u.unit,
                price=float(u.price),
                region=u.region,
                year=u.year,
                source=u.source,
                created_at=u.created_at
            )
            for u in items
        ],
        total=len(items)
    )