# Báo cáo bàn giao Sprint 1 — IndexBeast (nhóm 4 Hollows)

| | |
|---|---|
| Sprint | 1 — *Nền móng & Spike kỹ thuật*, 19/10 – 25/10/2026 |
| Ngày lập | 26/10/2026 (Asia/Saigon) |
| Người lập | TV1 (Hoanbucon), Tech Lead |
| Căn cứ | Nhánh `develop` tại `bf71d68` (đã kéo về local), các handover trong [`docs/handover/`](README.md), board Trello (đọc lại ngày 26/10) và các lần chạy kiểm tra ghi ở mục 5 |

## 1. Tóm tắt

Sprint 1 đạt mục tiêu **dựng nền tảng**: repo, môi trường dev, CI, khung API, crawler wiki.gg, adapter DeepSeek, notebook RAG baseline, golden set v0, giao diện web và khung bot đều đã nằm trên `develop`, CI xanh. Trello ghi **17/17 thẻ S1 ở cột Hoàn thành**.

Đây **chưa phải một chatbot chạy được**: backend mới có `/health` và một endpoint dev gọi LLM; chưa có `/chat`, chưa có dữ liệu trong Qdrant; web chạy ở chế độ xem thử; bot chỉ có lệnh `/ping`. Đó đúng là phạm vi S1 theo kế hoạch, nhưng cần nói rõ để S2 không bị hiểu nhầm.

Có **4 điểm cần cả nhóm quyết định hoặc xử lý đầu S2** (mục 6), trong đó quan trọng nhất là hợp đồng dữ liệu giữa TV2 và TV3.

## 2. Kết quả theo thành viên

| Thành viên | Thẻ S1 (Trello) | Bằng chứng trong repo | Handover |
|---|---|---|---|
| **TV1** Hoanbucon — Backend & DevOps | 4/4: CI, monorepo & quy ước, Docker Compose, Skeleton FastAPI | PR #8, #9, #10, #11, #16, #17 (quy ước cổng) | [Nền tảng và cấu hình](2026-10-19_s1-tv1_nen-tang-va-cau-hinh.md) |
| **TV2** UncleThing — Data | 3/3: khảo sát nguồn, crawler wiki.gg, ADR-003 | PR #19; mẫu 200 trang + 1188 ảnh; `docs/data-sources.md`, `docs/adr/003-chunking.md` | [Crawler và dữ liệu ảnh](2026-10-24_s1-tv2_crawler-va-du-lieu-anh.md) |
| **TV3** MinhMuc — AI/RAG | 4/4: DeepSeek, reranker, notebook baseline, golden set v0 | PR #12, #13, #20, #22, #23 | [DeepSeek LLM](2026-10-19_s1-tv3_deepseek-llm.md) · [RAG baseline và golden set](2026-10-26_s1-tv3_rag-baseline-va-golden-set.md) |
| **TV4** vungocquy — Web & Bot | 3/3: wireframe & design system, web React, Discord bot | PR #18 (2.665 dòng web) | [`web/IMPLEMENTATION.md`](../../web/IMPLEMENTATION.md) — chưa có handover trong `docs/handover/` |

### TV1 — nền tảng
- Môi trường dev một lệnh: `make up` bật PostgreSQL 18.6, Qdrant 1.19.2, Redis 8.10.2 (đều có healthcheck). Container **không ghi log xuống đĩa** theo yêu cầu.
- Khung FastAPI mở rộng được: tài nguyên mới chỉ cần `ctx.register(...)` là có trong `/health` và tự đóng khi tắt app; log JSON có `request_id`; production từ chối khởi động nếu còn mật khẩu mẫu.
- **Cấu hình: một file `.env` ở gốc repo**; mỗi container chỉ nhận biến nó cần (bot không biết mật khẩu DB).
- **Quy ước cổng**: không dùng cổng mặc định — cổng gốc + 10000 (API 18000, web 15173, PostgreSQL 15432, Qdrant 16333, Redis 16379), có test chặn tái phạm. Xem [`quy_uoc.md`](../quy_uoc.md) §8.
- CI: ruff, unit test, integration test với service thật, build web, typecheck bot. CI từng đỏ ở mọi PR vì docstring dài; đã sửa.

