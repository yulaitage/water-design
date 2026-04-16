import uuid
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.calculation_rule import CalculationRule
from app.models.unit_price import UnitPrice
from app.models.cost_estimate import CostEstimate
from app.schemas.cost_estimation import (
    CostEstimateItem, CostEstimateSummary, CostEstimateCreateRequest
)
from app.core.calculation_engine import CalculationEngine, CalculationContext


class CostCalculationService:
    """工程量计算服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = CalculationEngine()

    async def calculate(
        self, project_id: uuid.UUID, request: CostEstimateCreateRequest
    ) -> CostEstimate:
        """
        执行工程量计算

        1. 查询适用的计算规则
        2. 执行每个规则的计算
        3. 查询单价并汇总
        4. 保存估算结果
        """
        # 1. 获取适用的计算规则
        rules = await self._get_rules(request.project_type)

        # 2. 计算每个分项的工程量
        context = CalculationContext(
            design_params=request.design_params,
            constants={}
        )

        details: List[CostEstimateItem] = []
        summary_map: Dict[str, Dict[str, Any]] = {}

        for rule in rules:
            quantity = self._calculate_rule(rule, context)
            if quantity is None or quantity <= 0:
                continue

            # 查询单价
            unit_price = await self._get_unit_price(rule.item_name, rule.unit)
            if unit_price is None:
                continue

            subtotal = float(unit_price.price) * quantity

            # 分项明细
            item = CostEstimateItem(
                category=rule.item_category,
                item=rule.item_name,
                quantity=quantity,
                unit=rule.unit,
                unit_price=float(unit_price.price),
                subtotal=subtotal
            )
            details.append(item)

            # 分类汇总
            if rule.item_category not in summary_map:
                summary_map[rule.item_category] = {
                    "total_quantity": 0.0,
                    "total_amount": 0.0,
                    "unit": rule.unit
                }
            summary_map[rule.item_category]["total_quantity"] += quantity
            summary_map[rule.item_category]["total_amount"] += subtotal

        # 3. 生成汇总
        summary = [
            CostEstimateSummary(
                category=cat,
                total_quantity=data["total_quantity"],
                total_amount=data["total_amount"]
            )
            for cat, data in summary_map.items()
        ]

        # 4. 计算总价
        total_cost = sum(item.subtotal for item in details)

        # 5. 计算每公里造价
        length = request.design_params.get("length", 0)
        cost_per_km = (total_cost / length * 1000) if length > 0 else None  # 万元/km

        # 6. 保存结果
        estimate = CostEstimate(
            project_id=project_id,
            version=1,
            status="draft",
            design_params=request.design_params,
            summary=[s.model_dump() for s in summary],
            details=[d.model_dump() for d in details],
            total_cost=total_cost,
            cost_per_km=cost_per_km
        )
        self.db.add(estimate)
        await self.db.commit()
        await self.db.refresh(estimate)

        return estimate

    async def _get_rules(self, project_type: str) -> List[CalculationRule]:
        """获取适用的计算规则"""
        result = await self.db.execute(
            select(CalculationRule).where(
                and_(
                    CalculationRule.project_type == project_type,
                    CalculationRule.is_active == True
                )
            )
        )
        return list(result.scalars().all())

    def _calculate_rule(self, rule: CalculationRule, context: CalculationContext) -> Optional[float]:
        """计算单条规则的工程量"""
        return self.engine.evaluate(rule.formula, context)

    async def _get_unit_price(self, item_name: str, unit: str) -> Optional[UnitPrice]:
        """获取单价"""
        result = await self.db.execute(
            select(UnitPrice).where(
                and_(
                    UnitPrice.item_name == item_name,
                    UnitPrice.unit == unit
                )
            ).order_by(UnitPrice.year.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_estimates(self, project_id: uuid.UUID) -> List[CostEstimate]:
        """获取项目的所有估算"""
        result = await self.db.execute(
            select(CostEstimate)
            .where(CostEstimate.project_id == project_id)
            .order_by(CostEstimate.version.desc())
        )
        return list(result.scalars().all())

    async def get_estimate(self, estimate_id: uuid.UUID) -> Optional[CostEstimate]:
        """获取单条估算"""
        result = await self.db.execute(
            select(CostEstimate).where(CostEstimate.id == estimate_id)
        )
        return result.scalar_one_or_none()