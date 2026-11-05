# Hỏi lại và trợ lý gameplay — contract cho TV4

> Cập nhật tiếp 06/11: đường agent mặc định dùng mô hình chọn intent/slot/clarification, không dùng parser
> cố định bên dưới làm quyết định chính. Schema clarification giữ nguyên; PostgreSQL mode thêm capability
> transport. Xem [contract/setup agent và semantic memory](agent-semantic-memory.md).

05/11/2026 · TV3 MinhMuc · IndexBeast / 4 Hollows.

## Cách chạy và thử

Restart backend `make dev`, web `make web`. Không đổi `.env` hoặc reindex cho bản này.
CHAT_MODE giữ cơ chế hiện có; cấu hình dự án đang rag. Mặc định trong code vẫn mock cho máy mới.
Hai setting mới mặc định true: `GAMEPLAY_CLARIFICATION_ENABLED`, `GAMEPLAY_KNOWLEDGE_ENABLED`.
`.env.example` đã bổ sung, `.env` thật không bị sửa.

Ví dụ cùng một conversation:

1. “Chia chỉ số Moonveil”.
2. Bot hỏi level và starting class. Trả lời “100, Samurai”.
3. Bot hỏi PvE/PvP. Chọn PvE hoặc nhập trực tiếp.
4. Bot nối lại yêu cầu Moonveil với đủ điều kiện; có thể đưa ví dụ phân bổ được code kiểm.

Ví dụ route: “Tôi nên đi đâu tiếp?” → “current_location=Mistwood / objective=Nokron” bằng form
hoặc “Tôi đang ở Mistwood, muốn đến Nokron” bằng text. Hướng dẫn phải giữ điều kiện hạ Radahn,
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
    "fields": [{"key":"goal","label":"Bạn chơi PvE hay PvP?","input_type":"choice","options":["PvE","PvP"]}],
    "expires_at": "2026-11-05T12:30:00+00:00"
  }
}
```

Trả lời form vẫn gửi `message`, ví dụ `goal=PvE`, kèm conversation_id và clarification_id nhận từ server.
Form nhiều field gửi từng dòng `key=value`; cho phép trả lời một phần. Tối đa hai field/lượt.
Text “100, Samurai, PvE” cũng được nhận khi đang hỏi level/class. Không search riêng câu bổ sung.
Sai ID, sai conversation hoặc ID hết hạn: 400; conversation/channel/external_ref không khớp vẫn 404.
Không đưa API key vào web/Discord. Auth/rate limit vẫn hoạt động như trước.

Form web hiện là bản tối thiểu: input/select, nút Tiếp tục, hết hạn và text hướng dẫn hủy.
Chỉ card cuối cùng đã hoàn tất có thể tương tác; không gửi khi request đang chạy.
TV4 có thể chỉnh giao diện, giữ ID và mapping field. Không coi một card cũ là trạng thái còn hiệu lực.
Discord luôn auto, không cần UI form: trả lời text trong cùng thread/external_ref.
Live test đã dùng HTTP channel=discord với token thật; chưa đăng nhập Discord gateway hoặc gửi message vào server.

## State và giới hạn

State được giữ riêng theo ConversationState, dưới lock hiện có, commit sau khi JSON/SSE hoàn tất.
Generation lỗi hoặc stream hủy trước hoàn tất không tiêu thụ pending question hoặc commit profile mới.
TTL 30 phút; server kiểm lại khi nhận trả lời. “hủy”/“cancel” dừng pending request.
Câu hỏi/chủ đề mới rõ ràng thay yêu cầu cũ; thông tin explicit mới ghi đè level/goal cũ.
Không lấy câu hỏi “Samurai có spell không?” làm xác nhận class người chơi.
Parser hiện có grammar/tên mẫu có giới hạn, chưa phải NER; tên chưa nhận có thể nhập field weapon bằng text.
Không tự ánh xạ nickname hoặc tên gần giống. Lỗi/mơ hồ slot giữ câu hỏi, không đoán.

Working state độc lập history nên giữ level/class/weapon trong task đang làm khi history bị cắt.
Từ 06/11, task mới bắt đầu bằng thông tin của task mới; không tự mang weapon/location từ task trước.
Correction ngắn như `level 120` hoặc `PvP` cập nhật task còn hiệu lực, thay literal cũ trong query.
**Vẫn là RAM**, cùng kho hội thoại dev hiện có: restart, nhiều worker/process hoặc eviction có thể mất state.
Không triển khai PostgreSQL/checkpointer cho feature này. Chi tiết milestone/quest dài vẫn cần history/evidence;
chưa có world-state đầy đủ hay quản lý mọi quest flag. Không tuyên bố memory lâu dài đã hoàn thiện.

Service factory bật feature theo setting. Constructor LiveChatService mặc định giữ compatibility cho caller cũ;
caller tự tạo service muốn dùng tính năng phải truyền `gameplay_enabled=True`.
LangChain/LCEL prompt/model được giữ; từ 06/11 LangGraph điều phối gameplay/memory và RAG.
Không giữ HTTP request mở chờ người dùng; pending question vẫn ở RAM của conversation.
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
