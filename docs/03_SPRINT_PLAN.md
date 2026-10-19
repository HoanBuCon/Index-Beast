# Index Beast — Kế hoạch 6 Sprint

| Thuộc tính | Giá trị |
|---|---|
| Thời gian | 19/10/2026 → 29/11/2026 (6 sprint × 7 ngày) |
| Quy mô | 4 thành viên |
| Nguồn dữ liệu kế hoạch | planning/sprint_plan.json (sửa file này rồi chạy lại build_docs.py / trello_import.py) |
| Trello | https://trello.com/b/mZEBMPGV/elden-ring |

> Tài liệu này được sinh tự động từ `planning/sprint_plan.json`. Đừng sửa tay — sửa JSON rồi chạy lại script.

## 1. Phân vai

| Mã | Thành viên | Vai trò | Trọng tâm |
|---|---|---|---|
| TV1 | Hoanbucon | Tech Lead · Backend & DevOps | FastAPI, PostgreSQL, Docker, CI/CD, VPS, review code |
| TV2 | UncleThing | Data Engineer | Crawl, làm sạch, chunking, metadata, bảng thực thể, cập nhật dữ liệu |
| TV3 | MinhMuc | AI / RAG Engineer | Embedding, hybrid search, rerank, LLM, prompt, đánh giá chất lượng |
| TV4 | QuyVuiVe | Frontend & Discord Bot | React web, discord.js bot, UI/UX, UAT |

Nguyên tắc: mỗi thẻ có **một** người chịu trách nhiệm chính; thẻ `ALL` là hoạt động chung của team. Người chịu trách nhiệm có thể nhờ người khác hỗ trợ nhưng là người kéo thẻ sang Hoàn thành.

## 2. Lộ trình tổng quan

| Sprint | Thời gian | Chủ đề | Mục tiêu |
|---|---|---|---|
| S1 | 19/10/2026 – 25/10/2026 | **Nền móng & Spike kỹ thuật** | Mọi người chạy được môi trường dev bằng Docker; có dữ liệu mẫu; notebook RAG baseline trả lời được 10 câu; chốt các quyết định kỹ thuật (ADR) chính. |
| S2 | 26/10/2026 – 01/11/2026 | **Pipeline dữ liệu & khung API** | Toàn bộ lore Elden Ring base game được làm sạch, chia đoạn và index vào Qdrant; API contract v1 cố định; web và bot gọi được API (mock). |
| S3 | 02/11/2026 – 08/11/2026 | **RAG end-to-end → MVP nội bộ** | Hỏi trên web hoặc Discord nhận được câu trả lời thật, có trích dẫn, streaming trên web. Có số đo retrieval đầu tiên. Staging chạy trên VPS. |
| S4 | 09/11/2026 – 15/11/2026 | **Chất lượng & hoàn thiện tính năng** | Đạt mục tiêu chất lượng (Recall@5 ≥ 0.80, correctness ≥ 70%) trên golden set 120 câu; bổ sung feedback, lịch sử, thread Discord, bảo mật cơ bản. |
| S5 | 16/11/2026 – 22/11/2026 | **Production & hardening** | Hệ thống chạy production trên VPS qua HTTPS với CI/CD, backup, giám sát; đáp ứng mục tiêu độ trễ với 10–20 người dùng đồng thời; bot có mặt trên server cộng đồng. |
| S6 | 23/11/2026 – 29/11/2026 | **Ổn định, UAT & bàn giao** | Người dùng thật kiểm thử, sửa lỗi quan trọng, đóng băng tính năng, hoàn thiện tài liệu và demo cuối. Sprint này đồng thời là buffer cho việc trễ. |

Các mốc quan trọng: **cuối S1** chốt kỹ thuật (ADR) · **cuối S3** MVP nội bộ chạy end-to-end · **cuối S4** đạt mục tiêu chất lượng · **cuối S5** production · **S6** UAT, release v1.0 và buffer.

## 3. Phân bổ story point theo sprint

| Sprint | TV1 | TV2 | TV3 | TV4 | ALL | Tổng |
|---|---|---|---|---|---|---|
| S1 | 13 | 10 | 13 | 9 | 2 | 47 |
| S2 | 10 | 13 | 13 | 9 | 1 | 46 |
| S3 | 11 | 9 | 13 | 10 | 1 | 44 |
| S4 | 11 | 12 | 13 | 12 | 1 | 49 |
| S5 | 10 | 9 | 9 | 13 | 1 | 42 |
| S6 | 8 | 7 | 8 | 11 | 1 | 35 |
| **Tổng** | **63** | **60** | **69** | **64** | **7** | **263** |

Thang điểm Fibonacci (1, 2, 3, 5, 8): 1 điểm ≈ nửa ngày làm việc tập trung. Mỗi người ~10–14 điểm/sprint, chừa ~20% cho review code, họp và việc phát sinh. Sau Sprint 1, hiệu chỉnh theo velocity thực tế.

## 4. Cấu trúc bảng Trello

| Cột (List) | Mục đích |
|---|---|
| 📌 Thông tin dự án | Link tài liệu, Definition of Done, quy ước Git, phân vai |
| 🧊 Backlog | Ý tưởng / yêu cầu Could-have / CHANGE-REQ chưa xếp sprint |
| Sprint 1 | Thẻ đã lên kế hoạch cho sprint này; kéo sang Đang làm khi bắt đầu |
| Sprint 2 | Thẻ đã lên kế hoạch cho sprint này; kéo sang Đang làm khi bắt đầu |
| Sprint 3 | Thẻ đã lên kế hoạch cho sprint này; kéo sang Đang làm khi bắt đầu |
| Sprint 4 | Thẻ đã lên kế hoạch cho sprint này; kéo sang Đang làm khi bắt đầu |
| Sprint 5 | Thẻ đã lên kế hoạch cho sprint này; kéo sang Đang làm khi bắt đầu |
| Sprint 6 | Thẻ đã lên kế hoạch cho sprint này; kéo sang Đang làm khi bắt đầu |
| 🔨 Đang làm | Thẻ đang thực hiện (mỗi người tối đa 2 thẻ cùng lúc) |
| 👀 Review / QA | Đã mở PR, chờ review hoặc kiểm thử |
| ✅ Hoàn thành | Đạt Definition of Done |

Nhãn: `TV1`, `TV2`, `TV3`, `TV4`, `Team`, `Backend`, `Data`, `AI/RAG`, `Frontend`, `Bot`, `DevOps`, `Docs`, `Must`, `Should`, `Could`, `CHANGE-REQ`.

Mỗi thẻ có: tên `[S#][TV#] Tên việc`, mô tả (mục tiêu, yêu cầu SRS liên quan, story point), checklist các việc con, ngày bắt đầu/hạn = đầu/cuối sprint, nhãn người phụ trách + mảng + ưu tiên.

## Sprint 1 — Nền móng & Spike kỹ thuật (19/10/2026 – 25/10/2026)

**Mục tiêu:** Mọi người chạy được môi trường dev bằng Docker; có dữ liệu mẫu; notebook RAG baseline trả lời được 10 câu; chốt các quyết định kỹ thuật (ADR) chính.

