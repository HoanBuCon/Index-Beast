"""Làm sạch Markdown thận trọng và tách khối theo thứ tự trang. Không thêm dữ kiện gameplay, không xếp hạng."""

import re

IMAGE = re.compile(r"!\[[^\]\n]*\]\([^\n]*?\)")
LINK = re.compile(r"\[([^\]\n]*)\]\([^\s)]+(?:\s+\"[^\"]*\")?\)")
REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*https?://.*$", re.M)
NOISE = re.compile(
    r"^(?:sign in(?: now)?|log in|navigation|main page|recent changes|random page|"
    r"help about mediawiki|visit the main page|advertisement|cookie settings|"
    r"privacy policy|terms of service|follow us|share this article)\s*$",
    re.I,
)


def clean_markdown(raw: str) -> tuple[str, dict]:
    stats = {"image_markup_removed": 0, "link_markup_removed": 0, "navigation_lines_removed": 0}
    # Tavily trả về Markdown, không phải bản đã escape để hiển thị đôi khi được dán từ UI.
    # Không unescape text gameplay tùy ý hay parse JSON bên trong nội dung nguồn.
    text, stats["image_markup_removed"] = IMAGE.subn("", raw)
    text, stats["link_markup_removed"] = LINK.subn(lambda match: match[1], text)
    text = REFERENCE.sub("", text)
    inline_heading = re.search(r"(?<!\S)#\s+\S", text)
    if inline_heading is not None and re.search(
        r"navigation|sign in|recent changes|fextralife|mediawiki", text[: inline_heading.start()], re.I
    ):
        stats["navigation_lines_removed"] += len(text[: inline_heading.start()].splitlines())
        text = text[inline_heading.start() :]
    lines = text.splitlines()
    # Thanh điều hướng đã biết của giao diện wiki nằm trước H1 đầu tiên của bài, có dấu mốc rõ ràng.
    first_heading = next((i for i, line in enumerate(lines) if re.match(r"^#\s+\S", line)), None)
    if first_heading is not None and any(
        re.search(r"navigation|sign in|recent changes|fextralife|mediawiki", line, re.I)
        for line in lines[:first_heading]
    ):
        stats["navigation_lines_removed"] += first_heading
        lines = lines[first_heading:]
    kept = []
    for line in lines:
        visible = re.sub(r"^[\s*\-#>]+", "", line).strip()
        if NOISE.fullmatch(visible):
            stats["navigation_lines_removed"] += 1
            continue
        if visible or (kept and kept[-1]):
            kept.append(line.rstrip())
    return "\n".join(kept).strip(), stats


def select_excerpts(text: str, *, limit: int = 6) -> tuple[list[str], int]:
    """Tách trang thành các khối theo thứ tự trang; không xếp hạng (22/11: Agent chọn mở khối nào).

    Khối giữ tiêu đề mục và được gom tới khoảng 3.500 ký tự mà không đổi thứ tự, để các bước quest
    và bảng còn nguyên. `limit` là ngân sách kích thước mỗi trang (các khối đầu trang), không phải khẳng định
    về độ liên quan. Trả về các khối và số khối quá cỡ bị loại thay vì bị cắt lặng lẽ.
    """
    blocks, heading, excluded, current = [], "", 0, ""
    for raw in re.split(r"\n\s*\n", text):
        lines = raw.splitlines()
        # Giữ ngữ cảnh mục gắn với khối nội dung, không chép điều hướng không liên quan.
        headings = [line for line in lines if re.match(r"^#{1,6}\s+\S", line)]
        if headings:
            heading = headings[-1]
        block = raw.strip()
        if not block or len(block) < 8:
            continue
        # Khối mở đầu một chunk gom mới mang theo tiêu đề mục; bên trong chunk thì tiêu đề đã có sẵn.
        headed = heading + "\n\n" + block if heading and heading not in block else block
        if len(headed) > 3500:
            excluded += 1
            continue  # Không lặng lẽ cắt bảng hay điều kiện gameplay.
        if current and len(current) + len(block) + 2 > 3500:
            blocks.append(current)
            current = ""
        current = (current + "\n\n" + (block if current and heading in current else headed)).strip()
    if current:
        blocks.append(current)
    unique = list(dict.fromkeys(blocks))
    return unique[:limit], excluded
