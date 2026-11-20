"""Bounded model-selected read tools. No shell, crawler, persistence or implicit knowledge fallback."""

import asyncio
import json
import logging
import time
import unicodedata
from datetime import UTC, datetime
from itertools import zip_longest
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm import LLMError
from app.adapters.tavily import WebHit, WebSearchError
from app.api.schemas.chat import Clarification, ClarificationField
from app.rag.agent import GoalText, contains_superseded, spend
from app.rag.entity_spelling import correct_name, matching_names
from app.rag.output import OutputFormatError, decode_output
from app.rag.prompts import prompt, rewrite_prompt
from app.rag.retriever import document_to_hit, hit_to_document
from app.rag.task_plan import MAX_GOAL_SOURCES, MAX_GOALS, restore_evidence, save_evidence, update_plan
from app.rag.web_search import assess
from core.errors import UnavailableError, UpstreamError
from core.types import Hit


class ToolStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal[
        "check_name",
        "local_search",
        "web_search",
        "source_snapshot",
        "inspect_evidence",
        "calculator",
        "finish",
        "clarify",
        "stop",
    ]
    query: str = Field(default="", max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=5)
    snapshot_ids: list[str] = Field(default_factory=list, max_length=5)
    allocation: dict[str, int] = Field(default_factory=dict, max_length=8)
    # The attribute that takes the remainder of the level's points; the calculator does the arithmetic.
    fill: Literal["", "vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane"] = ""
    build_data: dict = Field(default_factory=dict)
    question: str = Field(default="", max_length=1000)
    missing: list[ClarificationField] = Field(default_factory=list, max_length=2)
    add_goals: list[GoalText] = Field(default_factory=list, max_length=MAX_GOALS)
    completed_goals: dict[str, Annotated[list[str], Field(max_length=MAX_GOAL_SOURCES)]] = Field(
        default_factory=dict, max_length=MAX_GOALS
    )
    reopen_goals: list[str] = Field(default_factory=list, max_length=MAX_GOALS)
    reason: Literal[
        "initial", "missing_evidence", "different_query", "player_detail", "ambiguous_name", "sufficient", "unavailable"
    ]


def invalid_output_issue(exc) -> dict:
    """What was wrong with a tool step, without echoing any model content."""
    if isinstance(exc, ValidationError):
        return {
            "kind": "schema",
            "fields": [
                {"field": ".".join(map(str, e["loc"])), "type": e["type"]}
                for e in exc.errors(include_input=False, include_url=False)
            ][:5],
        }
    if isinstance(exc, OutputFormatError):
        return {"kind": "json", "json_error": exc.diagnostics.get("json_error") or exc.diagnostics.get("reason")}
    return {"kind": "value", "type": type(exc).__name__}


def key(action, arguments):
    return action, unicodedata.normalize("NFKC", " ".join(arguments.split())).casefold()


