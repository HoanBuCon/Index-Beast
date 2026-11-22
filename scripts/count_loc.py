#!/usr/bin/env python3
"""Script đếm số dòng mã nguồn (LOC) của dự án.

Tự động lọc bỏ:
- Thư viện & môi trường ảo (.venv, node_modules, site-packages,...)
- Cache & build artifacts (__pycache__, dist, build, .pytest_cache, .ruff_cache,...)
- File phi-code (hình ảnh, video, âm thanh, binary, models, tài liệu .md, .txt,...)
- File dữ liệu & log (.log, .parquet, .sqlite, .db, .jsonl,...)
- File sinh tự động / lockfile (package-lock.json, pnpm-lock.yaml,...)

Chỉ sử dụng thư viện chuẩn của Python (Python 3.8+). Không phụ thuộc thư viện ngoài.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# Các thư mục luôn bỏ qua
DEFAULT_IGNORE_DIRS: set[str] = {
    # Dependency & Virtual Environments
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    "site-packages",
    ".pnpm-store",
    # Build & Dist
    "dist",
    "build",
    "out",
    ".next",
    ".output",
    "coverage",
    ".nyc_output",
    "target",
    "bin",
    "obj",
    # Caches & Tooling
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cache",
    # VCS & IDE
    ".git",
    ".github",
    ".vscode",
    ".idea",
    ".claude",
    ".gemini",
    # Data & Model assets
    "data",
    "models",
    "elden-ring-data",
    "logs",
    "tmp",
    "temp",
    "brain",
    "assets",
}

# Các file luôn bỏ qua
DEFAULT_IGNORE_FILES: set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "uv.lock",
}

# Định nghĩa ngôn ngữ theo đuôi file
# Cấu trúc: name -> (extensions, single_line_comments, block_comment_delimiters)
LANGUAGE_CONFIG = {
    "Python": {
        "exts": {".py", ".pyw"},
        "single": ["#"],
        "block": [('"""', '"""'), ("'''", "'''")],
    },
    "TypeScript": {
        "exts": {".ts"},
        "single": ["//"],
        "block": [("/*", "*/")],
    },
    "TSX (React)": {
        "exts": {".tsx"},
        "single": ["//"],
        "block": [("/*", "*/")],
    },
    "JavaScript": {
        "exts": {".js", ".mjs", ".cjs"},
        "single": ["//"],
        "block": [("/*", "*/")],
    },
    "JSX (React)": {
        "exts": {".jsx"},
        "single": ["//"],
        "block": [("/*", "*/")],
    },
    "CSS / SCSS": {
        "exts": {".css", ".scss", ".sass", ".less"},
        "single": ["//"],
        "block": [("/*", "*/")],
    },
    "HTML / Vue": {
        "exts": {".html", ".htm", ".vue", ".svelte"},
        "single": [],
        "block": [("<!--", "-->")],
    },
    "SQL": {
        "exts": {".sql"},
        "single": ["--"],
        "block": [("/*", "*/")],
    },
    "Shell / Bash": {
        "exts": {".sh", ".bash", ".zsh"},
        "single": ["#"],
        "block": [],
    },
    "PowerShell": {
        "exts": {".ps1", ".psm1", ".psd1"},
        "single": ["#"],
        "block": [("<#", "#>")],
    },
    "Batch": {
        "exts": {".bat", ".cmd"},
        "single": ["REM", "::"],
        "block": [],
    },
    "Makefile": {
        "names": {"Makefile", "makefile", "GNUMakefile"},
        "exts": {".mk"},
        "single": ["#"],
        "block": [],
    },
    "Docker": {
        "names": {"Dockerfile"},
        "exts": {".dockerfile"},
        "single": ["#"],
        "block": [],
    },
}

# Nhóm file cấu hình (tùy chọn đếm riêng nếu bật --include-config)
CONFIG_LANGUAGE_CONFIG = {
    "JSON": {
        "exts": {".json"},
        "single": ["//"],  # JSONC hỗ trợ //
        "block": [("/*", "*/")],
    },
    "YAML": {
        "exts": {".yaml", ".yml"},
        "single": ["#"],
        "block": [],
    },
    "TOML": {
        "exts": {".toml"},
        "single": ["#"],
        "block": [],
    },
}


@dataclass
class FileStats:
    path: str
    relative_path: str
    language: str
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    code_lines: int = 0
    module: str = "root"


def identify_language(file_path: Path, include_config: bool = False) -> tuple[str, dict] | None:
    """Xác định ngôn ngữ dựa trên đuôi file hoặc tên file."""
    name = file_path.name
    suffix = file_path.suffix.lower()

    # Bỏ qua các file minified / bundle / sourcemap
    if name.endswith(".min.js") or name.endswith(".min.css") or name.endswith(".map"):
        return None

    # Tìm trong nhóm ngôn ngữ code
    for lang, cfg in LANGUAGE_CONFIG.items():
        if "names" in cfg and (name in cfg["names"] or name.startswith("Dockerfile.")):
            return lang, cfg
        if suffix in cfg.get("exts", set()):
            return lang, cfg

    # Nếu bật đếm file cấu hình
    if include_config:
        for lang, cfg in CONFIG_LANGUAGE_CONFIG.items():
            if suffix in cfg.get("exts", set()):
                return lang, cfg

    return None


def determine_module(rel_path: Path) -> str:
    """Xác định module/tiểu dự án (backend, web, bot, scripts, infra,...)."""
    parts = rel_path.parts
    if len(parts) > 1:
        return parts[0]
    return "root"


def count_lines_in_file(path: Path, lang_cfg: dict) -> tuple[int, int, int, int]:
    """Phân tích số dòng: Tổng, Trống, Chú thích, Mã nguồn thực tế."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return 0, 0, 0, 0

    total = len(lines)
    blank = 0
    comment = 0

    single_markers = lang_cfg.get("single", [])
    block_markers = lang_cfg.get("block", [])

    in_block_comment = False
    current_block_end = ""

    for line in lines:
        stripped = line.strip()

        # Dòng trống
        if not stripped:
            blank += 1
            continue

        # Đang nằm trong block comment
        if in_block_comment:
            comment += 1
            if current_block_end and current_block_end in stripped:
                in_block_comment = False
                current_block_end = ""
            continue

        # Kiểm tra bắt đầu block comment
        started_block = False
        for start_sym, end_sym in block_markers:
            if stripped.startswith(start_sym):
                comment += 1
                started_block = True
                # Nếu không kết thúc ngay trên cùng 1 dòng
                if end_sym not in stripped[len(start_sym) :]:
                    in_block_comment = True
                    current_block_end = end_sym
                break

        if started_block:
            continue

        # Kiểm tra single line comment
        is_single = False
        for marker in single_markers:
            if stripped.startswith(marker):
                comment += 1
                is_single = True
                break

        if is_single:
            continue

    code = total - blank - comment
    return total, blank, comment, code


