# TV4 · Tinh chỉnh giao diện chat bằng Taste Skill

Ngày: 29/10/2026 (Asia/Saigon). Nhánh: `feature/s2-tv4-ui-chat-co-ban`. Chưa commit, push hoặc tạo PR cho đợt chỉnh này.

Cập nhật Git: người dùng đã yêu cầu stage toàn bộ, commit và push lên chính nhánh feature này. Đã fetch origin, xác nhận HEAD chứa develop hiện tại và chỉ có thay đổi web/tài liệu TV4. Remote feature còn lịch sử trước rebase; hợp nhất lịch sử remote để dùng push thường, không ghi đè lịch sử bằng force-push. Trạng thái chưa commit ở dòng đầu mô tả lúc bắt đầu bàn giao; commit/push sau đó theo yêu cầu mới, kết quả được thông báo cho người dùng.

## Phạm vi

Chỉnh UI chat cơ bản thuộc TV4, Sprint 2 trong `planning/sprint_plan.json`: ô nhập, danh sách tin nhắn và trạng thái chờ/lỗi. Đọc các quy ước trong `docs/`; không sửa backend, bot, dữ liệu, RAG, hợp đồng OpenAPI hoặc kế hoạch sprint. Giữ ghi chú cũ và root README.

Các yếu tố riêng của dự án được giữ: tên Index Beast, nội dung lore Elden Ring bản gốc, tiếng Việt, ảnh patches, font Agmena, icon Grace, góc vuông, ba câu hỏi gợi ý, lịch sử hội thoại, nguồn trích dẫn và phản hồi hữu ích. Câu hỏi chính của màn hình: “Tôi muốn hỏi điều gì về cốt truyện Elden Ring và kiểm chứng ở đâu?”

## Quyết định giao diện

- Dùng skill `design-taste-frontend` tại `C:/Users/Riley/.codex/skills/design-taste-frontend/SKILL.md`, hướng app screen **True-black flat**, seed `382339176`; giữ bảng màu và font đang có. Nền tối, phân cấp bằng độ sáng của bề mặt, vàng dành cho thương hiệu và hành động gửi.
- Có hai lượt rút lại shell do kết quả ban đầu bỏ sidebar, lượt kế tiếp thêm top bar. Cuối cùng giữ sidebar thu gọn và không có top bar theo yêu cầu trước đó của người dùng; không áp dụng shell được rút khi trái yêu cầu này.
- Giữ ảnh patches kéo đầy vùng main theo yêu cầu, chỉnh độ tối để chữ sáng và ô nhập nền đặc dễ đọc. Đây là ngoại lệ có chủ ý so với hướng app phẳng hoàn toàn. Không thêm khung tối lớn quanh lời chào.
- Cột chat tối đa 760 px. Ba gợi ý có cùng hai mép với ô nhập, khoảng cách 12 px; trên điện thoại xếp dọc. Font nhập 18 px, gợi ý 16 px, điều hướng 17 px, ghi chú 14 px.
- Giữ kích thước/vị trí icon Grace 30 × 30 px khi mở/đóng. Điện thoại mặc định dùng rail 62 px, mở menu phủ lên nội dung; chạm nền ngoài hoặc Escape để đóng. Focus bàn phím nằm trong menu đang mở, nội dung phía sau dùng `inert`.
- Giữ gửi/hủy, lỗi/thử lại, nguồn và bong bóng chờ ba chấm hiện có. Bổ sung mô tả giới hạn 2.000 ký tự và Enter/Shift+Enter cho trình đọc màn hình.

## File thay đổi

- `web/src/styles/refinement.css`: lớp tinh chỉnh nạp sau CSS cũ, giữ nguyên ghi chú và các quy tắc gốc trong `index.css`.
- `web/src/main.tsx`: nạp lớp CSS trên.
- `web/src/pages/ChatPage.tsx`: menu responsive, đóng bằng Escape/chạm nền, quản lý focus và nội dung phía sau menu.
- `web/src/components/chat/MessageInput.tsx`: mô tả trợ năng cho ô nhập.
- `web/.gitignore`, `web/.prettierignore`: bỏ qua ảnh và báo cáo QA cục bộ `.taste-skill/`.
- `web/IMPLEMENTATION.md` và handover này: hướng dẫn, kết quả thực tế.

## Kiểm tra đã chạy

