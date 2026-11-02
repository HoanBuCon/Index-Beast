# Bàn giao trợ lý Elden Ring: gameplay, build và đánh giá corpus

Ngày 29/10/2026 (Asia/Saigon). Phụ trách TV3 — MinhMuc, nhóm 4 Hollows.

## 1. Phạm vi và trạng thái

- Mở rộng IndexBeast từ chatbot lore sang trợ lý Elden Ring: gameplay, cơ chế/chỉ số, trang bị,
  vị trí vật phẩm, quest, boss strategy và gợi ý build khi có bằng chứng.
- Nhánh `feature/s2-tv3-gameplay-assistant`, tách từ develop tại `91c5934` sau PR #34.
  Giữ các thay đổi Makefile/prompt local đã có trước tác vụ mở rộng.
- Chưa commit/push, chưa mở PR hoặc merge. Không cập nhật Trello hoặc đánh dấu task Done.
- Handover này được bổ sung theo yêu cầu mới của người dùng sau khi hoàn thành tác vụ local.
- Không sửa `.env` thật, artifact, dữ liệu server hoặc dependency; không gọi DeepSeek/embedding thật trong lượt mở rộng.

## 2. Quyết định cần giữ

Gameplay/build nằm trong phạm vi, không dùng lời từ chối “chỉ hỗ trợ lore”. Nội dung không liên quan và
instruction injection vẫn bị từ chối; regex chỉ là lớp bổ trợ, không phải bảo vệ injection toàn diện.

Giữ game/release/continuity, unknown và review status. Không tự coi base, DLC và Nightreign là cùng game/canon;
không gán approval giả hoặc nhập mọi dòng review/excluded vào index.

RAG chỉ trả facts có evidence. Có thể gợi ý định tính từ mechanics được dẫn nguồn, ghi rõ đó là đề xuất,
không khẳng định tối ưu thực nghiệm. Không bịa stat spread, AR/DPS, breakpoint, patch/meta hoặc đường đi.
Chỉ hỏi 1–2 thông tin thực sự cần; không bắt người dùng điền form trước khi được trợ giúp.

Giữ ba mode mock/llm_only/rag và API v1; không tự fallback từ rag sang llm_only.
Thinking/budget máy hiện tại giữ nguyên. Temperature không phải giải pháp bù dữ liệu thiếu.

## 3. File và thay đổi chính

| File/nhóm | Thay đổi |
|---|---|
| [pipeline.py](../../backend/app/rag/pipeline.py) | Gỡ chặn build/PvP/tối ưu stats; refusal rộng hơn; tách out-of-scope với ambiguity; truyền metadata version/upgrade/trigger/variant nếu có |
| [persona](../../backend/app/rag/prompts/persona.md), [answer](../../backend/app/rag/prompts/answer.md), [rewrite](../../backend/app/rag/prompts/rewrite.md), [llm_only](../../backend/app/rag/prompts/llm_only.md) | Scope gameplay/build; trả lời tự nhiên, bám evidence, phân biệt mechanics với recommendation và version chưa rõ |
| [rewrite.py](../../backend/app/rag/rewrite.py) | Rewrite làm mất/thay số literal phải fallback về câu hỏi gốc; prompt giữ tên riêng, mục tiêu và điều kiện |
| [generator.py](../../backend/app/rag/generator.py) | Hỗ trợ field nội bộ tùy chọn `limitation`, kiểm rồi nối cuối answer; giữ citation/quote checks |
| [mock_chat.py](../../backend/app/services/mock_chat.py) | Thông báo thiếu dữ liệu trung tính, không nói chỉ có lore |
| [audit_corpus_capabilities.py](../../backend/scripts/audit_corpus_capabilities.py) | Census read-only, mẫu 12 title có chủ đích, phân biệt chunk đã chọn với review và literal signal với coverage ngữ nghĩa |
| [test_live_chat.py](../../backend/tests/unit/test_live_chat.py), [test_corpus_capabilities.py](../../backend/tests/unit/test_corpus_capabilities.py) | Regression gameplay, partial JSON/SSE, validation, rewrite và audit |
| [Makefile](../../Makefile), [.env.example](../../.env.example), [README](../../README.md) | Lệnh dev/health/unit, tự dùng Python venv; budget mẫu 4096; hướng dẫn chạy nhanh đã làm ở lượt trước và giữ trong cùng working tree |
| [RAG README](../../backend/app/rag/README.md), [hướng dẫn local](../testing/indexbeast-local-guide.md) | Cách dùng, scope, partial answer và giới hạn |

`limitation` tối đa 1.000 ký tự, chỉ nêu thiếu evidence hoặc câu hỏi làm rõ, không facts mới/citation/URL.
Phần answer có facts vẫn cần citation mỗi đoạn. Backend nối limitation sau khi validation thành công;
public API vẫn chỉ có answer/sources/grounded như trước, không thêm field mới.
`grounded=true` ở partial answer không chứng nhận mọi phần câu hỏi đã được giải đáp.
Validator không chứng minh entailment hoặc tự xác minh nội dung limitation không có facts sai.
SSE vẫn streaming thật, có cleanup; lỗi trước token đầu trả lỗi HTTP, lỗi giữa stream không gửi done thành công.

