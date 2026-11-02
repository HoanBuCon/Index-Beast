"""Verify the accepted S1 sample against current raw/media artifacts, without network."""

import argparse
from collections import Counter
from pathlib import Path

from ingest.artifacts import now, read, save, sha256


def audit(data_dir, job_path):
    job = read(job_path)
    errors = []
    statuses = Counter()
    hashes = {}
    licenses = Counter()
    groups = Counter()
    ids = [x["id"] for x in job["pages"]]
    if len(ids) != 200 or len(set(ids)) != 200:
        errors.append("Expected 200 distinct page IDs")
    membership = read(data_dir / "reports/categories.json")["membership"]
    for page in job["pages"]:
        raw = read(data_dir / page["path"])
        if sha256(raw["content"].encode()) != raw["content_hash"]:
            errors.append([page["id"], "raw checksum"])
        if raw["revision_id"] != page["revision_id"]:
            errors.append([page["id"], "raw revision"])
        groups.update(membership.get(page["id"], []))
        manifest_path = data_dir / "media/manifests/wikigg" / (page["id"] + ".json")
        if not manifest_path.exists():
            errors.append([page["id"], "missing manifest"])
            continue
        manifest = read(manifest_path)
        if manifest["revision_id"] != raw["revision_id"]:
            errors.append([page["id"], "media revision"])
        for item in manifest["images"]:
            statuses[item["status"]] += 1
            if item["status"] == "excluded":
                continue
            if item["status"] not in ("downloaded", "cached"):
                errors.append([page["id"], item["status"]])
                continue
            licenses[item["license_status"]] += 1
            path = (data_dir / item["path"]).resolve()
            if not path.is_relative_to(data_dir.resolve()):
                errors.append([page["id"], "image path escapes data"])
                continue
            if not path.exists() or sha256(path.read_bytes()) != item["sha256"]:
                errors.append([page["id"], "image checksum"])
                continue
            hashes[item["sha256"]] = path.stat().st_size
    result = {
        "checked_at": now(),
        "source_job": job["job_id"],
        "status": "passed" if not errors else "failed",
        "unique_pages": len(set(ids)),
        "manifest_count": len(ids),
        "image_occurrences": dict(statuses),
        "unique_image_blobs": len(hashes),
        "image_bytes": sum(hashes.values()),
        "image_license_statuses": dict(licenses),
        "category_memberships": dict(groups),
        "errors": errors,
        "original_crawl_elapsed_seconds": job["elapsed_seconds"],
        "repairs": [
            "crawl-212327e00883: validated PNG advertised as WebP; local extension/MIME reflect decoded format",
            "context parser v2: ignore infobox headings and exclude UI rating icons; recomputed from raw, no downloads",
        ],
        "scope_note": "Heuristic-eligible raw sample; full section-level scope review required before indexing",
    }
    save(data_dir / "reports/s1-acceptance.json", result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    p.add_argument("--crawl-report", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.data_dir, args.crawl_report)
    print(result)
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
