# TV1 Sprint 4 · Test CORS và giới hạn tần suất theo server Discord

Nhánh `fix/s4-tv1-cors-guild-limit` từ `develop`. Đóng hai điểm còn lệch giữa checklist Trello của TV1 và code.

## Đã làm

- **Test CORS** (`backend/tests/unit/test_cors.py`): trang web trong `CORS_ORIGINS` nhận `Access-Control-Allow-Origin`; trang lạ không nhận (preflight bị từ chối); phương thức ngoài GET/POST không được cấp. Không đổi code.
- **Giới hạn theo server Discord:** `/chat` nhận thêm `guild_id` tùy chọn (chuỗi số, tối đa 32 ký tự). Khi request có service token, ngoài hạn mức theo thread (`RATE_LIMIT_PER_MINUTE`, mặc định 10) còn có trần chung cả server (`RATE_LIMIT_GUILD_PER_MINUTE`, mặc định 30). Một server mở nhiều thread hoặc nhiều người dùng chung không vượt được ngân sách LLM. Request web không có service token thì `guild_id` bị bỏ qua, vẫn bị giới hạn theo IP.
- Gom ba đoạn đếm Redis lặp lại trong `guard.py` thành `_count`. Hành vi giữ nguyên (Redis lỗi thì 503).
- SRS 0.8.1 (FR-CHAT-04), `.env.example`, `docker-compose.yml`, `openapi.json` cập nhật.

## Việc cho TV4

Bot cần gửi `guild_id` (ID server từ sự kiện Discord, dạng số) trong body `POST /api/v1/chat`; chưa gửi thì chỉ có hạn mức theo thread như trước. Trường tùy chọn nên bot cũ vẫn chạy.

## Chưa làm

- Không có token riêng cho web (cố ý): bí mật nhúng trong trình duyệt công khai không bảo vệ được gì; web được bảo vệ bằng giới hạn IP, CORS và đăng nhập tùy chọn.
- Chưa có trần ngân sách toàn hệ thống (tổng số request/ngày bất kể nguồn). Với một bot công khai trên nhiều server nên cân nhắc ở Sprint 5.

## Kiểm chứng

1070 unit test đạt (thêm 3 ca guild, 3 ca CORS), ruff sạch, `export_openapi --check` đạt sau khi sinh lại.
