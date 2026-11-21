"""Spike (GĐ1 of the True Agent decision, 22/11/2026): one native tool-calling loop over the existing tools.

Not wired to the API and behind no flag: scripts call `run_true_agent` directly to compare with the multi-role
pipeline (Agent decision → Tool planner → Assessor → Generator). The model decides everything; the server only
runs tools, checks sources/arithmetic with the existing guards and keeps the budget. Rejections go back to the
model as tool results so it can fix its own call.

Two ways to write the final answer (`variant`):
- "generator": the Agent calls `finish` with evidence IDs; the existing Generator + Answer Guard write it.
- "final_answer": the Agent writes the answer itself; `validate_answer` checks citations and quotes, and any
  rejection or presentation issue goes back to the Agent once to fix.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.tavily import WebHit
from app.rag.build_data import build_rules, check, level_rule
from app.rag.entity_spelling import matching_names
from app.rag.generator import Generated, Prepared, RAGValidationError, validate_answer
from app.rag.matching import contains_name, contains_text
from app.rag.prompts import prompt
from app.rag.retriever import document_to_hit, hit_to_document

logger = logging.getLogger(__name__)
Variant = Literal["generator", "final_answer"]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(_Args):
    query: str = Field(min_length=1, max_length=300, description="Focused English search query")


class NameArgs(_Args):
    name: str = Field(min_length=1, max_length=100, description="The player's spelling of the name")


class OpenArgs(_Args):
    ids: list[str] = Field(min_length=1, max_length=5, description="Evidence IDs from earlier tool results")


class CalculatorArgs(_Args):
    level: str = Field(min_length=1, max_length=10, description="Target level exactly as the player wrote it")
    starting_class: str = Field(default="", max_length=60, description="Only if the player named their class")
    weapon: str = Field(default="", max_length=100, description="Only if the player named the weapon")
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


class AskArgs(_Args):
    question: str = Field(min_length=1, max_length=500, description="One natural question in the player's language")
    missing: list[str] = Field(min_length=1, max_length=2, description="What the player should tell you")


class ReplyArgs(_Args):
    text: str = Field(min_length=1, max_length=1000, description="Reply for greetings or unrelated requests")


class FinishArgs(_Args):
    request: str = Field(min_length=1, max_length=1000, description="The player's request as one standalone question")
    answer_language: Literal["vi", "en"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=5, description="Evidence supporting the answer")
    gameplay_advice: bool = Field(default=False, description="General gameplay know-how may supplement evidence")


class CitedSource(_Args):
    id: str = Field(description="Evidence ID")
    quote_ids: list[str] = Field(min_length=1, max_length=3, description="Quote IDs from open_evidence, e.g. q0")


class FinalAnswerArgs(_Args):
    answer: str = Field(min_length=1, max_length=16000, description="Markdown answer; [n] cites evidence[n-1]")
    answer_language: Literal["vi", "en"]
    evidence: list[CitedSource] = Field(default_factory=list, max_length=5)
    insufficient: bool = False
    limitation: str | None = Field(default=None, max_length=1000, description="What could not be confirmed")
    advisory: bool = Field(default=False, description="True only for uncited general gameplay advice")
    recommendation: str | None = Field(default=None, max_length=1000, description="Optional uncited suggestion")
    gameplay_advice: bool = False


TOOLS = {
    "search_corpus": (SearchArgs, "Search the local Elden Ring wiki corpus."),
    "search_web": (SearchArgs, "Search the web when the corpus cannot fill a gap."),
    "check_name": (NameArgs, "Look up a possibly misspelled proper name; returns candidate titles."),
    "open_evidence": (OpenArgs, "Show the full text and quote IDs of evidence already seen."),
    "calculator": (CalculatorArgs, "Check an eight-attribute allocation against level, class floors and weapon."),
    "ask_user": (AskArgs, "Ask the player one question and stop."),
    "reply": (ReplyArgs, "Reply without game facts (greetings, unrelated requests) and stop."),
    "finish": (FinishArgs, "Stop searching; the answer is written from the chosen evidence."),
    "final_answer": (FinalAnswerArgs, "Write the final cited answer yourself and stop."),
}


def tool_specs(variant: Variant, *, web: bool) -> list[dict]:
    skip = {"final_answer"} if variant == "generator" else {"finish"}
    if not web:
        skip.add("search_web")
    return [
        {"type": "function", "function": {"name": name, "description": doc, "parameters": model.model_json_schema()}}
        for name, (model, doc) in TOOLS.items()
        if name not in skip
    ]


FINAL_ANSWER_POLICY = """
When you have the evidence, call final_answer yourself. Rules for it:
- Open (open_evidence) every source you cite to get its quote IDs; evidence[i] is cited as [i+1] in the answer.
- Every factual paragraph, list item or table row carries a citation; never cite a number not in evidence.
- No URLs. Answer in answer_language with Markdown. For a build, print the eight attributes in a Markdown table
  (Attribute | Points | short reason) and put its citations on the line directly below the table.
