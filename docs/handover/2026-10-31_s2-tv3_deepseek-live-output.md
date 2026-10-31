# Bàn giao kiểm tra DeepSeek thật và protocol recovery

31/10/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.
Nhánh `fix/s2-tv3-deepseek-live-output`, HEAD nền `35cce86`; giữ working tree chưa commit của các tác vụ trước.
Không stash/reset/rebase, không commit/push/PR/merge. Khi review/commit cần phân biệt các nhóm thay đổi.

## Sự cố và bằng chứng

User gặp 502 với “các boss trong elden ring” và cho phép gọi DeepSeek thật để sửa.
Đã dùng **5 completion thật**, không transport retry; không gọi thêm sau lượt 5.
[Báo cáo đầy đủ](../testing/2026-10-31_deepseek-live-output-fix.md) và năm JSON liên kết ở đó ghi phương pháp/giới hạn.

Phát hiện thật: một response insufficient=true vẫn chèn citation dù evidence rỗng. Validator chặn đúng,
nhưng code cũ không retry protocol này. Hai lượt đúng câu hỏi qua retrieval thật thành công; chưa tái hiện được
JSON lỗi của request lịch sử nên không gán nguyên nhân chắc chắn cho request đó.
Lượt 4 dùng replay lỗi tối giản và một completion thật cho recovery, không phải hai completion thật.

## Thay đổi thuộc tác vụ này

- [generator.py](../../backend/app/rag/generator.py): RAGValidationError với reason static;
  recovery `insufficient_with_citations` cùng ngân sách format 0/1. Lượt recovery non-thinking/temp 0,
  giữ nguyên evidence và kiểm validator đầy đủ. Trace có retry reason/thinking. Final diagnostic mức ERROR,
  thông báo lỗi phân biệt các nhóm đầu ra/provider. Không thay API schema/status.
- [answer.md](../../backend/app/rag/prompts/answer.md): insufficient không được kể facts/mô tả nguồn/citation;
  partial answer dùng đủ evidence và limitation đúng contract.
- [llm.py](../../backend/app/adapters/llm.py): safe HTTP status/error class, finish aborted/system resource.
- [test_llm.py](../../backend/tests/unit/test_llm.py), [test_live_chat.py](../../backend/tests/unit/test_live_chat.py):
  regression format recovery thinking true→false qua HTTP fake, protocol lặp vẫn fail, tắt retry,
  SSE trước/sau token và không leak diagnostics.
- [.env.example](../../.env.example), [RAG README](../../backend/app/rag/README.md), báo cáo và năm JSON live.

Không cắt bỏ citation/facts từ output lỗi rồi công bố lại. Không retry quote/schema sai hoặc mọi citation mismatch.
SSE đã gửi text không tự restart; lỗi không phát done thành công. Primary thinking giữ cấu hình, chỉ recovery đổi.
Không sửa .env thật, không đổi key, không index/upsert dữ liệu. Hai lượt dùng E5 cached để query và Qdrant đọc;
không tải model hoặc recreate collection. Không chỉnh frontend/bot trong lượt này.

## Kiểm tra thực tế

Baseline trước tác vụ: 467 passed, 1 warning. Sau sửa: **475 passed, 1 warning**, 19,74 giây.
Warning Qdrant memory về payload index giữ nguyên. Ruff check/format 4 file Python và OpenAPI check đạt.
5 completion: 1 protocol failure quan sát thật, 4 kết quả thành công (một trong đó là recovery sau replay).
Input/output token tổng: 16.486 / 2.367. Không dùng thống kê nhỏ này để tuyên bố tỷ lệ thành công tổng quát.
Live kiểm component pipeline, không toàn HTTP API/UI, không rewrite hoặc history cũ; raw reasoning không được đọc/lưu.

## Dùng và việc còn lại

Nếu chưa reload thì restart `make api`, tạo chat mới rồi thử câu người dùng. Không cần index lại.
Generation failed nay mức ERROR có reason/status/class đã lọc; dùng request_id đối chiếu khi còn lỗi.
Các unknown nguyên nhân lịch sử, semantic answer quality, escape trình bày và retrieval chưa sát vẫn cần theo dõi.
Validator kiểm quote/citation không chứng minh entailment. Không bảo đảm provider không bao giờ trả JSON lỗi nữa.
Hướng dẫn và các report xem liên kết trên; script chẩn đoán tạm/budget trong .venv không thuộc bản bàn giao.
