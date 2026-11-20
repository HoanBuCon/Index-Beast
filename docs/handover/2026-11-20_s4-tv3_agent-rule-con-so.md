# TV3 · Chuyển rule con số cho Agent

Ngày 20/11/2026 · Nhánh `fix/s4-tv3-agent-rule-con-so` (tách từ `origin/develop` tại `bcbbf4c`, đã gồm PR #123 gỡ `llm_only`, xem [handover](2026-11-20_s4-tv3_go-llm-only.md)). Chưa push, chưa có PR.

## Vấn đề

Server kiểm quyết định của Agent bằng rule viết cứng:

- `preserves_numbers(question, query)` bắt **mọi chữ số** trong câu người dùng phải có trong query. Câu "chia 8 chỉ số" bị chặn khi Agent bỏ số 8 (không cần cho tìm kiếm), dẫn tới sửa lại nhiều lượt hoặc rơi về câu gốc.
- `_CONDITION_UNITS` (level/lv/cấp, patch/version/phiên bản/bản vá) và danh sách từ nối `or/and/hoặc/và` dùng để phát hiện giá trị cũ còn trong query. Chỉ đúng với vài ngôn ngữ và cách viết.
- `contains_entity` nhận dạng "Smithing Stone [3] và [4]" bằng cùng danh sách từ nối.

## Quyết định

Agent quyết định số nào là ràng buộc; server chỉ kiểm provenance (nguồn gốc) của những số Agent tự viết ra. Không dùng bảng từ khóa theo ngôn ngữ.

## Thay đổi

- `backend/app/rag/matching.py`: thêm `numbers_in()` (tách số như được viết, không suy đơn vị); `preserves_numbers` dùng lại hàm này.
- `backend/app/rag/agent.py`:
  - Bỏ `_CONDITION_UNITS`, regex từ nối và việc xóa số cũ khỏi câu hỏi (`numeric_question`).
  - Bỏ rule "mọi số của câu hỏi phải có trong query". Agent được bỏ số không cần.
  - Mọi số trong `resolved_question`/`search_query` phải có trong lời người dùng (câu hiện tại, `request_text`, memory đã chọn, constraints). Sai thì lý do `unsupported_number` (trước đây `changed_numeric_constraints`), vẫn được sửa một lượt và giữ fallback câu gốc như cũ.
  - `contains_superseded(text, inactive, comparison, active)`: giá trị cũ dạng số bị coi là còn sót khi số đó xuất hiện mà Agent **không** đánh dấu lại trong constraints hiện tại và không phải phương án so sánh. Giá trị dạng tên vẫn so khớp theo bề mặt như trước.
  - `contains_entity`: các bậc `[n]` nối bằng một chuỗi ngắn bất kỳ (tối đa 8 ký tự, không xuống dòng), không cần danh sách từ.
- `backend/app/rag/tool_agent.py`: hai chỗ gọi `contains_superseded` truyền giá trị profile hiện tại làm số đang hiệu lực.
- `backend/app/rag/prompts/agent.md`: Agent tự chọn số nào giữ trong query, được bỏ số đếm như "chia 8 chỉ số", không được tính/bịa số, ghi số là điều kiện vào constraints; nếu số trùng giá trị cũ nhưng vẫn là điều kiện hiện tại (attack power 90 sau khi đổi level 90) thì phải ghi vào constraints.

## Đánh đổi

- Không còn bảng đơn vị, server không phân biệt "attack power 90" với "level 90" cũ. Agent phải đánh dấu `attack_power: 90`; nếu quên sẽ tốn một lượt sửa.
- Agent có thể bỏ một số quan trọng khỏi query; server không chặn nữa. `player_profile` (constraints) vẫn đi tới Tool Agent và generator.

## Kiểm tra đã chạy (offline)

- `backend\.venv\Scripts\python.exe -m pytest -q`: **1.158 passed, 20 skipped**.
- `ruff check .`, `ruff format --check .`: đạt. `pre-commit run --files` cho các file thay đổi: đạt.
- Test mới trong `test_superseded_conditions.py`: câu "chia 8 chỉ số" qua được khi query bỏ 8 hoặc bỏ cả level; số không có nguồn (level 150, 80 Vigor) bị chặn; giá trị cũ viết kiểu "hoặc 90", "/ lv. 90", "o 90" vẫn bị bắt; "attack power 90" cần constraint. Test mới trong `test_gameplay_multi_source.py`: bậc nối bằng "or", dấu phẩy, "y".
- Test cũ đổi theo hợp đồng mới: tên lý do `unsupported_number`; ca "attack power 90" không có constraint giờ bị chặn.
- **Chưa chạy thật** với DeepSeek. Hành vi Agent theo prompt mới là giả thuyết.

## Còn lại

- Chạy câu thật mới (khi có ngân sách), ví dụ "Build Strength to cho PvE ở level 125, chia 8 chỉ số giúp mình." để xem Agent không còn bị sửa nhiều lượt.
- Các mục rà soát khác: timeout/ngân sách khi web `auto`, sửa chính tả tên do server tự đoán, fallback do server tự chọn bằng chứng.
