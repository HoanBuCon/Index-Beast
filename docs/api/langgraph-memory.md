# LangGraph và ký ức hội thoại liên quan

> Tài liệu này mô tả bản lexical đầu tiên. Bản model decisions + semantic memory PostgreSQL tiếp theo
> được mô tả trong [agent-semantic-memory.md](agent-semantic-memory.md); mặc định agent=true,
> persistence vẫn RAM cho đến khi operator setup và bật PostgreSQL.

06/11/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.

## Phạm vi bản triển khai

LangGraph thay orchestration LCEL tuyến tính bằng hai graph: chuẩn bị request và generation.
Model/prompt/retriever tiếp tục là component LangChain hiện có. Không phải agent tự do dùng tool tùy ý;
policy server, số truy vấn, top-5, ngân sách và validator vẫn quyết định phạm vi.

API/auth và lock conversation chạy trước graph. Sau graph thành công, service chọn ảnh và commit
conversation/player state, rồi trả JSON hoặc gửi `sources`/`done`. Mode mock dùng service cũ.
Web/Discord không phải đổi schema; nguồn/citation/image vẫn trong contract server hiện có.

## Sơ đồ triển khai

Cập nhật 22/11/2026: chỉ còn một luồng RAG; Agent decision + Tool Agent + Assessor được thay bằng một vòng lặp Agent
gọi tool ([ADR 006](../adr/006-true-agent.md)). Trước đó đã gỡ rewrite, overview heuristic, `llm_only` và tính năng tránh spoiler.

```mermaid
graph TD
    A["Chat JSON hoặc SSE"] --> B["API validation, guard, conversation routing, lock"]
    B --> S["scope: mode, ngôn ngữ tạm, web policy"]
    S --> M["memory: ứng viên user turn (RAM) hoặc semantic memory (PostgreSQL + Qdrant)"]
    M --> D["agent: vòng lặp Agent gọi tool (search_corpus/web, check_name, open_evidence, set_conditions, calculator)"]
    D -->|"reply, ask_user"| P["prompt"]
    D -->|"finish: yêu cầu, intent, ngôn ngữ, bằng chứng"| X["context: admission, dedup, top-5, budget"]
    X --> P
    P --> E["generate: static, JSON hoặc stream (mọi câu được giữ tới khi kiểm xong mới gửi)"]
    E --> V["validate: JSON, citation, quote, URL; đếm đoạn không trích dẫn"]
    V --> VQ{"Kết quả?"}
    VQ -->|"Lỗi protocol được sửa, còn 1 lần"| F["repair: cùng câu hỏi và evidence, non-thinking"]
    F --> E
    VQ -->|"Bảng chỉ số sai/thiếu hoặc lộ tên trường nội bộ"| G["Answer Guard: một lượt LLM sửa, kiểm lại"]
    G --> Z["finish generation graph"]
    VQ -->|"Thành công"| Z
    VQ -->|"Sai lệch nguồn hoặc hết lượt sửa"| ER["Lỗi có phân loại; không gửi done thành công"]
    Z --> IM["Service: ảnh tùy chọn, lưu turn và working state"]
    IM --> OUT["JSON hoặc SSE sources, done"]
    IM -.-> NEXT["Người dùng trả lời clarification trong request mới"]
    NEXT -.-> A
```

Các node `scope` đến `prompt` thuộc `ChatPipeline.prepare_graph`. `generate`, `validate`, `repair`, `finish`
thuộc `Generator.graph`; Answer Guard chạy trong bước validate khi phát hiện lỗi trình bày (bảng chỉ số, tên trường nội bộ).
Auth, lock, optional images và commit ở service boundary, không giả chúng là graph node.

## Ký ức được chọn thế nào

- RAM (`CHAT_PERSISTENCE=memory`): Agent nhận tối đa hai user turn gần nhất làm ứng viên, tự quyết định có dùng không.
- PostgreSQL: semantic memory trong collection Qdrant riêng đưa ra ứng viên; Agent chọn ID liên quan (`selected_memory_ids`).
- Chỉ user turn làm ký ức; câu trả lời của assistant không bao giờ là bằng chứng.
- Server chỉ kiểm provenance: constraint và tên riêng Agent dùng phải có trong lời người dùng.

## Ký ức khác bằng chứng

| Thành phần | Được nhận gì | Vai trò |
|---|---|---|
| Vòng lặp Agent | Câu hiện tại, điều kiện người chơi, ứng viên ký ức, câu đang hỏi lại; kết quả tool | Hiểu yêu cầu, ghi điều kiện, tìm và chọn bằng chứng, hỏi lại, gọi calculator, tự đánh giá đủ/thiếu |
| RAG generator | Câu đã resolve + numbered evidence, history rỗng | Trả lời và trích dẫn |
| Answer Guard | Câu trả lời + lỗi trình bày (bảng chỉ số, tên trường nội bộ) | Sửa đúng lỗi đó, không thêm dữ kiện hay nguồn |

Memory không biến thành Hit, Document hoặc source index; assistant từng nói sai không thể tự chứng minh đáp án mới.
Ngôn ngữ trả lời độc lập query retrieval; history không được phép đổi tiếng Việt thành trả lời tiếng Anh.

## Working state, lưu trữ và quyền truy cập

