"""Validated optional rewrite; invalid/provider output falls back to original question.

Phụ trách: TV3 · [S3] Query rewrite
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm import LLMError
from app.rag.prompts import prompt, rewrite_prompt


class RewriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    standalone_query_en: str = Field(min_length=1, max_length=2000)
    lang: Literal["vi", "en"]
    entities: list[str] = Field(max_length=20)
    out_of_scope: bool
    ambiguous: bool


async def rewrite(llm, question: str, history: list[dict], lang: str) -> tuple[RewriteResult, bool]:
    fallback = RewriteResult(
        standalone_query_en=question,
        lang=lang,
        entities=[],
        out_of_scope=False,
        ambiguous=False,
    )
    try:
        chain = rewrite_prompt() | llm.bind_model(json_output=True)
        result = await llm.invoke_chain(chain, {"policy": prompt("rewrite"), "history": history, "question": question})
        return RewriteResult.model_validate_json(result.content), False
    except (LLMError, ValidationError, ValueError):
        return fallback, True