### TV2 — dữ liệu
- Tập mẫu **200 trang** wiki.gg và **1.188 ảnh** (≈ 1,67 GB), kiểm checksum đạt, audit không lỗi. Lượt crawl gốc mất ≈ 24 phút, 1.391 request.
- Đã phát hiện và xử lý: Brotli lỗi, HTTP 403 ở một số truy vấn `oldid`, ảnh khai báo sai định dạng, ảnh giao diện lọt ngưỡng.
- **Dữ liệu raw và ảnh không nằm trong Git** (đã ignore); chuyển giữa các máy bằng artifact kèm checksum.

### TV3 — AI/RAG
- Adapter DeepSeek (`deepseek-flash`, tắt thinking): `complete`, `complete_json`, `stream`; lỗi không làm lộ nội dung prompt.
- Notebook baseline: e5-small + BM25 + RRF + DeepSeek trên **240 dòng `armors.csv`**. Lượt `20261025T144625694379Z`: Hit@5 **10/10**, MRR@5 **0,800**, correctness và faithfulness **20/20** trên 10 câu (do trợ lý hỗ trợ chấm, **không phải** kết quả chất lượng của chatbot).
- Golden set v0: **30 câu** (20 Việt / 10 Anh); 5 nhóm × 6 câu: nhân vật, sự kiện, địa điểm, đa bước, ngoài phạm vi; độ khó 12 easy / 12 medium / 6 hard.

### TV4 — giao diện
- Web: chat có SSE, nguồn và trích dẫn, lịch sử khách (localStorage), trang About, trang Admin, chuyển ngôn ngữ VI/EN, theme tối/vàng, responsive từ 360 px. Mặc định là chế độ **Xem thử giao diện** (dữ liệu cố định, có nhãn minh họa).
- Bot: khung lệnh, đăng ký slash command, `/ping`. `/ask`, `/help`, `/config` mới là file khung.

## 3. Những thứ đã sẵn sàng để Sprint 2 dùng ngay

| Có sẵn | Ở đâu |
|---|---|
| Môi trường dev, lệnh `make`, hướng dẫn chạy | [README](../../README.md) → "Chạy local" |
| Quy ước Git/PR, Mentor review, quy ước cổng | [`quy_uoc.md`](../quy_uoc.md) |
| Điểm mở rộng backend (tài nguyên, endpoint, middleware, cấu hình) | [Handover TV1](2026-10-19_s1-tv1_nen-tang-va-cau-hinh.md) §5 |
| Crawler, CLI `ingest`, mẫu 200 trang | [Handover TV2](2026-10-24_s1-tv2_crawler-va-du-lieu-anh.md) |
| LLM adapter, `ctx.llm` | [Handover TV3](2026-10-19_s1-tv3_deepseek-llm.md) |
| Golden set v0 và quy tắc chấm | `backend/eval/golden_set.jsonl`, [Handover TV3](2026-10-26_s1-tv3_rag-baseline-va-golden-set.md) §5 |
| Giao diện web và hợp đồng API dự kiến | [`web/IMPLEMENTATION.md`](../../web/IMPLEMENTATION.md) |
| Yêu cầu bàn giao sau mỗi nhóm task | [`docs/AGENTS.md`](../AGENTS.md), [README handover](README.md) |

## 4. Chênh lệch giữa Trello và thực tế repo

Trello ghi mọi thẻ S1 là Hoàn thành. Đối chiếu với handover và repo cho thấy một số thẻ **còn điều kiện mở**; các mục này cần được ghi nhận rõ thay vì coi là đã đóng hoàn toàn:

| Thẻ | Trello | Thực tế đã kiểm chứng |
|---|---|---|
| TV2 — ADR-003 chunking | Hoàn thành | ADR vẫn ghi **"Đề xuất, chờ review TV3 và Mentor"** |
| TV2 — Khảo sát nguồn | Hoàn thành | Đối chiếu 10 trang Fandom **chưa làm được**: `robots.txt` trả HTTP 403. TV2 tự ghi *chưa đánh dấu Done* |
| TV3 — Notebook RAG baseline | Hoàn thành | Chạy trên **240 dòng `armors.csv`**, không phải 200 trang mẫu của TV2; chưa chạy trên dữ liệu của TV2 |
| TV3 — Golden set v0 | Hoàn thành | File đủ 30 câu, nhưng mục "mỗi người đóng góp ≥ 5 câu" **chưa có bằng chứng**; nguồn chưa được TV2 review |
| TV3 — ADR-001, ADR-002 | Hoàn thành | `docs/adr/` **chỉ có ADR-003 và ADR-004**. Chưa tìm thấy file ADR-001/002 hay kết quả benchmark reranker trong repo |
| TV1 — Monorepo, branch protection | Hoàn thành | **Chưa xác minh được** từ repo: cài đặt nằm trên GitHub. Cần chủ repo xác nhận bằng ảnh chụp |
| ALL — "Cả 4 thành viên chạy được môi trường dev" | Hoàn thành | Chưa có bằng chứng từng người; đề nghị mỗi người dán kết quả `/health` vào thẻ |

