"""Đồng bộ `.env` với `.env.example` mà không sửa giá trị bạn đã điền: `make env`.

- Chưa có `.env`: tạo từ `.env.example`.
- `.env` thiếu biến so với `.env.example`: thêm vào cuối file (kèm chú thích mẫu), giữ nguyên mọi dòng cũ.
- `.env` thừa biến so với `.env.example`: in tên biến và hỏi xóa hay giữ (mặc định giữ). Tên biến chỉ được in ra,
  giá trị (có thể là secret) không bao giờ được in.

Biến chỉ có ở dạng chú thích trong `.env.example` (`# ADMIN_TOKEN=change-me`) là biến tùy chọn: không tự thêm và
không bị coi là thừa nếu bạn đã bật nó trong `.env`.

Chạy từ gốc repo:
  make env                              # đồng bộ, hỏi khi có biến thừa
  make env ARGS="--dry-run"             # chỉ báo cáo, không ghi file
  make env ARGS="--keep-extra"          # không hỏi, giữ biến thừa (dùng khi không có bàn phím)
  make env ARGS="--remove-extra"        # không hỏi, xóa biến thừa (tự lưu .env.bak trước)

Chỉ dùng thư viện chuẩn nên chạy được bằng mọi Python 3.

Phụ trách: TV1 · [S3] Script đồng bộ .env
"""

import argparse
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
COMMENTED_ASSIGNMENT = re.compile(r"^\s*#\s*([A-Z][A-Z0-9_]*)=")
PLACEHOLDER = "change-me"


@dataclass
class Example:
    lines: dict[str, str] = field(default_factory=dict)  # tên biến -> dòng KEY=giá-trị mẫu
    comments: dict[str, list[str]] = field(default_factory=dict)  # tên biến -> chú thích liền phía trên
    optional: set[str] = field(default_factory=set)  # biến chỉ có ở dạng chú thích


