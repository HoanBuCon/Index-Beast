# Phiếu review chéo golden set Sprint 2

Ngày 31/10/2026, tác giả TV3 — MinhMuc; người cần review **TV2 — UncleThing**.
Nhánh : `feature/s2-tv3-golden-set-expansion`.

## Trạng thái

- Từ 30 lên **60 câu**, thêm 30; toàn bộ 38 VI/22 EN, batch mới 18 VI/12 EN.
- Batch mới: **10 SotE**, 14 Elden Ring còn lại, **6 ngoài phạm vi**.
- Độ khó toàn set: 21 easy, 26 medium, 13 hard; đây là nhãn tác giả đề xuất, chưa là kết luận của TV2.
- Giữ ID/câu hỏi 001–030; sửa reference refusal 025–030 cho scope hiện tại.
  Riêng 027 chuyển từ out_of_scope/medium sang insufficient_evidence/hard theo yêu cầu gameplay/build mới.
- Tất cả review pending, không ghi review của AI thành review chéo của người.
- Đây chưa đủ ≥100 câu theo FR-EVAL-01. Nghiệm thu thẻ này còn chờ bước TV2 review.

## TV2 cần làm gì?

Mở [golden set](../../backend/eval/golden_set.jsonl) cùng
[sidecar review](../../backend/eval/reviews/s2-golden-set-review.jsonl).
Ưu tiên 031–060 và case 027 vừa đổi policy; kiểm tiếp legacy factual case khi hoàn thiện baseline đã review.

1. Đọc URL thật và snapshot/chunk tham chiếu; kiểm nguồn có hỗ trợ từng ý của expected_answer không.
   Các quote tác giả là gợi ý tìm nguồn, không mặc định chứng minh entailment.
2. Kiểm game/release, speculation, điều kiện quest, optional step, loại item và đơn vị/chỉ số.
   Source live có thể khác snapshot; ghi rõ khác biệt revision/patch, không âm thầm đổi câu hỏi snapshot thành latest.
3. Với ngoài phạm vi: xác nhận không yêu cầu nguồn; build Elden Ring không bị coi là ngoài phạm vi.
   Case 027 chấp nhận câu trả lời giới hạn trung thực hoặc khuyến nghị định tính có nguồn, không exact stat spread bịa.
4. Đánh độ khó theo rubric, kiểm câu hỏi không lặp ý hoàn toàn với câu đã có; máy chỉ phát hiện trùng câu chuẩn hóa,
   không phát hiện đầy đủ semantic duplicates hoặc đánh giá chất lượng đề.
5. Sửa JSONL nếu cần, giữ ID. Trong review record, điền checks source_urls/expected_answer/difficulty/scope,
   status changes_requested hoặc approved, reviewer UncleThing, reviewed_at ISO-8601 có timezone và comment cụ thể.
   Với source không áp dụng cho negative có thể chọn not_applicable, nhưng vẫn kiểm scope/answer/difficulty.

Ví dụ **chỉ minh họa, không phải một review đã diễn ra**:

```json
{
  "status": "approved",
  "reviewer": "UncleThing",
  "reviewed_at": "YYYY-MM-DDTHH:MM:SS+07:00",
  "checks": {"source_urls": "pass", "expected_answer": "pass", "difficulty": "pass", "scope": "pass"},
  "comment": "Ghi nguồn/điều kiện đã đối chiếu."
}
```

Chỉ copy các field thay đổi vào record của đúng ID; giữ author_evidence và metadata provenance.
Không sửa status approved chỉ để qua validation. Dùng Git/PR để ghi nhận reviewer thực, validator không xác thực danh tính.

## Rubric độ khó và chấm đáp án

| Độ khó | Tiêu chí |
|---|---|
| easy | Một ý hoặc nhóm facts trực tiếp, ít điều kiện, thường tìm được trong một đoạn rõ |
| medium | Quan hệ/so sánh/đơn vị hoặc vài điều kiện cần giữ; dễ nhầm đối tượng, phiên bản hoặc giới hạn |
| hard | Nhiều bước/phối hợp nguồn, diễn giải có ranh giới, chống suy luận quá mức hoặc injection |