## 4. Audit dữ liệu và collection

Xem [báo cáo khả năng dữ liệu và 10 câu thử](../testing/2026-10-29_elden-ring-assistant-capabilities.md)
và [JSON census/mẫu nguồn](../testing/2026-10-29_corpus-capabilities.json).

- Artifact chính: `backend/data/chunk_runs/s2-full-v1/chunks.jsonl`, 23.765 chunk.
- Pilot/en chọn 18.368; 5.397 không chọn do language, không đổi unknown thành en.
- Có effect/notes hữu ích, ví dụ bleed, chữa poison/rot, equip load và hai đoạn quest progression của Ranni.
- Nhiều acquisition, bảng stat và boss moves đã bị lọc ở bước clean: review có 6.637 dòng gameplay_section,
  3.983 gameplay_infobox_field, 228 numeric_stats_table và 129 combat_section_may_contain_lore.
  Đây là dòng review, không phải số chunk có thể tự phục hồi.
- Đã đối chiếu mẫu raw/review/chunk: acquisition Uchigatana và Bloodhound's Fang không còn trong chunk
  của chính title đó; bảng move Malenia còn ở review. Không thể bù dữ liệu mất chỉ bằng prompt/retrieval.
- Mẫu 12 title không đại diện cho mọi trang. Đếm từ khóa không chứng minh coverage, recall hoặc correctness.

Collection hiện tại dùng tiếp được: không đổi admission stamp, filter, ID mapping, vector schema hoặc embedding.
**Không cần reindex cho thay đổi code/prompt này.** Không kết nối server để xác nhận lại count trong tác vụ mở rộng.
Muốn gameplay đầy đủ cần artifact mới được review, giữ header/đơn vị/upgrade/affinity/quest order và patch có bằng chứng,
rồi tự dry-run và index vào collection riêng. Không nhập review.csv trực tiếp hoặc drop collection cũ.

## 5. Cách chạy và kiểm tra

Từ gốc project, sau khi mở Docker Desktop:

```powershell
make dev
```

Giữ terminal mở; tạo hội thoại API mới ở địa chỉ Vite in ra. `Ctrl+C` dừng API/web, Docker giữ dữ liệu.
Terminal khác có thể chạy `make health`. `make dev` không tự index hoặc gửi câu hỏi trả phí.
Chat thật sẽ dùng credits DeepSeek; tác vụ này chưa thực hiện các câu hỏi thật đó.
Restart API để nạp prompt mới; không cần đổi `.env` hoặc collection chỉ để thử.

Các lệnh offline sau **đã chạy** từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
.venv/Scripts/python.exe -X utf8 -m scripts.audit_corpus_capabilities --output ../docs/testing/2026-10-29_corpus-capabilities.json
.venv/Scripts/python.exe -X utf8 -m ingest index --input data/chunk_runs/s2-full-v1/chunks.jsonl --policy pilot --languages en --dry-run
```

Kết quả baseline **259 passed, 1 warning**; sau sửa **284 passed, 1 warning**, 15,66 giây.
Warning dự kiến: Qdrant memory không thực thi payload indexes như server.
Ruff lint/format (143 file), OpenAPI và Git whitespace check đạt. Không đổi dependency nên không chạy lại pip check.
Dry-run: 18.368 accepted, invalid 0; token check lượt này là declared_bounds_only, không encode.
Hash artifact giữ nguyên: `95794a89485e6f86ff320ee9b2a9a707a794e1bdc040162f0b41e5b2c208d03e`.

Case PvP build chuyển khỏi nhóm từ chối cũ sang test cho phép theo scope mới; không bỏ assertion evidence/unrelated.
Kiểm JSON/SSE bằng fake model/retriever, gồm lỗi trước/sau token đầu. Chưa kiểm DeepSeek thật,
server retrieval/index, UI browser hoặc Discord Gateway trong lượt này. Kết quả live 10/10 ở báo cáo trước
là của smoke test lore cũ, không phải đánh giá gameplay của prompt mới.

## 6. Việc còn lại

- Chuẩn bị/review artifact gameplay mới cùng TV2; chưa có numerical optimizer hoặc damage calculator.
- Chạy 10 câu trong báo cáo trên web và cả JSON/SSE khi có quyền gọi model thật; chấm retrieval và answer riêng.
- Đánh giá version/patch, nhiều thực thể, prompt injection và partial answer bằng model thật.
- Đồng bộ riêng SRS, ADR-004, ADR-003, kiến trúc/techstack, planning và `docs/AGENTS.md` còn phạm vi lore/base-only.
- Handover cũ giữ tính lịch sử. Khi chuẩn bị PR cần commit cả code, report và handover; chờ reviewer, không tự merge.
