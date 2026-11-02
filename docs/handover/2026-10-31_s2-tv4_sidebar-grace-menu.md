# TV4 · Nút điều hướng sidebar theo menu Elden Ring

Ngày: 31/10/2026 (Asia/Saigon). Nhánh hiện tại `feature/s2-tv4-bot-ask-api-mock`; thay đổi UI này chưa commit/push. Giữ nguyên các thay đổi Makefile/hướng dẫn bot đã có trước lượt làm việc.

## Phạm vi

Theo yêu cầu cụ thể của người dùng: chỉ thay giao diện nút trong Sidebar Navigation, hiệu ứng vệt sáng trên chữ và chọn biểu tượng từ thư mục `web/item_/` do người dùng cung cấp. Không sửa nền/main chat, khung đại kiếm, cờ gợi ý, nút gửi, logic hỏi/đáp, backend, bot hoặc phần TV1–TV3. Không sửa root README, planning hoặc tự đăng ký/chạy Discord.

## Component và tài nguyên

- `web/src/components/layout/GraceMenuItem.tsx`: component dùng chung, render button cho cuộc trò chuyện mới và NavLink cho About/Admin. Giữ nhãn trợ năng, disabled, title, aria-current và callback cũ; ảnh trang trí không nhận pointer, không kéo thả và không bị đọc lặp.
- `web/src/styles/sidebar-menu.css`: mọi selector giới hạn trong sidebar. Chữ mặc định opacity 0,6; route đang chọn 0,9; hover/focus lên 1. Vệt 2 px nằm phía trên vùng chữ, gradient trắng-vàng giữa và trong suốt hai đầu, drop-shadow hổ phách, scaleX từ tâm + opacity 0→1 trong 0,3 giây ease-in-out. Mouse leave chuyển ngược, không tạo viền/nền hộp. Reduced motion tắt transition nhưng giữ trạng thái rõ.
- `web/src/pages/ChatPage.tsx`: chỉ thay RailIcon và markup ba mục điều hướng bằng component; giữ chú thích cũ, thêm chú thích giải thích việc thay SVG.

Đã xem ảnh gốc trước khi chọn:

| Mục | Ảnh trong `web/item_/` |
|---|---|
| Cuộc trò chuyện mới | `MENU_40367_Information.png`: giấy và bút |
| Về dự án | `MENU_Tab_31_FaithMagic.png`: cuộn sách |
| Quản trị | `MENU_FL_Sysytem.png`: bánh răng |

Logo Grace và toggle mở/đóng sidebar không đổi. Icon mới dùng slot cố định 28 × 28 px, giữ cùng tọa độ mở/thu; menu cao 56 px để có chỗ cho vệt sáng. Thu gọn giấu nhãn, vệt sáng thu theo icon. Không chỉnh/sửa/xóa các ảnh khác trong item_; ba import trên là tài nguyên bắt buộc cần đưa cùng mã khi commit, các ảnh khác không được tự nhận là đã sử dụng.

## Quyết định thiết kế và ngoại lệ Taste Skill

Tiếp tục hướng app True-black flat và seed `382339176` của lượt thiết kế trước; không rút lại shell hoặc thiết kế lại main. Glow, gradient và text-shadow chỉ trong trạng thái tương tác sidebar là **yêu cầu trực tiếp của người dùng**, được ưu tiên so với quy tắc tránh trang trí của skill. Không thêm hiệu ứng vào toàn trang. Không dùng ảnh cursor lớn vì gradient CSS nhẹ hơn và co đúng theo nhãn.

## Kiểm tra đã chạy

