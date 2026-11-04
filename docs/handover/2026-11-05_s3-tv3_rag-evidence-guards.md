# TV3 — Guard rewrite, assessor và evidence RAG

Ngày 05/11/2026 · MinhMuc · IndexBeast / 4 Hollows.

## Phạm vi và Git

Sửa nguyên nhân từ chẩn đoán 25 câu, giảm chặn nhầm và câu trả lời cứng; giữ kiểm evidence/citation.
Nhánh `fix/s3-tv3-rag-evidence-guards`, tách tại HEAD `dfc0286` của nhánh đang làm
`feature/s3-tv3-golden-diagnostic` để giữ thay đổi local hiện có. Chưa fetch/rebase vì không cần
tác động lịch sử trong tác vụ offline; trước PR cần đồng bộ theo quy ước nhóm.
Không stash/reset, commit/push/merge hoặc cập nhật Trello. Chưa có PR, không đánh task Done.

Các file diagnostic/eval/guide/report ngày 04/11 vốn đã modified/untracked trước tác vụ vẫn được giữ;
không tự coi chúng là file mới của bản sửa guard. Report/golden/corpus gốc không chỉnh.

## File và quyết định chính

| File | Thay đổi |
|---|---|
| `backend/app/rag/web_search.py`, `prompts/assess.md` | Evidence list 1–3 ID, legacy string lossless; tách assessment_error khỏi thiếu bằng chứng |
| `backend/app/rag/rewrite.py` | Khung ngữ pháp đầu câu, Unicode token và full-name plural variants; giữ guard sai tên/số/phủ định/goal/intent |
| `backend/app/rag/context_policy.py`, `pipeline.py` | Độ phủ theo entity/section; dedup web alias với provenance, giữ policy/top-5/budget |
| `backend/app/rag/generator.py`, `prompts/answer.md`, `prompts/persona.md` | Nhiều quote/source; contract rõ, bounded recovery, quest necessity và build định tính/hỏi lại |
| `backend/tests/fixtures/golden_guard_replays.json`, `tests/unit/test_evidence_guards.py` | Output thật 24 assessor/8 rewrite/2 generation, context 044/050; thêm 70 regression offline |
| `backend/app/rag/README.md`, `docs/api/web-search-tv4.md` | Cách dùng và tương thích API |
| `docs/testing/2026-11-05_rag-evidence-guards.md`, handover/index | Kết quả, giới hạn và lệnh benchmark sau sửa |

Contract public JSON/SSE không đổi. TV4 không cần sửa frontend/bot cho bản này.
Internal assessor dùng index → list ID; string cũ được bọc singleton, không chọn mất các ID khác.
Internal generator thêm quote_ids, giữ quote_id/quote legacy; chỉ một dạng/source và không lặp index.
Source.text vẫn string, nhiều đoạn nối bằng `\n[…]\n`; URL từ metadata đại diện, chỉ nguồn được trích trả về.
Mọi alias URL giữ trong payload.provenance; không đổi ID chunk, admission/review status hoặc metadata unknown.

Trace quyết định rõ local_sufficient/local_partial/local_insufficient/ambiguous/assessment_error.
Sufficient mới skip web trong auto, assessment_error không chứng minh local thiếu.
Context chỉ ưu tiên candidate có thật, dựa entity rewrite hợp lệ và section; không thêm dữ liệu/LLM call.
Không gộp metadata điều kiện khác nhau. Dữ liệu/nguồn chưa review không bị giả approved.

Giảm guard sai không đồng nghĩa bỏ guard: vẫn reject tên/số/phủ định sai, quote/URL/index bịa,
insufficient có citations và output schema sai. Prompt hướng dẫn trả phần có bằng chứng, nêu gap cụ thể,
build thiếu điều kiện chỉ hỏi 1–2 thông tin; không bịa build số hoặc suy reward thành bắt buộc quest.
Không thêm semantic verifier; citation/quote validation chưa chứng minh entailment.

## Kiểm tra đã chạy

- Baseline trước sửa: **614 passed**, 1 warning, 20,28 giây.
- Sau sửa: **684 passed**, 1 warning, 20,58 giây ở lượt cuối; 70 test mới. Suite cũ giữ nguyên.
- Replay: 24/24 assessor output parse/reference đạt; 8/8 rewrite từng bị reject nay qua guard.
  Context 044 giữ cả hai loại đá; context 050 có đoạn phủ định điều kiện quest; 3 alias còn 1 với đủ provenance.
- Ruff check/format (198 file), OpenAPI check và pip check đạt.
- Đối chiếu output fixture với report: 33 phép kiểm đạt. Không phải điểm đúng của đáp án hoặc recall live.
- UTF-8, 102 liên kết local/5 tài liệu và `git diff --check` đạt; hash report và golden/review/selection không đổi.

Chi tiết lệnh, contract, budget, kết quả và giới hạn trong
[báo cáo offline](../testing/2026-11-05_rag-evidence-guards.md).
Warning duy nhất: Qdrant memory không thực thi payload index như server.
Không gọi DeepSeek/Tavily/model/encoder thật, index/crawl/notebook hoặc ghi server/DB; không sửa `.env`.

## Cách dùng và bước tiếp theo

Restart backend `make dev` để nạp code/prompt, không cần embedding/index lại.
OFF/ON/ALWAYS vẫn off/auto/always; Discord auto; mock/llm_only/rag, lifecycle, ảnh local và event giữ nguyên.
Budget không tăng: tối đa 1 rewrite + 1 assessment + 2 generation; 1 Search + 1 Extract batch;
top-5/budget cấu hình cũ, deadline tổng giữ nguyên; không retry generation sau khi phát text SSE.
Transport retry SDK vẫn theo cấu hình app; runner diagnostic đặt 0 để giới hạn chi phí.

Lệnh chạy lại cùng 25 ID mode auto vào **thư mục mới**, chưa thực hiện, nằm trong báo cáo liên kết trên.
Đối chiếu snapshot config/hash, corpus/Qdrant không đổi. Snapshot cũ ghi thinking=true nhưng
analysis mô tả false; đã ghi nhận sai khác, không sửa baseline hoặc suy luận wire request khi thiếu log.

Chưa chứng minh model thật hết 502, tự chọn đúng quote/điều kiện quest hoặc chất lượng tăng bao nhiêu.
Hai output build lỗi thật vẫn bị reject; test recovery dùng completion scripted hợp lệ.
Cần chạy lại, đọc đáp án/quote, chấm correctness/faithfulness và TV2 review; 25 câu là development,
không dùng làm tập test cuối độc lập. Corpus stat/class/progression còn giới hạn; không có ảnh web/calculator/LangGraph mới.