- If the evidence cannot answer, set insufficient=true with evidence=[] and name the missing detail.
"""


@dataclass
class TrueAgentRun:
    result: Generated | None
    prepared: Prepared
    variant: Variant
    stop: str
    model_calls: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    elapsed_ms: float = 0.0
    error: str | None = None


def _preview(hit) -> dict:
    p = hit.payload
    return {
        "id": hit.id,
        "title": p.get("title"),
        "section": p.get("section"),
        "origin": "web" if isinstance(hit, WebHit) else "corpus",
        **{k: p[k] for k in ("source_type", "game_scope", "patch_version") if p.get(k) is not None},
        "text": p["text"][:480],
        "truncated": len(p["text"]) > 480,
    }


def _stated(value: str, message: str) -> bool:
    return contains_text(message, value) or contains_name(message, value)


async def run_true_agent(
    pipe,
    req,
    *,
    variant: Variant = "generator",
    model=None,
    max_model_calls: int = 10,
    max_tool_calls: int = 10,
) -> TrueAgentRun:
    started = time.perf_counter()
    state = {
        "req": req,
        "history": [],
        "trace": {},
        "started": started,
        "original_question": req.message,
        "resolved_question": req.message,
    }
    pipe._scope(state)
    p: Prepared = state["prepared"]
    p.max_calls = None
    trace = p.trace
    run = TrueAgentRun(None, p, variant, "budget")
    web = state["search_mode"] != "off" and pipe.web_search is not None
    hits: dict = {}
    profile: dict = {}
    calculator_attempts = answer_attempts = 0
    deadline = started + pipe.settings.prepare_budget_seconds
    system = prompt("true_agent") + (FINAL_ANSWER_POLICY + "\n" + prompt("answer") if variant == "final_answer" else "")
    messages = [
        SystemMessage(system),
        HumanMessage(
            json.dumps(
                {
                    "player_message": req.message,
                    "requested_language": req.options.lang,
                    "web_policy": state["search_mode"] if web else "off",
                },
                ensure_ascii=False,
            )
        ),
    ]
    bound = (model or pipe.llm.model).bind_tools(
        tool_specs(variant, web=web),
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
        retriever = pipe.retriever.model_copy(
            update={"limit": pipe.settings.rag_prefetch, "search_timeout_seconds": 5, "rerank_deadline": deadline}
        )
        async with asyncio.timeout(5 + getattr(retriever, "reranker_timeout_seconds", 0) + 0.1):
            docs = await retriever.ainvoke(query)
        return [document_to_hit(d) for d in docs[: pipe.settings.rag_prefetch]]

    async def execute(name: str, raw: dict):
        """(result for the model, terminal outcome or None)."""
        nonlocal calculator_attempts, answer_attempts
        if name not in TOOLS or (name == "search_web" and not web):
            return {"status": "error", "error": f"Unknown or unavailable tool {name}"}, None
        try:
            args = TOOLS[name][0].model_validate(raw)
        except ValidationError as exc:
            fields = [".".join(map(str, e["loc"])) + ": " + e["type"] for e in exc.errors(include_input=False)][:5]
            return {"status": "error", "error": "Invalid arguments", "fields": fields}, None
        if name == "search_corpus":
            found = admit(await local(args.query))
            return {"status": "ok", "results": [_preview(h) for h in found]}, None
        if name == "search_web":
            found, diagnostic = await pipe.web_search.search(args.query)
            trace["web_search"].update(status="ok", trigger="true_agent", **diagnostic)
            return {"status": "ok", "results": [_preview(h) for h in admit(found)]}, None
        if name == "check_name":
            found = admit(await local(args.name))
            matches, close = matching_names(args.name, found)
            return {
                "status": "ok",
                "candidates": [title for title, _ in matches][:5],
                "single_close_match": close and len(matches) == 1,
                "results": [_preview(h) for h in found[:8]],
            }, None
        if name == "open_evidence":
            from app.rag.pipeline import context_item

            unknown = [i for i in args.ids if i not in hits]
            if unknown:
                return {"status": "error", "error": "Unknown evidence IDs", "ids": unknown}, None
            return {
                "status": "ok",
                "evidence": [{**context_item(hits[i], n), "id": i} for n, i in enumerate(args.ids, 1)],
            }, None
        if name == "calculator":
            calculator_attempts += 1
            if calculator_attempts > 3:
                return {"status": "error", "error": "Calculator budget used; finish with a reference suggestion"}, None
            given = {"level": args.level, "starting_class": args.starting_class, "weapon": args.weapon}
            unstated = [k for k, v in given.items() if v and not _stated(v, req.message)]
            if unstated:
                return {
                    "status": "error",
                    "error": "These are not the player's words; leave them empty unless the player said them",
                    "fields": unstated,
                }, None
            profile.clear()
            profile.update({k: v for k, v in given.items() if v})
            if build_rules(profile) is None:
                return {"status": "error", "error": "A level from the player is required"}, None
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
        if name in {"ask_user", "reply"}:
            text = args.question if name == "ask_user" else args.text
            return {"status": "ok"}, ("ask_user" if name == "ask_user" else "reply", Generated(text))
        if name == "finish":
            return {"status": "ok"}, ("finish", args)
        # final_answer
        answer_attempts += 1
        unknown = [c.id for c in args.evidence if c.id not in hits]
        if unknown:
            return {"status": "error", "error": "Unknown evidence IDs", "ids": unknown}, None
        cited = [hits[c.id] for c in args.evidence]
        extra = [hits[i] for i in (p.checked_build or {}).get("sources", []) if i in hits and hits[i] not in cited]
        lang = args.answer_language if req.options.lang == "auto" else p.lang
        check_p = Prepared(
            p.mode,
            lang,
            [],
            hits=cited + extra,
            checked_build=p.checked_build,
            values={"player_profile": dict(profile)},
            trace=trace,
            gameplay_advice=args.gameplay_advice or args.advisory,
        )
        data = {
            "answer": args.answer,
            "evidence": [{"index": n, "quote_ids": c.quote_ids} for n, c in enumerate(args.evidence, 1)],
            "insufficient": args.insufficient,
            **{k: getattr(args, k) for k in ("limitation", "recommendation") if getattr(args, k)},
            **({"advisory": True} if args.advisory else {}),
        }
        try:
            result = validate_answer(check_p, data)
        except RAGValidationError as exc:
            trace.pop("validation_failure", None)
            if answer_attempts >= 3:
                return {"status": "error"}, ("failed", exc.reason)
            return {"status": "error", "error": exc.reason, "fix": "Fix the citations/quotes and call again"}, None
        issues = trace.pop("guard_request", None)
        if issues and answer_attempts < 2:
            return {
                "status": "needs_fix",
                "issues": issues["issues"],
                "fix": "Fix these and call final_answer again",
            }, None
        p.lang, p.hits = lang, check_p.hits
        return {"status": "ok"}, ("final_answer", result)

    outcome = None
    while outcome is None:
        if run.model_calls >= max_model_calls or len(run.tool_calls) >= max_tool_calls:
            break
        if time.perf_counter() > deadline and run.model_calls:
            messages.append(HumanMessage("Budget exhausted: finish now with what you have."))
        run.model_calls += 1
        trace.setdefault("model_calls", []).append({"phase": "true_agent"})
        ai = await bound.ainvoke(messages)
        usage = ai.usage_metadata or {}
        run.usage["input_tokens"] += usage.get("input_tokens") or 0
        run.usage["output_tokens"] += usage.get("output_tokens") or 0
        messages.append(ai)
        # Live spike 22/11: a call whose arguments are not valid JSON (often a long build_data) lands in
        # invalid_tool_calls; the provider rejects the next request (400) unless every call ID gets a reply.
        for bad in ai.invalid_tool_calls:
            run.tool_calls.append({"name": bad.get("name") or "?", "status": "invalid_arguments", "ms": 0})
            messages.append(
                ToolMessage(
                    json.dumps(
                        {"status": "error", "error": "Arguments were not valid JSON; send the call again, shorter"}
                    ),
                    tool_call_id=bad["id"],
                )
            )
        if ai.invalid_tool_calls and not ai.tool_calls:
            continue
        if not ai.tool_calls:
            messages.append(HumanMessage("Call a tool; end with a terminal tool, not plain text."))
            continue
        for call in ai.tool_calls:
            t0 = time.perf_counter()
            try:
                result, terminal = await execute(call["name"], call.get("args") or {})
            except Exception as exc:  # noqa: BLE001 - tool/provider errors become observations for the Agent
                logger.warning(
                    "True agent tool error", extra={"data": {"tool": call["name"], "error": type(exc).__name__}}
                )
                result, terminal = {"status": "error", "error": type(exc).__name__}, None
            run.tool_calls.append(
                {"name": call["name"], "status": result.get("status"), "ms": round((time.perf_counter() - t0) * 1000)}
            )
            messages.append(ToolMessage(json.dumps(result, ensure_ascii=False), tool_call_id=call["id"]))
            if terminal is not None:
                outcome = terminal
                break

    trace["tool_actions"] = run.tool_calls
    if outcome is None and variant == "generator":
        outcome = ("finish_budget", None)
    if outcome is None:
        run.error = "no_final_answer"
    elif outcome[0] == "failed":
        run.stop, run.error = "final_answer_rejected", outcome[1]
    elif outcome[0] in {"ask_user", "reply", "final_answer"}:
        run.stop, run.result = outcome
    else:
        args: FinishArgs | None = outcome[1]
        run.stop = outcome[0]
        if args is not None:
            state["resolved_question"] = args.request
            if req.options.lang == "auto":
                p.lang = args.answer_language
            p.gameplay_advice = args.gameplay_advice
        ids = [i for i in (args.evidence_ids if args else []) if i in hits]
        for i in (p.checked_build or {}).get("sources", []):
            if i in hits and i not in ids:
                ids.append(i)
        trace["evidence_selection"] = (
            {"method": "model", "ids": ids} if ids else {"method": "all_evidence", "ids": list(hits)}
        )
        state["documents"] = [hit_to_document(h) for h in hits.values() if not isinstance(h, WebHit)]
        state["web_hits"] = [h for h in hits.values() if isinstance(h, WebHit)]
        state["next_player"] = {"constraints": [{"key": k, "value": v} for k, v in profile.items()]}
        pipe._context(state)
        prepared = pipe._prompt(state)
        if prepared.static_answer is not None:
            run.result = Generated(prepared.static_answer)
        else:
            try:  # The generator records its own "generation"/"answer_guard" model calls in the trace.
                run.result = await pipe.generator.generate(prepared)
            except Exception as exc:  # noqa: BLE001 - recorded for the spike report
                run.error = getattr(exc, "reason", type(exc).__name__)
        run.prepared = prepared
    run.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return run
