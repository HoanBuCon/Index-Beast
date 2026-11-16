# Pipeline dữ liệu IndexBeast

Tài liệu cho thẻ 5.6 và FR-ING-07 (cập nhật tăng dần). Phạm vi: từ wiki.gg đến PostgreSQL và Qdrant. Chi tiết từng bước đã nghiệm thu nằm ở [README ingest](../backend/ingest/README.md), [kế hoạch raw/clean/chunk](tv2-full-raw-clean-chunk-plan.md) và [handover S4](handover/2026-11-12_s4-tv2_wiki-quality.md).

## 1. Luồng dữ liệu

```text
                         wiki.gg (MediaWiki API, ≤ 1 request/giây, robots, contact email)
                                         │
        ┌────────────────────────────────┴───────────────────────────────┐
        │ DỰNG TOÀN BỘ (lần đầu, hoặc đổi chính sách clean/chunk)          │ CẬP NHẬT TĂNG DẦN (hằng tuần)
        │                                                                 │
        │ 1 crawl   ingest.crawl.full  → data/crawl_runs/<run>/           │ python -m ingest update
        │            inventory category, raw HTML theo revision, ảnh       │   a. phát hiện: recentchanges từ mốc state
        │ 2 clean   ingest.transform.full --gameplay --structured-tables   │      (hoặc --full-scan: so lastrevid)
        │            → data/clean_runs/<tên>/ (section, bảng, review.csv) │   b. describe(lastrevid) so với state
        │ 3 chunk   ingest.chunk.full --wiki-quality                      │   c. chỉ trang đổi/mới: bước 1–3 như cột trái
        │            → data/chunk_runs/<tên>/ (chunks.jsonl, documents)   │      trên một "run" nhỏ data/update_runs/<id>/
        │ 4 nạp     ingest.chunk.load_full  → PostgreSQL documents/chunks │   d. index: upsert point theo id ổn định,
        │           python -m ingest index  → Qdrant (dense + BM25)       │      xoá point thừa của trang co lại
        └─────────────────────────────────────────────────────────────────┤   e. PostgreSQL: upsert document, thay chunk;
                                                                          │      trang bị xoá → status deleted
   Cả hai cột cùng ghi: raw (data/raw), media (data/media), PostgreSQL,   │   f. ghi state + ingestion_jobs + report
   Qdrant (collection RAG_COLLECTION), bảng ingestion_jobs.               └──────────────────────────────────────────
```

Thành phần dùng chung giữa dựng toàn bộ và cập nhật tăng dần: `WikiGG` (nguồn), `MediaStore` (ảnh), `transform.full.run`, `chunk.full.run`, `chunk_fields` (dòng PostgreSQL), `ChunkRecord`/`CorpusPolicy`/`QdrantStore` (index). Cập nhật tăng dần không có đường xử lý riêng nên không lệch kết quả so với dựng toàn bộ.

Id ổn định là điều kiện để mọi bước chạy lại an toàn (`core/ids.py`): `document_id = uuid5(source:source_id)`, `chunk_id = uuid5(document_id, ordinal)`, point Qdrant = `uuid5(document_id, chunk_id)`. Cùng trang, cùng thứ tự đoạn thì cùng id, nên upsert ghi đè đúng chỗ.

## 2. Lệnh CLI

Chạy từ `backend/` (Docker: `python`; Windows: `.venv/Scripts/python.exe`). Cần `INGEST_CONTACT_EMAIL` trong `.env` khi gọi mạng.

| Việc | Lệnh |
|---|---|
| Xem lệnh chạy, không mạng | `python -m ingest crawl --dry-run` |
| Khảo sát category | `python -m ingest survey` |
| Crawl toàn bộ (resume theo `--run-id`) | `python -m ingest.crawl.full --run-id <id>` |
| Clean | `python -m ingest.transform.full --run-dir data/crawl_runs/<id> --output-dir data/clean_runs/<tên> --gameplay --structured-tables` |
| Chunk | `python -m ingest.chunk.full --input-dir data/clean_runs/<tên> --tokenizer <tokenizer.json> --output-dir data/chunk_runs/<tên> --wiki-quality` |
| Nạp PostgreSQL | `python -m ingest.chunk.load_full data/chunk_runs/<tên>` (`--validate-only` để kiểm) |
| Index Qdrant | `python -m ingest index --input data/chunk_runs/<tên>/chunks.jsonl --policy pilot --languages en --collection <tên mới>` |
| Một lệnh mỗi bước | `python -m scripts.data_pipeline status\|clean\|chunk\|load\|index\|all` |
| **Cập nhật tăng dần** | `python -m ingest update --source wikigg` |

