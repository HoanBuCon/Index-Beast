# TV3 (làm thay TV2) · Duyệt golden set 200 câu, bổ sung câu gõ nhầm

Ngày 24/11/2026 · Nhánh `chore/s5-tv3-duyet-golden-200` (từ `develop` sau PR #131). **Chưa commit**; chưa push, chưa có PR.
Không gọi API. Biên bản đầy đủ: [docs/evaluation/2026-11-24_golden-200-duyet.md](../evaluation/2026-11-24_golden-200-duyet.md).

## Phạm vi

MinhMuc: TV2 đã duyệt và bàn giao golden set; nhờ duyệt thay TV2, đánh dấu đã duyệt, đảm bảo bộ 200 câu có đủ độ
khó và các câu gõ sai, gõ nhầm.

## Thay đổi

| File | Nội dung |
|---|---|
| `backend/eval/golden_set.jsonl` | IB-GS-265: câu hỏi nêu thẳng Heart of Bayle (đề xuất 16/11). 23 câu đổi cách gõ: sai chính tả tên riêng, không dấu, sót phím Telex, viết tắt, viết thường không dấu câu. Đáp án, nguồn, độ khó giữ nguyên |
| `backend/eval/reviews/s4-golden-set-review.jsonl` | 200/200 `approved`. 25 phiếu sửa có `delegated_review` mới (Claude, ủy quyền từ MinhMuc, `human_direct_review=false`), câu cũ ở `revision.previous`, phiếu 16/11 ở `previous_review`. IB-GS-279: câu bổ sung khóa lần gặp đầu Diallos. Nhãn mới trong `case_tags`: `telex`, `abbreviation`, `casual_case` |
| `backend/eval/README.md` | Trạng thái duyệt, bảng nhãn `case_tags` và số câu |
| `docs/02_SRS.md` | FR-EVAL-01 thành Done; NFR-QUAL-01 và TBD-10 ghi còn phải đo trên bản đã duyệt |
| `docs/evaluation/2026-11-24_golden-200-duyet.md` | Biên bản: cách duyệt, kết quả, bảng 25 câu đã sửa (trước/sau), giới hạn |

## Kết quả

- `python -m eval.validate_golden --corpus data/chunk_runs/s4-wiki-release/chunks.jsonl --require-reviewed`: **accepted=true**,
  200/200 approved, 183/183 ca dữ kiện và 11/11 lượt bổ sung có quote khớp corpus.
- Phân bố: 110 VI / 90 EN; dễ 60, trung bình 90, khó 50. Câu gõ nhầm 49 (dễ 18, trung bình 23, khó 8; 42 VI, 7 EN).
- Unit `pytest tests/unit`: 939 passed, 20 skipped; pre-commit đạt.

## Lưu ý cho người dùng bộ câu

- Điểm các báo cáo trước 24/11 đo trên câu cũ của 25 ca đã sửa; không so từng ca đó.
- Giữ các câu cùng `variant_pair` trong cùng nhóm khi chia tập: nhiều câu gõ nhầm có bản chuẩn cùng ý làm đối chứng.
- Đây là duyệt theo ủy quyền bằng AI, không phải lượt kiểm trực tiếp của con người.

## Việc còn lại

- Chạy đo chính thức trên bản đã duyệt với luồng Agent: Recall@5/MRR (`eval.measure_retrieval`), correctness và
  faithfulness (NFR-QUAL-01/02). Gọi API, cần MinhMuc cho phép.
- Commit, push, PR về `develop` (MinhMuc tự làm).