async def run_tools(pipe, state):
    from app.rag.gameplay_knowledge import load_pack
    from app.rag.pipeline import context_item, select_context

    p, req = state["prepared"], state["req"]
    turn_started = state.get("started", time.perf_counter())
    inactive = (p.player_state or {}).get("inactive_conditions", [])
    comparison = req.message if p.agent_decision.get("intent") in {"comparison", "gameplay_comparison"} else ""
    if p.trace["web_search"]["requested"] == "always" and not pipe.settings.web_search_available:
        raise UnavailableError("Tìm trên web hiện chưa khả dụng.")
    catalog = (
        {
            row["id"]: row
            for group in load_pack()["groups"]
            for row in group["hits"]
            if pipe.policy.exclusion_reason(row["payload"]) is None
        }
        if pipe.settings.gameplay_knowledge_enabled
        else {}
    )
    from app.rag.build_data import BuildCache, build_rules, check, level_rule

    if not hasattr(pipe, "build_cache"):
        pipe.build_cache = BuildCache()
    profile = {c["key"]: c["value"] for c in (p.player_state or {}).get("constraints", [])}
    cached = pipe.build_cache.get(profile)
    if cached:
        for h in cached[1]:
            if isinstance(h, WebHit) or pipe.policy.exclusion_reason(h.payload) is None:
                catalog[h.id] = {"id": h.id, "payload": h.payload, "web": isinstance(h, WebHit)}
    task_plan = (p.player_state or {}).get("plan", [])
    hits = restore_evidence(pipe, state) if task_plan else {}
    seen, observations = set(), []
    raw_name = state.get("name_to_check", "")
    name_status = "pending" if raw_name else ""
    name_options = []
    source_batches = []
    local_calls, web_calls = 0, 0
    actions = p.trace["tool_actions"] = []
    stop_reason = "step_budget"
    rounds = (p.player_state or {}).get("clarification_rounds", 0)
    clarification_limit = pipe.settings.chat_clarification_max_rounds
    step_limit = pipe.settings.chat_tool_steps
    local_limit = pipe.settings.chat_tool_queries
    model_limit = pipe.settings.chat_agent_max_calls
    verify_coverage = state.get("verify_coverage", False)
    # Coverage mode (web auto) lets the model search until the evidence is sufficient, but still within
    # a bounded number of steps and model calls, and within the preparation time budget.
    coverage_steps = pipe.settings.chat_coverage_steps if verify_coverage else None
    if verify_coverage:
        step_limit = local_limit = None
        model_limit = pipe.settings.chat_coverage_max_calls
    # Preparation (Agent + tools) must hand over to generation by this time; generation keeps the rest.
    prepare_deadline = state.get("started", turn_started) + pipe.settings.prepare_budget_seconds

    def prepare_left() -> float:
        return prepare_deadline - time.perf_counter()

    calculator_failures = 0
    calculator_offered = False
    stalled = set()
    followup = None
    web_queries = []
    no_new_web_evidence = 0
    covered_ids = []
    inspected_ids = []
    checked_contexts = set()
    seen_excerpts = {(hit.payload.get("url"), " ".join(hit.payload["text"].split())) for hit in hits.values()}
    while step_limit is None or len(actions) < step_limit:
        if verify_coverage and prepare_left() <= 0:
            stop_reason = "answer_time_reserved"
            break
        if coverage_steps is not None and len(actions) >= coverage_steps:
            stop_reason = "step_budget"
            break
        # Reserve one generation call; repairs still obey the shared turn budget.
        if model_limit is not None and len(p.trace.get("model_calls", [])) >= model_limit - 1:
            stop_reason = "model_budget"
            break
        available = ["finish", "stop"]
        if clarification_limit is None or rounds < clarification_limit:
            available.append("clarify")
        unresolved_name = name_status in {"pending", "ambiguous", "not_found"}
        if (local_limit is None or local_calls < local_limit) and pipe.retriever is not None:
            if name_status == "pending":
                available.append("check_name")
            if not unresolved_name or name_status == "not_found":
                available.append("local_search")
        if (
            state["search_mode"] != "off"
            and (step_limit is None or not web_calls)
            and pipe.web_search is not None
            and (not unresolved_name or name_status == "not_found")
            and (not verify_coverage or no_new_web_evidence < 2)
        ):
            available.append("web_search")
        if catalog and not unresolved_name:
            available.append("source_snapshot")
        profile = {c["key"]: c["value"] for c in (p.player_state or {}).get("constraints", [])}
        if name_status == "verified":
            profile = {k: correct_name(v, raw_name, name_options[0]) for k, v in profile.items()}
        # Level is the only player input the arithmetic needs: level accounting and class floors are built-in
        # sourced rules, a missing class becomes Wretch, a missing weapon a suggestion or "not checked".
        targets = build_rules(profile) if not unresolved_name else None
        if (
            targets is not None
            and p.checked_build is None
            # Two rejected calculations end the attempt; the answer explains priorities without numbers.
            and calculator_failures < pipe.settings.chat_calculator_max_failures
        ):
            available.append("calculator")
            calculator_offered = True
        carried_ids = dict.fromkeys(key for item in task_plan for key in item["evidence_ids"] if key in hits)
        interleaved = (key for batch in zip_longest(*reversed(source_batches)) for key in batch if key is not None)
        candidate_ids = list(dict.fromkeys([*carried_ids, *covered_ids, *interleaved, *hits]))[:30]
        shown_ids = set(candidate_ids) | set(inspected_ids)
        if candidate_ids and not unresolved_name:
            available.append("inspect_evidence")
        inspected = set(inspected_ids)
        payload = {
            "player_profile": profile,
            "request": state["resolved_question"],
            "intent": p.agent_decision.get("intent"),
            "initial_query": state["query"],
            "search_hypotheses": p.agent_decision.get("search_hypotheses", []),
            "answer_language": p.lang,
            "web_policy": state["search_mode"],
            "available_actions": available,
            "remaining_steps": (
                None if (step_limit or coverage_steps) is None else (step_limit or coverage_steps) - len(actions)
            ),
            "observations": observations[-3:],
            "task_plan": task_plan,
            **(
                {"name_lookup": {"typed": raw_name, "status": name_status, "candidates": name_options}}
                if raw_name
                else {}
            ),
            "checked_build": p.checked_build,
            # Targets the allocation must meet (total, class floors, cap), so one calculator call can pass.
            **({"build_rules": {k: v for k, v in targets.items() if k != "rule_sources"}} if targets else {}),
            "cached_build_data": cached[0] if cached else None,
            "evidence_details": [{**context_item(hits[i], pos), "id": i} for pos, i in enumerate(inspected_ids, 1)],
            "candidates": [
                {
                    "id": i,
                    "title": hits[i].payload["title"],
                    "origin": "web" if isinstance(hits[i], WebHit) else "corpus",
                    **(
                        {"source_domain": urlsplit(hits[i].payload["url"]).hostname}
                        if isinstance(hits[i], WebHit)
                        else {}
                    ),
                    **{
                        k: hits[i].payload[k]
                        for k in ("section", "source_type", "game_scope", "release_scope", "patch_version", "rule_kind")
                        if hits[i].payload.get(k) is not None
                    },
                    **(
                        {"text": hits[i].payload["text"][:480], "preview_truncated": len(hits[i].payload["text"]) > 480}
                        if i not in inspected
                        else {"opened": True}
                    ),
                }
                for i in candidate_ids
            ],
            "snapshots": [{"id": k, "title": v["payload"]["title"]} for k, v in catalog.items()][:40],
        }
        decision_started = time.perf_counter()
        # Visible in deadline diagnostics if the turn times out inside this step.
        p.trace["tool_step_running"] = {"phase": "tool_decision", "step": len(actions) + 1}
        try:
            if followup:
                step = ToolStep(action="web_search", query=followup, reason="missing_evidence")
                followup = None
            else:
                spend(p.trace, "tool_decision", p.max_calls)
                decision_timeout = pipe.settings.chat_agent_timeout_seconds
                if verify_coverage:
                    decision_timeout = min(decision_timeout, prepare_left())
                async with asyncio.timeout(decision_timeout):
                    result = await pipe.llm.invoke_chain(
                        rewrite_prompt()
                        | pipe.llm.bind_model(
                            json_output=True,
                            thinking=False,
                            temperature=0,
                            max_tokens=2048 if "calculator" in available else 768,
                        ),
                        {"policy": prompt("tools"), "history": [], "question": json.dumps(payload, ensure_ascii=False)},
                    )
                data, _ = decode_output(result.content)
                step = ToolStep.model_validate(data)
        except LLMError:
            raise UpstreamError("Bước chọn công cụ của mô hình chưa hợp lệ.") from None
        except ValueError as exc:
            # Category and field names only, never the model output: tells the planner what to fix and lets the
            # trace distinguish broken JSON from a schema mistake (e.g. a malformed build_data).
            issue = invalid_output_issue(exc)
            actions.append({"status": "denied", "reason": "invalid_tool_output", "issue": issue})
            logging.getLogger(__name__).warning("Invalid tool output", extra={"data": issue})
            if "invalid_tool_output" in stalled:
                if hits:
                    # A second malformed step in a row: answer from the evidence already gathered, not a 502.
                    stop_reason = "invalid_tool_output"
                    break
                if step_limit is None:
                    raise UpstreamError("Bước chọn công cụ của mô hình chưa hợp lệ.") from None
            stalled.add("invalid_tool_output")
            observations.append(
                {
                    "status": "invalid_tool_output",
                    "error": issue,
                    "fix": "Return one JSON object with only the documented fields and value types.",
                }
            )
            continue
        except TimeoutError:
            if verify_coverage and hits:
                stop_reason = "tool_decision_timeout"
                break
            raise UnavailableError("Bước chọn công cụ vượt thời gian xử lý.") from None
        action = step.action
        row = {
            "action": action,
            "reason": step.reason,
            "status": "running",
            "decision_ms": round((time.perf_counter() - decision_started) * 1000, 2),
        }
        p.trace["tool_step_running"] = {"phase": action, "step": len(actions) + 1}
        if state.get("diagnostic_queries"):
            row["query"] = step.query
        actions.append(row)
        arguments = (
            step.query
            if action in {"local_search", "web_search"}
            else json.dumps(
                {
                    "ids": sorted(step.evidence_ids if action == "inspect_evidence" else step.snapshot_ids),
                    "allocation": step.allocation,
                    "fill": step.fill,
                    "build_data": step.build_data,
                },
                sort_keys=True,
            )
        )
        identity = key(action, arguments)
        if action not in available:
            # E.g. calculator withdrawn after two rejections. Asking again with other arguments does not
            # bring it back (live 20/11: three wasted steps), so a second request ends the loop.
            row["status"] = "denied"
            unavailable = ("unavailable", action)
            if unavailable in stalled:
                stop_reason = "repeated_unavailable_action"
                break
            stalled.add(unavailable)
            observations.append({"action": action, "status": "not_available", "available_actions": available})
            continue
        if identity in seen and action not in {"finish", "stop", "clarify"}:
            row["status"] = "denied"
            if step_limit is None and identity in stalled:
                stop_reason = "repeated_action"
                break
            stalled.add(identity)
            observations.append({"action": action, "status": "duplicate"})
            continue
        planned_text = "\n".join([step.query, *step.add_goals])
        if contains_superseded(planned_text, inactive, comparison, profile.values()):
            row["status"] = "denied"
            if identity in stalled:
                stop_reason = "repeated_action"
                break
            stalled.add(identity)
            observations.append({"action": action, "status": "superseded_constraint"})
            continue
        if unresolved_name and action == "finish":
            row["status"] = "denied"
            observations.append({"status": "name_not_verified"})
            continue
        if action in {"finish", "stop"} and state["search_mode"] == "always" and not web_calls:
            row["status"] = "denied_web_required"
            observations.append({"status": "always_requires_web_before_finish"})
            continue
        if action == "clarify" and (
            not step.question.strip()
            or not step.missing
            or (
                step.reason != "player_detail"
                and not (step.reason == "ambiguous_name" and name_status in {"ambiguous", "not_found"})
            )
        ):
            row["status"] = "denied"
            observations.append({"action": action, "status": "requires_missing_player_detail_or_ambiguous_name"})
            continue
        if not update_plan(task_plan, step, shown_ids):
            row["status"] = "denied"
            observations.append({"action": action, "status": "invalid_plan_update"})
            continue
        seen.add(identity)
        stalled.clear()
        if action in {"finish", "stop"}:
            invalid = len(set(step.evidence_ids)) != len(step.evidence_ids) or any(
                i not in shown_ids for i in step.evidence_ids
            )
            p.trace["evidence_selection"] = {
                "method": "model" if not invalid and (step.evidence_ids or action == "stop") else "rank_fallback",
                "ids": [] if invalid else step.evidence_ids,
            }
            if invalid:
                p.trace["evidence_selection"]["reason"] = "invalid_or_duplicate_id"
            elif action == "finish" and task_plan:
                plan_ids = [key for item in task_plan for key in item["evidence_ids"][:1]]
                if plan_ids:
                    p.trace["evidence_selection"] = {
                        "method": "model",
                        "ids": list(dict.fromkeys([*plan_ids, *step.evidence_ids]))[:5],
                    }
            if verify_coverage and not unresolved_name:
                # Use the same admission, order and context budget as the generator.
                ids = p.trace["evidence_selection"]["ids"] or candidate_ids
                # Leave room for new evidence when a previous partial verdict filled all five slots.
                retained = covered_ids[: max(0, pipe.settings.rag_top_k - 1)]
                newest = next((i for batch in reversed(source_batches) for i in batch if i not in covered_ids), None)
                if covered_ids and newest is not None and all(i in covered_ids for i in ids):
                    ids = [newest, *ids]
                ids = list(dict.fromkeys([*((p.checked_build or {}).get("sources", [])), *retained, *ids]))
                evaluated = select_context(
                    [hits[i] for i in ids],
                    pipe.settings.rag_top_k,
                    pipe.settings.rag_context_chars,
                    policy=pipe.policy,
                )
                context = [context_item(hit, i) for i, hit in enumerate(evaluated, 1)]
                if context:
                    spend(p.trace, "assessment", p.max_calls)
                assessment_timeout = min(
                    pipe.settings.chat_agent_timeout_seconds,
                    max(0, prepare_left()),
                )
                status, assessment = await assess(
                    pipe.llm,
                    state["resolved_question"],
                    [],
                    context,
                    assessment_timeout,
                    task={
                        "original_request": (
                            state["resolved_question"]
                            if inactive
                            else (p.player_state or {}).get("request_text", req.message)
                        ),
                        "goals": [item["goal"] for item in task_plan],
                        "player_profile": profile,
                        "checked_build": p.checked_build,
                        "searched_web_queries": web_queries[-8:],
                    },
                )
                supported = [evaluated[int(i) - 1].id for i in assessment.get("evidence", {})]
                if supported:
                    covered_ids = list(dict.fromkeys([*supported, *covered_ids]))[: pipe.settings.rag_top_k]
                context_ids = [hit.id for hit in evaluated]
                p.trace.setdefault("coverage_checks", []).append({**assessment, "context_ids": context_ids})
                p.trace["evidence_selection"] = {"method": "model", "ids": context_ids}
                if status == "sufficient" and not web_calls:
                    p.trace["web_search"]["status"] = "local_sufficient"
                if status not in {"sufficient", "ambiguous"}:
                    raw_query = assessment.get("followup_query", "").strip()
                    if not raw_query and not web_calls:
                        raw_query = state["query"]
                    if raw_query and no_new_web_evidence < 2:
                        # The assessor (LLM) writes the follow-up search; no server-side query rewriting.
                        proposed = raw_query
                        if key("web_search", proposed) not in seen and not contains_superseded(
                            proposed, inactive, comparison, profile.values()
                        ):
                            followup = proposed
                    if followup:
                        row["status"] = "needs_evidence"
                        observations.append(
                            {"action": action, "status": "needs_evidence", "missing": assessment.get("missing", [])}
                        )
                        continue
                    signature = (frozenset(hit.id for hit in evaluated), tuple(web_queries))
                    if (hits or p.trace["web_search"]["status"] == "ok") and signature not in checked_contexts:
                        checked_contexts.add(signature)
                        row["status"] = "needs_evidence"
                        observations.append(
                            {"action": action, "status": "needs_evidence", "missing": assessment.get("missing", [])}
                        )
                        continue
                if status != "sufficient":
                    row["status"] = "partial" if evaluated else "insufficient"
                    stop_reason = "coverage_unresolved"
                    break
            row["status"] = "ok"
            stop_reason = action
            break
        if action == "clarify":
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
            if action in {"check_name", "local_search"}:
                local_calls += 1
                retriever = pipe.retriever.model_copy(
                    update={
                        "limit": pipe.settings.rag_prefetch,
                        "search_timeout_seconds": min(5, pipe.settings.rag_retrieval_timeout_seconds),
                        "rerank_deadline": prepare_deadline,
                    }
                )
                retrieval_timeout = min(5, pipe.settings.rag_retrieval_timeout_seconds)
                rerank_timeout = getattr(retriever, "reranker_timeout_seconds", 0)
                retrieval_timeout += rerank_timeout + (0.1 if rerank_timeout else 0)
                async with asyncio.timeout(retrieval_timeout):
                    docs = await retriever.ainvoke(raw_name if action == "check_name" else step.query)
                    found = [document_to_hit(d) for d in docs[: pipe.settings.rag_prefetch]]
                # Retrieval ids/scores per local search, for the debugging trace (not a relevance claim).
                p.trace.setdefault("retrieved", []).extend(
                    {
                        "id": h.id,
                        "score": h.score,
                        "chunk_id": h.payload.get("artifact_chunk_id", h.id),
                        "title": h.payload.get("title"),
                        "url": h.payload.get("url"),
                    }
                    for h in found
                )
            elif action == "web_search":
                web_calls += 1
                web_queries.append(step.query)
                if verify_coverage:
                    async with asyncio.timeout(max(0, prepare_left())):
                        found, diagnostic = await pipe.web_search.search(step.query)
                else:
                    found, diagnostic = await pipe.web_search.search(step.query)
                p.trace["web_search"].update(status="ok", trigger="agent_tool", **diagnostic)
            elif action == "source_snapshot":
                if not step.snapshot_ids or any(k not in catalog for k in step.snapshot_ids):
                    raise ValueError("unknown_snapshot")
                found = [
                    (WebHit if catalog[k].get("web") else Hit)(k, 0.0, dict(catalog[k]["payload"]))
                    for k in step.snapshot_ids
                ]
            elif action == "inspect_evidence":
                if (
                    not step.evidence_ids
                    or len(set(step.evidence_ids)) != len(step.evidence_ids)
                    or not set(step.evidence_ids) <= shown_ids
                ):
                    raise ValueError("unknown_or_duplicate_evidence_id")
                inspected_ids = step.evidence_ids
                row["opened"] = len(inspected_ids)
            elif action == "calculator":
                # Arithmetic against the pack's sourced rules; weapon requirements only when quoted from a source.
                p.checked_build = check(step.build_data, step.allocation, profile, list(hits.values()), step.fill)
                requirement_hits = [hits[i] for i in p.checked_build["requirement_sources"]]
                pipe.build_cache.put(p.checked_build["data"], requirement_hits)
                # The level accounting snapshot becomes evidence so the answer can cite it.
                rule_hit, _ = level_rule()
                hits[rule_hit.id] = rule_hit
                row["calculation"] = {k: v for k, v in p.checked_build.items() if k not in {"data", "provenance"}}
            if action == "check_name" or (name_status == "not_found" and action in {"local_search", "web_search"}):
                candidates = [
                    h for h in found if isinstance(h, WebHit) or pipe.policy.exclusion_reason(h.payload) is None
                ]
                matches, can_verify = matching_names(
                    raw_name,
                    candidates,
                    contextual_query=step.query if action in {"local_search", "web_search"} else "",
                )
                name_options = [title for title, _ in matches][:5]
                name_status = (
                    "verified" if can_verify and len(matches) == 1 else "ambiguous" if matches else "not_found"
                )
                row["name_status"] = name_status
                found = matches[0][1] if name_status == "verified" else []
                if name_status == "verified":
                    p.trace["verified_name"] = {"typed": raw_name, "canonical": name_options[0]}
                    for field in ("resolved_question", "query"):
                        state[field] = correct_name(state[field], raw_name, name_options[0])
            admitted, novel = [], False
            for h in found:
                eligible = (
                    state["search_mode"] != "off"
                    if isinstance(h, WebHit)
                    else pipe.policy.exclusion_reason(h.payload) is None
                )
                if eligible:
                    hits[h.id] = h
                    admitted.append(h.id)
                    excerpt = (h.payload.get("url"), " ".join(h.payload["text"].split()))
                    if excerpt not in seen_excerpts:
                        seen_excerpts.add(excerpt)
                        novel = True
            if action == "web_search":
                no_new_web_evidence = 0 if novel else no_new_web_evidence + 1
            if admitted:
                source_batches.append(admitted)
                if action == "source_snapshot":
                    inspected_ids = admitted
                if verify_coverage and novel:
                    p.trace.pop("evidence_selection", None)
            if action == "calculator" and p.checked_build:
                inspected_ids = []
            row.update(status="ok", returned=len(found))
        except (UnavailableError, TimeoutError, WebSearchError, ValueError) as exc:
            row.update(status="error", error_type=type(exc).__name__)
            if action == "web_search":
                no_new_web_evidence += 1
                if p.trace["web_search"]["status"] != "ok":
                    p.trace["web_search"].update(status="error", reason=getattr(exc, "reason", type(exc).__name__))
            if action == "calculator":
                calculator_failures += 1
                row["validation"] = (
                    [
                        {"field": list(e["loc"]), "type": e["type"]}
                        for e in exc.errors(include_input=False, include_url=False)
                    ]
                    if isinstance(exc, ValidationError)
                    else str(exc)[:200]
                )
        row["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        observations.append({k: v for k, v in row.items() if k != "query"})
    p.trace["tool_stop"] = stop_reason
    p.trace.pop("tool_step_running", None)
    if calculator_offered or calculator_failures or p.checked_build is not None:
        # What actually happened to the exact allocation, so the answer states the true reason.
        # A missing class or weapon is never the cause: the class defaults to Wretch, equipment can be suggested.
        p.trace["build_check"] = {
            "status": "checked" if p.checked_build is not None else "failed" if calculator_failures else "not_run",
            "failed_attempts": calculator_failures,
            "class_given": bool(profile.get("starting_class")),
            "weapon_given": bool(profile.get("weapon")),
        }
    if task_plan:
        if p.clarification is not None:
            p.player_state["plan"] = task_plan
            save_evidence(p, task_plan, hits, pipe.settings.rag_collection)
        else:
            p.player_state.pop("plan", None)
        p.trace["task_plan"] = task_plan
    if p.static_answer is None and p.trace.get("evidence_selection", {}).get("method") != "model":
        completed_ids = [key for item in task_plan for key in item["evidence_ids"][:1] if key in hits]
        batch_leads = [batch[0] for batch in reversed(source_batches)] if len(source_batches) > 1 else []
        if completed_ids or batch_leads:
            ids = list(dict.fromkeys([*completed_ids, *covered_ids, *batch_leads, *hits]))[:5]
            p.trace["evidence_selection"] = {"method": "rank_fallback", "ids": ids}
    if raw_name and name_status != "verified" and p.static_answer is None:
        p.gameplay_advice = False
        hits = {}
        p.trace["evidence_selection"] = {"method": "model", "ids": []}
    if state["search_mode"] == "always" and not web_calls and p.static_answer is None:
        raise UnavailableError("Agent chưa hoàn tất tìm web bắt buộc trong ngân sách.")
    allow_advice = verify_coverage and p.gameplay_advice
    if web_calls and p.trace["web_search"]["status"] != "ok" and not hits:
        if not allow_advice:
            raise UnavailableError("Tìm trên web đang gặp sự cố.")
        p.trace["tool_stop"] = "web_error_advice_available"
    local_attempts = [
        row
        for row in actions
        if row.get("action") in {"local_search", "check_name"} and row["status"] in {"ok", "error"}
    ]
    if (
        p.static_answer is None
        and not hits
        and local_attempts
        and all(row["status"] == "error" for row in local_attempts)
        and p.trace["web_search"]["status"] != "ok"
        and not allow_advice
    ):
        raise UnavailableError("Không thể truy vấn kho tri thức RAG.")
    state["documents"] = [hit_to_document(h) for h in hits.values() if not isinstance(h, WebHit)]
    state["web_hits"] = [h for h in hits.values() if isinstance(h, WebHit)]
    return state
