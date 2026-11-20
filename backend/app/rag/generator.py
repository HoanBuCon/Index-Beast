"""Shared generation/stream validation with explicit evidence policy (not an entailment judge).

Phụ trách: TV3 · [S3] Generation
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Annotated, Protocol, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.adapters.llm import LLMError, LLMResponse
from app.adapters.tavily import WebHit
from app.api.schemas.chat import Clarification, Source
from app.rag.agent import spend
from app.rag.build_data import unchecked_stat_pairs
from app.rag.evidence import evidence_units
from app.rag.output import MAX_OUTPUT_CHARS, OutputFormatError, char_class, decode_output, stream_body_prefix
from app.rag.prompts import generation_prompt, prompt, rewrite_prompt
from core.errors import UnavailableError, UpstreamError
from core.types import Hit

_STREAM_EMITTER: ContextVar[Callable[[str], Awaitable[None]]] = ContextVar("indexbeast_stream_emitter")

CITATION = re.compile(r"\[(\d+)\]")
URL = re.compile(r"https?://|www\.", re.IGNORECASE)
# Payload/protocol field names are not player-facing words; an answer that echoes one is regenerated.
INTERNAL_FIELD = re.compile(
    r"\b(?:checked_build|build_check|player_profile|build_allocation|quote_ids?|evidence_units|task_plan)\b"
)
SECTION_HEADING = re.compile(r"#{2,3} [^\r\n]+")
BLOCK_SEPARATOR = re.compile(r"(\r?\n[ \t]*\r?\n(?:[ \t]*\r?\n)*)")


def cited_blocks(answer: str) -> tuple[str, int]:
    parts = BLOCK_SEPARATOR.split(answer)
    blocks = [(index, block) for index, block in enumerate(parts[::2]) if block.strip()]
    kept: list[str] = []
    previous = None
    dropped = 0
    for position, (index, block) in enumerate(blocks):
        if CITATION.search(block) or (
            SECTION_HEADING.fullmatch(block.strip())
            and position + 1 < len(blocks)
            and CITATION.search(blocks[position + 1][1])
        ):
            if previous is not None:
                kept.append(parts[2 * index - 1] if previous == index - 1 else "\n\n")
            kept.append(block)
            previous = index
        else:
            dropped += 1
    return ("".join(kept) if dropped else answer), dropped


def grounded_stream_prefix(text: str) -> str:
    # A block without a citation can still gain one while its tokens arrive. Hold it
    # until then, together with any heading that labels it. Use the same filter as JSON.
    return cited_blocks(text)[0].rstrip("\r\n") if text.strip() else ""


class LLM(Protocol):
    def bind_model(self, **kwargs) -> Runnable: ...
    async def invoke_chain(self, chain: Runnable, inputs) -> LLMResponse: ...
    def stream_chain(self, chain: Runnable, inputs) -> AsyncIterator[str]: ...


@dataclass
class Prepared:
    mode: str
    lang: str
    messages: list[dict]
    hits: list[Hit] = field(default_factory=list)
    static_answer: str | None = None
    trace: dict = field(default_factory=dict)
    template: ChatPromptTemplate | None = None
    values: dict = field(default_factory=dict)
    clarification: Clarification | None = None
    player_state: object = None  # Request-local copy; service commits only after successful completion.
    agent_decision: dict = field(default_factory=dict)
    max_calls: int | None = None
    checked_build: dict | None = None
    gameplay_advice: bool = False


@dataclass
class Generated:
    answer: str
    sources: list[Source] = field(default_factory=list)
    grounded: bool = False


class RAGValidationError(UpstreamError):
    """Static reason used internally for bounded protocol recovery; no answer bodies."""

    def __init__(self, reason: str):
        super().__init__("Câu trả lời RAG thiếu bằng chứng hoặc trích dẫn không hợp lệ.")
        self.reason = reason


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    index: int = Field(ge=1, le=5)
    quote: str | None = Field(default=None, min_length=8, max_length=2000)
    quote_id: str | None = Field(default=None, pattern=r"^q\d{1,4}$")
    quote_ids: list[Annotated[str, Field(pattern=r"^q\d{1,4}$")]] | None = Field(
        default=None, min_length=1, max_length=3
    )

    @model_validator(mode="after")
    def one_reference(self):
        if sum(value is not None for value in (self.quote, self.quote_id, self.quote_ids)) != 1:
            raise ValueError("Choose exactly one quote_ids, quote_id or legacy quote")
        if self.quote_ids is not None and len(set(self.quote_ids)) != len(self.quote_ids):
            raise ValueError("Duplicate quote ID")
        return self


class GroundedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str = Field(min_length=1, max_length=16000)
    evidence: list[Evidence] = Field(max_length=5)
    insufficient: bool
    advisory: bool = False
    recommendation: str | None = Field(default=None, min_length=1, max_length=1000)
    limitation: str | None = Field(default=None, min_length=1, max_length=1000)
    build_allocation: dict[str, int] | None = Field(default=None, min_length=8, max_length=8)


def build_issues(prepared, answer: str) -> list[dict]:
    """Presentation problems of a build answer the Answer Guard should fix. Never a reason to drop the answer."""
    from app.rag.build_data import ATTRIBUTES, build_rules, stat_pairs

    pairs = stat_pairs(answer)
    artifact = prepared.checked_build
    if artifact is not None:
        issues = []
        if wrong := unchecked_stat_pairs(answer, artifact):
            issues.append({"kind": "numbers", "pairs": [{"attribute": k, "printed": v} for k, v in wrong[:8]]})
        if {k for k, _ in pairs} != set(ATTRIBUTES):
            issues.append({"kind": "missing_table"})  # Not all eight attributes printed (wrong values: "numbers").
        return issues
    rules = build_rules((prepared.values or {}).get("player_profile") or {})
    table = dict(pairs)
    if rules and set(table) == set(ATTRIBUTES) and sum(table.values()) != rules["attribute_total"]:
        return [
            {
                "kind": "total",
                "printed_total": sum(table.values()),
                "level": rules["level"],
                "attribute_total": rules["attribute_total"],
            }
        ]
    return []


def log_stat_mismatch(prepared, wrong, artifact, where):
    """Attribute names and numbers only (game values, not prose): which printed number did not match."""
    from app.rag.build_data import checked_numbers

    allowed = checked_numbers(artifact)
    data = {
        "where": where,
        "pairs": [{"attribute": k, "printed": v, "allowed": sorted(allowed.get(k, set()))} for k, v in wrong[:8]],
    }
    prepared.trace.setdefault("stat_mismatch", []).append(data)
    logging.getLogger(__name__).warning("Stat number mismatch", extra={"data": data})


def allocation_label(artifact: dict, lang: str) -> str:
    """Heading of the rendered allocation, stating every assumption and every unchecked part."""
    weapon, cls = artifact.get("weapon"), artifact["starting_class"]
    vi = lang == "vi"
    notes = []
    if weapon:
        notes.append("một tay, không bonus" if vi else "one-handed, no bonuses")
    if artifact["weapon_suggested"]:
        notes.append("vũ khí do IndexBeast đề xuất" if vi else "weapon suggested by IndexBeast")
    if artifact["class_assumed"]:
        notes.append(
            f"giả định class {cls} vì bạn chưa nêu class" if vi else f"assuming {cls} since no class was given"
        )
    if not artifact["class_floor_verified"]:
        if cls:
            notes.append(f"chưa kiểm chỉ số khởi đầu của class {cls}" if vi else f"{cls} starting values not checked")
        else:
            notes.append("chưa kiểm chỉ số khởi đầu của class" if vi else "starting-class values not checked")
    if not artifact["requirements_checked"]:
        if weapon:
            notes.append("chưa kiểm yêu cầu vũ khí" if vi else "weapon requirements not checked")
        else:
            notes.append(
                "chưa chọn vũ khí nên chưa kiểm yêu cầu vũ khí" if vi else "no weapon chosen, requirements not checked"
            )
    head = (
        (f"Gợi ý phân bổ cho {weapon}" if weapon else "Gợi ý phân bổ 8 chỉ số")
        if vi
        else (f"Suggested allocation for {weapon}" if weapon else "Suggested eight-attribute allocation")
    )
    return head + (f" ({', '.join(notes)})" if notes else "")


def validate_answer(prepared: Prepared, data: dict) -> Generated:
    unchecked_notice = ""
    failure = "schema_invalid"
    try:
        parsed = GroundedAnswer.model_validate(data)
        used = {int(n) for n in CITATION.findall(parsed.answer)}
        evidence = {}
        for item in parsed.evidence:
            if item.index in evidence:
                failure = "duplicate_evidence_index"
                raise ValueError("Use one evidence object per source with quote_ids")
            if item.index > len(prepared.hits):
                failure = "quote_not_verbatim_or_index"
                raise ValueError("Evidence index is outside selected context")
            text = prepared.hits[item.index - 1].payload["text"]
            units = evidence_units(text)
            quotes = (
                [units.get(q) for q in item.quote_ids]
                if item.quote_ids is not None
                else [units.get(item.quote_id) if item.quote_id is not None else item.quote]
            )
            if any(quote is None for quote in quotes):
                failure = "unknown_quote_id"
                raise ValueError("Unknown evidence unit ID")
            evidence[item.index] = quotes
        if URL.search(parsed.answer):
            failure = "model_url"
            raise ValueError("URLs must come from server metadata")
        if any(INTERNAL_FIELD.search(text or "") for text in (parsed.answer, parsed.limitation, parsed.recommendation)):
            failure = "internal_field_name"
            raise ValueError("Internal field names are not player-facing text")
        if parsed.advisory:
            failure = "invalid_gameplay_advice"
            if (
                not prepared.gameplay_advice
                or parsed.insufficient
                or not parsed.answer.strip()
                or used
                or evidence
                or parsed.limitation is not None
                or parsed.recommendation is not None
                or parsed.build_allocation is not None
                or prepared.checked_build is not None
            ):
                raise ValueError("Gameplay advice requires an eligible request and uncited qualitative guidance")
            prepared.trace["answer_basis"] = "gameplay_advice"
            return Generated(parsed.answer)
        if parsed.insufficient:
            if prepared.checked_build is not None:
                failure = "invalid_build_allocation"
                raise ValueError("Checked build cannot be silently discarded")
            if parsed.build_allocation is not None:
                raise ValueError("Insufficient answers cannot include a build allocation")
            if used or evidence or parsed.limitation is not None or parsed.recommendation is not None:
                failure = "insufficient_with_citations"
                raise ValueError("Insufficient answer must not claim sources")
            return Generated(parsed.answer)
        if not used or not used <= set(evidence):
            failure = "citation_evidence_indices"
            # Only numeric protocol metadata, never answer/quote contents or private reasoning.
            prepared.trace["citation_indices"] = {"answer_indices": sorted(used), "evidence_indices": sorted(evidence)}
            logging.getLogger(__name__).warning(
                "Citation index mismatch", extra={"data": prepared.trace["citation_indices"]}
            )
            raise ValueError("Every citation needs explicit evidence")
        if unused := set(evidence) - used:
            # Extra evidence the answer never cites is not a claim: drop it rather than fail a valid answer
            # (live 20/11: a complete quest answer was lost after streaming because of one spare evidence item).
            for index in unused:
                evidence.pop(index)
            prepared.trace["dropped_unused_evidence"] = sorted(unused)
            logging.getLogger(__name__).warning("Dropped uncited evidence", extra={"data": {"count": len(unused)}})
        for index, quotes in evidence.items():
            if index > len(prepared.hits) or any(
                quote not in prepared.hits[index - 1].payload["text"] for quote in quotes
            ):
                failure = "quote_not_verbatim_or_index"
                raise ValueError("Evidence quote is not in cited text")
        answer = parsed.answer
        if parsed.recommendation is not None:
            failure = "invalid_gameplay_advice"
            if (
                not prepared.gameplay_advice
                or prepared.checked_build is not None
                or parsed.build_allocation is not None
                or not parsed.recommendation.strip()
                or URL.search(parsed.recommendation)
                or CITATION.search(parsed.recommendation)
            ):
                raise ValueError("A separate recommendation requires eligible gameplay evidence and no citations")
        issues = build_issues(prepared, answer)
        if issues and not prepared.trace.get("guard_done"):
            # Presentation problems are not a reason to drop an answer: the Answer Guard rewrites it before display.
            prepared.trace["guard_request"] = {"answer": parsed.answer, "issues": issues}
        if prepared.checked_build is not None:
            from app.rag.build_data import ATTRIBUTES, check

            failure = "invalid_build_allocation"
            artifact = prepared.checked_build
            verified = check(artifact["data"], artifact["allocation"], prepared.values["player_profile"], prepared.hits)
            if verified["version"] != artifact["version"] or (
                parsed.build_allocation is not None and parsed.build_allocation != artifact["allocation"]
            ):
                raise ValueError("Generator changed checked allocation")
            required_indices = {i for i, h in enumerate(prepared.hits, 1) if h.id in artifact["sources"]}
            # The backend renders the checked table and cites its rule/requirement sources itself; a source the
            # prose did not quote is cited with its own text, never with model wording.
            for i in required_indices - set(evidence):
                evidence[i] = [next(iter(evidence_units(prepared.hits[i - 1].payload["text"]).values()))]
            used |= required_indices
            # Assumptions and unchecked parts are always stated. The checked numbers line is added only when the
            # writer's own table is missing or (after the Answer Guard) still differs: nothing is dropped.
            wrong = unchecked_stat_pairs(answer, artifact)
            answer += "\n\n" + allocation_label(artifact, prepared.lang)
            if any(i["kind"] == "missing_table" for i in issues) or wrong:
                answer += ": " + " | ".join(f"{k.title()} {artifact['allocation'][k]}" for k in ATTRIBUTES)
                if wrong:
                    log_stat_mismatch(prepared, wrong, artifact, "final")
                    answer += (
                        " (đây là bảng đã kiểm; dùng các số này nếu khác bảng phía trên)"
                        if prepared.lang == "vi"
                        else " (this is the checked table; use these numbers where they differ from the one above)"
                    )
            else:
                prepared.trace["allocation_printed_by_writer"] = True
            answer += " " + "".join(f"[{i}]" for i in sorted(required_indices))
        elif parsed.build_allocation is not None:
            # A separate unchecked allocation field is not rendered; numbers the writer put in its own prose
            # are a reference suggestion and stay (their total is checked below).
            prepared.trace["dropped_unchecked_allocation"] = True
            unchecked_notice = (
                "Phân bổ chỉ số cụ thể chưa được công cụ tính kiểm tra nên không hiển thị."
                if prepared.lang == "vi"
                else "A specific stat allocation was not verified by the calculator, so it is not shown."
            )
        total_issue = next((i for i in issues if i["kind"] == "total"), None)
        if total_issue and prepared.trace.get("guard_done"):
            answer += "\n\n" + (
                f"Lưu ý: tổng 8 chỉ số trong bảng là {total_issue['printed_total']}; level "
                f"{total_issue['level']} cần {total_issue['attribute_total']}."
                if prepared.lang == "vi"
                else f"Note: the table totals {total_issue['printed_total']}; level {total_issue['level']} needs "
                f"{total_issue['attribute_total']}."
            )
        if unchecked_notice:
            answer += "\n\n" + unchecked_notice
        # Every paragraph is kept (no truncated answers); uncited ones are only counted for evaluation.
        if dropped := cited_blocks(answer)[1]:
            prepared.trace["uncited_paragraphs"] = dropped
            logging.getLogger(__name__).info("Uncited paragraphs kept", extra={"data": {"count": dropped}})
        if parsed.limitation is not None:
            failure = "invalid_limitation"
            if not parsed.limitation.strip() or URL.search(parsed.limitation) or CITATION.search(parsed.limitation):
                raise ValueError("Limitations cannot claim citations or URLs")
        sources = [
            Source(
                index=i,
                title=prepared.hits[i - 1].payload["title"],
                section=prepared.hits[i - 1].payload.get("section"),
                url=prepared.hits[i - 1].payload["url"],
                text="\n[…]\n".join(evidence[i]),
                origin="web" if isinstance(prepared.hits[i - 1], WebHit) else "corpus",
            )
            for i in sorted(used)
        ]
        # Operational grounding: model supplied evidence, exact quotes and indices checked.
        # This is NOT a guarantee of semantic entailment of every claim.
        if parsed.recommendation is not None:
            answer += "\n\n" + parsed.recommendation.strip()
            prepared.trace["answer_basis"] = "evidence_with_recommendation"
        if parsed.limitation is not None:
            answer += "\n\n" + parsed.limitation.strip()
        return Generated(answer, sources, True)
    except (ValidationError, ValueError, KeyError, TypeError):
        prepared.trace["validation_failure"] = failure
        # Static category only: never log model output, source quotes, prompts or private reasoning.
        logging.getLogger(__name__).warning("RAG validation failed", extra={"data": {"reason": failure}})
        raise RAGValidationError(failure) from None


class StreamPrefixError(UpstreamError):
    """Stream prefix cannot be decoded; carries only a character category for diagnostics."""

    def __init__(self, char_class: str):
        super().__init__("Định dạng stream RAG không hợp lệ.")
        self.char_class = char_class


def answer_prefix(raw: str) -> str:
    """Decode complete JSON string units while answer is still streaming; never expose JSON metadata."""
    raw = stream_body_prefix(raw)
    match = re.match(r'^\s*\{\s*"answer"\s*:\s*"', raw)
    if not match:
        if len(raw) > 64:
            raise StreamPrefixError("answer_not_first")
        return ""
    start = end = match.end()
    while end < len(raw):
        char = raw[end]
        if char == '"':
            break
        if char == "\\":
            if end + 1 >= len(raw):
                break
            width = 6 if raw[end + 1] == "u" else 2
            if end + width > len(raw):
                break
            end += width
        else:
            end += 1
    try:
        # Same tolerance as decode_output: raw line breaks/tabs inside the string are accepted.
        return json.loads('"' + raw[start:end] + '"', strict=False)
    except json.JSONDecodeError as exc:
        raise StreamPrefixError(char_class(raw[start:end], max(0, exc.pos - 1))) from None


# Lỗi giao thức trích dẫn có thể sửa bằng cách sinh lại; lần sau vẫn qua validate_answer nên không nới kiểm chứng.
RETRYABLE_REASONS = {
    "schema_invalid",
    "invalid_json",
    "empty_output",
    "insufficient_with_citations",
    "citation_evidence_indices",
    "unknown_quote_id",
    "model_url",
    "internal_field_name",
    "stat_number_mismatch",
    "invalid_limitation",
    "duplicate_evidence_index",
    "invalid_build_allocation",
    "invalid_gameplay_advice",
}


class GenerationState(TypedDict, total=False):
    prepared: Prepared
    attempt: int
    streaming: bool
    data: object
    result: Generated
    diagnostics: dict | None
    error: Exception | None
    retry_stream: bool


class Generator:
    def __init__(self, llm: LLM, *, thinking: bool = False, format_retries: int = 1, guard_timeout: float = 15):
        if format_retries not in (0, 1):
            raise ValueError("format_retries must be 0 or 1")
        self.llm = llm
        self.guard_timeout = guard_timeout
        self.thinking = thinking
        self.format_retries = format_retries
        graph = StateGraph(GenerationState)
        graph.add_node("generate", self._generate_node)
        graph.add_node("validate", self._validate_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("finish", self._finish_node)
        graph.add_edge(START, "generate")
        graph.add_edge("generate", "validate")
        graph.add_conditional_edges("validate", self._generation_route, {"retry": "repair", "done": "finish"})
        graph.add_edge("repair", "generate")
        graph.add_edge("finish", END)
        self.graph = graph.compile(name="indexbeast_generation")

    @staticmethod
    def _inputs(prepared: Prepared, attempt: int) -> dict:
        # The server-selected reply language wins over stale model/template values and English retrieval.
        values = dict(prepared.values)
        values["lang"] = prepared.lang
        target = "Vietnamese (tiếng Việt)" if prepared.lang == "vi" else "English"
        # Policies live in prompts/*.md; str.replace keeps literal JSON braces in those files intact.
        language_policy = "\n" + prompt("language").strip().replace("{target}", target) + "\n"
        if not attempt:
            values["policy"] = values.get("policy", "") + language_policy
            return values
        # Retry with the SAME evidence/question/history and a fixed protocol reminder.
        # Never feed malformed output or private reasoning back into the prompt.
        values["policy"] = values.get("policy", "") + "\n" + prompt("format_retry").strip() + " "
        if prepared.gameplay_advice:
            values["policy"] += " " + prompt("format_retry_gameplay").strip()
        values["policy"] += language_policy
        return values

    def _retry(self, prepared: Prepared, attempt: int, diagnostics: dict, *, emitted: str = "") -> bool:
        allowed = (
            attempt < self.format_retries
            and not emitted
            and diagnostics.get("reason") in RETRYABLE_REASONS
            and diagnostics.get("json_error") not in {"output_too_large", "nesting_too_deep"}
        )
        if allowed:
            prepared.trace["generation_retries"] = attempt + 1
            prepared.trace["generation_retry_reason"] = diagnostics.get("reason")
            prepared.trace["generation_retry_thinking"] = False
            logging.getLogger(__name__).warning(
                "Retrying RAG generation", extra={"data": {"attempt": attempt + 2, "thinking": False, **diagnostics}}
            )
        return allowed

    @staticmethod
    def _decode(prepared: Prepared, raw: str):
        data, wrapper = decode_output(raw)
        if wrapper != "none":
            prepared.trace["output_normalization"] = wrapper
        return data

    @staticmethod
    def _usage(prepared: Prepared, usage: dict):
        attempts = prepared.trace.setdefault("generation_usage", [])
        attempts.append({key: usage.get(key) for key in ("prompt_tokens", "completion_tokens")})
        # Preserve usage of discarded malformed completions as well as the accepted one.
        prepared.trace["usage"] = {
            key: sum(row[key] for row in attempts) if all(type(row[key]) is int for row in attempts) else None
            for key in ("prompt_tokens", "completion_tokens")
        }

    def chain(self, prepared: Prepared, *, recovery: bool = False) -> Runnable:
        template = prepared.template or generation_prompt()
        params = {"json_output": True, "thinking": self.thinking and not recovery}
        if recovery:
            params["temperature"] = 0
        return template | self.llm.bind_model(**params)

    @staticmethod
    def _failed(prepared, diagnostics):
        prepared.trace["generation_failure"] = dict(diagnostics)
        logging.getLogger(__name__).error("Generation failed", extra={"data": dict(diagnostics)})
        messages = {
            "invalid_json": "Mô hình trả câu trả lời chưa đúng định dạng. Vui lòng thử lại.",
            "empty_output": "Mô hình chưa trả nội dung câu trả lời. Vui lòng thử lại.",
            "incomplete_output": "Câu trả lời từ mô hình bị ngắt trước khi hoàn tất. Vui lòng thử lại.",
            "provider_request_failed": "Yêu cầu tới dịch vụ mô hình thất bại. Vui lòng thử lại.",
        }
        return UpstreamError(
            messages.get(diagnostics.get("reason"), "Không nhận được câu trả lời hợp lệ từ mô hình. Vui lòng thử lại.")
        )

    async def generate(self, prepared: Prepared) -> Generated:
        with tracing_context(enabled=False):
            state = await self.graph.ainvoke(
                {"prepared": prepared, "attempt": 0, "streaming": False}, config={"recursion_limit": 12}
            )
        return state["result"]

    async def _generate_node(self, state: GenerationState) -> dict:
        p, attempt = state["prepared"], state["attempt"]
        p.trace.setdefault("generation_graph_nodes", []).append("generate")
        if p.static_answer is not None:
            result = Generated(p.static_answer)
            if state["streaming"]:
                await _STREAM_EMITTER.get()(result.answer)
            return {"result": result, "diagnostics": None, "retry_stream": False}
        if state["streaming"]:
            # Reuse the guarded incremental decoder. Validation happens before completion;
            # no retry is possible after a visible token. The bridge enforces backpressure/cleanup.
            async with aclosing(self._stream_attempt(p, attempt)) as tokens:
                async for token in tokens:
                    await _STREAM_EMITTER.get()(token)
            retry = p.trace.pop("_format_retry", False)
            return {"retry_stream": retry, "result": p.trace.get("result"), "diagnostics": None}
        try:
            spend(p.trace, "generation", p.max_calls)
            result = await self.llm.invoke_chain(self.chain(p, recovery=attempt > 0), self._inputs(p, attempt))
            self._usage(p, {"prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens})
            try:
                data = self._decode(p, result.content)
            except OutputFormatError as exc:
                exc.diagnostics["finish_reason"] = result.finish_reason
                raise
            return {"data": data, "diagnostics": None, "error": None}
        except (LLMError, OutputFormatError) as exc:
            if isinstance(exc, LLMError) and exc.diagnostics.get("reason") == "empty_output":
                self._usage(p, exc.diagnostics)
            return {"diagnostics": exc.diagnostics, "error": None}
        except ValueError:
            raise self._failed(p, {"reason": "generation_value_error"}) from None

    async def _validate_node(self, state: GenerationState) -> dict:
        p = state["prepared"]
        p.trace["generation_graph_nodes"].append("validate")
        if p.static_answer is not None or state["streaming"] or state.get("diagnostics"):
            return {}
        try:
            return {"result": await self._finalize(p, state["data"])}
        except RAGValidationError as exc:
            return {"diagnostics": {"reason": exc.reason}, "error": exc}

    async def _finalize(self, prepared: Prepared, data) -> Generated:
        """Validate, and when the answer has a presentation problem let the Answer Guard rewrite it once.

        Source falsification still fails in validate_answer. A guard rewrite that breaks citations is ignored and
        the first (already safe) answer is kept, so nothing is dropped for presentation reasons.
        """
        result = validate_answer(prepared, data)
        request = prepared.trace.pop("guard_request", None)
        if request is None or not isinstance(data, dict):
            return result
        fixed = await self._guard(prepared, request)
        if fixed is None:
            return result
        prepared.trace["guard_done"] = True
        try:
            guarded = validate_answer(prepared, {**data, "answer": fixed})
        except RAGValidationError:
            prepared.trace["answer_guard"]["status"] = "rejected_by_validation"
            return result
        prepared.trace["answer_guard"]["status"] = "applied"
        return guarded

    async def _guard(self, prepared: Prepared, request: dict) -> str | None:
        """One LLM pass that fixes the build table (wrong numbers, missing table) and keeps everything else."""
        from app.rag.build_data import build_rules

        diagnostic = prepared.trace["answer_guard"] = {
            "issues": [i["kind"] for i in request["issues"]],
            "status": "error",
        }
        artifact = prepared.checked_build or {}
        data = artifact.get("data") or {}
        rules = build_rules((prepared.values or {}).get("player_profile") or {}) or {}
        payload = {
            "answer": request["answer"],
            "issues": request["issues"],
            "answer_language": "Vietnamese (tiếng Việt)" if prepared.lang == "vi" else "English",
            "attribute_total": rules.get("attribute_total"),
            "level": rules.get("level"),
            "attribute_cap": rules.get("attribute_cap"),
            "checked_allocation": artifact.get("allocation"),
            "class_floors": {k: f["value"] for k, f in ((data.get("starting_class") or {}).get("base") or {}).items()}
            or None,
            "weapon_requirements": {k: f["value"] for k, f in (data.get("requirements") or {}).items()} or None,
        }
        try:
            spend(prepared.trace, "answer_guard", prepared.max_calls)
            async with asyncio.timeout(self.guard_timeout):
                result = await self.llm.invoke_chain(
                    rewrite_prompt()
                    | self.llm.bind_model(json_output=True, thinking=False, temperature=0, max_tokens=4096),
                    {"policy": prompt("guard"), "history": [], "question": json.dumps(payload, ensure_ascii=False)},
                )
            out, _ = decode_output(result.content)
        except (LLMError, OutputFormatError, TimeoutError, UnavailableError, ValueError):
            return None
        fixed = out.get("answer") if isinstance(out, dict) else None
        if not isinstance(fixed, str) or not fixed.strip():
            diagnostic["status"] = "empty"
            return None
        diagnostic["status"] = "proposed"
        return fixed

    def _generation_route(self, state: GenerationState) -> str:
        if state["streaming"]:
            return "retry" if state.get("retry_stream") else "done"
        diagnostics = state.get("diagnostics")
        if not diagnostics:
            return "done"
        p = state["prepared"]
        if self._retry(p, state["attempt"], diagnostics):
            p.trace.pop("validation_failure", None)
            return "retry"
        failure = self._failed(p, diagnostics)
        if state.get("error") is not None:
            raise state["error"]
        raise failure from None

    @staticmethod
    def _repair_node(state: GenerationState) -> dict:
        state["prepared"].trace["generation_graph_nodes"].append("repair")
        return {"attempt": state["attempt"] + 1, "diagnostics": None, "error": None, "retry_stream": False}

    @staticmethod
    def _finish_node(state: GenerationState) -> dict:
        p = state["prepared"]
        p.trace["generation_graph_nodes"].append("finish")
        p.trace["result"] = state["result"]
        return {}

    async def stream(self, prepared: Prepared) -> AsyncIterator[str]:
        # A single owned graph task and one-delta handoff. Closing/cancelling this iterator
        # always cancels AND awaits that task, including provider finally/aclose handlers.
        # No callback/client is stored in graph state or a checkpoint.
        queue = asyncio.Queue(maxsize=1)

        async def emit(token):
            acknowledged = asyncio.get_running_loop().create_future()
            await queue.put(("token", token, acknowledged))
            await acknowledged

        async def run():
            context_token = _STREAM_EMITTER.set(emit)
            try:
                with tracing_context(enabled=False):
                    await self.graph.ainvoke(
                        {"prepared": prepared, "attempt": 0, "streaming": True},
                        config={"recursion_limit": 12},
                    )
            except asyncio.CancelledError:
                with suppress(asyncio.QueueFull):
                    queue.put_nowait(("cancelled", None, None))
                raise
            except Exception as exc:
                await queue.put(("error", exc, None))
            else:
                await queue.put(("done", None, None))
            finally:
                _STREAM_EMITTER.reset(context_token)

        task = asyncio.create_task(run())
        try:
            while True:
                kind, value, acknowledged = await queue.get()
                if kind == "done":
                    return
                if kind == "error":
                    raise value
                if kind == "cancelled":
                    raise asyncio.CancelledError
                yield value
                if not acknowledged.done():
                    acknowledged.set_result(None)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _stream_attempt(self, prepared: Prepared, attempt: int) -> AsyncIterator[str]:
        raw, emitted = "", ""
        # A build answer may need the Answer Guard, which reads the whole answer: hold it and show it once checked.
        buffer_until_complete = prepared.checked_build is not None or prepared.agent_decision.get("intent") == "build"
        try:
            spend(prepared.trace, "generation", prepared.max_calls)
            async with aclosing(
                self.llm.stream_chain(self.chain(prepared, recovery=attempt > 0), self._inputs(prepared, attempt))
            ) as stream:
                async for token in stream:
                    raw += token
                    if len(raw) > MAX_OUTPUT_CHARS:
                        raise UpstreamError("Câu trả lời vượt giới hạn stream.")
                    if buffer_until_complete:
                        continue
                    try:
                        text = answer_prefix(raw)
                    except UpstreamError as exc:
                        if not emitted:
                            # JSON object keys may arrive in any order. Do not expose
                            # metadata; decode and validate the bounded response at EOF.
                            buffer_until_complete = True
                            continue
                        raise OutputFormatError(
                            {
                                "json_error": "invalid_answer_prefix",
                                "output_chars": len(raw),
                                "json_char": getattr(exc, "char_class", "unknown"),
                            }
                        ) from None
                    # Validate complete visible clauses before emission, including citations
                    # split across provider chunks. Keep an unfinished clause in the buffer.
                    boundary = max(text.rfind("\n"), text.rfind(". "), text.rfind("! "), text.rfind("? "))
                    safe = text[: boundary + 1] if boundary >= 0 else ""
                    self._check_visible(prepared, safe)
                    if INTERNAL_FIELD.search(safe):
                        # Before any visible token this is retried like a JSON answer; never shown to the player.
                        raise RAGValidationError("internal_field_name")
                    # Uncited paragraphs are no longer dropped, so complete clauses can be shown as they arrive.
                    if len(safe) > len(emitted):
                        yield safe[len(emitted) :]
                        emitted = safe
            data = self._decode(prepared, raw)
            result = await self._finalize(prepared, data)
            if not result.answer.startswith(emitted):
                raise UpstreamError("Stream không nhất quán với câu trả lời cuối.")
            if len(result.answer) > len(emitted):
                yield result.answer[len(emitted) :]
            prepared.trace["result"] = result
        except RAGValidationError as exc:
            if self._retry(prepared, attempt, {"reason": exc.reason}, emitted=emitted):
                prepared.trace.pop("validation_failure", None)
                prepared.trace["_format_retry"] = True
                return
            self._failed(prepared, {"reason": exc.reason})
            raise
        except (LLMError, OutputFormatError) as exc:
            if self._retry(prepared, attempt, exc.diagnostics, emitted=emitted):
                prepared.trace["_format_retry"] = True
                return
            raise self._failed(prepared, exc.diagnostics) from None
        except ValueError:
            raise self._failed(prepared, {"reason": "generation_value_error"}) from None

    @staticmethod
    def _check_visible(prepared: Prepared, text: str) -> None:
        indices = {int(n) for n in CITATION.findall(text)}
        if URL.search(text) or any(i < 1 or i > len(prepared.hits) for i in indices):
            raise UpstreamError("Stream chứa nguồn hoặc trích dẫn không hợp lệ.")
