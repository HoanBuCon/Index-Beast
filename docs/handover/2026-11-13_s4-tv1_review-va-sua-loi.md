# TV1 Sprint 4 · Review phần việc TV1 và sửa lỗi

Nhánh `fix/s4-tv1-review-auth-hardening`, tách từ `feature/s4-tv1-feedback-eval-auth` (PR #96 chưa merge nên các sửa chữa dựa trên nhánh đó). Phạm vi review: đăng nhập Discord, quyền sở hữu hội thoại, feedback, `eval_runs`, runner dữ liệu, test e2e, cấu hình và CI của TV1. Không có thay đổi hành vi nào với khách và bot.

## Kết quả review

Không có lỗi nghiêm trọng. Đăng nhập kiểm đúng các điểm hay sai: `state` dùng một lần và khớp cookie, PKCE, token phiên chỉ lưu băm, `next` chỉ nhận đường dẫn tương đối (và luôn nối sau `WEB_URL`), `user_id` do server gắn nên client không giả mạo được, quản trị viên suy ra mỗi request, API không mở cổng ra ngoài Caddy nên `X-Forwarded-For` đáng tin.

| # | Mức | Phát hiện | Xử lý |
|---|---|---|---|
| 1 | Trung bình, bảo mật | `ENVIRONMENT=prod` vẫn khởi động được khi bật đăng nhập mà `WEB_URL` còn `http://`, cookie phiên khi đó không có cờ `Secure`. | `ensure_safe_for_environment` từ chối khởi động. |
| 2 | Trung bình, riêng tư | `/auth/me`, `/me/conversations`, các chuyển hướng đăng nhập và `/auth/logout` không có `Cache-Control: no-store`; proxy hoặc trình duyệt có thể giữ dữ liệu theo người dùng hoặc phản hồi có `Set-Cookie`. | Router `auth` gắn `no-store`; route tự trả `Response` đi qua `_private` (dependency không phủ được loại này). |
| 3 | Thấp, nợ kỹ thuật | Phiên hết hạn chỉ được dọn khi chính người đó đăng nhập lại: người không quay lại để rác mãi, chỉ mục `expires_at` không được dùng. | `create_session` xóa mọi phiên hết hạn (một câu lệnh có chỉ mục). |
| 4 | Thấp, mã | `_trusted_service` là hàm private nhưng ba module route import. | Đổi thành `is_trusted_service`. |
| 5 | Thấp, mã | `services/auth.py` import `repositories` trong hàm mà không có vòng import. | Đưa lên đầu file. |
| 6 | Thấp | `eval_runs --from-json` với file không tồn tại, hỏng, hoặc không phải object in traceback. | Báo lỗi gọn bằng `SystemExit`. |

Lint (`ruff check` và `format`) sạch trước và sau. Các cảnh báo của bộ luật bảo mật mở rộng (`B008` cho `Depends`, `S105` cho tên header, `S101` trong test) là mẫu dùng chuẩn của FastAPI/pytest, không sửa.

## Cố ý không sửa (tránh làm quá)

- Xóa khóa `state` Redis khi người dùng từ chối: khóa tự hết hạn sau 10 phút, đã giới hạn theo IP.
- Lưu đệm kết quả `admin_hashes` mỗi request: vài HMAC nhỏ, không đáng.
- Sau khi nhận hội thoại về tài khoản, người giữ `conversation_token` cũ vẫn đọc được. Đây là quyết định thiết kế (tương thích khách); nếu muốn chặt hơn, xóa token khi nhận hội thoại, cần chủ dự án quyết.
- **Không bao giờ đổi `AUTH_SECRET`** sau khi có người dùng: băm Discord ID đổi nên mọi người thành tài khoản mới và mất hội thoại đã nhận. Đã ghi ở cấu hình; chưa có cơ chế xoay khóa.

## Kiểm chứng

1064 unit test đạt (thêm: `no-store`, từ chối cookie không `Secure` ở prod, file JSON sai của `eval_runs`); integration test (auth, pipeline e2e) đạt, gồm ca mới dọn phiên hết hạn của người khác; `export_openapi --check` đạt (hợp đồng API không đổi); coverage `app/rag` vẫn trên ngưỡng 60%.
