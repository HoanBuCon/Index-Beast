# Sửa câu chào và câu hỏi danh tính bị từ chối khi bật rewrite

| | |
|---|---|
| Ngày | 02/11/2026 |
| Người thực hiện | TV1 (Hoanbucon); rewrite thuộc TV3, web và bot thuộc TV4 |
| Nhánh | `fix/s3-tv1-rag-chao-hoi` (từ `develop` tại `d2c30d8`) |

## Hiện tượng

Với `RAG_REWRITE_ENABLED=true`, hỏi "Chào" hoặc "Bạn là ai" trên web nhận câu từ chối "Mình hỗ trợ các câu hỏi về Elden Ring…", kèm dòng "Chưa tìm được đủ bằng chứng trong kho nguồn."

## Nguyên nhân

Không phải lỗi hệ thống. Có hai vấn đề riêng:

1. **LLM rewrite xếp câu xã giao vào `out_of_scope`.** Prompt `rewrite.md` chỉ mô tả câu hỏi về game và yêu cầu từ chối việc không liên quan. Câu từ chối trong ảnh chỉ sinh ra từ nhánh `rewritten.out_of_scope` trong `app/rag/pipeline.py`.
2. **Nhãn "thiếu bằng chứng" gắn cho mọi `grounded=false`.** `grounded=false` còn gồm câu chào, câu từ chối và câu hỏi lại, nên nhãn này sai ở các trường hợp đó. Khi thật sự thiếu nguồn thì nội dung câu trả lời đã tự nói rõ. Bot có footer tương tự.

## Đã sửa

- `backend/app/rag/pipeline.py`: thêm `small_talk()`, nhận câu chào, câu hỏi danh tính, câu cảm ơn tiếng Việt (có hoặc không dấu) và tiếng Anh, rồi trả lời cố định. Không gọi LLM, không truy xuất. Chỉ khớp **nguyên câu**, nên "Chào Ranni là ai?" vẫn đi luồng RAG. `language()` nhận thêm `chao`, `cam on`.
- `web/src/components/chat/MessageList.tsx`: bỏ dòng "Chưa tìm được đủ bằng chứng trong kho nguồn."
- `bot/src/utils/format.ts`: bỏ footer "Chưa tìm được đủ bằng chứng."; chỉ đặt footer khi còn nội dung.
- Thêm test trong `backend/tests/unit/test_live_chat.py` và `bot/tests/ask.test.ts`.

**Đánh đổi:** ở chế độ `llm_only`, câu trả lời không còn nhãn báo là chưa có nguồn. Chế độ này chỉ dùng để thử nghiệm. TV4 có thể khôi phục nhãn nếu API trả thêm loại câu trả lời.

## Kiểm tra trên máy TV1

| Kiểm tra | Kết quả |
|---|---|
| Backend unit test, ruff | 548 passed; ruff đạt |
| Bot test, typecheck | 27 passed; typecheck đạt |
| Web test, typecheck | 30 passed; typecheck đạt |
| Web thật, `CHAT_MODE=rag`, rewrite bật: "Chào", "Bạn là ai" | Trả lời giới thiệu IndexBeast, không còn nhãn thiếu bằng chứng |

## Chưa kiểm tra

- Câu hỏi về game khi bật rewrite: chưa chạy với DeepSeek thật, chỉ có test bằng LLM giả.
- Câu xã giao khác mẫu (ví dụ "Bạn giúp được gì?") vẫn đi qua LLM rewrite và có thể bị từ chối.
- Bot chưa thử trên Discord thật.
