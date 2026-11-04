# Query web, excerpt và chẩn đoán citation 502

Ngày 04/11/2026 · TV3 MinhMuc · nhánh `fix/s3-tv3-web-query-excerpts`, từ develop tại `79b50f5`.
Không commit/push/merge. Git ban đầu sạch; phần Tavily trước đó đã vào develop qua PR #70.

## Yêu cầu và phát hiện

User gặp 502 request `6f1f0e19-b594-47df-90f8-900d26cfcd1b` ở `validate_answer`, nhưng chưa có
reason/response mô hình nên chưa xác nhận nhánh validation nào của request đó. User tiếp tục gửi
đoạn trang Fextralife Classes có nhiều navigation và câu “Các class khởi đầu của elden ring”.
Đoạn gửi là trang đúng game; không kết luận search đã tìm sai game. Code xác nhận rewrite fallback
có thể giữ query gốc, query web chưa luôn có domain anchor, Extract chưa nhận query và chọn đầu trang.

## Thay đổi

- `app/rag/web_query.py`: giữ query và constraints, thêm Elden Ring nếu thiếu; nhận diện intent class
  khởi đầu để thêm English search focus. Không thêm dữ kiện về class hoặc đoán entity.
- `pipeline.py`: áp dụng plan web; trace query_kind luôn có, query text chỉ khi diagnostic opt-in.
- `adapters/tavily.py`: gửi query/chunks_per_source cho Extract; clean/rank excerpt trước khi tạo WebHit.
- `app/rag/web_content.py`: bỏ markup ảnh/link (giữ nhãn), navigation có marker trước H1,
  giữ bảng và thứ tự block trong excerpt; lexical coverage chọn nhóm block, tối đa 3 excerpt/page.
  Không truncate bảng lớn. Metadata content_processing cho text đã xử lý; quotes được kiểm trên text này.
- `prompts/answer.md`: q0 chỉ hợp lệ nếu có trong evidence_units của đúng source; đoạn dài dùng q1/q2
  đã cấp. Không copy Markdown URL/image vào answer.
- `generator.py`: model_url/invalid_limitation được sinh lại tối đa 1 lần trong budget chung;
  cùng context, vẫn full validation; không tự sửa citation hoặc bỏ validation. Quote bịa vẫn fail.
- `app/api/errors.py`: log app error cho RAGValidationError có reason tĩnh; public error schema giữ nguyên,
  không đưa output/raw prompt/key vào log. Giúp xác định lỗi khi user chỉ gửi traceback cuối.
- Tests: thêm regression Classes/nav, query game/intent/constraints, bảng/quest order, protocol retry,
  central error log. Bốn assertion query cũ cập nhật prefix Elden Ring có chủ đích, giữ tên/ý định và history.
- [Contract cập nhật](../api/web-search-tv4.md).

## Kiểm chứng

- Baseline: 593 passed, 1 warning Qdrant memory, 19,10 giây.
- Sau sửa: **606 passed**, 1 warning, 21,78 giây. Ruff check đạt; format các file đã sửa.
- OpenAPI --check và pip check đạt. UTF-8, links và git diff --check được kiểm.
- Không gọi Tavily/DeepSeek thật, không chạy embedding/index hoặc ghi DB/server, không sửa .env.
  Tests dùng MockTransport/fake; không phải benchmark chất lượng tìm kiếm thật hay đủ kiến thức gameplay.

## Giới hạn / cách thử

Restart API và thử lại câu Classes với ON/ALWAYS. Chưa chứng minh lỗi 502 lịch sử đã dứt;
nếu lặp lại, gửi log app error có reason/request_id. Recovery không chạy sau token SSE đã hiển thị.
Lexical rank chỉ là bước chọn nội dung đơn giản, không semantic relevance guarantee.
Nếu provider trả thiếu nội dung hoặc bảng >3500 ký tự bị loại, chưa tự phục hồi bảng.

Ảnh web **chưa triển khai**. Đã giải thích cho user: Source response chỉ gồm nguồn được trích,
không ép tối thiểu nhiều nguồn. Thêm ảnh cần pipeline media riêng, không lấy logo/menu làm ảnh nội dung.
Không thay đổi max_results, top-5 hoặc bỏ qua scope/source policy để làm đẹp kết quả.
