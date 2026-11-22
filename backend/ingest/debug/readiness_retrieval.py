"""Isolated local E5 diagnostic; no production retrieval changes, LLM or server writes."""

import argparse
import hashlib
import json
import random
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import numpy as np
from bs4 import BeautifulSoup

REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


def read_lines(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def url_key(url):
    parts = urlsplit(url)
    return parts.netloc.casefold(), unquote(parts.path).replace("_", " ").casefold()


def prepare(data, output, golden, baseline_documents=None):
    if (output / "protocol.json").exists():
        raise ValueError("Protocol already frozen")
    inventory = baseline_documents or data / "delivery/final/chunk/documents.jsonl"
    docs = read_lines(inventory)
    by_title = {d["title"]: d for d in docs}
    definitions = [
        ("Moonveil", "What is Moonveil's weight?", "field", "weight", "6.5", r"Weight:\s*6\.5\b"),
        (
            "Moonveil",
            "Moonveil có Physical Attack Power bao nhiêu?",
            "row",
            "Physical:",
            "73",
            r"Attack Power / Physical:\s*73\b",
        ),
        (
            "Moonveil",
            "What is Moonveil's guarded physical damage negation?",
            "row",
            "Physical:",
            "31",
            r"Guarded Damage Negation / Physical:\s*31\b",
        ),
        ("Moonveil", "What is Moonveil's magic attack power?", "row", "Magic:", "87", r"Attack Power / Magic:\s*87\b"),
        (
            "Moonveil",
            "Moonveil yêu cầu Intelligence bao nhiêu và scaling cấp nào?",
            "row",
            "Intelligence:",
            "23",
            r"Intelligence:\s*\|\s*23\s*\|\s*C\b",
        ),
        (
            "Uchigatana",
            "What is Uchigatana's physical attack power?",
            "row",
            "Physical:",
            "115",
            r"Attack Power / Physical:\s*115\b",
        ),
        ("Uchigatana", "Uchigatana nặng bao nhiêu?", "field", "weight", "5.5", r"Weight:\s*5\.5\b"),
        (
            "Uchigatana",
            "What blood loss buildup is listed for Uchigatana?",
            "field",
            "effects",
            "Causes blood loss buildup (45)",
            r"Causes blood loss buildup\s*\(45\)",
        ),
        ("Longsword", "Longsword nặng bao nhiêu?", "field", "weight", "3.5", r"Weight:\s*3\.5\b"),
        (
            "Longsword",
            "What is Longsword's base physical attack listed in its infobox?",
            "row",
            "Physical:",
            "110",
            r"Attack Power / Physical:\s*110\b",
        ),
        (
            "Malenia's Winged Helm",
            "What Poise is listed for Malenia's Winged Helm?",
            "row",
            "Poise:",
            "4",
            r"Resistance / Poise:\s*4\b",
        ),
        (
            "Malenia's Winged Helm",
            "Malenia's Winged Helm có Standard Damage Negation bao nhiêu?",
            "row",
            "Standard:",
            "4.4",
            r"Damage Negation / Standard:\s*4\.4\b",
        ),
        (
            "Carian Regal Scepter",
            "What Intelligence requirement and scaling grade does Carian Regal Scepter have?",
            "row",
            "Intelligence:",
            "60",
            r"Intelligence:\s*\|\s*60\s*\|\s*B\b",
        ),
        ("Finger Seal", "Finger Seal yêu cầu Faith bao nhiêu?", "row", "Faith:", "10", r"Faith:\s*\|\s*10\s*\|\s*C\b"),
        (
            "Flame, Cleanse Me",
            "What is the FP cost of Flame, Cleanse Me?",
            "field",
            "fp_cost",
            "14",
            r"FP Cost:\s*14\b",
        ),
    ]
    cases = []
    for i, (title, question, kind, field, value, pattern) in enumerate(definitions, 1):
        doc = by_title[title]
        raw = json.loads(Path(doc["source_snapshot"]).read_text(encoding="utf-8"))
        body = BeautifulSoup(raw["content"], "html.parser").select_one(".mw-parser-output")
        positions = {
            id(tag): f"dom:{n}:{tag.name}" + (f"#{tag['id']}" if tag.get("id") else "")
            for n, tag in enumerate(body.find_all(True))
        }
        node = None
        if kind == "field":
            node = body.select_one(f'.pi-data[data-source="{field}"] .pi-data-value')
            assert node is not None and node.get_text(" ", strip=True) == value, (title, field, value)
        else:
            for row in body.select("aside tr"):
                cells = row.find_all(["td", "th"], recursive=False)
                values = [c.get_text(" ", strip=True) for c in cells]
                if field in values and value in values:
                    node = row
                    break
            assert node is not None, (title, field, value)
        cases.append(
            {
                "id": f"TV2-STAT-{i:02d}",
                "question": question,
                "source_id": doc["source_id"],
                "source_url": doc["url"],
                "title": title,
                "evidence_pattern": pattern,
                "snapshot": doc["source_snapshot"],
                "revision_id": doc["revision_id"],
                "raw_content_hash": raw["content_hash"],
                "source_location": positions[id(node)],
                "raw_quote": node.get_text(" ", strip=True),
                "field": field,
                "raw_value": value,
                "status": "snapshot_diagnostic_not_latest_patch_certification",
            }
        )
    negatives = [
        {
            "id": "TV2-NEG-01",
            "question": "What is Fire Knight Armor's weight?",
            "title": "Fire Knight Armor",
            "reason": "weight_not_present_in_delivered_snapshot",
        },
        {
            "id": "TV2-NEG-02",
            "question": "What is Moonveil's exact damage in the patch released today?",
            "title": "Moonveil",
            "reason": "snapshot_has_no_verified_current_patch",
        },
        {
            "id": "TV2-NEG-03",
            "question": "What Moonveil PvP build guarantees a 100 percent win rate?",
            "title": "Moonveil",
            "reason": "optimization_guarantee_not_supported_by_snapshot",
        },
    ]
    golden_rows = read_lines(golden)
    reference_urls = {url_key(url) for row in golden_rows for url in row["source_urls"]}
    selected = {d["source_id"] for d in docs if url_key(d["url"]) in reference_urls}
    selected.update(by_title[c["title"]]["source_id"] for c in [*cases, *negatives])
    positives = len(selected)
    background = sorted({d["source_id"] for d in docs} - selected, key=int)
    selected.update(random.Random(20261108).sample(background, 150))
    save(
        output / "protocol.json",
        {
            "seed": 20261108,
            "source_ids": sorted(selected, key=int),
            "positive_source_pages": positives,
            "background_source_pages": 150,
            "cases": cases,
            "negatives": negatives,
            "golden": golden_rows,
            "golden_status": "pending; URL labels are provisional",
            "baseline_sha256": hashlib.sha256((inventory.parent / "chunks.jsonl").read_bytes()).hexdigest(),
            "scope": "controlled local source-page pool, not production/full-index recall or end-to-end RAG",
            "api_calls": 0,
        },
    )


def model(path):
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType

    name = "intfloat/multilingual-e5-small"
    if not any(m["model"] == name for m in TextEmbedding.list_supported_models()):
        TextEmbedding.add_custom_model(
            model=name,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=name),
            dim=384,
            model_file="onnx/model.onnx",
        )
    encoder = TextEmbedding(
        name, specific_model_path=str(path), local_files_only=True, threads=2, providers=["CPUExecutionProvider"]
    )
    encoder.model.tokenizer.no_truncation()
    return encoder