**Sản phẩm bàn giao cuối sprint:**

- Monorepo + Docker Compose dev (Postgres, Qdrant, Redis)
- FastAPI skeleton có /health, CI chạy lint/test
- Crawl thử 200 trang wiki.gg
- Notebook RAG baseline + benchmark reranker
- ADR-001/002/003 đã chốt, golden set v0 (30 câu)
- Wireframe web, skeleton React và Discord bot

| # | Thẻ | Phụ trách | Điểm | Ưu tiên | Yêu cầu SRS |
|---|---|---|---|---|---|
| 1 | Sprint 1 Planning & Kickoff | ALL | 1 | Must | - |
| 2 | Khởi tạo monorepo & quy ước code | TV1 | 3 | Must | NFR-MNT-01, NFR-SEC-01 |
| 3 | Docker Compose môi trường dev | TV1 | 5 | Must | NFR-DEP-01 |
| 4 | Skeleton FastAPI | TV1 | 3 | Must | NFR-OBS-01, NFR-MNT-02 |
| 5 | CI GitHub Actions cơ bản | TV1 | 2 | Should | NFR-MNT-01 |
| 6 | Khảo sát nguồn dữ liệu lore | TV2 | 3 | Must | FR-ING-01, FR-ING-02, NFR-LEG-01 |
| 7 | Prototype crawler wiki.gg | TV2 | 5 | Must | FR-ING-01, FR-ING-10 |
| 8 | Đề xuất chiến lược chunk (ADR-003) | TV2 | 2 | Must | FR-ING-04 |
| 9 | Notebook RAG baseline | TV3 | 5 | Must | FR-RET-02, FR-GEN-01 |
| 10 | Benchmark reranker trên CPU (ADR-002) | TV3 | 3 | Must | NFR-PERF-02 |
| 11 | Xác nhận DeepSeek deepseek-flash (ADR-001) | TV3 | 2 | Must | FR-GEN-07, NFR-COST-01 |
| 12 | Golden set v0 (30 câu) | TV3 | 3 | Must | FR-EVAL-01 |
| 13 | Wireframe & design system web | TV4 | 3 | Should | FR-WEB-01, FR-WEB-02 |
| 14 | Khởi tạo web React | TV4 | 3 | Must | FR-WEB-01 |
| 15 | Khởi tạo Discord bot | TV4 | 3 | Must | FR-BOT-01 |
| 16 | Sprint 1 Review & Retro | ALL | 1 | - | - |

### Chi tiết công việc Sprint 1

#### 1.1 [ALL] Sprint 1 Planning & Kickoff

Cả team đọc tài liệu, thống nhất cách làm việc và chốt phạm vi.

- [ ] Đọc 01_TECHSTACK.md và 02_SRS.md, ghi câu hỏi
- [ ] Workshop RAG 60 phút (TV3 trình bày)
- [ ] Thống nhất Definition of Done & quy ước Git
- [ ] Ghi nhận ADR-004: phạm vi lore Elden Ring base game; thảo luận ADR-005 (đăng nhập)
- [ ] Gán tên thật cho TV1..TV4, mời thành viên vào board

#### 1.2 [TV1] Khởi tạo monorepo & quy ước code

Cấu trúc repo thống nhất cho cả 4 người.

- [ ] Tạo cấu trúc: backend/ ingest/ web/ bot/ infra/ docs/ planning/
- [ ] pre-commit: ruff (lint+format) cho Python, prettier cho web/bot
- [ ] .editorconfig, .gitignore, .env.example (không commit secret)
- [ ] PR template, CODEOWNERS
- [ ] Bật branch protection cho main và develop (cấm push trực tiếp, bắt buộc PR, CI và Mentor approve); main chỉ nhận release/hotfix

#### 1.3 [TV1] Docker Compose môi trường dev

Một lệnh để chạy toàn bộ hạ tầng phụ trợ trên máy dev.

- [ ] Service postgres:18.6 (mount volume vào /var/lib/postgresql) + healthcheck
- [ ] Service qdrant/qdrant:v1.19.2 + volume
- [ ] Service redis:8.10.2 (maxmemory 128mb, allkeys-lru)
- [ ] Makefile/justfile: up, down, logs, migrate, test
- [ ] README: hướng dẫn chạy local trên Windows/macOS/Linux
- [ ] Cả 4 thành viên chạy thành công

#### 1.4 [TV1] Skeleton FastAPI

Khung backend để mọi module cắm vào.

- [ ] App factory + router /api/v1
- [ ] Settings bằng pydantic-settings (đọc .env)
- [ ] GET /health kiểm tra db, qdrant, redis
- [ ] logging chuẩn (định dạng JSON) + middleware request-id
- [ ] pytest + test /health
- [ ] Dockerfile backend (multi-stage)

#### 1.5 [TV1] CI GitHub Actions cơ bản

Chạy kiểm tra tự động cho mọi PR.

- [ ] Job Python: ruff + pytest
- [ ] Job web: tsc --noEmit + vite build
- [ ] Job bot: tsc --noEmit
- [ ] Badge CI trong README

#### 1.6 [TV2] Khảo sát nguồn dữ liệu lore

Biết chính xác lấy gì, ở đâu, bao nhiêu, giấy phép ra sao.

- [ ] Liệt kê category lore trên eldenring.wiki.gg (NPC, Bosses, Locations, Lore, Items, Characters thuộc phạm vi dự án) và đếm số trang
- [ ] Thử MediaWiki API: action=query (list=categorymembers), action=parse; kiểm tra có dump không
- [ ] Thử fanapis REST: các resource, phân trang (limit/page), các trường description
- [ ] So sánh nội dung Fandom vs wiki.gg trên 10 trang
- [ ] Viết docs/data-sources.md: nguồn, endpoint, giấy phép, giới hạn tốc độ

#### 1.7 [TV2] Prototype crawler wiki.gg

Client MediaWiki lịch sự, chịu lỗi, lưu bản thô.

- [ ] HTTP client có User-Agent kèm email, ≤1 req/s, retry + backoff
- [ ] Lấy danh sách trang theo category (có phân trang continue)
- [ ] Tải nội dung (wikitext hoặc HTML parse) + revision id
- [ ] Lưu raw vào thư mục data/raw/ (JSON) để không phải crawl lại
- [ ] Crawl thử 200 trang đa dạng, ghi số liệu thời gian/lỗi

#### 1.8 [TV2] Đề xuất chiến lược chunk (ADR-003)

Chọn cách chia đoạn dựa trên dữ liệu mẫu.

- [ ] Phân tích cấu trúc heading của 20 trang mẫu
- [ ] Đề xuất kích thước (300–500 token) & overlap
- [ ] Quy tắc giữ tiêu đề trang + section trong mỗi chunk
- [ ] Viết docs/adr/003-chunking.md

#### 1.9 [TV3] Notebook RAG baseline

Chứng minh toàn bộ ý tưởng chạy được trên dữ liệu mẫu.

