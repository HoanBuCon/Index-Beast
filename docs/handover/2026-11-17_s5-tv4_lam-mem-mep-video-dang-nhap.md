# TV4 · Làm mềm mép video đăng nhập

Ngày 17/11/2026. Nhánh `fix/tv4-giao-dien-dang-nhap`.

## Yêu cầu và phạm vi

Cho mép trên/dưới video hòa vào nền giống mép bên đang có. Chỉ sửa CSS frontend TV4;
không đổi bố cục, nút đăng nhập, OAuth, bot, backend, planning, README gốc hoặc tệp video.
Đã đối chiếu kế hoạch TV4, AGENTS, quy ước và bàn giao giao diện đăng nhập trước đó.

## Nguyên nhân và sửa đổi

`web/src/styles/login.css`: chuyển mask gradient hai chiều từ `.login-visual` sang phần tử
video/ảnh bên trong. Khung figure bị kéo cao theo hàng grid (764 px ở viewport 1440×900),
trong khi video chỉ cao khoảng 425 px, nên vùng fade trên figure không chạm mép video.
Đặt mask vào đúng media giữ bốn mép mờ đều, kể cả ảnh dự phòng khi video lỗi.
Giữ filter độ sáng, tỷ lệ contain, kích thước, loop/muted và điều khiển hiện tại. Giữ các ghi chú cũ.

## Kiểm tra thực tế

- Trình duyệt headless riêng qua CDP của Taste skill, fixture Vite tại 127.0.0.1:15174 chặn `/api`:
  đã xem ảnh trước/sau ở 1440, 768 và 360 px; không gọi API thật/LLM hoặc dùng phiên đăng nhập cá nhân.
- Xác nhận mask trên video, figure không còn mask; tỷ lệ 16:9 đúng, không tràn ngang,
  muted/loop bật và controls tắt; ảnh dự phòng cũng có mask khi phát sinh lỗi video.
- Script/screenshot thử nằm trong `web/.taste-skill/` đã được Git bỏ qua, không thêm dependency.
  Lượt đầu kiểm thử gặp ECONNRESET khi đóng browser; bổ sung xử lý đúng socket đóng và chạy lại đạt.
- `npm.cmd run build`: đạt. `npm.cmd run format:check`: đạt. `git diff --check`: đạt.

## Xem lại

Trang đăng nhập `/` hoặc `/login` ở web dev đang chạy; tải lại trang để nhận CSS mới.
Chỉ nghiệm thu giao diện mép media, không thử lại OAuth hoặc thay đổi logic đăng nhập.
Không tự commit/push/merge. Chưa kiểm tra trực tiếp Safari; đã kiểm trên Chromium của máy.

## Thu hẹp vùng mờ theo phản hồi

Người dùng nhận xét fade chiếm quá nhiều cả chiều ngang và chiều cao. Đã giảm từ 18% hai mép ngang
và 16–18% hai mép dọc xuống **6% mỗi mép**; vùng trung tâm 88% mỗi chiều giữ nguyên độ rõ.
Không đổi kích thước video hoặc tăng độ sáng. Chạy lại browser fixture 1440/768/360 px đạt,
ảnh dự phòng cũng giữ mask, không tràn ngang và tỷ lệ không đổi; đã xem screenshot desktop sau sửa.
Build và kiểm tra định dạng sau lần thu hẹp đều đạt.

## Nhãn nút trở về trang chủ

Theo phản hồi tiếp theo, đổi nhãn nút cuối `web/src/pages/AboutPage.tsx` từ “Trở về tra cứu ↗”
thành “Về trang chủ ↗” cho khớp đích `/` (màn giới thiệu/đăng nhập). Chỉ đổi chữ, giữ nguyên liên kết.

Người dùng sau đó chọn nhãn **“Xem trailer ↗”** thay cho “Về trang chủ ↗”. Đã cập nhật đúng nhãn này,
giữ liên kết tới `/`, nơi có video trailer. Kiểm tra định dạng file và `git diff --check` đạt.
