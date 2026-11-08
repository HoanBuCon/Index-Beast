# TV4 · Sprint 3: SSE web, bot và About

Ngày 08/11/2026 (Asia/Saigon), nhánh `feature/s3-tv4-web-streaming-sse`. Chưa commit/push.

## Căn cứ và phạm vi

Đọc `planning/sprint_plan.json`: ba thẻ TV4 Sprint 3 gồm Web streaming SSE + hiển thị nguồn (5 điểm), Bot câu trả lời thật/chia nhỏ/help/about (3 điểm), About & ghi nguồn (2 điểm).
Đối chiếu `docs/02_SRS.md` FR-WEB-01/02, NFR-UX-01, FR-BOT-02/03/06, FR-WEB-07/NFR-LEG-01, quy ước, docs/AGENTS và handover liên quan.

Chỉ sửa frontend/bot TV4 và tài liệu bàn giao/hướng dẫn của TV4. Không sửa backend, dữ liệu TV2, pipeline/model TV3, planning, SRS, README gốc, Makefile, `.env` hoặc hợp đồng API.
Giữ các thay đổi UI trước lượt này (nút Esc, focus khung chat, bảng bổ sung ẩn khi gửi) và ghi chú cũ. Chưa coi cả Sprint/thẻ đã Done: còn nghiệm thu, review/CI/merge theo Definition of Done.

## Thay đổi

- `web/src/pages/ChatPage.tsx`: mới/reset mặc định `api-stream`; gửi, retry và bổ sung từ hội thoại JSON cũ chuyển sang SSE nhưng giữ conversation ID/token/turn ID/lịch sử. Demo cũ vẫn demo; không fallback sang dữ liệu giả khi API lỗi.
- `web/src/components/chat/MessageList.tsx`, `web/src/styles/refinement.css`: dòng chờ “Đang tìm trong lore…” hiển thị cùng ba chấm ngay sau gửi, mất khi có nội dung; khoảng cách và wrap phù hợp màn nhỏ. Giữ Markdown an toàn, citation/popover, ảnh, dừng và thử lại.
- `bot/src/utils/format.ts`: `answerEmbeds` chia đủ văn bản thành các phần tối đa 3.600 UTF-16 code units; ưu tiên xuống dòng, không cắt đôi surrogate/emoji. Mỗi tin một embed, phần đầu có nguồn, đánh số phần; không vượt 4.096 description và 6.000 tổng ký tự embed/tin. Nguồn vẫn giới hạn theo dung lượng field.
- `bot/src/commands/ask.ts`: editReply phần đầu sau defer; followUp các phần còn lại, mentions tắt. Không thay external_ref channel/user/thread hoặc auth/API backend.
- `bot/src/commands/help.ts`, `about.ts`: triển khai khung lệnh cũ, giữ ghi chú; phản hồi ephemeral, hướng dẫn hỏi/hỏi tiếp/nguồn/giấy phép/disclaimer. Không gọi backend/LLM.
- `bot/src/commands/index.ts`: registry gồm ping, ask, help, about; script global hiện có dùng registry này. Không gọi Discord để xuất bản lệnh trong lượt này.
- `web/src/pages/AboutPage.tsx`: giữ team/disclaimer, cập nhật mô tả SSE/RAG, ghi wiki.gg là nguồn văn bản chính theo khảo sát TV2, phân biệt tài liệu đọc thêm và nguồn thực thể khảo sát; bổ sung điều kiện ghi công/nguồn/biến đổi/chia sẻ tương tự của CC BY-SA. Không gán giấy phép văn bản cho tất cả ảnh/font/API bên ngoài.
- `web/IMPLEMENTATION.md`, `bot/IMPLEMENTATION.md`: cách chạy và giới hạn mới. Giữ phần ghi chú S2 của bot và thêm cập nhật S3, không xóa lịch sử bàn giao.
- Test mới/cập nhật: `web/tests/sprint3.test.ts`, `bot/tests/ask.test.ts`, `bot/tests/info.test.ts`.

