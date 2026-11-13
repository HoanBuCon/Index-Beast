# TV3 · Agent thích ứng và lập kế hoạch

Ngày 13/11/2026 · Nhánh `feature/s4-tv3-adaptive-agent`.

## Thay đổi

- Bước quyết định tiếp tục để mô hình chọn intent, rewrite, tra tên và hỏi bổ sung. So tên chấp nhận khác biệt dấu phẩy và khoảng trắng. Với câu độc lập có tên hợp lệ trong câu gốc, Agent có thể dùng lại câu gốc nếu bản rewrite tiếp tục làm mất tên. Giữ các kiểm tra số, patch, phủ định và nguồn dữ kiện người dùng. [Quyết định](../../backend/app/rag/agent.py) · [Chuẩn hóa tên](../../backend/app/rag/rewrite.py)
- Agent có hành động `check_name` dùng một lượt truy xuất local. Backend so lỗi gõ với title và alias có trong ứng viên qua bộ lọc corpus. Chỉ thay khi có một tên phù hợp. Tên rút gọn chỉ đưa ra ứng viên để hỏi lại. Nguyên văn người dùng vẫn được giữ trong hội thoại. [Kiểm tra tên](../../backend/app/rag/entity_spelling.py) · [Vòng lặp công cụ](../../backend/app/rag/tool_agent.py)
- Agent có thể lập 2–4 mục tiêu cho câu phức hợp, đánh dấu phần đã có nguồn, mở lại mục tiêu và chọn bước kế tiếp trong ngân sách hiện có. Qua lượt hỏi bổ sung, trạng thái hội thoại giữ phần có nguồn trong giới hạn 64 KB và kiểm lại bộ lọc khi nạp. Khi hết bước, ưu tiên nguồn từ các mục đã hoàn thành và các lượt tìm bổ sung để generator trả phần có thể xác nhận. [Kế hoạch và bằng chứng](../../backend/app/rag/task_plan.py) · [Pipeline](../../backend/app/rag/pipeline.py)
- Với hội thoại đang tồn tại, RAM cũng có thể phát lại kết quả của cùng `turn_id` trong khi còn bản ghi, tương tự luồng PostgreSQL đã có. Web giữ khóa gửi đồng bộ trong hook hiện tại. Lượt mở hội thoại mới vẫn dùng khóa gửi phía web. [Chat service](../../backend/app/services/chat.py)

## Thử thật đã chạy

Chạy đúng 5 lượt JSON với DeepSeek và Tavily Auto trên collection `indexbeast_clean_20261108_76b39a01`. Runner dùng PostgreSQL và collection memory thử riêng. Corpus có 18.383 point trước và sau. Cả 5 lượt HTTP 200, 24 lượt gọi mô hình và 2 request Tavily. Kết quả này dùng bộ 5 ca chẩn đoán. [Manifest](../../backend/eval/adaptive_agent_5.json)

| Ca | Kết quả quan sát | Độ trễ |
| --- | --- | ---: |
| ADAPT-01 | Rewrite bỏ dấu phẩy vẫn qua. Trả lời Maliketh bắt buộc để mở Ashen Capital, có 3 nguồn. | 9,18 s |
| ADAPT-02 | Kho xác nhận `Mooonveil` là `Moonveil`. Tavily có trả ứng viên, câu cuối vẫn thiếu vị trí và không có trích dẫn. | 12,85 s |
| ADAPT-03 | Agent tự chọn Royal Capital cho tên rút gọn. Có 3 nguồn và còn thiếu bước làm rõ Ashen Capital. | 12,38 s |
| ADAPT-04 | Khung hỏi bổ sung yêu cầu class và level. Lượt này hỏi ngay từ bước quyết định và chưa thu thập bằng chứng cho mục lấy vũ khí. | 1,99 s |
| ADAPT-05 | Sau khi tạo lại service, Agent nối đúng hội thoại, lập hai mục và trả cách lấy Moonveil. Mục build còn mở vì hết lượt công cụ và thiếu dữ kiện đã kiểm cho calculator. | 20,01 s |

Sau thử thật, cập nhật prompt cho tên rút gọn và câu nhiều mục tiêu, bổ sung kiểm tra ứng viên trùng nghĩa, giữ đại diện từ các lượt tìm bổ sung trong context dự phòng và kiểm retry RAM. Các chỉnh sửa này được kiểm offline. Lượt thật đã dùng hết giới hạn năm câu. Kết quả gốc nằm tại `backend/data/research_runs/2026-11-13-adaptive-agent/report.json` ở máy chạy.

## Kiểm tra offline