- `npm.cmd run build`: TypeScript + Vite đạt; bundle chứa đúng ba ảnh được import.
- `npm.cmd test`: 17/17 test web hiện có đạt.
- `npm.cmd run format:check` và kiểm tra Prettier các file mới: đạt.
- Kiểm tra trình duyệt Chrome/CDP: default, hover, mouse leave, keyboard focus-visible, disabled; opacity 0,6→1, transition 0,3 giây, không có nền/viền hộp, không dịch chuyển nút hoặc composer. Ảnh tải thành công; About điều hướng đúng và có aria-current; thu gọn giấu nhãn; mobile overlay không tràn ngang; reduced motion về 0s; không có ngoại lệ JavaScript.
- Đã mở và xem ảnh desktop 1440 px, tablet 768 px, mobile 390 px, hover/focus và mobile menu mở. Các mép/main giữ nguyên, icon cùng cột, ánh sáng không che chữ; số liệu/biểu đồ/legend không áp dụng cho thay đổi này.
- Inspector cuối: **0 FAIL, 2 WARN** cũ về Cambria hệ thống và h1 lời chào 36 px ngoài sidebar; giữ nguyên vì yêu cầu chỉ sửa sidebar. Cambria đã được xác minh là font hệ thống thực sự trong lượt sửa font trước.
- Source lint nhận ngoại lệ `taste-skill-ignore` ngay khai báo gradient được yêu cầu; cảnh báo shadow gồm reset `none` và glow tương tác có chủ ý. Không bỏ glow chỉ để đạt quy tắc thiết kế mặc định trái yêu cầu người dùng.
- Artefact kiểm tra cục bộ (Git bỏ qua): `web/.taste-skill/grace-sidebar-final/`, `grace-sidebar/`, `check-sidebar.mjs`. Không gọi backend hoặc LLM trong QA.

## Cách xem và giới hạn

### Cập nhật theo ảnh mẫu menu TIẾP TỤC

Người dùng làm rõ hiệu ứng là dải sáng vàng loang **sau chữ**, không phải đường kẻ 2 px phía trên như yêu cầu đầu. Chỉ sửa `sidebar-menu.css`: dùng `web/item_/MENU_Title_Cursor.png` đã xem trước, vùng sáng cao 44 px, tâm trùng hàng chữ, texture phóng ngang 190% để hào quang phủ vùng nhãn, blend screen tránh nền đen hình hộp và mask làm mờ hai đầu để texture phóng lớn không bị cắt vuông. Chữ/icon nằm trên texture; thu gọn đổi sang vùng sáng cao 32 px sau icon. Giữ opacity/scale từ tâm, hover/focus 0,3 giây, disabled và reduced motion; không đổi JSX/chức năng/menu main.

Build và Prettier sau sửa đạt; kiểm thử CDP hover/leave/focus/disabled, vị trí nút/composer, ảnh, route About, rail/mobile và reduced motion vẫn đạt. Đã xem ảnh hover và menu mobile; inspector 1440/768/390 px vẫn 0 FAIL, 2 WARN ngoài sidebar như trước. Không chạy lại unit API vì chỉ đổi CSS; không gọi backend/Discord/LLM. Ảnh QA tại `web/.taste-skill/grace-sidebar-reference/`; tài nguyên cursor này là ảnh thứ tư bắt buộc cần commit cùng ba icon. Các quyết định “không dùng ảnh cursor”/“vệt phía trên” ở phần trước là lịch sử đã được thay bằng yêu cầu ảnh mẫu này.

Chạy `make web` tại gốc hoặc `npm.cmd run dev` trong web, tải lại trang. Hover lần lượt ba mục sidebar, dùng Tab để kiểm tra focus, thử thu gọn/mở menu. Callback của các nút giữ nguyên; Quản trị vẫn là khung tính năng hiện có, không được coi là tích hợp API admin hoàn tất.

Các ảnh item_ là tài nguyên do người dùng cung cấp; chưa thay đổi thông tin giấy phép/ghi nguồn ngoài phạm vi này. Chưa commit/push hoặc thay đổi branch.

### Chọn tài nguyên hi_01 và tăng độ rõ icon

Theo yêu cầu tiếp theo, đã xem bảng ảnh ứng viên trong thư mục người dùng cung cấp `../item/hi_01_common-tpf-dcx_split/`, rồi chọn đúng 5 ảnh gốc đưa vào `web/item_/`. Các ảnh đích đã tồn tại được so SHA-256 và giữ nguyên khi giống nguồn; không sao chép cả bộ hi_01.

- `MENU_FL_Message.png`: biểu tượng lời nhắn cho Cuộc trò chuyện mới.
- `MENU_40367_Information.png`: cuộn giấy cho Về dự án.
- `MENU_FL_Sysytem.png`: bánh răng cho Quản trị.
- `MENU_Title_Cursor.png`: hào quang ngang sau nhãn.
- `MENU_FL_Cursor_Top.png`: lõi sáng mảnh chồng trong hào quang.

