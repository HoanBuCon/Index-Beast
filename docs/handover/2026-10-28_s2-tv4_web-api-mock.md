# TV4 — Web Sprint 2: đối chiếu OpenAPI và tích hợp API mock

Ngày: 28/10/2026 (Asia/Saigon). Chủ sở hữu: TV4 (QuyVuiVe).

## Phạm vi

Hoàn thiện phần web của các thẻ **UI chat cơ bản** và **File api.ts viết tay cho web & bot** trong
[Sprint 2](../../planning/sprint_plan.json). Chỉ hoàn thiện nhánh web của thẻ client; phần bot vẫn chưa làm.
Các chỉnh sửa giao diện trước đó trong cùng phiên được giữ nguyên, không ghi đè thay đổi người dùng.

Không sửa backend, bot, ingestion, RAG, hạ tầng, kế hoạch, README gốc hoặc OpenAPI của TV1.
Đọc [bàn giao API của TV1](2026-10-28_s2-tv1_api-contract-v1-va-loi-chuan.md) để dùng đúng API mock đã có.
Review nhóm được bỏ qua theo yêu cầu người dùng; không đánh dấu review đã thực hiện.

## Thay đổi TV4

- [Types](../../web/src/api/types.ts): theo [OpenAPI v1](../api/openapi.json), giới hạn câu hỏi 2.000 ký tự,
  feedback 500 ký tự; Source.section/text nhận null; latency_ms bắt buộc; bổ sung FeedbackRequest/ConversationOut.
- [Client](../../web/src/api/client.ts): nhận response mock thật, kiểm tra UUID/latency/source; thông báo 422/404,
  giữ Retry-After, timeout và AbortSignal; thêm getConversation; kiểm tra feedback trước khi gửi.
- [Luồng chat](../../web/src/api/chat.ts), [hook](../../web/src/hooks/useChatStream.ts),
  [trang chat](../../web/src/pages/ChatPage.tsx): tạo mới dùng JSON API, gửi lang=vi, giữ conversation_id khi hỏi tiếp,
  truyền latency trong sự kiện hoàn tất. Không phục hồi bộ chọn chế độ đã bị người dùng yêu cầu xóa.
- Ô nhập và lý do feedback dùng giới hạn từ hợp đồng; demo cũ vẫn mở được, tạo mới luôn dùng API.
  Giữ các ghi chú đầu tệp và chú thích lịch sử, bổ sung ghi chú cập nhật thay vì xóa chúng.
- [Bộ kiểm thử HTTP](../../web/tests/integration/chat.test.ts) và
  [bộ gá backend](../../web/tests/integration/mock_backend.py) nằm hoàn toàn trong web.
  Bộ gá gọi create_app và MockChatService nguyên bản của TV1, truyền context thử nghiệm để tránh tạo DB/LLM.
  Cổng test do hệ điều hành cấp, chỉ bind loopback; không đổi API_PORT/WEB_PORT và không dừng server người dùng.
- [Hướng dẫn web](../../web/IMPLEMENTATION.md): bỏ hướng dẫn chọn chế độ không còn tồn tại,
  ghi cách chạy API mock, lệnh thử lỗi và giới hạn kiểm chứng.

Không commit/push hay tạo PR trong tác vụ này. Tên nhánh và các thay đổi có sẵn được giữ nguyên.

## Cách chạy

Trong web:

```powershell
npm.cmd test
npm.cmd run test:integration
npm.cmd run build
npm.cmd run format:check
```

Integration cần Python và dependency backend đã cài; script ưu tiên backend/.venv. Có thể đặt WEB_TEST_PYTHON
trỏ tới executable Python khác. Không tự cài lại package backend, không gọi API LLM.

Để dùng trên trình duyệt, khởi động API theo README gốc (`make api`), rồi chạy `npm.cmd run dev` trong web.
Vite proxy /api tới API_PORT đọc từ .env. Tạo cuộc trò chuyện mới để tránh ID mock đã hết sau khi server restart.
Thử `/mock-error`, `/mock-429`, `/mock-slow`, `/mock-ungrounded` theo hướng dẫn của TV1.

