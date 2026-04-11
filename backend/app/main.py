from fastapi import FastAPI
from app.api.v1 import terrain_router

app = FastAPI(title="Water Design API", version="0.1.0")

app.include_router(terrain_router, prefix="/api/v1")