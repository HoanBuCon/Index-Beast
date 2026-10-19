"""API tạm để so sánh DeepSeek thinking/non-thinking. Chỉ mount ở dev/test.

Phụ trách: TV3 (MinhMuc) · [S1] Xác nhận DeepSeek
"""

from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.llm import LLMError
from app.api.deps import get_ctx
from app.api.schemas.llm_test import LLMTestIn, LLMTestOut, LLMTestUsage
from app.context import AppContext

router = APIRouter(tags=["dev: DeepSeek test"])


@router.post(
    "/dev/llm/test",
    response_model=LLMTestOut,
    summary="Thử DeepSeek thinking hoặc non-thinking (gọi API thật, có dùng credits)",
    description="Dùng key server từ .env. Chưa dùng retrieval/RAG. Temperature chỉ có tác dụng khi thinking=false.",
)
async def test_llm(body: LLMTestIn, ctx: AppContext = Depends(get_ctx)) -> LLMTestOut:
    if ctx.llm is None:
        raise HTTPException(503, "Chưa có DEEPSEEK_API_KEY. Cập nhật .env rồi khởi động lại API.")
    start = perf_counter()
    try:
        result = await ctx.llm.complete(
            [
                {
                    "role": "system",
                    "content": "You are IndexBeast. Reply in the user's language and keep answers concise.",
                },
                {"role": "user", "content": body.message},
            ],
            thinking=body.thinking,
            reasoning_effort=body.reasoning_effort,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )
    except LLMError as exc:
        # LLMError đã bỏ thông tin nhạy cảm tại adapter, không forward raw SDK errors.
        raise HTTPException(502, str(exc)) from None
    return LLMTestOut(
        model=result.model,
        thinking=body.thinking,
        reasoning_effort=body.reasoning_effort if body.thinking else None,
        answer=result.content,
        reasoning_content=result.reasoning_content,
        finish_reason=result.finish_reason,
        latency_ms=round((perf_counter() - start) * 1000, 1),
        usage=LLMTestUsage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
            reasoning_tokens=result.reasoning_tokens,
        ),
    )
