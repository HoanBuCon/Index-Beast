# TV4 · Điều hướng đăng nhập/chat và menu tài khoản

Ngày 22/11/2026 (Asia/Saigon). Trợ lý thực hiện phần TV4 theo yêu cầu của người dùng. Làm trên nhánh cục bộ `feature/s5-tv4-menu-tai-khoan-auth-routing` (tách từ `origin/develop` tại `099639a`, chưa từng push); theo yêu cầu người dùng, toàn bộ thay đổi được commit, rebase lên `origin/develop` mới nhất và push lên `feature/s5-tv4-tai-khoan-auth-responsive`; sau đó người dùng yêu cầu xóa nhánh đó và chuyển toàn bộ (kèm đổi ghi chú dưới ô nhập) sang nhánh `feature/s5-tv4-giao-dien-tai-khoan-responsive`. Chưa mở PR. Không đưa vào nhánh: handover TV2 `2026-11-22_s5-tv2_chuyen-data-vao-backend.md` (việc của TV2) và ảnh có khung không dùng `MENU_FL_40135_Profile.png`.

## Yêu cầu và phạm vi

1. Điều hướng hai chiều giữa màn đăng nhập và chat; khách vẫn dùng thử được.
2. Hoàn thiện phần client của Discord/Google Auth trong phạm vi TV4, theo trạng thái backend thực tế.
3. Gom quản trị, đăng nhập/đăng xuất và xóa tài khoản vào một menu ở góc dưới sidebar, tương tự cách bố trí tài khoản của ChatGPT; giữ theme Elden Ring hiện có.

## Đã triển khai

- `AccountMenu.tsx`, `account.css`: một nút tài khoản cuối sidebar, tên/initial, popover mở phía trên; khách và thành viên có nhóm thao tác riêng. Menu hỗ trợ click ngoài, Esc, phím mũi tên/Home/End và trả focus. Tự chỉnh vị trí khi viewport hoặc khối tài khoản đổi kích thước. Nút vẫn hiện trong rail thu gọn với vùng bấm rộng 44 px.
- `ChatPage.tsx`: bỏ nút quản trị và các nút tài khoản rời; đưa vào menu chung. Quản trị theo `user.is_admin` hoặc `traceAvailable` (API có cơ chế token vận hành). Đăng nhập đi qua màn `/login`; logout/delete thành công về `/login`, giữ cơ chế dọn lịch sử theo chủ sở hữu. Dialog dùng vòng focus riêng, không bị vòng Tab của sidebar mobile can thiệp.
- `sidebar-menu.css`, `index.css`: bỏ style tài khoản rời cũ và quy tắc ẩn tài khoản khi thu gọn. Thay đổi này được kiểm bằng browser vì ban đầu CSS cũ làm nút biến mất ở 768 px.
- `LoginPage.tsx`, `login.css`: giữ **Dùng thử**, tiếp tục theo `next` khi đã có phiên; mỗi provider có trạng thái khả dụng/chờ chuyển trang riêng. Hiện thông báo cố định khi bị từ chối, hết hạn hoặc lỗi; không render trực tiếp giá trị query `login`. Theo yêu cầu bổ sung ngày 22/11, đã bỏ link **Trò chuyện ↗** ở góc trên phải và CSS riêng của link này.
- `api/auth.ts`, `useAuth.ts`, `AuthContext.ts`: URL builder cùng origin, chỉ quay lại màn hợp lệ; Google có capability riêng mặc định tắt. Sửa `logoutVerified`: không xem lỗi mạng của `/auth/me` là bằng chứng đã đăng xuất.
- Test mới `authNavigation.test.ts`, `accountNavigationUI.test.ts`; cập nhật các test cũ theo việc menu thay thế nút rời.
- Hợp đồng tích hợp và phần TV1 còn cần làm ghi trong [auth-tv4.md](../api/auth-tv4.md).

## Bổ sung 22/11: icon hi_01 cho menu tài khoản

