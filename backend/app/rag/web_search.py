"""Evidence coverage assessment and stable source interleaving, not score fusion."""

import asyncio
import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.adapters.llm import LLMError
from app.rag.context_policy import dedup_web
from app.rag.output import decode_output
from app.rag.prompts import prompt, rewrite_prompt


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: str = Field(pattern=r"^(sufficient|partial|insufficient|ambiguous)$")
    covered: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]] = Field(
        max_length=10
    )
    missing: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]] = Field(
        max_length=10
    )
    evidence: dict[
        str, Annotated[list[Annotated[str, Field(pattern=r"^q\d{1,4}$")]], Field(min_length=1, max_length=3)]
    ] = Field(max_length=5)

    @field_validator("evidence", mode="before")
    @classmethod
    def legacy_string(cls, value):
        if not isinstance(value, dict):
            return value
        # Lossless compatibility: one string -> singleton list. Never drop multiple references.
        return {key: [ids] if isinstance(ids, str) else ids for key, ids in value.items()}


async def assess(llm, question, history, context, deadline_seconds):
    if not context:
        return "insufficient", {"status": "insufficient", "reason": "no_context", "decision": "local_insufficient"}
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
        for index, quote_ids in parsed.evidence.items():
            row = next((c for c in context if str(c["index"]) == index), None)
            if (
                row is None
                or len(set(quote_ids)) != len(quote_ids)
                or any(q not in row["evidence_units"] for q in quote_ids)
            ):
                raise ValueError("Invalid evidence reference")
        if parsed.status == "sufficient" and (not parsed.evidence or not parsed.covered or parsed.missing):
            raise ValueError("Incomplete coverage")
        return parsed.status, {
            "status": parsed.status,
            "reason": "assessed",
            "decision": "ambiguous" if parsed.status == "ambiguous" else f"local_{parsed.status}",
        }
    except (TimeoutError, LLMError, ValueError):
        # Conservative search fallback, not proof of absence or fabricated confidence.
        return "error", {"status": "unknown", "reason": "assessment_failed", "decision": "assessment_error"}


def merge_evidence(local, web):
    """Web first for uncovered requests; alternate origins, dedup by URL+text, no score arithmetic."""
    if not web:
        return local
    web = dedup_web(web)
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