def _eol(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def parse_example(text: str) -> Example:
    example = Example()
    lines = text.lstrip("﻿").splitlines()
    for index, line in enumerate(lines):
        if match := ASSIGNMENT.match(line):
            key = match.group(1)
            if key in example.lines:
                continue
            example.lines[key] = line.strip()
            above: list[str] = []
            for previous in reversed(lines[:index]):
                stripped = previous.strip()
                if not stripped.startswith("#") or COMMENTED_ASSIGNMENT.match(previous):
                    break
                above.append(stripped)
            example.comments[key] = above[::-1]
        elif match := COMMENTED_ASSIGNMENT.match(line):
            example.optional.add(match.group(1))
    example.optional -= example.lines.keys()
    return example


def env_keys(text: str) -> dict[str, list[int]]:
    """Tên biến đang bật trong .env -> số thứ tự các dòng khai báo nó."""
    found: dict[str, list[int]] = {}
    for index, line in enumerate(text.lstrip("﻿").splitlines()):
        if match := ASSIGNMENT.match(line):
            found.setdefault(match.group(1), []).append(index)
    return found


def missing_keys(example: Example, present: dict[str, list[int]]) -> list[str]:
    return [key for key in example.lines if key not in present]


def extra_keys(example: Example, present: dict[str, list[int]]) -> list[str]:
    return [key for key in present if key not in example.lines and key not in example.optional]


def append_missing(text: str, example: Example, keys: list[str], today: date) -> str:
    eol = _eol(text)
    block = ["", f"# ---------- Thêm tự động bởi `make env` ({today.isoformat()}) ----------"]
    for key in keys:
        block += [*example.comments.get(key, []), example.lines[key]]
    head = text if not text or text.endswith(("\n", "\r")) else text + eol
    return head + eol.join(block) + eol


def remove_keys(text: str, present: dict[str, list[int]], keys: set[str]) -> str:
    drop = {index for key in keys for index in present[key]}
    lines = text.splitlines(keepends=True)
    return "".join(line for index, line in enumerate(lines) if index not in drop)


def needs_value(example: Example, keys: list[str]) -> list[str]:
    """Biến vừa thêm mà giá trị mẫu để trống hoặc là "change-me": người dùng phải tự điền."""
    pending = []
    for key in keys:
        value = ASSIGNMENT.match(example.lines[key]).group(2).strip().strip("\"'")
        if value in ("", PLACEHOLDER):
            pending.append(key)
    return pending


def choose_removals(extras: list[str], mode: str | None) -> set[str]:
    if mode == "keep":
        return set()
    if mode == "remove":
        return set(extras)
    removals: set[str] = set()
    decision = None  # "a" = xóa hết còn lại, "k" = giữ hết còn lại
    for key in extras:
        if decision is None:
            try:
                answer = input(f"  Xóa {key}? [y] xóa / [N] giữ / [a] xóa hết còn lại / [k] giữ hết còn lại: ")
            except EOFError:
                print("  (không đọc được câu trả lời: giữ các biến còn lại)")
                break
            answer = answer.strip().lower()
            if answer in ("a", "k"):
                decision = answer
            elif answer in ("y", "yes"):
                removals.add(key)
                continue
        if decision == "a":
            removals.add(key)
    return removals


def write_text(path: Path, text: str) -> None:
    """Ghi qua file tạm rồi thay thế: .env không bao giờ bị ghi dở khi lỗi giữa chừng."""
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def read_text(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read()


def sync(env: Path, example_path: Path, *, mode: str | None = None, dry_run: bool = False) -> int:
    example_text = read_text(example_path)
    example = parse_example(example_text)
    prefix = "[dry-run] " if dry_run else ""

    if not env.exists():
        print(f"{prefix}Chưa có {env.name}: tạo từ {example_path.name} ({len(example.lines)} biến).")
        if not dry_run:
            write_text(env, example_text)
        pending = needs_value(example, list(example.lines))
        if pending:
            print(f"Cần điền giá trị: {', '.join(pending)}")
        return 0

    text = read_text(env)
    present = env_keys(text)
    missing = missing_keys(example, present)
    extras = extra_keys(example, present)
    changed = False

    if missing:
        print(f"{prefix}Thêm {len(missing)} biến còn thiếu vào cuối {env.name} (không đụng các dòng cũ):")
        for key in missing:
            print(f"  + {key}")
        text = append_missing(text, example, missing, date.today())
        changed = True
        if pending := needs_value(example, missing):
            print(f"Cần điền giá trị cho: {', '.join(pending)}")
    else:
        print(f"{env.name} đã có đủ biến của {example_path.name}.")

    if extras:
        print(f"\n{len(extras)} biến có trong {env.name} nhưng không có trong {example_path.name}:")
        for key in extras:
            print(f"  ? {key}")
        if dry_run:
            print("[dry-run] Sẽ hỏi xóa hay giữ từng biến; chưa xóa gì.")
        else:
            removals = choose_removals(extras, mode)
            if removals:
                backup = env.with_name(env.name + ".bak")
                write_text(backup, read_text(env))
                text = remove_keys(text, env_keys(text), removals)
                changed = True
                print(f"Đã xóa: {', '.join(sorted(removals))} (bản cũ lưu ở {backup.name})")
            kept = [key for key in extras if key not in removals]
            if kept:
                print(f"Giữ lại: {', '.join(kept)}")

    if changed and not dry_run:
        write_text(env, text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env", help="file .env cần cập nhật")
    parser.add_argument("--example", type=Path, default=REPO_ROOT / ".env.example", help="file mẫu")
    parser.add_argument("--dry-run", action="store_true", help="chỉ báo cáo, không ghi file")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--keep-extra", dest="mode", action="store_const", const="keep", help="giữ biến thừa, không hỏi")
    group.add_argument(
        "--remove-extra", dest="mode", action="store_const", const="remove", help="xóa biến thừa, không hỏi"
    )
    args = parser.parse_args(argv)
    if not args.example.is_file():
        print(f"Không thấy {args.example}", file=sys.stderr)
        return 1
    return sync(args.env, args.example, mode=args.mode, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
