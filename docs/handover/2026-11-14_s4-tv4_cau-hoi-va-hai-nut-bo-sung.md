# TV4 — Câu hỏi và hai nút trong bảng bổ sung

Ngày: 14/11/2026 (Asia/Saigon). Nhánh hiện tại: `feature/tv4-dang-nhap-google-discord`.
Phạm vi: frontend TV4, theo yêu cầu mới về bảng hỏi lại; không đổi backend, bot hay hợp đồng API.
Không commit/push hoặc chuyển nhánh tự động.

## Thay đổi

- `web/src/components/chat/ClarificationForm.tsx`: nhãn textarea lấy `question.question`
  thay chữ cố định “Trả lời bổ sung”; câu hỏi mới từ API được hiển thị mỗi khi bảng xuất hiện.
  Hai nút OK và Hủy yêu cầu dùng chung footer.
- `web/src/components/chat/MessageList.tsx`: khi bảng đang nhận câu trả lời, ẩn phần prose
  nếu trùng chính xác câu hỏi trong bảng. Không xóa nội dung lịch sử; nội dung khác vẫn hiện,
  câu hỏi cũ vẫn hiện khi bảng không còn hoạt động. Không thay Markdown an toàn hoặc nguồn.
- `web/src/styles/clarification.css`: footer hai cột trên desktop/mobile, dùng texture khung
  `MENU_FL_Cursor_EntWaku.png` có sẵn; hover/focus dùng `MENU_FL_Cursor_Ent.png`.
  Câu hỏi dài tự xuống dòng; chiều ngang bảng và phần hướng dẫn bên ngoài giữ nguyên.
- `web/tests/clarification.test.ts`: kiểm tra nhãn câu hỏi động, một footer và ẩn văn bản lặp.

Giữ Enter gửi, Shift+Enter xuống dòng, đóng bảng ngay khi gửi/hủy, chặn gửi lặp,
khôi phục bản nháp khi gửi lỗi và trạng thái hết hạn. Không gán câu hỏi ví dụ cố định.
Hủy vẫn gửi cùng nội dung hủy/clarification ID như trước, không đổi xử lý backend.

## Kiểm tra

- Prettier bốn file thay đổi: đạt; build TypeScript/Vite: đạt.
- `node --test tests/clarification.test.ts`: 4/4 đạt.
- Browser fixture cục bộ ở 1440/768/360 px: câu hỏi dài hiển thị trong label liên kết textarea,
  hai nút cùng hàng không chồng nhau, không tràn ngang. Đã xem screenshot mobile.
- Kiểm tra OK/Enter/hủy: bảng đóng ngay, chặn gửi hai lần; thất bại giữ bản nháp,
  thành công giữ bảng đóng. Dùng callback giả, không gọi API/OAuth/LLM thật.
- Bộ gá cũ dùng ngày hết hạn 2099 gây tràn setTimeout; đã sửa riêng fixture bị Git bỏ qua
  sang thời hạn 10 phút để đo đúng trạng thái nhập, không sửa logic thời hạn backend.

Chưa xác nhận bằng một câu hỏi thật tới model. Dữ liệu câu hỏi và việc quyết định hỏi lại
vẫn thuộc luồng backend hiện có; lần này chỉ đổi cách trình bày phía web.
## Bỏ hướng dẫn dưới bảng

Theo yêu cầu tiếp theo, bỏ dòng hướng dẫn Enter/Shift+Enter bên ngoài bảng trong
ClarificationForm. Giữ nguyên xử lý phím gửi và xuống dòng, hai nút và câu hỏi động.
Kiểm tra Prettier component và 4 test clarification đạt.

## Khung nút kín bốn cạnh theo ảnh xác nhận

