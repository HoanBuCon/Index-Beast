# TV2 — full chunk + metadata + PostgreSQL base/SotE

Nhánh feature/s2-tv2-chunking-metadata. Đọc artifact của nhánh clean (commit 41a0276),
không cherry-pick/merge thay đổi clean vào nhánh này. Người dùng đã duyệt 4164 raw,
phạm vi Sprint 2 base game + Shadow of the Erdtree. Không embedding, Qdrant, LLM hoặc entities.

## Mã và lệnh

- ingest/chunk/full.py: streaming per-document JSONL/CSV/report; kiểm input CSV và
  processed khớp nhau, exact source slice, token encode và core.ids. Source scope không
  loại DLC. Section review nằm ngoài chunk, giữ text/lý do trong review.jsonl.
- ingest/chunk/load_full.py: preflight mọi checksum, natural ID, raw revision/hash,
  đối chiếu per-doc/global JSONL; upsert document + replace chunks trong một transaction.
  No-op chunk khi nội dung/metadata bằng nhau. Không đổi schema/repository TV1.

Từ backend, dùng output mới:

```powershell
.venv/Scripts/python.exe -m ingest.chunk.full --input-dir data/clean_runs/s2-full-v2 --tokenizer '<tokenizer.json-local>' --output-dir data/chunk_runs/<ten-moi>
.venv/Scripts/python.exe -m ingest.chunk.load_full data/chunk_runs/s2-full-v1 --validate-only
.venv/Scripts/python.exe -m ingest.chunk.load_full data/chunk_runs/s2-full-v1
```

## Kết quả đã chạy

- Clean đầu vào: data/clean_runs/s2-full-v2, 4164 trang, 22419 record, 20235 record eligible.
- Chunk output bàn giao: **data/chunk_runs/s2-full-v1**: chunks.csv BOM, chunks.jsonl,
  wikigg/<page>.jsonl, documents.jsonl, coverage.jsonl, review.jsonl, report.json.
- Mẫu 20: 689 chunk, 665 unit; regression đúng 200 ID S1: 2316 chunk, 2314 unit.
- Full: **23765 chunk, 23659/23659 unit covered, max450**, 2184 section/unit review.
  Cả 4164 trang đều có chunk. Dialogue chunks 3288, lang unknown 1801; không suy speaker.
- Languages: en18368, ja3447, unknown1801, các tab ngôn ngữ khác 149; giữ nhãn nguồn.
- Source types: wiki_prose15393, in_game_text8329, speculation43; phân loại heuristic.
- Kiểm chứng độc lập toàn bộ: source slices, ID uniqueness, encode lại cả chuỗi, max
  overlap50, đúng image IDs theo section, trigger/speaker. File validation.json ghi kết quả.
- Input fingerprints của clean/chunk không đổi; không sửa raw/ảnh. CSV round-trip đạt.
- Rerun 20 trang có logical_content_sha256 giống nhau; updated_at artifact thay theo lần tạo.
- **PostgreSQL đã nạp hai lần: 4164 documents, 23765 chunks, 0 lỗi**. Lượt hai 4164
  unchanged_documents; fingerprint toàn bộ chunks gồm updated_at không đổi. Hai job succeeded.
  postgres-first-load.json, postgres-report.json, postgres-validation.json là bằng chứng local.
- 157 unit tests passed, 13 integration deselected; chạy riêng DB/schema/loaders đạt 12
  integration tests trên DB tạm. Full loader test gồm base+SotE, unknown language,
  idempotent và rollback sau replace. Ruff check/format file mới đạt.

Entry point dễ xem: backend/data/delivery/s2-full/README.md và manifest.json, chỉ trỏ tới
artifact thật, không nhân bản file ảnh. data không đưa Git.

## Contract cần TV3 tiêu thụ

- game_scope=elden_ring theo ngoại lệ được người dùng duyệt; release_scope trong artifact
  là base_candidate/sote_candidate/mixed_or_sote_candidate/unknown, không giả đã review.
  TV3 cần đổi filter base-only khi tích hợp corpus này; TV2 chưa sửa retrieval của TV3.
- CSV/JSONL text là body; embedding_text có passage/title/section/variant/trigger/lang.
  **DB chunks.text lưu embedding_text** để context và token_count khớp chuỗi đầu vào.
  Indexer không được thêm passage prefix lần hai; review với TV3 trước index.
- title/url/source lấy từ document JOIN trong DB. Các trường release/ảnh/trigger/anchor/
  offsets/provenance đầy đủ nằm trong artifact, không tự tạo cột schema TV1.
- IDs dùng namespace chung core.ids. Không index ảnh hoặc suy caption; 7 media lỗi và
  license chưa rõ vẫn phải review. Không lấy unknown language làm en.
- Không đồng nghĩa corpus sạch hoàn toàn hoặc retrieval đã đạt chất lượng. Combat/
  bảng/cut/cross-game còn review, quy tắc source_type có thể cần hiệu chỉnh theo eval.
- Chưa cập nhật trạng thái Trello, chưa merge develop, chưa bắt đầu nhánh hệ thống thứ tư.
