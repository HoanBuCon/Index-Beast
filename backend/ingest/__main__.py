"""Offline data CLI: TV2 crawl/clean/chunk and explicit TV3 indexing."""

import argparse
import json
from pathlib import Path

from ingest.crawl.http import HttpClient
from ingest.crawl.runner import crawl, discover
from ingest.settings import load_settings
from ingest.sources.wikigg import WikiGG


def main(argv=None):
    p = argparse.ArgumentParser(description="IndexBeast offline crawl, clean, chunk and index (TV2/TV3)")
    p.add_argument("command", choices=["crawl", "survey", "report", "clean", "chunk", "index"])
    p.add_argument("--input", type=Path, help="Reviewed chunk JSONL for index")
    p.add_argument("--input-dir", type=Path)
    p.add_argument("--tokenizer", type=Path)
    p.add_argument("--max-tokens", type=int)
    p.add_argument("--overlap-tokens", type=int)
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--crawl-report", type=Path)
    p.add_argument("--source", choices=["wikigg"], default="wikigg")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--page")
    p.add_argument("--no-media", action="store_true")
    p.add_argument("--refresh-discovery", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--config", type=Path)
    args = p.parse_args(argv)
    if args.command == "index":
        if args.input is None:
            p.error("index requires --input reviewed-chunks.jsonl")
        from ingest.indexing import run_cli

        return run_cli(args.input, dry_run=args.dry_run)
    if args.limit < 1:
        p.error("--limit must be positive")
    config = load_settings(args.config)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "command": args.command,
                    "source": args.source,
                    "limit": args.limit,
                    "media": not args.no_media,
                    "data_dir": str(config["data_dir"]),
                    "network_requests": 0,
                },
                indent=2,
            )
        )
        return 0
    if args.command == "report":
        for path in sorted((config["data_dir"] / "reports").glob("*.json")):
            print(path)
        return 0
    if args.command == "clean":
        from ingest.transform.document import run_clean

        if not args.output_dir:
            p.error("clean requires --output-dir pointing to a new or empty directory")
        result = run_clean(config, args.output_dir, crawl_report=args.crawl_report, limit=args.limit)
        print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
        return 0
    if args.command == "chunk":
        from ingest.chunk.runner import run_chunk

        if not args.input_dir or not args.tokenizer or not args.output_dir:
            p.error("chunk requires --input-dir, --tokenizer and --output-dir")
        result = run_chunk(
            args.input_dir,
            args.tokenizer,
            args.output_dir,
            cap=args.max_tokens if args.max_tokens is not None else config["chunk"]["max_tokens"],
            overlap=args.overlap_tokens if args.overlap_tokens is not None else config["chunk"]["overlap_tokens"],
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "completed" else 2
    client = HttpClient(config)
    try:
        source = WikiGG(client, config)
        if args.command == "survey":
            result = discover(source, config)
            print(
                json.dumps(
                    {k: v for k, v in result.items() if k not in ("pages", "membership")}, ensure_ascii=False, indent=2
                )
            )
            return 0 if all(x["status"] == "ok" for x in result["categories"]) else 2
        result = crawl(
            source,
            config,
            1 if args.page else args.limit,
            page=args.page,
            with_media=not args.no_media,
            refresh_discovery=args.refresh_discovery,
        )
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in ("pages", "scope_excluded")}, ensure_ascii=False, indent=2
            )
        )
        return 0 if result["status"] == "completed" else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