- `npm.cmd run build`: TypeScript và Vite đạt.
- `npm.cmd test`: 17/17 đạt.
- `npm.cmd run format:check`: đạt.
- Taste browser inspector ở 1440, 768 và 390 px: **0 FAIL, 1 WARN**. Đã mở và xem ảnh ở cả ba kích thước, cùng ảnh hội thoại và menu điện thoại.
- Cảnh báo `panel-void`: công cụ coi main toàn màn hình là card có khoảng trống. Khoảng trống này dành cho căn giữa trạng thái chưa có tin nhắn; không phải card bị kéo theo hàng bên cạnh nên giữ nguyên.
- Source lint: 0 FAIL; 19 WARN do bắt chuỗi `box-shadow:`/`text-shadow:` kể cả giá trị `none`. Các dòng này gỡ bóng cũ, không tạo bóng mới.
- Kiểm tra thao tác trong Chrome qua CDP: gợi ý và composer bằng chiều rộng; icon giữ tọa độ/kích thước khi đóng/mở; nhập nhiều dòng tự tăng chiều cao; chờ hiện bong bóng; nhận câu trả lời; menu mobile phủ nội dung, Escape trả focus, không tràn ngang và không có ngoại lệ JavaScript.
- Kiểm tra hội thoại dùng `fetch` giả lập chỉ trong phiên trình duyệt QA; không sửa API sản phẩm, không gọi LLM. Không chạy lại tích hợp backend cho thay đổi CSS/menu này; kết quả trên không xác nhận backend/RAG thật.

## Tự kiểm tra hình ảnh và giới hạn

Đã đối chiếu bảy câu hỏi app screen của skill: hành động hỏi ở trung tâm; ô nhập và gợi ý chung mép; vàng có vai trò; không bịa số liệu/badge; không có biểu đồ/legend để đối chiếu; mobile thu menu, các khối vẫn đọc và thao tác được. Ba điểm đã sửa qua các lượt là chữ khó đọc, khoảng cách/lề chưa nhất quán và sidebar mobile chiếm cả chiều ngang.

Ảnh nguồn patches có chữ trong ảnh và bị kéo theo tỷ lệ màn hình theo yêu cầu cũ; không thể coi đây là typography/logo dạng chữ trên trang. Font Agmena thiếu một phần ký tự tiếng Việt nên vẫn cần fallback sẵn có. Admin vẫn là khung ở sprint sau, không được coi là tính năng backend hoàn tất.

Artefact QA nằm trong `web/.taste-skill/` (bị Git bỏ qua): `design/direction.json`, `final-chat/` và `after-chat/` (ảnh hội thoại/menu), `verify.mjs`. Không có dữ liệu giả mới cần thay trong mã sản phẩm.

## Cách xem

### Bổ sung: ba lá cờ chiến trận cho câu hỏi gợi ý

Theo lựa chọn của người dùng, đổi ba nút gợi ý thành cờ nền tối, viền vàng xỉn, mép trên dày hơn và đuôi khuyết chữ V. Chỉ chỉnh `web/src/styles/refinement.css`: pseudo-element tạo hình, không cắt bản thân button để giữ khung focus bàn phím. Hover làm viền/nền sáng nhẹ, không dịch chuyển; tôn trọng reduced motion.

Giữ nguyên ba câu hỏi, callback chọn câu hỏi và tổng chiều rộng bằng khung đại kiếm. Desktop/tablet ba cột, mobile xếp dọc; phần chữ có padding riêng tránh mép đuôi cờ. Không sửa nút gửi hoặc phần thành viên khác. Tiếp tục True-black flat seed `382339176`; hình cờ là ngoại lệ trang trí theo yêu cầu trực tiếp.

Đã chạy build và Prettier: đạt; xem ảnh inspector 1440/768/390 px, không thấy chữ bị cắt hoặc tràn ngang. Inspector 0 FAIL, 2 WARN cũ về Cambria hệ thống/lời chào 36 px, lý do giữ đã ghi ở phần trước. Không chạy lại test logic/API vì lần này chỉ đổi CSS. Ảnh QA cục bộ trong `web/.taste-skill/banners-ui/`. Chưa commit/push.

### Bổ sung: khung nhập đại kiếm, giữ nguyên nút gửi

