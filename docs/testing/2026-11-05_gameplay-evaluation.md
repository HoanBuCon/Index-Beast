# Golden 100, hỏi lại và HTTP gameplay diagnostic

05/11/2026 · TV3 MinhMuc · IndexBeast / 4 Hollows.

## Phạm vi đã thực hiện

Theo đính chính: thêm **40 câu vào 60 câu cũ**, không chạy toàn bộ 100 câu.
Triển khai state hỏi lại, nguồn bổ sung cho một số quest/route/weapon và kiểm tính khả thi build,
rồi test **25 prompt**, thêm 5 lượt OFF ghép cặp và 8 lượt retest các prompt đã phát hiện lỗi.
Tổng **38 HTTP chat requests**, không phải 38 câu độc lập; giữ cả kết quả lỗi hành vi trước sửa.
Không gọi LLM judge. Review bên dưới là AI-assisted provisional sau đọc answer/quote, chưa review chéo TV2.

Nhánh `feature/s3-tv3-gameplay-clarification`; chưa commit/push/PR. Thay đổi local của các tác vụ trước giữ nguyên.
Không sửa `.env` thật, corpus/artifact gốc, report ngày 04/11 hoặc index. Không chạy notebook/crawl/model download.
Query embedding dùng cache đã có, HF offline. Qdrant read-only, point count **18.368 → 18.368** trong cả ba lượt.

## Golden set

File [golden_set.jsonl](../../backend/eval/golden_set.jsonl) có đúng 100 record, bảy field theo contract.
60 record đầu giữ nguyên byte, SHA-256 prefix:
`85267b394c8af3bee7c55cc17e2b6738b1812e54f14197f703089cca7d570a35`.
40 câu mới là IB-GS-061–100; tổng **64 VI / 36 EN**, độ khó **33 easy / 44 medium / 23 hard**.
Category: character 10, event 6, location 10, multi_hop 8, mechanics 11, equipment 13,
quest 22, insufficient_evidence 7, out_of_scope 13. Giữ 10 SotE case cũ.

