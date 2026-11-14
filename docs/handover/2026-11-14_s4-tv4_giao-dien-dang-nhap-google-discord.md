# TV4 · Giao diện đăng nhập Google/Discord

Ngày: 14/11/2026 (Asia/Saigon). Nhánh: `feature/tv4-dang-nhap-google-discord`.

## Phạm vi

Người dùng cho phép làm màn hình đăng nhập trước, vẫn cho khách chat không cần đăng nhập.
Chỉ sửa frontend TV4 và tài liệu bàn giao; không sửa backend/bot, schema, .env, dependency, kế hoạch hoặc README gốc.
Không commit/push. Giữ ghi chú hiện có, thêm ghi chú phạm vi UI.

Đã đọc [kế hoạch](../../planning/sprint_plan.json), [quy ước](../quy_uoc.md),
[ADR-005](../adr/005-dang-nhap.md) và [contract Discord](../api/auth-tv4.md).
ADR hiện là đề xuất ngày 13/11, backend Discord đã có hợp đồng, khác trạng thái Deferred trong bàn giao cũ.
Tác vụ này không phê duyệt ADR hoặc mở rộng backend Google.

## Thay đổi

- `web/src/pages/LoginPage.tsx`: màn hình mới `/login`, tên dự án, biểu tượng Grace, hai provider Google/Discord,
  thông báo chưa khả dụng, link tiếp tục với tư cách khách và About. Hai nút native disabled, không có phiên đăng nhập giả.
- `web/src/styles/login.css`: CSS riêng theo token màu/font hiện có, cạnh vuông, bố cục tối đa 460 px,
  responsive 360 px. Tận dụng ảnh nền chat, không thêm asset hoặc dependency.
- `web/src/App.tsx`: thêm route `/login`.
- `web/src/pages/ChatPage.tsx`: thêm lối vào trên sidebar, khóa khi đang chat như các nút khác;
  riêng login dùng nền chat. Giữ ngữ cảnh và lịch sử khách qua điều hướng; không bắt đăng nhập trước khi chat.
- `web/src/components/layout/GraceMenuItem.tsx`: mở rộng icon login SVG, giữ nguyên các icon cũ.
- `web/tests/login.test.ts`: kiểm provider bị vô hiệu hóa, guest/About navigation và không có form/endpoint OAuth giả.
- `web/IMPLEMENTATION.md`: cách mở và phạm vi chưa tích hợp.

## Kiểm tra đã chạy

- Build TypeScript/Vite và Prettier toàn web đạt; 49 test web đạt, gồm test mới.
- Trình duyệt thật với API giả riêng, không gọi backend/LLM: desktop 1440 px, tablet 768 px, mobile 360 px
  không tràn ngang; provider disabled; không có composer trên trang login.
- Enter trên link tiếp tục khách về `/`, composer vẫn có; localStorage lịch sử không thay đổi trong lượt điều hướng kiểm tra.
  Mục sidebar mở lại `/login` được. Đã xem ảnh desktop và mobile.
- Ảnh/script kiểm tra nằm trong thư mục `.taste-skill` được Git ignore, không đưa dữ liệu thử vào sản phẩm.
- `git diff --check`, UTF-8 và liên kết tài liệu đạt.

## Cách xem

Chạy frontend như hiện tại (`make web` từ gốc hoặc `npm.cmd run dev` trong web), mở `/login`
hoặc bấm **ĐĂNG NHẬP** trên sidebar. Nếu port 15173 đã có Vite thì dùng server đang chạy, không mở bản thứ hai.
Không cần Discord key hay backend để xem UI. Chế độ khách vẫn hoạt động như trước.

## Chưa thực hiện

Đăng nhập thật, đọc trạng thái phiên/tên người dùng, đăng xuất, nhận lại lịch sử khách và đồng bộ tài khoản chưa được nối.
Không lưu service token/session token vào trình duyệt. Hai nút Google/Discord chưa bắt đầu OAuth.
Khi tích hợp Discord, phải dùng `auth_available`, API `/auth/me`, cookie httpOnly, xử lý callback/lỗi/hết phiên theo contract TV1.
Google cần nhóm thống nhất provider và contract backend riêng. Chưa kiểm thử OAuth với tài khoản thật.

