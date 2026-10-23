"""S1 CLI. Later pipeline stages are deliberately not exposed yet."""

import argparse
import json
from pathlib import Path

from ingest.crawl.http import HttpClient
from ingest.crawl.runner import crawl, discover
from ingest.settings import load_settings
from ingest.sources.wikigg import WikiGG


def main(argv=None):
    p = argparse.ArgumentParser(description="IndexBeast offline data prototype (TV2 S1)")
    p.add_argument("command", choices=["crawl", "survey", "report"])
    p.add_argument("--source", choices=["wikigg"], default="wikigg")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--page")
    p.add_argument("--no-media", action="store_true")
    p.add_argument("--refresh-discovery", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--config", type=Path)
    args = p.parse_args(argv)
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
