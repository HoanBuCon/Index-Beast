# TV2 Sprint 5 · Giới hạn lưu giữ

Ngày 16/11/2026. Nhánh `fix/s5-tv2-retention`, nền `c5635ec`. NFR-PRIV-01.

- Hội thoại khách web hết hạn được xác định từ tin nhắn mới nhất, hoặc thời điểm tạo nếu chưa có tin. CLI xoá hội thoại đã quá 90 ngày không hoạt động cùng tin nhắn, đánh giá, ký ức và vector. Hội thoại tài khoản và Discord vẫn giữ. Phiên đăng nhập hết hạn tiếp tục được dọn theo thời điểm hết hạn.
- Trace kỹ thuật `messages.rag_trace` và payload `ingestion_jobs.log` được xoá theo lô. Tuổi trace tính từ thời điểm tạo tin nhắn, tuổi log tính từ thời điểm job kết thúc. CLI ghi SQL NULL và bỏ qua cả SQL NULL lẫn JSON null. Trạng thái và số đếm của job được giữ.
- Mỗi lô hội thoại được khoá và kiểm lại trong cùng transaction PostgreSQL. Qdrant xoá trước PostgreSQL. Khi Qdrant lỗi, lô PostgreSQL có thể chạy lại. Hai kho có transaction độc lập, truy cập Qdrant trong transaction có thể kéo dài khoá.
- `--ingest-log-dir` xử lý file thường có tên `ingest-weekly-YYYYMMDD-HHMMSS.log` ngay trong thư mục cấu hình, dựa vào mtime. `--dry-run` chỉ đếm. Docker, journal, proxy, báo cáo và backup có chính sách vận hành riêng.
- [SRS](../02_SRS.md), [chính sách](../privacy.md) và trang About mô tả phạm vi. Định danh Discord tiếp tục dùng HMAC-SHA256 theo `auth.provider_hash`.

## Kiểm tra

- Backend unit suite offline đạt 1.272 test, 20 skip. Sau thay đổi cách đếm trace qua preview, chạy lại 14 test privacy và Ruff.
- Web typecheck, Prettier cho trang About và 71 bài test web đã qua.
- Các test integration PostgreSQL cho giữ lịch sử tài khoản/Discord, SQL NULL và dọn theo lô đã được thêm. Docker Engine local chưa kết nối được. Cần nghiệm thu trên staging và xác nhận rotation log hạ tầng trước khi lên lịch. Chưa thực thi retention trên dữ liệu đang phục vụ.

Xem trước từ `backend/` bằng `python -m scripts.retention --days 90 --dry-run`. Có thể thêm `--ingest-log-dir <thư mục>` trên host có log ingest.
