# TV2 · Rà soát golden set S4 bằng artifact local

Ngày 16/11/2026, nhánh `docs/s4-tv2-golden-review-local`, tách từ `origin/develop` tại `9c2efd9`. Không có thay đổi local trước tác vụ. Chưa commit, push hoặc mở PR.

## Phạm vi và trách nhiệm

Theo yêu cầu TV3, rà toàn bộ 200 câu S4, 26 ca đã sửa và bằng chứng lượt bổ sung. Chỉ dùng corpus, artifact và report local, không gọi dịch vụ thật. Codex thực hiện thay phần việc TV2 — UncleThing; người dùng cho biết TV2 nhận trách nhiệm. Phiếu ghi rõ hình thức duyệt qua AI theo ủy quyền, không ghi nhận TV2 tự kiểm tra trực tiếp.

## Thay đổi và kết quả

- Tạo [meta-prompt](../prompts/2026-11-16_tv2-s4-golden-review-local.md) và tự thực hiện trên cả 200 câu.
- Cập nhật [phiếu review](../../backend/eval/reviews/s4-golden-set-review.jsonl): 198 `approved`, 2 `changes_requested`, không còn `pending`; từng ca có lý do và `performed_by=Codex`, `human_direct_review=false`.
- IB-GS-265 cần định danh rõ Heart of Bayle thay “tim riêng”; IB-GS-279 cần khóa lần gặp đầu của Diallos ở Roundtable Hold. Trong 26 ca từng sửa có 25 đạt, IB-GS-279 còn vấn đề.
- Bổ sung bằng chứng rà soát cho 6 ca trong metadata riêng; giữ nguyên golden set, primary evidence, followup và điểm benchmark lịch sử.
- Tạo [báo cáo chi tiết](../evaluation/2026-11-16_s4-tv2-local-review.md) và [JSON tổng hợp/hash](../evaluation/2026-11-16_s4-tv2-local-review.json); cập nhật trạng thái hiện hành tại [eval README](../../backend/eval/README.md).

## Kiểm tra thực tế

Đã chạy validator offline với corpus 39.574 chunk: 183 ca dữ kiện và 11 lượt bổ sung có quote khớp. Kiểm thêm các quote bổ sung, tổng 256 lượt quote khớp chunk ID, dòng, URL, slice và SHA-256. Đã so sánh trường đầu vào benchmark với Git HEAD, không thay đổi. Test `tests/unit/test_golden_set.py`: 9 đạt. Gate `--require-reviewed` chưa đạt đúng dự kiến do còn 2 ca cần chỉnh, không công bố cả bộ đã được nghiệm thu.

Đối chiếu report/mẫu corpus được thực hiện local; không có lần gọi DeepSeek/Tavily, benchmark, embedding/indexing, truy cập web hoặc thử website public. Kiểm UTF-8, liên kết local và `git diff --check` trước bàn giao.

## Việc còn lại

Chỉnh hai câu trong phiên bản tập đánh giá mới rồi rà lại, tránh đổi âm thầm manifest và điểm lịch sử. Độ khó chưa hiệu chuẩn với người chơi, nhãn release `unknown` chưa được xác nhận toàn bộ. Việc publish và kiểm demo trên giao diện là tác vụ riêng. Các tài liệu ngày 14–15/11 ghi trạng thái `pending` phản ánh thời điểm cũ; trạng thái mới nằm ở báo cáo ngày 16/11.