Giữ nguyên ảnh nguồn, không vẽ lại hoặc chỉnh sửa bitmap. Icon bỏ opacity 0,7, tăng brightness/contrast và scale 1,15 trong ô 28 px cố định để rõ hơn mà không thay vị trí rail. Texture ánh sáng trở về 100% chiều rộng thay cho 190% bị cắt; giữ mask fade hai đầu, screen blend, opacity/scale 0,3 giây, disabled và reduced motion. Nhãn mặc định vẫn opacity 0,6 theo yêu cầu trước. Chỉ chỉnh component/CSS sidebar, giữ các comment cũ và bổ sung giải thích; không sửa main content, backend, bot hoặc README gốc.

Đã chạy: Prettier cho hai file, `npm.cmd run build` (đạt), kiểm tra CDP (đạt: ảnh tải, hover/leave/focus/disabled, không layout shift, thu gọn, About, mobile, reduced motion). Đã xem screenshot hover. Inspector trên Vite dev ở 1440/768/390 px: 0 FAIL, 3 WARN — font Cambria hệ thống, h1 36 px ngoài sidebar, và đang kiểm tra dev server. Build production đã đạt nhưng chưa chạy inspector trên preview production trong lượt này. Không chạy backend, Discord hoặc LLM. QA cục bộ trong `web/.taste-skill/hi01-after/` và bảng ứng viên `hi01-candidates.jpg` (Git bỏ qua). Chưa commit/push; phần thay đổi Makefile/bot có sẵn được giữ nguyên.

### Thay vệt ảnh bằng ánh sáng CSS có nhịp (yêu cầu mới nhất)

Người dùng không thích texture tĩnh. Đã bỏ hoàn toàn hai URL MENU_Title_Cursor / MENU_FL_Cursor_Top khỏi sidebar-menu.css; build không còn đóng gói hai ảnh hiệu ứng. Giữ file nguồn trong item_ để không xóa tài nguyên người dùng, nhưng chúng không còn được sử dụng. Ba ảnh icon vẫn giữ nguyên.

Thay bằng hai pseudo-element CSS: quầng vàng radial-gradient mềm và lõi linear-gradient trắng-vàng mảnh. Nhịp 1,15 giây khi hover/focus: mờ → sáng nhanh sau khoảng 0,32 giây → dịu xuống, lặp khi vẫn tương tác; rời nút fade-out 0,3 giây. Chỉ animate opacity/transform, không animate kích thước/layout hoặc filter; reduced motion tắt keyframes và giữ ánh sáng tĩnh để nhận biết focus. Không thêm JS/dependency. Comment lịch sử texture được cập nhật để tránh mô tả sai; giữ các ghi chú còn phù hợp.

Kiểm tra thực tế: Prettier và build đạt. CDP sidebar regression đạt (hover/leave/focus/disabled, ảnh icon, vị trí composer/nút, thu gọn, About, mobile, reduced motion). Kiểm tra Web Animations API pause/seek keyframes xác nhận opacity lõi lần lượt 0,45 → 1 → 0,55, duration 1150ms, background không có URL ảnh, reduced motion animation-name none. Đã xem ảnh hover sau thay đổi. Các kiểm tra trong web/.taste-skill/check-css-pulse.mjs và check-sidebar-reference.mjs bị Git bỏ qua. Chỉ sửa CSS sidebar và cập nhật bàn giao; không sửa main/bot/backend hoặc README gốc, chưa commit/push.

### Đổi toàn bộ ba icon và mở rộng, làm chậm hover

Theo phản hồi tiếp theo, thay cả ba ảnh sidebar bằng bộ tab không có khung trong hi_01. Đã Copy-Item từ `../item/hi_01_common-tpf-dcx_split/` vào `web/item_/` và đối chiếu SHA-256 nguồn/đích của từng file, đều giống nhau: `MENU_Tab_22.png` (lời nhắn, Cuộc trò chuyện mới), `MENU_Tab_18.png` (giấy, Về dự án), `MENU_Tab_03.png` (chìa khóa, Quản trị). Component import đúng ba file trong item_, không tải ảnh từ thư mục ngoài repo. Các icon trước đã được chép ở lượt trước; lượt này thay bộ mới vì chi tiết/khung của bộ cũ rối khi thu nhỏ. Giữ tài nguyên cũ của người dùng, không xóa hàng loạt.

Hover CSS được nới sang hai bên và quầng vàng trải rộng tới 63% trước khi fade, phủ hết nhãn thay vì đốm ở tâm. Transition xuất hiện/biến mất 0,65 giây; nhịp sáng 3,2 giây thay 1,15 giây, đỉnh ở 45% vòng (khoảng 1,44 giây). Scale tối thiểu 0,95–0,97 để không co ánh sáng nhỏ hơn chữ. Vẫn là CSS, không dùng lại texture; giữ reduced motion, disabled và rail. Chỉ sửa GraceMenuItem.tsx / sidebar-menu.css, bổ sung ghi chú và bàn giao.

