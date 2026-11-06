"""Bounded model-selected read tools. No shell, crawler, persistence or implicit knowledge fallback."""

import asyncio
import json
import time
import unicodedata
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.llm import LLMError
from app.adapters.tavily import WebHit, WebSearchError
from app.api.schemas.chat import Clarification, ClarificationField
from app.rag.agent import spend
from app.rag.output import decode_output
from app.rag.prompts import prompt, rewrite_prompt
from app.rag.retriever import document_to_hit, hit_to_document
from core.errors import UnavailableError, UpstreamError
from core.types import Hit


class ToolStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["local_search", "web_search", "source_snapshot", "calculator", "finish", "clarify", "stop"]
    query: str = Field(default="", max_length=1000)
    snapshot_ids: list[str] = Field(default_factory=list, max_length=5)
    allocation: dict[str, int] = Field(default_factory=dict, max_length=8)
    question: str = Field(default="", max_length=1000)
    missing: list[ClarificationField] = Field(default_factory=list, max_length=2)
    reason: Literal["initial", "missing_evidence", "different_query", "player_detail", "sufficient", "unavailable"]


def key(action, arguments):
    return action, unicodedata.normalize("NFKC", " ".join(arguments.split())).casefold()


async def run_tools(pipe, state):
    from app.rag.gameplay_knowledge import load_pack, trusted_rule_kind
    from app.rag.pipeline import context_item, select_context

    p, req = state["prepared"], state["req"]
    if p.trace["web_search"]["requested"] == "always" and not pipe.settings.web_search_available:
        raise UnavailableError("Tìm trên web hiện chưa khả dụng.")
    catalog = (
        {
            row["id"]: row
            for group in load_pack()["groups"]
            for row in group["hits"]
            if pipe.policy.exclusion_reason(row["payload"], spoilers=req.options.spoilers) is None
        }
        if pipe.settings.gameplay_knowledge_enabled
        else {}
    )
    hits, seen, observations = {}, set(), []
    local_calls, web_calls = 0, 0
    actions = p.trace["tool_actions"] = []
    stop_reason = "step_budget"
    for _ in range(pipe.settings.chat_tool_steps):
        # Reserve one generation call; repairs still obey the shared turn budget.
        if len(p.trace.get("model_calls", [])) >= pipe.settings.chat_agent_max_calls - 1:
            stop_reason = "model_budget"
            break
        selected = select_context(
            list(hits.values()), 5, pipe.settings.rag_context_chars, policy=pipe.policy, spoilers=req.options.spoilers
        )
        available = ["finish", "stop", "clarify"]
        if local_calls < pipe.settings.chat_tool_queries and pipe.retriever is not None:
            available.append("local_search")
        if state["search_mode"] != "off" and not web_calls and pipe.web_search is not None:
            available.append("web_search")
        if catalog:
            available.append("source_snapshot")
        if {"level_rule", "class_rule", "weapon_rule", "respec_rule"}.issubset(
            {trusted_rule_kind(h) for h in selected}
        ):
            available.append("calculator")
        payload = {
            "request": state["resolved_question"],
            "initial_query": state["query"],
            "answer_language": p.lang,
            "web_policy": state["search_mode"],
            "available_actions": available,
            "remaining_steps": pipe.settings.chat_tool_steps - len(actions),
            "observations": observations[-3:],
            "evidence": [context_item(h, i + 1) for i, h in enumerate(selected)],
            "snapshots": [{"id": k, "title": v["payload"]["title"]} for k, v in catalog.items()][:40],
        }
        spend(p.trace, "tool_decision", p.max_calls)
        try:
            async with asyncio.timeout(pipe.settings.chat_agent_timeout_seconds):
                result = await pipe.llm.invoke_chain(
                    rewrite_prompt()
                    | pipe.llm.bind_model(json_output=True, thinking=False, temperature=0, max_tokens=768),
                    {"policy": prompt("tools"), "history": [], "question": json.dumps(payload, ensure_ascii=False)},
                )
            data, _ = decode_output(result.content)
            step = ToolStep.model_validate(data)
        except (LLMError, ValueError):
            raise UpstreamError("Bước chọn công cụ của mô hình chưa hợp lệ.") from None
        except TimeoutError:
            raise UnavailableError("Bước chọn công cụ vượt thời gian xử lý.") from None
        action = step.action
        row = {"action": action, "reason": step.reason, "status": "running"}
        if state.get("diagnostic_queries"):
            row["query"] = step.query
        actions.append(row)
        arguments = (
            step.query
            if action in {"local_search", "web_search"}
            else json.dumps({"ids": sorted(step.snapshot_ids), "allocation": step.allocation}, sort_keys=True)
        )
        identity = key(action, arguments)
        if action not in available or (identity in seen and action not in {"finish", "stop", "clarify"}):
            row["status"] = "denied"
            observations.append({"action": action, "status": "not_available_or_duplicate"})
            continue
        seen.add(identity)
        if action in {"finish", "stop"}:
            if state["search_mode"] == "always" and not web_calls:
                row["status"] = "denied_web_required"
                observations.append({"status": "always_requires_web_before_finish"})
                continue
            row["status"] = "ok"
            stop_reason = action
            break
        if action == "clarify":
            rounds = (p.player_state or {}).get("clarification_rounds", 0)
            if not step.question.strip() or not step.missing or rounds >= 3:
                raise UpstreamError("Câu hỏi bổ sung chưa hợp lệ hoặc vượt giới hạn.")
            p.clarification = Clarification(
                id=uuid4(),
                question=step.question,
                fields=step.missing,
                expires_at=datetime.fromtimestamp(time.time() + 1800, UTC).isoformat(),
            )
            p.player_state.update(pending=p.clarification.model_dump(mode="json"), clarification_rounds=rounds + 1)
            p.static_answer = step.question
            row["status"] = "ok"
            stop_reason = "clarify"
            break
        started = time.perf_counter()
        found = []
        try:
            if action in {"local_search", "web_search"} and not step.query.strip():
                raise ValueError("empty_query")
            if action == "local_search":
                local_calls += 1
                retriever = pipe.retriever.model_copy(
                    update={"spoilers": req.options.spoilers, "limit": pipe.settings.rag_prefetch}
                )
                async with asyncio.timeout(min(5, pipe.settings.rag_retrieval_timeout_seconds)):
                    docs = await retriever.ainvoke(step.query)
                    found = [document_to_hit(d) for d in docs[: pipe.settings.rag_prefetch]]
            elif action == "web_search":
                web_calls += 1
                found, diagnostic = await pipe.web_search.search(step.query)
                p.trace["web_search"].update(status="ok", trigger="agent_tool", **diagnostic)
            elif action == "source_snapshot":
                if not step.snapshot_ids or any(k not in catalog for k in step.snapshot_ids):
                    raise ValueError("unknown_snapshot")
                found = [Hit(k, 0.0, dict(catalog[k]["payload"])) for k in step.snapshot_ids]
            elif action == "calculator":
                from app.rag.build_math import check_allocation

                profile = {c["key"]: c["value"] for c in (p.player_state or {}).get("constraints", [])}
                row["calculation"] = check_allocation(step.allocation, profile)
            for h in found:
                if (
                    isinstance(h, WebHit)
                    or pipe.policy.exclusion_reason(h.payload, spoilers=req.options.spoilers) is None
                ):
                    hits[h.id] = h
            row.update(status="ok", returned=len(found))
        except (UnavailableError, TimeoutError, WebSearchError, ValueError) as exc:
            row.update(status="error", error_type=type(exc).__name__)
        row["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        observations.append({k: v for k, v in row.items() if k != "query"})
    p.trace["tool_stop"] = stop_reason
    if state["search_mode"] == "always" and not web_calls and p.static_answer is None:
        raise UnavailableError("Agent chưa hoàn tất tìm web bắt buộc trong ngân sách.")
    if web_calls and p.trace["web_search"]["status"] != "ok" and not hits:
        raise UnavailableError("Tìm trên web đang gặp sự cố.")
    state["documents"] = [hit_to_document(h) for h in hits.values() if not isinstance(h, WebHit)]
    state["web_hits"] = [h for h in hits.values() if isinstance(h, WebHit)]
    return state