Chép nguyên bản `MENU_FL_SelectWaku.png` từ bộ `hi_01_common-tpf-dcx_split` bên ngoài
repository vào `web/item_`, xác minh byte trùng nguồn; không chép thêm hình vật phẩm hi_00.
`clarification.css` dùng border-image chia 9 vùng thay ảnh hai dấu ngoặc, tạo khung kín
cạnh mảnh/góc vuông cho cả OK và Hủy yêu cầu, hover/focus sáng nền nhẹ.
Không đổi nội dung gửi, điều kiện disabled hoặc luồng hỏi lại.
Prettier CSS, build và browser fixture 1440/768/360 px đạt: hai nút cùng hàng,
không tràn, gửi/hủy đóng ngay và lỗi khôi phục nháp. Đã xem khung kín trên ảnh mobile.

## Hover quầng sáng mềm như nút xác nhận trong game

Theo ảnh mẫu mới, bỏ nền hover tô phẳng; giữ nền nút tối và khung kín SelectWaku.
Thêm pseudo-element dùng Cursor_Ent có sẵn với blur nhẹ và quầng trắng ngà,
fade 0.3 giây khi hover/focus; không thêm viền outline cứng bên ngoài.
Giữ focus bàn phím bằng cùng quầng sáng, disabled không phát sáng và reduced-motion
không chuyển cảnh. Chỉ sửa CSS bảng bổ sung, không sửa sidebar hoặc xử lý gửi.

Prettier CSS và build đạt. Browser fixture 1440/768/360 px xác nhận hai nút cùng hàng,
không tràn, OK/Enter/hủy vẫn đóng ngay và lỗi giữ bản nháp. Đã xem ảnh mobile có focus.

## Sửa hover sáng đều bốn cạnh

Ảnh phản hồi cho thấy Cursor_Ent làm sáng tụ ở hai đầu, khác mẫu xác nhận.
`clarification.css` bỏ texture Cursor_Ent khỏi lớp hover, dùng đường sáng trắng ngà
và shadow trong/ngoài đồng đều, blur 0.8 px; lớp nền chỉ sáng rất nhẹ, không có đốm
ở hai đầu. Khung SelectWaku mặc định giữ nguyên, focus bàn phím dùng cùng hiệu ứng.
Không đổi kích thước nút hoặc thao tác gửi/hủy.
Prettier đạt; browser fixture 1440/768/360 px đạt bố cục và gửi/hủy/khôi phục nháp.
Đã xem screenshot focus mobile: viền và quầng sáng trải đều quanh nút.

## Giữ một viền duy nhất khi hover

Theo yêu cầu mới, bỏ đường viền CSS và shadow tạo cạnh thứ hai trong pseudo-element.
Khung SelectWaku chính giữ nguyên; lớp hover chỉ là bản texture làm mờ 3 px, trùng
kích thước khung và không có border riêng. Chuyển cảnh 0.3 giây, focus dùng chung.
Chỉ thay CSS nút; không đổi gửi/hủy hoặc kích thước bố cục.
Prettier và browser fixture 1440/768/360 px đạt; đã xem ảnh focus mobile,
khung chính rõ với lớp quầng mờ, không có đường border CSS thứ hai.

## Sửa vệt dọc bên trong hover

Ảnh phản hồi cho thấy kéo giãn texture SelectWaku tạo hai vệt dọc trong nút dài.
Thay riêng viền nút bằng border CSS 1 px, bỏ border-image và pseudo-element ảnh.
Hover/focus chỉ đổi màu viền và shadow mờ bên trong/bên ngoài cùng khung đó;
không có đường viền hoặc ảnh thứ hai. Giữ nguyên hàng nút, nhãn, điều kiện disabled
và xử lý gửi/hủy. Texture đã chép trước được giữ lại, không xóa tài nguyên người dùng.
Prettier và kiểm tra browser 1440/768/360 px đạt; đã xem screenshot focus mobile:
không còn hai vệt dọc, viền và quầng sáng sát cùng một khung.

## Nhịp sáng chậm khi hover

Theo yêu cầu, thêm animation `clarification-soft-pulse` chu kỳ 3.2 giây ease-in-out
cho hover/focus của nút được bật. Chỉ đổi sắc viền và độ lan quầng sáng, không tắt
chữ, không thêm viền thứ hai. Disabled không chạy; reduced-motion tắt animation.
Prettier CSS đạt; không thay hành vi gửi/hủy.