## Kiểm tra thực tế

- Web unit/contract/SSR: 17 test đạt.
- HTTP qua Vite → FastAPI mock: 9 test đạt (1 bài tổng, 8 bài con), gồm hỏi tiếp và nguồn, lịch sử,
  feedback 204, JSON→UI events, SSE, không bằng chứng, 404/422/429/502, phản hồi chậm, hủy và timeout.
- TypeScript + Vite production build đạt; kiểm tra định dạng thực hiện trước khi bàn giao.
- Timeout trong ca test là 50 ms để kiểm tra lỗi TimeoutError, không phải đo thời gian mặc định 30 giây của UI.
- Nguồn null và response thiếu latency/UUID sai được kiểm tra bằng unit/contract test.

## Hạn chế và việc còn lại

- Chưa tự động hóa thao tác gõ/bấm trên trình duyệt hoặc chạy Lighthouse/UAT; không suy diễn từ HTTP test.
- Mock backend giữ lịch sử trong RAM, feedback chỉ xác nhận nhận request; không phải lưu DB hay RAG thật.
- Admin /admin/* chưa có trong OpenAPI; khung UI S5 được giữ và chưa coi là hoàn thành tích hợp.
- Bot /ask và client/types phía bot vẫn là phần chưa hoàn thành của TV4 Sprint 2; không sửa trong tác vụ web này.
- API mock /mock-error luôn trả 502; retry cùng câu đó tiếp tục lỗi là đúng. Gửi câu hỏi bình thường để thử phục hồi.
- Các chỉnh sửa giao diện, font, ảnh nền và logo trong cùng nhánh vẫn là công việc TV4; build không thay thế review nhóm.

Không ghi secret hoặc giá trị thật từ .env vào tài liệu, log test hay bundle.

## Bổ sung: lệnh khởi động frontend

Theo yêu cầu tiếp theo của người dùng, bổ sung target `web` vào Makefile gốc và `.PHONY`:
`make web` chạy `cd web && npm run dev`. Giữ nguyên các target của thành viên khác và các ghi chú.
Vite vẫn tự đọc WEB_PORT/API_PORT từ .env; không khai báo cổng hoặc secret mới.
Lần đầu chạy `npm.cmd ci` trong web; sau đó dùng `make web` ở gốc qua Git Bash/WSL.
API chạy ở terminal riêng bằng `make api`. Kiểm tra recipe bằng `make -n web`, không bật thêm server dev của người dùng.

## Bổ sung: giản lược màn hình bắt đầu

Theo yêu cầu tiếp theo, bỏ ảnh logo ELDEN RING và ba nút gợi ý Nhân vật / Sự kiện / Thế giới khỏi ChatPage.
Giữ ảnh nền, lời chào, ô nhập, nguồn và các ghi chú mã nguồn. Không xóa tài nguyên gốc trong docs hoặc ảnh nền.
Kiểm thử SSR được cập nhật để xác nhận hai khối đã bỏ không còn render.

## Bổ sung: ảnh nền patches

Theo yêu cầu người dùng, đổi nền vùng chat sang `web/src/assets/patches.png`, dùng `background-size: 100% 100%`
để kéo giãn phủ hết vùng nội dung mà không cắt ảnh. Giữ lớp tối loang, bóng chữ và nền ô nhập để dễ đọc.
Chỉ thay CSS của web, không sửa ảnh gốc hay thanh bên; ảnh sẽ thay đổi tỉ lệ theo vùng hiển thị.

Theo yêu cầu bố cục tiếp theo, cụm lời chào và ô nhập ở trạng thái chưa có tin nhắn được căn giữa theo hai chiều
trong vùng nội dung chính. Sau khi có tin nhắn, ô nhập vẫn nằm dưới hội thoại như trước.

Theo yêu cầu giản lược tiếp theo, bỏ thanh thông báo kết nối API ở đầu vùng chat. Luồng JSON API mock,
xử lý lỗi và nguồn không thay đổi; hướng dẫn vẫn nêu rõ đây là dữ liệu giả của Sprint 2.
