# Golden set IndexBeast — Sprint 2

[golden_set.jsonl](golden_set.jsonl) là file chính, đường dẫn `eval/golden_set.jsonl` khi đứng ở backend.
Hiện có **60 câu: 38 VI / 22 EN (63,33% VI)**. Bổ sung 30 ID `IB-GS-031`–`IB-GS-060`,
gồm 18 VI/12 EN, 10 câu SotE, 6 câu ngoài phạm vi. Độ khó toàn bộ: easy 21, medium 26, hard 13.

Giữ đúng bảy trường: id, question, lang, expected_answer, source_urls, category, difficulty.
Không đổi ID/câu hỏi cũ. Đáp án tham chiếu là tập ý cần đúng và ràng buộc cần giữ, **không chấm exact string**.
SRS FR-EVAL-01 hướng tới ≥100 câu; 60 câu chưa hoàn thành toàn bộ mục tiêu đó.

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
Tất cả **60 pending, 0 approved** tại thời điểm bàn giao. ID 031–054 có author_evidence từ JSONL thật:
chunk ID, dòng, URL, release_scope/source_type gốc, quote nguyên văn và text hash. Không tự gọi đó là TV2 review.
24 factual case cũ chưa được audit lại toàn bộ trong tác vụ này, giữ pending thay vì tự xác nhận nguồn đúng.

Nguồn tác giả kiểm là snapshot local, không phải kiểm URL live hoặc xác minh patch mới nhất.
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

Không đưa expected_answer, câu hỏi hoặc author quote vào index như dữ liệu huấn luyện/evidence để tự làm đẹp điểm.
Các module retrieval.py/answer.py hiện còn là khung; tác vụ này không chạy benchmark model hoặc LLM judge,
không có điểm Recall/MRR/correctness được tạo mới. Thiếu dữ liệu ở runtime không biến factual golden thành negative.