## 5. Kiểm tra thực tế khi lập báo cáo (26/10, từ `develop`)

| Hạng mục | Kết quả |
|---|---|
| Backend: `ruff check`, `ruff format --check` | Đạt (117 file) |
| Backend: `pytest` (unit) | **79 passed**; 1 integration test bị loại theo cấu hình mặc định |
| Web: `format:check`, `build` | Đạt |
| Web: `npm test` | **2/2 fail trên máy lập báo cáo** (Node 22.14: `ERR_UNKNOWN_FILE_EXTENSION .ts`). Dự án yêu cầu Node 24.22, nên đây là lỗi môi trường; **chưa chạy được trên Node 24** để xác nhận test đạt |
| Bot: `typecheck`, `format:check` | Đạt |
| Golden set | 30 dòng; 20 vi / 10 en; 6 × 5 category; 12/12/6 độ khó |
| CI GitHub Actions trên `develop` | 4 lần chạy gần nhất đều **success** (mới nhất ứng với `bf71d68`) |
| Không chạy | Notebook, embedding/indexing, gọi DeepSeek, integration test, `crawl` — theo ràng buộc [`AGENTS.md`](../AGENTS.md) và vì không cần cho báo cáo |

## 6. Rủi ro và việc cần quyết định đầu Sprint 2

1. **Hợp đồng dữ liệu `RawPage → CleanDocument → ChunkRecord` chưa chốt.** TV2 đã mô tả contract raw ở `ingest/README.md` nhưng chưa sửa `core/types.py` dùng chung; ADR-003 còn ở trạng thái đề xuất. Thẻ *Embedding & indexing* của TV3 phụ thuộc trực tiếp vào output *Làm sạch + chunk* của TV2 **trong cùng sprint**. Đề nghị: chốt ADR-003 và `core/types.py` trong 1–2 ngày đầu; trong lúc chờ, TV3 viết indexing trên `ChunkRecord` với dữ liệu giả.
2. **Chưa lọc phạm vi base game ở cấp section.** Raw đang để `game_scope = null` kèm `requires_section_review`. Nếu không lọc, nội dung DLC có thể lọt vào index và trái [ADR-004](../adr/004-base-game-scope.md).
3. **Giấy phép ảnh chưa xác minh.** Toàn bộ 1.328 occurrence ảnh trong mẫu thiếu thông tin giấy phép (`unknown_review_required`). Chưa được dùng ảnh khi chưa rà trang File gốc.
4. **Hợp đồng API chưa được backend xác nhận.** Web và bot dựa trên giao kèo dự kiến theo SRS; backend chưa có `/chat`, `/chat/stream`, `/feedback`. TV1 phải chốt OpenAPI v1 và endpoint mock sớm để TV4 không làm lệch.

## 7. Nợ kỹ thuật

| Nợ | Chủ | Ghi chú |
|---|---|---|
| CI **chưa chạy `npm test` của web** (job web chỉ format + build) | TV1/TV4 | Dễ để test hỏng không ai biết; thêm bước vào CI trên Node 24 |
| `migrations/env.py` còn là khung → `make migrate` chưa chạy; Dockerfile chưa chạy migration | TV1 | Thẻ *Schema PostgreSQL* của S2 |
| `core/errors.py` (định dạng lỗi chung của API) chưa có | TV1 | S2 |
| Bảng `ingestion_jobs` chưa nối DB; job S1 chỉ là file | TV2 | FR-ING-10 chưa hoàn thành |
| ADR-001, ADR-002: chưa có file; benchmark reranker chưa có bằng chứng trong repo | TV3 | Cần để chốt SRS TBD-02 |
| `backend/eval/retrieval.py`, `answer.py` còn là khung | TV3 | Chưa có bộ chạy đánh giá |
| README notebook còn mô tả trạng thái "trước khi chạy" trong khi notebook đã có output | TV3 | Dễ gây hiểu nhầm |
| Bot: `/ask`, `/help`, `/config` còn là khung; chưa có handover của TV4 trong `docs/handover/` | TV4 | Theo `AGENTS.md`, mỗi nhóm task cần handover |
| Redis và Qdrant chưa có mật khẩu (an toàn nhờ chỉ bind `127.0.0.1`) | TV1 | Xử lý trước khi deploy, S5 |
| Image `api` ≈ 750 MB | TV1 | Xem lại khi thêm model |
| Tài liệu Word trong `docs/export/` có thể lệch so với Markdown | Cả nhóm | Tái sinh bằng `docs/export_docx.py` khi xuất tài liệu |