Theo yêu cầu mới, thêm lớp trang trí đại kiếm trong `MessageInput.tsx`: SVG chuôi, thân và mũi vát bằng CSS trong `refinement.css`. Chuôi giữ kích thước cố định, thân đi theo chiều cao ô nhập; mobile thu kích thước chuôi/mũi để dành chỗ gõ. Lớp trang trí `aria-hidden`, không nhận pointer; control vẫn là textarea/button HTML. Không tải ảnh hoặc thêm thư viện.

Giữ đúng nút máy bay giấy đen trên nền vàng, hover sáng hơn và ẩn khi input trống; giữ nút dừng, Enter/Shift+Enter và tự giãn tối đa hiện có. Tạo hình vũ khí là ngoại lệ trang trí được người dùng yêu cầu rõ, không rút lại hướng True-black flat/seed `382339176` hoặc thay đổi API.

Đã chạy build, 17/17 test và Prettier: đạt. Inspector 1440/768/390 px: 0 FAIL, 2 WARN (Cambria hệ thống và lời chào 36 px, lý do giữ như mục UI trước). Đã xem ảnh cả ba kích thước, ảnh hội thoại; các mép tổng thể của composer vẫn trùng ba gợi ý, không có khung phụ quanh lời chào, chuôi không che chữ. CDP QA tương tác (fetch giả lập riêng trong trình duyệt) đạt: nhập nhiều dòng, gửi/nhận, bubble chờ, sidebar và không tràn ngang. Kiểm tra thêm trạng thái nút trống/đã nhập và màu đen–vàng, textarea không chạm nút ở 1440/390 px. Không gọi LLM hay sửa phần thành viên khác. Artefact cục bộ trong `web/.taste-skill/sword-ui/`, `sword-ui-state/`, `verify-sword.mjs`.

### Bổ sung: biểu tượng gửi theo mẫu Messenger

Cập nhật theo yêu cầu tiếp theo: giữ hình máy bay giấy nhưng dùng icon đen trên nền vàng, hover vàng sáng hơn. Khi ô nhập trống hoặc chỉ có khoảng trắng, nút disabled dùng `visibility: hidden` để ẩn cả biểu tượng/nền, vẫn giữ chỗ trong lưới tránh dịch ô nhập. Nút ẩn không nhận focus bàn phím; nút dừng khi đang trả lời không bị ảnh hưởng. Thay thế màu xanh/xám mô tả ở lần chỉnh trước bên dưới. Build và Prettier cho CSS sau cập nhật đạt.

Thay ký tự mũi tên lên trong `MessageInput.tsx` bằng SVG máy bay giấy hướng sang phải, kích thước 24 px. Nút gửi dùng màu xanh, nền trong suốt, hover sáng nhẹ; khi ô nhập trống icon chuyển xám. CSS giới hạn trong `.send-button`, không đổi nút dừng hoặc logic gửi/Enter. Giữ nhãn trợ năng “Gửi câu hỏi”. Đã chạy Prettier cho hai file sửa và build TypeScript/Vite: đạt. Chỉ sửa UI TV4, chưa commit/push.

### Bổ sung: UI chat hiện đại kết hợp Điểm Ân Điển

Theo yêu cầu triển khai ý tưởng UI, chỉ sửa `web/src/styles/refinement.css` và tài liệu TV4. Tiếp tục hướng True-black flat, seed `382339176`, không rút lại hướng thiết kế. Giữ font Cambria cho tiếng Việt, Agmena cho logo, Grace, góc vuông và ảnh patches hiện có.

- Tách ảnh thành pseudo-element không nhận pointer, giảm bão hòa, opacity 0,38 khi màn hình trống và 0,16 khi có hội thoại. Ảnh tiếp tục kéo đầy main; không thêm panel quanh lời chào.
- Lời chào 36 px trên desktop, 26 px trên điện thoại; dòng phụ/ghi chú dịu hơn. Sidebar dùng mục cao 44 px, chữ 16 px và khoảng cách 6 px; icon Grace không đổi vị trí/kích thước.
- Ô nhập nền đặc, viền tĩnh nhẹ; gợi ý ba cột cùng mép, chiều cao 56 px desktop. Hover đổi sắc nền, không thêm khung hoặc dịch chuyển vị trí. Nút gửi vàng khi có nội dung, trạng thái vô hiệu hóa vẫn khác biệt.
- Câu hỏi bên phải, giữ xuống dòng; câu trả lời bên trái không có hộp bao. Nội dung dài được ngắt để tránh tràn ngang. Không thêm tính năng hay sửa luồng API.
- Chuyển màu hover 160 ms, độ nổi ảnh 220 ms; tắt các chuyển động mới khi người dùng bật reduced motion.

