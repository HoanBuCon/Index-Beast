"""Bounded player state and clarification, no model/tool calls or factual game inference."""

import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.api.schemas.chat import Clarification, ClarificationField
from app.rag.overview import folded
from core.errors import BadRequestError

TTL = 1800
CLASSES = (
    "Samurai",
    "Wretch",
    "Vagabond",
    "Warrior",
    "Hero",
    "Bandit",
    "Astrologer",
    "Prophet",
    "Prisoner",
    "Confessor",
)
WEAPONS = ("Moonveil", "Uchigatana", "Bloodhound's Fang", "Rivers of Blood", "Nagakiba")
LABELS = {
    "weapon": ("Bạn muốn dùng vũ khí nào?", "Which weapon would you like to use?"),
    "goal": ("Bạn chơi PvE hay PvP?", "Are you playing PvE or PvP?"),
    "level": ("Level mục tiêu của bạn là bao nhiêu?", "What is your target level?"),
    "starting_class": ("Bạn chọn class khởi đầu nào?", "What is your starting class?"),
    "current_location": ("Bạn đang ở khu vực hoặc Site of Grace nào?", "Where are you now (area or Site of Grace)?"),
    "objective": (
        "Bạn muốn tiếp tục cốt truyện chính, làm quest hay đến địa điểm nào?",
        "What is your destination or goal: main story or a quest?",
    ),
}


@dataclass
class PlayerState:
    slots: dict[str, str] = field(default_factory=dict)
    original: str = ""
    intent: str = ""
    lang: str = "vi"
    pending: Clarification | None = None
    updated: float = 0


@dataclass
class Decision:
    state: PlayerState
    query: str
    clarification: Clarification | None = None
    reply: str | None = None
    status: str = "not_applicable"


def intent_of(text):
    from app.rag.build_math import arithmetic_only

    if arithmetic_only(text):
        return ""
    text = folded(text)
    if re.search(r"\bbuild\b|phan bo.{0,20}(?:diem|chi so)|chia chi so|stat allocation|stat spread", text):
        return "build"
    if re.search(
        (
            "di dau tiep|where.{0,15}next|lo trinh|walkthrough|\\broute\\b|progression|huong "
            "dan.{0,25}(?:di|den)|how to (?:reach|get to)"
        ),
        text,
    ):
        return "route"
    return ""


def extract(text):
    slots = {}
    plain = folded(text)
    level = re.search(r"\b(?:level|lv|cấp|cap)\s*[:=]?\s*(\d{1,3})\b", text, re.I)
    if level and 1 <= int(level[1]) <= 713:
        slots["level"] = str(int(level[1]))
    goals = [goal for goal in ("PvE", "PvP") if re.search(r"\b" + goal + r"\b", text, re.I)]
    if goals:
        slots["goal"] = "/".join(goals)
    for name in CLASSES:
        if re.search(r"\b" + name + r"\b", text, re.I):
            slots["starting_class"] = name
    weapons = [name for name in WEAPONS if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I)]
    if weapons:
        slots["weapon"] = " / ".join(weapons)
    location = re.search(
        r"(?:đang ở|tôi ở|hiện ở|currently (?:at|in)|starting from|\bfrom)\s+([^\n,;.?!]{2,120})", text, re.I
    )
    if location:
        slots["current_location"] = location[1].strip()
    objective = re.search(r"(?:muốn đến|mục tiêu[: ]+|đường đến|how to reach|get to)\s+([^\n,;.?!]{2,120})", text, re.I)
    if objective:
        slots["objective"] = objective[1].strip()
    if "cot truyen chinh" in plain or "main story" in plain:
        slots["objective"] = "main story"
    for key in ("weapon", "current_location", "objective"):
        match = re.search(r"(?:^|\n)" + key + r"\s*=\s*([^\n]{1,120})", text)
        if match:
            slots[key] = match[1].strip()
    return slots


