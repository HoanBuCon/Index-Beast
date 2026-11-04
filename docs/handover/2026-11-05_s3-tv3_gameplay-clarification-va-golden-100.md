# TV3 — Golden 100, hỏi lại và test gameplay thật

05/11/2026 · MinhMuc · IndexBeast / 4 Hollows.

## Phạm vi và trạng thái

Theo đính chính của người dùng: thêm **40** vào 60 câu để đủ 100, không chạy cả 100.
Triển khai trước, rồi test 25 prompt bằng API DeepSeek/Tavily thật, thêm OFF ghép cặp và retest lỗi liên quan.
Nhánh `feature/s3-tv3-gameplay-clarification` tách từ nhánh local đang làm `fix/s3-tv3-rag-evidence-guards`
tại HEAD dfc0286, giữ các modified/untracked của tác vụ diagnostic/guard trước đó.
Không stash/reset/fetch-rebase, commit/push/merge hoặc Trello Done; chưa có PR.

Không sửa `.env` thật, corpus gốc, report baseline ngày 04/11. Không crawl/notebook/download model hoặc index/upsert.
Query embedding cache và Qdrant read-only được người dùng cho phép trong tác vụ này.
API benchmark loopback riêng đã đóng sau mỗi lượt; API dev đang chạy của người dùng không bị dừng.

## File và quyết định chính

| Nhóm | File |
|---|---|
| Golden append 40, review pending | `backend/eval/golden_set.jsonl`, `reviews/s2-golden-set-review.jsonl`, `scripts/extend_golden_s3.py` |
| Manifest 25 prompt, 10 scenario | `backend/eval/gameplay_diagnostic_25.json`, `gameplay_scenarios.json` |
| State hỏi lại, commit dưới lock | `backend/app/services/gameplay.py`, `chat.py`, `factory.py` |
| API additive | `backend/app/api/schemas/chat.py`, `conversation.py`, `routes/chat.py`, `docs/api/openapi.json` |
| Nguồn nhỏ và chọn context | `backend/app/rag/gameplay_knowledge.py`, `knowledge/gameplay.json`, `context_policy.py`, `pipeline.py`, `scripts/prepare_gameplay_pack.py` |
| Tính khả thi allocation | `backend/app/rag/build_math.py`, `generator.py`, prompts answer/persona/assess, guard rewrite |
| Cấu hình | `backend/core/config.py`, `.env.example`; không sửa `.env` thật |
| Web tối thiểu cho TV4 | types/client/chat adapter, useChatStream, ClarificationForm, MessageList, ChatPage, test clarification |
| Kiểm thử | `backend/tests/unit/test_gameplay_state.py`, golden diagnostic test, `scripts/diagnose_gameplay.py` |
| Hướng dẫn/kết quả | README RAG/eval, contract TV4, ba report HTTP và review, analysis này và handover index |

100 câu: **64 VI / 36 EN**, easy/medium/hard **33/44/23**; toàn bộ **pending review**, không giả TV2 approval.
60 record đầu giữ nguyên byte; 54 case có quote/hash artifact đối chiếu; hai case toán mới kiểm trang Stats.
Đây là development set sau dùng chỉnh hệ thống, không phải test độc lập cuối.

## Contract/cách demo

Restart `make dev`, `make web`; không cần reindex hoặc đổi `.env` để bật tính năng mới.
Factory bật theo hai setting gameplay mặc định true; CHAT_MODE default code vẫn mock.
API thêm optional clarification_id ở request; clarification ở JSON/history/SSE sources. Client cũ trả lời text vẫn được.
ID sai/hết hạn trả 400, không dùng ID của conversation khác. TTL 30 phút, tối đa hai câu hỏi/lượt.
State chỉ commit sau response/SSE thành công; lỗi/hủy không tiêu thụ pending state. Giữ mode/auth/feedback/ảnh local.

Demo: “Chia chỉ số Moonveil” → “100, Samurai” → “PvE”; bot nối chủ thể, không search riêng PvE.
Route: “Tôi nên đi đâu tiếp?” → nhập location/objective; bot trả tuyến có điều kiện thay vì giả đã hạ boss.
Quest: hỏi quest Ranni rồi tiếp tục sau Fingerslayer Blade.
Xem [contract, giới hạn và phần TV4](../api/gameplay-clarification-tv4.md).

