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
from app.rag.evidence import evidence_units
from app.rag.output import MAX_OUTPUT_CHARS, OutputFormatError, decode_output, stream_body_prefix
from app.rag.prompts import generation_prompt
from core.errors import UpstreamError
from core.types import Hit

_STREAM_EMITTER: ContextVar[Callable[[str], Awaitable[None]]] = ContextVar("indexbeast_stream_emitter")

CITATION = re.compile(r"\[(\d+)\]")
URL = re.compile(r"https?://|www\.", re.IGNORECASE)


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
    limitation: str | None = Field(default=None, min_length=1, max_length=1000)
    build_allocation: dict[str, int] | None = Field(default=None, min_length=8, max_length=8)


def validate_answer(prepared: Prepared, data: str | dict) -> Generated:
    if prepared.mode == "llm_only":
        if not isinstance(data, str) or not data.strip() or CITATION.search(data) or URL.search(data):
            raise UpstreamError("Câu trả lời chưa đúng chính sách không trích dẫn nguồn ở chế độ LLM.")
        return Generated(data)
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
        if parsed.insufficient:
            if prepared.checked_build is not None:
                failure = "invalid_build_allocation"
                raise ValueError("Checked build cannot be silently discarded")
            if parsed.build_allocation is not None:
                raise ValueError("Insufficient answers cannot include a build allocation")
            if used or evidence or parsed.limitation is not None:
                failure = "insufficient_with_citations"
                raise ValueError("Insufficient answer must not claim sources")
            return Generated(parsed.answer)
        if not used or used != set(evidence):
            failure = "citation_evidence_indices"
            # Only numeric protocol metadata, never answer/quote contents or private reasoning.
            prepared.trace["citation_indices"] = {"answer_indices": sorted(used), "evidence_indices": sorted(evidence)}
            logging.getLogger(__name__).warning(
                "Citation index mismatch", extra={"data": prepared.trace["citation_indices"]}
            )
            raise ValueError("Citations and explicit evidence must match")
        for index, quotes in evidence.items():
            if index > len(prepared.hits) or any(
                quote not in prepared.hits[index - 1].payload["text"] for quote in quotes
            ):
                failure = "quote_not_verbatim_or_index"
                raise ValueError("Evidence quote is not in cited text")
        answer = parsed.answer
        if prepared.checked_build is not None:
            from app.rag.build_data import check
            from app.rag.build_math import ATTRIBUTES

            failure = "invalid_build_allocation"
            artifact = prepared.checked_build
            attribute_pattern = "|".join(ATTRIBUTES)
            if re.search(rf"\b(?:{attribute_pattern})\b\s*[:=|—–-]?\s*\d", answer, re.I) or any(
                "|" in line and sum(bool(re.search(rf"\b{k}\b", line, re.I)) for k in ATTRIBUTES) >= 2
                for line in answer.splitlines()
            ):
                raise ValueError("Stat numbers belong in the checked artifact, not model prose")
            verified = check(artifact["data"], artifact["allocation"], prepared.values["player_profile"], prepared.hits)
            if verified["version"] != artifact["version"] or (
                parsed.build_allocation is not None and parsed.build_allocation != artifact["allocation"]
            ):
                raise ValueError("Generator changed checked allocation")
            required_indices = {i for i, h in enumerate(prepared.hits, 1) if h.id in artifact["sources"]}
            for i in required_indices:
                hit = prepared.hits[i - 1]
                facts = [artifact["data"][k] for k in ("starting_level", "points_per_level", "attribute_cap")]
                facts.append(artifact["data"]["class_floor_rule"])
                facts += list(artifact["data"]["base"].values()) + list(artifact["data"]["requirements"].values())
                units = evidence_units(hit.payload["text"])
                if any(units[f["quote_id"]] not in evidence.get(i, []) for f in facts if f["source_id"] == hit.id):
                    raise ValueError("Missing exact accounting quotes")
            if not required_indices <= used:
                raise ValueError("Missing accounting citations")
            answer += "\n\n" + (
                "Gợi ý phân bổ (một tay, không bonus): "
                if prepared.lang == "vi"
                else "Suggested allocation (one-handed, no bonuses): "
            )
            answer += " | ".join(f"{k.title()} {artifact['allocation'][k]}" for k in ATTRIBUTES)
            answer += " " + "".join(f"[{i}]" for i in sorted(required_indices))
        elif parsed.build_allocation is not None:
            from app.rag.build_math import ATTRIBUTES, check_allocation
            from app.rag.gameplay_knowledge import trusted_rule_kind
            from app.services.gameplay import extract

            failure = "invalid_build_allocation"
            profile = prepared.values.get("player_profile") or extract(
                json.loads(prepared.values["payload"])["question"]
            )
            required = {"level_rule", "class_rule", "weapon_rule", "respec_rule"}
            cited_rules = {trusted_rule_kind(prepared.hits[i - 1]) for i in used}
            if not required.issubset(cited_rules):
                raise ValueError("Accounting sources must be present and cited")
            prepared.trace["build_check"] = check_allocation(parsed.build_allocation, profile)
            label = "Gợi ý phân bổ chỉ số:" if prepared.lang == "vi" else "Suggested stat allocation:"
            table = " | ".join(f"{key.title()} {parsed.build_allocation[key]}" for key in ATTRIBUTES)
            # Server renders the checked values, never repairs arithmetic in model prose.
            answer += (
                "\n\n"
                + label
                + "\n"
                + table
                + " "
                + "".join(f"[{i}]" for i in sorted(used) if prepared.hits[i - 1].payload.get("rule_kind") in required)
            )
        paragraphs = [p for p in answer.split("\n\n") if p.strip()]
        cited = [p for p in paragraphs if CITATION.search(p)]
        if len(cited) < len(paragraphs):
            # Đoạn không có nguồn thì không hiển thị; đã chắc còn đoạn có nguồn vì used khớp evidence ở trên.
            answer = "\n\n".join(cited)
            prepared.trace["dropped_uncited_paragraphs"] = len(paragraphs) - len(cited)
            logging.getLogger(__name__).warning(
                "Dropped uncited paragraphs", extra={"data": {"count": len(paragraphs) - len(cited)}}
            )
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
        if parsed.limitation is not None:
            answer += "\n\n" + parsed.limitation.strip()
        return Generated(answer, sources, True)
    except (ValidationError, ValueError, KeyError, TypeError):
        prepared.trace["validation_failure"] = failure
        # Static category only: never log model output, source quotes, prompts or private reasoning.
        logging.getLogger(__name__).warning("RAG validation failed", extra={"data": {"reason": failure}})
        raise RAGValidationError(failure) from None


