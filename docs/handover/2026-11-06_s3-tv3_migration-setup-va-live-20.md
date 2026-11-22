# TV3 — Migration, setup memory và hoàn tất 20 lượt thật

Ngày 06/11/2026 (Asia/Saigon) · MinhMuc · IndexBeast / 4 Hollows.
Nhánh `feature/s3-tv3-agent-semantic-memory`, local, chưa commit/push/merge.

## Phạm vi và kết quả

Người dùng đã khôi phục hạ tầng và yêu cầu chạy migration/setup. PostgreSQL/Qdrant/Redis sẵn sàng.
Đã kiểm DB đích `indexbeast` rỗng trước khi chạy `alembic upgrade head`: tạo schema 0001 rồi thêm 0002.
Không giả DB rỗng đã chứa revision 0001. Đã setup `conversation_memories` dense 384 cosine,
5 keyword indexes: conversation_id, owner, status, embedding_model, embedding_version.

Đã tiếp tục bộ test thật được cho phép từ tác vụ trước: **đúng 20 user turn**, DeepSeek + Tavily auto + E5 cache,
DB `indexbeast_agent_test_70e67916e0`, memory collection `ib_agent_test_70e67916e0` riêng.
Run kết thúc exit 0, report complete; không bị dừng vì chạy lâu và không gửi lượt 21.
48 logical model calls, 5 Search + 5 Extract; 20 HTTP 200 nhưng có lỗi chất lượng cần theo dõi.
Chi tiết câu hỏi/đáp án/nguồn và nhận xét ở [báo cáo live](../testing/2026-11-06_agent-memory-20-live/README.md).

Sau run: DB test 12 conversation, 40 messages, 22 memory rows (21 active, 1 superseded),
21 point memory, không có active memory chưa index revision mới nhất.
Recreate service giữ được chủ đề gia phả Marika và pending Moonveil; correction level 120 supersede level 100.
Đây là xác minh có giới hạn trên bộ development 20 lượt, không hứa chất lượng hay recall tổng quát.

Corpus giữ nguyên **18.368 point**, không reindex/drop/recreate. Không sửa `.env`.
Main DB mới setup vẫn 0 conversation/message; **settings thực tế vẫn chat_persistence=memory**.
Muốn dùng persistence đã setup cần restart với postgres và tạo conversation mới; RAM cũ không tự migrate.

## File của tác vụ tiếp nối này

- [Setup verification](../testing/2026-11-06_memory-setup.json): schema/count/collection thực tế.
- [Raw live report](../testing/2026-11-06_agent-memory-20-live/report.json): checkpoint đủ 20 lượt, giữ nguyên lỗi.
- [Resource verification](../testing/2026-11-06_agent-memory-20-live/resource-verification.json): read-only kiểm tra sau run.
- [Báo cáo và nhận xét live](../testing/2026-11-06_agent-memory-20-live/README.md).
- [agent.py](../../backend/app/rag/agent.py) và [regression test](../../backend/tests/unit/test_agent_durable.py): sửa guard query không được dùng.
- [Hướng dẫn agent/setup](../api/agent-semantic-memory.md), [RAG README](../../backend/app/rag/README.md), index handover.

Không ghi đè report preflight bị chặn trước đó. Các thay đổi/untracked từ tác vụ trước được giữ nguyên.

## Lỗi thực tế và quyết định

Câu Maliketh bị guard chặn nhầm: rewrite=false nhưng guard vẫn bắt unused search_query giữ nguyên dấu phẩy
trong `Leyndell, Ashen Capital`. Sửa chỉ kiểm query thực thi ở chế độ này; vẫn kiểm equality với câu gốc,
provenance tên/số/goal và giữ kiểm cả hai query khi rewrite=true. Replay offline + test negative đạt;
**chưa gọi lại DeepSeek để retest**, không thay raw report thành kết quả sau sửa.

Vẫn còn: build không có spread tám chỉ số, Great Stars acquisition insufficient dù web chạy được,
suy diễn phía cha/mẹ từ half-brother, báo xung đột giả giữa acquisition từ Ranni và mục đích quest Fia.
Không chữa bằng tăng temperature hay bỏ citation. Citation/quote validation chưa chứng minh entailment.
Nhận xét là trợ lý đánh giá sơ bộ; manual scores vẫn null, chờ TV2/người dùng review.

## Kiểm tra đã chạy

- Migration/setup thật thành công, read-only verify main/test PG và Qdrant sau run.
- Live 20/20 hoàn tất; 1 SSE qua in-process ASGI, không phải benchmark mạng/browser/Discord.
- Full unit **774 passed**, 2 warning, 25,96 giây; baseline trước tác vụ 771 passed.
- Ruff check + format check 214 file, pip check, OpenAPI check đạt.
- Không chạy lại web tests/build vì tác vụ này không sửa frontend; kết quả trước nằm trong handover agent.

## Cách tiếp tục

Từ gốc project, hướng dẫn chưa chạy thay người dùng:

```powershell
$env:CHAT_PERSISTENCE = "postgres"
make dev
```

Restart backend cũ, tạo conversation mới và giữ capability token trong client.
Cấu hình dùng lâu dài: người dùng đặt `CHAT_PERSISTENCE=postgres` trong `.env`, xem
[setup và contract](../api/agent-semantic-memory.md). Không phải index lại corpus.
Chưa triển khai nhớ xuyên tài khoản/cross-conversation, UI quản lý memory hay restore token mất.
Không tự dọn DB/collection test hoặc chạy thêm câu live khi chưa có yêu cầu mới.
