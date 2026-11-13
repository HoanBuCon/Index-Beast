# ADR 005 Đăng nhập người dùng

Ngày: 2026-11-13. Trạng thái: **Đề xuất, chờ nhóm duyệt.** Bản cài đặt backend nằm cùng nhánh `feature/s4-tv1-feedback-eval-auth`. Thay thế quyết định "web ẩn danh ở v1" đã ghi trong SRS (TBD-04) nhưng chưa có file ADR trước đây.

## Bối cảnh

- Web hiện ẩn danh: mỗi hội thoại có một `conversation_token` ngẫu nhiên, chỉ băm của token nằm trong PostgreSQL (`conversations.client_user_ref`). Mất token là mất quyền đọc và tiếp tục hội thoại; không đồng bộ giữa các thiết bị.
- Quản trị dùng **một** `ADMIN_TOKEN` chung, không biết ai đang dùng.
- Sprint 4 yêu cầu "Auth service": toàn bộ tính năng đăng nhập để chuẩn bị triển khai lên cloud/VPS ở Sprint 5.
- Người dùng mục tiêu là người chơi Elden Ring trên Discord, và bot Discord đã dùng chung một ứng dụng Discord.

## Quyết định

1. **Đăng nhập bằng Discord OAuth2** (authorization code + PKCE, scope `identify`). Không làm email/mật khẩu: không phải lưu mật khẩu, không phải làm quên mật khẩu hay xác minh email.
2. **Chế độ khách vẫn còn.** Đăng nhập là tùy chọn: người đăng nhập có lịch sử đồng bộ và quyền theo vai trò; khách dùng như hiện nay. Đổi thành bắt buộc đăng nhập chỉ cần một cờ cấu hình ở bước sau, không đổi mô hình dữ liệu.
3. **Phiên lưu trong PostgreSQL** (bảng `auth_sessions`), cookie `httpOnly`, `SameSite=Lax`, `Secure` khi web chạy HTTPS. Cookie chứa token ngẫu nhiên 32 byte; DB chỉ lưu SHA-256 của token. Không dùng JWT (không thu hồi được trước hạn) và không lưu phiên trong Redis (Redis cấu hình `allkeys-lru` có thể xóa phiên).
4. **Riêng tư (NFR-PRIV-01):** chỉ lưu `HMAC-SHA256(AUTH_SECRET, discord_id)`, không lưu Discord ID thô; lưu thêm tên hiển thị để chào người dùng.
5. **Vai trò:** `user` và `admin`. Admin theo danh sách `AUTH_ADMIN_DISCORD_IDS` trong cấu hình, **suy ra ở mỗi request** (không lưu vai trò trong DB) nên gỡ một ID khỏi danh sách có hiệu lực ngay, không đợi phiên hết hạn. `ADMIN_TOKEN` giữ lại cho công cụ và vận hành (không phụ thuộc đăng nhập).
6. **Hội thoại thuộc về người dùng:** thêm `conversations.user_id`. Hội thoại tạo lúc đang đăng nhập gắn sẵn; hội thoại khách cũ được **nhận lại** bằng `conversation_token`. Chủ sở hữu đọc và tiếp tục hội thoại từ thiết bị khác mà không cần token.
7. **Bot Discord không đổi:** vẫn dùng `X-Service-Token` và `external_ref`.
8. **Chống tấn công:** `state` ngẫu nhiên dùng một lần (Redis, 10 phút) và khớp cookie; PKCE; `next` chỉ nhận đường dẫn tương đối; kiểm `Origin` trên các lệnh ghi dùng cookie; giới hạn tần suất bắt đầu đăng nhập theo IP; `AUTH_SECRET` tối thiểu 32 ký tự.

## Phương án đã cân nhắc

| Phương án | Lý do không chọn |
|---|---|
| Email và mật khẩu | Thêm quên mật khẩu, xác minh email, băm mật khẩu; rủi ro bảo mật và khối lượng lớn cho một sprint |
| JWT không trạng thái | Không thu hồi được trước hạn; phải quản lý khóa ký và refresh |
| Phiên trong Redis | Redis có thể xóa khóa khi đầy bộ nhớ, người dùng bị đăng xuất bất ngờ |
| Bắt buộc đăng nhập ngay | Làm hỏng cách dùng hiện tại (khách, bot), chưa có số liệu cần thiết |

## Hệ quả

- **Cần địa chỉ HTTPS thật để chạy trên cloud:** Discord chỉ chấp nhận `http://` cho `localhost`. Staging hiện dùng IP với chứng chỉ nội bộ, nên OAuth trên staging cần tên miền. Phát triển cục bộ dùng `localhost` được.
- Cần khai báo URL callback trong Discord Developer Portal và đặt `DISCORD_CLIENT_SECRET`, `AUTH_SECRET`.
- Thêm migration `0004` (bảng `users`, `auth_sessions`, cột `conversations.user_id`).
- Web (TV4) cần nút đăng nhập, trạng thái "Xin chào …", đăng xuất, danh sách hội thoại; hợp đồng ở `docs/api/auth-tv4.md`.
- Dữ liệu hội thoại sau này gắn với tài khoản: cần quy trình xóa tài khoản và dữ liệu (chưa làm ở S4, ghi vào việc còn lại).
- SRS thêm nhóm yêu cầu `FR-AUTH-*`; FR-WEB-09 chuyển từ Deferred sang In Progress.

## Chưa quyết (cần chủ dự án chọn)

- Có chuyển sang **bắt buộc đăng nhập** ở v2 không.
- Có thêm nhà cung cấp khác ngoài Discord không.
- Có xóa chế độ khách khi lên production không.
