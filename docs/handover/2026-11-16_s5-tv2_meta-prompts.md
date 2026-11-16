# Meta prompts Sprint 5 TV2

Đọc [quy ước](../quy_uoc.md), [SRS](../02_SRS.md), [kiến trúc](../04_ARCHITECTURE.md), [ADR phạm vi](../adr/004-base-game-scope.md), [pipeline](../data-pipeline.md), [chính sách riêng tư](../privacy.md), [sprint plan](../../planning/sprint_plan.json) và handover liên quan. Đối chiếu mã với `origin/develop` trước khi chỉnh. Scope TV2 gồm lỗi dữ liệu Tarnished Edition/Tarnished Pack có bằng chứng, pipeline thủ công, lưu giữ 90 ngày và tài liệu. Origins, Samurai và lịch cập nhật hằng tuần là các đầu việc riêng. Tái sử dụng API của các bước hiện có.

## GPT-6 Luna · FR-ING-07 và phạm vi wiki

Dùng `incremental-implementation` và `test-driven-development`. Từ raw và chunk local, tái hiện trang ngoài phạm vi bằng bằng chứng nguồn. Kiểm qua quy tắc chất lượng, đường dẫn chunk và validation. Giữ trang base/SotE có nhắc chéo. Dùng nguồn giả để kiểm category bị lỗi, revision và checkpoint để việc thiếu phản hồi không kéo theo xoá tài liệu. Ghi bước tái dựng khi đổi phiên bản pipeline. Giữ nguyên artifacts bàn giao.

## GPT-6.1 Terra · NFR-PRIV-01 và review ingest

Dùng `test-driven-development` để kiểm cửa sổ 90 ngày với hội thoại khách web, trace và log vận hành. Kiểm các trường hợp ngay ngưỡng, hội thoại đã gắn tài khoản, kênh Discord, phiên hết hạn và xóa tài khoản. Dùng `documentation-and-adrs` cho chính sách và trang About. Sau triển khai dùng `code-review-and-quality` để đọc diff ingest, kiểm ràng buộc đích, dry-run, tập candidate và phát lại sau lỗi. Dùng fixture và dịch vụ giả.

## Agent chính · Tích hợp và bàn giao

Dùng `documentation-and-adrs` để rà lệnh, đường dẫn, biến môi trường và các bước thêm nguồn. Đưa lịch cập nhật hằng tuần vào SRS và handover backlog. Dùng `code-review-and-quality` để kiểm đúng yêu cầu, khả năng đọc, phân lớp, rủi ro dữ liệu và chi phí theo kích thước corpus. Chạy test offline, ghi rõ phần cần staging. Dùng `git-workflow-and-versioning` và `pr` để mở ba PR riêng vào `develop`, yêu cầu mentor review.
