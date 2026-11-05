"""Validated optional rewrite; invalid/provider output falls back to original question.

Phụ trách: TV3 · [S3] Query rewrite
"""

import asyncio
import re
import time
import unicodedata
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm import LLMError
from app.rag.output import decode_output
from app.rag.prompts import prompt, rewrite_prompt


class RewriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    standalone_query_en: str = Field(min_length=1, max_length=2000)
    lang: Literal["vi", "en"]
    entities: list[str] = Field(max_length=20)
    out_of_scope: bool
    ambiguous: bool


def preserves_numbers(question: str, query: str) -> bool:
    """Fail back to the original query if a rewrite loses levels, stats, upgrade or patch literals."""
    pattern = r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)"
    expected = Counter(re.findall(pattern, question))
    actual = Counter(re.findall(pattern, query))
    return all(actual[number] >= count for number, count in expected.items())


_QUESTION_WORDS = set(
    [
        "who",
        "what",
        "where",
        "when",
        "why",
        "how",
        "is",
        "are",
        "was",
        "were",
        "does",
        "do",
        "did",
        "can",
        "could",
        "should",
        "tell",
        "me",
        "explain",
        "compare",
        "suggest",
        "please",
        "the",
        "a",
        "an",
        "i",
        "my",
        "for",
        "with",
        "without",
        "at",
        "on",
        "in",
        "of",
        "and",
        "or",
        "not",
        "no",
        "level",
        "patch",
        "build",
        "pve",
        "pvp",
        "int",
        "dex",
        "str",
        "faith",
        "arc",
        "vigor",
        "endurance",
        "mind",
        "boss",
        "game",
        "so",
        "cho",
        "toi",
        "hay",
    ]
)


_ENTITY_FORMS = {
    "Scadutree Fragment": ("Scadutree Fragment", "Scadutree Fragments"),
    "Revered Spirit Ash": ("Revered Spirit Ash", "Revered Spirit Ashes"),
}


def canonical_surface(text: str) -> str:
    """Only attested item-name inflections; never stem or fuzzy-match arbitrary proper names."""
    for canonical, forms in _ENTITY_FORMS.items():
        for form in sorted(forms, key=len, reverse=True):
            suffix = r"(?!\s+of\s+war\b)" if canonical == "Revered Spirit Ash" else ""
            text = re.sub(r"(?<!\w)" + re.escape(form) + r"(?!\w)" + suffix, canonical, text, flags=re.I)
    return text


def protected_names(question: str) -> list[str]:
    """Conservative surface-form guard, NOT NER or a translated-name dictionary."""
    # Strip recognized conversational phrases as units, not arbitrary capitalized words.
    question = canonical_surface(question)
    # Parse closed sentence-initial grammatical frames; preserve names after the frame.
    question = re.sub(
        r"(^|[.!?]\s+)(?:Ai(?=\s)|Trong(?=\s)|Theo(?=\s)|Sau(?:\s+khi)?(?=\s)|"
        r"According\s+to(?=\s)|Hai(?=\s+loại\b)|Con(?=\s+số\b)|Chia\s+(?:chỉ số|điểm)(?=\s))",
        r"\1",
        question,
    )
    question = re.sub(
        r"^(?:gia phả|gia pha|nói tiếp|noi tiep|nói thêm|noi them|tiếp tục|tiep tuc|"
        r"các con|cac con|cha mẹ|cha me|tell me more|continue)\b",
        "",
        question,
        flags=re.I,
    )
    # Whole Unicode words avoid extracting fragments of accented Vietnamese words.
    words = re.findall(r"\b[^\W\d_]+(?:['’][^\W\d_]+)*\b", question)
    words = [word for word in words if word.isascii() and word[0].isupper() and len(word) > 1]
    return [word for word in words if word.casefold() not in _QUESTION_WORDS]


def contextual_followup(question: str) -> bool:
    text = "".join(c for c in unicodedata.normalize("NFD", question.lower()) if not unicodedata.combining(c))
    return bool(
        re.search(
            r"^(?:noi tiep|noi them|tiep tuc|con (?:no|ba ay|ong ay)|cac con cua (?:ba|ong)|"
            r"tell me more|continue|what about (?:it|her|him))\b",
            text,
        )
    ) and not protected_names(question)


def _normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", canonical_surface(text)).casefold().replace("’", "'")


def _contains(text: str, surface: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_normalized(surface)) + r"(?!\w)", _normalized(text)) is not None