- [ ] Dùng 200 trang mẫu của TV2, chunk đơn giản
- [ ] Embed bằng intfloat/multilingual-e5-small qua fastembed (ONNX, nhớ tiền tố query:/passage:)
- [ ] Qdrant collection dense + sparse BM25, truy vấn hybrid RRF
- [ ] Gọi LLM với ngữ cảnh top-5, có trích dẫn
- [ ] Chạy 10 câu hỏi (5 vi, 5 en), ghi nhận xét

#### 1.10 [TV3] Benchmark reranker trên CPU (ADR-002)

Đo thật thay vì đoán — đây là rủi ro hiệu năng lớn nhất.

- [ ] Giới hạn container 4 CPU để mô phỏng VPS
- [ ] Đo bge-reranker-base ONNX (fastembed) vs Xenova/ms-marco-MiniLM-L-6-v2
- [ ] Đo p50/p95 rerank 20 và 30 đoạn; RAM sử dụng
- [ ] So sánh chất lượng sơ bộ trên 20 câu
- [ ] Viết docs/adr/002-reranker.md

#### 1.11 [TV3] Xác nhận DeepSeek deepseek-flash (ADR-001)

LLM đã chốt là deepseek-flash (non-thinking). Sprint này xác nhận bằng số đo thật.

- [ ] Tạo API key DeepSeek của dự án, nạp credit, lưu trong secret (không commit)
- [ ] Chạy 10 câu baseline: non-thinking vs thinking low (chất lượng tiếng Việt, độ trễ)
- [ ] Kiểm tra JSON output cho bước viết lại truy vấn
- [ ] Đo tỉ lệ cache hit của system prompt
- [ ] Viết docs/adr/001-llm.md

#### 1.12 [TV3] Golden set v0 (30 câu)

Thước đo chất lượng cho cả dự án — bắt đầu sớm. Mọi người cùng đóng góp câu hỏi.

- [ ] Định dạng JSONL: id, question, lang, expected_answer, source_urls, category, difficulty
- [ ] 30 câu, ≥ 50% tiếng Việt, đủ loại: nhân vật, sự kiện, địa điểm, đa bước, ngoài phạm vi
- [ ] Mỗi người đóng góp ≥ 5 câu
- [ ] Lưu tại eval/golden_set.jsonl

#### 1.13 [TV4] Wireframe & design system web

Thống nhất giao diện trước khi code.

- [ ] Wireframe: màn chat, khối nguồn trích dẫn, trang About, admin
- [ ] Bảng màu (tối, vàng Erdtree), font chữ, icon
- [ ] Trạng thái: rỗng, đang tìm, streaming, lỗi, không tìm thấy
- [ ] Team review wireframe

#### 1.14 [TV4] Khởi tạo web React

Khung dự án web.

- [ ] Vite + React + TypeScript
- [ ] Tailwind, react-router
- [ ] Prettier + tsc --noEmit
- [ ] Layout cơ bản + trang placeholder
- [ ] Build tĩnh (Caddy phục vụ ở production)

#### 1.15 [TV4] Khởi tạo Discord bot

Bot chạy được trên server test.

- [ ] Tạo Application + Bot trên Discord Developer Portal, server Discord test
- [ ] discord.js v14 + TypeScript
- [ ] Script đăng ký slash command (guild-scoped khi dev)
- [ ] Lệnh /ping
- [ ] Token trong .env, Dockerfile bot

#### 1.16 [ALL] Sprint 1 Review & Retro

Demo + rút kinh nghiệm.

- [ ] Demo notebook baseline & benchmark
- [ ] Chốt ADR-001, 002, 003
- [ ] Cập nhật SRS (phiên bản, trạng thái, TBD)
- [ ] Retro: Giữ / Bỏ / Thử
- [ ] Chuẩn bị backlog Sprint 2

## Sprint 2 — Pipeline dữ liệu & khung API (26/10/2026 – 01/11/2026)

**Mục tiêu:** Toàn bộ lore Elden Ring base game được làm sạch, chia đoạn và index vào Qdrant; API contract v1 cố định; web và bot gọi được API (mock).

**Sản phẩm bàn giao cuối sprint:**

- Dữ liệu wiki.gg đầy đủ trong Qdrant (dense + BM25) với metadata
- Schema PostgreSQL + migrations
- OpenAPI v1 + endpoint mock
- UI chat cơ bản & /ask gọi API mock
- Golden set v1 (60 câu)

| # | Thẻ | Phụ trách | Điểm | Ưu tiên | Yêu cầu SRS |
|---|---|---|---|---|---|
| 1 | Schema PostgreSQL & migrations | TV1 | 5 | Must | FR-CHAT-01, FR-ING-10 |
| 2 | API contract v1 (OpenAPI) + mock | TV1 | 3 | Must | FR-CHAT-01 |
| 3 | Xử lý lỗi & logging chuẩn | TV1 | 2 | Should | NFR-OBS-01 |
| 4 | Crawl toàn bộ wiki.gg | TV2 | 5 | Must | FR-ING-01, FR-ING-10 |
| 5 | Làm sạch & chuẩn hoá nội dung | TV2 | 5 | Must | FR-ING-03 |
| 6 | Chunking + metadata | TV2 | 3 | Must | FR-ING-04, FR-ING-05 |
| 7 | Crawler fanapis → bảng entities | TV3 | 2 | Should | FR-ING-02, FR-ING-09 |
| 8 | Embedding & indexing vào Qdrant | TV3 | 5 | Must | FR-ING-06 |
| 9 | Module retrieval hybrid | TV3 | 3 | Must | FR-RET-02, FR-RET-05 |
| 10 | Golden set v1 (60 câu) | TV3 | 3 | Must | FR-EVAL-01 |
| 11 | UI chat cơ bản | TV4 | 5 | Must | FR-WEB-01, NFR-UX-01 |
| 12 | File api.ts viết tay cho web & bot | TV4 | 1 | Should | - |
| 13 | Bot /ask gọi API mock | TV4 | 3 | Must | FR-BOT-01, FR-BOT-02 |
| 14 | Sprint 2 Review & Retro | ALL | 1 | - | - |

### Chi tiết công việc Sprint 2

#### 2.1 [TV1] Schema PostgreSQL & migrations

Mô hình dữ liệu theo SRS §6.

- [ ] SQLAlchemy 2 (async) models: documents, chunks, entities, conversations, messages, feedback, ingestion_jobs, eval_runs
- [ ] Alembic migration đầu tiên
- [ ] Repository/DAO layer + session dependency
- [ ] Test với Postgres thật chạy bằng docker compose

#### 2.2 [TV1] API contract v1 (OpenAPI) + mock

Cố định giao kèo để FE/Bot làm song song.

- [ ] Pydantic schema cho /chat, /chat/stream (SSE), /feedback, /conversations/{id}
- [ ] Endpoint mock trả dữ liệu giả có nguồn
- [ ] Xuất openapi.json vào repo
- [ ] Review contract với TV3 & TV4

#### 2.3 [TV1] Xử lý lỗi & logging chuẩn

Lỗi có định dạng thống nhất, dễ debug.

- [ ] Exception handler → JSON {code, message, request_id}
- [ ] Truyền request-id từ web/bot (header X-Request-ID)
- [ ] Log thời gian xử lý mỗi request

#### 2.4 [TV2] Crawl toàn bộ wiki.gg

