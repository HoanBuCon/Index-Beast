"""Evidence coverage assessment and stable source interleaving, not score fusion."""

import asyncio
import json

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.llm import LLMError
from app.rag.output import decode_output
from app.rag.prompts import prompt, rewrite_prompt


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: str = Field(pattern=r"^(sufficient|partial|insufficient|ambiguous)$")
    covered: list[str] = Field(max_length=10)
    missing: list[str] = Field(max_length=10)
    evidence: dict[str, str] = Field(max_length=5)


async def assess(llm, question, history, context, deadline_seconds):
    if not context:
        return "insufficient", {"status": "insufficient", "reason": "no_context"}
    try:
        async with asyncio.timeout(deadline_seconds):
            result = await llm.invoke_chain(
                rewrite_prompt() | llm.bind_model(json_output=True, thinking=False, temperature=0, max_tokens=512),
                {
                    "policy": prompt("assess"),
                    "history": history,
                    "question": json.dumps({"question": question, "context": context}, ensure_ascii=False),
                },
            )
        data, _ = decode_output(result.content)
        parsed = Assessment.model_validate(data)
        for index, quote_id in parsed.evidence.items():
            row = next((c for c in context if str(c["index"]) == index), None)
            if row is None or quote_id not in row["evidence_units"]:
                raise ValueError("Invalid evidence reference")
        if parsed.status == "sufficient" and (not parsed.evidence or not parsed.covered or parsed.missing):
            raise ValueError("Incomplete coverage")
        return parsed.status, {"status": parsed.status, "reason": "assessed"}
    except (TimeoutError, LLMError, ValueError):
        # Conservative search fallback, not proof of absence or fabricated confidence.
        return "insufficient", {"status": "unknown", "reason": "assessment_failed"}


def merge_evidence(local, web):
    """Web first for uncovered requests; alternate origins, dedup by URL+text, no score arithmetic."""
    if not web:
        return local
    merged, seen = [], set()
    for index in range(max(len(local), len(web))):
        for rows in (web, local):
            if index < len(rows):
                hit = rows[index]
                key = hit.id
                if key not in seen:
                    seen.add(key)
                    merged.append(hit)
    return merged