def advance(current, req, lang, *, now=None):
    """Copy-on-write: service commits only after a successful JSON/SSE completion."""
    now = time.time() if now is None else now
    state = deepcopy(current)
    if now - state.updated > TTL:
        state = PlayerState()
    text, plain = req.message, folded(req.message).strip()
    if req.clarification_id and (not state.pending or req.clarification_id != state.pending.id):
        raise BadRequestError("Câu hỏi bổ sung đã hết hạn hoặc không thuộc hội thoại này. Hãy gửi lại yêu cầu.")
    if plain.rstrip(".!?") in {"huy", "huy yeu cau", "cancel", "cancel request", "thoi", "bo qua"}:
        state.original, state.pending, state.intent = "", None, ""
        state.updated = now
        return Decision(
            state,
            text,
            reply="Đã hủy yêu cầu đang chờ." if lang == "vi" else "Pending request cancelled.",
            status="cancelled",
        )
    new_intent = intent_of(text)
    supplied = extract(text)
    pending = state.pending
    # Explicit new questions/topics supersede pending work. A slot-only reply continues it.
    new_question = bool(
        re.search(r"\?|\b(?:who|what|where|how)\b|là ai|ở đâu|làm gì|giải thích|kể về|gia phả|family tree", text, re.I)
    )
    correction = bool(
        state.intent
        and supplied
        and re.search(
            r"^(?:level|lv|goal|weapon|starting_class|current_location|objective)\s*[:=]?|^(?:PvE|PvP)\b|^đổi\b",
            text,
            re.I,
        )
    )
    continuing = (pending is not None or correction) and not new_intent and not new_question
    if continuing:
        lang = state.lang if req.options.lang == "auto" else lang
        keys = [f.key for f in pending.fields] if pending else []
        if "level" in keys and re.match(r"^\d{1,3}(?:\s*[,;]|$)", text):
            number = int(re.match(r"\d+", text)[0])
            if 1 <= number <= 713:
                supplied["level"] = str(number)
        # Only a single text field accepts a bare reply. Choice/number fields use strict parsing.
        text_fields = (
            [f.key for f in pending.fields if f.input_type == "text" and f.key not in supplied] if pending else []
        )
        if len(text_fields) == 1 and not supplied and len(text) <= 120:
            supplied[text_fields[0]] = text
    else:
        state.original, state.pending, state.intent = text, None, new_intent
        state.lang = lang
        # Slots belong to an active task, not a verified account-wide player profile.
        # An explicit new task starts with its own details; slot-only replies keep the pending task.
        state.slots = {}
    # An informational question about Samurai/Moonveil is not confirmation of the player's class/gear.
    explicit_profile = re.search(r"(?:^|\n)(?:level|starting_class|goal|weapon|current_location|objective)\s*=", text)
    if continuing or new_intent or explicit_profile:
        state.slots.update(supplied)
    state.updated = now
    if not state.intent:
        return Decision(state, text)
    if state.intent == "build":
        required = ["weapon", "goal"]
        if re.search(r"phan bo|chia chi so|stat allocation|stat spread|exact stats|cong diem", folded(state.original)):
            required = ["level", "starting_class", "weapon", "goal"]
    else:
        required = ["current_location", "objective"]
        # A named quest milestone can be looked up directly. Do not demand a full player profile
        # before retrieving its next step; retrieval/generation still checks the actual conditions.
        if re.search(
            r"Ranni|Fingerslayer Blade|Dark Moon Ring|Astel|Morgott|Fire Giant|Maliketh", state.original, re.I
        ):
            required = []
    missing = [key for key in required if not state.slots.get(key)]
    if missing:
        fields = []
        for key in missing[:2]:
            options = ["PvE", "PvP"] if key == "goal" else list(CLASSES) if key == "starting_class" else []
            fields.append(
                ClarificationField(
                    key=key,
                    label=LABELS[key][lang == "en"],
                    input_type="number" if key == "level" else "choice" if options else "text",
                    options=options,
                )
            )
        question = " ".join(f.label for f in fields)
        clarification = Clarification(
            id=uuid4(), question=question, fields=fields, expires_at=datetime.fromtimestamp(now + TTL, UTC).isoformat()
        )
        state.pending = clarification
        return Decision(state, text, clarification, question, "pending")
    state.pending = None
    details = "; ".join(f"{key}={value}" for key, value in state.slots.items())
    # A correction must replace stale literals in the working question too; appending a new
    # slot to "level 100 ... PvE" would otherwise ask the rewriter to preserve both old and new.
    question = state.original
    if continuing:
        if level := state.slots.get("level"):
            question = re.sub(
                r"\b(?:level|lv|cấp|cap)\s*[:=]?\s*\d{1,3}\b", lambda _: "level " + level, question, flags=re.I
            )
        if goal := state.slots.get("goal"):
            question = re.sub(r"\bPv[EP]\b", lambda _: goal, question, flags=re.I)
        original_slots = extract(state.original)
        for key in ("weapon", "starting_class", "current_location", "objective"):
            old, new = original_slots.get(key), state.slots.get(key)
            if old and new and old != new:
                question = re.sub(re.escape(old), lambda _, value=new: value, question, flags=re.I)
    query = question + "\nplayer-confirmed details (preferences, not factual evidence): " + details
    return Decision(state, query, status="resumed" if continuing else "ready")
