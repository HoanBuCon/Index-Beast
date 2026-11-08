"""Public capability flags only; no secrets, provider or infrastructure details."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_ctx
from app.context import AppContext

router = APIRouter(tags=["chat"])


class ChatCapabilities(BaseModel):
    web_search_available: bool
    # Web chỉ hiện liên kết "Xem trace" khi API có bật /admin/* (ADMIN_TOKEN); không lộ token
    trace_available: bool = False


@router.get("/chat/capabilities", response_model=ChatCapabilities)
async def capabilities(ctx: AppContext = Depends(get_ctx)):
    return ChatCapabilities(
        web_search_available=ctx.settings.web_search_available, trace_available=ctx.settings.admin_enabled
    )