## Cập nhật theo làm rõ của người dùng: màn vào độc lập

Người dùng muốn thấy màn đăng nhập trước khi vào web, thay vì đặt trong sidebar.
Luồng cuối cùng: `/` và `/login` render LoginPage độc lập; nút **Vào website** chuyển `/chat` có sidebar và composer.
Chế độ khách không bị khóa bằng xác thực giả; có thể mở `/chat` trực tiếp. Chưa bắt đầu OAuth.
`App.tsx` tách màn vào khỏi ChatPage; Header, reset/chọn lịch sử và link trở về từ bản chia sẻ trỏ tới `/chat`.
`LoginPage` có nền riêng từ asset đã có, không ảnh hưởng nền trong ứng dụng.
Kiểm tra ngôn ngữ/HTTP LAN chuyển route test chat sang `/chat`; test login kiểm hai route vào không có sidebar/composer.
Trình duyệt thật 1440/360 px: màn vào không có sidebar, Enter trên **Vào website** vào `/chat`,
lịch sử khách được seed trong browser kiểm tra vẫn còn sau điều hướng. Không gọi API/LLM thật.

## Tinh chỉnh nền và nội dung theo ảnh người dùng

Nền login chuyển `cover` sang `contain`: hiện toàn bộ ảnh patches đúng tỷ lệ, không crop; khoảng trống theo tỷ lệ màn hình có nền tối.
Bỏ footer About/disclaimer, ghi chú lịch sử khách và dòng trạng thái nhìn thấy dưới provider theo yêu cầu.
Giữ mô tả chưa khả dụng dạng `sr-only` cho công nghệ hỗ trợ; hai provider vẫn disabled.
Tiêu đề mới **Hỏi đáp về Elden Ring**, mô tả rõ tra cứu nhân vật, vũ khí, nhiệm vụ và cốt truyện.
Không đổi nội dung/cơ chế AI disclaimer ở trang chat hoặc About.

Theo yêu cầu tối giản tiếp theo, tiêu đề cuối cùng là **Hỏi đáp Elden Ring**, bỏ hẳn dòng mô tả;
giữ khoảng cách 32 px trước các nút. Kiểm tra định dạng hai file UI và test login đạt.

Người dùng tiếp tục yêu cầu bỏ cả tiêu đề: giao diện cuối chỉ giữ logo/tên INDEX BEAST và các nút.
Bỏ CSS heading không dùng; vùng main có aria-label **Đăng nhập INDEX BEAST** để giữ tên truy cập.
Cập nhật test route theo nhãn main, test login và định dạng đạt.

## Nút provider bấm được khi chưa có chức năng

Theo yêu cầu tiếp theo, bỏ disabled trên hai nút Google/Discord, thêm hover/active theo token hiện có.
Bấm nút hiện thông báo riêng theo provider trong vùng `role=status`; không giả đăng nhập thành công,
không tạo phiên, không redirect hoặc gọi OAuth. Thông báo chỉ xuất hiện sau thao tác, không khôi phục dòng ghi chú thường trực.
Test login đổi kỳ vọng thành hai nút bấm được; giữ kiểm tra không có form/token/endpoint OAuth giả.
TypeScript và test login đạt. Trình duyệt thật 360 px: click Google và Enter trên Discord hiện đúng thông báo,
vẫn ở màn vào, không tràn ngang. Không gọi API/LLM thật để kiểm tra thao tác này.

Theo phản hồi tiếp theo, bỏ mục **ĐĂNG NHẬP** lặp lại trong sidebar và icon login không còn dùng trong GraceMenuItem.
Màn vào riêng ở `/` và `/login` vẫn giữ nguyên; vào `/chat` không có mục đăng nhập trong menu nữa.
Test login kiểm thêm menu chat không có mục này; TypeScript, định dạng và test login đạt.

