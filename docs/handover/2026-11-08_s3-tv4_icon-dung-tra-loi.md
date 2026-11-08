# TV4 · Đổi biểu tượng dừng trả lời

- Phạm vi: frontend TV4, nút dừng trong composer. Không sửa code thành viên khác.
- Đã xem ảnh ứng viên trong `../item/hi_01_common-tpf-dcx_split/`: phím Esc, Back, BackSpace, Options và biểu tượng thoát. Chọn `MENU_Tab_Exit.png` (cánh cửa/mũi tên), chép nguyên bản vào `web/item_/`. SHA-256 nguồn/đích giống nhau: `5f856e848c9da8b0c4465222832579d4029fa8325bc2067c166ba9be91322533`. Không sửa bitmap, giữ tài nguyên nguồn và giấy phép hiện có.
- `web/src/components/chat/MessageInput.tsx`: thay hình vuông đen bằng ảnh; thêm title/aria-label “Dừng trả lời”. Giữ nguyên callback onStop, không rời trang hoặc thêm phím tắt.
- `web/src/styles/refinement.css`: nút dừng nền trong suốt, hover vàng nhẹ; ảnh object-fit contain 28×32 trong vùng bấm 44×44, không kéo méo. Giữ nút Enter và các ghi chú, cập nhật ghi chú liên quan cho đúng.
- Đã chạy: build TypeScript/Vite, Prettier toàn web và 2/2 test searchToggle/composer đều đạt. Đã xem bảng ảnh ứng viên; chưa kiểm tra nút trực tiếp trên trình duyệt hoặc gọi API thật. Diff/UTF-8/link bàn giao đã kiểm tra.
- Cách xem: tải lại web, gửi câu hỏi để nút dừng hiện ra; rê chuột thấy nhãn và bấm để hủy yêu cầu như trước. Việc nhận dữ liệu qua JSON/SSE không thay đổi.
- Không thay backend, bot, planning, sidebar, background hoặc favicon; không gọi model/LLM, commit hay push.

## Điều chỉnh sau phản hồi: dùng phím Esc thay cánh cửa

- Người dùng nhận xét biểu tượng cửa chưa đẹp. Áp dụng hướng app của skill `design-taste-frontend`, giữ theme hiện có; phím Esc mang nghĩa hủy rõ hơn và đồng bộ ảnh Enter. Không thiết kế lại trang.
- Chép nguyên bản `KG_Key_Esc.png` từ hi_01 sang `web/item_/`; SHA-256 nguồn/đích cùng `40492504277e6094a9e438b91f8af7d9542f0eb75a289ce21b743e83af427800`. Giữ ảnh cửa đã thêm, hiện không còn import; không xóa tài nguyên người dùng.
- Ảnh Esc 40×28 px với object-fit contain trong vùng bấm 44×44. Title nói rõ Esc hoạt động khi đang chọn ô chat; aria-label “Dừng trả lời”, aria-keyshortcuts Escape. Handler trên composer chỉ gọi onStop khi busy, không nhận phím lặp hoặc khi IME đang composition; không thêm shortcut toàn trang.
- Chrome/CDP trên fixture dùng component thật, không API: viewport 1440 và 360 không tràn ngang, ảnh tải được, vùng bấm đủ 44 px; nhấn Esc khi busy gọi dừng và đổi về nút gửi, Esc khi idle không gọi dừng; click cũng dừng. Đã xem screenshot mobile tại `.taste-skill/stop-esc-360.jpg`. Fixture/QA/screenshot ở thư mục Git bỏ qua `web/.taste-skill/`.
- Build, format:check và 2/2 test composer/searchToggle đạt sau thay đổi. Đây là kiểm tra UI/callback, chưa kiểm tra hủy một request backend thật. Nhánh hiện tại `feature/s3-tv4-web-streaming-sse`; không commit/push hoặc sửa develop.