30 câu factual mới có quote/hash từ artifact; hai câu toán kiểm quy tắc trên
[Stats](https://eldenring.wikidot.com/stats); 8 câu behavioral có rubric thay vì bịa source URL.
Validator đối chiếu tổng 54 case có artifact evidence; không tự suy toàn bộ 100 đáp án đã được thẩm định.
Sidecar có **100 pending, 0 approved**. 10 [scenario nhiều lượt](../../backend/eval/gameplay_scenarios.json)
để riêng, ba scenario đầu được chọn chạy live. Đã dùng để phát triển nên không phải tập test độc lập cuối.

## Artifact từng lượt

| Lượt | HTTP hoàn tất | Kết quả vận hành | DeepSeek logical calls | Tavily requests |
|---|---:|---|---:|---:|
| [Lượt chính](2026-11-05_gameplay-api-25/report.json) | 30/30 | 25 grounded protocol, 4 clarification, 1 chặn injection; không lỗi HTTP/SSE | 69 | 8 |
| [Retest 061, 092 và GP-01](2026-11-05_gameplay-focused-fix/report.json) | 5/5 | 3 grounded, 2 clarification; build vẫn thiếu bảng số | 9 | 2 |
| [Xác nhận build sau giữ đủ rule](2026-11-05_gameplay-build-verify/report.json) | 3/3 | 2 clarification, 1 ví dụ allocation được server kiểm | 3 | 2 |
| Tổng | 38/38 | Không dừng giữa chừng hoặc bỏ case lỗi hành vi | **81** | **12** |

Mỗi thư mục có `review.md` gồm input, rubric, answer và quote thật; `ai_review.jsonl` có chấm sơ bộ
correctness/faithfulness 0–2, behavior_ok và nhận xét. Không sửa summary null thành điểm LLM judge.
Không gọi grounded/HTTP 200 là Accuracy. Case 092 lượt đầu HTTP 200 nhưng hỏi lại sai nhu cầu,
được giữ correctness=0/behavior_ok=false trong review.

Lượt chính có p50 **3.991,24 ms**, p95 **12.089,73 ms**, nearest-rank trên cả static/clarification/off/auto.
Không phải benchmark tải đồng thời. Các lượt có corpus/cache/config giống nhau; code/prompt thay giữa
lượt chính và retest là chủ đích, không trộn thành một controlled before/after benchmark toàn bộ tập.
Lượt đầu lưu hash golden/manifest/pack/prompts; lượt retest thêm hash module RAG/service.
Không có snapshot toàn bộ source code lúc lượt đầu ngoài trạng thái nhánh và mô tả thay đổi này.

Known token usage cộng ba lượt: **202.500 prompt / 13.342 completion**.
**4 SSE generation calls không có token usage** qua adapter hiện tại; không lấy 0 làm usage thật hoặc suy tiền hóa đơn.
Tavily là **6 Search + 6 Extract batch**, không retry. Budget thực tế thấp hơn giới hạn 800/300 được phép;
runner còn giới hạn riêng 150 logical calls/60 Tavily requests mỗi invocation. Không đổi model/thinking/temperature.

## Cấu hình và kiểm API thật

DeepSeek `deepseek-flash`, thinking **true**, temperature config 0.2, output max 4096.
Khi thinking bật, adapter không gửi temperature sampling như mode non-thinking; không suy sampling 0.2 đang áp dụng.
Rewrite/assessor vẫn non-thinking; recovery nếu có giữ policy hiện tại.
Model/cache/policy: multilingual-e5-small, `pilot`, EN, prefetch 30, top-5, context 12000 ký tự,
rewrite enabled/query mode rewrite, deadline request 45 giây. Không load model trong import.
SDK transport retry **0 chỉ trong tiến trình benchmark**, rate limit 1000 để không đánh nhầm quota demo thành chất lượng.
Không đổi cấu hình app hoặc `.env` thật.

Runner dựng API loopback riêng trên cổng override, không dừng API dev người dùng. Các request đi qua HTTP,
middleware, auth/rate-limit, dependency service và JSON/SSE thật; trace lấy từ service cùng tiến trình sau response.
Hai request SSE ở lượt chính nhận đủ status/token/sources/done. Một request channel=discord đi qua token auth
và backend auto; chưa test Discord gateway/bot thực trong server Discord. Server benchmark đã đóng sau mỗi lượt.

## Có phụ thuộc Tavily không?

Trong 25 prompt AUTO của lượt chính:

- **4/25 gọi web (16%)**, 16 lượt assessor ghi local_sufficient.
- 5 lượt không assessment: 3 hỏi lại cần thiết, 1 chặn injection và **1 hỏi lại thừa** (092).
- 4 search đều do local_partial, không có assessment_error trong lượt này.
- 5 lượt OFF ghép cặp đều trả lời được phần chính bằng local; không có Tavily request ở OFF.

Không thể dùng các tỷ lệ này như Accuracy hoặc tỷ lệ corpus có đáp án. Tập cũ ngày 04/11 có 24/25 search,
nhưng tập/cấu hình code và nguồn bổ sung khác nhau; không tuyên bố một phần trăm cải thiện nhân quả từ hai lượt.
Kết quả chứng minh hệ thống hiện tại **không luôn search web**, đồng thời vẫn có false gap:

| Case | Bằng chứng / nguyên nhân | Xử lý và trạng thái |
|---|---|---|
| 061 | Local note đã có sweep/overhead và short/mid-range. Assessor đòi góc và khoảng cách định lượng mà user không hỏi; OFF trả đủ | Siết missing theo đúng độ chi tiết được hỏi; retest trả local, 0 Tavily |
| 075 | Context local trước search thiếu location rương theo assessor; web bổ sung chest/điều kiện | Chưa kết luận corpus không có. Chọn context/relevance vẫn cần cải thiện; có snapshot local context ở runner mới |
| GP-01:3 | Có rule tính nhưng assessor đòi bài build/ví dụ sẵn; sau ghép web respec rule bị loại top-5 | Giữ đủ bốn accounting rule, dựa cả original+rewrite; đã trả bảng có kiểm. Assessor **vẫn tìm web** cho case này |
| GP-02:2 | Route Mistwood→Nokron cần chỉ dẫn cụ thể; web bổ sung route, local giữ điều kiện Radahn | Có ích trong lần đo này; không tuyên bố mọi route đều được web giải quyết |

Không ép assessment_error thành sufficient hoặc dùng một similarity threshold để giả đủ bằng chứng.
Không thêm search loop hoặc tăng K. Bước tương lai hợp lý cho build là đưa kết quả calculator có kiểm vào
assessment để tránh đòi một bài build có sẵn; chưa làm thành agent loop hoặc damage simulator trong lượt này.

## Hỏi lại, route và build đã kiểm

“Chia chỉ số Moonveil” → hỏi level/class → “100, Samurai” → hỏi mục tiêu → “PvE”.
Hai lượt hỏi không gọi LLM/Tavily; chủ thể và slot giữ đúng, kể cả unit test history=0.
Lượt đầu và retest đầu chưa có bảng tám chỉ số: đây là thiếu sót thật, không xóa khỏi report.
Nguyên nhân cuối là selection dựa rewrite “stat distribution” làm mất intent “chia chỉ số”;
bản cuối dùng cả câu gốc và rewrite, giữ đủ bốn rule trong top-5.

Ví dụ cuối từ DeepSeek qua SSE, server kiểm/render:

| Vigor | Mind | Endurance | Strength | Dexterity | Intelligence | Faith | Arcane |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 43 | 18 | 20 | 12 | 24 | 46 | 8 | 8 |

Tổng **179**, level **100**, đạt floor Samurai và yêu cầu Moonveil một tay.
`build_check.feasible=true`, **optimality_verified=false**; không phải benchmark AR/DPS hoặc phân bổ tối ưu PvE/PvP.
Chỉ rule Samurai/Moonveil được kiểm trong feature này; không suy mọi class/weapon đã có calculator.
Các nguồn trường dữ liệu: [Samurai](https://wiki.eso-ui.com/index.php/Elden_Ring:Samurai),
[Moonveil](https://eldenring.wiki.gg/wiki/Moonveil), [respec](https://eip.gg/elden-ring/guides/how-to-respec/).
Trang wiki.gg trả 403 khi open đầy đủ qua web tool; requirements đối chiếu qua kết quả indexed và nguồn ESO,
không tự tuyên bố đã fetch full page hoặc xác minh patch mới nhất.

Route “đi đâu tiếp?” hỏi location/objective; sau trả Mistwood/Nokron, đáp án giữ điều kiện Radahn thay vì đoán đã hạ.
Quest Ranni nhiều lượt giữ hướng Renna's Rise→Ainsel, phân biệt statue/Fia, optional dialogue và cảnh báo Seluvis.
Nguồn bổ sung chỉ gồm một số mốc/quest đã chọn, không phải mọi walkthrough và mọi trạng thái thế giới mở.

State hiện là RAM, TTL 30 phút, copy-on-write dưới lock; restart/eviction/multi-worker chưa có shared persistence.
Không biến câu hỏi thông tin về class thành xác nhận class người chơi. Tên và grammar nhận dạng còn giới hạn.
Xem [contract và demo](../api/gameplay-clarification-tv4.md).

## Nhận xét chất lượng còn lại

- 041 trả đúng cure effect nhưng gán đánh giá “rất hữu ích ở Lake of Rot” từ note Speckled Hardtear
  sang Flame, Cleanse Me: rủi ro mất chủ ngữ. Đã thêm quy tắc prompt chung, **chưa retest live riêng ca này**.
- GP-03:2 nói tới “quest của Pidia” trong khi quote chỉ ghi Pidia cũng chết; cách gọi quá rộng.
  Không coi quote tồn tại là entailment. TV2 cần kiểm lại wording/nhánh thực tế.
- 001/003/069 vẫn thêm chi tiết hơn câu hỏi; 063/build lặp một số disclaimer. Văn phong chưa hoàn toàn ổn định.
- Source snapshot/metadata pending/unknown không chứng nhận facts đúng game hoặc đúng patch.
- Corpus class/stat/progression còn khuyết; knowledge pack là hỗ trợ nhỏ có provenance, không thay toàn bộ dữ liệu.

## Kiểm thử offline và lệnh đã chạy

Baseline đầu tác vụ: **684 passed**, 1 warning, 22,37 giây.
Bản cuối: **709 passed**, 1 warning, **20,98 giây**; **25 regression mới** cho state/ID, history, cancel/error, isolation/concurrency,
expiry, arithmetic, policy/spoiler, context accounting và bảo toàn missing-key 503.
Ruff/format (205 file), OpenAPI check, pip check và validation golden đều đạt.
UTF-8 và 121 liên kết local/7 tài liệu đã kiểm; `git diff --check` đạt.
Hash corpus và report gốc không đổi; prefix golden/review cũ khớp byte với HEAD.
Frontend **37 test đạt**, typecheck/build đạt. Lượt `npm test` song song ban đầu treo ở Vite SSR searchToggle;
dừng đúng tiến trình test của tác vụ, chạy lại tuần tự với deadline và giữ nguyên assertion: đạt.

```powershell
# Từ backend — đã chạy
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --corpus data/chunk_runs/s2-full-v1/chunks.jsonl

# Runner mặc định chỉ đọc kế hoạch, không model/server
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_gameplay
```

Lệnh live đã chạy có `--execute --allow-llm --allow-web`, cổng riêng và ba output directory như bảng trên.
Không chạy lại chúng nếu chỉ muốn đọc kết quả. Muốn chạy một lượt mới, dùng **thư mục mới** và cổng dự án còn trống:

```powershell
# Chỉ hướng dẫn chạy lại, tốn API và query embedding
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_gameplay --execute --allow-llm --allow-web --port <CONG_DU_AN_RANH> --output ../docs/testing/NEW_gameplay-api-25
# Có thể chọn hẹp: thêm --only IB-GS-092 hoặc --only GP-01
```

Trong `web/`, đã chạy:

```powershell
node --test --test-concurrency=1 --test-timeout=30000 tests/*.test.ts
npm run build
```

Không collect integration ngoài unit. Qdrant memory warning chỉ nói payload indexes không được thực thi trong memory mode.
Không sửa SRS/ADR/planning/Trello: nhóm cần đồng bộ FR-EVAL-01, yêu cầu hội thoại/gameplay và ADR phạm vi/persistence
theo quyết định đã duyệt, cùng rule review riêng; không coi số lượng golden hoặc demo là Done toàn sprint.
