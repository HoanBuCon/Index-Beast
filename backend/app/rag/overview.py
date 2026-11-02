"""Conservative overview routing and metadata preference; no factual taxonomy or model calls."""

import re
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from itertools import zip_longest

from app.rag.rewrite import protected_names
from core.types import Hit


def folded(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    return " ".join(re.sub(r"[^\w\s]", " ", "".join(c for c in text if not unicodedata.combining(c))).split())


@dataclass(frozen=True)
class Overview:
    topic: str
    keywords: tuple[str, ...]
    titles: tuple[str, ...]
    focus: str


TOPICS = (
    Overview(
        "lore",
        ("cot truyen", "the gioi", "lore", "story", "world"),
        ("Elden Ring", "Story", "The Lands Between"),
        "Elden Ring lore story world overview",
    ),
    Overview(
        "bosses",
        ("boss", "bosses", "trum"),
        ("Bosses",),
        "Elden Ring bosses overview lists categories mandatory optional remembrance",
    ),
    Overview(
        "weapons",
        ("vu khi", "weapon", "weapons"),
        ("Weapons", "Weapon Types"),
        "Elden Ring weapons overview weapon types categories",
    ),
    Overview(
        "armor",
        ("giap", "armor", "armour", "armors"),
        ("Armor", "Armors"),
        "Elden Ring armor overview equipment categories",
    ),
    Overview(
        "characters",
        ("nhan vat", "npc", "npcs", "characters"),
        ("Characters", "NPCs"),
        "Elden Ring characters NPCs overview list",
    ),
    Overview(
        "locations",
        ("dia diem", "khu vuc", "vung dat", "locations", "regions", "areas"),
        ("Locations",),
        "Elden Ring locations regions overview",
    ),
    Overview(
        "quests",
        ("nhiem vu", "quest", "quests", "questlines"),
        ("Quests", "NPCs"),
        "Elden Ring quests questlines overview NPC quests",
    ),
    Overview(
        "builds",
        ("build", "builds", "loi choi"),
        ("Builds", "Classes"),
        "Elden Ring builds playstyles overview mechanics equipment requirements",
    ),
)
GAME = Overview("game", ("game", "tro choi"), ("Elden Ring",), "Elden Ring overview world combat progression")
_BROAD = re.compile(
    r"\b(cac|nhung|tong quan|liet ke|ke ten|phan loai|nhom|bao nhieu|overview|list|types|kinds|"
    r"categories|all|which|what|introduce|introduction|explain|different|main|bosses|weapons|characters|"
    r"npcs|quests|builds|regions|locations|armors)\b"
)
_GENERAL_NAMES = {
    "all",
    "list",
    "types",
    "kinds",
    "categories",
    "overview",
    "different",
    "main",
    "show",
    "give",
    "introduce",
    "introduction",
    "elden",
    "ring",
    "shadow",
    "of",
    "the",
    "erdtree",
    "dlc",
    "sote",
    "base",
    "game",
    "between",
    "lands",
    "boss",
    "bosses",
    "weapons",
    "weapon",
    "armor",
    "armour",
    "armors",
    "npcs",
    "npc",
    "characters",
    "quests",
    "quest",
    "locations",
    "regions",
    "areas",
    "builds",
    "build",
    "pve",
    "pvp",
    "lore",
    "story",
    "world",
    "cac",
    "nhung",
    "tong",
    "quan",
    "liet",
    "ke",
    "ten",
    "loai",
    "nhan",
    "vat",
    "vu",
    "khi",
    "dia",
    "diem",
    "khu",
    "vuc",
    "giap",
    "nhiem",
    "gioi",
    "thieu",
}


def detect_overview(question: str) -> Overview | None:
    text = folded(question)
    if any(name.casefold() not in _GENERAL_NAMES for name in protected_names(question)):
        return None  # A named target/relationship continues through the entity pipeline.
    matches = [
        topic for topic in TOPICS if any(re.search(r"\b" + re.escape(word) + r"\b", text) for word in topic.keywords)
    ]
    if matches:
        topic = (
            matches[0]
            if len(matches) == 1
            else Overview(
                "+".join(item.topic for item in matches),
                tuple(word for item in matches for word in item.keywords),
                tuple(dict.fromkeys(title for item in matches for title in item.titles)),
                "Elden Ring overview lists categories of " + ", ".join(item.topic for item in matches),
            )
        )
        bare = any(
            text == word
            or text
            in {
                f"{word} trong elden ring",
                f"{word} in elden ring",
                f"elden ring {word}",
                f"{word} elden ring",
                f"{word} of elden ring",
            }
            for word in topic.keywords
        )
        return topic if bare or _BROAD.search(text) else None
    if (
        not matches
        and "elden ring" in text
        and re.search(
            r"tong quan|gioi thieu|overview|introduce|introduction|"
            r"elden ring la (?:game|tro choi|gi)|what is elden ring",
            text,
        )
    ):
        return GAME
    return None


def overview_queries(queries: list[tuple[str, str]], overview: Overview) -> list[tuple[str, str]]:
    # Retain every original constraint. In dual mode retain the original query too; never add a third query.
    kind, primary = queries[0]
    focused = ("overview", primary + "\nSearch focus: " + overview.focus)
    return [focused, queries[1]] if len(queries) > 1 else [(kind, primary), focused]


def prefer_overview(hits: list[Hit], overview: Overview) -> list[Hit]:
    """Stable metadata preference, not a semantic reranker or relevance certification.

    Prefer matching overview titles. Within each tier interleave source/section groups
    rather than spending the context on repeated segments of the same section.
    """
    titles = {folded(title) for title in overview.titles}
    tiers = [OrderedDict(), OrderedDict()]
    for hit in hits:
        payload = hit.payload
        tier = 0 if folded(str(payload.get("title", ""))) in titles else 1
        key = (payload.get("source_id") or payload.get("url") or hit.id, payload.get("section"))
        tiers[tier].setdefault(key, []).append(hit)
    ordered = []
    for index, tier in enumerate(tiers):
        groups = list(tier.items())
        if index == 0:
            groups.sort(
                key=lambda item: (
                    not bool(
                        re.match(r"^(introduction|overview|list|types|categories)\b", folded(str(item[0][1] or "")))
                    )
                )
            )
        ordered.extend(
            hit for round_ in zip_longest(*(rows for _, rows in groups)) for hit in round_ if hit is not None
        )
    return ordered


def no_overview_evidence(overview: Overview, lang: str) -> str:
    if lang == "vi":
        return (
            "Mình chưa lấy được nguồn phù hợp để tổng hợp câu hỏi này. "
            "Bạn muốn xem các nhóm chính hay một vài ví dụ để bắt đầu?"
        )
    return (
        "I haven't retrieved suitable evidence for this overview. "
        "Would you prefer the main categories or a few examples to start with?"
    )