Theo yêu cầu của TV4, thay chữ cái đầu và ký tự `···` bằng icon menu Elden Ring. Ảnh chép nguyên bản từ `item/hi_01_common-tpf-dcx_split` (ngoài repo) vào `web/item_`, không tham chiếu thư mục nguồn bên ngoài. Không dùng ảnh từ `hi_00_solo-tpfbdt`: thư mục này chỉ có ảnh vật phẩm/kiến thức 1024×1024 (~1 MB mỗi ảnh) và màn tải 4096×2048, không có icon giao diện phù hợp.

| Vị trí | Ảnh trong `web/item_` | Ghi chú |
|---|---|---|
| Avatar khách | `MENU_Tab_10.png` (mũ giáp) | **Mới chép** |
| Avatar thành viên | `MENU_Tab_Armor.png` (hiệp sĩ quỳ) | **Mới chép** |
| Nút mở menu (thay `···`) | `MENU_Tab_Option.png` (tay cầm) | **Mới chép** |
| Quản trị | `MENU_Tab_03.png` | Cùng icon quản trị ở sidebar |
| Đăng nhập / Trang đăng nhập | `MENU_Tab_12.png` (găng tay) | **Mới chép** |
| Đăng xuất | `MENU_Tab_Exit.png` | Đã có sẵn |
| Xóa tài khoản | `KG_Key_Delete.png` | **Mới chép**, cùng bộ phím với Enter/Esc của ô nhập |

**Quy ước TV4:** chỉ dùng icon **không có khung viền** (bộ `MENU_Tab_*`, phím `KG_Key_*`); không dùng ảnh `MENU_FL_*` có khung đá vuông (vd. `MENU_FL_Status`, `MENU_FL_40135_Profile`, `MENU_FL_Sysytem`). Bản đầu dùng ba ảnh có khung này và đã được thay; bản chép `MENU_FL_Status.png` đã xóa khỏi `item_`.

Các ảnh đã có sẵn được đối chiếu byte-to-byte với bản trong `hi_01`. File sửa: `AccountMenu.tsx` (thêm `MenuIcon`, ảnh `alt=""`, `aria-hidden`; nhãn và `aria-label` giữ nguyên) và `account.css` (avatar 34 px không bo tròn để giữ khung đá, icon menu 24 px).

Đã chạy: `npm test` 79/79 đạt, `npm run build` đạt, `npm run format:check` đạt. Đã xem trong browser ở trạng thái **khách** (Vite dev, không có API): avatar, nút menu và mục Đăng nhập hiển thị đúng. Trạng thái thành viên/admin (Đăng xuất, Xóa tài khoản, Quản trị) **chưa xem bằng browser** vì local chưa có phiên đăng nhập; chỉ được test render bao phủ.

## Kiểm tra thực tế

- `npm test`: toàn bộ 79 test đạt. Các test dùng fetch giả/SSR, không dùng tài khoản thật.
- `npm run build`: typecheck và Vite production build đạt.
- `npm run format:check`: đạt; `git diff --check` không có lỗi khoảng trắng.
- Browser Chrome/Edge qua CDP, fixture Vite cô lập: `.taste-skill/check-account-navigation.mjs`. Kiểm tại 1440×900, 768×900, 360×900: menu không tràn/cắt, sidebar thu gọn, khách/thành viên/admin, điều hướng login/chat, outside click, Escape và focus, Home/End, logout thành công/lỗi mạng, dialog Hủy/Esc, xóa lỗi/thử lại và chuyển trang khi thành công.
- Kiểm riêng sidebar mobile mở rộng: Esc đóng riêng menu và Tab giữ trong dialog xác nhận. Cả hai provider có phép thử chuyển hướng với endpoint **giả lập**, kiểm đường `next`; không phải đăng nhập với Google/Discord thật.
- Browser không có runtime exception ở lượt kiểm hoàn tất; ảnh kiểm tra nằm trong `.taste-skill/account-{guest,admin,login}-{1440,768,360}.jpg` (Git ignore).
- Kiểm lại bundle production qua `vite preview` với API fixture riêng: `.taste-skill/check-account-production.mjs`, đạt menu và routing tại cả 3 kích thước, không có runtime exception. Ảnh `.taste-skill/account-production-{1440,768,360}.jpg`.
- Đã chạy inspector `.taste-skill` cho màn chat. Inspector trả 1 do `text-shadow` của giao diện cũ; có cảnh báo về font dự phòng Cambria, cỡ tiêu đề màn chào và dev server. Giữ phong cách Elden Ring mà người dùng đã chọn; không coi lượt inspector này là pass toàn bộ quy tắc thiết kế. Kiểm production và kiểm tương tác ở trên được chạy riêng.

