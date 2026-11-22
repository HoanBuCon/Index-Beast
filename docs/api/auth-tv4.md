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
| DELETE | `/me` | Xóa tài khoản, mọi phiên và các hội thoại đã gắn với tài khoản (gồm hội thoại khách đã nhận qua `claim`) cùng tin nhắn, feedback, ký ức; hội thoại khách chưa nhận và hội thoại Discord không gắn tài khoản nên không bị xóa ở đây (retention 90 ngày hoặc `/clear` của bot xóa chúng); xóa cookie phiên; trả 204, **không hoàn tác**. Web nên hỏi xác nhận trước | 401 chưa đăng nhập (gồm cả khi gọi lại sau khi đã xóa); 403 `Origin` lạ; 503 không xóa được, chưa mất dữ liệu nào, thử lại |

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
- Đã có API xóa tài khoản và giao diện xác nhận; kiểm thử tự động dùng phiên giả lập, không xóa tài khoản thật.
- Cần `CHAT_PERSISTENCE=postgres` để hội thoại thuộc về tài khoản; chế độ `memory` chỉ cho phép đăng nhập, không có lịch sử.

## TV4 · Menu tài khoản và điều hướng (22/11/2026)

- `/` và `/login` là màn đăng nhập; `/chat` vẫn mở cho khách qua **Dùng thử**.
- Menu tài khoản nằm cuối sidebar, luôn truy cập được cả khi thu gọn. Khách có **Đăng nhập**; người có phiên có **Trang đăng nhập**, **Đăng xuất**, **Xóa tài khoản**. **Quản trị** hiện khi phiên có `is_admin` hoặc API đã bật khả năng quản trị bằng token. API vẫn kiểm quyền cho mọi thao tác.
- Từ menu vào `/login?next=...`; web chỉ nhận đường quay lại `/chat`, `/about`, `/admin` (có thể kèm query/fragment). Giá trị ngoài ứng dụng, percent-encoded nguy hiểm, ký tự điều khiển hoặc màn không tồn tại được đổi thành `/chat`.
- Đăng xuất hoặc xóa tài khoản thành công đưa về `/login` và dọn bản hội thoại của tài khoản ở trình duyệt theo cơ chế hiện có. Khi POST logout lỗi, chỉ kết luận hết phiên nếu `/auth/me` trả thành công với `authenticated: false, user: null`; lỗi mạng/503 giữ trạng thái để thử lại.
- Xóa tài khoản cần xác nhận; lỗi giữ hộp thoại cùng thông báo và cho thử lại. Esc/Hủy không gọi DELETE.

### Google: phần client đã sẵn sàng, backend chưa triển khai

**Hợp đồng đề xuất bàn giao cho TV1, chưa phải endpoint hiện có trong OpenAPI:**

1. Thêm boolean tùy chọn `google_auth_available` vào `GET /api/v1/chat/capabilities`, chỉ trả `true` sau khi Google OAuth phía server thực sự sẵn sàng. Web hiện coi thiếu trường hoặc sai kiểu là `false`, độc lập với Discord `auth_available`.
2. `GET /api/v1/auth/google/login?next=...` bắt đầu luồng OAuth qua chuyển hướng trình duyệt. Web đã có URL builder và nút dùng đường dẫn này khi capability được bật. Backend phải kiểm lại `next`, thực hiện callback, kiểm state/PKCE và thông tin từ Google, tạo phiên cookie httpOnly rồi đưa về trang yêu cầu.
3. Dùng lại hợp đồng `/auth/me`, `/auth/logout`, `/me/conversations`, `/me` cho cả hai nhà cung cấp; frontend không tự tạo phiên hoặc xử lý token của Google.

Hiện `ChatCapabilities` của backend chưa có `google_auth_available`, chưa có route Google. Vì vậy bản đang chạy hiển thị Google **chưa khả dụng**; không bật bằng biến Vite hoặc đưa client secret vào trình duyệt. Discord chỉ bật khi `auth_available` là `true`. Bản local kiểm ngày 22/11 có `auth_enabled=false`, nên cần TV1/người quản trị cấu hình OAuth trước khi đăng nhập thật.
