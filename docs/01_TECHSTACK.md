# Index Beast — Techstack (v1.6)

| | |
|---|---|
| Trạng thái | Chốt 2026-10-17; cập nhật 2026-11-08 theo code cuối Sprint 3 (`develop` `cb2a358`, kèm PR #67, #79, #80 ghi rõ ở từng dòng) |
| Phạm vi | Elden Ring base game + Shadow of the Erdtree; lore và gameplay/build khi có bằng chứng (đã chốt, thẻ CHANGE-REQ ở Sprint 3) |
| Quy mô mục tiêu | Vài trăm người dùng, ~50 đồng thời lúc cao điểm |
| Hạ tầng | 1 VPS 4 vCPU / 8 GB, Ubuntu 24.04 LTS, Docker Compose Staging cùng cấu hình (xem `docs/staging.md`). |
| Nguyên tắc | Tối giản, pin cứng phiên bản, nâng cấp qua PR nhãn `deps` |

## 1. Stack

| Tầng | Công nghệ | Phiên bản |
|---|---|---|
| Ngôn ngữ backend | Python + venv + pip | 3.11.9 · pip 26.2.1 |
| API | FastAPI + Uvicorn (2 worker) | 0.143.3 · 0.54.0 |
| LLM | DeepSeek `deepseek-flash` (V4.1-Flash-1017), tắt thinking | API |
| LLM chấm eval | DeepSeek `deepseek-v4-pro` | API |
| Điều phối LLM/RAG | LangChain: langchain-core (LCEL), langchain-deepseek (`ChatDeepSeek`) | 1.7.1 · 1.1.1 |
| Đồ thị xử lý RAG · agent | LangGraph: `StateGraph` cho bước chuẩn bị truy vấn, bước sinh câu trả lời và node `tool_agent` | 1.2.20 |
| SDK LLM | openai (định dạng OpenAI của DeepSeek, dùng bên dưới LangChain) | 3.33.0 |
| Embedding | `intfloat/multilingual-e5-small` (ONNX, 384 chiều) | — |
| BM25 | `Qdrant/bm25` (sparse vector) | — |
| Reranker | `BAAI/bge-reranker-base` (ONNX), **chưa bật**: code dùng `NoReranker` giữ thứ tự RRF | — |
| Chạy model | fastembed (onnxruntime, không PyTorch) | 0.9.0 |
| Đếm token E5 | tokenizers (tokenizer của e5, giới hạn 512) | 0.23.3 |
| Tìm kiếm web dự phòng | Tavily Search + Extract qua httpx (`app/adapters/tavily.py`), chế độ `off`/`auto`/`always`. Thay DuckDuckGo (ADR-008) | API |
| Vector DB | Qdrant · qdrant-client | v1.19.2 · 1.19.1 |
| Database | PostgreSQL | 18.6 |
| ORM · driver · migration | SQLAlchemy async · asyncpg · Alembic | 2.1.5 · 0.32.0 · 1.20.0 |
| Cache · rate-limit | Redis · redis-py (rate-limit `/chat` đã dùng; cache chưa) | 8.10.2 · 8.1.0 |
| Bộ nhớ hội thoại | PostgreSQL (`conversation_runtime`, `conversation_memories`, migration `0002`) là nguồn sự thật; Qdrant collection `conversation_memories` (dense E5, 384 chiều) chỉ là chỉ mục dẫn xuất | — |
| Trace và số đo | `messages.trace` (JSONB) và cột `rewritten_query`, `latency_ms`, `tokens_in/out`; `GET /api/v1/admin/trace/{id}` với `X-Admin-Token` (PR #79) | — |
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
| LLM | `deepseek-flash` cho cả viết lại truy vấn và sinh câu trả lời, gọi qua LangChain `ChatDeepSeek`. Thinking tắt mặc định (`RAG_THINKING_ENABLED`). Câu trả lời RAG là JSON (`answer`, `evidence`), backend kiểm trích dẫn nguyên văn. Base URL `https://api.deepseek.com`. Code gọi LLM gom trong `app/adapters/llm.py`. LangSmith (đi kèm LangChain) luôn tắt tracing. Đầu ra JSON hỏng/rỗng hoặc "thiếu bằng chứng nhưng có trích dẫn" được thử lại tối đa 1 lần không thinking (`RAG_FORMAT_RETRIES`, `app/rag/output.py`); không sửa nội dung, không nới kiểm trích dẫn. Từ Sprint 3 còn các lượt gọi riêng cho quyết định của agent, đánh giá bằng chứng và viết lại truy vấn: đo thử trên 25 và 20 câu cho khoảng 2–3 lượt gọi mỗi câu hỏi (chưa phải đo tải thật). |
| Chế độ chat | `CHAT_MODE`: `mock` (mặc định, dữ liệu giả), `llm_only`, `rag`. Không tự chuyển chế độ khi lỗi. `CHAT_PERSISTENCE`: `memory` (mặc định, hội thoại trong RAM) hoặc `postgres`. `CHAT_AGENT_ENABLED` và `CHAT_TOOL_AGENT_ENABLED` mặc định `true`. |
| Bảo vệ API | Ở `llm_only`/`rag`: giới hạn `RATE_LIMIT_PER_MINUTE` theo IP (web) hoặc `external_ref` (bot) bằng Redis; kênh `discord` cần `X-Service-Token`; hạn `CHAT_TIMEOUT_SECONDS` (45 s) cho một câu hỏi, bot chờ 60 s. `/api/v1/admin/*` cần `X-Admin-Token` (`ADMIN_TOKEN`) và tắt hẳn (404) khi chưa đặt (PR #79). |
| Truy vấn tiếng Việt | Chỉ index chunk tiếng Anh (`RAG_LANGUAGES=en`). Khi bật `RAG_REWRITE_ENABLED`, LLM viết lại thành câu tiếng Anh độc lập (giữ tên riêng, số liệu; timeout 8 s, tối đa 512 token); `RAG_QUERY_MODE=dual` truy vấn thêm câu gốc, gộp hai danh sách bằng RRF theo thứ hạng (`app/rag/query_plan.py`). Mặc định rewrite tắt: câu tiếng Việt đi thẳng vào e5 đa ngôn ngữ và BM25. Ngôn ngữ trả lời tách khỏi ngôn ngữ truy vấn. Khi agent bật (mặc định) mô hình quyết định có viết lại hay không; server vẫn kiểm giữ tên riêng, số, phủ định, mục tiêu và ý định (`app/rag/rewrite.py`, `app/rag/agent.py`). |
| Câu hỏi tổng quan | Câu rộng ("các boss trong Elden Ring") được nhận diện bằng từ khóa VI/EN, không gọi LLM (`app/rag/overview.py`, `RAG_OVERVIEW_ENABLED=true`): tối đa 2 truy vấn, ưu tiên trang/section tổng quan, trả lời theo nhóm có nguồn thay vì từ chối vì thiếu danh sách đầy đủ. |
| Hybrid search | Qdrant Query API: prefetch dense 30 + bm25 30 (`RAG_PREFETCH`) → RRF → chọn tối đa 5 đoạn (`RAG_TOP_K`) trong 12.000 ký tự ngữ cảnh. Tổng thời gian truy xuất tối đa 20 s (`RAG_RETRIEVAL_TIMEOUT_SECONDS`), chia đều cho các truy vấn. Không dùng Elasticsearch. |
| Rerank | Hiện chưa bật (`NoReranker`, giữ thứ tự RRF); bước đánh giá bằng chứng của agent thay cho ngưỡng điểm rerank. Kế hoạch cũ (`bge-reranker-base`, dự phòng MiniLM khi p95 > 800 ms) chưa có số đo; quyết định ở Sprint 4. |
| Tìm web khi thiếu ngữ cảnh | Tavily Search rồi Extract (`TAVILY_API_KEY`). Web có nút ba trạng thái OFF/ON/ALWAYS (`off`/`auto`/`always`), Discord luôn `auto`. Chỉ giữ URL thuộc allowlist `WEB_SEARCH_DOMAINS` (mặc định eldenring.wiki.gg, eldenring.wiki.fextralife.com, en.bandainamcoent.eu). `auto` chỉ tìm khi bước đánh giá bằng chứng báo thiếu (hạn 3 s), tối đa `WEB_SEARCH_MAX_RESULTS=3` kết quả, hạn 8 s. Đoạn trích được làm sạch (bỏ điều hướng, giữ bảng), qua cùng bước kiểm quote và trích dẫn như nguồn cục bộ, trả về với `Source.origin=web`. Mã DuckDuckGo cũ (`ddgs`, `web_fallback.py`) không còn được gọi. |
| Agent chọn tool có giới hạn | `CHAT_TOOL_AGENT_ENABLED`: mô hình chọn `local_search`, `web_search`, `source_snapshot`, `calculator`, `clarify`, `finish`/`stop` bằng structured output trong node LangGraph `tool_agent` (không phải native tool calling). Tối đa `CHAT_TOOL_STEPS=3` bước và `CHAT_TOOL_QUERIES=2` truy vấn mới mỗi bước. Server giữ schema, allowlist, ngân sách, chính sách corpus, nguồn và trích dẫn (`app/rag/tool_agent.py`, `docs/api/bounded-tool-agent.md`). Tắt cờ thì quay về đường cũ rewrite → hybrid → đánh giá → web. |
| Hội thoại và bộ nhớ ngữ nghĩa | Với `CHAT_PERSISTENCE=postgres`: lưu hội thoại, trạng thái làm việc (khóa lạc quan theo `revision`) và các mục nhớ chủ đề/sự kiện; recall bằng E5 dense ở collection riêng, lọc theo hội thoại và chủ sở hữu; dựng lại index từ PostgreSQL được. Lịch sử đưa vào viết lại chỉ gồm tối đa 3 lượt người dùng liên quan; câu trả lời cũ không thành nguồn kiến thức. Web giữ `conversation_token` để mở lại hội thoại (chủ sở hữu lưu dạng băm). Chi tiết: `docs/api/agent-semantic-memory.md`, `docs/api/langgraph-memory.md`. |
| Hỏi lại và gameplay | Tối đa 2 câu hỏi lại mỗi lượt, hết hạn sau 30 phút, trạng thái chỉ commit khi trả lời thành công. Kiến thức gameplay nhỏ `knowledge/gameplay.json` (`GAMEPLAY_KNOWLEDGE_ENABLED`). `build_math.py` chỉ kiểm phép chia chỉ số, không phải bộ tối ưu AR/DPS. |
| Kiểm chứng câu trả lời | JSON `answer`/`evidence`; đoạn trích nguyên văn do server cấp ID (`quote_id`), mô hình không tự chép. Trích dẫn `[n]` phải khớp tập bằng chứng; đoạn không có trích dẫn bị bỏ thay vì trả 502 (PR #67); lỗi giao thức trích dẫn sinh lại tối đa `RAG_FORMAT_RETRIES=1` lần. Đây là kiểm tra hình thức, chưa chứng minh câu trả lời được nguồn suy ra. |
| e5-small | Nạp bằng `TextEmbedding.add_custom_model` từ `onnx/model.onnx`. Bắt buộc tiền tố `query:` / `passage:`. |
| Redis | Dùng chung cho các worker: rate-limit (`INCR` + `EXPIRE`, cửa sổ 1 phút) đã có; cache câu trả lời (TTL 24h) chưa làm. Không dùng làm hàng đợi. |
| Ảnh minh họa | `GET /api/v1/images/{id}` chỉ phục vụ ảnh cục bộ đã kiểm (theo hash), không proxy URL ngoài. Bật bằng `RAG_IMAGES_ENABLED`; ảnh chỉ xét theo nguồn trích dẫn cục bộ, không có ảnh cho nguồn web. |
| Ingestion | Chạy bằng CLI: `docker compose run --rm api python -m ingest crawl\|index\|update`. Cập nhật hằng tuần bằng cron. |
| PostgreSQL 18 | Mount volume vào `/var/lib/postgresql`, không phải `.../data`. |
| Caddy | HTTPS tự động. Phục vụ build React bằng `file_server`. Proxy `/api/*`, đặt `flush_interval -1` để SSE không bị đệm. |
| Web | Một file `api.ts` viết tay theo `docs/api/openapi.json`. SSE bằng `fetch` + `ReadableStream`. Tailwind cùng vài file CSS riêng cho giao diện. UUID có dự phòng `getRandomValues` để chạy qua HTTP LAN/VPN. |
| Bot | Node 24 chạy thẳng file `.ts` (không dùng `enum`/`namespace`). Đọc biến môi trường bằng `--env-file`. |
| Deploy | `git pull && docker compose up -d --build`. Rollback bằng `git checkout <tag>`. Staging: `docker-compose.staging.yml`, `infra/Caddyfile.staging`, `scripts/staging/` (PR #80, chưa chạy trên VPS thật; xem `docs/staging.md`). |
| Giám sát | `healthcheck` + `restart: unless-stopped`. Với `CHAT_PERSISTENCE=postgres`, hội thoại, số đo và trace từng câu trả lời nằm trong bảng `messages` (PR #79); xem bằng `make trace ID=<message_id>`. Chưa có Prometheus/Grafana. |

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
langgraph==1.2.20
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

Phụ thuộc gián tiếp được khoá trong `constraints.txt`, sinh bằng `pip freeze` (gồm langchain-openai, langsmith do LangChain kéo theo). Lệnh cài: `pip install -r requirements-dev.txt -c constraints.txt`. **Cài lại sau mỗi lần pull có đổi `requirements*.txt`.** LangGraph kéo thêm 4 pin gián tiếp đã khoá trong `constraints.txt`. `ddgs` còn trong `requirements.txt` nhưng không còn được gọi (tìm web dùng Tavily qua httpx); gỡ khi dọn mã cũ.

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
                                                └─► Tavily (khi cần tìm web, tuỳ chế độ off/auto/always)
```

Mặc định (`CHAT_PERSISTENCE=memory`) hội thoại giữ trong RAM của từng worker, nên chạy chế độ live với `API_WORKERS=1`. Với `postgres`, trạng thái nằm ở PostgreSQL và được bảo vệ bằng khóa lạc quan theo `revision`, nhưng chưa có kiểm thử nhiều worker.

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

**Model ONNX chưa nằm trong image:** Dockerfile chưa tải model, `backend/.dockerignore` loại `models`, và compose gốc chỉ mount `backend/data`. Model đặt ở `backend/models/fastembed` (≈ 465 MB) và phải được mount vào container; compose staging đã mount (PR #80). Cách đưa model vào production chốt ở Sprint 5. Migration cũng chưa chạy tự động khi khởi động: chạy `alembic upgrade head` (hoặc `scripts/staging/deploy.sh`).

### Staging

Cấu hình dự kiến 1 VPS 4 vCPU / 8 GB, **chưa có VPS và chưa có tên miền**. `docker-compose.staging.yml` chồng lên compose gốc: `ENVIRONMENT=prod`, `CHAT_MODE=rag`, `CHAT_PERSISTENCE=postgres`, giới hạn CPU từng service; Caddy dùng `infra/Caddyfile.staging` với basic auth bắt buộc, tuỳ chọn lọc IP, chứng chỉ nội bộ khi truy cập bằng IP và Let's Encrypt khi có tên miền. Tổng `mem_limit` 5,4 GB (không tính ingest). Mới kiểm tra cú pháp (`caddy validate`, `docker compose config`); chưa chạy trên máy thật nên chưa có số đo RAM/CPU. Hướng dẫn: `docs/staging.md`.

## 5. Mục tiêu hiệu năng & chi phí

| Chỉ số | Mục tiêu |
|---|---|
| Token đầu tiên p95 | < 3.5 s |
| Câu trả lời hoàn chỉnh p95 | < 10 s |
| Rerank 30 đoạn p95 | < 800 ms |
| Tải | 50 người dùng đồng thời (đo bằng locust ở S5) |
| Chi phí LLM | ≈ $30/tháng cho 1.000 câu/ngày |

### Số đo thực tế (máy phát triển, chưa phải đo tải)

| Phép đo | Kết quả | Nguồn |
|---|---|---|
| 25 câu golden thật, tuần tự, Tavily `auto` | Thời gian mỗi câu: trung vị 8,3 s, **p95 12,4 s** (vượt mục tiêu 10 s) | `docs/handover/2026-11-04_s3-tv3_golden-25-diagnostic.md` |
| Số lượt gọi trong 25 câu | 74 lượt gọi LLM, 48 request Tavily, 201.813 token vào / 12.565 token ra | như trên |
| 20 lượt hội thoại thật (agent + bộ nhớ) | 48 lượt gọi LLM, 5 Search + 5 Extract; có lỗi chất lượng cần theo dõi | `docs/handover/2026-11-06_s3-tv3_migration-setup-va-live-20.md` |
| Recall@k, MRR, correctness | **Chưa có số đo chính thức** (golden set 100 câu chưa được TV2 duyệt) | `docs/evaluation/` |
| RAM/CPU trên VPS | **Chưa đo** (chưa có VPS) | `docs/staging.md` |

Chi phí Tavily chưa được tính vào ước lượng $30/tháng ở trên.

Giá `deepseek-flash` (mỗi 1M token, giờ thấp điểm / cao điểm): input $0.15 / $0.30, cache hit $0.003 / $0.006, output $0.60 / $1.20. Cao điểm là 08–11h và 13–17h giờ Việt Nam, thứ Hai–thứ Sáu; nên chạy eval ngoài khung giờ này.

## 6. Nguồn dữ liệu

| Nguồn | Vai trò | Giấy phép |
|---|---|---|
| eldenring.wiki.gg (MediaWiki API) | Nguồn chính: base game + Shadow of the Erdtree (4.164 trang) | CC BY-SA 4.0, bắt buộc ghi nguồn; ảnh chưa rõ giấy phép giữ `unknown_review_required` |
| eldenring.fanapis.com | Danh sách thực thể | Dùng có chừng mực |
| Wikipedia | Thông tin tổng quan | CC BY-SA 4.0 |

Corpus Sprint 2 dùng `game_scope=elden_ring`; `release_scope` (base/SotE candidate, unknown) là nhãn heuristic chưa review. Nightreign và Tarnished Edition vẫn ngoài phạm vi.

Không crawl Fandom và Fextralife. Riêng lúc truy vấn, Tavily có thể trả đoạn trích từ các domain trong allowlist `WEB_SEARCH_DOMAINS` (gồm eldenring.wiki.fextralife.com); đoạn đó không được lưu vào corpus và luôn đi kèm link nguồn. **Giấy phép và điều khoản của các domain này chưa được rà soát**; cần quyết định trước khi bật `auto` mặc định ở production. Giới hạn crawl ≤ 1 request/giây, User-Agent có email liên hệ.

## 7. Rủi ro

| Rủi ro | Dự phòng |
|---|---|
| CPU quá tải khi rerank | Đổi sang MiniLM, giảm top-N xuống 20, tăng thời gian giữ cache |
| Chất lượng câu trả lời chưa đạt | Bật thinking `reasoning_effort="low"` cho bước sinh câu trả lời |
| DeepSeek gián đoạn hoặc đổi giá | Sửa `llm.py` để đổi nhà cung cấp |
| Tavily hết quota, đổi giá hoặc gián đoạn; mỗi câu `auto` thêm vài giây | Đặt `WEB_SEARCH_MODE=off` hoặc `WEB_SEARCH_ENABLED=false`: hệ thống trả lời từ corpus cục bộ, nói rõ khi thiếu bằng chứng. Theo dõi chi phí qua `tokens_in/out` và số request Tavily |
| Agent nhiều lượt gọi làm vượt mục tiêu độ trễ và chi phí (p95 25 câu = 12,4 s) | Giảm `CHAT_TOOL_STEPS`, tắt tool agent (`CHAT_TOOL_AGENT_ENABLED=false`) để về đường cố định; đo lại ở Sprint 4 |
| Domain trong allowlist web (Fextralife, Bandai Namco) chưa rà giấy phép | Rà điều khoản trước production; thu hẹp `WEB_SEARCH_DOMAINS` về eldenring.wiki.gg nếu cần |
| Trace làm phình bảng `messages` | Giới hạn 64 KB mỗi bản (PR #79); theo dõi kích thước thật, tách bảng riêng hoặc xóa trace cũ nếu cần |

## 8. ADR

| ADR | Nội dung | Trạng thái |
|---|---|---|
| 001 | LLM `deepseek-flash`, eval bằng `deepseek-v4-pro` | Chốt |
| 002 | Reranker `bge-reranker-base`, dự phòng MiniLM | Chốt, benchmark ở S1 |
| 003 | Chunk tối đa 450 token theo heading, overlap 50 | Đề xuất (đã dùng cho corpus S2) |
| 004 | Phạm vi lore: Elden Ring base game | **Đã đổi**: base game + Shadow of the Erdtree (29/10); gồm cả gameplay/build (CHANGE-REQ Sprint 3). Cần cập nhật file `adr/004-base-game-scope.md` |
| 005 | Web ẩn danh ở v1 | Đề xuất |
| 006 | Trả lời theo ngôn ngữ người hỏi, giữ tên riêng tiếng Anh | Chốt |
| 007 | Tìm web dự phòng bằng DuckDuckGo, giới hạn theo allowlist domain | **Bị thay thế** bởi ADR-008 (giữ nguyên ý allowlist domain) |
| 008 | Tìm web bằng Tavily Search + Extract thay DuckDuckGo; chế độ off/auto/always | Chấp nhận (ghi ở handover 2026-11-04 TV3, chưa có file ADR) |
| 009 | LangGraph làm đồ thị xử lý; agent chọn tool có giới hạn, server giữ kiểm chứng | Chấp nhận (handover 2026-11-06 TV3, chưa có file ADR) |
| 010 | Hội thoại và bộ nhớ ngữ nghĩa lưu PostgreSQL, Qdrant chỉ là chỉ mục dẫn xuất | Chấp nhận (handover 2026-11-06 TV3, chưa có file ADR); mặc định vẫn `memory` |