Thu thập đầy đủ các trang lore.

- [ ] Danh sách category lore Elden Ring base game
- [ ] Crawl có resume (bỏ qua trang đã có cùng revision)
- [ ] Ghi ingestion_jobs (số trang ok/lỗi)
- [ ] Báo cáo: số trang, dung lượng, thời gian

#### 2.5 [TV2] Làm sạch & chuẩn hoá nội dung

Biến wikitext/HTML thành văn bản sạch giàu lore.

- [ ] Parse wikitext/HTML → text (mwparserfromhell hoặc BeautifulSoup)
- [ ] Bỏ infobox chỉ số, navbox, bảng stats, references rác
- [ ] Giữ: mô tả item, hội thoại NPC, phần Lore/Background
- [ ] Bộ test 20 trang mẫu đa dạng (so sánh output mong đợi)

#### 2.6 [TV2] Chunking + metadata

Chia đoạn theo ADR-003 và gắn metadata.

- [ ] Chunk theo heading, kích thước/overlap cấu hình được
- [ ] Metadata: doc_id, title, section, url, source, game_scope, source_type, lang, updated_at
- [ ] Gán game_scope=base cho chunk
- [ ] Heuristic source_type (in-game text / wiki prose / speculation)
- [ ] Ghi chunks vào PostgreSQL

#### 2.7 [TV3] Crawler fanapis → bảng entities

Danh sách thực thể chuẩn cho alias & lọc.

- [ ] Lấy bosses, npcs, locations, items… có phân trang
- [ ] Chuẩn hoá tên, loại thực thể
- [ ] Ghi bảng entities

#### 2.8 [TV3] Embedding & indexing vào Qdrant

Module ingest → vector.

- [ ] Collection lore_chunks: dense 384 cosine + sparse bm25 (IDF)
- [ ] Batch embed multilingual-e5-small (ONNX/fastembed)
- [ ] Upsert idempotent (point id = hash chunk)
- [ ] Payload index: game_scope, spoiler_level, source_type
- [ ] CLI: python -m ingest index
- [ ] Đo thời gian index toàn bộ

#### 2.9 [TV3] Module retrieval hybrid

Hàm retrieve() dùng Query API của Qdrant.

- [ ] Prefetch dense + sparse, fusion RRF, top-N cấu hình
- [ ] Hỗ trợ filter metadata
- [ ] Unit test với collection nhỏ
- [ ] Đo độ trễ

#### 2.10 [TV3] Golden set v1 (60 câu)

Mở rộng bộ đánh giá, có review chéo.

- [ ] Thêm 30 câu (giữ ≥ 50% tiếng Việt)
- [ ] Bổ sung câu hỏi lore Elden Ring base game và đáp án tham chiếu
- [ ] TV2 review chéo nguồn & đáp án
- [ ] Đánh dấu độ khó

#### 2.11 [TV4] UI chat cơ bản

Màn chat dùng API mock.

- [ ] Danh sách tin nhắn + ô nhập (Enter gửi, Shift+Enter xuống dòng)
- [ ] Render Markdown an toàn
- [ ] Trạng thái loading / lỗi / thử lại
- [ ] Gọi /chat mock

#### 2.12 [TV4] File api.ts viết tay cho web & bot

Khoảng 5 endpoint, không cần sinh code từ OpenAPI.

- [ ] Type request/response viết tay theo openapi.json
- [ ] Hàm chat, chatStream (fetch + ReadableStream), feedback
- [ ] Dùng chung cho bot (copy file)

#### 2.13 [TV4] Bot /ask gọi API mock

Luồng hoàn chỉnh trên Discord với dữ liệu giả.

- [ ] /ask <question>: deferReply ngay lập tức
- [ ] Gọi backend, editReply bằng embed (câu trả lời + nguồn)
- [ ] Xử lý timeout/lỗi thân thiện
- [ ] Gửi X-Request-ID

#### 2.14 [ALL] Sprint 2 Review & Retro

- [ ] Demo: số liệu dữ liệu đã index, UI + bot với mock
- [ ] Kiểm tra truy vấn hybrid trên dữ liệu thật
- [ ] Cập nhật SRS
- [ ] Retro
- [ ] Chuẩn bị Sprint 3

## Sprint 3 — RAG end-to-end → MVP nội bộ (02/11/2026 – 08/11/2026)

**Mục tiêu:** Hỏi trên web hoặc Discord nhận được câu trả lời thật, có trích dẫn, streaming trên web. Có số đo retrieval đầu tiên. Staging chạy trên VPS.

**Sản phẩm bàn giao cuối sprint:**

- Pipeline: rewrite → hybrid → rerank → generate có trích dẫn
- /chat và /chat/stream thật + lưu hội thoại
- Web streaming + nguồn; Bot trả lời thật
- Báo cáo Recall@k/MRR baseline
- Staging trên VPS

| # | Thẻ | Phụ trách | Điểm | Ưu tiên | Yêu cầu SRS |
|---|---|---|---|---|---|
| 1 | Endpoint /chat & /chat/stream thật | TV1 | 5 | Must | FR-CHAT-01, FR-CHAT-02, FR-CHAT-03, FR-GEN-05 |
| 2 | Trace từng bước RAG | TV1 | 3 | Must | FR-EVAL-05 |
| 3 | Staging trên VPS | TV1 | 3 | Must | NFR-RES-01 |
| 4 | Thêm Wikipedia & khử trùng lặp nguồn | TV2 | 3 | Should | FR-ING-08 |
| 5 | Bảng alias thực thể v1 | TV2 | 3 | Should | FR-ING-09 |
| 6 | Kiểm tra chất lượng dữ liệu | TV2 | 3 | Must | FR-ING-03, FR-ING-05 |
| 7 | Query rewrite + dịch truy vấn | TV3 | 3 | Must | FR-RET-01 |
| 8 | Reranker service | TV3 | 3 | Must | FR-RET-03, FR-RET-04 |
| 9 | Generation: prompt + trích dẫn + llm.py | TV3 | 5 | Must | FR-GEN-01, FR-GEN-02, FR-GEN-03, FR-GEN-07, NFR-MNT-02 |
| 10 | Script đánh giá retrieval | TV3 | 2 | Must | FR-EVAL-02 |
| 11 | Web: streaming SSE + hiển thị nguồn | TV4 | 5 | Must | FR-WEB-01, FR-WEB-02, NFR-UX-01 |
| 12 | Bot: câu trả lời thật, chia nhỏ, /help /about | TV4 | 3 | Must | FR-BOT-02, FR-BOT-03, FR-BOT-06 |
| 13 | Trang About & ghi nguồn | TV4 | 2 | Must | FR-WEB-07, NFR-LEG-01 |
| 14 | Sprint 3 Review — MVP Demo nội bộ | ALL | 1 | Must | - |

### Chi tiết công việc Sprint 3

#### 3.1 [TV1] Endpoint /chat & /chat/stream thật

Ghép pipeline RAG của TV3 vào API.

- [ ] Service orchestrator gọi rewrite → retrieve → rerank → generate
- [ ] SSE events: status, token, sources, done, error
- [ ] Lưu conversations & messages (nguồn, độ trễ, token)
- [ ] Lấy N lượt lịch sử gần nhất
- [ ] Test tích hợp với LLM giả (fake provider)

