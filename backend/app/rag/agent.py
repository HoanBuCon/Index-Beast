"""Model-owned intent/clarification/resolve decisions, server-owned contracts and budgets."""

import asyncio
import json
import logging
import re
import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError

from app.adapters.llm import LLMError
from app.api.schemas.chat import ClarificationField
from app.rag.output import OutputFormatError, decode_output
from app.rag.prompts import prompt, rewrite_prompt
from app.rag.rewrite import _contains, contains_name, name_key, preserves_numbers
from core.errors import UnavailableError, UpstreamError

GoalText = Annotated[str, Field(min_length=1, max_length=240)]
SearchName = Annotated[str, Field(min_length=1, max_length=120)]
logger = logging.getLogger(__name__)
_NEGATION = r"không (?:dùng|sử dụng|có)|tránh dùng|\bwithout\b|do not use|don't use"


class DecisionError(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class QueryNameMismatch(DecisionError):
    """The source entity is valid, but its name disappeared from the proposed query."""


def spend(trace: dict, phase: str, maximum: int | None):
    calls = trace.setdefault("model_calls", [])
    if maximum is not None and len(calls) >= maximum:
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
    superseded_constraints: list[Constraint] = Field(default_factory=list, max_length=10)
    missing: list[ClarificationField] = Field(max_length=2)
    reply: str = Field(max_length=1000)
    subgoals: list[GoalText] = Field(default_factory=list, max_length=4)
    name_to_check: str = Field(default="", max_length=100)
    search_hypotheses: list[SearchName] = Field(default_factory=list, max_length=3)
    reason: Literal["ready", "missing_player_details", "ambiguous_subject", "conversation_control", "unrelated"]

    @model_validator(mode="after")
    def coherent(self):
        if self.search_hypotheses and self.action != "retrieve":
            raise ValueError("Search hypotheses require retrieval")
        if self.subgoals and (
            len(self.subgoals) < 2 or len({s.strip().casefold() for s in self.subgoals}) != len(self.subgoals)
        ):
            raise ValueError("A plan requires distinct subgoals")
        if self.subgoals and (self.action not in {"retrieve", "clarify"} or any(not s.strip() for s in self.subgoals)):
            raise ValueError("Plan requires a game request")
        if self.name_to_check and (
            self.action != "retrieve" or not any(name_key(n) == name_key(self.name_to_check) for n in self.entities)
        ):
            raise PydanticCustomError(
                "invalid_name_lookup",
                "For a vague description with competing referents, choose clarify, ask which item or defining detail, "
                "set missing to 1-2 text fields, and leave name_to_check empty. For a single likely misspelled proper "
                "name, use the exact same user surface in entities and name_to_check. Do not infer a variant or tier.",
            )
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
            raise PydanticCustomError(
                "duplicate_constraint",
                "Duplicate constraint key. Keep one value per key. For multiple quest milestones, use one "
                "verbatim progress value and retain all milestones in the request and query. "
                "For a comparison, keep alternatives in the request and query, omit that key from constraints, "
                "and use a comparison intent. For new tasks set superseded_constraints=[].",
            )
        if self.superseded_constraints and (self.turn_type == "new" or self.action not in {"retrieve", "clarify"}):
            raise ValueError("Superseded constraints require a continuing game request")
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
    for constraint in [*normalized.constraints, *normalized.superseded_constraints]:
        aliases = [row for row in selected if row["id"] == constraint.source_id]
        if aliases and any(row["source_id"] != constraint.source_id for row in aliases):
            if len(aliases) != 1 or constraint.source_id in canonical:
                raise DecisionError("ambiguous_source_reference", "Ambiguous memory/source reference")
            row = aliases[0]
            if not _contains(row["text"], constraint.value):
                raise DecisionError("unverified_constraint", "Constraint absent from selected memory")
            constraint.source_id = row["source_id"]
            count += 1
    return normalized, count


def condition_changes(decision: AgentDecision, working: dict) -> list[Constraint]:
    if decision.turn_type == "new" or decision.action not in {"retrieve", "clarify"}:
        return []
    current = {c.key: name_key(c.value) for c in decision.constraints if c.source_id == "current"}
    replaced = [
        Constraint.model_validate(item)
        for item in working.get("constraints", [])
        if item["key"] in current and name_key(item["value"]) != current[item["key"]]
    ]
    return list({(c.key, name_key(c.value)): c for c in [*replaced, *decision.superseded_constraints]}.values())


def inactive_conditions(decision: AgentDecision, working: dict, changes: list[Constraint]) -> list[dict]:
    if decision.turn_type == "new":
        return []
    confirmed = {(c.key, name_key(c.value)) for c in decision.constraints if c.source_id == "current"}
    inactive = {
        (item["key"], name_key(item["value"])): item
        for item in [*working.get("inactive_conditions", []), *(c.model_dump() for c in changes)]
    }
    return [item for key, item in inactive.items() if key not in confirmed]


_NUMBER = r"[+-]?\d+(?:[.,]\d+)*"
_CONDITION_UNITS = {"level": r"level|lv\.?|cấp", "patch": r"patch|version|phiên bản|bản vá"}
_NUMBERED_NAME = re.compile(r"(.+?)\s+(\[\d+\])")


def contains_entity(text: str, name: str) -> bool:
    if contains_name(text, name):
        return True
    numbered = _NUMBERED_NAME.fullmatch(name)
    if not numbered:
        return False
    base, tier = map(name_key, numbered.groups())
    # Shared name with numbered variants, e.g. "Smithing Stone [3] và [4]".
    lists = re.findall(
        rf"(?<!\w){re.escape(base)}\s+(\[\d+\](?:\s*(?:,|/|\band\b|\bor\b|\bvà\b|\bhoặc\b)\s*\[\d+\])+)",
        name_key(text),
    )
    return any(tier in re.findall(r"\[\d+\]", values) for values in lists)


def contains_superseded(text: str, inactive: list[dict], comparison: str = "") -> bool:
    for item in inactive:
        old = item["value"]
        if contains_name(comparison, old):
            continue
        if re.fullmatch(_NUMBER, old) and (unit := _CONDITION_UNITS.get(item["key"])):
            # The number after "or" shares the unit of the first value.
            alternatives = re.findall(
                rf"\b(?:{unit})\s*[:=]?\s*({_NUMBER}(?!\w|[.,]\d)(?:\s*(?:/|,|or\b|and\b|hoặc\b|và\b)\s*{_NUMBER}(?!\w|[.,]\d))*)",
                text,
                re.I,
            )
            if any(preserves_numbers(old, part) for part in alternatives):
                return True
            continue
        matches = preserves_numbers(old, text) if re.fullmatch(_NUMBER, old) else contains_name(text, old)
        if matches:
            return True
    return False


def has_progress_anchor(decision, request_text, selected, working):
    if decision.intent not in {"route", "quest"} or not request_text.strip():
        return False
    if decision.turn_type == "clarification_reply" and not working.get("pending"):
        return False
    prior = {
        (item["source_id"], item["value"]) for item in working.get("constraints", []) if item["key"] == "progress"
    } | {
        (row["source_id"], row["text"])
        for row in selected
        if row.get("kind") == "fact" and row.get("key") == "progress"
    }
    return any(
        c.key == "progress" and c.value.strip() and (c.source_id == "current" or (c.source_id, c.value) in prior)
        for c in decision.constraints
    )


def check_decision(decision: AgentDecision, question: str, candidates: list[dict], working: dict):
    available = {row["id"]: row for row in candidates}
    if any(key not in available for key in decision.selected_memory_ids):
        raise DecisionError("unknown_memory_reference", "Unprovided memory reference")
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
    comparison = question if decision.intent in {"comparison", "gameplay_comparison"} else ""
    for item in decision.superseded_constraints:
        if (
            item.source_id == "current"
            or not contains_name(sources.get(item.source_id, ""), item.value)
            or any(c.key == item.key and name_key(c.value) == name_key(item.value) for c in decision.constraints)
            or contains_name(comparison, item.value)
        ):
            raise DecisionError(
                "invalid_condition_change",
                "Only retire values the user replaced or removed. Keep comparison options."
                " Give the earlier user source for each value you retire.",
            )
    if (
        decision.turn_type == "correction"
        and decision.action == "retrieve"
        and decision.intent not in {"comparison", "gameplay_comparison"}
        and not (decision.superseded_constraints or any(c.source_id == "current" for c in decision.constraints))
    ):
        raise DecisionError("missing_condition_change", "Identify the user's replacement or removal with its source")
    changes = condition_changes(decision, working)
    inactive = inactive_conditions(decision, working, changes)
    inactive_keys = {(item["key"], name_key(item["value"])) for item in inactive}
    for item in decision.constraints:
        contains_value = contains_name if item.key in {"weapon", "starting_class", "location"} else _contains
        if item.source_id not in sources or not contains_value(sources[item.source_id], item.value):
            raise DecisionError("unverified_constraint", "Constraint not present in its user source")
        if (item.key, name_key(item.value)) in inactive_keys:
            raise DecisionError("superseded_constraint", "Use active conditions or confirm the old value again")
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
            raise DecisionError("superseded_constraint", "Superseded constraint")
    context = question + "\n" + "\n".join(row["text"] for row in selected)
    context += "\n" + request_text
    context += "\n" + "\n".join(c.value for c in decision.constraints)
    if contains_superseded("\n".join([*decision.entities, *decision.subgoals]), inactive, comparison):
        raise DecisionError("superseded_constraint", "Remove superseded conditions from entities and goals")
    if unknown := next((name for name in decision.entities if not contains_entity(context, name)), None):
        raise DecisionError(
            "unverified_entity", f"Entity has no supplied user provenance: {unknown!r}. Use the original name."
        )
    if decision.name_to_check and not contains_name(context, decision.name_to_check):
        raise DecisionError("unverified_name_surface", "Suspected spelling has no supplied user provenance")
    if decision.action == "retrieve":
        for name in decision.search_hypotheses:
            if not decision.rewrite or contains_name(decision.resolved_question, name) or contains_name(context, name):
                raise DecisionError("invalid_search_hypothesis", "Hypotheses belong only to the search query")
        # A hypothesis omitted from the actual query is unused metadata, not evidence or a new player fact.
        decision.search_hypotheses = [
            name for name in decision.search_hypotheses if contains_name(decision.search_query, name)
        ]
        # Invariants only: no legacy name/intent classifier or equipment allowlist decides acceptance.
        # Without rewriting, retrieval executes the original question. An unused search_query
        # must not reject it (e.g. a model omits punctuation from a location name).
        queries = {"resolved_question": decision.resolved_question}
        if decision.rewrite:
            queries["search_query"] = decision.search_query
        numeric_question = question
        for item in inactive:
            if re.fullmatch(_NUMBER, item["value"]) and not contains_name(comparison, item["value"]):
                old = re.escape(item["value"])
                numeric_question = re.sub(rf"(?<![\w.,]){old}(?!\w|[.,]\d)", " ", numeric_question)
        negations = re.findall(rf"(?:{_NEGATION})[^,;.!?\n]*", question, re.I)
        keep_negation = any(not contains_superseded(clause, inactive, comparison) for clause in negations)
        for field, query in queries.items():
            if contains_superseded(query, inactive, comparison):
                raise DecisionError(
                    "superseded_constraint",
                    f"Remove superseded values from {field}, including mentions such as 'instead of X' or 'from X'. "
                    "Describe only the current task. Keep old values in superseded_constraints only.",
                )
            if not preserves_numbers(numeric_question, query) or not preserves_numbers(query, context):
                raise DecisionError(
                    "changed_numeric_constraints",
                    "Keep supplied digits. Translate number words as words and keep their original meaning.",
                )
            for name in decision.entities:
                if not contains_entity(query, name):
                    raise QueryNameMismatch(
                        "entity_missing_from_query",
                        f"{name!r} is missing from {field}. Keep proper names in both fields. "
                        "Keep translatable nouns out of entities and retain their meaning in the rewritten text.",
                    )
            for goal in ("PvE", "PvP", "NG+"):
                if (
                    goal.casefold() in question.casefold()
                    and goal.casefold() not in query.casefold()
                    and not contains_superseded(goal, inactive, comparison)
                ):
                    raise DecisionError("dropped_goal", "Goal dropped")
            if keep_negation and not re.search(_NEGATION + r"|\bavoid\b|\bexclude\b|\bnot\b|\bno\b|don't", query, re.I):
                raise DecisionError("dropped_negation", "Negation dropped")
        if not decision.rewrite and decision.resolved_question != question:
            raise DecisionError("unlabelled_rewrite", "A changed request must be labelled rewritten")
        if (
            decision.turn_type != "new"
            and not decision.entities
            and not has_progress_anchor(decision, request_text, selected, working)
        ):
            raise DecisionError(
                "missing_followup_context", "Dependent query lacks a resolved subject or progression milestone"
            )
    return selected


async def decide(
    llm, question, candidates, working, lang, settings, trace, *, shared_thread=False, requested_lang="auto"
) -> AgentDecision | None:
    started = time.perf_counter()
    spend(trace, "decision", settings.chat_agent_max_calls)
    diagnostic = {"status": "error", "reason": "invalid_decision"}
    trace["agent"] = diagnostic
    original_query = None
    try:
        payload = {
            "question": question,
            "answer_language": lang,
            "requested_language": requested_lang,
            "memories": candidates,
            "working_state": {k: v for k, v in working.items() if k not in {"plan_evidence", "retired_condition_keys"}},
            "shared_thread": shared_thread,
        }
        async with asyncio.timeout(settings.chat_agent_timeout_seconds):
            for attempt in range(3):
                result = await llm.invoke_chain(
                    rewrite_prompt() | llm.bind_model(json_output=True, thinking=False, temperature=0, max_tokens=1536),
                    {"policy": prompt("agent"), "history": [], "question": json.dumps(payload, ensure_ascii=False)},
                )
                data, _ = decode_output(result.content)
                try:
                    decision = AgentDecision.model_validate(data)
                    decision, normalized = normalize_sources(decision, candidates, working)
                    try:
                        check_decision(decision, question, candidates, working)
                    except DecisionError as exc:
                        if decision.rewrite and (
                            isinstance(exc, QueryNameMismatch) or exc.reason == "changed_numeric_constraints"
                        ):
                            prior_request = (
                                working.get("request_text", "") if decision.turn_type == "clarification_reply" else ""
                            )
                            if decision.turn_type != "new" and not (prior_request and working.get("pending")):
                                raise
                            original = "\n".join(part for part in (prior_request, question) if part)
                            fallback = decision.model_copy(
                                update={
                                    "rewrite": decision.turn_type != "new",
                                    "resolved_question": original,
                                    "search_query": original,
                                    "search_hypotheses": [],
                                }
                            )
                            try:
                                check_decision(fallback, question, candidates, working)
                            except DecisionError:
                                pass  # Keep the original validation failure for model repair.
                            else:
                                original_query = (fallback, normalized)
                        raise
                except ValueError as exc:
                    required = {k for k, v in AgentDecision.model_fields.items() if v.is_required()}
                    condition_error = isinstance(exc, DecisionError) and exc.reason in {
                        "unverified_entity",
                        "superseded_constraint",
                        "invalid_condition_change",
                        "missing_condition_change",
                        "entity_missing_from_query",
                    }
                    schema_issues = (
                        exc.errors(include_input=False, include_url=False, include_context=False)
                        if isinstance(exc, ValidationError)
                        else []
                    )
                    repairable_schema = any(
                        e["type"] in {"duplicate_constraint", "invalid_name_lookup"} for e in schema_issues
                    )
                    # Repair only a complete, recognizable decision; never turn arbitrary JSON into a fake success.
                    if (
                        attempt == 2
                        or (attempt and not (condition_error or repairable_schema))
                        or not isinstance(data, dict)
                        or not required <= data.keys()
                        or data.keys() - AgentDecision.model_fields.keys()
                        or (
                            settings.chat_agent_max_calls is not None
                            and len(trace.get("model_calls", [])) >= settings.chat_agent_max_calls - 1
                        )
                    ):
                        raise
                    issue = (
                        [{"field": list(e["loc"]), "type": e["type"], "message": e["msg"]} for e in schema_issues]
                        if schema_issues
                        else str(exc)
                    )
                    payload["repair"] = {"previous_decision": data, "validation_error": issue}
                    if isinstance(exc, DecisionError):
                        payload["repair"]["reason"] = exc.reason
                    diagnostic["repair_attempts"] = attempt + 1
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
        reason = (
            exc.reason
            if isinstance(exc, DecisionError)
            else "invalid_json"
            if isinstance(exc, OutputFormatError)
            else "invalid_decision_schema"
        )
        diagnostic["validation_reason"] = reason
        if original_query is not None:
            decision, normalized = original_query
            diagnostic.update(
                status="ok",
                action=decision.action,
                intent=decision.intent,
                turn_type=decision.turn_type,
                rewrite=decision.rewrite,
                reason="original_query_fallback",
                selected_memory_ids=decision.selected_memory_ids,
                normalized_source_refs=normalized,
            )
            return decision
        logger.warning(
            "Agent decision rejected",
            extra={"data": {"reason": reason, "repair_attempts": diagnostic.get("repair_attempts", 0)}},
        )
        return None
    finally:
        diagnostic["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
