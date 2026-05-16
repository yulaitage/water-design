from app.api.v1.projects import router as projects_router
from app.api.v1.terrain import router as terrain_router
from app.api.v1.cost_estimation import router as cost_estimation_router
from app.api.v1.unit_prices import router as unit_prices_router
from app.api.v1.chat import router as chat_router
from app.api.v1.reports import router as reports_router
from app.api.v1.knowledge_base import router as knowledge_base_router
from app.api.v1.export import router as export_router, calculation_router
from app.api.v1.interactive_report import router as interactive_report_router
from app.api.v1.skills import router as skills_router
from app.api.v1.user import router as user_router

__all__ = [
    "projects_router",
    "terrain_router",
    "cost_estimation_router",
    "unit_prices_router",
    "chat_router",
    "reports_router",
    "knowledge_base_router",
    "export_router",
    "calculation_router",
    "interactive_report_router",
    "skills_router",
    "user_router",
]