#### 3.2 [TV1] Trace từng bước RAG

Debug được vì sao một câu trả lời sai.

- [ ] Lưu query gốc, query viết lại, chunk ids + điểm, độ trễ từng bước, token
- [ ] Endpoint/CLI xem trace theo message_id
- [ ] Không log secret

#### 3.3 [TV1] Staging trên VPS

Phát hiện sớm vấn đề tài nguyên trên máy thật.

- [ ] Cài Docker, user deploy, SSH key, firewall (ufw)
- [ ] docker-compose.staging.yml + mem_limit từng service
- [ ] Bảo vệ staging bằng basic auth / IP
- [ ] Đo RAM/CPU khi chạy 1 câu hỏi

#### 3.4 [TV2] Thêm Wikipedia & khử trùng lặp nguồn

Mở rộng nguồn nhưng tránh chunk trùng.

- [ ] Crawl trang Wikipedia Elden Ring, trích xuất thông tin lore thuộc phạm vi
- [ ] Khử trùng lặp gần đúng (MinHash/hash đoạn chuẩn hoá)
- [ ] Báo cáo tỉ lệ trùng

#### 3.5 [TV2] Bảng alias thực thể v1

Giúp tìm đúng nhân vật dù gọi bằng tên khác.

- [ ] Lấy redirect của wiki.gg làm alias (list=allredirects)
- [ ] Gộp với entities từ fanapis
- [ ] Thêm thủ công alias quan trọng (Radagon/Marika, các danh hiệu)
- [ ] Xuất API/hàm lookup_aliases()

#### 3.6 [TV2] Kiểm tra chất lượng dữ liệu

Dữ liệu sạch quyết định chất lượng RAG.

- [ ] Lấy mẫu ngẫu nhiên 50 chunk, chấm sạch/bẩn
- [ ] Thống kê độ dài chunk, chunk quá ngắn/dài
- [ ] Sửa lỗi cleaning phát hiện được, re-index
- [ ] Ghi lại các lỗi đặc thù wiki

#### 3.7 [TV3] Query rewrite + dịch truy vấn

Câu hỏi tiếng Việt / phụ thuộc ngữ cảnh → truy vấn tiếng Anh độc lập.

- [ ] Prompt trả về JSON: standalone_query_en, lang, entities, out_of_scope
- [ ] Validate JSON, fallback dùng câu gốc khi lỗi
- [ ] Test với 20 câu có đại từ ('ông ta', 'cô ấy')

#### 3.8 [TV3] Reranker service

Rerank theo ADR-002.

- [ ] Load model ONNX 1 lần khi khởi động
- [ ] Semaphore giới hạn số rerank đồng thời
- [ ] Ngưỡng grounded → cờ 'không đủ ngữ cảnh'
- [ ] Đo p95 trên staging

#### 3.9 [TV3] Generation: prompt + trích dẫn + llm.py

Trái tim của chatbot.

- [ ] Module llm.py (generate, stream) gọi deepseek-flash, kèm bản giả để test
- [ ] System prompt: chỉ dựa trên ngữ cảnh, trích dẫn [n], trả lời theo ngôn ngữ người hỏi, giữ tên riêng
- [ ] Đánh số ngữ cảnh, ánh xạ [n] → title/url
- [ ] Từ chối lịch sự khi không đủ ngữ cảnh
- [ ] Prompt & tham số trong file cấu hình, không hardcode

#### 3.10 [TV3] Script đánh giá retrieval

Số đo đầu tiên để cải thiện có cơ sở.

- [ ] Tính Recall@5, Recall@10, MRR theo source_urls trong golden set
- [ ] So sánh: dense only / BM25 only / hybrid / hybrid+rerank
- [ ] Xuất bảng kết quả markdown

#### 3.11 [TV4] Web: streaming SSE + hiển thị nguồn

Trải nghiệm chat thật.

- [ ] Đọc SSE (fetch + ReadableStream), hiển thị token dần
- [ ] Trạng thái 'Đang tìm trong lore…' ≤ 300ms
- [ ] Khối nguồn: danh sách [n] tiêu đề + link
- [ ] Nút dừng sinh câu trả lời
- [ ] Xử lý lỗi giữa chừng

#### 3.12 [TV4] Bot: câu trả lời thật, chia nhỏ, /help /about

Bot dùng được thật trên server test.

- [ ] Gọi /chat thật, conversation_id theo channel/user
- [ ] Cắt câu trả lời theo giới hạn embed, link 'xem đầy đủ trên web'
- [ ] /help và /about (nguồn & giấy phép CC BY-SA)
- [ ] Đăng ký command global khi sẵn sàng

#### 3.13 [TV4] Trang About & ghi nguồn

Tuân thủ CC BY-SA & disclaimer.

- [ ] Giới thiệu dự án & team
- [ ] Nguồn dữ liệu + giấy phép CC BY-SA 4.0 + link
- [ ] Disclaimer: fan project, không liên kết FromSoftware/Bandai Namco

#### 3.14 [ALL] Sprint 3 Review — MVP Demo nội bộ

Mốc quan trọng: MVP chạy end-to-end.

- [ ] Demo 10 kịch bản Phụ lục A của SRS (ghi lại cái nào đạt)
- [ ] Trình bày số đo retrieval
- [ ] Liệt kê top 10 lỗi chất lượng → backlog Sprint 4
- [ ] Cập nhật SRS
- [ ] Retro

## Sprint 4 — Chất lượng & hoàn thiện tính năng (09/11/2026 – 15/11/2026)

**Mục tiêu:** Đạt mục tiêu chất lượng (Recall@5 ≥ 0.80, correctness ≥ 70%) trên golden set 120 câu; bổ sung feedback, lịch sử, thread Discord, bảo mật cơ bản.

**Sản phẩm bàn giao cuối sprint:**

- Eval câu trả lời tự động + lưu eval_runs
- Cấu hình retrieval tối ưu có bảng thí nghiệm
- Guardrails ngoài phạm vi / prompt injection
- Auth service token, rate-limit, feedback
- Web: feedback, lịch sử, gợi ý; Bot: thread + feedback