Player memory vẫn RAM, độc lập history window nhưng mất khi restart/eviction; không giả PostgreSQL/checkpointer đã có.
Grammar/tên mẫu chưa là NER. Chưa giữ mọi quest flag hoặc world-state dài hạn.
Không dùng LangGraph cho feature này; không giữ HTTP request mở đợi người dùng.

Nguồn bổ sung lấy từ snapshot có provenance/pending metadata; không index vào Qdrant, không nâng thành approved.
Khi cần bảng số, giữ đủ accounting rules trong top-5 dựa cả original và rewrite.
Hiện chỉ kiểm Samurai/Moonveil một tay: tổng điểm, class floors, cap và requirements; không AR/DPS/soft-cap/optimizer.
Ví dụ live cuối: 43/18/20/12/24/46/8/8, tổng 179 tại level 100; server render sau kiểm feasible=true, optimality=false.

## Kết quả thực tế và lỗi đã sửa

Baseline unit: **684 passed**, 1 warning, 22,37 giây. Bản cuối **709 passed**, 1 warning, **20,98 giây**; thêm 25 regression.
Frontend **37 test đạt**, typecheck/build đạt; test tuần tự tránh Vite SSR treo ở lượt npm song song ban đầu.
Ruff/format (205 file), OpenAPI, pip và validation golden đạt. Qdrant memory warning không phải failure.
UTF-8 và 121 liên kết local/7 tài liệu, `git diff --check` đạt; prefix golden/review cũ,
corpus và baseline report hash đã kiểm giữ nguyên.

Live hoàn tất: **30 + 5 + 3 = 38 HTTP requests**, **81 logical DeepSeek calls**, **12 Tavily requests**.
25 prompt chính + 5 OFF ghép cặp; 8 request sau là retest các prompt cũ, không chạy 100 hoặc chọn lại câu để làm đẹp.
Không lỗi HTTP/SSE trong ba lượt, nhưng có **lỗi hành vi thật**: pure arithmetic bị hỏi class/vũ khí, build chưa có bảng số.
Giữ report và review các lỗi. Sửa phân loại arithmetic; retest 092 trả trực tiếp, không web.
Sửa accounting context bị web đẩy khỏi top-5 khi rewrite dùng “distribution”; lượt cuối trả bảng đã kiểm.

Lượt chính AUTO search **4/25**; 16 local_sufficient, 5 branch không assessment gồm một hỏi lại thừa.
5 OFF ghép cặp trả đủ ý chính bằng local. 061 search vì assessor đòi góc/metres không được hỏi;
retest sau siết coverage trả local, 0 web. Build vẫn bị assessor coi thiếu ví dụ sẵn và gọi web dù rule đã đủ.
Không ép sufficient hoặc tăng tool budget để che điểm này. Không coi tỷ lệ search giảm so lượt cũ là controlled gain
vì tập câu và code/knowledge khác; không gọi HTTP 200/grounded là Accuracy.

Token usage biết được: **202.500 / 13.342** prompt/completion, chưa gồm 4 SSE generation calls thiếu usage.
Không quy thành tiền hoặc giả những call này tốn 0 token.
Qdrant point count giữ **18.368** trước/sau cả ba lượt. Benchmark override transport retry=0 và rate limit chỉ trong process.
Không đổi model/thinking/temperature giữa off/auto và các lượt; thinking true được ghi đúng snapshot.

Xem [analysis, lệnh đã chạy, raw report và review](../testing/2026-11-05_gameplay-evaluation.md).
Review là AI-assisted provisional; TV2 chưa review chéo. 041 có rủi ro chuyển chủ ngữ từ item note sang spell khác;
GP-03:2 có wording “quest Pidia” rộng hơn quote. Đã thêm prompt subject-binding, chưa retest live riêng các câu đó.

## Còn lại

- Shared/durable conversation/player state khi multi-worker/restart; quản lý quest flag đầy đủ.
- Cải thiện assessor cho yêu cầu cần tính toán, tránh tìm bài build có sẵn; không thay bằng số score tùy tiện.
- Mở rule/data class/weapon và route có kiểm chứng; không khẳng định mọi walkthrough đã đáp ứng.
- TV4 chỉnh UI form; chưa test tương tác trình duyệt bằng người dùng hoặc Discord gateway thật trong tác vụ này.
- TV2 review nhãn/nguồn/đáp án, bộ test cuối chưa dùng tuning. Không dùng goldenset/reference làm prompt runtime.
- SRS/ADR/planning cần nhóm đồng bộ yêu cầu hội thoại, gameplay, phạm vi và persistence qua quy trình riêng.
