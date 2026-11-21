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
from app.rag.budget import spend
from app.rag.evidence import evidence_units
from app.rag.output import MAX_OUTPUT_CHARS, OutputFormatError, decode_output
from app.rag.prompts import generation_prompt, prompt, rewrite_prompt
from core.errors import UnavailableError, UpstreamError
from core.types import Hit

_STREAM_EMITTER: ContextVar[Callable[[str], Awaitable[None]]] = ContextVar("indexbeast_stream_emitter")

CITATION = re.compile(r"\[(\d+)\]")
URL = re.compile(r"https?://|www\.", re.IGNORECASE)
# Payload/protocol field names are not player-facing words: the Answer Guard rewrites an answer that echoes one,
# and any name left after that is replaced with plain words (never a reason to drop the answer).
INTERNAL_FIELD = re.compile(r"`?\b(player_profile|agent_results|quote_ids?|evidence_units)\b`?")
PLAIN_FIELD_WORDS = {
    "vi": {
        "player_profile": "thông tin bạn đưa ra",
        "agent_results": "kết quả đã tính",
        "quote_id": "trích dẫn",
        "quote_ids": "trích dẫn",
        "evidence_units": "nguồn",
    },
    "en": {
        "player_profile": "the details you gave",
        "agent_results": "the computed results",
        "quote_id": "the quote",
        "quote_ids": "the quotes",
        "evidence_units": "the sources",
    },
}


def leaked_fields(text: str | None) -> list[str]:
    return sorted({m.group(1) for m in INTERNAL_FIELD.finditer(text or "")})


def plain_field_names(text: str | None, lang: str) -> str | None:
    """Last safety net after the Answer Guard: swap any internal field name for words a player understands."""
    if not text:
        return text
    words = PLAIN_FIELD_WORDS["vi" if lang == "vi" else "en"]
    return INTERNAL_FIELD.sub(lambda m: words[m.group(1)], text)


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


def validate_answer(prepared: Prepared, data: dict) -> Generated:
    failure = "schema_invalid"
    try:
        parsed = GroundedAnswer.model_validate(data)
        used = {int(n) for n in CITATION.findall(parsed.answer)}
        evidence = {}
        for item in parsed.evidence:
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
            # Two evidence items for one source are a layout slip, not a false claim: merge their quotes (22/11).
            merged = evidence.setdefault(item.index, [])
            merged.extend(q for q in quotes if q not in merged)
        if URL.search(parsed.answer):
            failure = "model_url"
            raise ValueError("URLs must come from server metadata")
        lang, guard_done = prepared.lang, prepared.trace.get("guard_done")
        field_issues = [{"kind": "internal_field_name", "fields": f}] if (f := leaked_fields(parsed.answer)) else []
        if field_issues:
            if guard_done:
                prepared.trace["internal_field_replaced"] = field_issues[0]["fields"]
            else:
                prepared.trace["guard_request"] = {"answer": parsed.answer, "issues": field_issues}
        if parsed.advisory:
            failure = "invalid_gameplay_advice"
            extras = [x.strip() for x in (parsed.recommendation, parsed.limitation) if x is not None]
            if (
                not prepared.gameplay_advice
                or parsed.insufficient
                or not parsed.answer.strip()
                or used
                or evidence
                or any(not x or URL.search(x) or CITATION.search(x) for x in extras)
            ):
                raise ValueError("Gameplay advice must be uncited, without URLs, and enabled by the Agent")
            prepared.trace["answer_basis"] = "gameplay_advice"
            return Generated(plain_field_names("\n\n".join([parsed.answer, *extras]), lang))
        if parsed.insufficient:
            if used or evidence or parsed.limitation is not None or parsed.recommendation is not None:
                failure = "insufficient_with_citations"
                raise ValueError("Insufficient answer must not claim sources")
            return Generated(plain_field_names(parsed.answer, lang))
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
                or not parsed.recommendation.strip()
                or URL.search(parsed.recommendation)
                or CITATION.search(parsed.recommendation)
            ):
                raise ValueError("A separate recommendation requires eligible gameplay evidence and no citations")
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
        return Generated(plain_field_names(answer, lang), sources, True)
    except (ValidationError, ValueError, KeyError, TypeError):
        prepared.trace.pop("guard_request", None)  # A rejected answer is never sent to the Answer Guard.
        prepared.trace["validation_failure"] = failure
        # Static category only: never log model output, source quotes, prompts or private reasoning.
        logging.getLogger(__name__).warning("RAG validation failed", extra={"data": {"reason": failure}})
        raise RAGValidationError(failure) from None


# Lỗi giao thức trích dẫn có thể sửa bằng cách sinh lại; lần sau vẫn qua validate_answer nên không nới kiểm chứng.
RETRYABLE_REASONS = {
    "schema_invalid",
    "invalid_json",
    "empty_output",
    "insufficient_with_citations",
    "citation_evidence_indices",
    "unknown_quote_id",
    "model_url",
    "invalid_limitation",
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
        """One LLM pass that rewrites the listed presentation problems (internal field names) and keeps the rest."""
        diagnostic = prepared.trace["answer_guard"] = {
            "issues": [i["kind"] for i in request["issues"]],
            "status": "error",
        }
        payload = {
            "answer": request["answer"],
            "issues": request["issues"],
            "answer_language": "Vietnamese (tiếng Việt)" if prepared.lang == "vi" else "English",
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
        # Every answer is held until it is complete and checked (MinhMuc, 21/11): the Answer Guard reads the whole
        # answer, a retry is still possible, and the player never sees text that is later cut or replaced by an error.
        try:
            spend(prepared.trace, "generation", prepared.max_calls)
            async with aclosing(
                self.llm.stream_chain(self.chain(prepared, recovery=attempt > 0), self._inputs(prepared, attempt))
            ) as stream:
                async for token in stream:
                    raw += token
                    if len(raw) > MAX_OUTPUT_CHARS:
                        raise UpstreamError("Câu trả lời vượt giới hạn stream.")
            data = self._decode(prepared, raw)
            result = await self._finalize(prepared, data)
            if result.answer:
                yield result.answer
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