## Đồng bộ vệt sáng menu cho ba nút

Theo ảnh tham chiếu, ba nút Google/Discord/Vào website bỏ viền hộp và nền hover chữ nhật.
`sidebar-menu.css` mở rộng riêng selector vệt sáng sang login: dùng chung gradient/quầng, transition 0,65 giây,
animation `grace-menu-shimmer` và `grace-menu-core` 3,2 giây, kể cả focus bàn phím và reduced-motion.
Không nhân bản hiệu ứng; layout/icon menu bên trong giữ nguyên. Login thêm span trang trí aria-hidden, giữ chữ/icon phía trên.
`login.css` chỉ điều chỉnh layout và nền trong suốt. Chức năng click/điều hướng không đổi.
Build đạt; 2 test login/sidebar, Prettier và diff check đạt. Trình duyệt thật kiểm cả ba nút hover/focus có cùng animation/duration,
border 0 px, mobile 360 px không tràn ngang. Đã xem ảnh desktop. Không gọi OAuth/API/LLM thật.

## Bố cục cuối theo ảnh trang đăng nhập Claude

Người dùng yêu cầu đổi bố cục theo ảnh mới: logo INDEX BEAST góc trên trái, tiêu đề và nhóm nút bên trái,
ảnh patches lớn bên phải. `LoginPage.tsx` thêm header, lưới hai cột và figure ảnh; `login.css` thay nền ảnh toàn màn
bằng nền tối phẳng, ảnh riêng `object-fit: contain` không cắt; giữ góc vuông theo sở thích trước đó.
Tiêu đề **Khám phá Elden Ring.**, mô tả ngắn; card/nút dùng màu hiện có, giữ vệt sáng chung khi hover/focus.
Không sao chép thương hiệu Claude hoặc thêm email/Apple, chính sách giả hay chức năng backend.
Hai nút provider vẫn chỉ báo chưa sẵn sàng; **Vào website** tới `/chat` dưới dạng khách.
Build TypeScript/Vite, test login và Prettier đạt; trình duyệt thật ở 1440/768/360 px xác nhận desktop hai cột,
tablet/mobile xếp dọc, ảnh tải đủ/contain, không tràn ngang; click Discord hiện thông báo và vào chat còn hoạt động.
Đã xem ảnh desktop/mobile. Các hướng dẫn cũ về ảnh nền toàn màn/ẩn tiêu đề phía trên là lịch sử đã được yêu cầu mới thay thế.

Tinh chỉnh tiếp: bỏ border của `.login-card`, chuyển toàn bộ chữ trong `.login-page` sang in hoa bằng CSS.
Chỉ áp dụng màn đăng nhập, không đổi chữ trong trang chat hoặc nội dung trả lời. Kiểm tra định dạng và diff đạt.

## Bỏ nền hộp và thêm email theo yêu cầu tiếp theo

Google/Discord/Vào website và nút email dùng nền trong suốt, kể cả hover/active; giữ vệt sáng chung.
Nút được đặt text-transform uppercase rõ ràng. Thêm form email với label, type=email, required, autocomplete=email;
giá trị email giữ nguyên hoa/thường và không lưu vào state/storage/log hoặc gửi API.
Submit email hợp lệ chỉ thông báo chưa sẵn sàng; không gửi mã và không giả phiên đăng nhập.
Không thêm email auth backend; đây là yêu cầu UI mới sau ảnh Claude.
Build, test login, Prettier và diff check đạt. Browser 360 px kiểm nền nút trong suốt, email sai bị native validation,
email hợp lệ hiện thông báo, không fetch/đổi trang, không tràn ngang. Không dùng email thật hoặc gọi LLM.

