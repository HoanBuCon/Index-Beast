# Bàn giao nhánh câu hỏi tổng quan

31/10/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.
Nhánh `feature/s2-tv3-overview-routing`, tách HEAD `03babb0` từ nhánh công việc hiện tại.
Working tree lúc bắt đầu sạch; giữ các thay đổi bảo vệ API/timeout của TV1 đã có trong HEAD.
Chưa commit/push, chưa tạo PR/merge. Không sửa .env thật hoặc dữ liệu gốc.

## Đã sửa

- [overview.py](../../backend/app/rag/overview.py): nhận diện overview VI/EN bằng cue/topic và guard tên riêng bảo thủ;
  hai query tối đa, English focus kèm nguyên question/conditions, metadata preference và đa dạng section/source.
  Không model call lúc routing/import, không corpus scan ở startup, không tạo kiến thức mới.
- [pipeline.py](../../backend/app/rag/pipeline.py): route overview trước rewrite, không ép entity khi topic rõ;
  giữ scope/injection gate trước routing, review/spoiler policy tại chọn context, top-5/budget hiện có.
  Câu named entity và tham chiếu mơ hồ vẫn luồng cũ. Thiếu context hỏi cách thu hẹp tổng quan.
- [overview prompt](../../backend/app/rag/prompts/overview.md), [rewrite prompt](../../backend/app/rag/prompts/rewrite.md):
  câu rộng hợp lệ; tổng hợp grouping/ví dụ có nguồn, partial answer thay từ chối vì thiếu danh sách đầy đủ,
  không bịa taxonomy/count/current patch/canon. Giữ normal evidence/JSON/limitation rules.
- [config](../../backend/core/config.py), [.env.example](../../.env.example), [Compose](../../docker-compose.yml):
  `RAG_OVERVIEW_ENABLED=true` mặc định, tắt được. Không đổi RAG_REWRITE_ENABLED, thinking hoặc key thật.
- [benchmark](../../backend/scripts/benchmark_vi_en.py): tính query upper bound của overview, report ghi flag
  để tránh nhầm tác dụng routing với rewrite khi so sánh. Không chạy benchmark inference thật.
- [40 case mới](../../backend/tests/unit/test_overview.py), [RAG README](../../backend/app/rag/README.md),
  [báo cáo và hướng dẫn](../testing/2026-10-31_overview-routing.md), [mẫu ordering artifact](../testing/2026-10-31_overview-ordering.json).

## Kiểm chứng

Baseline **483 passed, 1 warning**, 21,31 giây; cuối **523 passed, 1 warning**, 18,42 giây.
Ruff check/format 5 file Python của tác vụ, OpenAPI check, pip check đạt. Warning Qdrant memory giữ nguyên.
Full unit bao gồm JSON/SSE/citation/ảnh/ba mode và guard API/timeout của team; không xóa assertion cũ.
Đã đọc artifact để xác nhận title overview hiện có và chạy preference metadata trên 5 chunk mẫu, payload/ID giữ nguyên.
Đây không phải đo recall hoặc generation thật. Không gọi DeepSeek, chạy embedding/model hoặc server thật trong lượt này.

## Quy tắc tiếp tục

Overview priority chỉ là metadata routing, không semantic reranking. Không dùng query hints làm evidence.
Không đánh đồng câu rộng với thiếu referent, nhưng heuristic không nhận diện được mọi câu tự nhiên/tên viết thường.
Nguồn chỉ phủ một phần phải nói partial, không tuyên bố exhaustive/current/approved hoặc tự lấy kiến thức model.
Không bypass citation/review/spoiler/release; source metadata và liên kết ảnh giữ nguyên.
Routing không thêm LLM call, có thể thêm một query embedding/Qdrant, luôn trong tổng budget và tối đa 2 query/top-5.

Không cần reindex. Restart `make api` nếu chưa reload, tạo chat mới rồi thử các câu trong hướng dẫn.
Không cần thêm flag vào .env để nhận default true. Muốn tắt/benchmark cô lập rewrite thì tự đặt flag false và restart.
Chưa có kiểm thử model/browser/Discord thật cho nhánh mới. Dữ liệu thiếu và liệt kê toàn bộ corpus là giới hạn còn lại.
Các file SRS/ADR/planning, frontend/bot và persistence không chỉnh trong tác vụ này.
