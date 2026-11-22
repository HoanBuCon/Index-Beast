# Schema recovery và câu trả lời trực tiếp

- Ngày: 04/11/2026 · TV3 MinhMuc · nhánh `fix/s3-tv3-generation-response`.
- Yêu cầu: kiểm tra 502 khi hỏi “huong dan build katana”, sau đó bỏ cách kể quá trình tra cứu.
- Chỉ sửa local; chưa commit/push/merge. Không thay .env, corpus, Qdrant hoặc client.

## Phát hiện và giới hạn kết luận

Chưa nhận log/reason của request thật nên chưa xác nhận nguyên nhân cụ thể của lần 502 này.
Code kiểm tra thấy JSON hợp lệ nhưng thiếu/sai trường bị `schema_invalid` và trả 502 ngay,
không được hưởng format recovery. Đã tái hiện bằng fake provider trước khi thêm recovery;
không khẳng định mọi lỗi 502 có cùng nguyên nhân. Thiếu context hoặc insufficient hợp lệ
không tự gây 502; lỗi JSON, provider, quote và citation cần phân biệt.

## Thay đổi

- `backend/app/rag/generator.py`: thêm schema_invalid vào recovery chung 0/1 lần,
  recovery non-thinking, cùng evidence và validation đầy đủ. Không sửa/ép kiểu output để chấp nhận.
  Log ERROR `Generation failed` với reason tĩnh khi validation cuối thất bại, JSON và SSE.
- `prompts/persona.md`, `prompts/answer.md`: trả lời trực tiếp, không kể retrieval/nguồn cung cấp;
  giữ citation, không bịa hoặc giả đã xác minh. Thiếu thông tin nói rõ điều chưa xác nhận.
- `pipeline.py`, `overview.py`: thông báo không có context không kể thao tác tra cứu.
- Test mới `test_generation_schema_recovery.py`: schema thiếu/sai kiểu, retry tắt/giới hạn,
  không lưu output lỗi, bảo vệ quote, cleanup SSE, đúng câu katana với context không liên quan.
- Test cũ tách schema ra khỏi nhóm không-retry theo thay đổi hành vi có chủ đích;
  assertions transport/length/quote vẫn giữ. README RAG và danh sách handover cập nhật.

## Kiểm tra

- Baseline: 552 passed, 1 warning Qdrant memory, 19,93 giây.
- Sau sửa: toàn bộ unit 561 passed, 1 warning, 18,44 giây; sau đó bổ sung hai case katana,
  chạy riêng file mới: 12 passed, 0,29 giây (gồm hai case mới).
- Ruff check/format các file Python đã sửa, OpenAPI --check, pip check đạt.
- Không chạy model, query embedding, server hoặc DeepSeek thật. Fake không chứng minh chất lượng build
  hoặc phản hồi thật của provider. Không sửa lỗi bằng cách giả insufficient thay mọi lỗi upstream.

## Cách dùng và việc còn lại

Restart API (`make api` hoặc `make dev`), tạo chat mới và thử lại câu hỏi. Không cần index lại.
Recovery dùng ngân sách chung `RAG_FORMAT_RETRIES` và chỉ chạy SSE trước token đầu;
thất bại sau khi đã phát text vẫn báo error, không done thành công.

Nếu còn 502 cần log `Generation failed` / `RAG validation failed` cùng request_id để xác định
schema, citation, JSON hay provider. Chưa kiểm chứng live nên chưa tuyên bố dứt lỗi thực tế.

Yêu cầu câu trả lời tự nhiên đã áp dụng; chưa trộn kiến thức pretrained không kiểm chứng vào RAG
hoặc dựng web search. Đây là thay đổi chính sách/kiến trúc riêng, cần phân biệt provenance và grounding
nếu triển khai, không gán citation local cho thông tin chỉ có trong trí nhớ mô hình.
