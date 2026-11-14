# TV3 · Trợ lý chơi Elden Ring dùng nhiều nguồn

Ngày 14/11/2026 · Nhánh `fix/s4-tv3-progress-clarification`.

## Thay đổi

- Agent ưu tiên local trong Auto cho câu hỏi ổn định, tìm Tavily theo phần bằng chứng còn thiếu, và có thể tìm web trước với câu hỏi về patch hiện hành. Prompt đánh giá yêu cầu đúng mức chi tiết mà người chơi hỏi. Chỉ đường ưu tiên bước tiếp theo khả thi, nêu điều kiện mở khóa. Chiến thuật boss dựa trên bằng chứng cho các đòn, đợt đấu và hành vi cụ thể. [Agent](../../backend/app/rag/prompts/agent.md) · [Công cụ](../../backend/app/rag/prompts/tools.md) · [Kiểm bằng chứng](../../backend/app/rag/prompts/assess.md)
- Prompt cho phép kiến thức chung để đề xuất cách luyện tập hoặc đánh đổi định tính. Các bước quest, chỉ đường cụ thể, lore, patch và số liệu vẫn cần bằng chứng. Nếu Tavily gặp lỗi trong Auto và hết nguồn, gameplay đủ điều kiện có thể trả mẹo chung với trạng thái `grounded=false`. Hợp đồng quote, citation và calculator vẫn áp dụng. [Luồng công cụ](../../backend/app/rag/tool_agent.py) · [Prompt tư vấn](../../backend/app/rag/prompts/gameplay_advice.md)
- Web và Discord luôn cho phép spoiler. Schema nhận cả giá trị `false` của client cũ rồi chuẩn hóa thành `true`. Truy vấn dữ liệu trực tiếp vẫn có thể dùng metadata `spoiler_level`. [Tùy chọn chat](../../backend/app/api/schemas/chat.py)
- `benchmark_agent --max-cases` đếm câu hỏi chính. Runner giữ cùng hội thoại, gửi `clarification_id` qua JSON hoặc SSE, chỉ dùng câu trả lời chuẩn bị trước khi Agent thực sự hỏi. Thiếu câu bổ sung được ghi là `incomplete`. Chế độ test này bỏ giới hạn đếm công cụ và vòng làm rõ; timeout của từng request và kiểm truy vấn trùng vẫn áp dụng. `--max-turns` phục vụ manifest dạng cũ. [Runner](../../backend/scripts/benchmark_agent.py) · [Manifest mới](../../backend/eval/gameplay_multi_source_5.json)

## Kiểm thử và cách chạy

Full unit suite đạt 1.133 test. Sau thay đổi prompt sửa định dạng citation, chạy lại 123 test liên quan. Ruff, OpenAPI check và kiểm tra diff đạt. Unit test bao phủ tương thích spoiler với client cũ, lời khuyên gameplay khi web lỗi và việc nối câu hỏi phụ qua JSON/SSE. Năm câu hỏi chính được so trùng nguyên văn sau chuẩn hóa với golden set, manifest và kết quả thử đã lưu. [Unit test](../../backend/tests/unit/test_gameplay_multi_source.py)

### DeepSeek và Tavily Auto

5 câu chính có câu trả lời cuối qua 10 request chat. Runner ghi 54 lời gọi mô hình logic và 4 request Tavily. Qdrant báo 18.383 điểm corpus trước và sau. Kết quả ghi theo từng ca, bao gồm các lần sửa và chạy tiếp.

| Ca | Kết quả | Nguồn cuối |
| --- | --- | --- |
| PLAY-01 · Liurnia lên Altus | Chỉ đường qua Ruin-Strewn Precipice và nêu boss cần vượt. Đoạn về một lối khác còn mơ hồ và không cần thiết. | Local |
| PLAY-02 · Millicent | Lượt bổ sung đầu bị 502 vì Agent liệt kê từ “kim” như tên riêng. Sau sửa và mở lại cùng ca do checkpoint cũ chưa giữ token, runner gửi `clarification_id` qua SSE. IndexBeast chỉ rương ở Shaded Castle và chỗ giao cho Millicent. | Local |
| PLAY-03 · Valiant Gargoyles | Có đề xuất vị trí, cách thoát khỏi vùng độc và thời điểm phản công. | Local + web |
| PLAY-04 · Bell Bearing | Hai lần 502 do tên vật phẩm viết gọn ở Agent, sau đó do xung đột số trong ngoặc vuông ở generator. Bản cuối xác định Bell Bearing (2), vị trí và người nhận. | Local |
| PLAY-05 · Co-op Limgrave | Giải thích vai trò host/guest, vật phẩm đặt và hiện dấu, cách đặt Multiplayer Password. | Local + web |

Trace và lịch sử HTTP nằm tại `backend/data/research_runs/2026-11-14-gameplay-multi-source-5/report.json` trên máy chạy. Đây là chẩn đoán năm nhu cầu thực tế. Tư vấn khi cả local và Tavily không dùng được đã được kiểm offline. Lượt thật này đo bù bằng chứng web và tiếp tục câu hỏi phụ.

Từ `backend/`, có thể in kế hoạch trước khi chạy thật.

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/gameplay_multi_source_5.json --max-cases 5
```

Để tự chạy, thêm `--execute --allow-llm --allow-web --allow-embedding --output data/research_runs/gameplay-multi-source-run` với thư mục output mới. Runner cần PostgreSQL, Redis, Qdrant, cache encoder và key DeepSeek/Tavily đã cấu hình. Dùng tài nguyên hội thoại riêng, truy xuất collection corpus đang cấu hình.

Sau khi xử lý lỗi HTTP, dùng lại cùng manifest, ngân sách và thư mục output với `--resume --continue-cases`. Runner giữ lịch sử lần thử, chỉ tiếp tục ca lỗi. Nếu Agent hỏi thêm ngoài dữ kiện có sẵn trong manifest, kết quả sẽ ghi `incomplete` để xem lại hồ sơ thử.