def rewrite_problem(question: str, query: str, entities: list[str], history: list[dict]) -> str | None:
    if not query.strip():
        return "empty_query"
    if contextual_followup(question) and (not history or not entities):
        return "unresolved_topic"
    if not preserves_numbers(question, query):
        return "numeric_constraint_lost"
    # Assistant prose can neither authorize a new subject nor become game evidence.
    context = question + "\n" + "\n".join(str(row.get("content", "")) for row in history if row.get("role") == "user")
    for entity in entities:
        if not entity.strip() or not _contains(context, entity):
            return "unverified_entity"
        if not _contains(query, entity):
            return "entity_lost"
    if any(not _contains(query, name) for name in protected_names(question)):
        return "proper_name_lost"
    # Reject new numeric literals, except those explicitly provided by user history.
    user_context = (
        question + "\n" + "\n".join(str(row.get("content", "")) for row in history if row.get("role") == "user")
    )
    if not preserves_numbers(query, user_context):
        return "numeric_constraint_added"
    # Explicit corrections replace old constraints; history must not authorize both values.
    level_pattern = r"\b(?:level|lv|cấp)\s*[:=]?\s*(\d{1,3})\b"
    current_levels = set(re.findall(level_pattern, question, re.I))
    if len(current_levels) == 1 and set(re.findall(level_pattern, query, re.I)) - current_levels:
        return "superseded_constraint"
    goals = {goal for goal in ("pve", "pvp") if re.search(r"\b" + goal + r"\b", question, re.I)}
    if len(goals) == 1 and any(re.search(r"\b" + goal + r"\b", query, re.I) for goal in {"pve", "pvp"} - goals):
        return "superseded_constraint"
    for goal in ("PvE", "PvP", "NG+"):
        if goal.casefold() in question.casefold() and goal.casefold() not in query.casefold():
            return "goal_lost"
    if re.search(
        r"không (?:dùng|sử dụng|có)|tránh dùng|\bwithout\b|do not use|don't use", question, re.I
    ) and not re.search(r"\bwithout\b|\bavoid\b|\bexclude\b|\bnot\b|\bno\b|don't", query, re.I):
        return "negation_lost"
    intents = (
        (r"so sánh|\bcompare\b", r"compare|comparison|versus|\bvs\b|better|difference"),
        (r"\bbuild\b", r"\bbuild\b|loadout"),
        (
            r"(?:lấy|tìm|nhặt|kiếm).{0,100}ở đâu|where.*(?:find|obtain|get)",
            r"where|location|obtain|acquir|find|\bget\b",
        ),
        (r"chiến thuật|né đòn|đánh bại|\bstrategy\b", r"strategy|strategies|defeat|dodge|fight|beat"),
    )
    for pattern, expected in intents:
        if re.search(pattern, question, re.I) and not re.search(expected, query, re.I):
            return "intent_lost"
    return None


async def rewrite(
    llm,
    question: str,
    history: list[dict],
    lang: str,
    *,
    deadline_seconds: float = 8,
    max_tokens: int = 512,
    diagnostics: dict | None = None,
) -> tuple[RewriteResult, bool]:
    started = time.perf_counter()
    stats = diagnostics if diagnostics is not None else {}
    stats.update(status="fallback", reason="invalid_output", model_calls=1)
    fallback = RewriteResult(
        standalone_query_en=question,
        lang=lang,
        entities=[],
        out_of_scope=False,
        ambiguous=False,
    )
    try:
        chain = rewrite_prompt() | llm.bind_model(
            json_output=True, max_tokens=max_tokens, temperature=0, thinking=False
        )
        async with asyncio.timeout(deadline_seconds):
            result = await llm.invoke_chain(
                chain,
                {
                    "policy": prompt("rewrite")
                    + f"\nServer-selected reply language: {lang}. Return this value in lang.",
                    "history": history,
                    "question": question,
                },
            )
        stats["usage"] = {"prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens}
        data, _ = decode_output(result.content)
        rewritten = RewriteResult.model_validate(data)
        if not rewritten.out_of_scope and not rewritten.ambiguous:
            problem = rewrite_problem(question, rewritten.standalone_query_en, rewritten.entities, history)
            if problem:
                stats["reason"] = problem
                return fallback, True
        # Output language is always decided by the server, never by a translated retrieval query.
        rewritten.lang = lang
        stats.update(
            status="accepted",
            reason="out_of_scope" if rewritten.out_of_scope else "ambiguous" if rewritten.ambiguous else "ok",
        )
        return rewritten, False
    except TimeoutError:
        stats["reason"] = "timeout"
        return fallback, True
    except (LLMError, ValidationError, ValueError):
        return fallback, True
    finally:
        stats["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
