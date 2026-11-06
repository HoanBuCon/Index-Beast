# Hỏi lại và trợ lý gameplay — contract cho TV4

> Cập nhật 06/11: web đã dùng **khung nhập tự do ngay dưới câu hỏi**, không dropdown/key=value.
> Retry giữ văn bản, clarification ID và turn ID; câu hỏi gốc được giữ qua nhiều lượt bổ sung.
> Backend giới hạn 3 lượt hỏi bổ sung/task; lỗi decision không hợp lệ trả upstream error, không giả làm câu hỏi mới.
> Cập nhật tiếp 06/11: đường agent mặc định dùng mô hình chọn intent/slot/clarification, không dùng parser
> cố định bên dưới làm quyết định chính. Schema clarification giữ nguyên; PostgreSQL mode thêm capability
> transport. Xem [contract/setup agent và semantic memory](agent-semantic-memory.md).

05/11/2026 · TV3 MinhMuc · IndexBeast / 4 Hollows.

## Cách chạy và thử

Chạy lại `make dev` (đã bao gồm backend và web). Không đổi `.env` hoặc reindex cho bản này.
CHAT_MODE giữ cơ chế hiện có; cấu hình dự án đang rag. Mặc định trong code vẫn mock cho máy mới.
Hai setting mới mặc định true: `GAMEPLAY_CLARIFICATION_ENABLED`, `GAMEPLAY_KNOWLEDGE_ENABLED`.
`.env.example` đã bổ sung, `.env` thật không bị sửa.

Ví dụ cùng một conversation:

1. “Chia chỉ số Moonveil”.
2. Bot hỏi level và starting class. Trả lời “100, Samurai”.
3. Nếu mô hình còn cần mục tiêu, nhập “chủ yếu PvE” vào khung phụ.
4. Bot nối lại yêu cầu Moonveil với đủ điều kiện; có thể đưa ví dụ phân bổ được code kiểm.

Ví dụ route: “Tôi nên đi đâu tiếp?” → nhập “Tôi đang ở Mistwood, muốn đến Nokron” trong khung phụ. Hướng dẫn phải giữ điều kiện hạ Radahn,
không giả người chơi đã hạ boss. Quest “Hướng dẫn quest Ranni” rồi “Đã giao Fingerslayer Blade, đi đâu tiếp?”
dùng history và các đoạn quest để tiếp tục. Không áp một thứ tự boss duy nhất.

## JSON và SSE

`ChatRequest` thêm **optional** `clarification_id: UUID`. Không gửi ID khi hỏi câu mới.
`ChatResponse`, `MessageOut` và SSE **sources** thêm `clarification: object | null`, default null.
Không đổi tên event hoặc contract cũ. Client cũ có thể bỏ qua field và trả lời bằng text.

```json
{
  "clarification": {
    "id": "33333333-3333-4333-8333-333333333333",
    "status": "pending",
    "question": "Bạn chơi PvE hay PvP?",
    "fields": [{"key":"goal","label":"Bạn chơi PvE hay PvP?","input_type":"text","options":[]}],
    "expires_at": "2026-11-05T12:30:00+00:00"
  }
}
```

Khung phụ gửi văn bản tự do nguyên văn, ví dụ:

```json
{
  "message": "Samurai level 100, chủ yếu PvE",
  "channel": "web",
  "conversation_id": "11111111-1111-4111-8111-111111111111",
  "clarification_id": "33333333-3333-4333-8333-333333333333",
  "turn_id": "44444444-4444-4444-8444-444444444444"
}
```

Postgres conversation còn cần `conversation_token` nhận từ server; ví dụ trên lược bỏ token.
`fields` là gợi ý nội bộ tương thích contract cũ, không phải yêu cầu UI hiển thị select/form profile.
Mô hình tạo `question`/`reply` và tự đánh giá thông tin còn thiếu, không gọi thêm model chỉ để viết lại câu hỏi.
Enter gửi, Shift+Enter xuống dòng; không gửi khi đang xử lý. Draft còn nguyên khi lỗi, có thể thử lại
hoặc dùng nút “Thử lại” ở chat. Retry giữ cùng `turn_id` và `clarification_id` và không nhân đôi user turn trên web.
Idempotent replay backend hiện yêu cầu persistence PostgreSQL; RAM không có cam kết exactly-once.
Card đang chờ vẫn được giữ trong lúc reply lỗi; trả lời thành công thì đóng. Nút “Hủy yêu cầu” gửi ý định hủy
bằng text qua cùng planner; ô chat chính vẫn dùng để chuyển chủ đề mới.
Sai ID, khác conversation hoặc hết hạn: 400; auth/capability và channel checks vẫn áp dụng.
Không đưa API key vào web/Discord. Không dùng câu trả lời bổ sung làm bằng chứng factual về game.
Discord luôn auto, không cần UI form: trả lời text trong cùng thread/external_ref.
Ở milestone trước, live test đã dùng HTTP channel=discord với token thật; chưa đăng nhập Discord gateway hoặc gửi message vào server.

## State và giới hạn

