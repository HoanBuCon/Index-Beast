# Index Beast — Kiến trúc thư mục

| | |
|---|---|
| Trạng thái | Khung xương — 2026-10-17 |
| Mục tiêu | Dễ mở rộng, dễ debug; crawl → lọc → xử lý → index tách rời từng bước |

**Phạm vi:** chỉ lore Elden Ring base game. Không thu thập/index nội dung DLC (bao gồm Shadow of the Erdtree) hoặc Elden Ring Nightreign. `game_scope=base` là ràng buộc của cả ingestion, retrieval và web fallback; trang có nội dung trộn phải lọc theo section, phần chưa xác định cần kiểm tra thủ công.

Quy trình Git áp dụng theo [quy_uoc.md](quy_uoc.md): feature tách từ develop, PR về develop và Mentor review trước khi merge.

## 1. Cây thư mục

```
Index-Beast/
├─ backend/
│  ├─ core/                 # DÙNG CHUNG (online + offline), không I/O mạng ngoài DB/Qdrant
│  │  ├─ config.py          # toàn bộ tham số
│  │  ├─ logging.py         # log JSON + request_id / job_id
│  │  ├─ errors.py
│  │  ├─ ids.py             # id ổn định → upsert idempotent
│  │  ├─ types.py           # hợp đồng dữ liệu giữa các bước
│  │  ├─ db/                # session, models, repositories
│  │  ├─ vector/            # schema collection, store (upsert, hybrid search)
│  │  ├─ encoders/          # e5-small, bm25, reranker (ONNX)
│  │  └─ text/              # html_clean, sections, normalize, chunking (thuần, không I/O)
│  │
│  ├─ app/                  # ONLINE — API
│  │  ├─ main.py, context.py
│  │  ├─ api/               # HTTP: routes/, schemas/, deps.py, router.py
│  │  ├─ services/          # nghiệp vụ: chat_service, feedback_service
│  │  ├─ rag/               # pipeline, rewrite, retriever, reranker, generator, web_fallback, trace, prompts/
│  │  └─ adapters/          # bên ngoài: llm (DeepSeek), redis, web_search (DuckDuckGo)
│  │
│  ├─ ingest/               # OFFLINE — pipeline dữ liệu
│  │  ├─ __main__.py        # CLI
│  │  ├─ config/sources.toml
│  │  ├─ settings.py, jobs.py
│  │  ├─ sources/           # plugin nguồn: base, wikigg, wikipedia, fanapis
│  │  ├─ crawl/             # 1. tải thô
│  │  ├─ filter/            # 2. giữ/bỏ + lý do, khử trùng lặp
│  │  ├─ transform/         # 3. làm sạch + metadata
│  │  ├─ chunk/             # 4. chia đoạn
│  │  ├─ index/             # 5. embed + ghi Qdrant/PG
│  │  ├─ entities/          # alias thực thể
│  │  └─ debug/             # inspect_page, report
│  │
│  ├─ eval/                 # golden_set.jsonl, retrieval.py, answer.py, reports/
│  ├─ migrations/           # Alembic
│  ├─ tests/                # unit/, integration/, fixtures/
│  └─ data/                 # (gitignore) artifact từng bước ingest — xem §3
│
├─ web/src/                 # api/, pages/, components/{chat,layout}/, hooks/, lib/, styles/
├─ bot/src/                 # api/, commands/, interactions/, utils/, deploy-commands.ts
├─ infra/                   # Caddyfile, caddy.Dockerfile
├─ scripts/                 # deploy.sh, backup.sh, ingest-weekly.sh
├─ docs/  planning/
├─ docker-compose.yml  .env.example  .github/workflows/ci.yml
```

## 2. Quy tắc phụ thuộc

```
app/api → app/services → app/rag → app/adapters ─┐
                                                 ├─► core/
ingest/<bước> ───────────────────────────────────┘
```

| Quy tắc | Lý do |
|---|---|
| `core/` không import `app/` hay `ingest/` | Dùng chung được, test độc lập |
| `app/` và `ingest/` không import lẫn nhau | Online và offline triển khai, chạy, mở rộng riêng |
| `api/` chỉ parse request + gọi service | Đổi giao thức (REST/SSE/WebSocket) không đụng nghiệp vụ |
| Gọi hệ thống ngoài chỉ qua `adapters/` hoặc `core/{db,vector,encoders}` | Đổi DeepSeek/DuckDuckGo/Redis chỉ sửa 1 file; test thay bằng bản giả |
| `core/text/` là hàm thuần | Ingest và web fallback dùng chung một cách làm sạch/chunk |
| Mọi tham số ở `core/config.py` / `sources.toml` | Tinh chỉnh không sửa code |

