# Staging trên VPS: compose, Caddy bảo vệ, script cài đặt, deploy và đo tài nguyên

| | |
|---|---|
| Ngày | 08/11/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `feature/s3-tv1-staging-vps` (từ `develop` tại `cb2a358`) |
| Thẻ Trello | 3.3 Staging trên VPS |
| Cấu hình VPS dự kiến | 4 vCPU, 8 GB RAM, Ubuntu 24.04; **chưa có VPS, chưa có tên miền** |

## Đã làm

- `docker-compose.staging.yml` chồng lên compose gốc: `ENVIRONMENT=prod`, `CHAT_MODE=rag`, `CHAT_PERSISTENCE=postgres`, giới hạn CPU từng service, mount `backend/models` vào api, tắt ảnh minh họa mặc định. `mem_limit` từng service đã có ở compose gốc (tổng ≈ 5,4 GB).
- `infra/Caddyfile.staging`: basic auth bắt buộc, tùy chọn lọc IP (`STAGING_ALLOW_IPS`). `STAGING_HOST` là IP VPS thì Caddy dùng CA nội bộ; là tên miền thì tự xin Let's Encrypt.
- `scripts/staging/bootstrap.sh` (root, chạy lại được): Docker, user `deploy` không có sudo, SSH chỉ bằng khóa, `ufw` mở 22/80/443, 2 GB swap.
- `scripts/staging/deploy.sh [ref]`: lấy mã, build, hạ tầng, chỉnh quyền, `alembic upgrade head`, khởi động, chờ healthy; không có `DISCORD_TOKEN` thì bỏ qua bot.
- `scripts/staging/measure.sh`: RAM/CPU trước, đỉnh trong lúc, sau khi hỏi 1 câu RAG thật.
- `.env.staging.example` và `docs/staging.md` (các bước, chép dữ liệu, rollback, bảo vệ, bảng điền số đo).

## Phát hiện khi đọc compose gốc

- **Model không vào image:** `backend/.dockerignore` loại `models` và `data`, compose gốc chỉ mount `data`. API trong container sẽ không thấy model E5. Staging mount `backend/models` để xử lý.
- **Migration không chạy tự động:** Dockerfile còn ghi chú "chạy migration trước khi khởi động" chưa làm; `deploy.sh` chạy `alembic upgrade head` rõ ràng.
- **`ENVIRONMENT` chỉ có `dev|test|prod`:** staging dùng `prod` để có kiểm tra "còn change-me" và ẩn Swagger.
- **Compose gốc mặc định `CHAT_MODE=mock` và `CHAT_PERSISTENCE=memory`:** chạy thẳng sẽ không phải RAG thật và mất hội thoại khi khởi động lại.

## Kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| `Caddyfile.staging`, `caddy validate` (2.8-alpine, có và không có biến tùy chọn) | Valid configuration |
| `docker compose ... config` với và không có `STAGING_PASSWORD_HASH` | Hợp lệ khi có; báo lỗi rõ khi thiếu |
| `bash -n` ba script | Đạt |
| Bộ phân tích đỉnh RAM của `measure.sh` trên dữ liệu mẫu | Đúng |

## Chưa làm hoặc chưa kiểm tra

- **Chưa chạy trên VPS thật** (chưa có máy): `bootstrap.sh`, `deploy.sh`, `measure.sh`, chép dữ liệu và Caddy với chứng chỉ nội bộ đều chưa được chạy. Không có shellcheck nên chỉ kiểm tra cú pháp.
- **Chưa đo RAM/CPU**; bảng trong `docs/staging.md` đang trống. Giới hạn api 3 GB với 2 worker cần kiểm chứng.
- Caddy được kiểm tra với 2.8-alpine (có sẵn trên máy); ảnh build dùng 2.11.7.
- Quy trình chép corpus (pg_dump, snapshot Qdrant) viết theo tài liệu công cụ, chưa thử khôi phục.
- Chưa có fail2ban, tự cập nhật bảo mật, giám sát, backup (thẻ Sprint 5).

## Cần từ bạn

VPS và khóa SSH để chạy lần đầu; IP của VPS (và nhóm IP được phép nếu muốn lọc).
