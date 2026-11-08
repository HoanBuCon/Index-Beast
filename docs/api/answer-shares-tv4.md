# Bản chia sẻ một câu trả lời Discord · TV4

Bổ sung ngày 08/11/2026, được người dùng cho phép sửa phần backend giới hạn này. Không thay quyền GET history,
không đổi schema `/chat` hoặc SSE, không sửa pipeline RAG/ingestion hoặc tạo migration.

## Giao kèo

- `POST /api/v1/answer-shares`: chỉ chấp nhận `X-Service-Token` hợp lệ, cả ở chế độ mock.
  Body `{conversation_id: UUID, message_id: UUID}`. Server đọc câu trả lời assistant trong đúng hội thoại Discord,
  lấy câu hỏi user ngay trước đó cùng answer/sources/grounded; không nhận nội dung tự do từ người gọi để xuất bản.
- Trả 201 `{token, expires_at}`. Token ngẫu nhiên 32 byte, URL-safe 43 ký tự. Snapshot Redis có TTL 86.400 giây,
  khóa dùng SHA-256 của token. Snapshot tối đa 1 MB, answer tối đa 100.000 ký tự, nguồn tối đa 100; quá giới hạn thì không tạo link.
- `GET /api/v1/answer-shares` với `X-Answer-Share-Token` trả `{question, answer, sources, grounded, expires_at}`.
  Không trả ID hội thoại, token hội thoại, service token, trạng thái người chơi hoặc các lượt hỏi khác.
- Link web là `WEB_URL/answer#<token>`. Fragment không gửi tới máy chủ web; frontend truyền token qua header API,
  không path/query, không lưu localStorage. Web/API phải cùng origin qua proxy Vite hoặc Caddy hiện có.
- Ai có link đều có thể đọc bản chụp tới khi hết hạn. Đọc không gia hạn TTL. Redis bị xóa/evict có thể làm link mất sớm;
  dữ liệu JSON snapshot trong Redis không được mã hóa bởi tính năng này. Cache-Control no-store, Referrer-Policy no-referrer.
- 401 khi tạo không đúng service; 400 khi target không phải hội thoại Discord; 404 khi không có target/token không hợp lệ/hết hạn;
  503 khi Redis lỗi hoặc snapshot không thể tạo/đọc. Token chia sẻ không phải credential cho `/conversations` hoặc `/chat`.

## Tích hợp bot/web

Bot tạo link bằng request phụ tối đa 5 giây sau khi nhận câu trả lời. Lỗi link không được làm mất embed hoặc gọi lại LLM.
Footer báo link ai cũng đọc được trong 24 giờ; viewer chỉ đọc, dùng Markdown an toàn và khối nguồn hiện có.
`WEB_URL` phải là URL gốc HTTP(S) không credentials/query/fragment; khi không hợp lệ hoặc để trống, bot không tạo link.
Không tự gắn link giả về trang chủ. Không cần đăng ký lại command vì không thay định nghĩa slash command.

## Tài nguyên và kiểm tra

Redis hiện có là kho snapshot tạm; không thêm cổng/service/dependency. Không bảo đảm link sống qua mất dữ liệu Redis.
Xem [bàn giao TV4](../handover/2026-11-08_s3-tv4_nguon-va-link-xem-day-du.md) cho kết quả test và phạm vi được duyệt.
OpenAPI sinh bằng `.venv/Scripts/python.exe -m scripts.export_openapi` khi đứng ở `backend/`.