Chấm theo ý, không buộc câu trả lời giống từng chữ. Facts đúng nhưng thiếu điều kiện quan trọng có thể chỉ đạt một phần.
Citation tồn tại/quote nguyên văn không đồng nghĩa mọi khẳng định đúng. Đánh correctness và faithfulness riêng.
Negative case không cần citation; không yêu cầu model phải có nguồn để từ chối yêu cầu ngoài phạm vi.

## Batch mới chờ review

| ID | Lang | Scope | Category | Difficulty | Review |
|---|---|---|---|---|---|
| IB-GS-031 | vi | SotE | location | easy | pending |
| IB-GS-032 | vi | SotE | character | medium | pending |
| IB-GS-033 | vi | SotE | character | hard | pending |
| IB-GS-034 | vi | SotE | mechanics | medium | pending |
| IB-GS-035 | vi | SotE | mechanics | medium | pending |
| IB-GS-036 | vi | SotE | multi_hop | hard | pending |
| IB-GS-037 | en | SotE | character | easy | pending |
| IB-GS-038 | en | SotE | character | medium | pending |
| IB-GS-039 | en | SotE | location | medium | pending |
| IB-GS-040 | en | SotE | location | easy | pending |
| IB-GS-041 | vi | Elden Ring | mechanics | easy | pending |
| IB-GS-042 | vi | Elden Ring | equipment | medium | pending |
| IB-GS-043 | vi | Elden Ring | mechanics | medium | pending |
| IB-GS-044 | vi | Elden Ring | multi_hop | medium | pending |
| IB-GS-045 | vi | Elden Ring | equipment | medium | pending |
| IB-GS-046 | en | Elden Ring | mechanics | medium | pending |
| IB-GS-047 | en | Elden Ring | equipment | medium | pending |
| IB-GS-048 | en | Elden Ring | mechanics | medium | pending |
| IB-GS-049 | vi | Elden Ring | quest | hard | pending |
| IB-GS-050 | vi | Elden Ring | quest | medium | pending |
| IB-GS-051 | vi | Elden Ring | quest | easy | pending |
| IB-GS-052 | en | Elden Ring | quest | hard | pending |
| IB-GS-053 | en | Elden Ring | quest | hard | pending |
| IB-GS-054 | en | Elden Ring | equipment | easy | pending |
| IB-GS-055 | vi | outside | out_of_scope | easy | pending |
| IB-GS-056 | vi | outside | out_of_scope | easy | pending |
| IB-GS-057 | vi | outside | out_of_scope | medium | pending |
| IB-GS-058 | vi | outside | out_of_scope | hard | pending |
| IB-GS-059 | en | outside | out_of_scope | medium | pending |
| IB-GS-060 | en | outside | out_of_scope | easy | pending |

## Kiểm tra và giới hạn

Từ backend: `python -m eval.validate_golden --corpus data/chunk_runs/s2-full-v1/chunks.jsonl`.
Sau review có thể dùng --require-reviewed để gate toàn set; hiện gate này chưa đạt vì tất cả đang pending.
Author đã đối chiếu 24 factual case mới với artifact, không thẩm định lại 24 factual case legacy hoặc kiểm URL live.
Không gọi LLM, không chạy embedding/index/notebook hoặc ghi Qdrant/PostgreSQL trong tác vụ này.
Chưa có kết quả chạy chatbot trên 60 câu; không tự ghi điểm đánh giá, TV2 approve hoặc task Done.

Kiểm tra thực tế: [validation JSON](2026-10-31_golden-set-validation.json) đạt draft schema/provenance;
gate reviewed chưa đạt (child exit 2). Unit suite **331 passed, 1 warning**, Ruff lint/format và link/UTF-8 đạt.
Đây không phải điểm correctness/faithfulness hoặc xác nhận 60 đáp án đã được thẩm định.
