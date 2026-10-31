"""Shared generation/stream validation with explicit evidence policy (not an entailment judge).

Phụ trách: TV3 · [S3] Generation
"""

import json
import logging
import re
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Protocol

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.adapters.llm import LLMError, LLMResponse
from app.api.schemas.chat import Source
from app.rag.evidence import evidence_units
from app.rag.output import MAX_OUTPUT_CHARS, OutputFormatError, decode_output, stream_body_prefix
from app.rag.prompts import generation_prompt
from core.errors import UpstreamError
from core.types import Hit

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

    @model_validator(mode="after")
    def one_reference(self):
        if (self.quote is None) == (self.quote_id is None):
            raise ValueError("Choose exactly one quote_id or legacy quote")
        return self


class GroundedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str = Field(min_length=1, max_length=16000)
    evidence: list[Evidence] = Field(max_length=5)
    insufficient: bool
    limitation: str | None = Field(default=None, min_length=1, max_length=1000)


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
            if item.index > len(prepared.hits):
                failure = "quote_not_verbatim_or_index"
                raise ValueError("Evidence index is outside selected context")
            text = prepared.hits[item.index - 1].payload["text"]
            quote = evidence_units(text).get(item.quote_id) if item.quote_id is not None else item.quote
            if quote is None:
                failure = "unknown_quote_id"
                raise ValueError("Unknown evidence unit ID")
            evidence[item.index] = quote
        if URL.search(parsed.answer):
            failure = "model_url"
            raise ValueError("URLs must come from server metadata")
        if parsed.insufficient:
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
        for index, quote in evidence.items():
            if index > len(prepared.hits) or quote not in prepared.hits[index - 1].payload["text"]:
                failure = "quote_not_verbatim_or_index"
                raise ValueError("Evidence quote is not in cited text")
        if any(not CITATION.search(p) for p in parsed.answer.split("\n\n") if p.strip()):
            failure = "uncited_paragraph"
            raise ValueError("Every answer paragraph needs evidence")
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
                text=evidence[i],
            )
            for i in sorted(used)
        ]
        # Operational grounding: model supplied evidence, exact quotes and indices checked.
        # This is NOT a guarantee of semantic entailment of every claim.
        answer = parsed.answer
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


class Generator:
    def __init__(self, llm: LLM, *, thinking: bool = False, format_retries: int = 1):
        if format_retries not in (0, 1):
            raise ValueError("format_retries must be 0 or 1")
        self.llm = llm
        self.thinking = thinking
        self.format_retries = format_retries

    @staticmethod
    def _inputs(prepared: Prepared, attempt: int) -> dict:
        if not attempt:
            return prepared.values
        # Retry with the SAME evidence/question/history and a fixed protocol reminder.
        # Never feed malformed output or private reasoning back into the prompt.
        values = dict(prepared.values)
        values["policy"] = values.get("policy", "") + (
            '\nFORMAT RETRY: Return ONLY one valid JSON object, with "answer" first, '
            '"evidence" array and "insufficient" boolean. No Markdown or prose outside JSON. '
            'If evidence is insufficient, return {"answer":"State the specific evidence gap '
            'in the requested language.","evidence":[],"insufficient":true}. '
            "Use only the supplied evidence; never invent citations or change source indices."
            " If insufficient=true, answer must contain ONLY the specific gap or clarification: no related facts, "
            "source counts, source descriptions or bracketed citations. "
            "Keep the response short and avoid decorative quotes."
        )
        return values

    def _retry(self, prepared: Prepared, attempt: int, diagnostics: dict, *, emitted: str = "") -> bool:
        allowed = (
            prepared.mode == "rag"
            and attempt < self.format_retries
            and not emitted
            and diagnostics.get("reason") in {"invalid_json", "empty_output", "insufficient_with_citations"}
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
        if prepared.static_answer is not None:
            return Generated(prepared.static_answer)
        for attempt in range(self.format_retries + 1):
            try:
                result = await self.llm.invoke_chain(
                    self.chain(prepared, recovery=attempt > 0), self._inputs(prepared, attempt)
                )
                self._usage(
                    prepared, {"prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens}
                )
                try:
                    data = self._decode(prepared, result.content)
                except OutputFormatError as exc:
                    exc.diagnostics["finish_reason"] = result.finish_reason
                    raise
                return validate_answer(prepared, data)
            except RAGValidationError as exc:
                if self._retry(prepared, attempt, {"reason": exc.reason}):
                    prepared.trace.pop("validation_failure", None)
                    continue
                raise
            except (LLMError, OutputFormatError) as exc:
                if isinstance(exc, LLMError) and exc.diagnostics.get("reason") == "empty_output":
                    self._usage(prepared, exc.diagnostics)
                if self._retry(prepared, attempt, exc.diagnostics):
                    continue
                raise self._failed(prepared, exc.diagnostics) from None
            except ValueError:
                raise self._failed(prepared, {"reason": "generation_value_error"}) from None

    async def stream(self, prepared: Prepared) -> AsyncIterator[str]:
        if prepared.static_answer is not None:
            yield prepared.static_answer
            prepared.trace["result"] = Generated(prepared.static_answer)
            return
        for attempt in range(self.format_retries + 1):
            async with aclosing(self._stream_attempt(prepared, attempt)) as tokens:
                async for token in tokens:
                    yield token
            if not prepared.trace.pop("_format_retry", False):
                return

    async def _stream_attempt(self, prepared: Prepared, attempt: int) -> AsyncIterator[str]:
        raw, emitted = "", ""
        try:
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
