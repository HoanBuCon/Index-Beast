# Hướng dẫn làm việc với IndexBeast

Áp dụng cho toàn bộ repository. Đọc [quy ước dự án](docs/quy_uoc.md), [quy ước bàn giao](docs/handover/README.md) và handover liên quan trước khi sửa phần tương ứng.

## Luôn bàn giao sau khi làm việc

Theo yêu cầu của người dùng ngày 26/10/2026, mỗi khi hoàn thành một nhóm tác vụ có thay đổi file, **phải tạo mới hoặc cập nhật handover trong `docs/handover/` trước khi báo hoàn tất**. Áp dụng cả mã nguồn, cấu hình, dữ liệu đánh giá, notebook, tài liệu và xử lý sự cố Git. Câu hỏi giải thích thuần túy không cần tạo file bàn giao.

- Handover nằm cùng nhánh và cùng commit/PR với thay đổi được bàn giao, khi tác vụ có commit/PR. Không để việc bàn giao thành lời hứa làm sau.
- Đặt tên theo `<YYYY-MM-DD>_s<sprint>-tv<thành-viên>_<chu-de-khong-dau>.md`; dùng ngày tại Asia/Saigon và chủ sở hữu tác vụ trong kế hoạch. Không tự nhận đóng góp thay thành viên.
- Khi thêm file, thêm liên kết vào danh sách trong `docs/handover/README.md`.
- Ghi phạm vi/tác vụ, file thay đổi, nhánh/PR nếu có, quyết định/quy ước, cách dùng, kiểm tra thực tế, sự cố/cách xử lý, hạn chế và việc còn lại.
- Phân biệt rõ việc đã chạy với hướng dẫn để người dùng tự chạy. Không ghi điểm đánh giá, kết quả test, review hoặc trạng thái merge chưa kiểm chứng.
- Không ghi secret hoặc giá trị thật từ `.env` vào handover.
- Trước khi kết thúc, kiểm tra liên kết local, mã hóa UTF-8 và tính khớp giữa handover với trạng thái repository; dẫn link handover trong câu trả lời cuối.

## Các ràng buộc đang áp dụng

- Phạm vi nội dung mặc định: lore **Elden Ring base game**; ngoại lệ Sprint 2 người dùng duyệt 29/10/2026 cho TV2 clean/chunk **base + Shadow of the Erdtree**, xem cập nhật trong [ADR-004](docs/adr/004-base-game-scope.md).
- Không tự chạy notebook, tải model, embedding/indexing hoặc gọi API LLM. Chỉ thực hiện khi người dùng yêu cầu rõ; nếu không, viết hướng dẫn để người dùng tự chạy. Có thể đọc output đã lưu và kiểm tra tĩnh JSON/lint/định dạng mà không thực thi cell.
- Không commit/push trực tiếp lên `main`, `master` hoặc `develop`; dùng nhánh riêng và Conventional Commits theo `docs/quy_uoc.md`. Không tự merge PR khi người dùng chưa yêu cầu.
- Khi tạo nhánh từ `origin/develop`, dùng `git switch --no-track -c <ten-nhanh> origin/develop` để không gán upstream của nhánh mới vào `develop`. Lần push đầu dùng `git push -u origin <ten-nhanh>` và xác minh upstream đúng nhánh công việc.
- Khi xử lý Git, giữ thay đổi của người dùng. Với commit đã push nhầm lên nhánh chung, ưu tiên revert qua nhánh/PR riêng; không tự reset hoặc force-push lịch sử nhánh chung.
