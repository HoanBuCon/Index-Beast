# Bàn giao query VI → EN và benchmark theo tầng

31/10/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.
Nhánh `feature/s2-tv3-vi-en-retrieval`, HEAD nền `35cce86`.
Working tree đã có JSON recovery và nối ảnh web chưa commit: giữ nguyên, không stash/reset/rebase.
Thay đổi cũ vẫn cùng working tree; phải phân biệt khi review/commit. Chưa commit/push/PR/merge.

## Phạm vi và kết luận

Người dùng quan sát query EN thường tốt hơn VI. Trước sửa, rewrite chỉ kiểm schema/số liệu và chưa có so sánh ghép cặp.
Đã triển khai guard/fallback/budget và dual query opt-in; chưa chứng minh dense đa ngôn ngữ hoặc BM25 gây lỗi cụ thể.
Không chạy embedding/LLM/server thật, không đo recall/correctness mới. Không sửa dữ liệu gốc, .env thật hoặc index.

## Code và quyết định

- [rewrite.py](../../backend/app/rag/rewrite.py), [prompt rewrite](../../backend/app/rag/prompts/rewrite.md):
  English standalone query, giữ tên bề mặt/số liệu/mục tiêu và một số ý định/phủ định;
  output language do server quyết định, timeout 8 giây, max output 512 mặc định, một logical call.
  Unknown nickname không tự map; prompt yêu cầu ambiguity. Guard là heuristic, không phải semantic proof hoặc NER.
- [query_plan.py](../../backend/app/rag/query_plan.py): tối đa hai query khác nhau, rank fusion RRF,
  không cộng score native. Dedup point và exact content chỉ khi có provenance tương ứng; giữ khác biệt release,
  điều kiện, source type/review/spoiler/image metadata.
- [pipeline.py](../../backend/app/rag/pipeline.py): response language tách query; mode rewrite mặc định,
  dual opt-in; chia await budget 20 giây cho tối đa hai query. Một query lỗi có thể degrade sang query kia;
  tất cả lỗi không bị đổi thành "không có evidence". Đại từ chưa rõ vẫn hỏi lại khi rewrite lỗi.
  Context vẫn tối đa 5, giữ policy/filter/ID/metadata/ảnh. Không thay E5/BM25/schema collection/encoder.
- [config](../../backend/core/config.py), [.env.example](../../.env.example), [Compose](../../docker-compose.yml):
  mode/budgets có giới hạn, rewrite vẫn false. Thinking/temperature generation giữ nguyên.
- [13 cặp VI–EN](../../backend/eval/vi_en_pairs.jsonl), [benchmark](../../backend/scripts/benchmark_vi_en.py),
  [38 case test](../../backend/tests/unit/test_vi_en.py), cập nhật RAG/eval README.

Không thêm reranker model; NoReranker chưa phải reranking chất lượng cao. Không tự fallback llm_only/web search.
Không thay câu trả lời thiếu evidence bằng factual content không có nguồn. Các sửa JSON/SSE/citation/ảnh trước được giữ.

## Bộ câu và benchmark

26 câu = 13 cặp, 50% VI; tất cả pending, không tự approve hoặc tạo evidence labels.
Đã đối chiếu năm trang target với URL trong artifact local; đây chưa xác nhận chunk chứa đáp án.
Tên ở ngoặc là người dùng cung cấp rõ, không phải xác nhận một nickname Việt phổ biến.
Golden set 60 câu hiện có giữ nguyên.

Plan-only mặc định: chỉ đọc bộ câu, không client/model/network/write. Đã chạy ba strategy:
78 dòng, upper bound 52 logical rewrite call và 104 retrieval query nếu người dùng thực thi đủ bộ.
`--execute` mới cho embedding/Qdrant; `--allow-llm` bắt buộc cho rewrite/generation; --generate là opt-in riêng.
Output cần file JSON mới, ngoài data; không ghi đè dữ liệu/report cũ. Client có finally cleanup.

Report tách rewrite → retrieval/context → generation; source-page hit không phải evidence recall.
Expected chunk IDs cần review trước, nếu chưa có thì recall=null. Semantic correctness/faithfulness/rewrite-intent
chờ chấm tay; benchmark trực tiếp pipeline không đo HTTP status. Không dùng kết quả fake để báo chất lượng thật.

## Kiểm thử thực tế

Từ backend, `tests/unit` với pyproject.toml: baseline **429 passed, 1 warning**, 17,97 giây;
sau sửa **467 passed, 1 warning**, 16,56 giây. Thêm 38 case fake LLM/retriever/ranking, không inference CPU thật.
Warning Qdrant local không thực thi payload index giữ nguyên. Ruff check/format trên 6 file tác vụ,
OpenAPI check, pip check và CLI plan-only đạt. Không collect integration hoặc route test_llm ngoài unit.

## Người tiếp tục

Đọc [hướng dẫn cấu hình và benchmark](../testing/2026-10-31_vi-en-retrieval-guide.md) để có lệnh chính xác.
Chưa bật rewrite trên ứng dụng thật. Người dùng tự bật biến environment hoặc .env rồi restart API;
ưu tiên thử rewrite một query trước, so sánh dual sau khi có số liệu. Không cần reindex cho phần code này.
Rewrite tăng logical LLM call; dual tăng query embedding/Qdrant; SDK retry transport có ngân sách riêng.
Await timeout không bảo đảm dừng lập tức CPU trong thread encoder.

Vẫn cần TV2 review paired cases/chunk labels, benchmark VI–EN thật, đọc answer/context và đánh giá semantic.
Các khoảng trống corpus gameplay cũ không được sửa bằng dịch query; chuẩn bị artifact gameplay là tác vụ riêng.