## 3. Pipeline dữ liệu (offline)

Mỗi bước **đọc artifact của bước trước, ghi artifact của mình**. Vì vậy có thể chạy lại riêng một bước (ví dụ chỉ chunk lại khi đổi kích thước) và mở file ra xem khi debug.

| # | Bước | Lệnh | Đầu vào | Đầu ra (artifact) |
|---|---|---|---|---|
| 1 | crawl | `python -m ingest crawl --source wikigg` | API nguồn | `data/raw/<source>/<id>.json` (HTML, revid, categories, url) |
| 2 | filter | `... filter` | raw | `data/filtered/<source>/decisions.jsonl` (id, keep, lý do) |
| 3 | transform | `... transform` | raw + decisions | `data/processed/<source>/<id>.json` (sections + metadata) |
| 4 | chunk | `... chunk` | processed | `data/chunks/<source>/<id>.jsonl` |
| 5 | index | `... index` | chunks | Qdrant `lore_chunks` + PG `documents`/`chunks` |
| — | run | `... run` | | chạy 1→5 |
| — | update | `... update` | | crawl trang có revision mới → 2→5 cho trang đó (cron hằng tuần) |

Tuỳ chọn chung: `--source`, `--limit N`, `--page TITLE`, `--dry-run`.

Tính chất bắt buộc của mỗi bước:
- **Idempotent:** chạy lại cho cùng kết quả. id sinh từ `core/ids.py`; bước index so `content_hash` trước khi ghi.
- **Incremental:** bỏ qua phần không đổi (revision ở bước crawl, hash ở bước index).
- **Có report:** mỗi lần chạy ghi một dòng vào bảng `ingestion_jobs` và file `data/reports/<job_id>.json` (số lượng vào/ra/lỗi, thời gian).

## 4. Debug

| Muốn biết | Cách |
|---|---|
| Vì sao một trang bị bỏ | `data/filtered/<source>/decisions.jsonl` |
| Trang được làm sạch / chunk ra sao | `python -m ingest inspect --page "Starscourge Radahn"` (in output qua từng bước) |
| Tình trạng dữ liệu tổng thể | `python -m ingest report` (số trang/chunk, phân bố độ dài, lý do lọc) |
| Vì sao một câu trả lời sai | `messages.trace` (query viết lại, chunk + điểm từng bước, độ trễ) → `/api/v1/admin/trace/{message_id}` |
| Theo một request qua web/bot → api | Header `X-Request-ID`, có trong mọi dòng log |
| Lỗi làm sạch với một trang cụ thể | Lưu HTML trang đó vào `tests/fixtures/` và viết test |
| Chất lượng có tốt lên không | `eval/retrieval.py`, `eval/answer.py` → bảng `eval_runs` |

## 5. Mở rộng

| Nhu cầu | Làm gì |
|---|---|
| Thêm nguồn dữ liệu | 1 file `ingest/sources/<tên>.py` (implement `base.Source`) + 1 mục `[sources.<tên>]` trong `sources.toml` |
| Thêm quy tắc lọc | `ingest/filter/rules.py` hoặc thêm vào `[filter]` trong `sources.toml` |
| Thêm metadata (spoiler, nhân vật…) | `ingest/transform/metadata.py` + payload index trong `core/vector/schema.py` |
| Đổi chiến lược chunk | Sửa `[chunk]` → `ingest chunk` + `ingest index` (không cần crawl lại) |
| Đổi LLM / search engine | `app/adapters/llm.py` / `app/adapters/web_search.py` |
| Thêm bước RAG | Module mới trong `app/rag/`, gọi từ `pipeline.py`, ghi thời gian vào trace |
| Thêm kênh (Telegram, Messenger…) | Client mới gọi `/api/v1/chat` với `channel` và `external_ref` riêng |
| Tăng tải | API stateless (state ở PG/Redis/Qdrant): tăng worker hoặc instance; tách ingest sang máy khác vì chỉ dùng chung `core/` |

Thêm nguồn dữ liệu chỉ được bổ sung lore base game; hỗ trợ DLC hoặc Nightreign là thay đổi phạm vi và không thuộc kế hoạch hiện tại.

## 6. Thứ tự dựng (Sprint 1–2)

1. `core/config.py`, `core/logging.py`, `app/main.py`, `/health` → chạy được container.
2. `core/types.py` → cả team thống nhất hợp đồng dữ liệu trước khi code các bước.
3. `ingest/sources/wikigg.py` + `crawl/` → có `data/raw/`.
4. `filter/` → `transform/` → `chunk/` → `index/`, kiểm tra từng bước bằng `inspect`.
5. `app/rag/*` → `services/chat_service.py` → `api/routes/chat.py`.
