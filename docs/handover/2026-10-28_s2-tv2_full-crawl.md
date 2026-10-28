# TV2 — full crawl (chưa nghiệm thu toàn bộ)

Nhánh: feature/s2-tv2-crawl-toan-bo-wikigg, từ origin/develop 02c4abf.

Thêm ingest/crawl/full.py: inventory category đệ quy chống cycle, resume category/document,
snapshot theo revision/hash, report và ingestion_jobs qua repository hiện có.
Media dùng manifest riêng để giữ manifest mẫu S1. Raw mẫu cũ không bị ghi đè.

Lệnh dự kiến từ backend: `.venv/Scripts/python.exe -m ingest.crawl.full --run-id s2-full`.
Chạy lại cùng run-id để resume; không chạy đồng thời cùng thư mục dữ liệu.
Không áp dụng bộ loại trang S1 cho toàn corpus; scope được xét ở bước clean.

Kiểm chứng: 2 test mới passed (category cycle, cache/revision, giữ snapshot, lỗi discovery).
Bộ 147 test trước thay đổi passed; chưa chạy lại toàn bộ sau bổ sung hai test.
Một request wiki.gg thực tế thành công. PostgreSQL từ chối kết nối; docker/pg_ctl/psql
không tìm thấy trên PATH. Chưa chạy crawl toàn bộ, chưa nghiệm thu DB hoặc đóng thẻ.

Hạn chế: chưa có khóa đa tiến trình; inventory được cố định theo run-id, muốn khám phá
lại dùng run-id mới. Metadata revision timestamp còn thiếu. Độ phủ category cần review.
