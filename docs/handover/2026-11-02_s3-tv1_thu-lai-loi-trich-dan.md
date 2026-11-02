# Thử lại khi LLM trích dẫn sai giao thức và sửa thông báo 502 trên web

| | |
|---|---|
| Ngày | 02/11/2026 |
| Người thực hiện | TV1 (Hoanbucon); generator thuộc TV3, web thuộc TV4 |
| Nhánh | `fix/s3-tv1-thu-lai-loi-trich-dan` (từ `develop` tại `161c0ae`) |

## Hiện tượng

Hỏi "Marika đẻ được không ?" trên web nhận "Câu trả lời chưa hoàn tất" và "Không kết nối được dịch vụ". Log API ghi `RAGValidationError` rồi `POST /api/v1/chat 502` sau 2,9 giây.

## Nguyên nhân

1. `validate_answer` loại cả câu trả lời nếu có một đoạn không gắn `[n]` (`uncited_paragraph`), rồi trả 502. Log một request khác sau khi thêm thử lại cho thấy DeepSeek lặp lại đúng lỗi này ở lần thứ hai, nên thử lại không giải quyết được.
2. `web/src/api/client.ts` gộp 502 vào thông báo chung "Không kết nối được dịch vụ", nên lỗi kiểm tra trông như mất kết nối.

## Đã sửa

- `backend/app/rag/generator.py`:
  - **Bỏ đoạn không có trích dẫn** khi câu trả lời còn đoạn có trích dẫn hợp lệ, không gọi lại LLM. Số đoạn bỏ được ghi vào trace `dropped_uncited_paragraphs` và log, không ghi nội dung. Câu trả lời đủ trích dẫn giữ nguyên văn.
  - Thêm `citation_evidence_indices`, `unknown_quote_id` vào `RETRYABLE_REASONS`; nhắc lại quy tắc trích dẫn khi thử lại. Số lần thử vẫn theo `RAG_FORMAT_RETRIES`, và câu trả lời lần sau vẫn phải qua `validate_answer`.
- `web/src/api/client.ts`: 502 hiển thị "Chưa tạo được câu trả lời hợp lệ. Vui lòng thử lại."
- Test: `test_live_chat.py` thêm test bỏ đoạn và test thử lại; `chat.test.ts` thêm test 502; `uuid.test.ts` đổi chuỗi mong đợi theo thông báo mới.

**Cần TV3 xem lại,** vì đổi hai hành vi đã có test:
- `test_partial_answers_do_not_relax_existing_evidence_validation`: đoạn không có trích dẫn trước đây làm hỏng cả câu trả lời, nay bị bỏ. Đoạn đó vẫn không đến tay người dùng; test mới `test_uncited_gameplay_fact_is_never_shown` giữ điều này.
- `test_transport_length_grounding_and_schema_errors_do_not_trigger_format_retry`: câu trả lời hoàn toàn không có trích dẫn nay được thử lại một lần. Quote không có trong nguồn và lỗi schema vẫn không thử lại.

**Đánh đổi:** câu trả lời có thể mất câu dẫn hoặc câu kết nên đọc hơi cụt. Mỗi lần gặp `citation_evidence_indices` hoặc `unknown_quote_id` tốn thêm một lượt gọi DeepSeek.

## Kiểm tra trên máy TV1

| Kiểm tra | Kết quả |
|---|---|
| Backend unit test, ruff | 552 passed; ruff đạt |
| Web test, typecheck, prettier | 31 passed; typecheck và prettier đạt |

## Chưa kiểm tra

- Chưa chạy lại việc bỏ đoạn với DeepSeek thật. Lỗi `schema_invalid` và `quote_not_verbatim_or_index` vẫn trả 502.
- `/chat/stream` không rút lại được đoạn đã gửi: nếu đoạn không có trích dẫn đã được gửi cho người dùng thì vẫn báo lỗi. Thử lại cũng chỉ chạy khi chưa gửi token nào.
