# Golden set IndexBeast — Sprint 3

Cập nhật 05/11/2026: **thêm đúng 40 câu vào 60 câu cũ**, tổng 100; không chạy 100 câu test.
Đợt live dùng 25 prompt và 5 lượt OFF ghép cặp, sau đó test lại có mục tiêu các lỗi phát hiện.
Xem [hướng dẫn gameplay/hỏi lại](../../docs/api/gameplay-clarification-tv4.md)
và [báo cáo thực tế](../../docs/testing/2026-11-05_gameplay-evaluation.md).

Đã có runner chẩn đoán tập 25 ID: `python -m scripts.diagnose_golden` mặc định plan-only.
Xem [hướng dẫn chạy, review và giới hạn](../../docs/evaluation/golden-diagnostic-guide.md).
Runner này đo pipeline, không hoàn thiện các module LLM judge/retrieval metric còn là khung bên dưới.

Bộ so sánh ngôn ngữ riêng: [vi_en_pairs.jsonl](vi_en_pairs.jsonl), 13 cặp VI–EN đang chờ review.
Không gộp vào golden_set 100 câu hoặc tính evidence recall khi chưa có chunk labels đã review.
Xem [hướng dẫn benchmark theo tầng](../../docs/testing/2026-10-31_vi-en-retrieval-guide.md).

[golden_set.jsonl](golden_set.jsonl) là file chính, đường dẫn `eval/golden_set.jsonl` khi đứng ở backend.
Hiện có **100 câu: 64 VI / 36 EN (64% VI)**. Sprint 3 thêm `IB-GS-061`–`IB-GS-100`,
26 VI/14 EN. Giữ nguyên 60 record cũ theo byte; độ khó toàn bộ: easy 33, medium 44, hard 23.
Category: character 10, event 6, location 10, multi_hop 8, mechanics 11, equipment 13,
quest 22, insufficient_evidence 7, out_of_scope 13. Giữ 10 câu SotE cũ.

Giữ đúng bảy trường: id, question, lang, expected_answer, source_urls, category, difficulty.
Không đổi ID/câu hỏi cũ. Đáp án tham chiếu là tập ý cần đúng và ràng buộc cần giữ, **không chấm exact string**.
Đã đạt số lượng 100 theo FR-EVAL-01; review chéo và đánh giá độc lập vẫn chưa hoàn tất.

## Phạm vi và nhãn

Theo quyết định mới, chatbot hỗ trợ lore/gameplay/build/quest Elden Ring và SotE có bằng chứng.
Không gộp continuity khác hoặc tự đoán metadata unknown thành base. SRS/ADR cũ cần nhóm đồng bộ riêng.

- `character`, `event`, `location`, `multi_hop`: giữ nhóm cũ.
- `mechanics`, `equipment`, `quest`: bổ sung cho năng lực trợ lý hiện tại.
- `out_of_scope`: ngoài Elden Ring hoặc instruction injection, không cần source URL.
- `insufficient_evidence`: trong phạm vi nhưng không có cơ sở cho khẳng định yêu cầu; không đánh đồng với out_of_scope.
  ID 027 về build PvP chuyển sang nhóm này: không được từ chối chỉ vì là gameplay,
  nhưng cũng không bịa build “mạnh nhất”. Có thể hỏi điều kiện hoặc gợi ý định tính có nguồn.

Các factual case có URL nguồn, negative behavioral case dùng source_urls=[]; không bịa URL cho câu ngoài phạm vi.
Scope phục vụ đánh giá nằm trong sidecar review, không thêm trường hoặc đổi payload admission của backend.

## Nguồn và tình trạng review

[Sidecar review](reviews/s2-golden-set-review.jsonl) có một record cho mỗi ID, phân công TV2 — UncleThing.
Tất cả **100 pending, 0 approved** tại thời điểm bàn giao. ID 031–054 và 061–090 có author_evidence từ JSONL thật:
chunk ID, dòng, URL, release_scope/source_type gốc, quote nguyên văn và text hash. Không tự gọi đó là TV2 review.
54 case có quote/hash artifact được validator đối chiếu. 091–092 kiểm quy tắc toán trên
[Stats](https://eldenring.wikidot.com/stats), không giả có artifact quote hoặc TV2 approval.
24 factual case cũ chưa được audit lại toàn bộ trong tác vụ này, giữ pending.

Các quote artifact là snapshot local; hai câu toán và các trường trong knowledge pack được kiểm trang công khai.
Không coi ngày đọc trang là xác minh patch mới nhất.
Các câu số liệu 045/048 và khuyến nghị 047 ghi rõ snapshot/note; không chấm chúng như khẳng định meta hiện tại.
Không dùng ngày crawl hoặc candidate release làm chứng nhận patch/canon.

TV2 làm theo [phiếu review và rubric](../../docs/evaluation/2026-10-31_golden-set-s2-review.md).
Mỗi người review bằng nhánh/PR riêng theo quy ước; chưa tự gửi yêu cầu review hoặc cập nhật board.

## Validation offline

Từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --corpus data/chunk_runs/s2-full-v1/chunks.jsonl
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --require-reviewed
```

Lệnh đầu kiểm schema, URL syntax, ID/câu hỏi trùng, ≥50% VI và review mapping.
Lệnh có corpus còn đối chiếu quote/hash và URL theo artifact, không embedding hoặc kết nối server.
Lệnh --require-reviewed **hiện exit 2 có chủ đích** vì chưa được review; schema hợp lệ không bằng approved.
Approval cần reviewer UncleThing (hoặc TV2 - UncleThing), thời gian có timezone và các checks hoàn tất.
Validator chỉ kiểm khai báo trong file, không xác thực danh tính hay thay thế PR review của TV2.

Không đưa expected_answer/câu hỏi/author rubric vào index hoặc prompt runtime để tự làm đẹp điểm.
Runtime knowledge pack giữ nguyên source chunks độc lập, không chứa câu hỏi/đáp án golden; đây là
bổ sung nguồn có chủ đích cho development, không phải đo tổng quát hóa trên tập chưa thấy.
Các module retrieval.py/answer.py còn là khung; runner HTTP mới là `python -m scripts.diagnose_gameplay`.
Manifest chọn 25 prompt: [gameplay_diagnostic_25.json](gameplay_diagnostic_25.json).
10 scenario multi-turn riêng: [gameplay_scenarios.json](gameplay_scenarios.json), không giả thành standalone golden.
Chỉ có nhận xét AI-assisted sơ bộ; không có human-reviewed Accuracy/Recall/MRR mới.
Thiếu dữ liệu runtime không biến factual golden thành negative. Xem báo cáo để phân biệt valid output với đúng nội dung.
