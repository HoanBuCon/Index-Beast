# TV4 · Khóa điều hướng sidebar khi đang trả lời

- Nhánh: `feature/s3-tv4-hoan-thien-web-bot`.
- Phạm vi: frontend TV4; không sửa backend, bot, planning hoặc mã thành viên khác.
- `web/src/pages/ChatPage.tsx`: truyền `stream.busy` cho Về dự án và Quản trị, giống Trò chuyện mới. Tự mở lại khi busy kết thúc, kể cả dừng hoặc lỗi.
- `web/src/components/layout/GraceMenuItem.tsx`: mục có đường dẫn khi disabled được render thành button disabled, không có liên kết điều hướng. Chặn click, bàn phím và mở tab mới; dùng lại CSS disabled hiện có để chữ/icon cùng mờ và không phát sáng hover. Khi enabled vẫn là NavLink như cũ. Giữ ghi chú cũ.
- `web/tests/sidebar.test.ts`: kiểm tra cả hai mục có button disabled thay cho liên kết khi busy và khôi phục href khi idle. Test dùng MemoryRouter cùng module với ứng dụng; không gọi API thật.
- Đã chạy: test sidebar 1/1 đạt, build (TypeScript + Vite) và format:check đạt; kiểm tra diff/UTF-8/liên kết bàn giao đạt. Chưa thử thao tác trực tiếp trên trình duyệt.
- Cách kiểm tra thủ công: gửi câu hỏi, quan sát cả ba mục sidebar cùng mờ và không bấm được; sau trả lời xong/dừng, Về dự án và Quản trị mở được như trước. Không thay thời điểm busy hoặc khóa lúc chỉ chờ người dùng bổ sung.
- Không gọi model/LLM, commit hoặc push. Không có thay đổi hợp đồng API cần phối hợp.
