# TV3 · Nối lượt hỏi đường bằng mốc tiến độ

Ngày 14/11/2026 · Nhánh `fix/s4-tv3-progress-clarification`.

Người dùng hỏi “giờ đi đâu tiếp”, nhận câu hỏi bổ sung rồi trả lời “vừa xong tutorial”. HTTP 502 xảy ra tại `agent_decision`. Stack trace cũ thiếu mã từ chối cụ thể. Kiểm thử tái hiện điều kiện cũ yêu cầu có thực thể cho mọi truy vấn nối tiếp. [Meta-prompt](../prompts/2026-11-14_tv3-progress-clarification.md)

## Thay đổi

- Agent dùng yêu cầu gốc và câu hỏi trong `working_state.pending` để giải nghĩa câu trả lời. Validator nhận mốc `progress` có nguyên văn và nguồn xác thực cho route hoặc quest, kể cả khi `entities=[]`. Lượt bổ sung cần có câu hỏi đang chờ. Các câu đáp chung chung và tham chiếu chưa rõ vẫn cần làm rõ. [Validator](../../backend/app/rag/agent.py) · [Prompt quyết định](../../backend/app/rag/prompts/agent.md)
- `search_hypotheses` chứa tên dùng để truy xuất. Validator yêu cầu chúng xuất hiện trong truy vấn và ở ngoài trạng thái người chơi cùng câu hỏi đã giải nghĩa. Prompt hướng dẫn trả đường đi theo điều kiện nếu chưa biết vị trí chính xác. [Prompt công cụ](../../backend/app/rag/prompts/tools.md) · [Prompt trả lời](../../backend/app/rag/prompts/answer.md)
- Log `Agent decision rejected` ghi mã như `missing_followup_context`, `unverified_entity`, `invalid_decision_schema` hoặc `invalid_json`, kèm số lần thử sửa. Dùng request ID để đối chiếu với 502. Payload của người dùng và output thô của mô hình nằm ngoài log chẩn đoán này. [Kiểm thử hồi quy](../../backend/tests/unit/test_progress_clarification.py)

## Cách thử

Khởi động lại backend trên nhánh này. Trong chat mới, gửi `giờ đi đâu tiếp`. Khi IndexBeast hỏi tiến độ, nhập `vừa xong tutorial` ở khung phụ. Kỳ vọng Agent tìm hướng đi từ mốc tutorial và trả theo vị trí có thể xác nhận. Nếu gặp lại 502, tìm dòng `Agent decision rejected` theo cùng request ID.

1.103 unit test đạt, cùng hai cảnh báo từ Qdrant local và Alembic. Ruff và OpenAPI check đạt. Lượt kiểm thử dùng LLM và retriever giả, qua cả JSON và SSE, với hai cấu hình Agent có và không có vòng lặp công cụ. Kết quả của DeepSeek và Tavily trên câu này cần được xác nhận khi chạy thật.

## Sửa quyết định viết lại số và đơn vị

Trong sáu lượt thử thật, hai hội thoại chỉ đường qua SSE thành công. Ca Reduvia trả 502 vì hai quyết định đều đổi “tám chỉ số” thành “8 điểm”. Phát lại quyết định offline cho thấy mã `changed_numeric_constraints`.

Agent chịu trách nhiệm nhận ra ý nghĩa và đơn vị. Prompt yêu cầu giữ số viết bằng chữ ở dạng chữ khi dịch và phân biệt bảng thuộc tính với số điểm còn để cộng. Khi validator phát hiện sai chữ số, Agent nhận phản hồi có mã lý do để tự sửa. Nếu quyết định vẫn lỗi số, backend có thể dùng nguyên văn yêu cầu gốc và câu trả lời bổ sung của lượt đang chờ, sau khi kiểm lại các ràng buộc hiện có. Cách này giữ nguyên dữ kiện để tìm, kể cả khi mô hình chưa sửa được bản dịch.

Phần hỏi đường cũng bỏ danh sách từ dùng để nhận diện câu đáp chung chung. Agent xác định câu nói có chứa mốc tiến độ hay cần hỏi thêm. Backend kiểm mốc được trích từ câu người dùng hoặc dữ kiện hội thoại đã xác nhận, cùng trạng thái câu hỏi đang chờ. [Validator và phản hồi sửa](../../backend/app/rag/agent.py) · [Prompt Agent](../../backend/app/rag/prompts/agent.md) · [Test hồi quy](../../backend/tests/unit/test_progress_clarification.py)

Phát lại đúng hai quyết định Reduvia đã ghi nhận. Luồng mới tiếp tục với nguyên văn hai lượt thay cho HTTP 502 ở bước quyết định. Toàn bộ 1.107 unit test đạt, với hai cảnh báo cũ. Ruff và OpenAPI check đạt. Lần thử DeepSeek thật nêu trên diễn ra trước bản sửa số và đơn vị.