| # | Thẻ | Phụ trách | Điểm | Ưu tiên | Yêu cầu SRS |
|---|---|---|---|---|---|
| 1 | Xác thực client, CORS, bảo vệ admin | TV1 | 3 | Must | FR-CHAT-06, NFR-SEC-03 |
| 2 | Rate-limit bằng Redis | TV1 | 3 | Must | FR-CHAT-04, NFR-COST-01 |
| 3 | API feedback & conversations | TV1 | 2 | Must | FR-WEB-04, FR-BOT-05 |
| 4 | Test tích hợp pipeline | TV1 | 3 | Should | NFR-MNT-01 |
| 5 | Golden set v2 (120 câu) | TV2 | 3 | Must | FR-EVAL-01 |
| 6 | Gắn spoiler_level & chuẩn hoá game_scope | TV2 | 3 | Could | FR-ING-11, FR-RET-05 |
| 7 | Tìm web dự phòng qua DuckDuckGo (FR-RET-08) | TV2 | 3 | Should | FR-RET-08 |
| 8 | Sửa dữ liệu theo phân tích lỗi eval | TV2 | 3 | Must | FR-ING-03, FR-ING-04 |
| 9 | Eval câu trả lời (LLM-as-judge) | TV3 | 5 | Must | FR-EVAL-03, FR-EVAL-04, NFR-QUAL-02 |
| 10 | Tối ưu retrieval | TV3 | 5 | Must | NFR-QUAL-01, FR-RET-06 |
| 11 | Guardrails: ngoài phạm vi, prompt injection, giả thuyết | TV3 | 3 | Should | FR-GEN-04, FR-GEN-06, NFR-SEC-02 |
| 12 | Web: feedback, lịch sử, câu hỏi gợi ý | TV4 | 5 | Must | FR-WEB-03, FR-WEB-04, FR-WEB-05 |
| 13 | Web: popover trích dẫn | TV4 | 2 | Should | FR-WEB-02 |
| 14 | Bot: hỏi tiếp trong thread + nút feedback | TV4 | 5 | Should | FR-BOT-04, FR-BOT-05 |
| 15 | Sprint 4 Review & Retro | ALL | 1 | - | - |

### Chi tiết công việc Sprint 4

#### 4.1 [TV1] Xác thực client, CORS, bảo vệ admin

Chỉ client hợp lệ gọi được API.

