# Kiểm thử offline: LangGraph, history liên quan và giọng trả lời

06/11/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.

## Baseline thực tế sau revert

Workspace sạch, HEAD `eeccb93` trước khi sửa; nhánh ban đầu `feature/s3-tv3-semantic-chat-memory`.
Không dùng handover hôm trước làm bằng chứng tính năng còn tồn tại: code thực tế chưa có module
semantic memory, repository chat PostgreSQL hoặc LangGraph dependency.

`LiveChatService._history_for` lấy 8 message gần nhất theo default; pipeline truyền cả user/assistant
vào rewrite, evidence assessor và generation. Cách này cho phép prose cũ ảnh hưởng việc hiểu câu mới
và có thể cạnh tranh với evidence mới. Đây là nguyên nhân có thể xác định từ luồng code,
không phải kết luận rằng mọi đáp án sai đều do history hoặc đã đo được tỷ lệ lỗi live.

Baseline chạy từ `backend`:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
```

**709 passed, 1 warning, 22,42 giây**, không có test fail từ trước trong suite unit được chọn.

## Phạm vi thay đổi

- Preparation graph: scope → gameplay → memory → rewrite → retrieve → rerank → assess → optional web → context → prompt.
- Generation graph: generate → validate → finish hoặc một repair → generate. Mode mock và thành phần LCEL model giữ nguyên.
- Lexical recall user turn trong 64 message, chọn tối đa 3 trong budget cấu hình, provenance theo message/conversation/thời gian.
- RAG assessor/generator không nhận history; rewrite nhận user context đã chọn. Citation vẫn chỉ thuộc evidence local/web.
- Working state mới không lấy slot của task cũ; correction thay cả literal cũ trong query để không còn hai level/goal mâu thuẫn.
- Prompt trực tiếp, bỏ lời dè dặt/disclaimer chung; giữ quy tắc thiếu bằng chứng, speculation, citation và build feasibility.
- SSE backpressure, cancel/await graph/provider và deadline cả lượt gồm chờ lock.

Hướng dẫn/giới hạn và sơ đồ: [LangGraph memory](../api/langgraph-memory.md).

## Kiểm thử sau sửa

31 case mới trong `backend/tests/unit/test_memory_graph.py` kiểm hành vi:

- Câu độc lập không nhận transcript cũ; tên riêng và pronoun trong câu đủ chủ thể không làm lẫn topic.
- Tìm chủ đề cũ hơn 8 message trước khi áp dụng input budget; VI/EN, compound name, ambiguity và reset.
- Provenance, dedup, giới hạn số turn/ký tự/window, không lấy assistant claim làm subject/evidence.
- Sửa level/PvP, task mới bỏ weapon/location cũ, clarification rồi tiếp tục đúng task.
- Các nhánh off/auto/always; assessor không nhận memory; thiếu chủ thể không gọi model/tool.
- Khi web tắt, clarification vẫn hoạt động dù client chọn always.
- Graph construction không tạo HTTP client/encoder; invocation không chia sẻ state hoặc checkpoint.
- Retry JSON một lần, không truy vấn lại corpus, chỉ lưu một cặp message thành công.
- Lỗi sau token không retry/commit/done; timeout chờ lock không nhả lock của lượt khác; timeout stream đóng provider.
- Prompt vẫn yêu cầu truth/citation khi bỏ disclaimer chung.

Các test cũ về việc gửi nguyên transcript/assistant vào prompt được cập nhật theo yêu cầu hành vi mới,
và thêm assertion cấm assistant history; không xóa kiểm JSON, source, quote, build, retry hoặc API/SSE.
Missing referent nay hỏi lại trước model; test lỗi rewrite có history thật vẫn kiểm fallback/không search câu thiếu chủ thể.

Trong migration, test cancellation đã phát hiện provider có thể chạy trước consumer do graph scheduling.
Đã sửa acknowledgement ở provider bridge và stream graph, giữ test cleanup hiện có.
Test diagnostic retrieval cũng bắt việc trace không đi theo exception qua graph state copy;
đã gắn diagnostic tại node wrapper, giữ phân biệt lỗi retrieval với thiếu evidence.

Lượt toàn suite sau sửa: **740 passed, 1 warning, 21,56 giây**.
Warning duy nhất: payload index không có tác dụng ở Qdrant memory, giống baseline; không phải server verification.
Lượt toàn suite cuối đã bao gồm sửa import/catch dư thừa, subject viết thường trong khung gia phả
và guard không search khi rewrite chưa resolve entity. Không nới validator.

Các lệnh kiểm tra đã chạy từ `backend`:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check app core scripts tests/unit/test_memory_graph.py tests/unit/test_live_chat.py tests/unit/test_vi_en.py tests/unit/test_chat_guard.py
.venv/Scripts/python.exe -m ruff format --check app core scripts tests/unit/test_memory_graph.py tests/unit/test_live_chat.py tests/unit/test_vi_en.py tests/unit/test_chat_guard.py
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```

Ruff check và format đạt (106 file); pip không phát hiện dependency hỏng; OpenAPI check đạt, schema public không đổi.
Đã kiểm UTF-8 và 111 liên kết local trong 6 tài liệu; `git diff --check` đạt.
`langgraph==1.2.20` đã được cài vào virtualenv bằng constraints cũ; chỉ thêm 5 package LangGraph/ormsgpack,
không nâng pin LangChain/FastEmbed/Qdrant. Requirements và constraints cùng được cập nhật.
Không dùng pip freeze Windows ghi đè constraints cho Linux.

## Giới hạn kiểm chứng

Không gọi DeepSeek/Tavily, tải/chạy embedding, index corpus, ghi server DB/vector, chạy migration/crawl/notebook,
sửa `.env` thật hoặc commit/push/merge. Không chạy lại golden set bằng API thật.
Không cần PostgreSQL migration hoặc collection memory setup vì vẫn dùng RAM hiện có.

Đã dùng provider/retriever giả trong test; suite cũ có Qdrant memory/vector tổng hợp.
Không đo chất lượng tìm kiếm ngữ nghĩa, Recall@k, faithfulness hay giọng văn thực tế của DeepSeek trong tác vụ này.
740 test đạt không chứng minh chất lượng đáp án live, cải thiện recall hoặc không còn mọi lỗi 502.
Corpus/route/build knowledge không được bổ sung hay thẩm định lại.

Chưa có semantic memory, durable chat, checkpoint hoặc cross-chat identity. Không tuyên bố nhớ lâu dài.
Web UUID không xác minh ownership; không mở rộng memory ra ngoài conversation đang routing.
Parser lexical/slot có grammar giới hạn, tên thường/nickname hoặc paraphrase khác ngôn ngữ có thể chưa resolve.
SRS/ADR/architecture tổng thể và tài liệu sinh cần nhóm đồng bộ riêng nếu chấp thuận hướng migration;
không tự sửa các báo cáo cũ để biến kết quả lịch sử thành kết quả mới.

Các bước cài dependencies, restart và thử hội thoại thật là **hướng dẫn chưa chạy**, xem tài liệu API liên kết trên.
