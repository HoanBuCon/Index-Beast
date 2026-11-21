"""Quy tắc level có nguồn mà Agent luôn có thể trích dẫn (tổng 8 chỉ số = level + 79).

Trước 24/11 nằm trong gói `knowledge/gameplay.json` cùng các nhóm alias của luồng gameplay cũ; runtime chỉ còn dùng
quy tắc này nên giữ nó ở đây, cùng ID và nội dung để trace cũ vẫn khớp.
"""

import copy

from core.types import Hit

LEVEL_RULE_ID = "curated:ba65849e047b19b9d362892b846d96d8f2a3b2aff567957125575b34d23649cb"
_LEVEL_RULE = {
    "text": (
        "A character's level equals the sum of the eight primary attributes minus 79. Thus the target attribute sum "
        "is level + 79. Vigor affects HP; Mind affects FP; Endurance affects stamina and equip load. Arithmetic does "
        "not establish optimality."
    ),
    "title": "Attribute point accounting",
    "section": "Verified fields / arithmetic constraints",
    "url": "https://eldenring.wikidot.com/stats",
    "source": "curated_gameplay_snapshot",
    "source_type": "wiki_prose",
    "source_type_evidence": "manual_field_check_2026-11-05_not_cross_review",
    "game_scope": "elden_ring",
    "release_scope": "base",
    "patch_version": "unknown",
    "lang": "en",
    "review_status": "pending",
    "rule_kind": "level_rule",
    "image_ids": [],
}


def level_rule() -> Hit:
    """Quy tắc tính level đã tuyển chọn, ở dạng hit có thể trích dẫn (bản sao mới mỗi lượt)."""
    return Hit(LEVEL_RULE_ID, 0.0, copy.deepcopy(_LEVEL_RULE))
