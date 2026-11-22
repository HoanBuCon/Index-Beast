# TV3 · Cập nhật điều kiện khi người dùng đổi yêu cầu

Ngày 14/11/2026 · Nhánh `fix/s4-tv3-progress-clarification`.

Điều kiện cũ từng lọt vào truy vấn vì validator chỉ xác nhận giá trị có xuất hiện trong lời người dùng. Ví dụ, yêu cầu đổi sang level 70 có thể sinh truy vấn `level 70 or 90` khi level 90 còn trong câu gốc. [Meta-prompt](../prompts/2026-11-14_tv3-superseded-constraints.md)

## Thay đổi

- Agent quyết định điều kiện nào còn phù hợp, điều kiện nào đã thay hoặc bỏ, và khi nào cần hỏi lại. `superseded_constraints` mang giá trị cũ cùng nguồn. Người dùng có thể nhắc lại giá trị đó để so sánh hoặc xác nhận dùng lại. Backend kiểm nguồn và gửi lý do từ chối để Agent sửa quyết định. [Validator](../../backend/app/rag/agent.py) · [Prompt Agent](../../backend/app/rag/prompts/agent.md)
- Truy vấn công cụ và truy vấn tiếp theo của bước kiểm bằng chứng được kiểm với trạng thái đã cập nhật. Generator nhận hồ sơ hiện hành. Khi điều kiện đổi trong lúc có câu hỏi đang chờ, kế hoạch và bằng chứng đã lưu cần được đánh giá lại. [Pipeline](../../backend/app/rag/pipeline.py) · [Công cụ](../../backend/app/rag/tool_agent.py)
- PostgreSQL cập nhật trạng thái dữ kiện bị bỏ trong cùng giao dịch lưu lượt chat. Trạng thái `superseded` loại dữ kiện khỏi kết quả nhớ lại. Lời người dùng vẫn nằm trong lịch sử để đối chiếu. Dùng schema hiện có. [Kho ký ức](../../backend/app/services/memory_repository.py)

## Kiểm thử

- Bản cuối chạy toàn bộ unit suite với 1.122 test đạt, cùng hai cảnh báo từ Qdrant local và Alembic. Ruff, định dạng, OpenAPI check và `git diff --check` đạt. Hồi quy offline bao phủ level, class, vũ khí, PvE/PvP, patch, tiến độ, so sánh, phục hồi ký ức và luồng công cụ. [Test](../../backend/tests/unit/test_superseded_conditions.py)
- Bốn lượt thật dùng DeepSeek và Tavily Auto trong cùng một hội thoại. Harness dùng PostgreSQL và collection ký ức riêng. Corpus có 18.383 điểm trước và sau lượt chạy. Harness ghi 34 lời gọi mô hình logic và 17 request Tavily.

| Lượt | Kết quả bản thử thật | Quan sát |
| --- | --- | --- |
| SC01 · Bandit 90, Reduvia một tay, PvE | HTTP 200 · 44,36 giây | Câu trả lời dùng đúng hồ sơ khởi đầu. |
| SC02 · Giảm xuống level 70 | HTTP 200 · 44,13 giây | Agent thay level 90 thành 70, giữ Bandit, Reduvia một tay và PvE. Truy vấn và câu trả lời dùng level 70. |
| SC03 · Chuyển PvE sang PvP và đổi sang Great Knife | HTTP 502 · 4,11 giây | Agent xác định đúng hai giá trị bị thay, nhưng sau lần sửa đầu vẫn nhắc PvE và Reduvia trong `resolved_question`. Validator từ chối trước khi gọi công cụ. |
| SC04 · So sánh Great Knife PvP ở level 70 và 90 | HTTP 502 · 4,35 giây | Agent ghi trùng khóa `level` và trả `superseded_constraints` cho tác vụ mới. Schema từ chối ở bước quyết định. |

Sau lượt chạy, bổ sung chỉ dẫn bỏ các giá trị cũ khỏi từng trường và đưa hai mức so sánh vào câu hỏi cùng truy vấn. Phản hồi schema giải thích cách sửa khóa trùng. Cho phép Agent sửa thêm một lần nếu lỗi còn lại liên quan tới điều kiện, trong giới hạn thực thi hiện có. Hai ca hồi quy mô phỏng chuỗi quyết định bị từ chối, kiểm Agent nhận đúng lý do và luồng tiếp tục truy xuất sau khi mô hình giả trả quyết định đã sửa. Bốn lượt thật đã dùng hết mức thử của tác vụ. Báo cáo chi tiết lưu local tại `backend/data/research_runs/2026-11-14-superseded-conditions-live/report.json` trong thư mục được Git bỏ qua.

## Cách thử trên web

Khởi động lại backend. Trong cùng một hội thoại với chế độ `Auto`, hỏi build cho `Bandit level 90, Reduvia một tay, PvE`, rồi nhắn `Đổi sang level 70, các điều kiện khác giữ nguyên`. Kiểm tra câu trả lời và truy vấn chỉ dùng level 70. Sau đó yêu cầu `So sánh level 70 và 90` để kiểm tra hai giá trị cùng xuất hiện khi người dùng thực sự muốn so sánh.

Validator kiểm các bề mặt nhận dạng được. Các cách diễn đạt tương đương bằng ngôn ngữ tự nhiên vẫn phụ thuộc vào Agent diễn giải. Kết quả thử thật được chấm theo việc giữ đúng điều kiện hội thoại.
