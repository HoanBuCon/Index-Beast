# TV3 — LangGraph, history liên quan và prompt trực tiếp

06/11/2026 · MinhMuc · IndexBeast / 4 Hollows.

## Phạm vi và Git

Triển khai lại sau revert theo code thực tế tại HEAD `eeccb93`.
Nhánh mới `feature/s3-tv3-langgraph-relevant-memory`, tách từ HEAD local của nhánh cũ
`feature/s3-tv3-semantic-chat-memory` với working tree sạch; không fetch/rebase/stash/reset.
Chưa commit/push/merge, chưa có PR hoặc Trello Done. Trước PR cần đồng bộ develop theo quy ước nhóm.

## File và quyết định

| File | Thay đổi |
|---|---|
| `backend/app/rag/history.py` | Lexical recall user turn, budget/provenance/dedup, ambiguous thì hỏi lại |
| `backend/app/rag/pipeline.py` | Preparation StateGraph, gameplay/memory/rewrite/retrieval/assess/web; history chỉ vào rewrite trong RAG |
| `backend/app/rag/generator.py` | Generation StateGraph, validation và bounded repair, bridge stream có backpressure |
| `backend/app/adapters/llm.py` | Acknowledgement để provider không chạy trước consumer và được đóng khi hủy |
| `backend/app/services/chat.py`, `gameplay.py` | Candidate history trước budget, task slot isolation/correction, commit sau thành công, SSE deadline gồm lock |
| `backend/app/rag/prompts/{persona,answer,rewrite,llm_only}.md` | Giọng trực tiếp, không kể tra cứu/disclaimer chung, vẫn giữ truth/citation |
| `backend/requirements.txt`, `constraints.txt` | LangGraph 1.2.20 và 4 pin transitive; giữ dependency cũ |
| `backend/tests/unit/test_memory_graph.py` | 31 case mới về memory, graph, retry, scope, streaming/deadline |
| `backend/tests/unit/{test_live_chat,test_vi_en,test_chat_guard}.py` | Cập nhật kỳ vọng transcript/assistant theo hành vi mới; giữ validator và contract assertions |
| `.env.example` | Giải thích lại history budget, không đổi giá trị và không sửa `.env` thật |
| `backend/app/rag/README.md`, `docs/api/gameplay-clarification-tv4.md` | Đồng bộ luồng hiện hành |
| `docs/api/langgraph-memory.md` | Sơ đồ graph TD, thuật toán/budget, persistence/auth limits, cách chạy/rollback |
| `docs/testing/2026-11-06_langgraph-memory.md`, handover/index | Kết quả thực tế và ranh giới kiểm chứng |

History cũ nạp 8 message gồm assistant vào rewrite/assessor/generator; nay chỉ chọn user turn liên quan
trong tối đa 64 message của đúng conversation, tối đa 3 và không vượt cấu hình budget.
RAG generation/assessor nhận history rỗng; query đã resolve và evidence mới là input trả lời.
Không biến memory thành nguồn game, không lấy assistant answer làm kiến thức đã xác minh.

Giữ mock/llm_only/rag, off/auto/always, Discord auto, API JSON/SSE/conversation/feedback/images/citation.
Auth và lock ở service trước graph; images và commit sau graph thành công. Không sửa frontend/bot hoặc schema API.
Retry có tối đa một repair; không re-search hoặc vòng lặp đến khi có đáp án. Missing evidence bình thường không phải lỗi 502;
output vẫn sai sau budget/lỗi upstream thật vẫn trả error, không gửi done thành công.

## Kiểm tra thực tế

- Baseline sau revert: **709 passed**, 1 warning, 22,42 giây.
- Sau triển khai: **740 passed**, 1 warning, 21,56 giây; thêm 31 case.
- Ruff check/format, pip check và OpenAPI check đạt.
- Đã sửa lỗi cancellation do provider chạy trước consumer; test hiện có về đóng stream/abandon/cancel được giữ.
- Dependency LangGraph cài bằng constraints, không nâng model/client cũ; không chạy model thật.

Chi tiết lệnh, failure đã tìm được và giới hạn trong [báo cáo offline](../testing/2026-11-06_langgraph-memory.md).
Hướng dẫn dùng và sơ đồ trong [tài liệu graph/memory](../api/langgraph-memory.md).

## Cách chạy và giới hạn

Người dùng tự cập nhật virtualenv bằng requirements-dev + constraints rồi `make dev`; xem lệnh chính xác trong tài liệu API.
Không cần reindex, migration hoặc sửa `.env` để dùng graph/recall. `CHAT_MODE=mock` vẫn là default code.
Đặt history messages hoặc chars bằng 0 sẽ tắt recall, không quay về nạp transcript.

**Bản này là lexical recall trong RAM, chưa có semantic embedding hoặc trí nhớ dài hạn.**
Conversation giới hạn 64 message/LRU 500; pending/player state TTL 30 phút, mất sau restart/eviction.
Không có PostgreSQL chat persistence/checkpointer mới; biến CHAT_PERSISTENCE không tự kích hoạt lưu trữ sau revert.
Không tìm xuyên conversation; web UUID chưa là quyền sở hữu được xác minh. Không có profile cá nhân đã xác minh trong shared thread.

Không gọi DeepSeek/Tavily, tải/chạy embedding, ghi server PostgreSQL/Qdrant, index/crawl/notebook hoặc chạy migration.
Không sửa corpus, golden set/report cũ hoặc `.env` thật. Các lệnh thử app thật chỉ là hướng dẫn, chưa chạy.
Chưa đo recall semantic, chất lượng trả lời live hoặc độ tự nhiên của model; test fake không chứng minh các điều này.

Tài liệu cần nhóm đồng bộ tiếp nếu duyệt kiến trúc: `docs/02_SRS.md`, `docs/04_ARCHITECTURE.md`,
`docs/indexbeast-system-pipeline.md`, ADR liên quan và kế hoạch/bản sinh nếu yêu cầu thay đổi.
Không tự sửa chúng trong tác vụ để tránh lẫn quyết định kiến trúc mới với báo cáo cũ.
