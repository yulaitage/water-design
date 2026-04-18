import logging
import time
from collections import defaultdict
from threading import Lock
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    projects_router,
    terrain_router,
    cost_estimation_router,
    unit_prices_router,
    chat_router,
    reports_router,
    knowledge_base_router,
)
from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Water Design API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self._window: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60
        with self._lock:
            self._window[key] = [t for t in self._window[key] if t > window_start]
            allowed = len(self._window[key]) < self.rpm
            if allowed:
                self._window[key].append(now)
            return allowed


_rate_limiter = RateLimiter(requests_per_minute=60)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}"

    if not _rate_limiter.is_allowed(key):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "请求过于频繁，请稍后再试"},
        )

    return await call_next(request)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if not settings.api_key or request.url.path == "/health":
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != settings.api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or missing API key"},
        )
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(projects_router, prefix="/api/v1")
app.include_router(terrain_router, prefix="/api/v1")
app.include_router(cost_estimation_router, prefix="/api/v1")
app.include_router(unit_prices_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(knowledge_base_router, prefix="/api/v1")