def scan_directory(
    root_dir: Path,
    include_config: bool = False,
    extra_ignore_dirs: set[str] | None = None,
    filter_exts: set[str] | None = None,
) -> list[FileStats]:
    """Quét toàn bộ thư mục và tính thống kê cho từng file mã nguồn hợp lệ."""
    ignore_dirs = DEFAULT_IGNORE_DIRS.copy()
    if extra_ignore_dirs:
        ignore_dirs.update(extra_ignore_dirs)

    results: list[FileStats] = []

    for root, dirs, files in os.walk(root_dir):
        # Lọc các thư mục bị bỏ qua ngay tại chỗ để os.walk không duyệt sâu vào
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".git")]

        rel_root = Path(root).relative_to(root_dir)

        for filename in files:
            if filename in DEFAULT_IGNORE_FILES:
                continue

            file_path = Path(root) / filename
            rel_file_path = rel_root / filename

            # Lọc theo extension nếu người dùng chỉ định
            if filter_exts and file_path.suffix.lower() not in filter_exts:
                continue

            match = identify_language(file_path, include_config=include_config)
            if not match:
                continue

            lang, cfg = match
            total, blank, comment, code = count_lines_in_file(file_path, cfg)

            stats = FileStats(
                path=str(file_path),
                relative_path=str(rel_file_path).replace("\\", "/"),
                language=lang,
                total_lines=total,
                blank_lines=blank,
                comment_lines=comment,
                code_lines=code,
                module=determine_module(rel_file_path),
            )
            results.append(stats)

    return results


