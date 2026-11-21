"""True Agent: one native tool-calling loop prepares every RAG turn (GĐ2, 22/11/2026).

Replaces the former multi-role preparation (Agent decision → Tool planner → Assessor). The model decides what the
player asks, which conditions apply, what to search, whether a name is the one meant, whether to ask back and
which evidence supports the answer. The server only runs tools, checks them with deterministic guards (corpus
policy, provenance of player conditions, quoted numbers, arithmetic, web policy) and keeps the budget. Every
rejection goes back to the model as a tool result so it can fix its own call. The existing Generator and Answer
Guard still write and check the final answer from the evidence the Agent chose.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm import LLMError
from app.adapters.tavily import WebHit, WebSearchError
from app.api.schemas.chat import Clarification, ClarificationField
from app.rag.build_data import build_rules, check, level_rule
from app.rag.entity_spelling import matching_names
from app.rag.matching import contains_name, contains_text
from app.rag.prompts import prompt
from app.rag.retriever import document_to_hit, hit_to_document
from core.errors import UnavailableError, UpstreamError

logger = logging.getLogger(__name__)
STATE_TTL_SECONDS = 1800
PREVIEW_CHARS = 320
RESULTS_PER_SEARCH = 8
INTENTS = Literal["lore", "acquisition", "mechanics", "build", "route", "quest", "comparison", "overview", "other"]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(_Args):
    query: str = Field(min_length=1, max_length=300, description="Focused English search query")


class NameArgs(_Args):
    name: str = Field(min_length=1, max_length=100, description="The player's spelling of the name")


class OpenArgs(_Args):
    ids: list[str] = Field(min_length=1, max_length=5, description="Evidence IDs from earlier tool results")


class Condition(_Args):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$", description="e.g. level, starting_class, weapon, goal")
    value: str = Field(min_length=1, max_length=120, description="Exactly as the player wrote it")
    source_id: str = Field(
        min_length=1, max_length=100, description='"current" or the memory/condition ID it came from'
    )


class ConditionArgs(_Args):
    set: list[Condition] = Field(default_factory=list, max_length=10, description="Conditions to add or replace")
    retire: list[str] = Field(default_factory=list, max_length=10, description="Keys the player withdrew or replaced")


class CalculatorArgs(_Args):
    allocation: dict[str, int] = Field(description="Targets per attribute (vigor, mind, …); unset ones stay at floor")
    fill: str = Field(default="", description="One attribute that takes the remaining points, or empty")
    build_data: dict = Field(
        default_factory=dict,
        description=(
            "Quoted facts: {weapon, requirements: {attribute: NUMBER}, starting_class: {name, level: NUMBER, "
            "base: {all eight attributes: NUMBER}}}; NUMBER = {value:int, source_id:evidence ID, quote_id:'q0', "
            "label:'exact label in the quote'}"
        ),
    )


class Missing(_Args):
    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80, description="Short label in the player's language")


class AskArgs(_Args):
    question: str = Field(min_length=1, max_length=500, description="One natural question in the player's language")
    missing: list[Missing] = Field(min_length=1, max_length=2, description="What the player should tell you")
    answer_language: Literal["vi", "en"]


class ReplyArgs(_Args):
    text: str = Field(
        min_length=1, max_length=2000, description="Reply in the player's language, without new game facts"
    )
    answer_language: Literal["vi", "en"]
    about_conversation: bool = Field(
        default=False, description="The player asked about this conversation (what was asked or answered)"
    )
    end_task: bool = Field(default=False, description="The player cancelled the current request")
    unrelated: bool = Field(default=False, description="The request is not about Elden Ring")


class FinishArgs(_Args):
    request: str = Field(min_length=1, max_length=1000, description="The player's request as one standalone question")
    intent: INTENTS
    answer_language: Literal["vi", "en"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=5, description="Evidence supporting the answer")
    gameplay_advice: bool = Field(default=False, description="General gameplay know-how may supplement evidence")


TOOLS = {
    "search_corpus": (SearchArgs, "Search the local Elden Ring wiki corpus."),
    "search_web": (SearchArgs, "Search the web when the corpus cannot fill a gap."),
    "check_name": (NameArgs, "Look up a possibly misspelled proper name; returns candidate titles."),
    "open_evidence": (OpenArgs, "Show the full text and quote IDs of evidence already seen."),
    "set_conditions": (ConditionArgs, "Record or retire the player's conditions (level, class, weapon, goal…)."),
    "calculator": (CalculatorArgs, "Check an eight-attribute allocation against the level, class floors and weapon."),
    "ask_user": (AskArgs, "Ask the player one question and stop."),
    "reply": (
        ReplyArgs,
        "Reply without new game facts and stop: greetings, cancel, unrelated requests, or questions about this "
        "conversation answered from recent_turns.",
    ),
    "finish": (FinishArgs, "Stop; the answer is written from the chosen evidence."),
}


def tool_specs(*, web: bool, calculator: bool = True, ask: bool = True) -> list[dict]:
    skip = set()
    if not web:
        skip.add("search_web")
    if not calculator:
        skip.add("calculator")
    if not ask:
        skip.add("ask_user")
    return [
        {"type": "function", "function": {"name": name, "description": doc, "parameters": model.model_json_schema()}}
        for name, (model, doc) in TOOLS.items()
        if name not in skip
    ]


def _preview(hit) -> dict:
    p = hit.payload
    return {
        "id": hit.id,
        "title": p.get("title"),
        "section": p.get("section"),
        "origin": "web" if isinstance(hit, WebHit) else "corpus",
        **{k: p[k] for k in ("source_type", "game_scope", "patch_version") if p.get(k) is not None},
        "text": p["text"][:PREVIEW_CHARS],
        "truncated": len(p["text"]) > PREVIEW_CHARS,
    }


def _web_results(found) -> list[dict]:
    """Web blocks grouped by page in page order, with short previews; the Agent opens what it needs."""
    pages: dict[str, dict] = {}
    for h in found:
        page = pages.setdefault(
            h.payload["url"], {"url": h.payload["url"], "title": h.payload.get("title"), "blocks": []}
        )
        page["blocks"].append({"id": h.id, "section": h.payload.get("section"), "text": h.payload["text"][:200]})
    return list(pages.values())


def working_state(state: dict) -> tuple[dict, dict | None]:
    """The conversation's working state if still valid, and the pending clarification (if any)."""
    req = state["req"]
    working = state.get("player") if isinstance(state.get("player"), dict) else {}
    if req.channel == "discord" and (req.external_ref or "").startswith("discord:thread:"):
        working = {}  # No verified actor identity in the shared-thread transport.
    if time.time() - working.get("updated", 0) > STATE_TTL_SECONDS:
        working = {}
    pending = working.get("pending")
    if pending and datetime.fromisoformat(pending["expires_at"]).timestamp() <= time.time():
        working, pending = {}, None
    if req.clarification_id and (not pending or str(req.clarification_id) != pending["id"]):
        from core.errors import BadRequestError

        raise BadRequestError("Câu hỏi bổ sung đã hết hạn hoặc không thuộc hội thoại này.")
    return working, pending


