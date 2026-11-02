# Bàn giao golden set Sprint 2 và phiếu review TV2

TV3 — MinhMuc, nhóm 4 Hollows, ngày 31/10/2026 (Asia/Saigon).
Nhánh `feature/s2-tv3-golden-set-expansion` từ develop `94c968a` sau PR #41.
Liên quan FR-EVAL-01, thẻ mở rộng golden set Sprint 2. Chưa commit/push/PR/merge, chưa cập nhật Trello.

## Đã triển khai

- [Golden set](../../backend/eval/golden_set.jsonl): thêm **30 câu**, ID 031–060; tổng **60**, 38 VI/22 EN.
  Batch mới 18 VI/12 EN, gồm 10 SotE và 6 ngoài phạm vi. ≥50% VI ở cả batch mới và toàn set.
- Độ khó toàn bộ: easy 21, medium 26, hard 13. Tiêu chí difficulty và cách chấm theo ý ở phiếu review.
- Giữ ID/câu hỏi cũ. Sửa lời từ chối 025–030 để không nói chatbot chỉ hỗ trợ lore/base game.
  ID 027 build PvP level 150 chuyển sang insufficient_evidence/hard: trong phạm vi, không được bịa build tối ưu.
- [Sidecar review](../../backend/eval/reviews/s2-golden-set-review.jsonl): 60 record phân công TV2 — UncleThing;
  **60 pending, 0 approved**. Tác giả không giả đã có review chéo của người.
- 24 câu factual mới có author_evidence: artifact/chunk ID/dòng, URL gốc, quote exact slice, hash,
  release_scope/source_type nguyên trạng. Không gán approval hoặc biến unknown/candidate thành base.
- [Phiếu TV2](../evaluation/2026-10-31_golden-set-s2-review.md),
  [eval README](../../backend/eval/README.md), [validator offline](../../backend/eval/validate_golden.py)
  và [unit tests](../../backend/tests/unit/test_golden_set.py).

## Quy tắc cần giữ

Golden JSONL giữ đúng bảy trường cũ, không thêm review metadata vào record đánh giá.
Fact phải có source URL; out_of_scope/insufficient_evidence hiện là behavioral negative, nguồn rỗng.
Không chấm exact wording; expected_answer gồm các ý đúng và giới hạn cần giữ.
Thiếu dữ liệu khi retrieval không biến câu factual thành ngoài phạm vi.
Không coi build/gameplay Elden Ring là out_of_scope; không gộp game khác/SotE/Nightreign thành chung canon.

Nguồn tác giả đã kiểm là snapshot trong artifact local, không phải kiểm URL live hoặc xác minh patch mới nhất.
Legacy 24 factual case chưa được audit lại toàn bộ; giữ pending để TV2 kiểm, không tự thừa nhận nguồn/answer đã đúng.
Case số liệu 045/048 và recommendation 047 được gắn ngữ cảnh snapshot/note, không khẳng định latest/meta.

## Review chéo — việc còn lại bắt buộc

TV2 đọc nguồn và đáp án, kiểm scope/điều kiện/độ khó, sửa nếu cần rồi điền status/checks/reviewer/date/comment
trong sidecar, giữ ID và provenance. Ưu tiên batch mới và ID 027; các legacy case còn pending cần review tiếp
khi chốt toàn bộ baseline. Không đổi approved chỉ để qua gate. Reviewer thật ghi nhận qua quy trình Git/PR.
Validator kiểm khai báo, không xác thực danh tính người review hoặc chứng minh entailment.

**Thẻ chưa hoàn tất phần TV2 review**. SRS đặt mục tiêu ≥100 câu, hiện 60 nên cũng chưa hoàn tất toàn FR-EVAL-01.
Không liên hệ TV2 bằng công cụ chat/email hoặc tự ghi task Done trong tác vụ này.

## Kiểm tra

Từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --corpus data/chunk_runs/s2-full-v1/chunks.jsonl
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --require-reviewed
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
```

Schema/URL syntax/ID và câu hỏi trùng/VI ratio hợp lệ; đối chiếu author quote/hash/URL với artifact cho 24 case mới.
--require-reviewed hiện cần exit 2 có chủ đích vì 60 pending, không phải lỗi schema.
Full suite **331 passed, 1 warning** (15,88 giây), gồm 8 case mới cho golden set/validator.
Warning dự kiến: Qdrant memory không thực thi payload indexes như server.
Ruff lint/format (166 file), UTF-8/local links và `git diff --check` đạt.
Đã kiểm child exit code --require-reviewed đúng 2. Đã đối chiếu HEAD: factual 001–024 nguyên trạng,
toàn bộ ID/câu hỏi 001–030 giữ nguyên. Không thay expected chỉ để che lỗi test; chỉ đổi scope cũ đã lỗi thời.
Kết quả schema/provenance lưu ở [validation JSON](../evaluation/2026-10-31_golden-set-validation.json).

Không gọi LLM, chạy notebook/embedding/index, ghi Qdrant/PostgreSQL hoặc sửa corpus/.env/dependency.
Không có điểm benchmark Recall/MRR/correctness mới; eval/retrieval.py và eval/answer.py vẫn là khung.
Chưa sửa SRS/ADR/handover lịch sử. Golden set không đưa vào index để tránh làm đẹp điểm bằng đáp án tham chiếu.
