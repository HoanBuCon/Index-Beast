# Bàn giao web — TV4

Phạm vi: mã nguồn trong `web/`, tương ứng các thẻ web S1–S5. Không triển khai nhiệm vụ backend, RAG, ingestion,
database, bot hay hạ tầng. Các ghi chú đầu tệp được giữ nguyên. README và kế hoạch chung không được chỉnh sửa.

## Chạy và kiểm tra

Tại thư mục `web`, chạy `npm.cmd ci` lần đầu, rồi `npm.cmd run dev`. Cổng đọc từ `WEB_PORT` ở `.env` gốc
(mặc định 15173); proxy `/api` sang `API_PORT` theo cấu hình Vite đã có. Không đưa secret `.env` vào web.

- `npm.cmd run build`: TypeScript và build tĩnh vào `dist/`.
- `npm.cmd test`: kiểm tra JSON `/chat`, response sai, hủy request, thử lại, mock cục bộ, SSE và HTTP 429 bằng fetch giả.
- `npm.cmd run format:check`: kiểm tra định dạng.

## Chức năng

- Font Mantinia Regular từ thư mục người dùng cung cấp `web/Mantinia Regular/` được dùng cho logo.
  File OTF không có glyph trong khối tiếng Việt U+1EA0–U+1EF9, vì vậy tiêu đề và nội dung
  tiếp tục dùng Segoe UI để giữ dấu chính xác. Font được Vite đóng gói cùng bản build, không tải từ CDN.

- Bố cục tham khảo ảnh chat do người dùng cung cấp: thanh bên có cuộc trò chuyện mới, liên kết About/Admin
  và lịch sử; màn hình trống đặt lời chào, ô nhập và gợi ý ở giữa. Khi có tin nhắn, ô nhập nằm cuối vùng chat.
  Giữ theme tối/vàng Erdtree, viền vuông và ảnh nền chỉ ở Main Content. Không thêm Shop, Library,
  upload hay voice từ ứng dụng tham khảo vì không thuộc nhiệm vụ UI chat Sprint 2 của TV4.

- Giao diện, câu hỏi gợi ý và phản hồi minh họa dùng tiếng Việt; ngày hiển thị theo `vi-VN`.
  Đã bỏ nút VI/EN và bộ bản dịch tiếng Anh. Lựa chọn ngôn ngữ cũ trong localStorage được bỏ qua.
  Không tự dịch nội dung hội thoại hoặc dữ liệu API; tên riêng và thương hiệu giữ nguyên.

- `/`: chat, gợi ý, Enter/Shift+Enter, dừng sinh, thử lại, Markdown không render HTML thô, nguồn và hộp trích dẫn.
- Lịch sử khách: localStorage, tối đa 30 cuộc trò chuyện, xóa từng cuộc; lỗi lưu trữ không làm hỏng trang.
- Chế độ mặc định **Xem thử giao diện**: mock JSON cục bộ, có nhãn minh họa, không gọi LLM hoặc backend.
  Feedback ở đây chỉ hiển thị xác nhận thử, không gửi hoặc lưu vào server.
- **Kết nối API (JSON)**: gửi POST `/api/v1/chat` theo luồng Sprint 2, chờ JSON hoàn chỉnh và kiểm tra schema trước khi render.
  Timeout 30 giây, có nút Dừng, báo lỗi và Thử lại. Không tự gửi lại request hoặc chuyển sang dữ liệu giả.
- **Kết nối API (SSE)**: giữ luồng `/api/v1/chat/stream` cho Sprint 3. Câu trả lời bị ngắt được đánh dấu chưa hoàn tất.
- `/about`: phạm vi, nguồn, CC BY-SA, nhóm, lưu trữ trên trình duyệt và disclaimer.
- `/admin`: form token, danh sách hội thoại, tra cứu trace, feedback xấu, ingestion, eval. Token chỉ nằm trong memory.
  Quyền truy cập phải do backend kiểm tra; frontend không thay thế xác thực.
- Theme tối/vàng Erdtree, responsive từ 360px, trạng thái focus và dialog dùng bàn phím.

## Hợp đồng chờ TV1 xác nhận

### Tự kiểm tra UI Sprint 2 khi chưa có backend

1. Chọn **Xem thử giao diện**, tình huống **Thành công**: gửi câu hỏi, quan sát trạng thái chờ rồi câu trả lời JSON mẫu, Markdown và nguồn.
2. Chọn **Lỗi** rồi gửi: phải thấy thông báo lỗi. Chuyển tình huống sang **Thành công**, bấm **Thử lại**:
   câu hỏi lỗi được gửi lại mà không nhân đôi lượt trong lịch sử frontend.
3. Chọn **Phản hồi chậm**, gửi rồi bấm **Dừng** trước khi hết 6 giây: request mẫu bị hủy, không xuất hiện câu trả lời muộn.
4. Trong lúc chờ, không gửi trùng hoặc chuyển cuộc trò chuyện; vẫn có thể đóng/mở sidebar.
5. Khi TV1 có API, chọn **Kết nối API (JSON)**, gửi rồi kiểm tra Network có POST `/api/v1/chat` và response đúng contract.

Mock cục bộ chỉ chứng minh hành vi frontend, **không hoàn thành checklist “Gọi /chat mock của backend”**.
Các ghi chú cũ và cấu trúc `pages → hooks → api` được giữ; `src/api/chat.ts` gom JSON/SSE về sự kiện cho UI hiện có.

Backend hiện mới có health và dev LLM; schema chat/admin còn là khung. Type trong `src/api/types.ts` là giao kèo
frontend dự kiến theo SRS, **chưa phải OpenAPI đã được backend xác nhận**. Điểm thay đổi khi tích hợp gom ở `src/api/`.

| Request                                | Nội dung dự kiến                                               |
| -------------------------------------- | -------------------------------------------------------------- |
| POST `/api/v1/chat`                    | ChatRequest → ChatResponse JSON                                |
| POST `/api/v1/chat/stream`             | ChatRequest → `text/event-stream`                              |
| POST `/api/v1/feedback`                | `{ message_id, rating: 1 hoặc -1, reason }`                    |
| GET `/api/v1/admin/stats`              | AdminStats: conversations, feedback, ingestion_jobs, eval_runs |
| GET `/api/v1/admin/trace/{message_id}` | JSON trace; header `X-Admin-Token` như stats                   |

SSE: mỗi event kết thúc bằng một dòng trống, `data` là JSON:

```text
event: status
data: {"status":"retrieving"}

event: token
data: {"token":"Nội dung"}

event: sources
data: {"sources":[{"index":1,"title":"Nguồn","url":"https://example.org","text":"Trích đoạn"}]}

event: done
data: {"conversation_id":"uuid","message_id":"uuid","grounded":true}

```

Event `error` báo lỗi và giữ phần trả lời dở dang. HTTP 429 đọc `Retry-After`. API có thể bổ sung dữ liệu nhưng
cần đồng bộ tên trường và kiểu trước khi kiểm thử tích hợp. Nguồn được gửi trước `done`.

## Việc cần phối hợp

TV1 xác nhận contract và header auth, triển khai API; TV3 cung cấp pipeline RAG/trace; TV2 cung cấp dữ liệu.
Sau đó mới có thể xác nhận end-to-end, chất lượng câu trả lời và chính sách lưu server. S6 UAT, Lighthouse ≥85,
review thiết kế của nhóm, slide/video và phát hành cần thực hiện với dữ liệu và người dùng thật; không coi build đạt
là bằng chứng những đầu việc này đã hoàn thành. OAuth vẫn thuộc backlog chờ ADR-005.
