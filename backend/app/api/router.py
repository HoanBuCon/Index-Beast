"""Gom các router con dưới tiền tố API_PREFIX. Thêm router mới: import rồi include_router ở đây.

Phụ trách: TV1 · [S1] Skeleton FastAPI · [S2] API contract v1
"""

from fastapi import APIRouter

from app.api.routes import chat, conversations, feedback, health, images

API_PREFIX = "/api/v1"
HEALTH_PATH = f"{API_PREFIX}{health.PATH}"

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(feedback.router)
api_router.include_router(conversations.router)
api_router.include_router(images.router)
