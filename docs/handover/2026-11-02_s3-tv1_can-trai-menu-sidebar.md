# Căn trái chữ menu sidebar web

| | |
|---|---|
| Ngày | 02/11/2026 |
| Người thực hiện | TV1 (Hoanbucon), theo yêu cầu người dùng; giao diện thuộc TV4 |
| Nhánh | `fix/s3-tv1-can-trai-menu-sidebar` (từ `develop` tại `4fc69e4`) |

## Thay đổi

- `web/src/styles/sidebar-menu.css`: `.grace-menu__label` đổi `text-align` từ `center` sang `left`. Các mục "TRÒ CHUYỆN MỚI", "VỀ DỰ ÁN", "QUẢN TRỊ" giờ bắt đầu ngay sau icon thay vì căn giữa cột chữ. Không đổi icon, hiệu ứng hover/active hay chế độ thu gọn sidebar.

## Kiểm tra

- Mở web local (`make web`): cả 3 nhãn có `text-align: left`, chữ bắt đầu cùng vị trí (cách mép menu 36 px, ngay sau icon 28 px + khoảng cách 8 px).
- `npm test`, `npm run build`, Prettier: đạt.
- Chưa xem trên màn hình điện thoại.
