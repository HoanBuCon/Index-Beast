# Đăng nhập Discord: hợp đồng cho web (TV4)

Backend: TV1 · Sprint 4 · [ADR-005](../adr/005-dang-nhap.md) (đề xuất). Nguồn chính xác của kiểu dữ liệu là [`openapi.json`](openapi.json).

## Nguyên tắc

- **Khách vẫn dùng được.** Mọi thứ cũ chạy như trước; đăng nhập chỉ thêm tính năng.
- **Web không bao giờ thấy token phiên.** Phiên là cookie `httpOnly` do server đặt; gọi API cùng origin (proxy Vite hoặc Caddy), **không** cần `credentials` đặc biệt, **không** lưu gì vào `localStorage`.
- Chỉ hiện nút đăng nhập khi `GET /api/v1/chat/capabilities` trả `"auth_available": true`.

## Luồng

```text
1. Người dùng bấm "Đăng nhập"  →  điều hướng trình duyệt (không phải fetch) tới
   /api/v1/auth/discord/login?next=/duong-dan-quay-ve
2. Server đặt cookie ib_oauth, chuyển (302) sang Discord
3. Người dùng cấp quyền trên Discord
4. Discord gọi /api/v1/auth/discord/callback; server tạo phiên, đặt cookie ib_session,
   chuyển (302) về WEB_URL + next
5. Web tải lại trạng thái: GET /api/v1/auth/me
```

Người dùng bấm "Từ chối" trên Discord thì được đưa về `/?login=denied`: web nên hiện thông báo nhẹ nhàng.

## Endpoint

| Method | Đường dẫn | Mô tả | Lỗi |
|---|---|---|---|
| GET | `/auth/discord/login?next=/` | Bắt đầu đăng nhập, trả 302. `next` chỉ nhận đường dẫn tương đối (`/...`); giá trị khác bị đổi thành `/` | 404 chưa cấu hình; 429 quá 10 lần/phút/IP |
| GET | `/auth/discord/callback` | Do Discord gọi, **web không gọi** | 400 phiên đăng nhập hết hạn hoặc không hợp lệ; 502 Discord lỗi |
| GET | `/auth/me` | Luôn 200: `{"authenticated": false, "user": null}` hoặc `{"authenticated": true, "user": {"id", "display_name", "is_admin"}}` | 503 DB lỗi |
| POST | `/auth/logout` | Xóa phiên, 204. Gọi bằng `fetch` từ trang của mình | 403 nếu `Origin` lạ |
| GET | `/me/conversations` | Hội thoại của tôi, mới nhất trước, tối đa 50: `[{"id", "title", "created_at"}]` | 401 chưa đăng nhập |
| POST | `/me/conversations/claim` | Nhận hội thoại khách: body `{"conversation_id", "conversation_token"}`, trả 204 | 401 sai token hoặc chưa đăng nhập; 404 không có hoặc đã có chủ khác; 403 `Origin` lạ |

Tiền tố chung `/api/v1`.

## Việc web cần làm

1. **Đọc `auth_available`** từ `/chat/capabilities`; chỉ hiện nút đăng nhập khi `true`.
2. **Khi tải trang và sau khi quay về từ Discord:** gọi `/auth/me` để biết trạng thái; hiện `display_name` và nút đăng xuất.
3. **Sau khi đăng nhập, nhận lại hội thoại khách:** với mỗi hội thoại đang lưu ở trình duyệt có `serverId` và `serverToken`, gọi `POST /me/conversations/claim`. 404 nghĩa là hội thoại đã có chủ khác hoặc không còn; bỏ qua.
4. **Danh sách hội thoại khi đã đăng nhập:** dùng `/me/conversations`; mở một hội thoại bằng `GET /conversations/{id}` **không cần** `X-Conversation-Token` (server nhận ra chủ sở hữu qua cookie).
5. **Tiếp tục hội thoại ở thiết bị khác:** gửi `/chat` hoặc `/chat/stream` với `conversation_id`, **không cần** `conversation_token` khi đã đăng nhập.
6. **Hội thoại mới tạo khi đang đăng nhập** tự gắn vào tài khoản; web vẫn nhận `conversation_token` như cũ.
7. **Đăng xuất:** `POST /auth/logout`, rồi coi như khách.

## Quản trị viên

Người đăng nhập có Discord ID trong `AUTH_ADMIN_DISCORD_IDS` có `is_admin: true` và vào được `/admin/*` **không cần** `X-Admin-Token`. Trang Admin chỉ cần `fetch` cùng origin: cookie được gửi tự động. Nút nhập token vẫn dùng được cho vận hành.

## Cài đặt môi trường (chạy cục bộ)

1. Tạo ứng dụng trên Discord Developer Portal (dùng chung ứng dụng của bot được); trong **OAuth2** thêm Redirect: `http://localhost:15173/api/v1/auth/discord/callback`.
2. Trong `.env`: `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `AUTH_SECRET` (`openssl rand -hex 32`, từ 32 ký tự), tùy chọn `AUTH_ADMIN_DISCORD_IDS`. Chạy `make env` để thêm các biến còn thiếu.
3. `make migrate` (migration `0004`), rồi khởi động lại API. Đăng nhập lưu hội thoại cần `CHAT_PERSISTENCE=postgres`.
4. **Trên cloud cần HTTPS thật:** Discord chỉ chấp nhận `http://` cho `localhost`. Đặt `WEB_URL=https://...`: cookie tự có cờ `Secure`.

## Giới hạn hiện tại

- Chưa thử với Discord thật (cần client secret và người bấm). Phần gọi Discord được kiểm bằng giả lập.
- Chưa có xóa tài khoản và dữ liệu (FR-AUTH-08).
- Cần `CHAT_PERSISTENCE=postgres` để hội thoại thuộc về tài khoản; chế độ `memory` chỉ cho phép đăng nhập, không có lịch sử.
