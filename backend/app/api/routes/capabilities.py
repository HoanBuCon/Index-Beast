"""Public capability flags only; no secrets, provider or infrastructure details."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_ctx
from app.context import AppContext

router = APIRouter(tags=["chat"])


class ChatCapabilities(BaseModel):
    web_search_available: bool


@router.get("/chat/capabilities", response_model=ChatCapabilities)
async def capabilities(ctx: AppContext = Depends(get_ctx)):
    return ChatCapabilities(web_search_available=ctx.settings.web_search_available)