Prettier và build đạt; output build dùng đúng ba ảnh MENU_Tab mới. CDP regression đạt: ảnh tải, hover/leave/focus/disabled, không dịch layout/composer, About, rail, mobile và reduced motion. Đã xem screenshot hover: icon không khung và quầng sáng bao toàn bộ nhãn. Không chạy backend/Discord/LLM; chưa commit/push.

### Menu in hoa, chuyển ghi chú AI và nới hover hai bên

Theo yêu cầu mới: nhãn GraceMenuItem dùng text-transform uppercase (ba mục menu, không đổi tiêu đề lịch sử). Ghi chú “AI có thể mắc sai sót.” được bỏ khỏi sidebar và đặt ngay sau MessageInput trong fragment composer dùng chung; hiện dưới ô nhập cả lúc trống và khi có hội thoại, không thêm vào About/Admin. Style chat-ai-note trong refinement.css căn giữa, 14 px, giữ độ tương phản trên nền ảnh.

Quầng hover mở rộng từ left 28/right -8 sang left -12/right -14, đi qua toàn hàng icon + chữ; miền màu trải tới 73% rồi fade tới 94%, phủ rõ hai đầu đoạn chữ. Giữ nhịp 3,2 giây và chuyển cảnh 0,65 giây như lượt trước. Override rail thu gọn vẫn giữ quầng nhỏ theo ô icon.

Prettier và build đạt. CDP regression đạt hover/leave/focus/disabled, không dịch layout lúc tương tác, tải icon, route About, rail/mobile và reduced motion. Đã xem screenshot mới: cả ba nhãn in hoa, ghi chú nằm dưới ô chat, sidebar không còn ghi chú. Chỉ sửa web/src/pages/ChatPage.tsx, web/src/styles/sidebar-menu.css, web/src/styles/refinement.css và bàn giao; không sửa phần TV1–TV3, bot hay README gốc. Chưa commit/push.

### Nhãn sidebar tiếng Anh cố định

Theo yêu cầu mới nhất, ba nhãn menu đổi thành NEW CHAT, ABOUT và OPTION (thay Quản trị). Tooltip và aria-label lấy cùng label từ GraceMenuItem. OPTION vẫn dẫn /admin, ABOUT vẫn /about, NEW CHAT vẫn reset hội thoại; chưa tạo trang cài đặt mới. Các nội dung trang, thông báo và lịch sử giữ tiếng Việt, không khôi phục bộ chuyển ngôn ngữ.

Chỉ sửa nhãn ChatPage.tsx, cập nhật kỳ vọng trong language.test.ts và bàn giao. 17/17 test đạt, build đạt; Prettier ban đầu báo nhãn ngắn làm JSX cần định dạng lại, đã chạy write rồi check đạt. Không gọi backend/LLM/Discord và chưa commit/push.

### Trở về nhãn tiếng Việt đã chốt

Người dùng duyệt bộ nhãn TRÒ CHUYỆN MỚI / VỀ DỰ ÁN / QUẢN TRỊ thay cho NEW CHAT / ABOUT / OPTION. Đã đổi ba label trong ChatPage.tsx; tooltip và aria-label theo cùng label. Giữ kiểu chữ in hoa, icon, hiệu ứng và route/callback. Cập nhật language.test.ts xác nhận đúng nhãn Việt kể cả lựa chọn en cũ hoặc storage bị chặn. Prettier đạt, 17/17 test đạt, build đạt. Chỉ sửa nhãn web TV4, test liên quan và bàn giao; không đổi bot/backend hoặc README gốc. Chưa commit/push.

### Chọn khung cho favicon

Theo yêu cầu xem và đưa một khung hi_01 vào item_, đã xem 12 ảnh khung ứng viên, chọn MENU_FL_Arts_wakuDeco.png (182×184 px): nét vàng, góc vát và tâm trong suốt. Khung này hợp hướng mỹ thuật Elden Ring hơn khung SelectWaku trắng hoặc các nền tối. Đã chép nguyên bản từ ../item/hi_01_common-tpf-dcx_split/ vào web/item_/ và kiểm tra SHA-256 nguồn/đích giống nhau. Không sửa bitmap, không thay favicon HoanGiapVang.jpg trong index.html hoặc icon Grace của sidebar. Khi ghép favicon 16/32 px, chi tiết hoa văn nhỏ có thể mất; cần kiểm tra độ rõ sau khi ghép theo yêu cầu tiếp theo. Chỉ thêm asset và bàn giao, không cần chạy lại build/test vì chưa import hoặc thay mã nguồn. Ảnh ứng viên được xem tại web/.taste-skill/favicon-frames.jpg (Git bỏ qua). Chưa commit/push.

