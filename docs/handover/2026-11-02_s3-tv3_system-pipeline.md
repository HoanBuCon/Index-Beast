# Bàn giao sơ đồ pipeline hệ thống IndexBeast

- Ngày: 02/11/2026 · TV3 MinhMuc.
- Nhánh: `docs/s3-tv3-system-pipeline`; chưa commit/push hoặc tạo PR.
- Phạm vi: tài liệu theo yêu cầu vẽ pipeline hệ thống bằng Mermaid `graph TD`.

## Nội dung

Thêm [pipeline hệ thống](../indexbeast-system-pipeline.md), cập nhật theo yêu cầu thành hai phiên bản: A cho người dùng (chuẩn bị kho kiến thức → hỏi qua web/Discord → tìm nguồn → trả lời/thiếu bằng chứng); B cho người kỹ thuật (toàn hệ thống dữ liệu, ứng dụng, hạ tầng, đánh giá), kèm hai sơ đồ chi tiết RAG online và indexing. Tổng cộng bốn sơ đồ Mermaid `graph TD`. Đối chiếu `pipeline.py`, `services/chat.py`, `vector/store.py`, routes history/feedback, Makefile và handover TV1. Cập nhật liên kết tại README handover.

Ghi rõ ba mode, proxy LAN/Radmin, hội thoại RAM, Redis rate limit, rewrite VI–EN, overview, hybrid RRF, top-5, validation/recovery và ảnh theo nguồn. Phân biệt sửa cleaner với việc có artifact/index mới; chưa coi gameplay stats đã vào corpus.

Bản kỹ thuật phân biệt PostgreSQL ingestion với RAM live chat; feedback mới xác nhận request, chưa lưu bền. Admin/entities chưa hoàn chỉnh không được thể hiện như luồng đã hoạt động. Đánh giá chạy riêng không có nghĩa đã hoàn thành review/đo recall.

## Kiểm tra và giới hạn

Bổ sung tiếp mục A1 theo yêu cầu: một sơ đồ `graph TD` riêng theo lượt người dùng hỏi, từ tiếp nhận/history, chuẩn bị truy vấn, chọn top-5, generation/validation đến nguồn và ảnh. Giữ nguyên toàn bộ nội dung file pipeline trước lần bổ sung này, gồm cả tiêu đề người dùng đã chỉnh. Tổng số sơ đồ sau bổ sung là năm.

Kiểm tra UTF-8, liên kết local và `git diff --check`. Không chạy model, API, embedding/index hoặc sửa dữ liệu/cấu hình. Không chạy lại unit test vì chỉ thêm tài liệu. Chưa render bằng Mermaid engine; cần Markdown Preview hỗ trợ Mermaid hoặc GitHub để xem hình.