`update` nhận thêm:

| Cờ | Ý nghĩa |
|---|---|
| `--dry-run` | Phát hiện và phân loại new/changed/deleted/unchanged, in tiêu đề; không tải trang, không ghi state/DB/index. Vẫn gọi API chỉ-đọc của wiki. |
| `--since <ISO 8601>` | Quét thay đổi từ mốc này thay vì mốc đã lưu (xem chạy bù). Không đẩy mốc state nếu muộn hơn mốc hiện tại. |
| `--full-scan` | Không dùng recentchanges: duyệt category rồi so `lastrevid` mọi trang đã biết. Chi phí tăng theo corpus nhưng chỉ đọc metadata. Dùng khi nghi ngờ sót (vd. mỗi tháng). |
| `--max-pages N` | Chỉ xử lý N trang mỗi lượt; phần còn lại tự được phát hiện lại ở lượt sau (mốc không được đẩy). |
| `--batch-pages N` | Kích thước lô crawl-clean-chunk-index, mặc định 50 (`[update] batch_pages`). |
| `--bootstrap-from <thư mục chunk>` / `--bootstrap-from-db` | Tạo state lần đầu (xem 4.1). |
| `--tokenizer`, `--collection`, `--policy`, `--languages`, `--no-media` | Giống các lệnh khác; mặc định theo `RAG_*`. |

Mã thoát: 0 khi `completed` hoặc `dry_run`; 2 khi `partial`/`failed`, thiếu state, hoặc đang có lượt khác giữ lock.

Cron production: [`scripts/ingest-weekly.sh`](../scripts/ingest-weekly.sh) chạy `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app run --rm -T api python -m ingest update --source wikigg`. Script giữ `flock` (mã 75 khi lượt trước còn chạy), ghi log ngoài repo (`/var/log/indexbeast` hoặc `~/.local/state/indexbeast`, giữ 12 log) và trả mã thoát của lệnh. Crontab mẫu: `30 3 * * 0 /opt/indexbeast/scripts/ingest-weekly.sh`.

## 3. Cấu hình

| Nơi | Khoá | Tác dụng |
|---|---|---|
| `backend/ingest/config/sources.toml` `[crawl]` | `min_interval_seconds` (≥ 1), `max_retries`, `allowed_hosts`, `user_agent` | Giới hạn lịch sự với wiki, dùng cho mọi request kể cả `update` |
| `[sources.wikigg]` | `api_url`, `page_url`, `categories`, `category_depth`, `license` | Phạm vi nguồn; category gốc cũng là phạm vi của trang mới khi `update` |
| `[update]` | `recentchanges_max_age_days` (30), `overlap_minutes` (30), `batch_pages` (50) | Mốc cũ hơn ngưỡng tự chuyển sang `--full-scan`; mốc được lùi `overlap_minutes` để không sót |
| `[chunk]`, `[filter]`, `[clean]` | token tối đa/overlap, section bỏ qua | Đổi các khoá này là đổi chính sách: cần dựng toàn bộ (mục 6) |
| `.env` | `INGEST_CONTACT_EMAIL`, `RAG_COLLECTION`, `RAG_CORPUS_POLICY`, `RAG_LANGUAGES`, `RAG_BATCH_SIZE`, `RAG_MODELS_DIR`, `QDRANT_URL`, `DATABASE_URL` | Đích index và chính sách nhận chunk |
| Môi trường script | `INGEST_LOG_DIR`, `INGEST_LOCK_FILE`, `INGEST_ARGS` | Vị trí log/khoá; tham số thêm cho `update` |

