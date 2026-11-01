# Cập nhật techstack RAG của TV3 và setup toàn bộ hệ thống trên máy TV1

| | |
|---|---|
| Ngày | 01/11/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `docs/s3-tv1-techstack-rag-va-setup` (từ `origin/develop` tại `fc23c66`) |
| Căn cứ | Handover TV3 ngày 31/10: [overview routing](2026-10-31_s2-tv3_overview-routing.md), [VI→EN retrieval](2026-10-31_s2-tv3_vi-en-retrieval.md), [sửa JSON output](2026-10-31_s2-tv3_sua-rag-json-output.md), [DeepSeek live output](2026-10-31_s2-tv3_deepseek-live-output.md), [nối ảnh backend–web](2026-10-31_s2-tv3_noi-anh-backend-web.md) |

## 1. Tài liệu đã cập nhật

Không có nhánh/PR nào của TV3 chưa merge. Phần TV3 thêm (PR #45, #47, #54) là thành phần mới của luồng RAG, **không thêm thư viện** (`requirements*.txt`, `package.json` không đổi).

- [`docs/01_TECHSTACK.md`](../01_TECHSTACK.md) lên v1.5:
  - Phục hồi đầu ra JSON hỏng tối đa 1 lần (`RAG_FORMAT_RETRIES`, `app/rag/output.py`).
  - Viết lại truy vấn VI→EN và chế độ `dual` gộp bằng RRF (`RAG_QUERY_MODE`, `app/rag/query_plan.py`, timeout 8 s, 512 token).
  - Định tuyến câu hỏi tổng quan không gọi LLM (`RAG_OVERVIEW_ENABLED`, `app/rag/overview.py`).
  - Ngân sách truy xuất 20 s (`RAG_RETRIEVAL_TIMEOUT_SECONDS`).
  - Phạm vi đã chốt: base + SotE, lore và gameplay/build.
- [`docs/04_ARCHITECTURE.md`](../04_ARCHITECTURE.md): phạm vi đã chốt; thư mục `rag/` thêm `overview`, `query_plan`, `output`.

## 2. Setup trên máy TV1

| Hạng mục | Trạng thái |
|---|---|
| Python 3.11.9 + venv backend | Đã cài lại theo `requirements-dev.txt` + `constraints.txt`; `pip check` sạch |
| Node 24.22.0, `web/` và `bot/` | `node_modules` khớp lockfile (`npm ls` không báo thiếu) |
| Docker: PostgreSQL 18.6, Qdrant 1.19.2, Redis 8.10.2 | `make up`: cả ba healthy |
| Migration | `0001 (head)` |
| `.env` gốc | Thêm 30 biến còn thiếu theo `.env.example` (chat/RAG, bảo vệ API, `WEB_HOST`); `CHAT_MODE=rag`; `LLM_MAX_TOKENS` 2048 → 4096 theo mức TV3 đã smoke test. **Không ghi giá trị bí mật** |
| Model E5/BM25 | Đã có ở `backend/models/fastembed` (tải lúc index ngày 31/10) |
| `.claude/launch.json` | Cấu hình `api` và `web` để chạy trong Browser pane của app; chỉ dùng local, không commit |

## 3. Dữ liệu đã nạp

| Tầng | Nguồn | Trạng thái trên máy TV1 |
|---|---|---|
| Raw | `data/raw/wikigg/snapshots` (4.164 trang) | Có sẵn từ TV2 |
| Clean | `data/clean_runs/s2-full-v2` | Có sẵn từ TV2 (bản chính thức) |
| Chunk | `data/chunk_runs/s2-full-v1` (23.765 chunk) | Có sẵn từ TV2 |
| PostgreSQL | `load_full` ngày 31/10 | documents 4.164, chunks 23.765 |
| Qdrant `lore_chunks` | `ingest index --policy pilot --languages en` ngày 31/10 | 18.368 point, green |
| Ảnh | `media/blobs`, `images.csv`, manifest | Đủ đường dẫn theo cấu hình mặc định |
| `entities` | — | **0 dòng: chưa có mã nạp** (mục 5) |

Không clean/chunk lại: bản chính thức đã có, và sửa cleaner ở PR #53 chưa làm chunk khác đi (khối chỉ số vẫn `excluded`).

## 4. Khởi chạy và thử nghiệm (01/11)

- API (`make api`, cổng 18000): `/api/v1/health` = `{"status":"ok","checks":{"postgres":true,"redis":true,"qdrant":true}}`.
- `POST /api/v1/chat` ở `CHAT_MODE=rag`: trả 503 `Chưa cấu hình DeepSeek API key.` (đúng, vì `.env` chưa có key).
- Truy xuất thật bằng `scripts.check_retrieval` (embedding câu hỏi + Qdrant, không gọi LLM):

| Câu hỏi | Top kết quả |
|---|---|
| Who are Ranni's parents? | Ranni the Witch, Godwyn the Golden, Miquella of the Haligtree |
| Ranni là ai? | Ranni the Witch, Letter for Freyja, Ranni's Rise |
| How do I start Ranni's quest? | Ranni the Witch ×2, Ranni's Rise, Three Sisters, Preceptor Seluvis |
| Moonveil weight and requirements | Moonveil, Unique Skill: Transient Moonlight, nhưng **không có** Weight/thuộc tính (chưa vào corpus) |

- Web (`make web`, cổng 15173): trang chat hiển thị.
- **Chat RAG thật qua DeepSeek** (sau khi người dùng điền key và đặt `CHAT_MODE=rag`; 4 câu, `POST /api/v1/chat`, thinking tắt):

| Câu hỏi | HTTP / thời gian | Kết quả |
|---|---|---|
| Who are Ranni's parents? | 200 / 5,8 s | Radagon và Queen Rennala; 3 nguồn (Ranni the Witch Infobox, Background; Empyreans); 2 ảnh |
| Ranni là ai? Cha mẹ cô là ai? | 200 / 2,2 s | Trả lời tiếng Việt, giữ tên riêng tiếng Anh; cha mẹ và hai anh Radahn, Rykard; 3 nguồn; 2 ảnh |
| Các boss chính trong Elden Ring là ai? | 200 / 3,9 s | Đi nhánh câu hỏi tổng quan: dẫn trang Bosses (Introduction, Mandatory bosses, Remembrance base/SotE), liệt kê boss bắt buộc; 4 nguồn; 3 ảnh |
| Moonveil nặng bao nhiêu và cần bao nhiêu Intelligence? | 200 / 1,8 s | Không bịa số: nêu rõ nguồn không có trọng lượng và yêu cầu Intelligence. Đúng với hiện trạng: chỉ số chưa vào corpus (đề xuất dữ liệu #2) |

  Cả 4 câu `grounded=true`. Mình đọc lại câu trả lời so với tiêu đề/section nguồn; chưa đối chiếu từng câu với text gốc.
- Lần chạy đầu sau khi điền key vẫn trả mock vì `.env` ghi `CHAT_MODE=mock` (giá trị mặc định của `.env.example`); người dùng đổi sang `rag` và khởi động lại API.
- **Chưa chạy:** `/chat/stream` (SSE) qua web với DeepSeek thật; bot Discord (cần `DISCORD_TOKEN` và `API_SERVICE_TOKEN` thật).

## 5. Phát hiện

1. **Thẻ "Crawler fanapis → bảng entities" (TV3) đã ở *Hoàn thành* nhưng mã chưa có:** `ingest/sources/fanapis.py` và `ingest/entities/aliases.py` vẫn là khung 4 dòng, nên bảng `entities` trống. Cần TV3 xác nhận và mở lại thẻ ở S3.
2. Ổ C: còn 3,6 GB, H: còn 13 GB. Cần theo dõi khi index lại hoặc chạy clean/chunk mới.

## 6. Cách chạy lại trên máy TV1

1. `make up` (Docker), sau đó `make api` và `make web` ở hai terminal (hoặc `make dev`).
2. `.env` cần `DEEPSEEK_API_KEY` và `CHAT_MODE=rag`; sửa `.env` thì phải khởi động lại API.
3. Mở http://localhost:15173. Mỗi câu hỏi tốn credit DeepSeek; rate-limit mặc định 10 câu/phút.
