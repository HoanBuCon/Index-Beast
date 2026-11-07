# Cập nhật SRS và TechStack theo công nghệ, pipeline cuối Sprint 3

| | |
|---|---|
| Ngày | 08/11/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `docs/s3-tv1-cap-nhat-srs-techstack` (từ `develop` tại `cb2a358`) |
| Tài liệu | `docs/01_TECHSTACK.md` v1.5 → **v1.6**; `docs/02_SRS.md` 0.6.0 → **0.7.0**; bản Word `docs/export/01_TECHSTACK.docx`, `02_SRS.docx` xuất lại bằng `docs/export_docx.py` |

## Cách làm

Đọc mã trên `develop` (`cb2a358`) và handover từ 02/11 đến 07/11 của TV3, TV4, rồi đối chiếu từng dòng của hai tài liệu với mã (cấu hình mặc định trong `core/config.py`, `requirements.txt`, `docker-compose.yml`, schema API, model DB). Không chạy lại hệ thống; trạng thái dựa trên đọc mã và báo cáo của các thành viên. Các PR của TV1 chưa merge (#79 trace, #80 staging) được ghi rõ số PR ở từng chỗ nhắc tới.

## TechStack v1.6

- **Thêm:** LangGraph 1.2.20; Tavily Search + Extract thay DuckDuckGo; agent chọn tool có giới hạn; hội thoại và bộ nhớ ngữ nghĩa lưu PostgreSQL (migration `0002`, collection Qdrant `conversation_memories`); hỏi lại và kiến thức gameplay; kiểm chứng câu trả lời; trace và số đo; staging.
- **Sửa cho đúng thực tế:** reranker chưa bật (thay bằng bước đánh giá bằng chứng); câu "model ONNX tải sẵn vào `/models` lúc build" không đúng (Dockerfile chưa làm, `.dockerignore` loại `models`, compose gốc không mount); migration không tự chạy; `ddgs` còn trong requirements nhưng không còn được gọi.
- **Thêm mục số đo thực tế:** 25 câu golden p95 = 12,4 s (vượt mục tiêu 10 s), 74 lượt gọi LLM và 48 request Tavily; Recall@k, MRR, RAM/CPU trên VPS **chưa có**.
- **ADR:** 007 (DuckDuckGo) bị thay thế; thêm 008 (Tavily), 009 (LangGraph và agent), 010 (hội thoại PostgreSQL). Cả ba mới ghi trong bảng, chưa có file trong `docs/adr/`.

## SRS 0.7.0

- Phạm vi: base game + Shadow of the Erdtree, lore và gameplay/build. Theo §9 của SRS, đổi phạm vi là tăng MAJOR; giữ 0.x vì chưa release v1.0 (đã ghi trong changelog).
- Mọi yêu cầu FR có trạng thái thật thay cho "Proposed" hàng loạt; thêm cột trạng thái cho NFR. Đổi nội dung: FR-RET-03 (top-K 5), FR-RET-04 (đánh giá bằng chứng), FR-RET-08 (Tavily), FR-CHAT-02 (lịch sử liên quan), FR-GEN-06 (build không còn bị từ chối), FR-EVAL-01/05.
- §5 viết lại theo `openapi.json`; §6 thêm `conversation_runtime`, `conversation_memories`, hai collection Qdrant; phụ lục A đổi kịch bản 5 và 9, thêm 12–14.
- Thêm TBD-07..10 (bên dưới).

## Các điểm không khớp phát hiện khi đối chiếu (chưa sửa, cần chủ sở hữu quyết)

| # | Vấn đề | Chủ sở hữu | Ghi ở |
|---|---|---|---|
| 1 | Trang About còn ghi "Phạm vi hiện tại không gồm DLC hoặc Nightreign", trái phạm vi đã chốt | TV4 | TBD-08 |
| 2 | Nút 👍/👎 đã gỡ khỏi web (05/11) và `/feedback` chưa lưu dữ liệu; kịch bản demo 9 và FR-WEB-04, FR-BOT-05 treo | Cả nhóm | TBD-09 |
| 3 | Allowlist tìm web gồm Fextralife và Bandai Namco, chưa rà giấy phép/điều khoản | TV1 + nhóm | TBD-07 |
| 4 | Thẻ Sprint 3 yêu cầu "báo cáo Recall@k/MRR baseline": **chưa có**, vì golden set 100 câu chưa câu nào được TV2 duyệt | TV2, TV3 | TBD-10 |
| 5 | Reranker chưa bật, chưa có số đo | TV3 | TBD-02 |
| 6 | Bot: chưa chia nhiều tin, chưa có link "xem đầy đủ trên web" | TV4 | FR-BOT-03 |
| 7 | `docs/04_ARCHITECTURE.md` (2 chỗ) và `docs/03_SPRINT_PLAN.md` (2 chỗ) còn nhắc DuckDuckGo; `docs/adr/004-base-game-scope.md` còn nói base game | TV1 | chưa sửa |

## Giới hạn

- Trạng thái "Done" nghĩa là đã có mã và test tự động, không phải đã đạt chất lượng. Chưa có số đo chất lượng chính thức nào.
- Không cập nhật `04_ARCHITECTURE.md`, `03_SPRINT_PLAN.md`, ADR và tài liệu `docs/api/*` (ngoài yêu cầu).
- Các số p95/độ trễ lấy từ báo cáo của TV3 chạy trên máy phát triển, tuần tự; không phải đo tải.
- Bản Word được tạo bằng script có sẵn, chưa mở kiểm tra bằng Word.
