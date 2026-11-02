# Căn trái và thẳng cột menu sidebar web

| | |
|---|---|
| Ngày | 02/11/2026 |
| Người thực hiện | TV1 (Hoanbucon), theo yêu cầu người dùng; giao diện thuộc TV4 |
| Nhánh | `fix/s3-tv1-can-trai-menu-sidebar` (từ `develop` tại `4fc69e4`) |

## Thay đổi

- `web/src/styles/sidebar-menu.css`: `.grace-menu__label` đổi `text-align` từ `center` sang `left`. Các mục "TRÒ CHUYỆN MỚI", "VỀ DỰ ÁN", "QUẢN TRỊ" giờ bắt đầu ngay sau icon thay vì căn giữa cột chữ. Không đổi icon, hiệu ứng hover/active hay chế độ thu gọn sidebar.
- Cùng file: cột icon từ 28 px lên 30 px (bằng nút logo), khoảng cách icon–chữ từ 8 px lên 10 px, ô icon 30 px; chế độ thu gọn cũng dùng cột 30 px. Kết quả: tâm icon menu thẳng tâm logo, chữ menu thẳng cột chữ "INDEX BEAST".

## Kiểm tra

- Đo trên web local, viewport 1280×800: tâm logo và tâm 3 icon đều ở x = 31 (mở và thu gọn sidebar); chữ "INDEX BEAST" và chữ 3 mục menu đều bắt đầu ở x = 56. Trước khi sửa: icon x = 30, chữ menu x = 52.
- `npm test`, `npm run build`, Prettier: đạt.
- Chưa xem trên màn hình điện thoại.
