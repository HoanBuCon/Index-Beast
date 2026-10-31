# Ảnh trong câu trả lời · UI TV4 và tích hợp backend TV3

Chat thật đã nhận `images` từ backend cho cả JSON và SSE. Trang preview fixture của TV4 vẫn độc lập,
không gọi API hoặc Discord. Phần tích hợp do TV3 thực hiện theo yêu cầu người dùng ngày 31/10/2026.

## Thử chat thật

Chạy API có `CHAT_MODE=rag` và `RAG_IMAGES_ENABLED=true`, có corpus/index cùng catalog/blob ảnh local.
Chạy `make web` từ gốc, chọn chế độ API hoặc API streaming. Nếu web đang chạy thì Ctrl+F5 để nạp code mới.
Thử cuộc trò chuyện mới với câu: **Bloodhound's Fang có hiệu ứng gây chảy máu không?**
Không cần reindex cho phần frontend này. Những câu trả lời cũ chưa lưu images không tự có thêm ảnh.

Ảnh xuất hiện dưới answer sau khi lượt trả lời hoàn tất và grounded=true. Backend chỉ chọn ảnh liên kết
với chunk thực sự được trích; không bảo đảm mọi câu hỏi về cùng thực thể đều có ảnh.
`images=[]` là kết quả hợp lệ; không dùng ảnh fixture hoặc ảnh nhận diện bằng từ khóa để lấp chỗ trống.

Frontend đọc `ChatResponse.images`, `sources.images` trong SSE và `messages[].images` từ history backend.
State/localStorage giữ metadata, không lưu bytes/base64. Response/history cũ không có trường ảnh vẫn dùng được.
Chỉ nhận URL ảnh `/api/v1/images/<sha256>` cùng origin, source HTTP(S) hợp lệ và source_indices tồn tại;
lọc ảnh sai, dedup và tối đa 3. Media sai không làm mất answer text. Vite đã proxy `/api`, không cần URL máy API
trong metadata ảnh, nên dùng cùng cách trên LAN/VPN.

UI dùng tên nguồn, caption/alt từ backend; không đoán ảnh là nhân vật hay vũ khí từ câu hỏi.
Hiển thị attribution/license nếu có, giữ thông báo quyền sử dụng chưa xác minh khi metadata chưa được duyệt.
Không hiển thị ảnh cho message đang stream, bị hủy/lỗi, user hoặc grounded=false.

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

## Dữ liệu UI và adapter backend

`src/components/chat/answerMedia.ts` định nghĩa `AnswerIllustration` gồm ID, loại, tên, URL ảnh, alt text, nhãn/link/ghi nguồn. Đây là kiểu UI riêng, không phải schema backend.

`MessageList` nhận prop tùy chọn `illustrationsByMessage` cho trang preview. Trong chat thật,
adapter `backendIllustrations` lấy `message.images` và nguồn đã trích; không cần truyền prop preview.
Chỉ assistant có nội dung, đã hoàn tất và không đang chờ mới hiển thị ảnh.
Thuộc tính `demo` đơn lẻ không bật fixture. Trạng thái mô phỏng chỉ trang preview truyền bằng `illustrationPreviewState`.

Ảnh dùng `object-fit: contain`, frame 4:3 đặt trước kích thước, cột ảnh + thông tin trên desktop và xếp dọc dưới 520 px. Nếu lỗi mạng hoặc quá 15 giây, hiển thị nút thử lại thủ công; không tự retry vòng lặp. Đổi URL ảnh tạo lượt tải mới. Không bật ảnh/HTML từ Markdown; chỉ chấp nhận URL HTTP(S) hoặc đường dẫn cùng origin cho ảnh và nguồn, không nhận credentials trong URL.

Fixture gồm tranh Elden Beast có sẵn, biểu tượng vũ khí chung `MENU_Tab_07.png` và biểu tượng chìa khóa `MENU_Tab_03.png`. Không coi chúng là ảnh xác định một vũ khí/vật phẩm có tên trong game. Nguồn được ghi là tài nguyên người dùng cung cấp, chưa xác minh tác giả/giấy phép; fixture không được đóng gói trong bản production.

Contract backend: [images-tv4.md](../docs/api/images-tv4.md). TV3 đã nối DTO/parser/state/history/adapter vào component
TV4 có sẵn. Không sửa cách backend resolve ảnh, không thêm tìm kiếm hoặc sinh ảnh.

## Kiểm tra

```powershell
npm.cmd test
npm.cmd run test:integration
npm.cmd run build
```

`tests/backendImages.test.ts` kiểm tra contract JSON/SSE, patch message dùng trong hook,
history/localStorage và render chat thật không cần fixture props. Các test trước về Markdown an toàn,
nguồn, feedback và trạng thái rỗng/tải/lỗi giữ nguyên.
Kết quả tích hợp TV3: 30 test frontend và 9 integration mock đạt; build/typecheck đạt.
GET thật ba ảnh backend và một ảnh qua proxy web trả 200, hash khớp; không gọi DeepSeek thật.
Xem [bàn giao tích hợp](../docs/handover/2026-10-31_s2-tv3_noi-anh-backend-web.md).
QA fixture TV4 trước đó ghi tại [bàn giao UI](../docs/handover/2026-10-31_s2-tv4_anh-minh-hoa-cau-tra-loi.md).
