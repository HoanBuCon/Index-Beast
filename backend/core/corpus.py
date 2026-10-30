"""Shared corpus admission, language selection and query filters. Admission is not lore verification."""

from dataclasses import dataclass
from typing import Literal

from qdrant_client import models

SOURCE_TYPES = ("in_game_text", "wiki_prose", "speculation")
# Only scope-only reasons from the former base-game filter may be reconsidered.
LEGACY_RELEASE_REASONS = frozenset(
    {
        "explicit_dlc_lead_definition",
        "mixed_or_dlc_page_context",
        "dlc_or_mixed_marker_in_content",
        "entity_from_explicit_dlc_or_mixed_sample",
        "no_positive_scope_evidence",
        "no_positive_base_evidence",
    }
)
ADMISSION_KEY = "indexbeast_admission"


def parse_languages(value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    items = value.split(",") if isinstance(value, str) else value
    if not items or any(not isinstance(x, str) or not x.strip() for x in items):
        raise ValueError("Specify at least one language, for example en or en,ja")
    return tuple(dict.fromkeys(x.strip() for x in items))


@dataclass(frozen=True)
class CorpusPolicy:
    # Low-level callers keep the old strict policy unless the application opts in.
    mode: Literal["reviewed", "pilot"] = "reviewed"
    languages: tuple[str, ...] = ("en", "vi", "ja")

    def __post_init__(self):
        if self.mode not in {"reviewed", "pilot"}:
            raise ValueError("Unknown corpus policy")
        object.__setattr__(self, "languages", parse_languages(self.languages))

    @classmethod
    def from_settings(cls, settings):
        return cls(settings.rag_corpus_policy, tuple(settings.rag_languages))

    @property
    def scopes(self) -> tuple[str, ...]:
        return ("base", "elden_ring") if self.mode == "pilot" else ("base",)

    @property
    def stamp(self) -> str:
        return f"{self.mode}-v1"

    def exclusion_reason(self, payload: dict, *, spoilers: bool = True) -> str | None:
        for key in (
            "game_scope",
            "source_type",
            "lang",
            "review_status",
            "scope_status",
            "scope_reason",
            "reason",
            "decision",
        ):
            if payload.get(key) is not None and not isinstance(payload[key], str):
                return "invalid_policy_metadata"
        if payload.get("game_scope") not in self.scopes:
            return "game_not_admitted"
        if self.mode == "reviewed":
            if payload.get("review_status") != "approved" or payload.get("scope_status") in {"review", "excluded"}:
                return "scope_or_review_not_approved"
        else:
            if payload.get("review_status") in {"rejected", "excluded"}:
                return "review_rejected"
            # A structural/manual processing decision is distinct from a legacy scope decision.
            if payload.get("decision") in {"review", "excluded"} or payload.get("chunk_eligible") is False:
                return "processing_not_eligible"
            if payload.get("scope_status") in {"review", "excluded"}:
                reason = payload.get("scope_reason") or payload.get("reason") or ""
                legacy = reason in LEGACY_RELEASE_REASONS or reason.startswith("explicit_dlc_heading:")
                if not legacy:
                    return "unresolved_scope_or_structure"
        if payload.get("source_type") not in SOURCE_TYPES:
            return "source_type_not_supported"
        if payload.get("lang") not in self.languages:
            return "language_not_selected"
        level = payload.get("spoiler_level")
        if not spoilers and (type(level) not in (int, float) or level != 0):
            return "spoiler_safety_unknown_or_spoiler"
        return None

    def index_payload(self, payload: dict) -> dict:
        reason = self.exclusion_reason(payload)
        if reason:
            raise ValueError(f"Corpus admission failed: {reason}")
        if ADMISSION_KEY in payload:
            raise ValueError(f"Reserved metadata collision: {ADMISSION_KEY}")
        # Operational provenance only. Does not overwrite review_status or source metadata.
        return {**payload, ADMISSION_KEY: self.stamp}

    def query_filter(self, *, spoilers: bool = True) -> models.Filter:
        scope = models.MatchValue(value="base") if self.mode == "reviewed" else models.MatchAny(any=list(self.scopes))
        must = [models.FieldCondition(key="game_scope", match=scope)]
        if self.mode == "reviewed":
            must.append(models.FieldCondition(key="review_status", match=models.MatchValue(value="approved")))
        else:
            # Only points admitted through this policy/version participate in pilot retrieval.
            must.append(models.FieldCondition(key=ADMISSION_KEY, match=models.MatchValue(value=self.stamp)))
        must.extend(
            [
                models.FieldCondition(key="lang", match=models.MatchAny(any=list(self.languages))),
                models.FieldCondition(key="source_type", match=models.MatchAny(any=list(SOURCE_TYPES))),
            ]
        )
        if not spoilers:
            must.append(models.FieldCondition(key="spoiler_level", range=models.Range(gte=0, lte=0)))
        return models.Filter(must=must)