Kiểm tra thực tế: build đạt, 17/17 test đạt, Prettier đạt. Inspector 1440/768/390 px: 0 FAIL, 2 WARN. `font-fallback` là cảnh báo do Cambria là font hệ thống, không có webfont khai báo; đã xác minh Cambria thực tế bằng CDP ở bước sửa font. `app-title-size` được giữ vì đây là lời chào duy nhất của trạng thái trống, cần nổi hơn thân bài; không tăng tiêu đề công cụ hay tiêu đề trang quản trị. Source lint 0 FAIL, 19 WARN vẫn do quy tắc reset bóng `none`.

Đã xem ảnh desktop/tablet/mobile và ảnh hội thoại: hành động hỏi ở trung tâm, ô nhập/gợi ý chung mép, không có số liệu giả, không có biểu đồ/legend, mobile thu điều hướng. Font ổn định và nền giảm nổi giải quyết hai điểm cạnh tranh thị giác; khoảng cách và hover không dịch chuyển giải quyết điểm thứ ba. Kiểm tra CDP tương tác lại đạt: tọa độ Grace, chiều rộng gợi ý, nhập nhiều dòng, chờ/trả lời giả lập, overlay mobile, Escape và không tràn ngang/không có ngoại lệ JavaScript. Phản hồi chỉ giả lập trong browser QA, không gọi backend hoặc LLM. Artefact cục bộ: `web/.taste-skill/grace-ui/`, `grace-ui-state/`, `verify-grace.mjs`; không commit chúng.

### Bổ sung: sửa font tiếng Việt

Theo yêu cầu tiếp theo của người dùng, đổi `--font-interface` trong `web/src/styles/index.css` sang `Cambria, "Times New Roman", serif`. Tách `--font-brand` cho Agmena và dùng riêng ở `.brand`/`.brand small`. Giữ @font-face, file font, giấy phép và ghi chú cũ; không sửa phần việc của thành viên khác.

Đã chạy lại Prettier cho CSS và `npm.cmd run build`: đạt. Kiểm tra font thực tế bằng Chrome DevTools Protocol xác nhận tiêu đề, placeholder ô nhập và nút gợi ý dùng Cambria; chữ logo dùng Agmena Pro Book. Đã xem ảnh chụp màn hình và không ghi nhận ngoại lệ JavaScript. Đây là thay đổi CSS, không chạy lại kiểm thử API.

Cambria là font hệ thống, không tải từ mạng. Máy không có Cambria dùng Times New Roman hoặc serif hệ thống nên hình dáng có thể khác giữa các hệ điều hành. Không cố bổ sung glyph tiếng Việt bằng CSS vào Agmena.

### Bổ sung: dọn font không dùng

Theo yêu cầu người dùng, đã xóa 10 tệp không dùng (2.569.841 byte): ZIP tải về, shortcut nguồn, hai bản TTF Agmena, các bản EOT/SVG/WOFF, trang demo và hai tệp Mantinia. Xóa thư mục Mantinia sau khi rỗng; gỡ khai báo `@font-face` Mantinia, giữ ghi chú lịch sử trong CSS. Không đổi đường dẫn WOFF2 logo đang dùng.

Trong `web/font/` hiện chỉ còn `License.txt` và `Agmena Pro Book/Web Fonts/342059cdb5197a064e40738c5fdc8727.woff2`. Giữ ghi nguồn font trên trang Về dự án. Đã kiểm tra danh sách đường dẫn trước khi xóa, xác nhận tất cả nằm trong `web/font/`, cập nhật `web/IMPLEMENTATION.md`.

Build TypeScript/Vite và `npm.cmd run format:check` sau khi dọn đều đạt. Bundle không còn đóng gói Mantinia; font WOFF2 Agmena vẫn được xuất ra. Không chạy lại test API cho thay đổi tài nguyên/CSS này. Không tự commit hoặc push.

Trong thư mục `web`, chạy `npm.cmd run dev`, mở địa chỉ Vite in ra (thường `http://localhost:15173`) rồi tải lại trang. Thử đóng/mở sidebar, thu màn hình, gõ nhiều dòng và Shift+Enter. Gửi câu hỏi thật cần backend của dự án đang chạy; lỗi kết nối khi thiếu backend không có nghĩa là CSS lỗi.
