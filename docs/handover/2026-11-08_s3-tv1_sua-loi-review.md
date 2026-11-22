# Sửa 9 lỗi tìm thấy khi review phần Sprint 3 của TV1

| | |
|---|---|
| Ngày | 08/11/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `fix/s3-tv1-review-fixes` (từ `develop` tại `8efc487`) |

## Đã sửa

| # | Lỗi | Sửa |
|---|---|---|
| 1 | Trong container `REPO_ROOT` là `/` (mã ở `/app/core`), nên encoder tìm model ở `/backend/models` và ảnh ở `/backend/data`, không khớp các mount `/app/models`, `/app/data`. **Ảnh hưởng cả compose gốc và lệnh `python -m ingest index` trong container.** | Thêm `core.config.BACKEND_ROOT` và dùng ở `factory.py`, `images.py`, `ingest/indexing.py`. Các script dev (`backend/scripts/*`) chạy trên máy host nên giữ `REPO_ROOT`. |
| 2 | `bootstrap.sh`: `systemctl reload ssh` lỗi trên Ubuntu 24.04 khi `ssh.service` chưa chạy, script dừng trước khi bật `ufw` | Bật `ufw` trước bước SSH; dùng `try-reload-or-restart ssh` rồi `restart ssh.socket`; in cấu hình sshd hiệu lực |
| 3 | `tokens_in/out` bỏ sót token của lượt gọi agent | `token_usage` cộng thêm `trace["agent"]["usage"]`. Lượt đánh giá bằng chứng và tool agent chưa ghi token nên vẫn chưa được tính. |
| 4 | Trace (tới 64 KB) nằm trong `messages.trace`, bị nạp lại cùng 64 tin nhắn mỗi lượt | Cột mới `messages.rag_trace`, `deferred`, chỉ nạp khi xem trace. **Migration `0003`: cần `alembic upgrade head`.** Trace lưu bởi PR #79 (nằm ở `trace["rag"]`) không còn được đọc; chỉ có dữ liệu thử nghiệm ngắn ngày nên không chuyển. |
| 5 | `repository.trace()` không bắt lỗi DB (trả 500) | Đổi thành `UnavailableError` (503) như `load`/`save` |
| 6 | `measure.sh` mặc định gọi `https://localhost`, Caddy chỉ phục vụ `STAGING_HOST` | Mặc định `https://$STAGING_HOST` đọc từ `.env` |
| 7 | `latency_ms` tính hai lần, DB và phản hồi lệch nhau | Tính một lần trước khi lưu. **Độ trễ trả về không còn gồm bước đồng bộ bộ nhớ ngữ nghĩa** (tối đa 5 giây, `CHAT_MEMORY_TIMEOUT_SECONDS`). |
| 8 | Docs ghi user `deploy` "không có sudo" nhưng nhóm `docker` tương đương root | Sửa chữ trong `bootstrap.sh` và `docs/staging.md` |
| 9 | `TraceOut.source` là `str` | Đổi thành `Literal["postgres", "memory"]`; `openapi.json` xuất lại |

## Kiểm tra trên máy TV1

| Kiểm tra | Kết quả |
|---|---|
| Backend unit test, ruff | 832 passed; ruff đạt |
| Test tích hợp PostgreSQL thật (gồm migration `0003` khớp model) | 11 passed |
| `bash -n` ba script staging | Đạt |

Test mới: `BACKEND_ROOT`, cột `rag_trace` deferred, lỗi DB của `trace()`, tổng token có agent.

## Chưa kiểm tra

- Chưa chạy trong container thật: lỗi #1 chỉ được kiểm bằng test đường dẫn, và `bootstrap.sh` chưa chạy trên Ubuntu 24.04 thật.