Theo yêu cầu ngay sau đó, bỏ lại toàn bộ divider HOẶC/form email/nút tiếp tục email và CSS không còn dùng.
Trạng thái cuối chỉ có Google/Discord/Vào website; không thay đổi luồng guest hoặc hiệu ứng nút.
Test login kiểm không còn form/input/divider, Prettier và diff check đạt.
## Nền phủ menu từ hi_00 và hi_01

Đã xem các ảnh trong `item/hi_00_solo-tpfbdt` và `item/hi_01_common-tpf-dcx_split`
ở thư mục ngoài repository. hi_00 chủ yếu là hình vật phẩm nên không chọn làm nền đăng nhập.
Chép nguyên bản hai texture menu từ hi_01 vào frontend, kiểm tra SHA256 trùng với bản nguồn:

- `web/item_/MENU_BaseMain_01.png`: lớp phủ tối và ánh mờ phía dưới trang; thêm lớp nhẹ trên ảnh minh họa.
- `web/item_/MENU_FL_MenuBase.png`: nền tối mép mềm sau nhóm nút đăng nhập.

`web/src/styles/login.css` dùng pseudo-element riêng, opacity lần lượt 0.8 cho trang,
0.85 cho nhóm nút và 0.42 cho ảnh. Lớp trang trí không nhận chuột, không che thao tác bàn phím.
Giữ bố cục hai cột desktop, xếp dọc mobile, ảnh contain, chữ in hoa và hiệu ứng hover dùng chung.
Không sửa sidebar, chat, backend, bot hoặc chức năng xác thực.

Kiểm tra lần này: build TypeScript/Vite và Prettier CSS đạt; test login 1/1 đạt.
Trình duyệt thật ở 1440/768/360 px xác nhận ảnh tải được, không tràn ngang và bố cục đúng;
kiểm tra thông báo provider và chuyển sang chat đạt. Đã xem ảnh chụp desktop.
Không gọi API/OAuth/LLM thật. Google/Discord vẫn chỉ hiển thị thông báo chưa sẵn sàng.
Texture là tài nguyên game có sẵn do người dùng cung cấp; không khẳng định đã xác minh quyền phân phối.

## Thay biểu tượng provider bằng hình menu người dùng chọn

Chép nguyên bản từ hi_01 vào `web/item_/MENU_Tab_Net.png` (quả địa cầu) và
`web/item_/MENU_Tab_Manual.png` (tay cầm có sơ đồ nút), xác minh SHA256 trùng nguồn.
`LoginPage.tsx` dùng hai ảnh thay chữ G và SVG Discord; giữ nguyên nhãn Google/Discord,
thông báo chưa sẵn sàng và điều hướng khách. Ảnh trang trí có alt rỗng, không kéo thả;
CSS dành ô 32 × 32 px và object-fit contain để không méo ảnh hoặc xô chữ.

Kiểm tra: Prettier, build TypeScript/Vite, test login 1/1 đạt. Browser fixture
1440/768/360 px đạt kiểm tra bố cục/không tràn, thông báo provider và vào chat;
đã xem ảnh mobile. Không sửa backend/bot, không thêm xác thực hoặc gọi API thật.

## Lớp phủ liên tục toàn màn hình đăng nhập

Theo phản hồi ảnh minh họa còn tách khỏi nền phủ, `login.css` chuyển texture trang
lên trên ảnh bằng z-index 1 và bỏ lớp phủ riêng opacity 0.42 của `.login-visual::after`.
Logo, nội dung và nút ở z-index 2 để chữ không bị mờ và thao tác không bị chặn;
texture phủ một lần toàn trang, gồm cả cột ảnh. Không thay ảnh hoặc cắt ảnh.
Thay đổi này thay thế cách phủ riêng trên ảnh được ghi ở mục trước.

Prettier CSS và build TypeScript/Vite đạt. Browser fixture 1440/768/360 px đạt:
không tràn ngang, ảnh contain/tải đủ, bố cục đúng, thông báo provider và vào chat hoạt động.
Đã xem screenshot desktop: ánh mờ phía dưới chạy xuyên cả nền và ảnh.
Chỉ sửa CSS đăng nhập và bàn giao TV4; không gọi OAuth/API/LLM thật.

