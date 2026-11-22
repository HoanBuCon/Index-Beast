# TV4 · Bỏ viền nút Web trong ô chat

- Nhánh: `feature/s3-tv4-hoan-thien-web-bot`.
- Phạm vi: giao diện frontend TV4, chỉ sửa `web/src/styles/refinement.css` và tài liệu bàn giao.
- Bỏ border của `.web-search-toggle` và khai báo border-color cho chế độ `always`. Tăng padding mỗi phía 1 px để giữ kích thước nút sau khi bỏ border.
- Giữ nguyên nhãn, màu chữ, thao tác chuyển chế độ tìm web và trạng thái disabled.
- Cách xem: mở web đang chạy, quan sát nút Web bên dưới ô nhập; chuyển chế độ để xem nút không còn viền hình hộp.
- Kiểm tra đã chạy: Prettier cho file CSS và `git diff --check` đều đạt. Chưa kiểm tra trực quan trên trình duyệt cho thay đổi này; không chạy test logic vì chỉ thay CSS.
- Không sửa backend, bot hay phần của thành viên khác; không gọi API/LLM, commit hoặc push. Không có thay đổi hợp đồng cần phối hợp.
