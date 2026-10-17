# Index Beast — Techstack (v1.3)

| | |
|---|---|
| Trạng thái | Đã chốt — 2026-10-17 |
| Phạm vi | Chỉ lore Elden Ring base game; loại trừ mọi DLC và Elden Ring Nightreign |
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
| SDK LLM | openai (định dạng OpenAI của DeepSeek) | 3.33.0 |
| Embedding | `intfloat/multilingual-e5-small` (ONNX, 384 chiều) | — |
| BM25 | `Qdrant/bm25` (sparse vector) | — |
| Reranker | `BAAI/bge-reranker-base` (ONNX) | — |
| Chạy model | fastembed (onnxruntime, không PyTorch) | 0.9.0 |
| Tìm kiếm web dự phòng | DuckDuckGo qua thư viện ddgs (`backend="duckduckgo"`) | 9.16.0 |
| Vector DB | Qdrant · qdrant-client | v1.19.2 · 1.19.1 |
| Database | PostgreSQL | 18.6 |
| ORM · driver · migration | SQLAlchemy async · asyncpg · Alembic | 2.1.5 · 0.32.0 · 1.20.0 |
| Cache · rate-limit | Redis · redis-py | 8.10.2 · 8.1.0 |
| Runtime JS | Node.js LTS | 24.22.0 |
| TypeScript | chỉ dùng `tsc --noEmit` | 6.0.3 |
| Web | React · Vite · Tailwind CSS · react-router | 19.3.1 · 8.3.4 · 4.3.3 · 8.4.0 |
| Bot | discord.js | 14.27.0 |
| Proxy · HTTPS · web tĩnh | Caddy | 2.11.7 |
| CI | GitHub Actions (lint + test) | — |

## 2. Quyết định chính

| Chủ đề | Quyết định |
|---|---|
| LLM | `deepseek-flash` cho cả viết lại truy vấn và sinh câu trả lời. Gửi kèm `extra_body={"thinking": {"type": "disabled"}}`. Bước viết lại truy vấn dùng `response_format: json_object`. Base URL `https://api.deepseek.com`. Code gọi LLM gom trong 1 file `llm.py`. |
| Truy vấn tiếng Việt | LLM dịch câu hỏi sang tiếng Anh, sau đó chạy hybrid search. Embedding đa ngôn ngữ dùng làm lớp dự phòng. |
| Hybrid search | Qdrant Query API: prefetch dense 40 + bm25 40 → RRF → top 30. Không dùng Elasticsearch. |
| Rerank | `bge-reranker-base` chạy trong threadpool, mỗi worker tối đa 1 lượt cùng lúc. Nếu p95 > 800 ms thì đổi sang `Xenova/ms-marco-MiniLM-L-6-v2`. |
| Tìm web khi thiếu ngữ cảnh | Chỉ chạy khi điểm rerank cao nhất thấp hơn ngưỡng. Tìm DuckDuckGo với `query_en` (tối đa 5 kết quả), chỉ giữ kết quả thuộc allowlist (`eldenring.wiki.gg`, `en.wikipedia.org`). Tải 2 trang đầu bằng httpx (timeout 4 s), làm sạch bằng BeautifulSoup, chunk, rerank chung với kết quả cũ rồi mới sinh câu trả lời. Câu trả lời gắn nhãn "nguồn web". Lưu cache Redis 7 ngày, toàn hệ thống tối đa 1 lượt tìm/giây. Nếu bị chặn hoặc lỗi thì trả lời "không tìm thấy". URL tìm được ghi vào log để lần ingest sau bổ sung vào kho. |
| e5-small | Nạp bằng `TextEmbedding.add_custom_model` từ `onnx/model.onnx`. Bắt buộc tiền tố `query:` / `passage:`. |
| Redis | Dùng chung cho 2 worker: rate-limit (`INCR` + `EXPIRE`) theo IP, user và guild; cache câu trả lời (TTL 24h). Không dùng làm hàng đợi. |
| Ingestion | Chạy bằng CLI: `docker compose run --rm api python -m ingest crawl\|index\|update`. Cập nhật hằng tuần bằng cron. |
| PostgreSQL 18 | Mount volume vào `/var/lib/postgresql`, không phải `.../data`. |
| Caddy | HTTPS tự động. Phục vụ build React bằng `file_server`. Proxy `/api/*`, đặt `flush_interval -1` để SSE không bị đệm. |
| Web | Một file `api.ts` viết tay. SSE bằng `fetch` + `ReadableStream`. Chỉ dùng Tailwind thuần. |
| Bot | Node 24 chạy thẳng file `.ts` (không dùng `enum`/`namespace`). Đọc biến môi trường bằng `--env-file`. |
| Deploy | `git pull && docker compose up -d --build`. Rollback bằng `git checkout <tag>`. |
| Giám sát | `healthcheck` + `restart: unless-stopped`. Log lưu trong bảng `messages` của PostgreSQL. |

**Không dùng:** PyTorch khi chạy production, LangChain/LlamaIndex, Elasticsearch, Nginx, Kubernetes, hàng đợi job (arq/Celery), registry image, Prometheus/Grafana, ESLint, TypeScript 7.

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
redis==8.1.0
ddgs==9.16.0
httpx==0.28.1
beautifulsoup4==4.15.0
```

`backend/requirements-dev.txt`

```text
-r requirements.txt
pytest==9.1.1
pytest-asyncio==1.4.0
ruff==0.17.1
locust==2.46.7
```

Phụ thuộc gián tiếp được khoá trong `constraints.txt`, sinh bằng `pip freeze`. Lệnh cài: `pip install -r requirements.txt -c constraints.txt`.

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
                                                └─► DuckDuckGo (khi thiếu ngữ cảnh)
```

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
| eldenring.wiki.gg (MediaWiki API) | Nguồn chính: chỉ lore Elden Ring base game | CC BY-SA 4.0, bắt buộc ghi nguồn |
| eldenring.fanapis.com | Danh sách thực thể | Dùng có chừng mực |
| Wikipedia | Thông tin tổng quan | CC BY-SA 4.0 |

Chỉ thu thập và index nội dung base game (`game_scope=base`). Loại các trang/section DLC và Nightreign, kể cả khi cùng domain wiki.gg; tìm web dự phòng cũng phải áp dụng bộ lọc phạm vi này.

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
| 003 | Chunk 350–450 token theo heading, overlap 50 | Đề xuất |
| 004 | Chỉ lore Elden Ring base game; loại trừ mọi DLC và Elden Ring Nightreign | Chốt theo yêu cầu nhóm |
| 005 | Web ẩn danh ở v1 | Đề xuất |
| 006 | Trả lời theo ngôn ngữ người hỏi, giữ tên riêng tiếng Anh | Chốt |
| 007 | Tìm web dự phòng bằng DuckDuckGo, giới hạn theo allowlist domain | Chốt |
