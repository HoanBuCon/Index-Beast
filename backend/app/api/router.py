"""Gom các router con dưới tiền tố /api/v1. Thêm router mới: import rồi include_router ở đây.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S2] API contract v1
"""

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