def print_table(headers: list[str], rows: list[list[str]], alignments: list[str]):
    """In bảng căn lề đẹp dạng CLI."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    # Đường phân cách
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_sep = "=" + "=".join("=" * (w + 2) for w in col_widths) + "="

    # Format header
    header_str = "|"
    for i, h in enumerate(headers):
        header_str += f" {h.center(col_widths[i])} |"

    print(sep)
    print(header_str)
    print(header_sep)

    for row in rows:
        row_str = "|"
        for i, val in enumerate(row):
            w = col_widths[i]
            align = alignments[i]
            sval = str(val)
            if align == "right":
                row_str += f" {sval.rjust(w)} |"
            elif align == "center":
                row_str += f" {sval.center(w)} |"
            else:
                row_str += f" {sval.ljust(w)} |"
        print(row_str)

    print(sep)


def display_results(stats: list[FileStats], by_module: bool = False, top_files: int = 0):
    """Hiển thị bảng tổng hợp ngôn ngữ, module và top file."""
    if not stats:
        print("Không tìm thấy file mã nguồn nào phù hợp.")
        return

    # 1. Thống kê theo ngôn ngữ
    lang_totals = defaultdict(lambda: {"files": 0, "total": 0, "blank": 0, "comment": 0, "code": 0})
    grand_total = {"files": 0, "total": 0, "blank": 0, "comment": 0, "code": 0}

    for s in stats:
        bucket = lang_totals[s.language]
        bucket["files"] += 1
        bucket["total"] += s.total_lines
        bucket["blank"] += s.blank_lines
        bucket["comment"] += s.comment_lines
        bucket["code"] += s.code_lines

        grand_total["files"] += 1
        grand_total["total"] += s.total_lines
        grand_total["blank"] += s.blank_lines
        grand_total["comment"] += s.comment_lines
        grand_total["code"] += s.code_lines

    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1]["code"], reverse=True)

    headers = ["Ngôn ngữ", "Số files", "Tổng dòng", "Dòng trống", "Chú thích", "Dòng Code (LOC)", "Tỉ lệ Code"]
    alignments = ["left", "right", "right", "right", "right", "right", "right"]

    rows = []
    for lang, d in sorted_langs:
        pct = (d["code"] / grand_total["code"] * 100) if grand_total["code"] > 0 else 0
        rows.append(
            [
                lang,
                f"{d['files']:,}",
                f"{d['total']:,}",
                f"{d['blank']:,}",
                f"{d['comment']:,}",
                f"{d['code']:,}",
                f"{pct:.1f}%",
            ]
        )

    # Dòng tổng cộng
    rows.append(
        [
            "TỔNG CỘNG",
            f"{grand_total['files']:,}",
            f"{grand_total['total']:,}",
            f"{grand_total['blank']:,}",
            f"{grand_total['comment']:,}",
            f"{grand_total['code']:,}",
            "100.0%",
        ]
    )

    print("\n=== THỐNG KÊ MÃ NGUỒN THEO NGÔN NGỮ ===")
    print_table(headers, rows, alignments)

    # 2. Thống kê theo Module / Tiểu dự án nếu có yêu cầu hoặc mặc định hiển thị
    if by_module:
        module_totals = defaultdict(lambda: {"files": 0, "total": 0, "blank": 0, "comment": 0, "code": 0})
        for s in stats:
            m = module_totals[s.module]
            m["files"] += 1
            m["total"] += s.total_lines
            m["blank"] += s.blank_lines
            m["comment"] += s.comment_lines
            m["code"] += s.code_lines

        sorted_mods = sorted(module_totals.items(), key=lambda x: x[1]["code"], reverse=True)
        mod_headers = [
            "Module / Thư mục",
            "Số files",
            "Tổng dòng",
            "Dòng trống",
            "Chú thích",
            "Dòng Code (LOC)",
            "Tỉ lệ Code",
        ]
        mod_rows = []
        for mod, d in sorted_mods:
            pct = (d["code"] / grand_total["code"] * 100) if grand_total["code"] > 0 else 0
            mod_rows.append(
                [
                    mod,
                    f"{d['files']:,}",
                    f"{d['total']:,}",
                    f"{d['blank']:,}",
                    f"{d['comment']:,}",
                    f"{d['code']:,}",
                    f"{pct:.1f}%",
                ]
            )

        print("\n=== THỐNG KÊ THEO MODULE / TIỂU DỰ ÁN ===")
        print_table(mod_headers, mod_rows, alignments)

    # 3. Top file lớn nhất nếu yêu cầu
    if top_files > 0:
        sorted_files = sorted(stats, key=lambda x: x.code_lines, reverse=True)[:top_files]
        f_headers = ["#", "File", "Ngôn ngữ", "Tổng", "Trống", "Chú thích", "Code (LOC)"]
        f_alignments = ["right", "left", "left", "right", "right", "right", "right"]
        f_rows = []
        for idx, f in enumerate(sorted_files, 1):
            f_rows.append(
                [
                    str(idx),
                    f.relative_path,
                    f.language,
                    f"{f.total_lines:,}",
                    f"{f.blank_lines:,}",
                    f"{f.comment_lines:,}",
                    f"{f.code_lines:,}",
                ]
            )
        print(f"\n=== TOP {top_files} FILE CÓ SỐ DÒNG CODE CAO NHẤT ===")
        print_table(f_headers, f_rows, f_alignments)


def main():
    # Đảm bảo in UTF-8 không bị lỗi trên Windows console
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Đếm số dòng mã nguồn (LOC) của dự án, bỏ qua thư viện và file phi-code."
    )
    parser.add_argument(
        "--path",
        "-p",
        type=str,
        default=".",
        help="Thư mục gốc cần đếm (mặc định: thư mục hiện tại)",
    )
    parser.add_argument(
        "--include-config",
        "-c",
        action="store_true",
        help="Đếm thêm cả các file cấu hình (JSON, YAML, TOML)",
    )
    parser.add_argument(
        "--by-module",
        "-m",
        action="store_true",
        help="Hiển thị bảng chi tiết theo từng module thư mục",
    )
    parser.add_argument(
        "--top",
        "-t",
        type=int,
        default=10,
        help="Hiển thị top N file dài nhất (mặc định: 10, đặt 0 để tắt)",
    )
    parser.add_argument(
        "--ext",
        type=str,
        default=None,
        help="Lọc chỉ đếm các đuôi file nhất định (vd: .py,.ts,.tsx)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả ra định dạng JSON (dùng cho CI/CD hoặc tích hợp tool)",
    )

    args = parser.parse_args()

    root_path = Path(args.path).resolve()
    if not root_path.exists():
        print(f"Lỗi: Thư mục không tồn tại: {root_path}", file=sys.stderr)
        sys.exit(1)

    filter_exts = None
    if args.ext:
        filter_exts = {
            e.strip().lower() if e.strip().startswith(".") else f".{e.strip().lower()}" for e in args.ext.split(",")
        }

    stats = scan_directory(
        root_dir=root_path,
        include_config=args.include_config,
        filter_exts=filter_exts,
    )

    if args.json:
        output_data = {
            "root": str(root_path),
            "files": [s.__dict__ for s in stats],
            "total_files": len(stats),
            "total_lines": sum(s.total_lines for s in stats),
            "total_blank": sum(s.blank_lines for s in stats),
            "total_comment": sum(s.comment_lines for s in stats),
            "total_code": sum(s.code_lines for s in stats),
        }
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    else:
        display_results(stats, by_module=args.by_module, top_files=args.top)


if __name__ == "__main__":
    main()