async def run_agent(pipe, state: dict) -> dict:
    """Fill the preparation state: evidence, conditions, clarification or a static reply."""
    from app.rag.pipeline import context_item

    p, req = state["prepared"], state["req"]
    trace = p.trace
    working, pending = working_state(state)
    replying = bool(req.clarification_id and pending)
    conditions = {c["key"]: dict(c) for c in working.get("constraints", [])}
    memories = state.get("memory_candidates", [])
    sources = {"current": req.message, **{m["source_id"]: m["text"] for m in memories}}
    # A memory may be named by its row ID; conditions are stored with the user message it came from.
    aliases = {m["id"]: m["source_id"] for m in memories if m.get("id") and m["id"] != m["source_id"]}
    for row_id, source_id in aliases.items():
        sources.setdefault(row_id, sources[source_id])
    for c in conditions.values():
        if c["source_id"] != "current":
            sources.setdefault(c["source_id"], c["value"])
    if replying:
        sources["request"] = working.get("request_text", "")
    rounds = working.get("clarification_rounds", 0) if replying else 0
    limit = pipe.settings.chat_clarification_max_rounds
    can_ask = limit is None or rounds < limit
    web = state["search_mode"] != "off" and pipe.web_search is not None
    hits: dict = {}
    calculator_attempts = web_calls = local_ok = local_failed = 0
    retired: set[str] = set()
    started = time.perf_counter()
    deadline = state.get("started", started) + pipe.settings.prepare_budget_seconds
    # Web auto keeps the larger coverage budget; other modes the per-turn Agent budget (one call is for writing).
    max_calls = (
        pipe.settings.chat_coverage_max_calls
        if state.get("verify_coverage") or pipe.settings.chat_agent_max_calls is None
        else pipe.settings.chat_agent_max_calls
    )
    trace["agent"] = {"status": "running", "steps": []}
    trace["web_search"]["status"] = "not_run"

    def active_profile() -> dict:
        return {k: c["value"] for k, c in conditions.items()}

    payload = {
        "player_message": req.message,
        **(
            {
                "replying_to": {
                    "id": pending["id"],
                    "question": pending["question"],
                    "original_request": working.get("request_text"),
                }
            }
            if replying
            else {}
        ),
        "conditions": list(conditions.values()),
        "memories": [{k: m[k] for k in ("id", "source_id", "text", "kind") if k in m} for m in memories],
        "recent_turns": state.get("recent_turns", []),
        "requested_language": req.options.lang,
        "web_policy": state["search_mode"] if web else "off",
        "can_ask_user": can_ask,
    }
    messages = [SystemMessage(prompt("true_agent")), HumanMessage(json.dumps(payload, ensure_ascii=False))]
    bound = pipe.llm.model.bind_tools(
        tool_specs(web=web, ask=can_ask),
        tool_choice="auto",
        max_tokens=4096,
        temperature=0,
        extra_body={"thinking": {"type": "disabled"}},
    )

    def admit(found) -> list:
        new = []
        for h in found:
            ok = (
                state["search_mode"] != "off"
                if isinstance(h, WebHit)
                else pipe.policy.exclusion_reason(h.payload) is None
            )
            if ok:
                hits[h.id] = h
                new.append(h)
        return new

    async def local(query: str) -> list:
        nonlocal local_ok, local_failed
        local_failed += 1  # Counted as a success below once the retriever answered.
        retriever = pipe.retriever.model_copy(
            update={"limit": pipe.settings.rag_prefetch, "search_timeout_seconds": 5, "rerank_deadline": deadline}
        )
        async with asyncio.timeout(5 + getattr(retriever, "reranker_timeout_seconds", 0) + 0.1):
            docs = await retriever.ainvoke(query)
        local_failed, local_ok = local_failed - 1, local_ok + 1
        found = [document_to_hit(d) for d in docs[: pipe.settings.rag_prefetch]]
        # Retrieval IDs/scores per local search, for the debugging trace (not a relevance claim).
        trace.setdefault("retrieved", []).extend(
            {"id": h.id, "score": h.score, "title": h.payload.get("title"), "url": h.payload.get("url")} for h in found
        )
        return found

    def stated(c: Condition) -> bool:
        text = sources.get(c.source_id)
        return text is not None and (contains_text(text, c.value) or contains_name(text, c.value))

    async def execute(name: str, raw: dict):
        """(result for the model, terminal outcome or None)."""
        nonlocal calculator_attempts, web_calls
        if name not in TOOLS or (name == "search_web" and not web) or (name == "ask_user" and not can_ask):
            return {"status": "error", "error": f"Tool {name} is not available"}, None
        try:
            args = TOOLS[name][0].model_validate(raw)
        except ValidationError as exc:
            fields = [".".join(map(str, e["loc"])) + ": " + e["type"] for e in exc.errors(include_input=False)][:5]
            return {"status": "error", "error": "Invalid arguments", "fields": fields}, None
        if name == "search_corpus":
            found = admit(await local(args.query))
            return {"status": "ok", "results": [_preview(h) for h in found[:RESULTS_PER_SEARCH]]}, None
        if name == "search_web":
            web_calls += 1
            try:
                found, diagnostic = await pipe.web_search.search(args.query)
            except WebSearchError as exc:
                trace["web_search"].update(status="error", reason=getattr(exc, "reason", type(exc).__name__))
                return {"status": "error", "error": "Web search failed"}, None
            trace["web_search"].update(status="ok", trigger="agent_tool", **diagnostic)
            return {"status": "ok", "pages": _web_results(admit(found))}, None
        if name == "check_name":
            found = admit(await local(args.name))
            matches, close = matching_names(args.name, found)
            return {
                "status": "ok",
                "candidates": [title for title, _ in matches][:5],
                "single_close_match": close and len(matches) == 1,
                "results": [_preview(h) for h in found[:RESULTS_PER_SEARCH]],
            }, None
        if name == "open_evidence":
            unknown = [i for i in args.ids if i not in hits]
            if unknown:
                return {"status": "error", "error": "Unknown evidence IDs", "ids": unknown}, None
            return {
                "status": "ok",
                "evidence": [{**context_item(hits[i], n), "id": i} for n, i in enumerate(args.ids, 1)],
            }, None
        if name == "set_conditions":
            # Provenance only: each value must appear in the source it names (the player's words or memory).
            unstated = [c.key for c in args.set if not stated(c)]
            if unstated:
                return {
                    "status": "error",
                    "error": "Values must be the player's own words from the named source",
                    "keys": unstated,
                }, None
            for key in args.retire:
                if conditions.pop(key, None) is not None:
                    retired.add(key)
            for c in args.set:
                row = c.model_dump()
                if row["source_id"] in aliases:
                    row["source_id"] = aliases[row["source_id"]]
                    trace["agent"]["normalized_source_refs"] = trace["agent"].get("normalized_source_refs", 0) + 1
                conditions[c.key] = row
            return {"status": "ok", "conditions": list(conditions.values())}, None
        if name == "calculator":
            calculator_attempts += 1
            if calculator_attempts > pipe.settings.chat_calculator_max_failures + 1:
                return {"status": "error", "error": "Calculator budget used; finish with a reference suggestion"}, None
            profile = active_profile()
            if build_rules(profile) is None:
                return {"status": "error", "error": "Record the player's level with set_conditions first"}, None
            try:
                p.checked_build = check(
                    args.build_data, args.allocation, profile, list(hits.values()), args.fill or None
                )
            except (ValueError, ValidationError) as exc:
                return {"status": "error", "error": str(exc)[:500]}, None
            rule_hit, _ = level_rule()
            hits[rule_hit.id] = rule_hit
            keep = ("allocation", "starting_class", "weapon", "class_floor_verified", "requirements_checked")
            return {
                "status": "ok",
                "checked_build": {k: p.checked_build[k] for k in keep},
                "rule_source": rule_hit.id,
            }, None
        if name == "finish" and state["search_mode"] == "always" and not web_calls and web:
            return {"status": "error", "error": "Web policy is always: call search_web before finish"}, None
        return {"status": "ok"}, (name, args)

    outcome = None
    calls = 0
    while outcome is None:
        if calls >= max_calls - 1 or len(trace["agent"]["steps"]) >= max_calls:
            break
        if time.perf_counter() > deadline and calls:
            messages.append(HumanMessage("Time budget exhausted: call finish now with what you have."))
        calls += 1
        trace.setdefault("model_calls", []).append({"phase": "agent"})
        try:
            async with asyncio.timeout(pipe.settings.chat_agent_timeout_seconds):
                ai = await bound.ainvoke(messages)
        except TimeoutError:
            if hits:
                break
            raise UnavailableError("Bước Agent vượt thời gian xử lý.") from None
        except Exception as exc:  # noqa: BLE001 - provider failure; answer from evidence when there is some
            logger.warning("Agent model error", extra={"data": {"error": type(exc).__name__}})
            if hits:
                break
            raise UpstreamError("Dịch vụ mô hình đang gặp sự cố. Vui lòng thử lại.") from None
        usage = ai.usage_metadata or {}
        # Same keys as the generation usage, so token_usage() and the stored trace count the Agent too.
        agent_usage = trace["agent"].setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0})
        agent_usage["prompt_tokens"] += usage.get("input_tokens") or 0
        agent_usage["completion_tokens"] += usage.get("output_tokens") or 0
        messages.append(ai)
        # A call whose arguments are not valid JSON lands in invalid_tool_calls; every call ID needs a reply.
        for bad in ai.invalid_tool_calls:
            trace["agent"]["steps"].append({"tool": bad.get("name") or "?", "status": "invalid_arguments"})
            messages.append(
                ToolMessage(
                    json.dumps({"status": "error", "error": "Arguments were not valid JSON; send the call again"}),
                    tool_call_id=bad["id"],
                )
            )
        if not ai.tool_calls:
            if not ai.invalid_tool_calls:
                messages.append(HumanMessage("Call a tool; end with finish, ask_user or reply, not plain text."))
            continue
        for call in ai.tool_calls:
            t0 = time.perf_counter()
            try:
                result, terminal = await execute(call["name"], call.get("args") or {})
            except (UnavailableError, TimeoutError, LLMError, WebSearchError) as exc:
                result, terminal = {"status": "error", "error": type(exc).__name__}, None
            trace["agent"]["steps"].append(
                {"tool": call["name"], "status": result.get("status"), "ms": round((time.perf_counter() - t0) * 1000)}
            )
            messages.append(ToolMessage(json.dumps(result, ensure_ascii=False), tool_call_id=call["id"]))
            if terminal is not None:
                outcome = terminal
                # Remaining calls of this message get no reply: the loop ends here, nothing is sent after them.
                break

    if outcome is None and calls and not any(s["status"] == "ok" for s in trace["agent"]["steps"]):
        # The model never made a usable tool call: a provider failure, not an empty "no information" answer.
        trace["agent"]["status"] = "invalid_decision"
        raise UpstreamError("Mô hình chưa trả quyết định hợp lệ. Vui lòng thử lại.")
    trace["agent"].update(status="ok" if outcome else "budget", model_calls=calls)
    trace["tool_stop"] = outcome[0] if outcome else "model_budget"
    # Room for writing the answer: generation, one format repair, the Answer Guard and image selection.
    p.max_calls = len(trace.get("model_calls", [])) + 4
    name, args = outcome if outcome else ("finish", None)
    if req.options.lang == "auto":
        # The Agent's declared language; if it never declared one, the conversation's language, else Vietnamese.
        lang = getattr(args, "answer_language", None) or working.get("lang") or "vi"
        p.lang = state["answer_language"] = lang
    action = {"ask_user": "clarify", "reply": "respond"}.get(name, "retrieve")
    if name == "reply":
        intent = (
            "cancel"
            if args.end_task
            else "out_of_scope"
            if args.unrelated
            else "conversation"
            if args.about_conversation
            else "smalltalk"
        )
    else:
        intent = getattr(args, "intent", None) or "other"
    request = getattr(args, "request", None) or (working.get("request_text") if replying else None) or req.message
    p.agent_decision = {"action": action, "intent": intent, "resolved_question": request}
    trace["agent"].update(action=action, intent=intent)
    trace["memory"]["selected_ids"] = sorted(
        {c["source_id"] for c in conditions.values() if c["source_id"] not in {"current", "request"}}
    )
    p.player_state = {
        "constraints": list(conditions.values()),
        "original": working.get("original", req.message) if replying else req.message,
        "request_text": working.get("request_text", req.message) if replying else req.message,
        "clarification_rounds": rounds + int(name == "ask_user"),
        "intent": intent,
        "lang": p.lang,
        "pending": None,
        "updated": time.time(),
        **({"retired_condition_keys": sorted(retired)} if retired else {}),
    }
    if intent == "cancel":
        p.player_state = {"updated": time.time(), "constraints": [], "pending": None}
    state["next_player"] = p.player_state
    state["history"] = []
    state["resolved_question"] = request
    trace["rewritten_query"] = request
    state["overview"] = intent == "overview"
    if state["overview"]:
        trace["request_kind"] = "overview"
    if name == "ask_user":
        p.clarification = Clarification(
            id=uuid4(),
            question=args.question,
            fields=[ClarificationField(key=m.key, label=m.label) for m in args.missing],
            expires_at=datetime.fromtimestamp(time.time() + STATE_TTL_SECONDS, UTC).isoformat(),
        )
        p.player_state["pending"] = p.clarification.model_dump(mode="json")
        p.static_answer = args.question
    elif name == "reply":
        p.static_answer = args.text
    else:
        p.gameplay_advice = bool(args and args.gameplay_advice)
        chosen = [i for i in (args.evidence_ids if args else []) if i in hits]
        trace["evidence_selection"] = (
            {"method": "model", "ids": chosen} if chosen else {"method": "all_evidence", "ids": list(hits)}
        )
        if p.checked_build is not None or calculator_attempts:
            trace["build_check"] = {
                "status": "checked" if p.checked_build is not None else "failed",
                "failed_attempts": calculator_attempts - int(p.checked_build is not None),
                "class_given": "starting_class" in conditions,
                "weapon_given": "weapon" in conditions,
            }
        if not hits and local_failed and not local_ok and not p.gameplay_advice:
            # The corpus itself was unavailable: a service error, not an empty "no information" answer.
            raise UnavailableError("Kho tri thức chưa sẵn sàng.")
        if web and state["search_mode"] == "always" and not web_calls and not hits:
            raise UnavailableError("Agent chưa hoàn tất tìm web bắt buộc trong ngân sách.")
    state["documents"] = [hit_to_document(h) for h in hits.values() if not isinstance(h, WebHit)]
    state["web_hits"] = [h for h in hits.values() if isinstance(h, WebHit)]
    return state
