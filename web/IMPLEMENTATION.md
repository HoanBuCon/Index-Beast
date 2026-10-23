# Bàn giao web — TV4

Phạm vi: mã nguồn trong `web/`, tương ứng các thẻ web S1–S5. Không triển khai nhiệm vụ backend, RAG, ingestion,
database, bot hay hạ tầng. Các ghi chú đầu tệp được giữ nguyên. README và kế hoạch chung không được chỉnh sửa.

## Chạy và kiểm tra

Tại thư mục `web`, chạy `npm.cmd ci` lần đầu, rồi `npm.cmd run dev`. Cổng đọc từ `WEB_PORT` ở `.env` gốc
(mặc định 15173); proxy `/api` sang `API_PORT` theo cấu hình Vite đã có. Không đưa secret `.env` vào web.

- `npm.cmd run build`: TypeScript và build tĩnh vào `dist/`.
- `npm.cmd test`: kiểm tra SSE, packet UTF-8/CRLF, stream bị ngắt và HTTP 429 bằng fetch giả.
- `npm.cmd run format:check`: kiểm tra định dạng.

## Chức năng

- Nút **VI / EN** trên thanh điều hướng đổi ngôn ngữ giao diện, câu hỏi gợi ý và định dạng ngày.
  Lựa chọn được lưu trong localStorage (`indexbeast.language`); nếu lưu trữ bị chặn vẫn đổi được trong phiên.
  Không tự dịch nội dung hội thoại hoặc dữ liệu API, không gọi dịch vụ dịch thuật. Thêm bản dịch tại
  `src/lib/translations.json`; các ghi chú mã nguồn giữ nguyên tiếng Việt.

- `/`: chat, gợi ý, Enter/Shift+Enter, dừng sinh, thử lại, Markdown không render HTML thô, nguồn và hộp trích dẫn.
- Lịch sử khách: localStorage, tối đa 30 cuộc trò chuyện, xóa từng cuộc; lỗi lưu trữ không làm hỏng trang.
- Chế độ mặc định **Xem thử giao diện**: dữ liệu cố định, có nhãn minh họa, không gọi LLM hoặc backend.
  Feedback ở đây chỉ hiển thị xác nhận thử, không gửi hoặc lưu vào server.
- **Kết nối API**: fetch SSE thật; lỗi không tự chuyển sang dữ liệu giả. Câu trả lời bị ngắt được đánh dấu chưa hoàn tất.
- `/about`: phạm vi, nguồn, CC BY-SA, nhóm, lưu trữ trên trình duyệt và disclaimer.
- `/admin`: form token, danh sách hội thoại, tra cứu trace, feedback xấu, ingestion, eval. Token chỉ nằm trong memory.
  Quyền truy cập phải do backend kiểm tra; frontend không thay thế xác thực.
- Theme tối/vàng Erdtree, responsive từ 360px, trạng thái focus và dialog dùng bàn phím.

## Hợp đồng chờ TV1 xác nhận

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
