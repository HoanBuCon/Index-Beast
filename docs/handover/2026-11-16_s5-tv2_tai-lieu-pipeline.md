# TV2 Sprint 5 · Tài liệu pipeline và backlog cập nhật hằng tuần

Ngày 16/11/2026. Thẻ 5.6 và FR-ING-07. Nhánh `docs/s5-tv2-data-pipeline` từ `develop`.

- [Pipeline dữ liệu](../data-pipeline.md) mô tả Crawl → Clean → Chunk → PostgreSQL → Qdrant, bao gồm lệnh CLI, cấu hình, chạy bù và các bước thêm nguồn.
- [SRS](../02_SRS.md) và [kiến trúc](../04_ARCHITECTURE.md) ghi nhận CLI thủ công. [Bàn giao ban đầu của FR-ING-07](2026-11-16_s5-tv2_cap-nhat-tang-dan.md) lưu chi tiết thiết kế.
- [Meta prompts](2026-11-16_s5-tv2_meta-prompts.md) ghi phạm vi của Luna, Terra và bước review sau triển khai.

## Backlog FR-ING-07

1. Khi tiếp tục trên staging, xác minh cùng một bản chụp corpus giữa PostgreSQL và Qdrant. Chọn checkpoint và collection staging tương ứng. Sau khi áp dụng bản sửa preview, thử bootstrap và lập kế hoạch bằng `--dry-run`.
2. Nghiệm thu một lượt nhỏ với `--max-pages` trên staging. Đối chiếu report, `ingestion_jobs`, revision sau cập nhật, dữ liệu của một trang bị xoá và số point còn lại khi số chunk giảm. Chạy lại để kiểm tra tính lặp lại và xác nhận checkpoint khi một lô lỗi.
3. Đo thời lượng và số request khi chạy theo mốc và khi quét toàn bộ. Xác minh đường dẫn mount của data và log, quyền của tài khoản chạy job, khoá chống chồng và vòng đời log trước khi đặt cron VPS vào giờ thấp điểm.

Lịch tuần được hoãn theo quyết định Sprint 5. Đã đối chiếu lệnh và tên cấu hình với repository, kiểm liên kết nội bộ của tài liệu mới, kiểm diff và chạy `bash -n scripts/ingest-weekly.sh`. Nghiệm thu bằng wiki.gg, PostgreSQL và Qdrant thật còn trong backlog.
