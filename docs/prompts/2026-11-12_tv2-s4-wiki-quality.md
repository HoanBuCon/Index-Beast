# Meta prompts Sprint 4 · TV2

## Prompt 1 — Triage eval và sửa dữ liệu (Must)

Bạn là TV2 của Index-Beast. Đọc Sprint 4 trong planning, FR-ING-03/04, kiến trúc, ADR-003/004, quy ước và handover TV2. Xác định cohort từ crawl/clean report. Dùng báo cáo eval thật để phân loại từng lỗi có bằng chứng theo tầng dữ liệu, retrieval, hoặc generation/decision; ghi chưa đủ bằng chứng nếu cần. Truy ngược về raw cùng revision và so sánh chunk trước/sau. Nếu thông tin đã có, tìm lỗi phân đoạn cụ thể và kiểm thử, không thêm đáp án từ golden set vào corpus. Giữ raw, facts, ảnh và provenance. Đo lại bằng chứng trên tập đầy đủ và chạy lại phép đo retrieval local có thể tái lập. Bàn giao lỗi còn lại đúng thành viên.

## Prompt 2 — Gắn metadata và kiểm lại payload (Could)

Dùng revision raw để đối chiếu danh mục, khu vực, heading và nội dung. Chuẩn hoá Elden Ring base + Shadow of the Erdtree thành elden_ring, giữ release_scope là tín hiệu riêng. Gắn spoiler_level 0 (có căn cứ an toàn), 1 (tiến trình hoặc chưa chắc) hoặc 2 (ending/tình tiết cuối); mặc định 1. Gắn bằng chứng và phiên bản quy tắc, kiểm trên mẫu 50 trang cố định, gồm ca đầu/cuối game, DLC, hỗn hợp và thiếu bằng chứng. Kiểm payload bằng cùng chính sách admission của ứng dụng, trên collection cục bộ riêng. Ghi riêng số điểm có vector thật, kết quả lọc, kiểm tra không có vector và mọi phần eval còn thiếu. Giữ nguyên hệ thống đang phục vụ.
