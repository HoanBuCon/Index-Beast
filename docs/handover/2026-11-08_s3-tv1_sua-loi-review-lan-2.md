# Sửa 3 lỗi tìm thấy ở lần review thứ hai phần Sprint 3 của TV1

| | |
|---|---|
| Ngày | 08/11/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `fix/s3-tv1-review-fixes-2` (từ `develop` tại `09999f8`) |

## Đã sửa

| # | Lỗi | Sửa |
|---|---|---|
| 1 | **Allowlist IP của Caddy staging không có tác dụng.** `respond @denied 403` đứng rời xếp sau `handle` theo thứ tự directive của Caddy, nên không bao giờ chạy: `STAGING_ALLOW_IPS=192.0.2.1/32` vẫn cho IP khác vào (đã tái hiện bằng Caddy 2.8, trả 200 và 502) | Đổi thành `handle @denied { respond 403 }` đặt trước các `handle` khác. Kiểm lại với đúng `infra/Caddyfile.staging`: IP ngoài allowlist 403 (cả `/` lẫn `/api`), IP trong allowlist qua được, không mật khẩu vẫn 401. Thêm test chặn việc quay lại `respond` rời. |
| 2 | **`/admin/*` không giới hạn số lần thử token** (60 lần sai liên tiếp đều 401, không có 429) | Đếm lần sai theo IP trong Redis; quá `RATE_LIMIT_PER_MINUTE` (mặc định 10) lần sai trong một phút thì 429 kèm `Retry-After`, **kể cả khi lần sau đúng token**. Chỉ đếm lần sai nên dùng đúng token không bao giờ bị chặn. Redis lỗi thì 503 (đóng cửa, giống `/chat`). Chưa đặt `ADMIN_TOKEN` thì vẫn 404 và không chạm Redis. `require_admin` thành `async`. |
| 3 | `deploy.sh` chạy `chown -R 10001` lên `backend/data` và `backend/models` mỗi lần deploy: đổi chủ thư mục khiến user `deploy` không rsync thêm dữ liệu được nữa | Bỏ `chown`. Container chỉ **đọc** hai thư mục này nên chỉ đảm bảo quyền đọc cho "other" (`find ... chmod o+r`). `docs/staging.md` bỏ cách "để lần chạy đầu tự tải model": model phải chép sẵn vì container không ghi được. |

## Kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Backend unit test, ruff | 869 passed; ruff đạt |
| Caddy 2.8 với `Caddyfile.staging` thật (chỉ đổi địa chỉ site sang HTTP), `caddy validate` | 403, 200/502 và 401 đúng như trên; cấu hình hợp lệ |
| API và Redis thật: 14 lần sai liên tiếp | 10 lần 401 rồi 4 lần 429; token đúng ngay sau đó cũng 429 (`retry-after`); sau khi xóa bộ đếm, token đúng 200; 25 lần đúng liên tiếp đều 200 |

## Giới hạn

- Giới hạn theo từng IP: kẻ tấn công dùng nhiều IP vẫn thử được nhiều hơn. Với token 64 ký tự hex thì không đáng lo; token yếu vẫn yếu.
- `deploy.sh` và `bootstrap.sh` vẫn chưa chạy trên VPS thật.
- Trường hợp truy cập `/admin/*` qua proxy: IP lấy từ `X-Forwarded-For` giống `/chat` (`--proxy-headers`).