## Responsive màn chào ở cửa sổ hẹp (22/11)

Người dùng báo ở cửa sổ ~530 px (chia đôi màn hình): tiêu đề đè lên chữ logo "ONION RING" của ảnh nền và 3 nút gợi ý bị ép thành 3 cột hẹp, chữ xuống 3 dòng.

- Nguyên nhân: `patches.png` (1054×1459) bị `background-size: 100% 100%` kéo giãn dọc theo khung chat, nên vị trí chữ logo trôi theo chiều cao; lời chào lại canh giữa dọc. Quy tắc thu nhỏ ở mốc 700 px trong `index.css` bị `refinement.css` (nạp sau, cùng độ ưu tiên) ghi đè, nên chỉ mốc 520 px có tác dụng.
- Sửa `refinement.css`: thêm `@media (max-width: 700px)`: ảnh nền phủ ngang, neo trên (`100% auto`, `center top`); lời chào neo dưới logo bằng `padding-top: max(40px, (100vw − 62px) × 0,38)` thay vì canh giữa; tiêu đề 28 px với `text-wrap: balance`; nút gợi ý 1 cột. Mốc 520 px giữ cùng cách tính padding trên.
- Đã xem bằng browser ở 375×812, 530×945, 680×900, 768×1024 và 1440×900: ở ≤700 px tiêu đề nằm dưới logo, nút gợi ý xếp dọc. Cỡ >700 px không đổi so với trước. `npm test` 79/79, `npm run build`, `format:check` đạt.
- Bổ sung theo yêu cầu người dùng: màn rộng (> 700 px) giữ ảnh kéo đầy khung như thiết kế, nhưng chữ logo luôn kết thúc ở ~26 % chiều cao khung, nên lời chào neo ở `padding-top: 29dvh` (`margin: 0 auto auto`) thay vì canh giữa dọc. Cửa sổ thấp (≤ 759 px cao) dùng 28dvh và thu gọn khoảng cách tiêu đề/giới thiệu/ghi chú để không phát sinh thanh cuộn.
- Đo bằng browser (đỉnh tiêu đề so với đáy chữ logo, thanh cuộn của `.chat-content`): 1920×1080 313/281, 1440×900 261/234, 1280×720 202/187, 1366×600 168/156, 1280×650 182/169, 1024×768 223/200, 820×1000 290/260, 530×945 178/168; tất cả không có thanh cuộn. Sau đó `npm test` 79/79, `build`, `format:check` đạt.

## Ghi chú dưới ô nhập (22/11)

Theo yêu cầu người dùng, ghi chú dưới ô chat (`ChatPage.tsx`, `.chat-ai-note`) đổi từ "AI có thể mắc sai sót." thành **"INDEX-BEAST có thể mắc sai sót."** Người dùng gõ "sai xót"; dùng chính tả đúng "sai sót". Các câu tương tự ở trang chia sẻ (`SharedAnswerPage.tsx`), trang Về dự án và lệnh `/about`, `/help` của bot giữ nguyên vì không nằm trong yêu cầu. Đã xem trên browser; `npm test` 79/79, `build`, `format:check` đạt.

## Bố cục điện thoại: thanh tiêu đề + ngăn kéo (22/11)

Người dùng yêu cầu responsive đúng nghĩa (bố cục đổi theo màn hình) thay vì chỉ co nội dung: ở điện thoại, cột icon 62 px bên trái làm nội dung bị bóp hẹp.