### Màu chữ #f9c043

Theo yêu cầu đổi màu chữ, đã đặt --ui-text và --ui-muted thành #f9c043 trong refinement.css; đồng bộ chữ logo, menu, nhãn assistant, ghi chú AI và chữ About/Admin/trích dẫn. sidebar-menu.css dùng biến chữ chung thay màu hardcode. Giữ opacity menu mặc định/hover, không tô lại bitmap icon/favicon, không đổi nền nút hoặc màu lỗi. Chỉ sửa hai file CSS web TV4 và bàn giao.

Prettier và build đạt. CDP xác nhận computed color rgb(249,192,67) ở logo, ba menu, lời chào, mô tả, textarea, ghi chú AI, ba gợi ý và nội dung About. Đã xem ảnh web/.taste-skill/gold-text-home.jpg; script check-gold-text.mjs được Git bỏ qua. Không gọi API/backend hoặc chạy lại unit vì thay màu CSS. Chưa commit/push.

### Chữ menu trắng sáng, bỏ độ mờ

Người dùng yêu cầu riêng ba nhãn sidebar sáng trắng hơn. Đã đổi color của grace-menu từ màu vàng nhạt hiện có #f0dfbd sang #fff, opacity nhãn mặc định và active từ 0,6/0,9 sang 1. Giữ trạng thái disabled 0,3, hiệu ứng hover, icon và màu logo/phần còn lại tại thời điểm sửa; không áp lại màu toàn web. Chỉ thay sidebar-menu.css và bàn giao. Prettier và build đạt; Chrome/CDP xác nhận đủ ba nhãn có computed color rgb(255,255,255), opacity 1 ngay khi chưa hover. Không gọi API/backend và chưa commit/push.

### Làm rõ cụm logo phía trên

Người dùng thấy cụm logo mờ. CSS không có blur áp lên chữ logo; Agmena có nét mảnh ở cỡ 20 px, dòng phụ 11 px màu muted. Đã sửa riêng refinement.css: logo desktop 22 px/weight 600, tracking 0,04em, vàng #f9c043; strong kế thừa màu/weight. Dòng phụ 12 px dùng font giao diện cho nét rõ, màu trắng. Giữ ảnh Grace, ô toggle 30×30 tại x16/y28, callback và sidebar. Font Agmena chỉ có bản Book nên weight đậm được trình duyệt tổng hợp theo font-synthesis weight sẵn có.

Prettier/build đạt. Chrome/CDP xác nhận cỡ/weight/màu, logo và phụ đề không vượt sidebar, toggle không dịch vị trí, mobile 390 px không tràn ngang; đã xem screenshot web/.taste-skill/brand-clear.jpg. Không chạy lại unit vì chỉ CSS, không gọi backend/LLM, chưa commit/push.

### Cân bằng độ sáng chữ theo phản hồi mới nhất

Người dùng muốn chữ hài hòa, không chói trên nền tối. Đã chọn hệ màu ấm thay cho trắng tuyệt đối/vàng gắt: --ui-text #ddd7ca (chữ chính, menu), --ui-muted #b7b09f (mô tả, dòng phụ logo, ghi chú AI), --ui-brand #d4b571 (logo). Menu vẫn opacity 1 để không nhòe nét; chỉ giảm màu, không hạ opacity. Giảm text-shadow hover menu từ #edc77b66/10px xuống #edc77b33/8px. Giữ cỡ chữ, độ đậm logo, bố cục, icon, màu nút/màu lỗi và nhịp hover.

Chỉ sửa refinement.css, sidebar-menu.css và bàn giao. Prettier/build đạt. Chrome/CDP xác minh màu computed của menu/lời chào/logo/dòng phụ/ghi chú và opacity menu 1; mobile 390 px không tràn ngang. Đã xem ảnh desktop web/.taste-skill/text-balanced-desktop.jpg, ảnh mobile và script check-text-balanced.mjs được Git bỏ qua. Không gọi API, không chạy lại unit cho thay màu CSS, chưa commit/push.
