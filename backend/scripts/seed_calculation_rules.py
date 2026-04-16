"""
初始化计算规则种子数据

运行: cd backend && python -m scripts.seed_calculation_rules
"""
import asyncio
from app.db.database import async_session_maker
from app.models.calculation_rule import CalculationRule


RULES = [
    # 堤防工程 - 土方工程
    {
        "project_type": "堤防",
        "item_category": "土方工程",
        "item_name": "土方开挖",
        "formula": "height * (topwidth + slope_ratio * height) * length",
        "unit": "m³",
        "params": {
            "height": {"type": "design_param", "description": "堤高"},
            "topwidth": {"type": "design_param", "description": "堤顶宽度"},
            "slope_ratio": {"type": "design_param", "description": "边坡系数"},
            "length": {"type": "design_param", "description": "河道长度"}
        },
        "description": "堤防土方开挖 V = H × (B + m×H) × L"
    },
    {
        "project_type": "堤防",
        "item_category": "土方工程",
        "item_name": "土方填筑",
        "formula": "height * (topwidth + slope_ratio * height) * length * 1.05",
        "unit": "m³",
        "params": {
            "height": {"type": "design_param"},
            "topwidth": {"type": "design_param"},
            "slope_ratio": {"type": "design_param"},
            "length": {"type": "design_param"},
            "coefficient": {"type": "constant", "value": 1.05}
        },
        "description": "堤防土方填筑（含松散系数）"
    },
    # 堤防工程 - 护岸工程
    {
        "project_type": "堤防",
        "item_category": "护岸工程",
        "item_name": "护坡混凝土",
        "formula": "length * sqrt(height**2 + (slope_ratio * height)**2)",
        "unit": "m²",
        "params": {
            "length": {"type": "design_param"},
            "height": {"type": "design_param"},
            "slope_ratio": {"type": "design_param"}
        },
        "description": "护坡混凝土面积 S = L × √(H² + (m×H)²)"
    },
    {
        "project_type": "堤防",
        "item_category": "护岸工程",
        "item_name": "垫层",
        "formula": "length * sqrt(height**2 + (slope_ratio * height)**2) * 0.1",
        "unit": "m³",
        "params": {
            "length": {"type": "design_param"},
            "height": {"type": "design_param"},
            "slope_ratio": {"type": "design_param"}
        },
        "description": "垫层体积 = 护坡面积 × 0.1m"
    },
]


async def seed():
    async with async_session_maker() as session:
        for rule_data in RULES:
            rule = CalculationRule(**rule_data)
            session.add(rule)
        await session.commit()
        print(f"Seeded {len(RULES)} calculation rules")


if __name__ == "__main__":
    asyncio.run(seed())