def answer_prefix(raw: str) -> str:
    """Decode complete JSON string units while answer is still streaming; never expose JSON metadata."""
    raw = stream_body_prefix(raw)
    match = re.match(r'^\s*\{\s*"answer"\s*:\s*"', raw)
    if not match:
        if len(raw) > 64:
            raise UpstreamError("Định dạng stream RAG không hợp lệ.")
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
        return json.loads('"' + raw[start:end] + '"')
    except ValueError:
        raise UpstreamError("Định dạng stream RAG không hợp lệ.") from None


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
    "duplicate_evidence_index",
    "invalid_build_allocation",
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
    def __init__(self, llm: LLM, *, thinking: bool = False, format_retries: int = 1):
        if format_retries not in (0, 1):
            raise ValueError("format_retries must be 0 or 1")
        self.llm = llm
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
        language_policy = (
            f"\nAUTHORITATIVE RESPONSE LANGUAGE: Write all explanatory prose in {target}, "
            "including answer, clarification and limitation. The request may have been rewritten into English "
            "for search and the evidence may be English; neither changes the response language. "
            "Keep proper names, exact quotations, citation markers, JSON keys and technical identifiers unchanged. "
            "Do not copy the language of JSON examples. Check the language before returning the response.\n"
        )
        if not attempt:
            values["policy"] = values.get("policy", "") + language_policy
            return values
        # Retry with the SAME evidence/question/history and a fixed protocol reminder.
        # Never feed malformed output or private reasoning back into the prompt.
        values["policy"] = values.get("policy", "") + (
            '\nFORMAT RETRY: Return ONLY one valid JSON object, with "answer" first, '
            '"evidence" array and "insufficient" boolean. No Markdown or prose outside JSON. '
            'If evidence is insufficient, return {"answer":"State the specific evidence gap '
            'in the requested language.","evidence":[],"insufficient":true}. '
            "Use only the supplied evidence; never invent citations or change source indices."
            " If insufficient=true, answer must contain ONLY the specific gap or clarification: no related facts, "
            "source counts, source descriptions or bracketed citations. "
            "If insufficient=false, every answer paragraph must contain [n], the set of [n] must equal the set of "
            "evidence.index, and each quote_id must come from that source's evidence_units. "
            "Keep the response short and avoid decorative quotes."
            " Required fields: answer (nonempty string), evidence (array), insufficient (boolean). "
            "Each evidence item must have integer index and exactly one of quote_ids (1–3 distinct ID strings), "
            "quote_id (one ID string) or quote (legacy exact text). Do not repeat source indices. "
            "limitation is optional: omit it when unused; do not return null, empty text, or extra fields. "
            "Do not include type, response_format, status or any other undeclared field. "
            'For a build that needs clarification use {"answer":"Which weapon and PvE or PvP?",'
            '"evidence":[],"insufficient":true}, translated into the reply language. '
            "Do not mix this clarification object with supported claims, evidence or limitation. "
            "Answer directly without narrating retrieval or describing the supplied context. "
        )
        values["policy"] += language_policy
        return values

    def _retry(self, prepared: Prepared, attempt: int, diagnostics: dict, *, emitted: str = "") -> bool:
        allowed = (
            prepared.mode == "rag"
            and attempt < self.format_retries
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
        if prepared.mode != "rag":
            return raw
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
        params = {
            "json_output": prepared.mode == "rag",
            "thinking": self.thinking and prepared.mode == "rag" and not recovery,
        }
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

    def _validate_node(self, state: GenerationState) -> dict:
        p = state["prepared"]
        p.trace["generation_graph_nodes"].append("validate")
        if p.static_answer is not None or state["streaming"] or state.get("diagnostics"):
            return {}
        try:
            return {"result": validate_answer(p, state["data"])}
        except RAGValidationError as exc:
            return {"diagnostics": {"reason": exc.reason}, "error": exc}

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
        try:
            spend(prepared.trace, "generation", prepared.max_calls)
            async with aclosing(
                self.llm.stream_chain(self.chain(prepared, recovery=attempt > 0), self._inputs(prepared, attempt))
            ) as stream:
                async for token in stream:
                    raw += token
                    if len(raw) > MAX_OUTPUT_CHARS:
                        raise UpstreamError("Câu trả lời vượt giới hạn stream.")
                    try:
                        text = answer_prefix(raw) if prepared.mode == "rag" else raw
                    except UpstreamError:
                        raise OutputFormatError(
                            {"json_error": "invalid_answer_prefix", "output_chars": len(raw)}
                        ) from None
                    # Validate complete visible clauses before emission, including citations
                    # split across provider chunks. Keep an unfinished clause in the buffer.
                    boundary = max(text.rfind("\n"), text.rfind(". "), text.rfind("! "), text.rfind("? "))
                    safe = text[: boundary + 1] if boundary >= 0 else ""
                    self._check_visible(prepared, safe)
                    if len(safe) > len(emitted):
                        yield safe[len(emitted) :]
                        emitted = safe
            data = self._decode(prepared, raw)
            result = validate_answer(prepared, data)
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