Dữ liệu `data/` (mount `./backend/data:/app/data` trong Compose) giữ raw, media, state và báo cáo; không nằm trong Git. State cập nhật: `data/state/<source>-update.json`; báo cáo mỗi lượt: `data/reports/update-<id>.json` và một dòng `ingestion_jobs` (`kind=update`, `pages_ok`, `pages_failed`, `log` chứa số đếm và lỗi).

## 4. Cập nhật tăng dần hoạt động thế nào

State là một file JSON nhỏ: `watermark` (mốc thời gian quét tới), `pages[source_id] = {revision_id, title, chunks}` và `scope_categories` (cache cây category). Nguồn sự thật cho nội dung vẫn là PostgreSQL và Qdrant; state chỉ cho biết revision nào đã được áp dụng.

1. **Phát hiện.** Mặc định gọi `list=recentchanges` (namespace 0; sửa, tạo mới, log xoá/đổi tên) từ `watermark`. Một lời gọi trả tối đa 500 thay đổi, nên chi phí theo số thay đổi chứ không theo corpus. Dòng log xoá không có `pageid` được ánh xạ qua tiêu đề trong state. Nếu `watermark` trống hoặc cũ hơn `recentchanges_max_age_days`, hoặc có `--full-scan`: duyệt category (1 request mỗi category) rồi lấy mọi id đã biết.
2. **Phân loại.** `describe` lấy `lastrevid`, redirect, namespace và category theo lô 50 id, so với state:
   - **unchanged**: cùng revision (sửa rồi hoàn tác, hoặc đã xử lý ở lượt trước). Bỏ qua.
   - **changed**: revision khác. Xử lý lại.
   - **new**: chưa có trong state và thuộc category phạm vi (hoặc category con đã duyệt). Ngoài phạm vi thì tính `skipped_out_of_scope`.
   - **deleted**: trang bị xoá, thành redirect, rời namespace 0 hoặc dính tựa/category Nightreign/Tarnished Edition. Chỉ tính khi đã có trong state.
3. **Xoá.** Với trang bị xoá: xoá mọi point Qdrant có `document_id` của trang, xoá chunk PostgreSQL và đặt document `deleted`, bỏ khỏi state.
4. **Dựng lại theo lô** (`--batch-pages`, mặc định 50): `PipelineBuilder` tải raw theo revision (snapshot `raw/<source>/snapshots/<id>/<rev>-<hash>.json`), ảnh qua `MediaStore`, rồi chạy đúng `transform.full` (S3 structured) và `chunk.full --wiki-quality` trên một run nhỏ `data/update_runs/<id>/`. Lô lỗi được tách từng trang để cô lập trang hỏng.
5. **Index.** Chunk qua `ChunkRecord` và `CorpusPolicy` (chunk bị chính sách loại không vào Qdrant). Encode theo mẻ `RAG_BATCH_SIZE`, upsert theo point id ổn định, **sau đó** xoá point của chính tài liệu đó không còn trong tập mới (trang co từ 8 xuống 5 đoạn thì 3 point cuối bị xoá; nếu dừng giữa chừng, tài liệu vẫn có đủ dữ liệu hợp lệ). Collection được tạo/kiểm bằng `ensure_collection`, không bao giờ drop.
6. **PostgreSQL.** `upsert_document` rồi `replace_chunks` trong một transaction mỗi tài liệu.
7. **State.** Ghi sau **mỗi lô**. Đây là điểm resume: lượt chạy lại bỏ qua trang đã khớp revision.
8. **Kết thúc.** Chỉ khi không còn lỗi và không còn trang hoãn, `watermark = giờ bắt đầu − overlap_minutes`. Có lỗi từng trang → `partial`, mốc giữ nguyên, lượt sau phát hiện lại cùng cửa sổ và chỉ làm lại trang lỗi. Lỗi hạ tầng (Qdrant/PG sập) → `failed`, ngoại lệ được ném ra sau khi ghi job và state các lô đã xong.

Tính chất:

- **Idempotent**: chạy hai lần liên tiếp, lần hai không dựng lại gì (test `test_rerun_is_idempotent...`). Id ổn định nên upsert lặp ghi đè cùng điểm.
- **Resumable**: tiến trình chết giữa chừng, state còn nguyên theo lô; lô dở được làm lại toàn bộ (an toàn vì upsert + xoá thừa lặp được).
- **Chống chạy chồng**: `flock` trong script và khoá file `data/state/run.lock` trong CLI.
- **Không đụng corpus còn lại**: không đọc, không ghi artifact của trang không đổi.

### 4.1 Lần đầu (bootstrap)

State chưa tồn tại thì `update` dừng với mã 2. Tạo state một lần, từ nguồn đã khớp với những gì đang index:

- `python -m ingest update --source wikigg --bootstrap-from data/chunk_runs/<bản đang phục vụ> --dry-run`: đọc `documents.jsonl` và `wikigg/*.jsonl` (revision, số chunk, mốc = `fetched_at` sớm nhất), rồi phát hiện thay đổi từ mốc đó. Bootstrap luôn ghi file state (một lần, không gọi mạng); bỏ `--dry-run` để chạy thật ngay.
- Hoặc `--bootstrap-from-db`: lấy từ bảng `documents` (status active). Nếu thiếu `fetched_at` thì mốc để trống và lượt đầu tự quét toàn bộ.

Bản dùng để bootstrap phải là bản đã nạp vào PostgreSQL/Qdrant đang phục vụ, nếu không `update` sẽ tin rằng trang đã được index.

### 4.2 Chạy bù, kiểm tra

- Lỡ nhiều tuần: lượt kế tiếp tự dùng mốc cũ; quá `recentchanges_max_age_days` thì tự chuyển sang quét toàn bộ.
- Xem trước: `--dry-run` rồi đọc `data/reports/update-<id>.json` sau lượt thật. Lỗi theo trang nằm ở `errors[]` (`phase`, `error`).
- Bắt buộc dựng lại một trang: xoá mục của nó trong state (hoặc đặt `revision_id` về 0) rồi chạy `update --since <ngày>`.

## 5. Thêm nguồn mới

1. **Khai báo** trong `sources.toml`: bảng `[sources.<tên>]` với `enabled`, `plugin`, `api_url`/`base_url`, `page_url`, `license` và phạm vi (category/trang/resource). Thêm host vào `crawl.allowed_hosts`.
2. **Viết plugin** `ingest/sources/<tên>.py` có `name` và `client` (HttpClient dùng chung, đã có giới hạn tốc độ và robots). Giao diện nguồn mà các bước hiện dùng: `list_category(category)`, `describe(ids)` (trả `pageid`, `title`, `ns`, `lastrevid`, `categories`, `missing`/`redirect`), `fetch(page)` (trả raw schema 1: `source`, `source_id`, `title`, `url`, `revision_id`, `fetched_at`, `content`, `content_hash`, `license`…), và cho cập nhật tăng dần thêm `recent_changes(since)`. Nguồn không phải MediaWiki phải tự ánh xạ sang các hình dạng trên, kể cả khi API không có recentchanges (khi đó chỉ dùng `--full-scan`).
3. **Đăng ký CLI**: thêm tên vào `--source choices` trong `ingest/__main__.py`; tách lớp `WikiGG(client, config)` khỏi chỗ gọi cứng trong `ingest/update_cli.py` và `crawl/full.py` nếu nguồn mới chạy song song với wiki.gg.
4. **Bước clean/chunk**: `transform.full` hiện đọc HTML kiểu MediaWiki. Nguồn có cấu trúc khác cần một bộ clean riêng cho ra cùng hợp đồng `processed/<source>/<id>.json`; sau đó `chunk.full` và `QdrantIndex` dùng được nguyên vẹn.
5. **Danh tính**: dùng `source` mới trong `document_id(source, source_id)`; `source_id` phải bất biến theo thời gian (pageid, không phải tiêu đề).
6. **Chính sách và test**: cập nhật `CorpusPolicy` nếu cần `game_scope`/`source_type` mới; viết test với fake nguồn như `tests/unit/test_ingest_update_run.py`; thử `--dry-run` trước.
7. **Giấy phép**: ghi `license` và cách ghi nguồn khi trích dẫn (xem [data-sources](data-sources.md)).