## Làm tan mép đen quanh nền toàn trang

Phản hồi tiếp theo yêu cầu bốn cạnh màn hình có sắc xám nâu như menu tham chiếu,
không thành khung đen. `login.css` thay nền đặc bằng gradient xám nâu tối phía trên,
xám ô liu phía dưới; dùng CSS mask làm tan 5% mép texture gốc và mép ảnh minh họa.
Bỏ nền đen riêng của figure, giữ ảnh contain và không chỉnh sửa tệp ảnh nguồn.
Chữ/nút vẫn nằm trên lớp phủ và giữ nguyên hành vi.

Prettier CSS, build TypeScript/Vite đạt; browser fixture 1440/768/360 px đạt kiểm tra
bố cục, ảnh tải đủ, không tràn ngang, thông báo provider và chuyển vào chat.
Đã xem screenshot desktop sau chỉnh: mép ngoài hòa vào xám nâu, không còn khung đen riêng.
Phạm vi chỉ CSS đăng nhập và handover TV4, không đổi API/xác thực/chat.

## Nhóm đăng nhập theo hàng cài đặt game

Theo ảnh tham chiếu mới, các nút đăng nhập chuyển sang nền hàng menu thay cho
vệt sáng menu chính: `MENU_FL_MultiBase.png` làm nền hàng, `MENU_FL_Cursor_Wide.png`
làm dải chọn và `MENU_FL_Cursor_EntWaku.png` làm khung sáng khi hover/focus/active.
Ba ảnh đã có trong `web/item_` nên không chép trùng. Thư mục nguồn hiện có hi_00/hi_01,
không thấy hi_02 tại vị trí bộ ảnh người dùng cung cấp; các ảnh chọn đều từ hi_01.

`LoginPage.tsx` dùng class riêng `login-menu__highlight`, không còn dùng animation
grace-menu của sidebar. `login.css` giữ icon 32 px, hàng 60 px, chuyển cảnh 0.3 giây
và tôn trọng reduced-motion. Không thay sidebar, chức năng provider hoặc API.
Prettier, build TypeScript/Vite, test login 1/1 đạt; browser fixture 1440/768/360 px
đạt kiểm tra bố cục, không tràn, thông báo provider và vào chat.

## Dải chọn phủ hết chiều ngang khung đăng nhập

Phản hồi mới yêu cầu dải chọn dài bằng khung, không chỉ quanh nhãn. `login.css`
thêm biến bleed theo padding desktop/tablet/mobile để texture Cursor_Wide phủ cả icon,
chữ và tới hai mép nền card. Bỏ pseudo-element khung EntWaku quanh nhãn.
Các hàng giữ nguyên chiều cao và hành vi hover/focus/active, không sửa sidebar.

Prettier CSS và build đạt. Browser fixture ở 1440/768/360 px xác minh chiều ngang
dải chọn bằng nền card (504/504/352 px tương ứng), không tràn trang và thao tác vẫn hoạt động.
Đã xem screenshot mobile có focus: dải xám vàng trải toàn hàng, không có khung con.

## Đồng đều sắc tối giữa nền, nhóm nút và ảnh

Theo phản hồi các mảng đen lệch tông, `login.css` giảm nền MenuBase sau nhóm nút
từ opacity 0.85 xuống 0.16, dùng mask ellipse để tan cả bốn cạnh; các hàng nút bỏ
texture nền tối riêng, dùng nền trong suốt. Giữ texture dải chọn Cursor_Wide khi
hover/focus, vẫn dài bằng toàn khung. Mở rộng vùng hòa mép ảnh (16–18%) để tránh
ranh giới ảnh chữ nhật đậm hơn nền trang. Không thay màu chữ hay thao tác đăng nhập.

