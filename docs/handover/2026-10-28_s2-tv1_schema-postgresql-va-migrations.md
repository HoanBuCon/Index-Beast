# Sprint 2 TV1: schema PostgreSQL và migrations

| | |
|---|---|
| Ngày | 28/10/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `feature/s2-tv1-schema-postgres` (từ `origin/develop`; chưa có PR khi viết tài liệu này) |
| Thẻ Trello | *Schema PostgreSQL & migrations* |

## Phạm vi

Mô hình dữ liệu theo SRS §6, migration đầu tiên, tầng repository và dependency session. API vẫn dùng dịch vụ mock của nhánh hợp đồng API; nối API với DB thuộc S3.

## Đã làm

- **8 bảng** trong `backend/core/db/models.py`: `documents`, `chunks`, `entities`, `conversations`, `messages`, `feedback`, `ingestion_jobs`, `eval_runs`. Khóa chính UUID, thời gian `timestamptz`, enum dạng text + `CHECK`.
- **Migration** `backend/migrations/versions/0001_initial_schema.py` (sinh bằng autogenerate, đã đọc lại). `migrations/env.py` chạy async; URL lấy từ cấu hình, test có thể ghi đè bằng `sqlalchemy.url`.
- **Repository** `backend/core/db/repositories.py`: tạo/đọc hội thoại, thêm tin nhắn, N tin gần nhất, feedback, upsert document theo `(source, source_id)`, thay toàn bộ chunk của một document, ghi và đóng job ingest. Hàm chỉ flush; nơi gọi quyết định commit.
- **Dependency** `get_session` trong `app/api/deps.py`: một transaction cho mỗi request.

## Quyết định cần team biết

- `chunks` có thêm `game_scope` (sao chép từ document) để lọc không cần join; `documents.game_scope` để NULL khi chưa rà soát, theo ADR-004 và handover TV2.
- `chunks.source_type` chỉ nhận `in_game_text`, `wiki_prose`, `speculation`. TV2 cần dùng đúng ba giá trị này.
- `chunks.id` do ingest sinh (uuid5 từ document và ordinal), không tự sinh ở DB, để upsert idempotent.
- `messages.created_at` dùng `clock_timestamp()` thay `now()`: test với Postgres thật cho thấy `now()` làm mọi tin trong cùng transaction trùng giờ nên sai thứ tự.
- `feedback` cho phép nhiều dòng trên một message (ghi log, chưa ràng buộc duy nhất).
- `ingestion_jobs.external_id` lưu mã job của CLI (vd. `crawl-2301a25ddbc1`); `log` là JSONB.
- `entities` chưa có cột thuộc tính khác ngoài tên, alias, loại, nguồn; TV3 báo nếu cần thêm khi làm thẻ fanapis.

## Cách dùng

Từ `backend/`, sau `make up`:

```bash
python -m alembic upgrade head        # hoặc make migrate
python -m alembic revision --autogenerate -m "mô tả"   # sau khi sửa models.py; đọc lại file sinh ra
```

## Kiểm tra đã chạy

- `pytest` backend: 79 passed (không gồm integration); `ruff check` và `ruff format` đạt.
- `pytest -m integration tests/integration/test_db_schema.py`: 10 passed trên PostgreSQL 18.6 thật. Mỗi lần chạy tạo một database tạm và xóa đi. Test kiểm: migration tạo đủ bảng, models khớp migration (không lệch), downgrade rồi upgrade sạch, thứ tự tin nhắn, JSONB, `CHECK`, upsert idempotent, thay chunk, trạng thái job.
- `alembic upgrade head` đã chạy thật trên DB dev: 9 bảng (8 bảng + `alembic_version`).
- Chưa chạy: CI trên GitHub, Dockerfile chạy migration lúc khởi động (chưa làm; hiện chạy tay bằng `make migrate`).

## Còn lại

- Review với TV2 (chunk/document/job) và TV3 (entities).
- Quyết định có cho container `api` tự chạy migration khi khởi động hay giữ chạy tay.
- Nối `/chat` và `/feedback` với repository ở S3 (thay dịch vụ mock).
