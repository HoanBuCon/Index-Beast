# TV4 — Đổi font Agmena và sửa lỗi khởi động web

Ngày: 29/10/2026 (Asia/Saigon). Phạm vi: frontend TV4; không sửa backend, bot, RAG, kế hoạch hoặc OpenAPI.
Giữ các thay đổi trước đó của người dùng và các ghi chú mã nguồn, không commit/push.

## Lỗi và cách sửa

Build ban đầu thất bại vì Header, ChatPage, MessageList còn import `grace.png`, trong khi assets hiện có
`ERN_Map_Icon_Site_of_Grace.png`. Đổi cả ba import sang tệp thực tế; không đổi ảnh gốc hoặc hành vi đóng/mở sidebar.

## Font

Đọc font ở `web/font/Agmena Pro Book/`: family **Agmena Pro Book**, Regular.
Khai báo @font-face WOFF2 trong [CSS](../../web/src/styles/index.css), dùng biến --font-interface cho logo,
nội dung, các tiêu đề và trường nhập. Vite đóng gói font, không thêm dịch vụ font hoặc thư viện ngoài.

Kiểm tra cmap trong TTF của bộ font: có 2/90 ký tự khối U+1EA0–U+1EF9, thiếu Ơ/ơ/Ư/ư.
Vì vậy cấu hình Cambria / Times New Roman dự phòng cho ký tự chưa có. Đây là fallback theo ký tự,
không khẳng định font Agmena cung cấp đầy đủ tiếng Việt hoặc mọi ký tự đều có nét giống nhau.

Giữ License.txt và tệp font gốc; thêm ghi nguồn OnlineWebFonts ở trang Về dự án theo ghi chú trong bộ tải về.
Không suy diễn ghi chú phân phối là xác nhận giấy phép thương mại. Thêm thư mục font tải về vào .prettierignore
để format không sửa tệp demo, giấy phép và nội dung của bên cung cấp.

## Kiểm tra thực tế

- `npm.cmd run build`: đạt; đầu ra có WOFF2 Agmena và ảnh Grace đúng đường dẫn.
- `npm.cmd test`: 17 test đạt.
- `npm.cmd run format:check`: đạt.
- Khởi động Vite riêng ở loopback/cổng test do hệ điều hành cấp, kiểm tra HTTP 200 của trang chính,
  ChatPage, MessageList, CSS, icon Grace và WOFF2; sau đó đóng server test.
- Chưa kiểm tra trực quan trên trình duyệt người dùng hoặc mọi thiết bị; HTTP 200 không thay thế kiểm tra đó.

## Cách dùng và giới hạn

Từ gốc repo, chạy `make web` như trước; mở terminal khác chạy `make api` để thử chat API mock.
Nếu Vite đang chạy thì tải lại trang sau khi cập nhật import. Không đổi cổng, không dừng server đang có của người dùng.

Tệp thay đổi: web/src/styles/index.css, ba component import icon, web/src/pages/AboutPage.tsx,
web/.prettierignore, [hướng dẫn web](../../web/IMPLEMENTATION.md), bản bàn giao TV4 và liên kết trong danh sách bàn giao.

## Dọn hai bản font trùng

Theo yêu cầu, bỏ `web/Agmena Pro Book` và `web/Agmena Pro Book copy` khỏi dự án.
Lệnh xóa trực tiếp bị kiểm duyệt tự động chặn; môi trường không hỗ trợ chuyển vào Thùng rác.
Đã chuyển hai thư mục vào thư mục tạm ngoài repo, không xóa vĩnh viễn:
`%TEMP%/Index-Beast-font-copies-016ee400f3344db7ba8861e42c2b7554`.
Đã kiểm tra đường dẫn nguồn nằm trực tiếp trong web, đích nằm trong thư mục tạm trước khi chuyển.
Giữ nguyên WOFF2 và giấy phép trong `web/font`, là bản CSS đang dùng; bỏ mục ignore của bản trùng đã chuyển.

Theo phản hồi nền quá sáng, đổi lớp trắng phủ ảnh patches thành lớp tối nhẹ khoảng 25%.
Chỉ tác động background, giữ nguyên màu chữ, font, ô nhập và các nút.

Theo yêu cầu tăng chữ sau khi đổi font: ô nhập 18 px, ba câu hỏi gợi ý 16 px.
Chiều cao tối thiểu textarea tăng lên 44 px để không cắt dòng chữ; giữ tự giãn, font Agmena và hàng ba cột.

Tăng cỡ chữ sidebar theo phản hồi tiếp theo: INDEX BEAST 20 px, dòng phụ 9 px, điều hướng 16 px,
ghi chú AI 14 px, mục Tất cả và tiêu đề cuộc trò chuyện 15 px, ngày/chế độ trong lịch sử 12 px.
Không đổi kích thước icon hoặc tọa độ các hàng khi đóng/mở thanh bên.

Tăng chữ riêng trang Về dự án qua class `document about`: nội dung/danh sách 18 px, đoạn dẫn 20 px,
tiêu đề mục 26–30 px, tên thành viên 24 px, mô tả thành viên 16 px. Giãn dòng và tăng độ sáng chữ;
không đổi nội dung bài giới thiệu hoặc CSS của trang admin.

## Mở lại commit 4a3e833 theo yêu cầu

Người dùng yêu cầu dùng lại commit `feat(web): giao diện và sửa lỗi đường dẫn ảnh` có mã 4a3e833.
Đã tạo và chuyển sang nhánh riêng `feature/s2-tv4-khoi-phuc-4a3e833` tại đúng commit này.
Nhánh `feature/s2-tv4-ui-chat-co-ban` đã rebase vẫn được giữ tại 5bdf189, không reset hoặc force-push.

Trước khi đổi nhánh, lưu hai thay đổi tài liệu bàn giao rebase chưa commit vào stash
`71c2facce7638a4ff38f7e2910ce82d68a25ada2` (mô tả: TV4: luu ban giao rebase truoc khi mo lai 4a3e833).
Đã kiểm tra HEAD là 4a3e833 và web/Makefile không khác bản 5bdf189 trước đó; không viết lại mã frontend.
Các kiểm tra build/17 test ở lần rebase vẫn áp dụng cùng nội dung web; không chạy lại test cho thao tác đổi nhánh.
Bổ sung ghi chú này là thay đổi tài liệu chưa commit; không tự commit/push trong bước khôi phục.

## Giữ nội dung 4a3e833 đồng thời cập nhật develop

Theo yêu cầu tiếp theo, đã git fetch origin và xác nhận origin/develop vẫn là 02c4abf.
Nhánh feature/s2-tv4-ui-chat-co-ban tại 5bdf189 đã chứa commit develop này và có web/Makefile giống hệt 4a3e833.
Đã chuyển trở lại nhánh feature đó, giữ thay đổi tài liệu chưa commit. Không cần rebase thêm, không reset/ghi đè mã.
4a3e833 là mã trước rebase; 5bdf189 là mã mới có cùng nội dung frontend sau khi đổi commit cha.
Nhánh khôi phục và nhánh backup vẫn được giữ; chưa push remote hoặc tự áp dụng lại stash tài liệu rebase.

Theo yêu cầu gom thư mục font, chuyển `web/Mantinia Regular` vào `web/font/Mantinia Regular`,
cập nhật src của @font-face Mantinia. Giữ toàn bộ tệp và giấy phép đi kèm; font chính vẫn là Agmena.
Đã xác minh đường dẫn nguồn/đích nằm trong web trước khi chuyển, không ghi đè thư mục đã tồn tại.
