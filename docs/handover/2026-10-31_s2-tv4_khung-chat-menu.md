# TV4 · Khung chat kiểu menu Elden Ring

## Phạm vi

Thay giao diện ô nhập và ba câu gợi ý theo ảnh người dùng cung cấp. Công việc thuộc UI chat TV4 trong Sprint 2. Không sửa backend, bot, API contract, phần TV1–TV3 hoặc README gốc; không commit/push. Những thay đổi sidebar và Makefile có sẵn được giữ nguyên.

## Tài nguyên và quyết định

- Đã xem bảng ảnh ứng viên từ `../item/hi_01_common-tpf-dcx_split/`, chép `MENU_FL_Cursor_Ent.png` và `MENU_FL_Cursor_EntWaku.png` vào `web/item_/`. Kiểm tra trùng nội dung nếu file đích đã tồn tại; giữ ảnh nguồn nguyên bản.
- Mặc định dùng Ent, khung mềm màu vàng xám. Khi ô nhập có focus dùng EntWaku, nền tối và hai dấu ngoặc sáng. Câu gợi ý chuyển trạng thái trên hover/focus/active; chuyển cảnh opacity 240 ms. Reduced motion bỏ transition.
- Dùng border-image nine-slice để giữ hai góc ngoặc khi chiều rộng thay đổi hoặc textarea tự giãn nhiều dòng. Lớp trang trí không nhận pointer; textarea/nút gửi nằm trên lớp ảnh.
- Bỏ markup và CSS chuôi/lưỡi đại kiếm, bỏ hình cờ chữ V. Giữ và cập nhật ghi chú cũ để mô tả thiết kế thay thế. Không đổi nút gửi đen–vàng, nút dừng, tự giãn, giới hạn ký tự hoặc cách xử lý Enter/Shift+Enter/IME.
- Placeholder: `Hỏi INDEX BEAST`. Ba gợi ý: `Elden Ring là gì?`, `Boss cuối là ai?`, `Có bao nhiêu ending?`. Callback gửi câu hỏi hiện có giữ nguyên; gợi ý không chứa sẵn đáp án hoặc bỏ qua xử lý spoiler của backend.

## File

`web/src/components/chat/MessageInput.tsx`, `web/src/pages/ChatPage.tsx`, `web/src/styles/refinement.css`, hai ảnh trong `web/item_/`, và `web/tests/language.test.ts` (đổi ba chuỗi kỳ vọng cũ cho khớp yêu cầu mới).

## Kiểm tra đã chạy

- Build TypeScript/Vite đạt, Prettier cho bốn file đạt.
- 17/17 unit test đạt sau khi cập nhật ba câu gợi ý trong test tiếng Việt. Lần đầu test còn kỳ vọng câu cũ nên thất bại; đã sửa đúng kỳ vọng, không bỏ kiểm tra.
- Chrome/CDP: placeholder đúng, đại kiếm biến mất, focus chuyển ảnh, textarea tăng chiều cao khi nhập bốn dòng, câu gợi ý focus đúng trạng thái, mobile 390 px không tràn ngang, không lỗi JavaScript. Không gửi câu hỏi tới backend/Discord/LLM trong kiểm tra trình duyệt.
- Đã xem ảnh default, focus, multiline và mobile; sửa z-index textarea/nút gửi để lớp ảnh focus không che chữ. Artefact cục bộ trong `web/.taste-skill/menu-fields-*.jpg` và `check-menu-fields.mjs` được Git bỏ qua.

## Cách dùng và giới hạn

### Sửa câu hỏi bị lệch trong hội thoại

Nguyên nhân: `.message.user` giới hạn cả hàng ở 80% (mobile 92%), nên `justify-content: flex-end` chỉ căn theo hàng đã bị thu hẹp; bong bóng hụt vào trong so với cột câu trả lời. Sửa refinement.css: hàng câu hỏi width/max-width 100%, chỉ `.message.user .prose` giới hạn 80% (mobile 92%). Giữ câu hỏi bên phải và câu trả lời bên trái, cùng hai mép của một cột hội thoại; không đổi dữ liệu, Markdown hoặc xử lý gửi.

Prettier và build đạt. CDP dùng hội thoại fixture trong profile trình duyệt QA riêng, không gửi backend: kiểm tra câu ngắn và dài tại 1440/768/390 px, mép phải bong bóng trùng mép phải cột assistant với sai số dưới 1 px, chiều rộng trong giới hạn và không tràn ngang. Đã xem ảnh desktop; ảnh QA trong web/.taste-skill/chat-align-*.jpg, script check-chat-align.mjs (Git bỏ qua). Không chạy lại unit cho CSS này; chưa commit/push. Chỉ sửa CSS của web TV4 và bàn giao.

### Cập nhật nút Enter và ô Tên (yêu cầu tiếp theo)

Người dùng làm rõ trạng thái gõ phải giống dòng **Tên** nền đen, không phải dòng Loại cơ thể có ngoặc trắng. Riêng pseudo-element focus của composer đã bỏ EntWaku, thay bằng nền gần đen, mép bo nhẹ 5 px và viền sáng mờ bằng CSS theo ảnh mẫu. Trạng thái mặc định và ba gợi ý vẫn dùng texture hi_01. Đây là thay thế quyết định focus ở phần trên, không đổi logic nhập/gửi.

Biểu tượng máy bay và nền vàng của nút gửi được thay bằng ảnh phím `web/item_/KG_Key_Enter.png` có sẵn, đã mở ảnh kiểm tra trước khi dùng. Import trực tiếp vào MessageInput; nút vẫn có accessible name “Gửi câu hỏi”, chỉ hiện khi có chữ, giữ vùng bấm 44×44 px. Nút dừng không đổi. Khung focus không dùng ảnh cũ; không tự sửa bitmap.

Build và Prettier hai file đạt. Chạy lại CDP menu-fields: focus, tự giãn nhiều dòng, gợi ý focus, mobile không tràn ngang đều đạt; đã xem ảnh multiline thấy nền đen, chữ trắng rõ, icon Enter. Không gửi API/backend trong QA. 17 unit test đạt ở lượt trước; không chạy lại unit cho thay đổi ảnh/CSS này. Chỉ cập nhật MessageInput.tsx, refinement.css và bàn giao; chưa commit/push.

Chạy `make web` hoặc `npm.cmd run dev` trong web. Ctrl+F5, bấm ô nhập để thấy trạng thái nền tối; bấm ra ngoài để trở về mặc định. Shift+Enter xuống dòng, Enter gửi như trước. Trên điện thoại ba câu gợi ý xếp dọc; desktop tổng chiều rộng bằng ô nhập. Ảnh hi_01 là tài nguyên người dùng cung cấp; không thay đổi thông tin giấy phép. Chưa kiểm tra backend thật hoặc trả lời ba câu hỏi mới.