Prettier CSS, build TypeScript/Vite đạt. Browser fixture desktop/tablet/mobile
1440/768/360 px đạt kiểm tra không tràn, ảnh contain, kích thước hover bằng khung,
thông báo provider và vào chat. Đã xem screenshot desktop: nhóm nút hòa vào nền chung.
Chỉ sửa CSS đăng nhập và handover TV4, không thay backend/bot/sidebar hoặc xác thực.

## Bỏ dải tối lan vào giữa màn hình

Phản hồi tiếp theo xác nhận texture vẫn tạo các dải tối rộng ngoài vùng mép.
`login.css` đổi lớp phủ trang sang `mix-blend-mode: screen`, opacity 0.55,
bỏ mask tuyến tính 5% trên lớp phủ trang. Cách hòa này giữ ánh sương của texture
nhưng phần đen không tiếp tục đè tối nền và ảnh phía trong. Mask hòa mép ảnh riêng,
chữ, icon và dải hover giữ nguyên. Điều chỉnh này thay thế opacity 0.8/mask phủ trang
đã ghi trong các mục trước.

Prettier CSS và build đạt; browser fixture 1440/768/360 px đạt kiểm tra bố cục,
ảnh contain, không tràn, chiều ngang hover và điều hướng/notice provider.
Đã xem screenshot desktop. Không sửa phần của TV1/TV2/TV3 hoặc nối xác thực thật.

## Tiêu đề BẮT ĐẦU HÀNH TRÌNH

Theo yêu cầu mới, đổi heading LoginPage thành **BẮT ĐẦU HÀNH TRÌNH**, bỏ CSS ép
in hoa toàn trang và các nút. Mô tả và nhãn nút giữ nguyên chữ theo câu;
tên thương hiệu INDEX BEAST giữ nguyên. Không đổi bố cục, nền hoặc hành vi.
Kiểm tra Prettier hai file UI và TypeScript đạt.

## Rút gọn tiêu đề đăng nhập

Theo yêu cầu tiếp theo, bỏ dòng mô tả “Câu chuyện, nhân vật và những bí ẩn đang chờ bạn.”
và đổi heading từ BẮT ĐẦU HÀNH TRÌNH thành **KHÁM PHÁ ELDEN RING**.
Chỉ đổi nội dung LoginPage, giữ nguyên ảnh minh họa, các nút và chức năng.
Prettier và TypeScript đạt.

## Giảm độ sáng tổng thể theo phản hồi

`login.css` hạ các điểm màu nền xám nâu và giảm opacity lớp sương Screen từ 0.55
xuống 0.28. Ảnh minh họa dùng brightness 0.78, saturate 0.9; không áp filter lên
toàn trang để giữ nguyên độ rõ của chữ và các nút. Giữ cách hòa nền liên tục,
không thêm các hộp đen riêng. Phạm vi chỉ giao diện đăng nhập TV4.
Prettier và build đạt; kiểm tra browser 1440/768/360 px đạt bố cục, chiều ngang hover,
ảnh tải đúng tỷ lệ và thao tác provider/vào chat. Đã xem screenshot desktop sau chỉnh.

## Đổi tiêu đề thành LANG THANG ELDEN RING

Theo yêu cầu người dùng, chỉ đổi nội dung heading LoginPage từ KHÁM PHÁ ELDEN RING
thành **LANG THANG ELDEN RING**. Giữ nguyên kiểu chữ, bố cục, nền và các nút.
Kiểm tra định dạng LoginPage bằng Prettier đạt.

## Thu gọn cỡ tiêu đề

Theo phản hồi heading quá lớn và RING rơi riêng một dòng, `login.css` giảm cỡ desktop
từ tối đa 56 xuống 36 px, line-height 1.3, tracking 0.015em; mobile dùng clamp 22–28 px.
Thêm text-wrap balance để cân dòng khi không đủ chỗ. Giữ nguyên nội dung và phần khác.
Prettier, build và browser fixture 1440/768/360 px đạt; đã xem screenshot desktop,
tiêu đề nằm gọn trên một dòng ở 1440 px, không tràn ngang.

