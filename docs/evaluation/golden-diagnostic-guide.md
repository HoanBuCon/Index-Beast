# Chẩn đoán 25 câu IndexBeast

Đây là tập phát triển để tìm lỗi hiện tại, không phải điểm đánh giá cuối của đồ án.
Chọn nguyên câu từ [golden set](../../backend/eval/golden_set.jsonl) theo
[manifest 25 ID](../../backend/eval/diagnostic_25.json). Không sửa câu hỏi/đáp án gốc, không thêm
đáp án tham chiếu vào prompt hoặc index để tự làm đẹp kết quả.

## Dữ liệu và phạm vi

Các nhóm: character/event/location làm đối chứng; mechanics/equipment/quest/multi-hop ưu tiên gameplay;
một câu build mạnh nhất thiếu điều kiện và một câu instruction injection. Ít nhất 50% VI.
Golden hiện chưa có câu liệt kê starting class hoặc tính stat allocation hợp lệ cụ thể;
không tuyên bố lượt này đã đo hai năng lực đó. Câu độc lập, history rỗng; không đánh giá hội thoại nhiều lượt.
Toàn bộ 60 source/answer cross-review đang pending ở thời điểm tạo bộ.

## Validation và kế hoạch (offline)

Từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m eval.validate_golden --corpus data/chunk_runs/s2-full-v1/chunks.jsonl
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_golden
```

Plan-only chỉ đọc JSON/JSONL, không load Settings/model, không client/network hoặc tạo report.
Validation kiểm schema và quote/hash đã khai báo; không chứng minh ngữ nghĩa hoặc tự approve TV2.

## Chạy thật (tốn API)

Từ backend, khi được phép dùng DeepSeek/Tavily và query embedding:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.diagnose_golden --execute --allow-llm --allow-web --mode auto --output-dir ../docs/testing/NEW_golden-25-auto
```

Tên thư mục phải mới, parent tồn tại dưới docs/testing; không ghi đè report cũ.
`--limit 5` chỉ chạy 5 ID đầu để kiểm runner, không phải mẫu đại diện gameplay.
`--mode off --allow-llm --execute` là baseline local riêng; không cần --allow-web cho off.
Mỗi lệnh execute là một lượt tốn API mới. Không tự retry cả bộ đến khi có kết quả đẹp.

Runner dùng pipeline thật; đọc Qdrant, query embedding với cache đã có và HF offline.
Không crawl/index/upsert/drop collection hoặc ghi PostgreSQL. Không gọi HTTP chat API, nên status lỗi
là exception/equivalent HTTP code, không phải đo trực tiếp endpoint, rate limit, persistence hay frontend.
Không gọi image resolver; không kết luận chất lượng ảnh. Không sửa .env thật.

Mỗi case giữ deadline tổng bằng CHAT_TIMEOUT_SECONDS, tối đa 4 logical model calls;
cả bộ tối đa 100 logical model calls và 50 Tavily request (Search+Extract, không retry).
SDK DeepSeek transport retry được đặt 0 trong runner để giới hạn chi phí; khác cấu hình app nếu app có retry.
Không bỏ lỗi, đổi expected_answer hoặc chuyển câu factual thành negative vì runtime thiếu bằng chứng.

## Artifact

- `report.json`: checkpoint atomic sau mỗi case, có snapshot config cho phép, input/prompt hashes, collection,
  query/trace, context thật, final answer/sources, lỗi và độ trễ.
- `model_outputs`: final content của rewrite/assessor/generator và token usage, không private reasoning/key.
  Output lỗi được giữ để điều tra, không có nghĩa đã được gửi cho người dùng.
- `review.md`: câu hỏi, tham chiếu draft, answer và context để đọc từng câu.
- `manual_review.jsonl`: mẫu chấm để trống; không giả là con người/TV2 đã chấm.

Nếu process bị ngắt, report status vẫn running và số case đã lưu cho biết tiến độ;
không báo complete chỉ vì có file. Case thất bại vẫn giữ nguyên và runner tiếp tục case sau.
Exit 0 của runner nghĩa là đã hoàn tất lượt chẩn đoán, không phải mọi câu đều đúng;
phải đọc summary.errors, từng case và review. Các cổng chất lượng cuối chưa được định nghĩa ở đây.

## Đọc kết quả

Đánh giá riêng: rewrite có giữ ý không; context có bằng chứng không; generator dùng bằng chứng đúng không;
lỗi là timeout/provider/protocol hay chỉ trả insufficient. Grounded chỉ xác nhận protocol quote/citation,
không phải correctness hay entailment.

`source_page_hit_at5` là tỷ lệ có ít nhất một URL trang tham chiếu (bỏ fragment) trong top-5,
không phải Recall của evidence. Một trang web khác có thể có đáp án đúng nhưng không trùng URL draft.
Chưa có nhãn relevance đầy đủ nên Precision/Recall/MRR để null; không lấy mọi chunk cùng trang làm relevant.

Chấm sơ bộ 0–2:

| Tiêu chí | 0 | 1 | 2 |
|---|---|---|---|
| Correctness | Sai trọng tâm/ý chính | Đúng một phần hoặc thiếu ý bắt buộc | Đúng các ý bắt buộc |
| Faithfulness | Claim chính không được evidence hỗ trợ | Có phần suy diễn/thiếu hỗ trợ | Claim thực tế được evidence hỗ trợ |

Không đánh cùng điểm cho sai kiến thức và thiếu evidence. Có thể để null khi chưa đủ căn cứ chấm.
`behavior_ok` đánh giá hành vi trong phạm vi, ngoài phạm vi, hỏi lại hoặc nhận thiếu bằng chứng.
Case lỗi không có answer hợp lệ phải tính vào tỷ lệ lỗi; không tự đánh faithfulness=2 vì không thấy hallucination.
Nhận xét nên chỉ ra claim/quote/tầng lỗi cụ thể, reviewer và trạng thái provisional.
Đánh giá hỗ trợ bởi AI phải ghi đúng như vậy; TV2 review chéo vẫn là bước riêng.

## So sánh sau này

Giữ snapshot bộ phát triển và baseline này, sửa một nhóm nguyên nhân rồi chạy lại cùng ID/cấu hình.
Muốn đo Tavily có ích hay không cần thêm lượt off với cùng 25 câu, không suy ra lợi ích từ một lượt auto.
Trong golden set cuối 200 câu, các câu đã dùng sửa hệ thống nên nằm tập development;
dành tập test mới chưa dùng chỉnh prompt để báo cáo cuối.
