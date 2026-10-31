# Index Beast — Techstack (v1.4)

| | |
|---|---|
| Trạng thái | Chốt 2026-10-17; cập nhật 2026-10-31 theo code sau Sprint 2 |
| Phạm vi | Elden Ring base game + Shadow of the Erdtree (ngoại lệ ADR-004 ngày 29/10); lore, gameplay, build khi có bằng chứng. Cần chốt bằng CHANGE-REQ |
| Quy mô mục tiêu | Vài trăm người dùng, ~50 đồng thời lúc cao điểm |
| Hạ tầng | 1 VPS 4 vCPU / 8 GB, Ubuntu 24.04 LTS, Docker Compose |
| Nguyên tắc | Tối giản, pin cứng phiên bản, nâng cấp qua PR nhãn `deps` |

## 1. Stack

| Tầng | Công nghệ | Phiên bản |
|---|---|---|
| Ngôn ngữ backend | Python + venv + pip | 3.11.9 · pip 26.2.1 |
| API | FastAPI + Uvicorn (2 worker) | 0.143.3 · 0.54.0 |
| LLM | DeepSeek `deepseek-flash` (V4.1-Flash-1017), tắt thinking | API |
| LLM chấm eval | DeepSeek `deepseek-v4-pro` | API |
| Điều phối LLM/RAG | LangChain: langchain-core (LCEL), langchain-deepseek (`ChatDeepSeek`) | 1.7.1 · 1.1.1 |
| SDK LLM | openai (định dạng OpenAI của DeepSeek, dùng bên dưới LangChain) | 3.33.0 |
| Embedding | `intfloat/multilingual-e5-small` (ONNX, 384 chiều) | — |
| BM25 | `Qdrant/bm25` (sparse vector) | — |
| Reranker | `BAAI/bge-reranker-base` (ONNX), **chưa bật**: code dùng `NoReranker` giữ thứ tự RRF | — |
| Chạy model | fastembed (onnxruntime, không PyTorch) | 0.9.0 |
| Đếm token E5 | tokenizers (tokenizer của e5, giới hạn 512) | 0.23.3 |
| Tìm kiếm web dự phòng | DuckDuckGo qua thư viện ddgs (`backend="duckduckgo"`), **chưa triển khai** (S4) | 9.16.0 |
| Vector DB | Qdrant · qdrant-client | v1.19.2 · 1.19.1 |
| Database | PostgreSQL | 18.6 |
| ORM · driver · migration | SQLAlchemy async · asyncpg · Alembic | 2.1.5 · 0.32.0 · 1.20.0 |
| Cache · rate-limit | Redis · redis-py (rate-limit `/chat` đã dùng; cache chưa) | 8.10.2 · 8.1.0 |
| Làm sạch · ảnh | BeautifulSoup · Pillow (kiểm định dạng ảnh crawl và ảnh trả về) | 4.15.0 · 12.3.0 |
| Runtime JS | Node.js LTS | 24.22.0 |
| TypeScript | chỉ dùng `tsc --noEmit` | 6.0.3 |
| Web | React · Vite · Tailwind CSS · react-router | 19.3.1 · 8.3.4 · 4.3.3 · 8.4.0 |
| Bot | discord.js | 14.27.0 |
| Proxy · HTTPS · web tĩnh | Caddy | 2.11.7 |
| Test JS | `node --test` chạy thẳng file `.ts` (không thêm test framework) | Node 24 |
| Chất lượng mã | ruff (Python), Prettier (TS), pre-commit | 0.17.1 · 3.9.10 · 4.7.0 |
| CI | GitHub Actions (lint + test + kiểm `docs/api/openapi.json`) | — |

## 2. Quyết định chính

