# TV3 — So sánh và hỏi bổ sung đúng lý do

Ngày 09/11/2026 · MinhMuc · Nhánh `fix/s3-tv3-clarification-comparison`.


## Thay đổi

- `backend/app/rag/prompts/agent.md`, `tools.md`, `assess.md`, `answer.md` hướng dẫn dùng intent `comparison` có sẵn. Planner tìm bằng chứng bổ sung cho từng lựa chọn và generator trình bày gợi ý theo tiêu chí thay cho xếp hạng tuyệt đối. Câu hỏi về lối chơi xuất hiện khi cần cá nhân hóa.
- `backend/app/rag/tool_agent.py` truyền intent vào bước chọn công cụ. `clarify` yêu cầu lý do `player_detail` và dùng payload `Clarification` hiện có. Lựa chọn `stop` với danh sách bằng chứng rỗng được giữ nguyên qua bước chọn context. Lỗi truy xuất toàn bộ khi không còn bằng chứng đi vào nhánh lỗi dịch vụ.
- `backend/app/rag/pipeline.py` trả thông báo thiếu thông tin khi context rỗng. Giới hạn ba lần hỏi bổ sung được giữ qua bước truy xuất của cùng yêu cầu đang chờ.
- `backend/app/rag/generator.py` đồng bộ prompt sửa JSON với cách hỏi bổ sung có cấu trúc. Lỗi định dạng vẫn qua cơ chế sửa hiện có và báo lỗi nếu không khôi phục được.
- `backend/tests/unit/test_tool_agent.py` kiểm so sánh có hai bằng chứng, từ chối dùng `clarify` vì thiếu nguồn, phân biệt lỗi truy xuất và bảo toàn giới hạn hỏi bổ sung.

## Kiểm tra và cách dùng

- 148 test tập trung và 995 test toàn bộ `backend/tests/unit` đạt. Mỗi lượt có 2 cảnh báo từ Qdrant local và Alembic. Ruff check và format cho nhóm file thay đổi đạt. OpenAPI `--check` đạt.
- Các ca so sánh dùng mô hình và nguồn giả lập để kiểm luồng xử lý. Chất lượng lựa chọn tiêu chí, nguồn và câu trả lời từ DeepSeek trên dữ liệu thật còn cần thử thực tế.
- Sau khi khởi động lại backend RAG với agent và tool agent, thử “class tốt nhất đầu game” để kiểm so sánh theo điều kiện. Thử tiếp một yêu cầu tư vấn cá nhân thiếu thông tin thiết yếu, rồi nhập câu trả lời tự do vào khung phụ nếu hệ thống hỏi.
- Repo đang ở nhánh làm việc local. Tác vụ thực hiện bằng kiểm thử offline, chưa commit hoặc push.


- `backend/app/rag/agent.py` và `prompts/agent.md` thêm `gameplay_comparison`. Intent `comparison` vẫn dành cho so sánh cần bám nguồn, bao gồm lore. Yêu cầu trộn lore/NPC/mô tả với gameplay được hướng về luồng cần bằng chứng.
- `backend/app/rag/pipeline.py` bật tư vấn cho lượt truy xuất có intent `mechanics`, `build` hoặc `gameplay_comparison`. Khi tắt spoiler, lượt trả lời vẫn đi qua luồng giới hạn theo nguồn để giữ bộ lọc spoiler.
- `backend/app/rag/prompts/gameplay_advice.md` cho phép đề xuất từ kiến thức chung và tính từ đầu vào, công thức đã xác định. Định dạng nội bộ `advisory=true` yêu cầu `evidence=[]`, không có trích dẫn hoặc bảng chia chỉ số. API trả lời bình thường với `grounded=false`. Khi có bằng chứng, mô hình có thể suy ra gợi ý theo tiêu chí và trích các dữ kiện làm đầu vào.
- Phạm vi lời khuyên và nguồn của phép tính được hướng dẫn bằng prompt. Backend kiểm tra intent, hình dạng kết quả và các ràng buộc trích dẫn. Bộ kiểm tra build hiện có kiểm bảng tám chỉ số. Các phép tính diễn giải khác do mô hình thực hiện.
- **1.003 unit test đạt** với 2 cảnh báo cũ. Ca mới kiểm tư vấn khi truy xuất rỗng qua cả JSON và SSE, chặn chế độ tư vấn đối với lore và khi tắt spoiler, cùng các ràng buộc trạng thái và trích dẫn. Ruff và OpenAPI check đạt.
- Manifest thử thật gồm 5 lượt tại `backend/eval/gameplay_advice_5.json`.

### Kết quả 5 lượt thật

Đã chạy qua API trong tiến trình thử nghiệm, dùng dữ liệu hiện có, DeepSeek thật và Tavily Auto cho câu chọn class. Bộ kiểm thử hoàn tất đúng 5 lượt. Qdrant corpus giữ 18.383 point trước và sau. Runner dùng database và collection memory thử riêng.

| Lượt | HTTP | Thời gian | Nhận xét |
|---|---:|---:|---|
| Marika là ai | 200 | 11,60 s | Có 5 nguồn trích dẫn. |
| Cha ruột của Marika | 200 | 5,08 s | Nêu chưa xác nhận được và không đoán tên. Phần nói thêm về lore không có trích dẫn nên câu trả lời chưa đủ gọn. |
| Tập né hay đỡ đòn | 200 | 10,75 s | SSE hoàn tất, đưa cách tập dựa trên 3 nguồn. |
| Class tốt nhất đầu game | 200 | 16,42 s | Có gợi ý Samurai và Vagabond, nhưng hai đoạn nói về vũ khí nhặt sớm thay cho hồ sơ class. Bộ kiểm tra loại một đoạn thiếu citation. |
| Level 40 lên 55, mỗi cấp thêm một điểm | 200 | 7,54 s | Tính đúng 15 điểm theo giả định của người chơi. |

25 lượt gọi mô hình logic và 2 request Tavily. Các kết quả này là chẩn đoán từng tình huống. Cả năm lượt đều dùng đường trả lời đã có nguồn hoặc báo khoảng trống. Đường `advisory=true` đã được kiểm offline khi truy xuất rỗng.

Sau lượt thật, thêm `recommendation` để server nối gợi ý có điều kiện sau dữ kiện đã trích. Trường này chỉ áp dụng cho intent gameplay phù hợp và cần phần dữ kiện hợp lệ. Tinh chỉnh tìm kiếm để ưu tiên hồ sơ và bảng class, đồng thời rút câu trả lời khi lore thiếu nguồn về một câu nêu chi tiết còn thiếu. Đã kiểm `recommendation` qua JSON/SSE với nguồn và mô hình giả lập. Toàn bộ backend unit đạt **1.004 test**, Ruff check, Ruff format check và OpenAPI check đạt. Lượt thật ở bảng trên diễn ra trước các thay đổi này.

[Kết quả gốc của 5 lượt](../testing/2026-11-09_gameplay-advice-5/report.json).
