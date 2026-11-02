# Bàn giao sửa lỗi JSON output của RAG

TV3 — MinhMuc · 31/10/2026 · IndexBeast / 4 Hollows.
Nhánh `fix/s2-tv3-rag-json-output`, tách develop tại `35cce86`. Chưa commit/push/PR/merge.

## Sự cố và kết luận

Sau PR #47, người dùng vẫn gặp 502, log xác định `invalid_json` dù provider kết thúc `stop`.
Nguyên nhân trực tiếp là content không parse được, không phải nhánh không có context.
Không lưu raw output lịch sử nên chưa thể kết luận ký tự/cơ chế provider gây sai.
Lần sửa trước tăng diagnostic/prompt; lần này bổ sung phục hồi định dạng có giới hạn.

[Báo cáo phân tích, bằng chứng và lệnh kiểm tra](../testing/2026-10-31_rag-json-recovery.md).
Hai lượt live được duyệt ở tác vụ trước đã hết: lượt này **không gọi DeepSeek thật**.

## File và quyết định

- [output.py](../../backend/app/rag/output.py): decoder toàn response dùng chung JSON/SSE, bỏ BOM hoặc
  một fence hoàn chỉnh; không extract JSON con hoặc sửa nội dung. Chặn duplicate key/NaN/phần dư/giới hạn.
- [generator.py](../../backend/app/rag/generator.py): retry format tối đa một lượt, cùng evidence/history,
  không đưa output lỗi vào prompt, không retry sau token stream đầu tiên; log vị trí parse an toàn.
  Giữ schema/citation/quote validation, cleanup/cancellation và fail-closed. Usage JSON cộng các attempt đã báo.
- [pipeline.py](../../backend/app/rag/pipeline.py), [config.py](../../backend/core/config.py),
  [.env.example](../../.env.example), [Compose](../../docker-compose.yml): `RAG_FORMAT_RETRIES=1` mặc định,
  chỉ nhận 0/1. Có thể tăng phí/độ trễ một generation khi format sai. SDK transport retry là cơ chế riêng.
- [answer.md](../../backend/app/rag/prompts/answer.md): bắt buộc JSON kể cả thiếu evidence,
  history text không phải mẫu output. Giữ persona/ngôn ngữ và chính sách evidence.
- Unit [parser](../../backend/tests/unit/test_rag_output.py), [wire LLM](../../backend/tests/unit/test_llm.py),
  [live chat](../../backend/tests/unit/test_live_chat.py), [config](../../backend/tests/unit/test_config.py);
  cập nhật [RAG README](../../backend/app/rag/README.md).

Không đổi .env thật, algorithm retrieval/ID/vector hoặc data; không sửa frontend/Discord/persistence/API schema.
Không tự chuyển thinking/non-thinking hoặc llm_only. Không retry schema/grounding/length/network.
Không biến lỗi provider thành câu "không có dữ liệu" để giấu 502.

## Kiểm tra thực tế và giới hạn

Baseline **377 passed, 1 warning**; kết thúc **429 passed, 1 warning**, 17,09 giây, thêm 52 case.
Ruff check/format trên 8 file Python, pip check và OpenAPI check đạt.
Giữ warning Qdrant memory không thực thi payload index. Các bài kiểm tra đều offline, có HTTP transport giả
qua LangChain/SDK thật, TestClient cho API và stream; không gọi provider/model/server DB thật.

Test xác nhận retry tối đa một lần, insufficient không lỗi, source metadata không bị thay và invalid output
không ghi history; SSE không tự restart sau khi đã gửi text, lỗi không có done thành công.
Không khẳng định entailment hoặc độ tin cậy model thật. Stream retry chưa có token usage.

## Người tiếp tục

Restart bằng `make api` nếu worker chưa reload; không cần reindex. Biến mới chưa có trong `.env` vẫn dùng default.
Tắt generation bổ sung bằng `RAG_FORMAT_RETRIES=0` rồi restart. Đây là hướng dẫn, chưa chạy API thay người dùng.
Khi test thật, lưu request_id và log lỗi đã lọc, không chia sẻ raw output/reasoning/key.
Provider trả JSON sai liên tục vẫn lỗi sau lượt cuối; cần số liệu live mới để đánh giá tỉ lệ phục hồi.
Review diff rồi tạo PR về develop khi được yêu cầu, không tự merge.
