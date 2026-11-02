"""Một lệnh cho từng bước dữ liệu: crawl → clean → chunk → load (PostgreSQL) → index (Qdrant).

Chỉ gọi lại các CLI có sẵn (ingest.crawl.full, ingest.transform.full, ingest.chunk.full, ingest.chunk.load_full,
ingest index) với giá trị mặc định an toàn; không thay logic pipeline.

Chạy từ backend/ (Windows dùng .venv\\Scripts\\python, Linux/Docker dùng python):
  python -m scripts.data_pipeline status                 # bản dữ liệu mới nhất của từng bước
  python -m scripts.data_pipeline crawl                  # resume lượt crawl mặc định (gọi mạng, rất lâu)
  python -m scripts.data_pipeline clean                  # clean toàn bộ raw → clean_runs/<mới>
  python -m scripts.data_pipeline chunk                  # chunk bản clean mới nhất → chunk_runs/<mới>
  python -m scripts.data_pipeline load                   # kiểm tra rồi nạp chunk mới nhất vào PostgreSQL
  python -m scripts.data_pipeline index --dry-run        # kiểm tra chunk trước khi index, không cần model
  python -m scripts.data_pipeline index --collection lore_chunks_v2   # embedding + ghi Qdrant (lâu, CPU)
  python -m scripts.data_pipeline all                    # clean → chunk → load → index --dry-run

Mặc định:
- Đầu ra clean/chunk luôn là thư mục MỚI có thời gian: không ghi đè bản đang phục vụ.
- "Mới nhất" = thư mục chạy toàn bộ (full) gần nhất có report.json hợp lệ; truyền --input để chọn bản khác.
- index thật bắt buộc --collection: index đè collection đang dùng không xóa point cũ.
- crawl không nằm trong `all` vì gọi mạng và mất hàng giờ.

Phụ trách: TV1 · [S3] Script pipeline dữ liệu (logic từng bước thuộc TV2/TV3)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
DEFAULT_CRAWL_RUN = "s2-full-20261028"
TOKENIZER_GLOB = "models/fastembed/models--intfloat--multilingual-e5-small/snapshots/*/tokenizer.json"


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M")


def report(directory: Path) -> dict | None:
    path = directory / "report.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def crawl_pages() -> int:
    """Số trang của lượt crawl mặc định (thành công + chỉ lỗi ảnh); dùng để bỏ qua các lượt thử --limit."""
    info = report(DATA / "crawl_runs" / DEFAULT_CRAWL_RUN) or {}
    return len(info.get("pages", [])) + len(info.get("errors", []))


def latest(kind: str, version_key: str, prefix: str, pages_key: str) -> Path | None:
    """Thư mục mới nhất trong data/<kind> đúng phiên bản pipeline full và có đủ số trang của lượt crawl."""
    root, expected = DATA / kind, crawl_pages()
    candidates = []
    for d in root.iterdir() if root.exists() else []:
        info = report(d) or {}
        full = expected and info.get("counts", {}).get(pages_key) == expected
        if d.is_dir() and str(info.get(version_key, "")).startswith(prefix) and full:
            candidates.append(d)
    return max(candidates, key=lambda d: (d / "report.json").stat().st_mtime, default=None)


def latest_clean() -> Path | None:
    return latest("clean_runs", "cleaning_version", "s2-full-clean", "pages_in")


def latest_chunk() -> Path | None:
    return latest("chunk_runs", "chunking_version", "s2-full-chunk", "pages")


def tokenizer() -> Path:
    found = sorted(BACKEND.glob(TOKENIZER_GLOB))
    if not found:
        sys.exit("Không tìm thấy tokenizer E5. Chạy index một lần để FastEmbed tải model, hoặc truyền --tokenizer.")
    return found[-1]


def need(path: Path | None, what: str) -> Path:
    if path is None or not path.exists():
        sys.exit(f"Không tìm thấy {what}. Chạy bước trước hoặc truyền --input.")
    return path


def run(module: str, *args: object) -> None:
    command = [sys.executable, "-X", "utf8", "-m", *module.split(), *map(str, args)]
    print("→", " ".join(command[3:]), flush=True)
    code = subprocess.call(command, cwd=BACKEND)
    if code:
        sys.exit(f"Bước '{module}' dừng với mã {code}.")


def crawl(a) -> None:
    run("ingest.crawl.full", "--run-id", a.run_id, *(["--no-media"] if a.no_media else []))


def clean(a) -> Path:
    source = need(a.input or DATA / "crawl_runs" / DEFAULT_CRAWL_RUN, "lượt crawl")
    output = a.output or DATA / "clean_runs" / f"clean-{stamp()}"
    run("ingest.transform.full", "--run-dir", source, "--output-dir", output)
    return output


def chunk(a, source: Path | None = None) -> Path:
    source = need(source or a.input or latest_clean(), "bản clean")
    output = a.output or DATA / "chunk_runs" / f"chunk-{stamp()}"
    run("ingest.chunk.full", "--input-dir", source, "--tokenizer", a.tokenizer or tokenizer(), "--output-dir", output)
    return output


def load(a, source: Path | None = None) -> None:
    source = need(source or a.input or latest_chunk(), "bản chunk")
    run("ingest.chunk.load_full", source, "--validate-only")
    if not a.validate_only:
        run("ingest.chunk.load_full", source)


def index(a, source: Path | None = None) -> None:
    source = need(source or a.input or latest_chunk(), "bản chunk")
    if not a.dry_run and not a.collection:
        sys.exit("Index thật cần --collection (nên là collection mới, ví dụ lore_chunks_v2).")
    args = ["--input", source / "chunks.jsonl", "--policy", a.policy, "--languages", a.languages]
    args += ["--collection", a.collection] if a.collection else []
    run("ingest index", *args, *(["--dry-run"] if a.dry_run else []))


def status(_a) -> None:
    crawl_status = (report(DATA / "crawl_runs" / DEFAULT_CRAWL_RUN) or {}).get("status", "không có")
    print(f"crawl  {DEFAULT_CRAWL_RUN}: {crawl_status}, {crawl_pages()} trang (gồm trang chỉ lỗi ảnh)")
    for name, path, key in (
        ("clean", latest_clean(), "cleaning_version"),
        ("chunk", latest_chunk(), "chunking_version"),
    ):
        info = report(path) if path else None
        counts = (info or {}).get("counts", {})
        print(f"{name:6} {path.name if path else 'không có'}: {(info or {}).get(key, '')} {counts}")


def pipeline(a) -> None:
    a.dry_run, a.collection = True, None
    cleaned = clean(a)
    a.output = None  # đầu ra chunk tự đặt tên
    chunked = chunk(a, cleaned)
    load(a, chunked)
    index(a, chunked)
    print(f"Xong. Chunk mới: {chunked}. Index thật: python -m scripts.data_pipeline index --collection <mới>")


def main() -> None:
    p = argparse.ArgumentParser(description="Pipeline dữ liệu IndexBeast: crawl, clean, chunk, load, index")
    p.add_argument("step", choices=["status", "crawl", "clean", "chunk", "load", "index", "all"])
    p.add_argument("--input", type=Path, help="Thư mục đầu vào (mặc định: bản mới nhất của bước trước)")
    p.add_argument("--output", type=Path, help="Thư mục đầu ra mới (mặc định: tên có thời gian)")
    p.add_argument("--run-id", default=DEFAULT_CRAWL_RUN, help="crawl: id lượt crawl, dùng lại để resume")
    p.add_argument("--no-media", action="store_true", help="crawl: bỏ tải ảnh")
    p.add_argument("--tokenizer", type=Path, help="chunk: tokenizer.json của E5 (mặc định: tìm trong models/)")
    p.add_argument("--validate-only", action="store_true", help="load: chỉ kiểm tra, không ghi PostgreSQL")
    p.add_argument("--collection", help="index: collection Qdrant đích (bắt buộc khi index thật)")
    p.add_argument("--policy", default="pilot", choices=["pilot", "reviewed"], help="index: chính sách nạp corpus")
    p.add_argument("--languages", default="en", help="index: ngôn ngữ được index, vd en hoặc en,ja")
    p.add_argument("--dry-run", action="store_true", help="index: kiểm tra, không tải model, không ghi Qdrant")
    a = p.parse_args()
    {"status": status, "crawl": crawl, "clean": clean, "chunk": chunk, "load": load, "index": index, "all": pipeline}[
        a.step
    ](a)


if __name__ == "__main__":
    main()