| Chủ đề | Quyết định |
|---|---|
| LLM | `deepseek-flash` cho cả viết lại truy vấn và sinh câu trả lời, gọi qua LangChain `ChatDeepSeek`. Thinking tắt mặc định (`RAG_THINKING_ENABLED`). Câu trả lời RAG là JSON (`answer`, `evidence`), backend kiểm trích dẫn nguyên văn. Base URL `https://api.deepseek.com`. Code gọi LLM gom trong `app/adapters/llm.py`. LangSmith (đi kèm LangChain) luôn tắt tracing. |
| Chế độ chat | `CHAT_MODE`: `mock` (mặc định, dữ liệu giả), `llm_only`, `rag`. Không tự chuyển chế độ khi lỗi. |
| Bảo vệ API | Ở `llm_only`/`rag`: giới hạn `RATE_LIMIT_PER_MINUTE` theo IP (web) hoặc `external_ref` (bot) bằng Redis; kênh `discord` cần `X-Service-Token`; hạn `CHAT_TIMEOUT_SECONDS` (45 s) cho một câu hỏi, bot chờ 60 s. |
| Truy vấn tiếng Việt | Hiện chỉ index chunk tiếng Anh (`RAG_LANGUAGES=en`). Bước viết lại/dịch truy vấn có sẵn nhưng tắt mặc định (`RAG_REWRITE_ENABLED=false`), nên câu hỏi tiếng Việt đi thẳng vào e5 đa ngôn ngữ và BM25. |
| Hybrid search | Qdrant Query API: prefetch dense 30 + bm25 30 (`RAG_PREFETCH`) → RRF → chọn tối đa 5 đoạn (`RAG_TOP_K`) trong 12.000 ký tự ngữ cảnh. Không dùng Elasticsearch. |
| Rerank | Kế hoạch: `bge-reranker-base` chạy trong threadpool, mỗi worker tối đa 1 lượt; p95 > 800 ms thì đổi `Xenova/ms-marco-MiniLM-L-6-v2`. Hiện chưa bật, chưa có số đo. |
| Tìm web khi thiếu ngữ cảnh | Chỉ chạy khi điểm rerank cao nhất thấp hơn ngưỡng. Tìm DuckDuckGo với `query_en` (tối đa 5 kết quả), chỉ giữ kết quả thuộc allowlist (`eldenring.wiki.gg`, `en.wikipedia.org`). Tải 2 trang đầu bằng httpx (timeout 4 s), làm sạch bằng BeautifulSoup, chunk, rerank chung với kết quả cũ rồi mới sinh câu trả lời. Câu trả lời gắn nhãn "nguồn web". Lưu cache Redis 7 ngày, toàn hệ thống tối đa 1 lượt tìm/giây. Nếu bị chặn hoặc lỗi thì trả lời "không tìm thấy". URL tìm được ghi vào log để lần ingest sau bổ sung vào kho. |
| e5-small | Nạp bằng `TextEmbedding.add_custom_model` từ `onnx/model.onnx`. Bắt buộc tiền tố `query:` / `passage:`. |
| Redis | Dùng chung cho các worker: rate-limit (`INCR` + `EXPIRE`, cửa sổ 1 phút) đã có; cache câu trả lời (TTL 24h) chưa làm. Không dùng làm hàng đợi. |
| Ảnh minh họa | `GET /api/v1/images/{id}` chỉ phục vụ ảnh cục bộ đã kiểm (theo hash), không proxy URL ngoài. |
| Ingestion | Chạy bằng CLI: `docker compose run --rm api python -m ingest crawl\|index\|update`. Cập nhật hằng tuần bằng cron. |
| PostgreSQL 18 | Mount volume vào `/var/lib/postgresql`, không phải `.../data`. |
| Caddy | HTTPS tự động. Phục vụ build React bằng `file_server`. Proxy `/api/*`, đặt `flush_interval -1` để SSE không bị đệm. |
| Web | Một file `api.ts` viết tay theo `docs/api/openapi.json`. SSE bằng `fetch` + `ReadableStream`. Tailwind cùng vài file CSS riêng cho giao diện. UUID có dự phòng `getRandomValues` để chạy qua HTTP LAN/VPN. |
| Bot | Node 24 chạy thẳng file `.ts` (không dùng `enum`/`namespace`). Đọc biến môi trường bằng `--env-file`. |
| Deploy | `git pull && docker compose up -d --build`. Rollback bằng `git checkout <tag>`. |
| Giám sát | `healthcheck` + `restart: unless-stopped`. Log lưu trong bảng `messages` của PostgreSQL. |

**Không dùng:** PyTorch khi chạy production, LlamaIndex, Elasticsearch, Nginx, Kubernetes, hàng đợi job (arq/Celery), registry image, Prometheus/Grafana, ESLint, TypeScript 7.

## 3. Phiên bản thư viện

`backend/requirements.txt`

```text
fastapi==0.143.3
uvicorn[standard]==0.54.0
pydantic-settings==2.16.0
sqlalchemy[asyncio]==2.1.5
asyncpg==0.32.0
alembic==1.20.0
qdrant-client==1.19.1
fastembed==0.9.0
openai==3.33.0
langchain-core==1.7.1
langchain-deepseek==1.1.1
redis==8.1.0
ddgs==9.16.0
httpx==0.28.1
beautifulsoup4==4.15.0
pillow==12.3.0
tokenizers==0.23.3
```

`backend/requirements-dev.txt`

```text
-r requirements.txt
pytest==9.1.1
pytest-asyncio==1.4.0
ruff==0.17.1
locust==2.46.7
pre-commit==4.7.0
```

Phụ thuộc gián tiếp được khoá trong `constraints.txt`, sinh bằng `pip freeze` (gồm langchain-openai, langsmith do LangChain kéo theo). Lệnh cài: `pip install -r requirements-dev.txt -c constraints.txt`. **Cài lại sau mỗi lần pull có đổi `requirements*.txt`.**

| Web (npm) | Phiên bản | Bot (npm) | Phiên bản |
|---|---|---|---|
| react, react-dom | 19.3.1 | discord.js | 14.27.0 |
| react-router | 8.4.0 | typescript (dev) | 6.0.3 |
| react-markdown, remark-gfm | 10.1.0, 4.0.1 | prettier (dev) | 3.9.10 |
| vite, @vitejs/plugin-react | 8.3.4, 6.1.2 | | |
| tailwindcss, @tailwindcss/vite | 4.3.3 | | |
| typescript, prettier (dev) | 6.0.3, 3.9.10 | | |

