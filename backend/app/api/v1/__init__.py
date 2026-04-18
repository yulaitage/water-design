from app.api.v1.projects import router as projects_router
from app.api.v1.terrain import router as terrain_router
from app.api.v1.cost_estimation import router as cost_estimation_router
from app.api.v1.unit_prices import router as unit_prices_router
from app.api.v1.chat import router as chat_router
from app.api.v1.reports import router as reports_router
from app.api.v1.knowledge_base import router as knowledge_base_router

__all__ = [
    "projects_router",
    "terrain_router",
    "cost_estimation_router",
    "unit_prices_router",
    "chat_router",
    "reports_router",
    "knowledge_base_router",
]
