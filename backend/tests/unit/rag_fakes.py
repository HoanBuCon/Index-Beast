"""Hit giả dùng chung cho test RAG offline; không phải bằng chứng về chất lượng retrieval."""

from core.types import Hit


def hit(key="a", **payload):
    return Hit(
        key,
        0.1,
        {
            "text": f"Evidence for {key}",
            "title": "Ranni the Witch",
            "url": "https://eldenring.wiki.gg/wiki/Ranni_the_Witch",
            "source": "wikigg",
            "source_id": "ranni",
            "revision_id": "v1",
            "section": "Lore",
            "game_scope": "base",
            "release_scope": "unknown",
            "review_status": "approved",
            "source_type": "wiki_prose",
            "lang": "en",
            **payload,
        },
    )
