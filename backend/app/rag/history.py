"""Bounded lexical recall of user-authored turns, never a source of game evidence.

No model, vector store, global user profile or new persistence is created here.
The caller supplies only the current conversation after its existing access checks.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from app.rag.rewrite import contextual_followup, protected_names

SCAN_MESSAGES = 64
MAX_SELECTED = 3
_STOP = set(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "did",
        "can",
        "could",
        "would",
        "should",
        "i",
        "my",
        "you",
        "your",
        "me",
        "we",
        "who",
        "what",
        "where",
        "when",
        "why",
        "how",
        "to",
        "of",
        "for",
        "in",
        "on",
        "at",
        "and",
        "or",
        "about",
        "tell",
        "more",
        "continue",
        "toi",
        "ban",
        "minh",
        "no",
        "ho",
        "ong",
        "ba",
        "ay",
        "la",
        "gi",
        "ai",
        "o",
        "dau",
        "khi",
        "nao",
        "tai",
        "sao",
        "co",
        "khong",
        "hay",
        "cho",
        "ve",
        "noi",
        "tiep",
        "them",
        "tuc",
        "lay",
        "tim",
        "nhat",
        "kiem",
        "dung",
        "bao",
        "nhieu",
        "duoc",
        "nhu",
        "the",
        "nao",
        "voi",
        "cua",
        "please",
        "explain",
        "describe",
        "get",
        "obtain",
        "find",
        "it",
        "he",
        "she",
        "him",
        "her",
        "they",
        "them",
        "elden",
        "ring",
        "game",
        "level",
        "lv",
        "pve",
        "pvp",
        "doi",
        "sang",
        "instead",
        "now",
        "intelligence",
        "dexterity",
        "strength",
        "vigor",
        "endurance",
        "mind",
        "faith",
        "arcane",
    ]
)
_PRONOUN = re.compile(r"\b(?:no|ho|ong ta|co ay|anh ay|ba ay|it|he|she|him|her|they|them)\b")
_RESET = re.compile(r"^(?:doi chu de|chu de moi|new topic|change (?:the )?topic|forget that)\b")
_CORRECTION = re.compile(
    r"^(?:doi sang|doi thanh|thay bang|level\s*[:=]?\s*\d|lv\s*\d|instead|make it|now level|pvp\b|pve\b)"
)
_CONTINUATION = re.compile(
    r"^(?:noi tiep|noi them|tiep tuc|giai thich them|ke tiep|tell me more|continue|explain more|more about|go on)\b"
)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return "".join(c for c in text if not unicodedata.combining(c))


def terms(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", fold(text))) - _STOP


def dependent(question: str) -> bool:
    """Closed referent cues; names in a self-contained question take precedence."""
    if topic_followup(question) or _CORRECTION.search(fold(question)):
        return True
    if subject_names(question):
        return False
    return bool(_PRONOUN.search(fold(question)))


def topic_followup(question: str) -> bool:
    return not subject_names(question) and bool(contextual_followup(question) or _CONTINUATION.search(fold(question)))


def subject_names(text: str) -> list[str]:
    """Group adjacent protected surface tokens, e.g. Bloodhound's Fang; not a game NER."""
    allowed = {word.casefold() for word in protected_names(text)} - _STOP
    result = []
    for match in re.finditer(r"\b[A-Z][a-zA-Z'’]+(?:\s+[A-Z][a-zA-Z'’]+)*\b", text):
        parts = [word for word in match[0].split() if word.casefold() in allowed]
        if parts:
            result.append(" ".join(parts))
    # A user-supplied subject need not be capitalized. Recognize the explicit topic
    # frame without translating a nickname or treating its spelling as canonical.
    if not result and (match := re.match(r"^(?:gia phả|gia pha|family tree(?: of)?)\s+(.+?)[?.!]*$", text, re.I)):
        result = [part.strip() for part in re.split(r"\s+(?:và|and|vs)\s+", match[1], flags=re.I) if part.strip()]
    return result


@dataclass
class HistorySelection:
    rows: list[dict] = field(default_factory=list)
    provenance: list[dict] = field(default_factory=list)
    reason: str = "standalone"
    ambiguous: bool = False


def select_history(question: str, history: list[dict], *, max_messages: int, max_chars: int) -> HistorySelection:
    """Search up to 64 messages and return whole user turns within both budgets.

    Overlap is a lexical signal, not a probability or measured semantic recall.
    Bare pronouns bind only to a single explicit subject in the latest user topic.
    Topic continuations can search older user turns; competing topics ask for clarification.
    """
    if _RESET.search(fold(question)) or not dependent(question):
        return HistorySelection()
    if not max_messages or not max_chars:
        return HistorySelection(reason="disabled", ambiguous=True)
    users = []
    for row in history[-SCAN_MESSAGES:]:
        if row.get("role") != "user" or not isinstance(row.get("content"), str) or not row["content"].strip():
            continue
        if _RESET.search(fold(row["content"])):
            users.clear()
        users.append(row)
    if not users:
        return HistorySelection(reason="missing_subject", ambiguous=True)

    # A useful topic anchor must be a complete user-authored request, not a prior unresolved pronoun.
    anchors = [row for row in users if not dependent(row["content"])]
    if not anchors:
        return HistorySelection(reason="missing_subject", ambiguous=True)
    wanted = terms(question)
    ranked = [(len(wanted & terms(row["content"])), i, row) for i, row in enumerate(anchors)]
    # A pronoun binds locally. Only a topic-labelled continuation may jump to an older topic.
    matching = [item for item in ranked if item[0] > 0] if topic_followup(question) else []
    if matching:
        best_score = max(item[0] for item in matching)
        tied = [row for score, _, row in matching if score == best_score]
        signatures = {tuple(name.casefold() for name in subject_names(row["content"])) for row in tied}
        if len(signatures) > 1:
            return HistorySelection(reason="competing_topics", ambiguous=True)
        anchor = tied[-1]
        reason = "lexical_topic"
    else:
        anchor = anchors[-1]
        reason = "recent_referent"
        # No jumping back over an intervening, unresolved user topic.
        last = users[-1]
        if last is not anchor and not dependent(last["content"]):
            return HistorySelection(reason="missing_subject", ambiguous=True)

    names = set(subject_names(anchor["content"]))
    if not names or (len(names) != 1 and not _CORRECTION.search(fold(question))):
        return HistorySelection(reason="competing_or_unknown_subject", ambiguous=True)
    candidates = [anchor]
    position = next(i for i, row in enumerate(users) if row is anchor)
    # Include subsequent user corrections/continuations only until the next standalone topic.
    for row in users[position + 1 :]:
        if not dependent(row["content"]):
            break
        candidates.append(row)
    limit = min(MAX_SELECTED, max_messages)
    # Keep the subject plus most recent correction(s), never replace the subject with a dangling reply.
    candidates = [candidates[0], *candidates[1:][-(limit - 1) :]] if limit > 1 else candidates[:1]
    selected, provenance, seen, used = [], [], set(), 0
    for row in candidates:
        content = row["content"]
        key = fold(content).strip()
        if key in seen:
            continue
        if used + len(content) > max_chars:
            return HistorySelection(reason="budget_exceeded", ambiguous=True)
        selected.append({"role": "user", "content": content})
        provenance.append({key: row[key] for key in ("message_id", "created_at", "conversation_id") if key in row})
        seen.add(key)
        used += len(content)
    return HistorySelection(selected, provenance, reason)