Ghi nguồn dựa vào `docs/data-sources.md` (footer wiki.gg mẫu ghi CC BY-SA 4.0). Đã đọc điều kiện tại [Creative Commons](https://creativecommons.org/licenses/by-sa/4.0/); trang copyright wiki.gg không truy cập được trong lượt kiểm tra này, không khẳng định đã xác minh lại toàn bộ corpus/ảnh.

## Kiểm tra đã chạy

- Web: TypeScript + Vite build đạt; format:check đạt; 43/43 test đạt khi chạy `node --test --test-concurrency=1 tests/*.test.ts`.
- Bot: TypeScript đạt, 30/30 test đạt, format:check đạt. Test interaction/fetch giả, không đọc secret, kết nối Discord hoặc gọi model.
- Chrome/CDP trên toàn App React qua fixture fetch/SSE giả, tại 1440/768/360: POST `/api/v1/chat/stream`, nhận từng token trước done; stop abort và giữ phần dở; thử lại giữ turn ID, không nhân đôi câu hỏi; nguồn vẫn bấm được; lần hỏi tiếp giữ conversation capability; lỗi sau token hiện lỗi và trả control về trạng thái dùng được; không tràn ngang.
- Dòng chờ xuất hiện trên DOM sau gửi: lần đầu 49/13,7/31,2 ms ở 1440/768/360; lần kiểm tra tiếp 37/11,5/14,9 ms. Đạt dưới 300 ms trong fixture local; không phải benchmark paint trên thiết bị thật, backend mạng, retrieval hoặc LLM production.
- Đã xem screenshot streaming và About ở mobile; About 1440/360 không tràn ngang. QA/fixture/screenshot ở `web/.taste-skill/s3-preview.html`, `check-s3.mjs`, `s3-streaming-*.jpg`, `s3-about-*.jpg` (Git bỏ qua).
- Lần chạy test web song song mặc định có cảnh báo cổng WebSocket 24678 do nhiều Vite SSR harness; 42 test cũ vẫn đạt. Lượt sau có test mới chạy tuần tự 43/43 đạt, không sửa mã ứng dụng để né cảnh báo. Hai assertion trong QA được chỉnh cho đúng: Markdown bỏ dấu cách cuối và đóng citation dialog trước khi gửi tiếp.
- Diff, UTF-8, liên kết local của handover được kiểm tra. Không chạy LLM, model, notebook, indexing hoặc API thật để kiểm thử.

## Cách mở và thử

Web: từ gốc chạy `make web` với backend đang chạy, hoặc `cd web` và `npm.cmd run dev`. Sau tải lại, DevTools Network phải thấy `/api/v1/chat/stream` và `text/event-stream`.
Backend chọn mock hay RAG theo cấu hình của người chạy. Không tự thay `.env` hoặc gọi model trong lượt này. Để kiểm thử UI offline xem fixture và lệnh `node .taste-skill/check-s3.mjs` trong web.

Bot: `make bot` với backend sẵn sàng. **Hướng dẫn chưa chạy:** `make bot-deploy` để đăng ký đủ bốn lệnh global sau khi duyệt thay đổi; thử `/help`, `/about`, `/ask`, câu hỏi tiếp và câu trả lời dài trên server test. `make bot-dev` ép mock nên không dùng để tuyên bố RAG thật thành công.

## Trạng thái checklist và việc chờ

| Mục | Kết quả |
|---|---|
| Đọc SSE và hiện token dần | Đã bật và kiểm tra trên toàn App bằng luồng giả |
| Trạng thái tìm trong lore ≤300 ms | Đạt fixture local; chưa đo môi trường người dùng/production |
| Nút dừng và lỗi giữa chừng | Đạt test/QA giả lập; chưa gọi LLM thật |
| Danh sách nguồn [n] dưới câu trả lời | Giữ gỡ theo yêu cầu người dùng trước; chỉ còn citation/popover. Chưa tích mục gốc, cần thống nhất thay đổi yêu cầu với nhóm |
| Bot /chat thật theo channel/user | Code có, mock test đạt; chưa nghiệm thu Discord → backend RAG thật |
| Chia nội dung theo embed | Đã trả đủ nhiều phần, kiểm tra emoji/giới hạn/thứ tự |
| Link xem đầy đủ trên web | Chưa làm; cần TV1 thống nhất quyền chia sẻ lịch sử Discord |
| /help và /about | Code và kiểm thử đạt; chưa đăng ký/thử thật trên Discord |
| Đăng ký global | Script sẵn, registry đủ; chưa thực hiện xuất bản |
| About: giới thiệu/nguồn/CC BY-SA/disclaimer | Đã có UI và test; quyền từng tài nguyên vẫn theo metadata nguồn |

Backend hiện chỉ cho trusted-service đọc hội thoại Discord. Không đưa service token lên frontend/URL, không tạo link giả về trang chủ. TV1 cần thiết kế quyền đọc/chia sẻ phù hợp trước khi triển khai link “xem đầy đủ trên web”; TV2 cung cấp metadata bản quyền từng nguồn/ảnh, TV3/TV1 hỗ trợ nghiệm thu câu trả lời thật. Không sửa phần của họ để tự hoàn tất thẻ.

Không commit/push/rebase, không thay con trỏ develop hoặc đánh dấu SRS/board hoàn thành. Các thay đổi UI trước đó trong working tree vẫn giữ nguyên.

## Cập nhật lượt tiếp theo ngày 08/11

Đã đăng ký và đọc lại bốn lệnh global thành công; kiểm tra Gateway và hai lượt handler → backend thật đạt.
Chi tiết và giới hạn xem [đăng ký global và thử backend thật](2026-11-08_s3-tv4_dang-ky-global-va-thu-backend-that.md).
Phần “chưa đăng ký” phía trên là trạng thái trước lượt tiếp theo; nghiệm thu thao tác của người dùng trong Discord vẫn chưa xác nhận.