| Thành phần | Hiện lưu ở đâu | Qua restart? |
|---|---|---|
| Conversation hiển thị | RAM, tối đa 64 message/conversation, LRU 500 conversation | Không |
| Memory được chọn | State riêng của một graph invocation | Không |
| Player slot và pending clarification | RAM của conversation, TTL 30 phút | Không |
| Graph checkpoint | Không cấu hình checkpointer | Không có |
| Corpus local | Qdrant/PostgreSQL hiện có, không chỉnh trong task này | Theo hệ lưu trữ hiện có |

Player slot là working state của task, không phải hồ sơ người chơi lâu dài. Task mới bỏ slot cũ;
correction trong task thay level/goal/weapon cũ cả trong working query. Lỗi hoặc hủy trước commit không đổi player state.

Chỉ tìm trong conversation đang được routing; không tìm xuyên conversation hoặc chia sẻ profile giữa người dùng.
Channel/external_ref được kiểm như trước. **Web hiện chưa có danh tính tài khoản/capability xác minh ownership**:
biết UUID conversation không chứng minh quyền sở hữu. Bản này không nâng mức bảo đảm auth của API cũ và không
thêm endpoint tìm ký ức toàn cục. Không dùng shared Discord thread làm hồ sơ cá nhân đã xác minh.
Muốn nhớ xuyên phiên/cross-chat cần thiết kế identity + quyền truy cập + persistence/retention riêng trước.

Không có `CHAT_PERSISTENCE` mới trong code sau revert. Chỉ thêm biến `CHAT_PERSISTENCE=postgres` vào `.env`
không làm chat tự lưu PostgreSQL. Không có migration hoặc collection memory cần setup cho bản này.

## Retry, web và streaming

- `off`: không assess/search web; `auto`: assess local, search khi chưa đủ hoặc assessment lỗi;
  `always`: search với câu hỏi game cần tra cứu. Chào hỏi và hỏi làm rõ không cần web.
- Discord vẫn ép `auto`, không lấy chế độ từ web client.
- Search/Extract giữ giới hạn của adapter hiện có; không retry tool trong graph hoặc chạy vòng tìm kiếm vô hạn.
- `RAG_FORMAT_RETRIES` giữ 0 hoặc 1. Lượt sửa dùng cùng evidence, non-thinking, temperature 0;
  không gọi lại retrieval/search và vẫn qua validator. Lỗi mạng/quote không nguyên văn không được biến thành đủ bằng chứng.
- Giới hạn recursion prepare/generation là 24/12; không gắn RetryPolicy tự lặp tool.
- Một queue bounded và acknowledgement nối graph với SSE: consumer nhận tiếp thì provider mới tiếp tục.
  Hủy stream sẽ cancel và await tác vụ graph/provider. Từ 21/11 câu trả lời chỉ được gửi (một event `token`) sau khi
  kiểm và Answer Guard xong, nên lỗi sinh câu luôn xảy ra trước token đầu: được sinh lại, hoặc trả lỗi HTTP JSON.
- `CHAT_TIMEOUT_SECONDS` (45 giây, JSON/Discord) và `CHAT_STREAM_TIMEOUT_SECONDS` (90 giây, web SSE) bao gồm chờ lock,
  preparation (tối đa `CHAT_PREPARE_TIMEOUT_SECONDS`), generation/repair/Answer Guard và ảnh; SSE tiếp tục dùng deadline
  của cùng lượt sau token đầu. Timeout/lỗi không lưu turn thành công hoặc gửi `done`.
- Không tìm thấy evidence bình thường trả câu trả lời thiếu thông tin, không mặc định 502.
  Output vẫn sai sau budget hoặc dịch vụ thật lỗi vẫn có thể trả lỗi HTTP đúng loại.

Citation/quote validation là kiểm tra giao thức và đoạn trích, không chứng minh entailment.
Prompt khuyến khích trả lời trực tiếp khi rõ, bỏ disclaimer chung; không sửa temperature để chữa retrieval.

## Cách dùng — người dùng tự chạy

Từ gốc project, cập nhật dependency trong virtualenv backend:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt -c backend/constraints.txt
make dev
```

Không cần sửa `.env`, migration hoặc reindex cho graph/lexical recall. Mode vẫn lấy cấu hình đang có;
`CHAT_MODE=mock` là default code. Muốn thử câu trả lời thật, tự chuẩn bị local corpus/server và key như trước.
Các lệnh trên **chưa chạy trong tác vụ**; chỉ việc cài riêng LangGraph đã được thực hiện để kiểm thử offline.

Ví dụ thử trên cùng conversation:

- `Gia phả Marika` → `nói tiếp về gia phả`.
- Chuyển sang `Ranni là ai?`: không dùng câu trả lời Marika cũ.
- `So sánh Moonveil và Uchigatana` → `Lấy nó ở đâu?`: hỏi lại vũ khí nào.
- `Chia chỉ số Moonveil` → `100, Samurai, PvE` → `level 120` → `PvP`: sửa task hiện tại.

`CHAT_HISTORY_MESSAGES=0` hoặc `CHAT_HISTORY_CHARS=0` tắt recall; pending gameplay vẫn hoạt động riêng.
Tắt recall không quay về việc nạp toàn transcript. Không có feature flag đổi về LCEL;
nếu cần rollback code, review/revert commit/PR tính năng bằng quy trình Git của nhóm, không reset dữ liệu người dùng.

Tham chiếu thiết kế API: [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
[streaming](https://docs.langchain.com/oss/python/langgraph/streaming).
Bản này dùng bridge riêng để giữ backpressure/cancellation của SSE, không phát graph debug/state ra client.
