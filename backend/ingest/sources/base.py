"""Source protocol; only wiki.gg is implemented for Sprint 1."""

from typing import Protocol


class Source(Protocol):
    name: str

    def list_category(self, category: str) -> list[dict]: ...
    def fetch(self, page: dict) -> dict: ...