def encode(encoder, texts, cache_dir):
    key_file, vector_file = cache_dir / "vector-keys.json", cache_dir / "vectors.npy"
    keys = json.loads(key_file.read_text()) if key_file.exists() else []
    vectors = list(np.load(vector_file)) if vector_file.exists() else []
    cache = dict(zip(keys, vectors, strict=True))
    pending = {
        hashlib.sha256(text.encode()).hexdigest(): text
        for text in texts
        if hashlib.sha256(text.encode()).hexdigest() not in cache
    }
    pairs = list(pending.items())
    for start in range(0, len(pairs), 8):
        batch = pairs[start : start + 8]
        if any(len(encoder.model.tokenizer.encode(text).ids) > 512 for _, text in batch):
            raise ValueError("Input would truncate")
        result = list(encoder.embed([text for _, text in batch], batch_size=8))
        for (key, _), vec in zip(batch, result, strict=True):
            if vec.shape != (384,) or not np.isfinite(vec).all() or not np.isclose(np.linalg.norm(vec), 1, atol=1e-4):
                raise ValueError("Invalid genuine E5 vector")
            cache[key] = vec
        if start % 200 == 0:
            print(f"E5 {start}/{len(pairs)} new texts", flush=True)
    save(key_file, list(cache))
    np.save(vector_file, np.asarray(list(cache.values()), dtype=np.float32))
    return np.asarray([cache[hashlib.sha256(t.encode()).hexdigest()] for t in texts], dtype=np.float32)