- `ChatPage.tsx`: thêm `.mobile-topbar` gồm chỗ cho nút menu (dùng lại `sidebarToggle` có sẵn, giữ `aria-controls`/`aria-expanded`), chữ **INDEX BEAST** (link `/chat`) và nút **Trò chuyện mới** (icon `MENU_Tab_22`, gọi `reset()`, khóa khi đang trả lời).
- `refinement.css`, `@media (max-width: 700px)`: lưới 1 cột × 2 hàng (thanh 56 px + nội dung); sidebar ẩn hẳn khi đóng; khi mở là ngăn kéo `min(300px, 100% − 56px)` phủ lên nội dung với lớp tối (dùng lại scrim/inert/Esc/vòng Tab của mốc 900 px). Ngoài mốc này, `.mobile-topbar` luôn `display: none`. Padding lời chào ở màn hẹp đổi từ `(100vw − 62px) × 0,38` sang `100vw × 0,38` vì không còn rail.
- Đã xem bằng browser: 375×812 (`/chat`, mở/đóng ngăn kéo bằng nút và bấm lớp tối, focus trả về nút menu; `/about`), 530×945, 700×900 (thanh tiêu đề hiện, sidebar ẩn, không thanh cuộn) và 701×900 (giữ cột icon 62 px như cũ). `npm test` 79/79, `build`, `format:check` đạt.
- Chưa xem trên điện thoại thật và chưa xem màn đang có tin nhắn ở cỡ điện thoại (cần gửi câu hỏi thật tới API).

## Cấu hình Discord OAuth local và đăng nhập thật (22/11)

- Người dùng tự tạo Client Secret, khai báo Redirect `http://localhost:15173/api/v1/auth/discord/callback` trên Discord Developer Portal và tự dán `DISCORD_CLIENT_SECRET`, `AUTH_ADMIN_DISCORD_IDS` vào `.env`. Trợ lý tạo `AUTH_SECRET` ngẫu nhiên 64 ký tự (không in ra), đổi `WEB_URL` sang `http://localhost:15173` (giữ giá trị IP cũ trong dòng chú thích ngay trên) và `CHAT_PERSISTENCE=postgres`. Không ghi giá trị bí mật vào tài liệu.
- DB local đã ở revision `0005`; đã chạy `scripts.memory_admin setup --apply` tạo collection `conversation_memories` (corpus không đổi).
- Kiểm: `Settings().auth_enabled` là `True`; API gửi đúng `redirect_uri` ở trên. Lần đầu Discord báo `Invalid OAuth2 redirect_uri` do Redirect chưa được lưu trên Portal; sau khi người dùng lưu, đăng nhập thành công: bảng `users` có 1 người dùng và `auth_sessions` có 1 phiên còn hạn.
- OAuth với IP/VPN (`26.x`) không dùng được bằng `http`: Discord chỉ nhận `http://` cho `localhost`; chia sẻ qua mạng cần tên miền HTTPS (TV1).

## Giới hạn và bàn giao TV1

- Discord: đã đăng nhập thật trên local (mục trên). Chưa kiểm thật nhánh bấm **Từ chối** và chưa thử trên staging/production. Backend chỉ chuyển về `/?login=denied`; lỗi state hết hạn (400) và lỗi Discord (502) trả JSON thay vì chuyển về `/login?login=expired|error`, nên hai thông báo tương ứng trên web chưa bao giờ hiện. Đề xuất TV1 đổi callback sang redirect.
- **Google Auth backend chưa có**: web đã sẵn sàng nhận `google_auth_available` và điều hướng `/auth/google/login`, nhưng cả capability lẫn route là hợp đồng đề xuất cho TV1, chưa nằm trong backend/OpenAPI hiện hành. Google vẫn khóa và ghi **chưa khả dụng** cho đến khi backend triển khai. Không thể kết luận đăng nhập Google thật đã hoàn thành từ các test client.
- Menu không thay thế kiểm quyền phía API. Chưa nghiệm thu trên tài khoản production; không gọi LLM, không sửa dữ liệu corpus hay thông tin OAuth local trong tác vụ UI.

## Cách thử

Chạy `make dev`, mở `/login`, chọn **Dùng thử** vào `/chat`, bấm nút **Khách** ở góc dưới trái rồi chọn **Đăng nhập**. Khi OAuth server đã cấu hình, đăng nhập và kiểm menu tài khoản, quyền quản trị, logout, xác nhận xóa. Không thử xóa tài khoản thật chỉ để kiểm giao diện; fixture đã kiểm nhánh này.