## 8. Hành động đề xuất cho cả nhóm

| # | Việc | Ai | Hạn |
|---|---|---|---|
| 1 | Review và chấp nhận (hoặc sửa) ADR-003; chốt `core/types.py` | TV2 + TV3 + Mentor | Đầu S2 |
| 2 | Viết ADR-001/002 và đưa kết quả benchmark reranker vào repo | TV3 | S2, tuần đầu |
| 3 | Review chéo golden set theo phân công đề xuất (Hoanbucon 001–008, UncleThing 009–016, MinhMuc 017–023, QuyVuiVe 024–030) và xác nhận đóng góp | Cả nhóm | S2, tuần đầu |
| 4 | Viết handover cho web và bot trong `docs/handover/` | TV4 | S2, tuần đầu |
| 5 | Thêm `npm test` vào CI cho web | TV1 hoặc TV4 | S2, tuần đầu |
| 6 | Xác nhận branch protection trên GitHub (PR + approve + CI + Code Owner) | Chủ repo | Ngay |
| 7 | Mỗi người **tạo lại `.env` từ `.env.example`** sau các thay đổi cổng/cấu hình, rồi dán kết quả `/health` vào thẻ | Cả nhóm | Ngay |
| 8 | Cài **Node 24.22.0** nếu chạy bot hoặc test web (Node 22 chưa chạy được file `.ts`) | Cả nhóm | Ngay |
| 9 | Ghi nhận trạng thái các thẻ ở mục 4 trên Trello cho đúng thực tế (đã làm / còn điều kiện mở) | Từng chủ thẻ | Sprint Review |

## 9. Quy tắc làm việc nhóm cần nhớ

- Mọi thay đổi qua **nhánh riêng + PR về `develop`**, Mentor review; nhánh tạo bằng `git switch --no-track -c <nhánh> origin/develop`. Không push thẳng `develop`/`main` (golden set từng bị push nhầm, đã revert bằng PR #21).
- **Không dùng cổng mặc định**; mỗi cổng một biến `*_PORT` trong `.env`.
- **Một `.env` ở gốc repo**, không ghi chú cuối dòng, không commit secret.
- **Không tự chạy** notebook, embedding/indexing hay gọi LLM nếu chưa được yêu cầu rõ (tốn credits).
- Phạm vi nội dung: **lore Elden Ring base game** (ADR-004).
- Sau mỗi nhóm task có thay đổi file: **viết handover** trong `docs/handover/`, thêm vào bảng ở README.

## 10. Sự cố nổi bật trong sprint

| Sự cố | Cách xử lý |
|---|---|
| CI đỏ ở mọi PR (docstring > 120 ký tự) | Sửa 18 docstring; pre-commit chặn từ đó |
| Ổ đĩa chứa disk image của Docker đầy → mọi container báo lỗi I/O | Giải phóng ổ, khởi động lại Docker Desktop |
| Web proxy trả 502 khi API đổi cổng | Một biến `API_PORT` duy nhất cho `make api`, Vite và bot |
| Golden set push nhầm lên `develop` | Revert qua PR #21, đưa lại qua PR #22; không reset/force-push |
| Chú thích cuối dòng trong `.env` bị compose đọc thành giá trị | Chú thích lên dòng riêng; có test chặn |

## 11. Phạm vi của tài liệu này

Báo cáo chỉ tổng hợp từ handover, lịch sử Git, trạng thái Trello và các lệnh kiểm tra tĩnh/unit nêu ở mục 5. Không có điểm đánh giá, kết quả review hay trạng thái merge nào được suy ra ngoài các nguồn đó. Thay đổi trong lần này: thêm file này, thêm một dòng vào [README handover](README.md), và **cập nhật các chỗ sai lệch kiểm chứng được trong handover TV1, TV2, TV3** (liên kết `AGENTS.md` đã chuyển vào `docs/`, trạng thái merge của PR #19 và #23, số test, trạng thái PR của TV1). Không sửa nội dung đánh giá, kết quả chạy hay nhận định của từng thành viên.
