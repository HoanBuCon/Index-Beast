# TV2 — full crawl (chưa nghiệm thu toàn bộ)

## Cập nhật resume sau gián đoạn

Phát hiện report còn running nhưng không có tiến trình crawler. Checkpoint ghi nhận
1134 trang thành công, 2 excluded, 3 lỗi ảnh; inventory 4179 ứng viên. Chưa xác định
nguyên nhân tiến trình dừng. Không coi trạng thái running trong report là liveness.

Đã bổ sung OS file lock theo run directory; cache media chỉ dùng lại khi manifest
completed khớp ID/revision và mọi blob tải về khớp checksum. Checkpoint raw trước bước
media để retry ảnh không tải lại HTML. Khi resume giữ report cũ trong history, đối
chiếu external_id để kết thúc orphan job với termination_observed_at (không suy đoán
thời điểm tiến trình thực sự dừng). CLI chưa được chạy lại ở lượt này nên lịch sử và
trạng thái job DB hiện vẫn giữ nguyên.

Kiểm chứng mới: 153 unit tests passed, 13 integration tests deselected. Thêm integration
case recovery nhưng CHƯA chạy vì Docker/PG đang tắt. Log Docker Desktop mới báo thiếu
registry SOFTWARE/Docker Inc./Docker Desktop; đã hỏi người dùng đường dẫn bản cài đang
dùng. Không sửa Registry, cài lại Docker hoặc bỏ ghi ingestion_jobs để lách lỗi DB.

Sau khi Docker Engine sẵn sàng: bật postgres, chạy integration test_crawl_jobs.py,
rồi resume cùng run-id s2-full-20261028. Có thể chạy process detached với WindowStyle
Hidden, stdout/stderr và PID lưu dưới thư mục run; kiểm tra PID/report trước khi
khởi chạy để tránh trùng. Đây là hướng dẫn tiếp tục, chưa khởi chạy detached lần này.

## Cập nhật vận hành 28/10/2026

PostgreSQL đã hoạt động. Integration test mới test_crawl_jobs.py chạy trên database tạm
đạt: ghi trạng thái partial, bộ đếm thành công/lỗi, kết thúc job bị gián đoạn. Unit suite
nhánh crawl: 149 passed, 12 deselected. Không thay đổi schema hay mã TV1.

Đã khởi chạy thật `python -m ingest.crawl.full --run-id s2-full-20261028` có tải ảnh.
Job external_id: crawl-full-a6fd33301ba04b68b51b610095d4bc3b, đã ghi PostgreSQL.
Inventory/report/checkpoint ở backend/data/crawl_runs/s2-full-20261028.
Ở thời điểm kiểm tra: job running, đang discovery, chưa nghiệm thu full corpus.
Không chạy một crawler thứ hai vào cùng data directory. Chỉ resume cùng run-id khi
tiến trình cũ đã dừng. Những mục mô tả thiếu DB bên dưới là lịch sử trước cập nhật này.

Sau khi crawl completed: chuyển sang nhánh clean-chuan-hoa để clean --all với report
chỉ định rõ; sau đó dùng nhánh chunking-metadata để chunk và load đã kiểm chứng. Không
gộp nhánh, không đóng thẻ hoặc tạo nhánh mở rộng thứ tư trước nghiệm thu các bước này.

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