- [ ] Service token cho bot (header) và web (server-side hoặc public key giới hạn)
- [ ] CORS chỉ domain web
- [ ] Endpoint /admin/* yêu cầu admin token
- [ ] Test các trường hợp 401/403

#### 4.2 [TV1] Rate-limit bằng Redis

Chống spam và kiểm soát chi phí LLM.

- [ ] Giới hạn theo IP (web), user & guild (bot)
- [ ] Trả 429 kèm Retry-After
- [ ] Cấu hình được qua .env
- [ ] Giới hạn max token mỗi request

#### 4.3 [TV1] API feedback & conversations

- [ ] POST /feedback (rating, reason)
- [ ] GET /conversations/{id}
- [ ] Test

#### 4.4 [TV1] Test tích hợp pipeline

Bảo vệ khỏi hồi quy khi tuning.

- [ ] Test end-to-end với Qdrant + Postgres thật và LLM giả
- [ ] Chạy trong CI
- [ ] Coverage module RAG lõi ≥ 60%

#### 4.5 [TV2] Golden set v2 (120 câu)

Đủ lớn để số đo có ý nghĩa.

- [ ] Thêm 60 câu, cân bằng category & độ khó
- [ ] Thêm câu từ log người dùng thật (staging)
- [ ] Review chéo toàn bộ đáp án
- [ ] Đóng băng v2 cho các thí nghiệm sprint này

#### 4.6 [TV2] Gắn spoiler_level & chuẩn hoá game_scope

- [ ] Quy tắc spoiler theo category/khu vực/ending
- [ ] Kiểm tra game_scope trên mẫu 50 trang
- [ ] Re-index payload

#### 4.7 [TV2] Tìm web dự phòng qua DuckDuckGo (FR-RET-08)

Chỉ chạy khi điểm rerank cao nhất thấp hơn ngưỡng (không đủ ngữ cảnh). TV3 review phần ghép vào pipeline.

- [ ] ddgs 9.16.0, backend=duckduckgo, query_en, tối đa 5 kết quả, chạy trong threadpool
- [ ] Lọc theo allowlist domain (eldenring.wiki.gg, en.wikipedia.org) và phạm vi lore base game
- [ ] Tải 2 trang đầu bằng httpx (timeout 4s), làm sạch bằng BeautifulSoup, chunk, rerank chung với kết quả cũ
- [ ] Cache Redis 7 ngày; giới hạn toàn hệ thống 1 lượt tìm/giây
- [ ] Gắn nhãn "nguồn web"; lỗi hoặc CAPTCHA thì trả lời "không tìm thấy"; cờ WEB_FALLBACK_ENABLED
- [ ] Ghi URL tìm được vào log để lần ingest sau bổ sung vào kho
- [ ] Test với 10 câu hỏi lore Elden Ring base game chưa có trong kho

#### 4.8 [TV2] Sửa dữ liệu theo phân tích lỗi eval

Lỗi do dữ liệu phải sửa ở dữ liệu.

- [ ] Phân loại câu sai: do retrieval / do dữ liệu / do generation
- [ ] Sửa cleaning/chunking cho nhóm lỗi dữ liệu
- [ ] Re-index & chạy lại eval

#### 4.9 [TV3] Eval câu trả lời (LLM-as-judge)

Đo faithfulness & correctness tự động.

- [ ] Prompt judge: faithfulness (có dựa vào ngữ cảnh?), correctness (so với đáp án)
- [ ] Kiểm tra tay 30 câu để xác nhận judge đáng tin
- [ ] Lưu eval_runs (git sha, config, metrics)
- [ ] Báo cáo so sánh giữa các lần chạy

#### 4.10 [TV3] Tối ưu retrieval

Đạt Recall@5 ≥ 0.80.

- [ ] Thí nghiệm: kích thước chunk, top-N, top-K, trọng số fusion
- [ ] Mở rộng truy vấn bằng alias
- [ ] Luôn filter game_scope=base
- [ ] Bảng thí nghiệm + chọn cấu hình mặc định

#### 4.11 [TV3] Guardrails: ngoài phạm vi, prompt injection, giả thuyết

- [ ] Từ chối build/stats/không phải Elden Ring
- [ ] Tách rõ system / ngữ cảnh / câu hỏi; test 10 câu injection
- [ ] Nêu rõ khi nội dung là giả thuyết (dựa trên source_type)

#### 4.12 [TV4] Web: feedback, lịch sử, câu hỏi gợi ý

- [ ] Nút 👍/👎 + lý do tuỳ chọn
- [ ] Danh sách cuộc trò chuyện (localStorage), tạo mới
- [ ] Câu hỏi gợi ý khi màn hình trống
- [ ] Hiển thị lỗi 429 thân thiện

#### 4.13 [TV4] Web: popover trích dẫn

Click [n] để xem đoạn nguồn.

- [ ] Biến [n] trong Markdown thành nút
- [ ] Popover hiển thị section + trích đoạn + link

#### 4.14 [TV4] Bot: hỏi tiếp trong thread + nút feedback

- [ ] Nút 'Hỏi tiếp' tạo thread; tin nhắn trong thread dùng chung conversation_id
- [ ] Nút 👍/👎 gọi /feedback
- [ ] Giới hạn thread hết hạn/không hoạt động

#### 4.15 [ALL] Sprint 4 Review & Retro

- [ ] Trình bày bảng eval (trước/sau)
- [ ] Quyết định model LLM cuối cùng dựa trên số liệu
- [ ] Cập nhật SRS + ngưỡng NFR nếu cần
- [ ] Retro

## Sprint 5 — Production & hardening (16/11/2026 – 22/11/2026)

**Mục tiêu:** Hệ thống chạy production trên VPS qua HTTPS với CI/CD, backup, giám sát; đáp ứng mục tiêu độ trễ với 10–20 người dùng đồng thời; bot có mặt trên server cộng đồng.

**Sản phẩm bàn giao cuối sprint:**

- Production + HTTPS + domain
- CI/CD tự động + rollback
- Backup & monitoring
- Báo cáo load test
- Trang admin, theme hoàn chỉnh, bot production

| # | Thẻ | Phụ trách | Điểm | Ưu tiên | Yêu cầu SRS |
|---|---|---|---|---|---|
| 1 | Deploy production + HTTPS | TV1 | 5 | Must | NFR-DEP-01, NFR-SEC-01, NFR-RES-01, NFR-AVL-01 |
| 2 | Script deploy đơn giản | TV1 | 2 | Must | NFR-DEP-01 |
| 3 | Backup & monitoring | TV1 | 3 | Should | NFR-AVL-01 |
| 4 | Cập nhật dữ liệu tăng dần | TV2 | 5 | Should | FR-ING-07 |
| 5 | Quyền riêng tư & lưu trữ log | TV2 | 2 | Should | NFR-PRIV-01 |
| 6 | Tài liệu pipeline dữ liệu | TV2 | 2 | Should | - |
| 7 | Load test & tối ưu độ trễ | TV3 | 5 | Must | NFR-PERF-01, NFR-CAP-01 |
| 8 | Tối ưu chi phí LLM | TV3 | 2 | Should | NFR-COST-01 |
| 9 | Eval trên cấu hình production | TV3 | 2 | Must | NFR-QUAL-01, NFR-QUAL-02 |
| 10 | Web: theme Elden Ring, responsive, a11y | TV4 | 5 | Should | FR-WEB-06 |
| 11 | Trang admin | TV4 | 5 | Should | FR-WEB-08 |
| 12 | Bot production: /config, mention | TV4 | 3 | Could | FR-BOT-07, FR-BOT-08 |
| 13 | Sprint 5 Review & Retro | ALL | 1 | - | - |

### Chi tiết công việc Sprint 5

#### 5.1 [TV1] Deploy production + HTTPS

- [ ] Caddy 2.11.7: reverse proxy + HTTPS tự động + phục vụ web tĩnh
- [ ] docker-compose.prod.yml: mem_limit, restart: unless-stopped, healthcheck
- [ ] Secrets qua .env trên server (quyền 600)
- [ ] Chỉ mở cổng 80/443/22

#### 5.2 [TV1] Script deploy đơn giản

Chỉ có 1 server: deploy bằng git pull, không cần registry.

- [ ] Script deploy.sh: git pull → docker compose up -d --build
- [ ] Tự chạy alembic upgrade head khi api khởi động
- [ ] Hướng dẫn rollback: git checkout <tag> rồi chạy lại deploy.sh
- [ ] (Tuỳ chọn) GitHub Actions gọi deploy.sh qua SSH khi tạo tag

#### 5.3 [TV1] Backup & monitoring

- [ ] pg_dump hằng ngày + giữ 7 bản
- [ ] Qdrant snapshot hằng tuần
- [ ] healthcheck + restart: unless-stopped cho mọi container; (tuỳ chọn) dịch vụ ping miễn phí bên ngoài báo qua Discord
- [ ] Thử khôi phục từ backup 1 lần

#### 5.4 [TV2] Cập nhật dữ liệu tăng dần

- [ ] Dùng recentchanges/revision id để tìm trang thay đổi
- [ ] Re-chunk & re-index trang đổi, xoá chunk trang bị xoá
- [ ] Cron trên VPS chạy docker compose run --rm api python -m ingest update hằng tuần, giờ thấp điểm
- [ ] Log ingestion_jobs

#### 5.5 [TV2] Quyền riêng tư & lưu trữ log

- [ ] Hash Discord user id
- [ ] Job xoá log > 90 ngày
- [ ] Ghi chính sách trên trang About

#### 5.6 [TV2] Tài liệu pipeline dữ liệu

- [ ] docs/data-pipeline.md: luồng, lệnh CLI, cấu hình
- [ ] Hướng dẫn thêm nguồn mới

#### 5.7 [TV3] Load test & tối ưu độ trễ

- [ ] Kịch bản Locust 20 và 50 người dùng đồng thời
- [ ] Đo p95 từng bước từ trace
- [ ] Tối ưu: số thread ONNX, semaphore rerank, top-N
- [ ] Cache Redis cho câu hỏi lặp (FR-CHAT-05), TTL 24h
- [ ] Báo cáo trước/sau

#### 5.8 [TV3] Tối ưu chi phí LLM

- [ ] Prompt caching cho system prompt cố định (nếu provider hỗ trợ)
- [ ] Rút gọn ngữ cảnh/giới hạn output
- [ ] Thống kê chi phí thực tế/ngày

#### 5.9 [TV3] Eval trên cấu hình production

- [ ] Chạy full eval trên production
- [ ] So sánh với Sprint 4
- [ ] Ghi eval_runs

#### 5.10 [TV4] Web: theme Elden Ring, responsive, a11y

- [ ] Theme hoàn chỉnh theo design system
- [ ] Responsive mobile (360px+)
- [ ] Kiểm tra bàn phím & tương phản
- [ ] Lighthouse ≥ 85

#### 5.11 [TV4] Trang admin

TV1 hỗ trợ API /admin/stats.

- [ ] Đăng nhập admin token
- [ ] Bảng hội thoại gần đây + trace
- [ ] Danh sách feedback 👎 để phân tích
- [ ] Trạng thái ingestion & kết quả eval

#### 5.12 [TV4] Bot production: /config, mention

- [ ] /config kênh được phép (chỉ admin server)
- [ ] Trả lời khi được mention
- [ ] Link mời bot + mời vào server cộng đồng demo

#### 5.13 [ALL] Sprint 5 Review & Retro

- [ ] Demo trên domain production
- [ ] Báo cáo load test & chi phí
- [ ] Chuẩn bị kế hoạch UAT
- [ ] Retro

## Sprint 6 — Ổn định, UAT & bàn giao (23/11/2026 – 29/11/2026)

**Mục tiêu:** Người dùng thật kiểm thử, sửa lỗi quan trọng, đóng băng tính năng, hoàn thiện tài liệu và demo cuối. Sprint này đồng thời là buffer cho việc trễ.

**Sản phẩm bàn giao cuối sprint:**

- Báo cáo UAT
- Release v1.0 (tag + changelog)
- Báo cáo chất lượng cuối
- Tài liệu kỹ thuật & hướng dẫn sử dụng
- Slide + video demo

| # | Thẻ | Phụ trách | Điểm | Ưu tiên | Yêu cầu SRS |
|---|---|---|---|---|---|
| 1 | UAT với người chơi thật | TV4 | 3 | Must | - |
| 2 | Bug bash & sửa lỗi Critical/High | TV1 | 5 | Must | - |
| 3 | Rà soát bảo mật | TV1 | 2 | Must | NFR-SEC-01, NFR-SEC-02, NFR-SEC-03 |
| 4 | Release v1.0 | TV1 | 1 | Must | - |
| 5 | Cập nhật & đóng băng dữ liệu cuối | TV2 | 2 | Must | FR-ING-07 |
| 6 | Sửa lỗi dữ liệu từ UAT | TV2 | 3 | Must | - |
| 7 | Tài liệu kỹ thuật dữ liệu | TV2 | 2 | Should | - |
| 8 | Eval cuối & báo cáo chất lượng | TV3 | 3 | Must | NFR-QUAL-01, NFR-QUAL-02 |
| 9 | Sửa lỗi câu trả lời từ UAT | TV3 | 3 | Must | - |
| 10 | Tài liệu kiến trúc RAG | TV3 | 2 | Should | - |
| 11 | Hoàn thiện UI từ UAT | TV4 | 3 | Must | - |
| 12 | Slide & video demo | TV4 | 3 | Must | - |
| 13 | Hướng dẫn sử dụng web & bot | TV4 | 2 | Should | - |
| 14 | Final Demo & Retrospective dự án | ALL | 1 | Must | - |

### Chi tiết công việc Sprint 6

#### 6.1 [TV4] UAT với người chơi thật

Cả team tham gia, TV4 điều phối.

- [ ] Mời 10–15 người chơi Elden Ring
- [ ] Form khảo sát (độ đúng, độ hữu ích, giao diện)
- [ ] Tổng hợp feedback + log 👎 → thẻ lỗi
- [ ] Báo cáo UAT

#### 6.2 [TV1] Bug bash & sửa lỗi Critical/High

- [ ] Buổi bug bash 1 giờ cả team
- [ ] Phân loại mức độ lỗi
- [ ] Sửa toàn bộ Critical/High
- [ ] Feature freeze từ giữa sprint

#### 6.3 [TV1] Rà soát bảo mật

- [ ] Quét secret trong lịch sử git
- [ ] Cập nhật dependency có lỗ hổng
- [ ] Kiểm tra quyền bot Discord tối thiểu
- [ ] Kiểm tra lại rate-limit & admin auth

#### 6.4 [TV1] Release v1.0

- [ ] CHANGELOG.md
- [ ] Tag v1.0.0 + GitHub Release
- [ ] README hoàn chỉnh (chạy local, deploy, kiến trúc)

#### 6.5 [TV2] Cập nhật & đóng băng dữ liệu cuối

- [ ] Chạy cập nhật tăng dần lần cuối
- [ ] Snapshot Qdrant phiên bản release
- [ ] Ghi thống kê dữ liệu cuối

#### 6.6 [TV2] Sửa lỗi dữ liệu từ UAT

- [ ] Phân tích câu sai liên quan dữ liệu
- [ ] Sửa & re-index
- [ ] Thêm câu UAT vào golden set

#### 6.7 [TV2] Tài liệu kỹ thuật dữ liệu

- [ ] Hoàn thiện docs/data-pipeline.md
- [ ] Sơ đồ luồng dữ liệu

#### 6.8 [TV3] Eval cuối & báo cáo chất lượng

- [ ] Chạy eval golden set cuối
- [ ] Biểu đồ cải thiện qua các sprint
- [ ] Phân tích các nhóm câu còn yếu & hướng phát triển

#### 6.9 [TV3] Sửa lỗi câu trả lời từ UAT

- [ ] Phân tích câu sai do retrieval/generation
- [ ] Điều chỉnh prompt/cấu hình
- [ ] Chạy lại eval để tránh hồi quy

#### 6.10 [TV3] Tài liệu kiến trúc RAG

- [ ] docs/rag-architecture.md: luồng, prompt, tham số, kết quả eval
- [ ] Cập nhật 01_TECHSTACK.md theo thực tế

#### 6.11 [TV4] Hoàn thiện UI từ UAT

- [ ] Sửa các vấn đề UX từ UAT
- [ ] Kiểm tra lại trên mobile
- [ ] Sửa lỗi bot

#### 6.12 [TV4] Slide & video demo

Mọi người đóng góp phần của mình.

- [ ] Slide: bài toán, kiến trúc, dữ liệu, kết quả eval, demo, bài học
- [ ] Video demo 3–5 phút (web + Discord)
- [ ] Tập dượt demo

#### 6.13 [TV4] Hướng dẫn sử dụng web & bot

- [ ] Hướng dẫn người dùng (web)
- [ ] Hướng dẫn mời & dùng bot Discord

#### 6.14 [ALL] Final Demo & Retrospective dự án

- [ ] Demo cuối
- [ ] Chốt SRS v1.0 (trạng thái mọi yêu cầu)
- [ ] Retro toàn dự án
- [ ] Backlog cho phiên bản sau

## Backlog (chưa xếp sprint)

| Thẻ | Phụ trách đề xuất | Điểm | Ghi chú |
|---|---|---|---|
| Đăng nhập web bằng Discord OAuth (FR-WEB-09) | TV4 | 5 | Chờ ADR-005. Đồng bộ lịch sử chat giữa web và Discord. |
| Tách câu hỏi phức hợp thành truy vấn con (FR-RET-07) | TV3 | 3 | Cho câu hỏi đa bước. Chỉ làm nếu eval cho thấy lỗi ở nhóm câu hỏi đa bước. |
| Ẩn spoiler theo cài đặt người dùng/guild (FR-GEN-08) | TV3 | 3 | Dùng spoiler_level của chunk + cài đặt; Discord dùng ||spoiler||. |
| Mẫu thẻ yêu cầu thay đổi (CHANGE-REQ) | TV1 | 0 | Sao chép thẻ này khi muốn đổi yêu cầu. |

## Nghi thức Scrum rút gọn (sprint 1 tuần)

| Hoạt động | Thời điểm | Thời lượng | Nội dung |
|---|---|---|---|
| Sprint Planning | Thứ Hai đầu sprint | 45 phút | Chọn thẻ, xác nhận người phụ trách & điểm |
| Daily (async) | Hằng ngày trên Discord | 5 phút/người | Hôm qua / Hôm nay / Vướng mắc |
| Sync giữa sprint | Thứ Năm | 20 phút | Gỡ vướng, điều chỉnh phạm vi |
| Sprint Review | Chủ nhật | 30 phút | Demo, chạy eval, cập nhật SRS |
| Retrospective | Chủ nhật (sau Review) | 20 phút | Giữ / Bỏ / Thử |

## Rủi ro kế hoạch & phương án dự phòng

| Rủi ro | Dấu hiệu | Phương án |
|---|---|---|
| Crawl/cleaning lâu hơn dự kiến | S2 chưa index xong toàn bộ | S3 chạy trên tập con đã index; TV3 hỗ trợ TV2 |
| Rerank CPU quá chậm | p95 > 1 s ở S3 | Đổi MiniLM, giảm top-N, cache; quyết định ở Review S3 |
| Chất lượng chưa đạt ở S4 | Recall@5 < 0.8 | Ưu tiên dữ liệu & retrieval, hoãn các thẻ Could |
| Thành viên bận/ốm | Velocity giảm > 30% | Cắt thẻ Should/Could; S6 là buffer |
| Yêu cầu thay đổi nhiều | Nhiều thẻ CHANGE-REQ | Xử lý theo SRS §9, chỉ nhận vào sprint kế tiếp |

