"""Validated optional rewrite; invalid/provider output falls back to original question.

Phụ trách: TV3 · [S3] Query rewrite
"""

import re
from collections import Counter
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


def preserves_numbers(question: str, query: str) -> bool:
    """Fail back to the original query if a rewrite loses levels, stats, upgrade or patch literals."""
    pattern = r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)"
    expected = Counter(re.findall(pattern, question))
    actual = Counter(re.findall(pattern, query))
    return all(actual[number] >= count for number, count in expected.items())


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
        rewritten = RewriteResult.model_validate_json(result.content)
        if (
            not rewritten.out_of_scope
            and not rewritten.ambiguous
            and not preserves_numbers(question, rewritten.standalone_query_en)
        ):
            raise ValueError("Rewrite dropped numeric constraints")
        return rewritten, False
    except (LLMError, ValidationError, ValueError):
        return fallback, True