## 6. Ghi chú mở rộng

Chi phí mỗi lượt (không tính lần dựng đầu):

| Giai đoạn | Chi phí theo | Ghi chú |
|---|---|---|
| recentchanges | số thay đổi / 500 request | độc lập kích thước corpus |
| describe | số ứng viên / 50 request | một lượt hằng tuần chỉ vài chục request |
| `--full-scan` | số trang / 50 request, cộng số category | chỉ đọc metadata; corpus 10× vẫn là hàng trăm request, tính theo `min_interval_seconds` |
| fetch + ảnh | số trang đổi × (1 request parse + ảnh mới), ≥ 1 giây/request | nút cổ chai chính, do giới hạn lịch sự |
| clean, chunk | số trang đổi (CPU) | vài trang một lô, bộ nhớ không tăng theo corpus |
| encode + upsert | số chunk của trang đổi, mẻ `RAG_BATCH_SIZE` | CPU E5-small; không encode lại chunk trang không đổi |
| state | O(số trang) | 4.164 mục là vài trăm KB |

Cơ chế giữ chi phí tỉ lệ với thay đổi: lô cố định, state ghi theo lô (bộ nhớ không phụ thuộc corpus), upsert id ổn định (không cần đọc index để biết chunk nào đổi), xoá thừa theo bộ lọc `document_id` có payload index, `--max-pages` để chia nhỏ một đợt thay đổi lớn (vd. wiki cập nhật lớn sau patch hoặc DLC).

Khi corpus lớn gấp 10 (khoảng 40 nghìn trang, hơn 300 nghìn chunk):

- **Qdrant**: dense 384 chiều float32 xấp xỉ 1,5 KB mỗi point, nên vector chiếm vài trăm MB cộng sparse và payload. Đo lại RAM VPS; bật `on_disk` cho vector/payload hoặc quantization nếu thiếu RAM, và chụp snapshot trước đợt re-index lớn.
- **Crawl**: giữ 1 request/giây là giới hạn chính; không tăng song song với cùng host. Chạy `update` hằng ngày thay vì hằng tuần để mỗi lượt nhỏ, và dùng `--max-pages` để lượt không vượt giờ thấp điểm.
- **`--full-scan`**: vẫn rẻ (metadata) nhưng chạy mỗi tháng là đủ; nếu cần nhanh hơn, quét theo category có đánh dấu thay đổi.
- **State**: vẫn là file JSON đến cỡ vài trăm nghìn mục; vượt thì chuyển sang bảng PostgreSQL (`documents.revision_id` đã có sẵn, chỉ cần thêm `watermark`).
- **Encode**: tách tiến trình encode khỏi tiến trình crawl (hàng đợi lô), hoặc dùng GPU, nếu đợt thay đổi lớn làm lượt chạy vượt cửa sổ.
- **PostgreSQL**: chỉ số hiện có (`document_id`, `ordinal`) đủ; thay đổi chỉ chạm chunk của trang đổi.

Giới hạn đã biết:

- Đổi chính sách clean/chunk (`[chunk]`, `[filter]`, version trong mã) không tự được phát hiện, vì revision trang không đổi. Khi đó dựng toàn bộ vào **collection mới**, kiểm eval, rồi đổi `RAG_COLLECTION`. State cần bootstrap lại từ bản mới.
- Chỉ theo dõi namespace 0. Trang chỉ đổi category (không sửa nội dung) có thể không xuất hiện trong recentchanges; `--full-scan` định kỳ bù phần này. Trang rời phạm vi category mà vẫn tồn tại không bị gỡ (chỉ gỡ khi bị xoá, thành redirect hoặc dính tựa ngoài phạm vi).
- Bộ lọc admission (`CorpusPolicy`) loại chunk ngôn ngữ khác `RAG_LANGUAGES` khỏi Qdrant nhưng PostgreSQL vẫn giữ, giống đường nạp toàn bộ.
- Lần đầu trên VPS cần `data/` và state được mang theo (mount `./backend/data`).
- Lệnh `update` chưa được chạy với mạng, Qdrant và PostgreSQL thật; kiểm bằng `--dry-run` trước khi bật cron.