## 4. Triển khai

```
Internet ─► caddy ─┬─► web tĩnh (React build)
                   └─► api (FastAPI ×2 worker) ─┬─► postgres
bot (discord.js) ──────► api                    ├─► qdrant
                                                ├─► redis
                                                ├─► DeepSeek API
                                                └─► DuckDuckGo (khi thiếu ngữ cảnh, S4)
```

Hội thoại hiện giữ trong RAM của từng worker: khi chạy chế độ live, đặt `API_WORKERS=1` cho tới khi chuyển sang PostgreSQL (S3).

| Container | Image | `mem_limit` |
|---|---|---|
| caddy | `caddy:2.11.7-alpine` | 64 MB |
| api | `python:3.11.9-slim-bookworm` | 3 GB |
| postgres | `postgres:18.6-bookworm` | 1 GB |
| qdrant | `qdrant/qdrant:v1.19.2` | 1 GB |
| redis | `redis:8.10.2-alpine` (`maxmemory 128mb`, `allkeys-lru`) | 192 MB |
| bot | `node:24.22.0-bookworm-slim` | 192 MB |
| ingest (chỉ khi chạy) | dùng image api | 1.5 GB |
| **Tổng** | | **≈ 6.9 GB** |

Model ONNX tải sẵn vào `/models` lúc build image.

## 5. Mục tiêu hiệu năng & chi phí

| Chỉ số | Mục tiêu |
|---|---|
| Token đầu tiên p95 | < 3.5 s |
| Câu trả lời hoàn chỉnh p95 | < 10 s |
| Rerank 30 đoạn p95 | < 800 ms |
| Tải | 50 người dùng đồng thời (đo bằng locust ở S5) |
| Chi phí LLM | ≈ $30/tháng cho 1.000 câu/ngày |

Giá `deepseek-flash` (mỗi 1M token, giờ thấp điểm / cao điểm): input $0.15 / $0.30, cache hit $0.003 / $0.006, output $0.60 / $1.20. Cao điểm là 08–11h và 13–17h giờ Việt Nam, thứ Hai–thứ Sáu; nên chạy eval ngoài khung giờ này.

## 6. Nguồn dữ liệu

| Nguồn | Vai trò | Giấy phép |
|---|---|---|
| eldenring.wiki.gg (MediaWiki API) | Nguồn chính: base game + Shadow of the Erdtree (4.164 trang) | CC BY-SA 4.0, bắt buộc ghi nguồn; ảnh chưa rõ giấy phép giữ `unknown_review_required` |
| eldenring.fanapis.com | Danh sách thực thể | Dùng có chừng mực |
| Wikipedia | Thông tin tổng quan | CC BY-SA 4.0 |

Corpus Sprint 2 dùng `game_scope=elden_ring`; `release_scope` (base/SotE candidate, unknown) là nhãn heuristic chưa review. Nightreign và Tarnished Edition vẫn ngoài phạm vi.

Không crawl Fandom và Fextralife. Giới hạn crawl ≤ 1 request/giây, User-Agent có email liên hệ.

## 7. Rủi ro

| Rủi ro | Dự phòng |
|---|---|
| CPU quá tải khi rerank | Đổi sang MiniLM, giảm top-N xuống 20, tăng thời gian giữ cache |
| Chất lượng câu trả lời chưa đạt | Bật thinking `reasoning_effort="low"` cho bước sinh câu trả lời |
| DeepSeek gián đoạn hoặc đổi giá | Sửa `llm.py` để đổi nhà cung cấp |
| DuckDuckGo chặn IP của VPS (không có API chính thức, có thể bắt CAPTCHA) | Bỏ qua bước tìm web và trả lời "không tìm thấy". Tăng TTL cache. Có thể tắt hẳn bằng biến `WEB_FALLBACK_ENABLED=false` |

## 8. ADR

| ADR | Nội dung | Trạng thái |
|---|---|---|
| 001 | LLM `deepseek-flash`, eval bằng `deepseek-v4-pro` | Chốt |
| 002 | Reranker `bge-reranker-base`, dự phòng MiniLM | Chốt, benchmark ở S1 |
| 003 | Chunk tối đa 450 token theo heading, overlap 50 | Đề xuất (đã dùng cho corpus S2) |
| 004 | Phạm vi lore: Elden Ring base game | Chấp nhận; ngoại lệ base + SotE ngày 29/10 |
| 005 | Web ẩn danh ở v1 | Đề xuất |
| 006 | Trả lời theo ngôn ngữ người hỏi, giữ tên riêng tiếng Anh | Chốt |
| 007 | Tìm web dự phòng bằng DuckDuckGo, giới hạn theo allowlist domain | Chốt |
