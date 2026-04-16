from fastapi import FastAPI
from app.api.v1 import terrain_router, cost_estimation_router, unit_prices_router, chat_router

app = FastAPI(title="Water Design API", version="0.1.0")

app.include_router(terrain_router, prefix="/api/v1")
app.include_router(cost_estimation_router, prefix="/api/v1")
app.include_router(unit_prices_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")