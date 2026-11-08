"""Model-owned intent/clarification/resolve decisions, server-owned contracts and budgets."""

import asyncio
import json
import re
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.adapters.llm import LLMError
from app.api.schemas.chat import ClarificationField
from app.rag.output import decode_output
from app.rag.prompts import prompt, rewrite_prompt
from app.rag.rewrite import _contains, preserves_numbers
from core.errors import UnavailableError, UpstreamError


def spend(trace: dict, phase: str, maximum: int | None):
    if maximum is None:
        return
    calls = trace.setdefault("model_calls", [])
    if len(calls) >= maximum:
        raise UnavailableError("Lượt hỏi đã đạt giới hạn xử lý. Hãy gửi yêu cầu cụ thể hơn.")
    calls.append({"phase": phase})


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    value: str = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1, max_length=100)


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intent: Literal[
        "lore",
        "acquisition",
        "mechanics",
        "build",
        "route",
        "quest",
        "comparison",
        "gameplay_comparison",
        "overview",
        "smalltalk",
        "cancel",
        "out_of_scope",
        "other",
    ]
    turn_type: Literal["new", "followup", "correction", "clarification_reply"]
    action: Literal["retrieve", "clarify", "respond", "refuse"]
    rewrite: bool
    answer_language: Literal["vi", "en"] | None = None
    resolved_question: str = Field(max_length=3000)
    search_query: str = Field(max_length=2000)
    entities: list[str] = Field(max_length=20)
    selected_memory_ids: list[str] = Field(max_length=6)
    constraints: list[Constraint] = Field(max_length=10)
    missing: list[ClarificationField] = Field(max_length=2)
    reply: str = Field(max_length=1000)
    reason: Literal["ready", "missing_player_details", "ambiguous_subject", "conversation_control", "unrelated"]

    @model_validator(mode="after")
    def coherent(self):
        if self.action == "retrieve" and (not self.search_query.strip() or not self.resolved_question.strip()):
            raise ValueError("Retrieval requires a resolved question and query")
        if self.action == "clarify" and (not self.missing or not self.reply.strip()):
            raise ValueError("Clarification requires fields and a question")
        if self.action != "clarify" and self.missing:
            raise ValueError("Fields only belong to clarification")
        if self.action == "respond" and self.intent not in {"smalltalk", "cancel"}:
            raise ValueError("Game facts require evidence")
        if self.action == "refuse" and self.intent != "out_of_scope":
            raise ValueError("Only unrelated requests use refusal")
        if self.intent == "out_of_scope" and self.action != "refuse":
            raise ValueError("Out-of-scope decisions cannot execute game tools")
        if self.intent in {"smalltalk", "cancel"} and self.action != "respond":
            raise ValueError("Conversation controls do not require retrieval")
        if self.action in {"respond", "refuse"} and not self.reply.strip():
            raise ValueError("Response text missing")
        if self.action != "retrieve" and re.search(r"https?://|www\.|\[\d+\]", self.reply, re.I):
            raise ValueError("Conversation-control replies cannot invent sources")
        if self.action == "retrieve" and self.turn_type != "new" and not self.rewrite:
            raise ValueError("Dependent requests must be resolved")
        if len({c.key for c in self.constraints}) != len(self.constraints):
            raise ValueError("Duplicate constraint")
        if len(set(self.selected_memory_ids)) != len(self.selected_memory_ids):
            raise ValueError("Duplicate memory")
        return self


def normalize_sources(decision: AgentDecision, candidates: list[dict], working: dict):
    """Resolve a selected memory handle to its canonical user message, never invent provenance."""
    selected = [row for row in candidates if row["id"] in decision.selected_memory_ids]
    canonical = {"current", "request", *(row["source_id"] for row in selected)}
    canonical.update(c["source_id"] for c in working.get("constraints", []))
    normalized = decision.model_copy(deep=True)
    count = 0
    for constraint in normalized.constraints:
        aliases = [row for row in selected if row["id"] == constraint.source_id]
        if aliases and any(row["source_id"] != constraint.source_id for row in aliases):
            if len(aliases) != 1 or constraint.source_id in canonical:
                raise ValueError("Ambiguous memory/source reference")
            row = aliases[0]
            if not _contains(row["text"], constraint.value):
                raise ValueError("Constraint absent from selected memory")
            constraint.source_id = row["source_id"]
            count += 1
    return normalized, count


