# Chẩn đoán 25 câu golden set thật

Ngày 04/11/2026 · TV3 MinhMuc · nhánh `feature/s3-tv3-golden-diagnostic`, từ develop `dfc0286`.
Git sạch trước khi tạo nhánh; không commit/push/merge hoặc sửa Trello.

## Phạm vi và artifact

User yêu cầu chạy khoảng 25 câu từ golden set để chẩn đoán hệ thống hiện tại.
Đã chạy đủ 25 câu thật, dùng DeepSeek, Tavily và query embedding cache/Qdrant read.
Không index/crawl/notebook/upsert/drop/ghi PostgreSQL hoặc sửa .env; không chạy lại case lỗi để làm đẹp điểm.
Giữ nguyên pipeline/prompt trong toàn lượt để baseline nhất quán.

- `backend/eval/diagnostic_25.json`: 25 ID nguyên bản, ưu tiên gameplay, 18 VI/7 EN; giới hạn phạm vi rõ.
- `backend/scripts/diagnose_golden.py`: mặc định plan-only, execute có flags riêng cho LLM/web;
  giới hạn call, checkpoint atomic từng case, không echo secret/private reasoning, không leak expected vào input.
- `backend/tests/unit/test_golden_diagnostic.py`: plan/permission/output guard, error continuity,
  checkpoint, no-answer leakage, budget và private reasoning.
- [Hướng dẫn](../evaluation/golden-diagnostic-guide.md), README eval cập nhật.
- [Báo cáo phân tích](../testing/2026-11-04_golden-25-auto/analysis.md).
- [Report gốc](../testing/2026-11-04_golden-25-auto/report.json), review.md, mẫu manual_review.jsonl để trống,
  observations.json ghi 25 nhận xét hỗ trợ bởi Codex, không giả TV2 đã review hoặc người chấm độc lập.

## Kết quả và phát hiện

24/25 phản hồi hợp lệ (23 grounded theo protocol + 1 static chặn injection), 1 lỗi build 027.
Không gọi 96% là answer accuracy. Median 8,324 s, p95 12,354 s; tổng thời gian case 213,274 s.
74 logical LLM calls (24 rewrite, 24 assessor, 26 generation); 48 Tavily HTTP requests theo adapter
(24 Search + 24 Extract, không retry). Provider báo 201.813 prompt/12.565 completion tokens.
SDK retry đặt 0 riêng cho diagnostic để giới hạn chi phí, khác app nếu app cấu hình khác 0.

Đã phát hiện bằng output thật:
1. 23/24 assessor trả evidence index → list quote ID, trong khi backend yêu cầu string; auto gần như luôn search.
2. Rewrite fallback 8/24: 6 proper_name_lost, 2 singular/plural entity_lost, kể cả câu EN.
3. Build 027 lần đầu extra field type gây schema_invalid; retry insufficient=true vẫn citation gây 502 tương đương.
4. 044 thiếu normal +25: ứng viên local có trang đúng rank 6 nhưng bị bỏ khỏi context, không phải toàn corpus vắng.
5. 050 trùng web text ba URL alias chiếm 3/5 slot; generator suy bắt buộc quest Ranni sai quan hệ điều kiện.
6. 041 claim số liệu có trong body nguồn nhưng quote được chọn trỏ gallery; quote tồn tại không chứng minh entailment.

Chưa sửa runtime trong tác vụ này. Những phát hiện trên là cơ sở task sửa tiếp, không tự đổi corpus hoặc nới validator.

## Kiểm tra và giới hạn

- Baseline backend: 606 passed, 1 warning, 23,35 s.
- Sau thêm runner/test và test budget/private reasoning: **614 passed**, 1 warning, 19,95 s.
- Ruff, format, OpenAPI --check, pip check và UTF-8/links/diff kiểm theo quy trình.
- Golden schema 60 hợp lệ, 24 author-evidence case đối chiếu artifact thành công; tất cả review vẫn pending.
- Page target match 20/23 factual, không gọi evidence Recall. Precision/Recall/MRR/correctness/faithfulness aggregate để null.
- Lượt auto duy nhất, không có baseline off để chứng minh causal benefit của web. Không gọi HTTP chat API,
  không test auth/rate-limit/UI/images và không multi-turn. Không có starting-class hay exact-stat-allocation case.

## Dùng lại

Từ backend, plan-only: `python -m scripts.diagnose_golden`.
Muốn chạy lại thật phải dùng execute/permission flags và output-dir mới, xem guide.
Không ghi đè report gốc. TV2 đọc review.md/report.json, chấm rubric và review nguồn/đáp án riêng;
không tự gán approved để tính điểm. Bộ 25 này đã dùng phát hiện lỗi nên thuộc tập development cho báo cáo cuối.
