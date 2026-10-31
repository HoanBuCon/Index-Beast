# Thử ảnh minh họa trong câu trả lời · TV4

Đây là frontend với fixture, chưa phải tính năng trả ảnh từ backend. Không cần chạy API hoặc Discord.

## Cách mở

Tại gốc dự án chạy `make web`, hoặc trong thư mục `web` chạy:

```powershell
npm.cmd run dev
```

Mở `http://127.0.0.1:15173/preview/answer-images` (dùng cổng `WEB_PORT` nếu đã đổi). Trang này chỉ có trong dev server; production hiển thị trang không tìm thấy. Không thêm liên kết vào sidebar hoặc thay đổi màn chat bình thường.

Chọn Nhân vật / Vũ khí / Vật phẩm / Cả ba loại. Thử các tình huống:

- **Thành công:** ảnh thật từ asset cục bộ, có tên, loại, alt text, liên kết nguồn và ghi chú nguồn.
- **Ảnh đang tải:** mô phỏng loading cố định để xem bố cục; chuyển về Thành công để tải ảnh.
- **Ảnh lỗi lần đầu:** bấm Thử lại (hoặc Tab tới nút rồi Enter) để tải ảnh cục bộ thật.
- **Không có ảnh:** không hiển thị section hoặc frame trống.
- **Câu trả lời chưa hoàn tất / Đã dừng:** không hiển thị ảnh của lượt đó.

Fixture chọn thủ công theo ID cố định; không nhận diện từ câu hỏi, không tự bật khi API lỗi và không ghi ảnh vào lịch sử. Chế độ thử không gửi request `/api`.

## Dữ liệu UI và điểm tích hợp sau

`src/components/chat/answerMedia.ts` định nghĩa `AnswerIllustration` gồm ID, loại, tên, URL ảnh, alt text, nhãn/link/ghi nguồn. Đây là kiểu UI riêng, không phải schema backend.

`MessageList` nhận prop tùy chọn `illustrationsByMessage`, ánh xạ ID tin nhắn sang danh sách ảnh. Chỉ câu trả lời assistant có nội dung, đã hoàn tất và không đang chờ mới hiển thị ảnh. Không truyền prop thì không xuất hiện ảnh; thuộc tính `demo` đơn lẻ cũng không bật fixture. Trạng thái mô phỏng chỉ trang preview truyền bằng `illustrationPreviewState`.

Ảnh dùng `object-fit: contain`, frame 4:3 đặt trước kích thước, cột ảnh + thông tin trên desktop và xếp dọc dưới 520 px. Nếu lỗi mạng hoặc quá 15 giây, hiển thị nút thử lại thủ công; không tự retry vòng lặp. Đổi URL ảnh tạo lượt tải mới. Không bật ảnh/HTML từ Markdown; chỉ chấp nhận URL HTTP(S) hoặc đường dẫn cùng origin cho ảnh và nguồn, không nhận credentials trong URL.

Fixture gồm tranh Elden Beast có sẵn, biểu tượng vũ khí chung `MENU_Tab_07.png` và biểu tượng chìa khóa `MENU_Tab_03.png`. Không coi chúng là ảnh xác định một vũ khí/vật phẩm có tên trong game. Nguồn được ghi là tài nguyên người dùng cung cấp, chưa xác minh tác giả/giấy phép; fixture không được đóng gói trong bản production.

Sau này cần phối hợp TV1/TV2/TV3 để xác định đúng thực thể, thống nhất metadata/URL/nguồn/giấy phép, spoiler và hợp đồng trả dữ liệu. Adapter frontend sẽ ánh xạ hợp đồng đã thống nhất sang `AnswerIllustration`; chưa làm bước đó ở nhánh này.

## Kiểm tra

```powershell
npm.cmd test
npm.cmd run format:check
npm.cmd run build
```

Các test có sẵn kiểm tra luồng API/streaming giả lập; test mới `tests/answerMedia.test.ts` kiểm tra điều kiện hiển thị, URL, dữ liệu ảnh được truyền rõ ràng, Markdown an toàn, nguồn, feedback và trạng thái rỗng/tải/lỗi. QA mạng ảnh chậm/lỗi, retry, bàn phím, mobile và loại bỏ fixture khỏi production được ghi trong [bàn giao](../docs/handover/2026-10-31_s2-tv4_anh-minh-hoa-cau-tra-loi.md).
