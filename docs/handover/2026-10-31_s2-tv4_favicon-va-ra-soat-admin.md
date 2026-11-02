# TV4 · Ghép favicon và rà soát giao diện Quản trị

## Phạm vi

Người dùng yêu cầu ghép favicon hiện tại với khung đã chọn và xem xét cách tổ chức lại Quản trị. Đã triển khai favicon; phần Quản trị mới rà soát/đề xuất, chưa sửa giao diện hoặc gọi API. Không thay đổi phần TV1–TV3, bot hoặc README gốc. Chưa commit/push.

## Favicon đã làm

- Thêm `web/src/assets/favicon-framed.svg`: ghép nguyên ảnh `HoanGiapVang.jpg` vào khung `web/item_/MENU_FL_Arts_wakuDeco.png`. SVG nhúng cả hai ảnh bằng data URI, clip theo góc vát, giữ tỷ lệ ảnh, không vẽ lại/chỉnh bitmap gốc.
- Sửa link favicon trong `web/index.html` sang SVG mới. Không thay logo Grace của sidebar hoặc avatar câu trả lời.
- SVG tự chứa khoảng 209 kB, giữ chất lượng nguồn; hoa văn chỉ rõ ở kích thước lớn, 16 px chủ yếu thấy sắc vàng và dáng khung. Có thể tạo bản raster 32/48 px tối ưu sau nếu cần; lượt này không thêm pipeline xử lý ảnh.
- Prettier index.html và build đạt. Chrome/CDP xác nhận favicon tải HTTP 200, decode 184×184, chứa cả hai ảnh, đã xem ở 16/32/64/184 px. Ảnh QA `web/.taste-skill/favicon-framed-preview.jpg`, script `check-favicon-frame.mjs` (Git bỏ qua). Không chạy lại unit vì chỉ đổi asset/link HTML.
- Xem bằng `make web`, Ctrl+F5; trình duyệt có thể cache favicon lâu, thử đóng/mở tab nếu cần.

## Rà soát Quản trị

Căn cứ `planning/sprint_plan.json` và `docs/02_SRS.md`: Trang admin thuộc TV4, Sprint 5, FR-WEB-08, Should. TV1 hỗ trợ API `/admin/stats` và bảo vệ admin. Checklist gồm token, hội thoại + trace, phản hồi chưa hữu ích, trạng thái thu thập dữ liệu và kết quả đánh giá.

Hiện trạng `web/src/pages/AdminPage.tsx`: toàn bộ các khối hiện nối dài ngay cả trước khi kết nối; hai danh sách hội thoại/phản hồi không có thông báo rỗng sau khi tải thành công; trace hiện JSON thô; tên Ingestion/Message ID/trace còn trộn ngôn ngữ. Token chỉ giữ trong state, có abort khi đổi token/rời trang; nên giữ hành vi này.

`web/src/api/client.ts` có hàm gọi `/admin/stats` và `/admin/trace/{id}` cùng hợp đồng frontend. `docs/api/openapi.json` hiện không có path chứa admin. Đây là khoảng trống hợp đồng cần phối hợp TV1 trước khi xác nhận tích hợp thật; không tự tạo hoặc sửa endpoint backend trong công việc UI.

### Bố cục đề xuất để triển khai sau

1. Chưa kết nối: tiêu đề **Quản trị**, mô tả một câu, form token với nút **Kết nối**. Hiển thị lỗi ngay form; ẩn các bảng trống chưa tải. Bỏ thông báo dành cho lập trình viên về TV1 khỏi giao diện người dùng.
2. Đã kết nối: thanh trạng thái **Đã kết nối**, nút **Làm mới** và **Ngắt kết nối**. Không lưu token xuống storage, không ghi log token.
3. Ba khu vực: **Hội thoại**, **Phản hồi**, **Dữ liệu & đánh giá**. Giữ đủ checklist, không biến Quản trị thành cài đặt cá nhân.
4. Hội thoại: bảng tiêu đề/thời gian/mã, trạng thái không có dữ liệu rõ ràng. Đưa **Chi tiết xử lý** (trace) vào phần chi tiết hoặc disclosure; giữ JSON trong mục kỹ thuật để không chiếm trang chính. Việc bấm một hội thoại để tải các tin nhắn/trace phải chờ hợp đồng endpoint, không đoán dữ liệu.
5. Phản hồi: danh sách lý do chưa hữu ích và mã tin nhắn, trạng thái rỗng, tải/lỗi/thử lại riêng. Chưa thêm phân trang, tìm kiếm server hoặc bộ lọc gọi endpoint mới khi chưa thống nhất API.
6. Dữ liệu & đánh giá: hai khối trạng thái thu thập dữ liệu và bảng chỉ số đánh giá, nhãn tiếng Việt; hiển thị dữ liệu thật được API trả về, không tạo số liệu giả.

Có thể tự làm phía TV4: bố cục, nhãn, tab/disclosure, trạng thái rỗng/tải/lỗi, responsive và kiểm thử fixture. Cần TV1 trước tích hợp: schema stats/trace, xác thực và 401/403, phân trang/lọc nếu có. Lượt này chưa triển khai các đề xuất admin hoặc coi checklist Sprint 5 hoàn thành.
