"""Chỉ khớp text để kiểm nguồn gốc: chữ người dùng đưa có xuất hiện trong một đoạn text không?

Không danh sách từ khóa, từ điển thực thể, rule intent hay NER. Quyết định ngữ nghĩa thuộc về Agent.
"""

import re
import unicodedata


def _normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().replace("’", "'")


def contains_text(text: str, surface: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_normalized(surface)) + r"(?!\w)", _normalized(text)) is not None


def name_key(text: str) -> str:
    return " ".join(re.sub(r"(?<=[^\W\d_]),\s*(?=[^\W\d_])", " ", _normalized(text)).split())


def contains_name(text: str, name: str) -> bool:
    key = name_key(name)
    return bool(key and re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", name_key(text)))