Toàn bộ backend unit suite đạt **1.085 test**, có hai cảnh báo từ Qdrant local và Alembic. Ruff và OpenAPI check đạt. Các ca hồi quy dùng model và kết quả retrieval giả để kiểm chuẩn hóa tên, hỏi lại khi có nhiều ứng viên, giữ bằng chứng qua lượt bổ sung, kiểm lại spoiler, xử lý quyết định công cụ sai schema và phát lại lượt gửi trong RAM.

## Cập nhật runner thử thật

Trace `ADAPT-02` ghi nhận `rewrite=true`. Lần quyết định đầu tự thay thành `Moonveil` trước khi kiểm tên. Lần sửa giữ `Mooonveil` để kho xác nhận, rồi dùng câu đã chuẩn hóa `Where can the Moonveil be found in Elden Ring?`. Agent gọi Tavily với `Elden Ring Moonveil location where to find Gael Tunnel Magma Wyrm`. Ba ứng viên web được trả về và hai ứng viên vào context cuối. Agent dừng ở `step_budget` trước một lượt đánh giá tiếp.

Runner `benchmark_agent` dùng `--max-turns` để giới hạn câu hỏi. Trong tiến trình thử riêng, bỏ trần theo số bước công cụ, số truy vấn local và số lượt model. Agent có thể gọi Tavily lần nữa với truy vấn khác. Runner vẫn ghi số lượt gọi, giữ timeout, chống lặp thao tác và ghi kết quả từng câu. Khi đã có kết quả hoặc lỗi của một câu, runner tiếp tục các câu còn lại. Các cấu hình giới hạn API chạy thường ngày giữ theo môi trường của người chạy. Ca test offline kiểm 3 lượt tìm local, 2 lượt web và lựa chọn nguồn từ lượt web sau. [Runner](../../backend/scripts/diagnose_agent_memory.py) · [Kiểm thử](../../backend/tests/unit/test_adaptive_agent.py)

Sau cập nhật runner, 1.086 unit test đạt với hai cảnh báo cũ. Đợt năm câu ở trên chạy bằng phiên bản runner trước cập nhật.

## Auto kiểm độ bao phủ trước khi trả lời

Auto trên luồng Tool Agent, khi Tavily có cấu hình và người dùng cho phép spoiler, đánh giá các đoạn sẽ gửi cho generator khi planner chọn `finish` hoặc `stop`. Lượt đánh giá đọc câu gốc, câu đã giải nghĩa, các mục của kế hoạch và kết quả tính đã kiểm. Nếu còn thiếu dữ kiện, truy vấn Tavily theo phần thiếu, giữ nguồn đã hỗ trợ được một phần và đánh giá lại sau khi có kết quả. Danh sách đầy đủ cần nguồn xác nhận số lượng và các mục, hoặc một nguồn liệt kê toàn bộ.

Luồng này dùng thời gian xử lý của request, chống truy vấn trùng và ngừng mở rộng web khi hai truy vấn liên tiếp không đem lại đoạn mới. Câu đã đủ từ kho kết thúc với `local_sufficient`. Khi vẫn còn phần chưa xác nhận, generator dùng các dữ kiện đã kiểm và nêu cụ thể phần còn thiếu. `coverage_checks` trong trace ghi kết quả kiểm từng lượt. Hành vi `Off`, `Always` và chính sách spoiler đi theo cấu hình hiện có. [Vòng lặp Agent](../../backend/app/rag/tool_agent.py) · [Prompt đánh giá](../../backend/app/rag/prompts/assess.md) · [Test hồi quy](../../backend/tests/unit/test_adaptive_agent.py)

Backend unit suite đạt 1.088 test, nhóm 83 test Agent/web đạt khi kiểm lại, Ruff và OpenAPI check đạt. Các ca offline kiểm Auto vượt trần bước mặc định khi còn thiếu dữ kiện, giữ nguồn local khi có kết quả Tavily và kết thúc từ local khi đủ. Kết quả Auto/Always 10 lượt đã lưu trước thay đổi này. Có thể dùng lại manifest `backend/data/research_runs/2026-11-13-auto-always-manifest.json` với thư mục kết quả mới để kiểm so sánh thật.

## Cách thử lại

Từ `backend`, dùng thư mục đầu ra mới. Benchmark cần các dịch vụ Docker, corpus đã index, cache encoder và cấu hình DeepSeek/Tavily có hiệu lực. Lệnh `--execute` có phát sinh lượt gọi API. [Meta-prompt](../prompts/2026-11-13_tv3-adaptive-agent.md) · [Kiểm thử hồi quy](../../backend/tests/unit/test_adaptive_agent.py)

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/adaptive_agent_5.json --max-turns 5
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --manifest eval/adaptive_agent_5.json --max-turns 5 --execute --allow-llm --allow-web --allow-embedding --output data/research_runs/adaptive-agent-recheck
```
