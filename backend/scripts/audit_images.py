"""Read-only image artifact audit; checks metadata census, paths and a bounded blob sample. No clients/models."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.services.images import ImageCatalog
from core.config import REPO_ROOT, Settings
from core.types import Hit
from scripts.benchmark_index import save


async def audit(sample_size):
    settings = Settings(_env_file=None)
    catalog = ImageCatalog(settings)
    catalog._load()
    if catalog.counts.get("catalog_unavailable"):
        raise ValueError("Image catalog unavailable")
    with catalog.catalog_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    chunk_path = REPO_ROOT / "backend/data/chunk_runs/s2-full-v1/chunks.jsonl"
    chunks = [json.loads(line) for line in chunk_path.read_text(encoding="utf-8").splitlines()]
    sample = []
    for image_id in sorted(catalog._blobs)[:sample_size]:
        blob, reason = catalog.read_blob(image_id)
        dimensions = None
        if blob:
            with Image.open(io.BytesIO(blob.data)) as image:
                dimensions = list(image.size)
        sample.append(
            {
                "id": image_id,
                "valid": blob is not None,
                "reason": reason,
                "mime": blob.mime if blob else None,
                "bytes": len(blob.data) if blob else None,
                "dimensions": dimensions,
            }
        )
    cases = []
    for title in ("Bloodhound's Fang", "Ranni the Witch", "Messmer the Impaler"):
        candidates = [r for r in chunks if r["title"] == title and r["lang"] == "en" and r.get("image_ids")]
        chosen = next((r for r in candidates if r["section"] == "Infobox"), candidates[0])
        hit = Hit(chosen["chunk_id"], 0.0, chosen)
        result = await catalog.resolve([hit], [1], spoilers=True)
        cases.append(
            {
                "title": title,
                "chunk_id": chosen["chunk_id"],
                "section": chosen["section"],
                "images": [r.model_dump() for r in result.images],
                "excluded": result.reasons,
            }
        )
    # Local ASGI only: fake context, mock chat, real local image file, no infrastructure resources.
    from types import SimpleNamespace

    app = create_app(settings, context=SimpleNamespace(health_checks={}))
    endpoints = []
    with TestClient(app) as client:
        client.app.state.image_catalog = catalog
        for case in cases:
            for image in case["images"]:
                response = client.get(image["url"])
                endpoints.append(
                    {
                        "id": image["id"],
                        "status": response.status_code,
                        "mime": response.headers.get("content-type"),
                        "body_sha256_matches_id": hashlib.sha256(response.content).hexdigest() == image["id"],
                    }
                )
    return {
        "method": "Full metadata census; existence checks on eligible blobs; sorted bounded hash/Pillow sample. "
        "Three chosen actual linked chunks and local TestClient image endpoints. No remote HTTP/server/model calls.",
        "rows": len(rows),
        "unique_occurrences": len({r["occurrence_id"] for r in rows}),
        "associations": dict(Counter(r["association"] for r in rows)),
        "media_status": dict(Counter(r["media_status"] for r in rows)),
        "license_status": dict(Counter(r["license_status"] for r in rows)),
        "catalog": dict(catalog.counts),
        "eligible_blob_files_exist": sum(p.is_file() for p in catalog._blobs.values()),
        "chunks": len(chunks),
        "linked_chunks": sum(bool(r.get("image_ids")) for r in chunks),
        "en_linked_chunks": sum(r.get("lang") == "en" and bool(r.get("image_ids")) for r in chunks),
        "chunk_image_ids": len({i for r in chunks for i in r.get("image_ids", [])}),
        "blob_validation_sample": sample,
        "resolved_examples": cases,
        "local_asgi_endpoints": endpoints,
        "artifact_hashes": {
            p.relative_to(REPO_ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (catalog.catalog_path, catalog.documents_path, chunk_path)
        },
        "limitations": "Existence is not byte verification. Only the bounded sample/examples decoded; semantic "
        "image relevance beyond explicit section links and rights not certified. Unknown license remains unknown.",
    }


def main():
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 100 or args.output.exists() or args.output.suffix != ".json":
        parser.error("sample-size must be 1..100, output must be a new .json report")
    if args.output.resolve().is_relative_to((REPO_ROOT / "backend/data").resolve()):
        parser.error("Report must be outside source artifacts")
    report = asyncio.run(audit(args.sample_size))
    save(args.output, report)
    print(
        json.dumps({"rows": report["rows"], "catalog": report["catalog"], "endpoints": report["local_asgi_endpoints"]})
    )


if __name__ == "__main__":
    main()
