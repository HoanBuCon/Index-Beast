"""Chỉ khớp text để kiểm nguồn gốc: chữ/số người dùng đưa có xuất hiện trong một đoạn text không?

Không danh sách từ khóa, từ điển thực thể, rule intent hay NER. Quyết định ngữ nghĩa thuộc về Agent.
"""

import re
import unicodedata
from collections import Counter


def folded(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    return " ".join(re.sub(r"[^\w\s]", " ", "".join(c for c in text if not unicodedata.combining(c))).split())


_NUMBER_TOKEN = r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)"


def numbers_in(text: str) -> list[str]:
    """Các số đúng như được viết (level, chỉ số, nâng cấp, patch); không suy ra đơn vị hay ý nghĩa."""
    return re.findall(_NUMBER_TOKEN, text)


def preserves_numbers(question: str, query: str) -> bool:
    """Mọi số trong text thứ nhất đều còn trong text thứ hai."""
    expected = Counter(numbers_in(question))
    actual = Counter(numbers_in(query))
    return all(actual[number] >= count for number, count in expected.items())


def _normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().replace("’", "'")


def contains_text(text: str, surface: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_normalized(surface)) + r"(?!\w)", _normalized(text)) is not None


def name_key(text: str) -> str:
    return " ".join(re.sub(r"(?<=[^\W\d_]),\s*(?=[^\W\d_])", " ", _normalized(text)).split())


def contains_name(text: str, name: str) -> bool:
    key = name_key(name)
    return bool(key and re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", name_key(text)))