def check_decision(decision: AgentDecision, question: str, candidates: list[dict], working: dict):
    available = {row["id"]: row for row in candidates}
    if any(key not in available for key in decision.selected_memory_ids):
        raise ValueError("Unprovided memory reference")
    selected = [available[key] for key in decision.selected_memory_ids]
    sources = {"current": question}
    # Server-retained raw user request anchors pending work even when recall is empty/disabled.
    request_text = working.get("request_text", "") if decision.turn_type != "new" else ""
    if request_text:
        sources["request"] = request_text
    for row in selected:
        sources[row["source_id"]] = sources.get(row["source_id"], "") + "\n" + row["text"]
    # Working state contains only previously validated user constraints, with original provenance.
    for item in working.get("constraints", []):
        if item["source_id"] != "current":
            sources[item["source_id"]] = sources.get(item["source_id"], "") + "\n" + item["value"]
    for item in decision.constraints:
        if item.source_id not in sources or not _contains(sources[item.source_id], item.value):
            raise ValueError("Constraint not present in its user source")
        # An old question is not authority to reinstate a superseded player fact.
        latest = next((c for c in working.get("constraints", []) if c["key"] == item.key), None)
        if (
            item.source_id != "current"
            and latest
            and latest["value"] != item.value
            and not any(
                r.get("kind") == "fact" and r.get("key") == item.key and r["text"] == item.value for r in selected
            )
        ):
            raise ValueError("Superseded constraint")
    context = question + "\n" + "\n".join(row["text"] for row in selected)
    context += "\n" + request_text
    context += "\n" + "\n".join(c.value for c in decision.constraints)
    if any(not name.strip() or not _contains(context, name) for name in decision.entities):
        raise ValueError("Entity has no supplied user provenance")
    if decision.action == "retrieve":
        # Invariants only: no legacy name/intent classifier or equipment allowlist decides acceptance.
        # Without rewriting, retrieval executes the original question. An unused search_query
        # must not reject it (e.g. a model omits punctuation from a location name).
        queries = (
            (decision.search_query, decision.resolved_question) if decision.rewrite else (decision.resolved_question,)
        )
        for query in queries:
            if not preserves_numbers(question, query) or not preserves_numbers(query, context):
                raise ValueError("Query changed numeric constraints")
            for name in decision.entities:
                if not name.strip() or not _contains(context, name) or not _contains(query, name):
                    raise ValueError("Entity has no supplied user provenance")
            for goal in ("PvE", "PvP", "NG+"):
                if goal.casefold() in question.casefold() and goal.casefold() not in query.casefold():
                    raise ValueError("Goal dropped")
            if re.search(
                r"không (?:dùng|sử dụng|có)|tránh dùng|\bwithout\b|do not use|don't use", question, re.I
            ) and not re.search(r"\bwithout\b|\bavoid\b|\bexclude\b|\bnot\b|\bno\b|don't", query, re.I):
                raise ValueError("Negation dropped")
        if not decision.rewrite and decision.resolved_question != question:
            raise ValueError("A changed request must be labelled rewritten")
        if decision.turn_type != "new" and not decision.entities:
            raise ValueError("Dependent query lacks a resolved subject")
    return selected


async def decide(
    llm, question, candidates, working, lang, settings, trace, *, shared_thread=False, requested_lang="auto"
) -> AgentDecision | None:
    started = time.perf_counter()
    spend(trace, "decision", settings.chat_agent_max_calls)
    diagnostic = {"status": "error", "reason": "invalid_decision"}
    trace["agent"] = diagnostic
    try:
        payload = {
            "question": question,
            "answer_language": lang,
            "requested_language": requested_lang,
            "memories": candidates,
            "working_state": working,
            "shared_thread": shared_thread,
        }
        async with asyncio.timeout(settings.chat_agent_timeout_seconds):
            for attempt in range(2):
                result = await llm.invoke_chain(
                    rewrite_prompt() | llm.bind_model(json_output=True, thinking=False, temperature=0, max_tokens=1536),
                    {"policy": prompt("agent"), "history": [], "question": json.dumps(payload, ensure_ascii=False)},
                )
                data, _ = decode_output(result.content)
                try:
                    decision = AgentDecision.model_validate(data)
                    decision, normalized = normalize_sources(decision, candidates, working)
                    check_decision(decision, question, candidates, working)
                except ValueError as exc:
                    required = {k for k, v in AgentDecision.model_fields.items() if v.is_required()}
                    # Repair only a complete, recognizable decision; never turn arbitrary JSON into a fake success.
                    if (
                        attempt
                        or not isinstance(data, dict)
                        or not required <= data.keys()
                        or data.keys() - AgentDecision.model_fields.keys()
                        or len(trace.get("model_calls", [])) >= settings.chat_agent_max_calls - 1
                    ):
                        raise
                    from pydantic import ValidationError

                    issue = (
                        [
                            {"field": list(e["loc"]), "type": e["type"]}
                            for e in exc.errors(include_input=False, include_url=False)
                        ]
                        if isinstance(exc, ValidationError)
                        else str(exc)
                    )
                    payload["repair"] = {"previous_decision": data, "validation_error": issue}
                    diagnostic["repair_attempts"] = 1
                    spend(trace, "decision_repair", settings.chat_agent_max_calls)
                    continue
                diagnostic["normalized_source_refs"] = normalized
                diagnostic.update(
                    status="ok",
                    action=decision.action,
                    intent=decision.intent,
                    turn_type=decision.turn_type,
                    rewrite=decision.rewrite,
                    reason=decision.reason,
                    selected_memory_ids=decision.selected_memory_ids,
                    usage={"prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens},
                )
                return decision
    except LLMError:
        diagnostic["reason"] = "provider_error"
        raise UpstreamError("Dịch vụ mô hình đang gặp sự cố. Vui lòng thử lại.") from None
    except TimeoutError:
        diagnostic["reason"] = "timeout"
        raise UnavailableError("Bước hiểu yêu cầu vượt thời gian xử lý. Vui lòng thử lại.") from None
    except ValueError as exc:
        diagnostic["reason"] = "timeout" if isinstance(exc, TimeoutError) else "invalid_decision"
        return None
    finally:
        diagnostic["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
