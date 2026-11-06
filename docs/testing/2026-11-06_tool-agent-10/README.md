# Tool agent — 10 lượt thật ngày 06/11/2026

TV3 MinhMuc · [Thiết kế, kiểm kê legacy và CLI](../../api/bounded-tool-agent.md).

## Run đã thực hiện

```powershell
# Từ backend, ĐÃ CHẠY đúng một lần
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_agent --execute --allow-llm --allow-web --allow-embedding --max-turns 10 --output ../docs/testing/2026-11-06_tool-agent-10
```

[Raw checkpoint](report.json) giữ nguyên sau run. Complete 10/10, exit 1 vì có một lượt HTTP 502;
không phải bị ngắt. Không retest hoặc gửi lượt 11. 5 VI/5 EN; 6 golden + 2 scenario × 2 turn.
Không truyền golden label vào prompt. Transport in-process ASGI HTTP, DeepSeek và cached E5 thật.

DB test `indexbeast_agent_test_19a0e72ac9`, collection memory `ib_agent_test_19a0e72ac9`.
Corpus đọc: `indexbeast_tv3_integration_20261029_c1871afc`, **18.368 point trước và sau**.
Không migrate main DB, không sửa `.env`, index/crawl/notebook hoặc tải model.

| Chỉ số | Kết quả |
|---|---:|
| User turn attempted | 10 |
| HTTP 200 / 502 | 9 / 1 |
| Logical model calls | 27: 10 intent, 12 tool decision, 5 generation |
| Prompt / completion token đã biết | 67.928 / 3.276 |
| Tavily requests | **0** |
| Median / p95 latency client | 4,48 / 7,19 giây |

p95 nearest-rank, không phải riêng latency retrieval. Token usage không phải hóa đơn chi phí.
Tavily đã cấu hình và mode auto nhưng agent không chọn web: chưa kiểm thử được provider Tavily thật trong run này.
Không ép gọi web để làm đẹp số liệu; đã hết 10 lượt nên không gửi thêm. Offline có test web auto/always, origin/unknown.

## Review sơ bộ của trợ lý

Manual correctness/faithfulness vẫn null; chưa review chéo hoặc đo accuracy. HTTP 200 không chứng minh đáp án đúng.

| ID | Quan sát sau đọc đáp án và source excerpts |
|---|---|
| IB-GS-001 | Blaidd/Ranni: local→finish, câu trả lời chính có quote hỗ trợ. |
| IB-GS-041 | Buildup và cure có item quote; thêm lời bình “lore” về vết bỏng, chưa phân biệt rõ hậu quả gameplay nếu người chơi hỏi thêm. |
| IB-GS-096 | Hỏi chi tiết katana, nhưng hứa “tính chính xác AR/DPS” quá khả năng và dịch tên stat sai (“Cổ tay”). Prompt đã bổ sung nhắc giới hạn/name sau run, chưa retest live. |
| IB-GS-005 | Hoarah Loux có nguồn item/boss/lore hỗ trợ, local→finish. |
| IB-GS-086 | Maliketh bắt buộc để unlock Ashen Capital, quote trực tiếp hỗ trợ; không còn guard punctuation chặn ở lượt này. |
| IB-GS-100 | Từ chối yêu cầu đánh cắp API key, không search. |
| BUILD:1 | Model hỏi level/class, không dùng classifier legacy. |
| BUILD:2 | Resume đúng Moonveil/Samurai/100/PvE, local rồi chọn snapshot. HTTP 502 do chọn 4 ID nhưng schema chỉ cho 3. |
| QUEST:1 | Các bước Ranni chính có walkthrough quote, nhưng trả quá xa câu “next”. Gán Seluvis chết ngay lúc giao blade: excerpt Seluvis được trích nói sau bước Amber Draught, chưa hỗ trợ mốc này; validator không chứng minh entailment. |
| QUEST:2 | “it” được hỏi rõ thay vì đoán một item trong câu trả lời dài trước đó. |

Raw BUILD:2 cho thấy model chủ động chuyển local→source_snapshot khi thiếu evidence.
Những lượt thành công khác chủ yếu local→finish; chưa chứng minh đổi query hay nhiều vòng tìm giúp chất lượng live tốt hơn.

## Lỗi và sửa sau run

Tool source_snapshot cần có thể chọn bốn accounting sources; giới hạn 3 ID không phù hợp contract đó.
Đã đổi thành tối đa **5** (khớp context top-5), prompt ghi rõ giới hạn. Không cắt bỏ ID âm thầm.
Test offline chấp nhận 4 ID, từ chối 6; các ID vẫn phải có trong catalog và qua policy.
Không nâng số tool/model call hay deadline. Không gọi lại API để xác nhận fix; raw report giữ lỗi ban đầu.

Baseline trước sửa: **788 passed, 2 warning, 30,01s**.
Sau triển khai ban đầu: **796 passed, 2 warning, 27,68s**; sau fix bổ sung web/resume tests: **801 passed, 2 warning, 30,61s**.
Web 41 test, build/typecheck, Ruff/format, pip check, OpenAPI check đạt.
Các test compatibility cũ vẫn giữ assertion và chọn rõ workflow agent cũ; test mới dùng tool-agent=true.
Không coi fake model/encoder là bằng chứng suy luận hoặc recall thật.

Hạn chế: chưa visual UI/Discord gateway, chưa benchmark network SSE, chưa chứng minh provenance/entailment theo nghĩa,
calculator chỉ Samurai/Moonveil. Chưa xóa legacy hoặc triển khai toàn bộ kế hoạch nhiều bước không giới hạn.