State được giữ riêng theo ConversationState, dưới lock hiện có, commit sau khi JSON/SSE hoàn tất.
Generation lỗi hoặc stream hủy trước hoàn tất không tiêu thụ pending question hoặc commit profile mới.
TTL 30 phút; server kiểm lại khi nhận trả lời. “hủy”/“cancel” dừng pending request.
Câu hỏi/chủ đề mới rõ ràng thay yêu cầu cũ; thông tin explicit mới ghi đè level/goal cũ.
Không lấy câu hỏi “Samurai có spell không?” làm xác nhận class người chơi.
Parser gameplay.py là đường legacy khi CHAT_AGENT_ENABLED=false; đường agent không dùng nó làm classifier.
Agent giữ request_text là nguyên văn yêu cầu đầu và constraints có provenance riêng, không thay root bằng reply ngắn.
History/semantic recall giữ cơ chế hiện có; raw request trong working state giúp resume ngay cả khi recall bị tắt.
Không tự ánh xạ nickname hoặc tên gần giống. Mô hình có thể hỏi rõ chủ thể mơ hồ; lỗi decision/schema trả upstream error.

Working state độc lập history nên giữ level/class/weapon trong task đang làm khi history bị cắt.
Từ 06/11, task mới bắt đầu bằng thông tin của task mới; không tự mang weapon/location từ task trước.
Correction ngắn như `level 120` hoặc `PvP` cập nhật task còn hiệu lực, thay literal cũ trong query.
Persistence phụ thuộc cấu hình: `memory` mất state sau restart/eviction; `postgres` dùng repository và
working state lưu bền đã có, yêu cầu migration/setup và capability token. Tác vụ free-text không thêm migration/checkpointer. Chi tiết milestone/quest dài vẫn cần history/evidence;
chưa có world-state đầy đủ hay quản lý mọi quest flag. Không tuyên bố memory lâu dài đã hoàn thiện.

Service factory bật feature theo setting. Constructor LiveChatService mặc định giữ compatibility cho caller cũ;
caller tự tạo service muốn dùng tính năng phải truyền `gameplay_enabled=True`.
LangChain/LCEL prompt/model được giữ; từ 06/11 LangGraph điều phối gameplay/memory và RAG.
Không giữ HTTP request mở chờ người dùng; pending question được commit vào kho conversation tương ứng với CHAT_PERSISTENCE.
Xem [luồng graph và giới hạn memory](langgraph-memory.md). API JSON/SSE không đổi.

## Nguồn bổ sung và build chỉ số

`backend/app/rag/knowledge/gameplay.json` là gói nguồn nhỏ, đọc lazy/cache và chọn theo query:
Ranni/Nokron, Academy Key/Thops, các mốc Morgott/Fire Giant/Maliketh và Moonveil.
Các chunk từ artifact giữ nguyên text/ID/metadata/hash; point ID dùng mapping core.types hiện có.
Bốn bản ghi ngắn riêng giữ quy tắc tổng điểm, Samurai, requirements Moonveil và respec.
Provenance, pending review, patch unknown được giữ; không giả approved/canon/latest patch.
Không ghi pack vào PostgreSQL/Qdrant, không embedding lại. Context ghi `local_candidate_origin=curated_source_snapshot`.
Đây là nguồn local bổ sung tại runtime, nên kết quả không phải chỉ riêng Qdrant retrieval nguyên bản.
Policy pilot/ngôn ngữ/spoiler vẫn kiểm như context khác; reviewed policy sẽ loại nguồn chưa approved.

Context vẫn top-5/budget. Khi người dùng yêu cầu phân bổ chính xác, giữ đủ nhóm quy tắc trước
khi ghép local/web; intent chọn context dựa cả câu gốc và rewrite để không mất “chia chỉ số”.
Generator thêm internal field optional `build_allocation`; public API chỉ nhận text đã kiểm/render.
Hiện chỉ xác minh **Samurai + Moonveil, một tay, không buff cộng chỉ số**:
tổng điểm=level+79, sàn class, cap 99 và requirements. Không kiểm AR/DPS, soft cap hoặc tối ưu PvE/PvP.
Class/vũ khí khác vẫn có thể tư vấn định tính; chưa có rule thì không bịa bảng số.
Không thêm vòng agent/search; budget rewrite/assessment/generation và Search/Extract giữ nguyên.
Ví dụ đã test thực tế: level 100, tổng 179; xem [báo cáo](../testing/2026-11-05_gameplay-evaluation.md).

## Kiểm chứng cập nhật free-text — 06/11/2026

Baseline backend 784 passed; sau sửa 788 passed (2 warning cũ), 26,45 giây.
Web 41 test đạt; build/typecheck, Prettier, Ruff và OpenAPI check đạt. Có warning không fatal ở fixture web về HMR port 24678 bận.
Web build đạt trên asset hiện có, không thêm/thay asset TV4. Test dùng scripted model và HTTP giả;
không chứng minh DeepSeek thật hiểu đúng mọi câu trả lời. Chưa kiểm tra trực quan trên browser/mobile.
Không gọi DeepSeek/Tavily, tải model, embedding, ghi server dữ liệu hoặc sửa .env thật.

Tự thử: “Chia chỉ số Moonveil” → nhập “level 100” → nếu cần nhập “Samurai, chủ yếu PvE”;
“đổi thành level 120”; thử hủy, đổi chủ đề, và thử lại sau lỗi mạng. Câu hỏi cụ thể do mô hình quyết định,
không đảm bảo sẽ hỏi theo đúng một kịch bản hay sẽ đủ evidence để đưa bảng chỉ số.
