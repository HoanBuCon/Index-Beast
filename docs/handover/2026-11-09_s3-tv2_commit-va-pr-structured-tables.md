# TV2 — Commit và PR pipeline bảng có cấu trúc

Ngày 09/11/2026. Người dùng yêu cầu commit trên nhánh mới rồi tạo PR.

- Nhánh công việc: `feature/s3-tv2-structured-tables-ingestion`.
- Base/đích PR: `origin/develop` / `develop`; đồng bộ develop trước push.
- Phạm vi: toàn bộ mã, test và tài liệu TV2 của audit dữ liệu, parser bảng,
  export facts/clean/chunk, kiểm chứng và công cụ quản lý artifact local đã làm.
- Không commit dữ liệu trong backend/data, ảnh, model cache, `.env` hoặc credential.
  Dữ liệu bàn giao vẫn chỉ có local; PR không tự cập nhật database/index production.
- Nhánh fix/s3-tv2-chat-luong-du-lieu cũ và stash có sẵn được giữ nguyên.

Kiểm nghiệm dữ liệu của lượt triển khai được ghi tại
[báo cáo release](../testing/2026-11-09_tv2-structured-release.md) và
[handover tái tạo](2026-11-09_s3-tv2_tai-tao-facts-clean-chunk-tu-raw.md).
Các dòng “chưa commit/push” trong tài liệu trước phản ánh thời điểm triển khai,
được thay thế bởi yêu cầu Git hiện tại. Kiểm lại test/lint sau đồng bộ develop;
kết quả và link PR sẽ được bổ sung khi đã chạy thực tế. Không tự merge.

Đã rebase lên develop tại `3697e79` (PR #87/#88/#89). Chỉ xung đột danh sách
docs/handover/README.md; đã giữ cả liên kết TV4 mới và liên kết TV2. Không sửa
mã của TV1/TV3/TV4. Kiểm lại sau rebase: 93 unit test dữ liệu đạt, 20 fixture cũ
skip; Ruff check và format cho cả 16 file Python của PR đạt, diff check đạt.
