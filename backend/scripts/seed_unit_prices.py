"""
初始化单价种子数据

运行: cd backend && python -m scripts.seed_unit_prices
"""
import asyncio
from app.db.database import async_session_maker
from app.models.unit_price import UnitPrice


PRICES = [
    # 土方工程
    {"item_name": "土方开挖", "unit": "m³", "price": 12.5, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "土方填筑", "unit": "m³", "price": 15.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "土方运输", "unit": "m³", "price": 8.5, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    # 护岸工程
    {"item_name": "护坡混凝土", "unit": "m²", "price": 85.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "垫层", "unit": "m³", "price": 65.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "浆砌石", "unit": "m³", "price": 120.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    # 穿堤建筑物
    {"item_name": "防洪闸", "unit": "孔", "price": 50000.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
]


async def seed():
    async with async_session_maker() as session:
        for price_data in PRICES:
            price = UnitPrice(**price_data)
            session.add(price)
        await session.commit()
        print(f"Seeded {len(PRICES)} unit prices")


if __name__ == "__main__":
    asyncio.run(seed())