def evaluate(artifact, output, model_path, name):
    protocol = json.loads((output / "protocol.json").read_text(encoding="utf-8"))
    signature = {
        "model": "intfloat/multilingual-e5-small",
        "revision": REVISION,
        "onnx_sha256": hashlib.sha256((model_path / "onnx/model.onnx").read_bytes()).hexdigest(),
        "tokenizer_sha256": hashlib.sha256((model_path / "tokenizer.json").read_bytes()).hexdigest(),
        "prefixes": ["query:", "passage:"],
        "dimension": 384,
    }
    cache_manifest = output / "vector-cache-manifest.json"
    if cache_manifest.exists():
        if json.loads(cache_manifest.read_text(encoding="utf-8")) != signature:
            raise ValueError("Vector cache belongs to a different model/tokenizer")
    else:
        previous = output / "before-retrieval-summary.json"
        if (output / "vectors.npy").exists() and (
            not previous.exists() or json.loads(previous.read_text())["onnx_sha256"] != signature["onnx_sha256"]
        ):
            raise ValueError("Existing cache cannot be attributed to this model")
        save(cache_manifest, signature)
    chosen = set(protocol["source_ids"])
    corpus = [c for c in read_lines(artifact) if c["source_id"] in chosen and c["lang"] == "en"]
    encoder = model(model_path)
    vectors = encode(encoder, [c["embedding_text"] for c in corpus], output)
    questions = [*protocol["cases"], *protocol["golden"], *protocol["negatives"]]
    query_vectors = encode(encoder, ["query: " + q["question"] for q in questions], output)
    results = []
    for case, query in zip(questions, query_vectors, strict=True):
        scores = vectors @ query
        indices = np.argsort(-scores, kind="stable")[:10]
        hits = [
            dict(
                chunk_id=corpus[i]["chunk_id"],
                source_id=corpus[i]["source_id"],
                url=corpus[i]["url"],
                section=corpus[i]["section"],
                cosine=float(scores[i]),
                text=corpus[i]["text"],
                embedding_text=corpus[i]["embedding_text"],
            )
            for i in indices
        ]
        row = {"id": case["id"], "question": case["question"], "hits": hits}
        if "evidence_pattern" in case:
            row["evidence_in_pool"] = any(
                c["source_id"] == case["source_id"] and re.search(case["evidence_pattern"], c["embedding_text"], re.I)
                for c in corpus
            )
            row["evidence_hit5"] = any(
                c["source_id"] == case["source_id"] and re.search(case["evidence_pattern"], c["embedding_text"], re.I)
                for c in hits[:5]
            )
            row["source_hit5"] = any(c["source_id"] == case["source_id"] for c in hits[:5])
        elif "source_urls" in case:
            expected = {url_key(u) for u in case["source_urls"]}
            row["source_labels"] = len(expected)
            row["source_in_pool"] = any(url_key(c["url"]) in expected for c in corpus)
            row["source_hit5"] = any(url_key(c["url"]) in expected for c in hits[:5])
        else:
            row["unsupported_reason"] = case["reason"]
            row["interpretation"] = (
                "Nearest neighbours are not evidence that the requested claim is supported. No answer/LLM tested."
            )
        results.append(row)
    gear = [r for r in results if r["id"].startswith("TV2-STAT")]
    golden = [r for r in results if r["id"].startswith("IB-GS") and r["source_labels"]]
    summary = {
        "name": name,
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "corpus_pages": len({c["source_id"] for c in corpus}),
        "corpus_chunks": len(corpus),
        "model": "intfloat/multilingual-e5-small",
        "model_revision": REVISION,
        "onnx_sha256": hashlib.sha256((model_path / "onnx/model.onnx").read_bytes()).hexdigest(),
        "vector_dim": vectors.shape[1],
        "api_calls": 0,
        "gear_cases": len(gear),
        "gear_evidence_present": sum(r["evidence_in_pool"] for r in gear),
        "gear_source_hit5": sum(r["source_hit5"] for r in gear),
        "gear_evidence_hit5": sum(r["evidence_hit5"] for r in gear),
        "golden_factual_with_url": len(golden),
        "golden_source_present": sum(r["source_in_pool"] for r in golden),
        "golden_any_source_hit5": sum(r["source_hit5"] for r in golden),
        "negative_cases": len(protocol["negatives"]),
        "limitations": [
            protocol["scope"],
            "Dense E5 only; production hybrid/rewrite/sidecar/web/LLM not evaluated.",
            "Golden source URL labels are pending review, not official Recall/MRR.",
            "Stats matches are source-specific regex diagnostics against frozen raw values, not latest-patch accuracy.",
        ],
    }
    (output / (name + "-retrieval.jsonl")).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8"
    )
    save(output / (name + "-retrieval-summary.json"), summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "evaluate"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--baseline-documents", type=Path, help="Source-page inventory for a new frozen protocol")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--name", default="before")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(Path("data"), args.output, Path("eval/golden_set.jsonl"), args.baseline_documents)
    else:
        evaluate(args.artifact, args.output, args.model_path, args.name)
