# TV4 — Dọn ảnh không sử dụng

Ngày: 14/11/2026 (Asia/Saigon). Nhánh: `feature/tv4-dang-nhap-google-discord`.

## Phạm vi và cách xác định

Người dùng yêu cầu bỏ ảnh/tài nguyên thừa không ảnh hưởng dự án. Chỉ dọn trong
`web/src/assets` và `web/item_`, không sửa backend, bot, dữ liệu hoặc pipeline.
Đối chiếu tên tệp với mã nguồn, test, HTML, CSS, SVG, cấu hình web và tài liệu
docs/planning/README. Kiểm tra không có cơ chế dựng đường dẫn/glob tải bộ ảnh bị xóa.
Chỉ xóa tệp đã được Git theo dõi, không xóa tệp untracked của người dùng.

Đã xóa 32 ảnh/texture không có tham chiếu, tổng 1.697.784 byte (khoảng 1,62 MiB).
Giữ tất cả ảnh có tham chiếu runtime hoặc tài liệu; giữ font, license, favicon,
icon, ảnh nền, fixture minh họa và cả hai video. Không coi ảnh chỉ được nhắc trong
handover là đang dùng trên giao diện, nhưng chưa xóa để tránh phá tham chiếu tài liệu.

## Danh sách đã xóa

Trong `web/src/assets/`:

- `8c48005c-368b-41d4-9c52-007f93479461.jpg`
- `elden-ring-1.jpg`
- `elden-ring-2.jpg`

Trong `web/item_/`:

- `MENU_FL_40167_Creed.png`
- `MENU_FL_Arts_waku2.png`
- `MENU_FL_Arts_waku3.png`
- `MENU_FL_Arts_waku4.png`
- `MENU_FL_BarDeco_Boss.png`
- `MENU_FL_BarEdge.png`
- `MENU_FL_BarEdge2.png`
- `MENU_FL_Cursor_Half.png`
- `MENU_FL_Dialog.png`
- `MENU_FL_Dialog_02.png`
- `MENU_FL_Enterbutton.png`
- `MENU_FL_HelpCursor.png`
- `MENU_FL_HP_Base.png`
- `MENU_FL_Rar_d0.png`
- `MENU_FL_Rar_d1.png`
- `MENU_FL_Rar_d2.png`
- `MENU_FL_scroll_Bar.png`
- `MENU_FL_Slider.png`
- `MENU_FL_SliderFuta.png`
- `MENU_FL_SliderMark.png`
- `MENU_FL_SliderPart.png`
- `MENU_FL_Tab_base.png`
- `MENU_FL_Tab_base2.png`
- `MENU_FL_Tuto_toast.png`
- `MENU_Gauge.png`
- `MENU_Gauge_Edge.png`
- `MENU_HP_Bar.png`
- `MENU_Loading_02.png`
- `MENU_TitleBase.png`

## Kiểm tra

- Build TypeScript/Vite trước và sau dọn: đạt.
- So sánh SHA256 toàn bộ tệp đầu ra production trước/sau: trùng hoàn toàn.
  Các ảnh bị xóa vốn không được đưa vào bundle, nên dung lượng bundle không giảm.
- `npm.cmd test`: 49/49 đạt. Có cảnh báo cổng WebSocket HMR 24678 từ các Vite test
  chạy đồng thời; không có test thất bại, không đổi cấu hình/cổng dự án để xử lý cảnh báo.
- Không gọi API/LLM thật. Không thay CSS, JSX hoặc hành vi giao diện trong lần dọn này.

Các tệp đã xóa có thể khôi phục bằng Git nếu sau này cần dùng làm thiết kế mới.
Không tự commit, push hoặc sửa lịch sử Git.
