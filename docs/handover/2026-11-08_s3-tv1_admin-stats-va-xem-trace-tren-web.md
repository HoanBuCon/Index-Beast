# `/admin/stats` và xem trace từ giao diện web

| | |
|---|---|
| Ngày | 08/11/2026 |
| Người thực hiện | TV1 (Hoanbucon), **làm hộ TV4** phần web (`MessageList.tsx`, `ChatPage.tsx`, `AdminPage.tsx`, CSS) |
| Nhánh | `feature/s3-tv1-admin-stats-trace-ui` (từ `develop` tại `cb8636d`) |

## Vấn đề

Trang Admin gọi `/admin/stats` (chưa có API) nên nút "Kết nối" luôn báo lỗi, và web không hiển thị `message_id` nên không biết nhập gì vào ô "Tra cứu trace".

## Đã làm

**API**
- `GET /api/v1/admin/stats` (cần `X-Admin-Token`): hội thoại gần đây (20, tiêu đề là câu hỏi đầu cắt 60 ký tự), feedback gần đây (50), job ingestion (10), kết quả eval (10). Hình dạng khớp `AdminStats` mà client web kiểm nghiêm: `reason` không trả `null`, số đo eval chỉ gồm số. Lỗi PostgreSQL trả 503. Chế độ `CHAT_PERSISTENCE=memory` trả danh sách rỗng.
- `GET /api/v1/chat/capabilities` thêm `trace_available` (true khi `ADMIN_TOKEN` là giá trị thật); không lộ token.
- `Settings.admin_enabled` dùng chung cho guard admin và capabilities.
- `docs/api/openapi.json` xuất lại.

**Web**
- Khi `trace_available`, mỗi câu trả lời hoàn tất hiển thị "ID câu trả lời" và liên kết **Xem trace** tới `/admin?message_id=<id>`. Tắt hoàn toàn khi API chưa bật `ADMIN_TOKEN`.
- Trang Admin điền sẵn Message ID từ URL. Bấm "Kết nối" tải cả thống kê lẫn trace; lỗi của hai lời gọi gộp một thông báo (không lặp). **Token không đi theo URL**, vẫn chỉ giữ trong state của trang.

## Kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Backend unit test, ruff | 864 passed; ruff đạt |
| Test tích hợp PostgreSQL thật cho các truy vấn thống kê | passed |
| Web: test, typecheck, prettier | 48 passed; đạt (một lần chạy xen với tiến trình test đang tắt có 5 test lỗi, không lặp lại ở 3 lần chạy sau) |
| Chạy thật trên trình duyệt: API và Vite trên cổng tạm, database tạm có 1 hội thoại, 1 trace, 1 feedback, token giả | Câu trả lời hiện ID và "Xem trace"; bấm sang `/admin` có sẵn ID; nhập token, "Kết nối" hiện hội thoại, feedback và trace JSON |

## Chưa làm hoặc chưa kiểm tra

- Chưa kiểm tra với một câu trả lời thật qua DeepSeek (dữ liệu thử là bản ghi chèn tay).
- "Phản hồi chưa hữu ích" vẫn trống vì `/feedback` chưa lưu dữ liệu (TBD-09). "Kết quả đánh giá" trống vì chưa có bước ghi `eval_runs`.
- Trace vẫn hiển thị JSON thô.
- `/admin/ingest` (kích hoạt ingestion) chưa có.
- `X-Admin-Token` chưa nằm trong `allow_headers` của CORS; không ảnh hưởng khi web gọi cùng origin (Vite proxy, Caddy).

## Cần TV4 xem lại

Ba file web trên thuộc phần TV4; thay đổi chỉ thêm một prop tùy chọn, một dòng hiển thị và đổi cách tải ở trang Admin.
