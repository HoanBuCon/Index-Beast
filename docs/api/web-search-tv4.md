# Web search — contract và giao diện

Ngày 04/11/2026 · TV3 MinhMuc · IndexBeast / 4 Hollows.

## Cập nhật chất lượng query/excerpt

Query web được giữ nguyên điều kiện và thêm phạm vi Elden Ring khi chưa có; ý hỏi class khởi đầu
được bổ sung English search focus `starting classes list character creation`, kể cả khi rewrite lỗi.
Không dịch/đoán tên entity mới. Query thực dùng chỉ lưu trong trace khi opt-in diagnostic_queries.
Extract cũng nhận query và chunks_per_source=3; không chỉ lấy đầu trang.

Backend làm sạch Markdown: bỏ image markup, giữ nhãn của link, bỏ menu trước H1 khi có dấu hiệu
wiki skin; giữ heading, bảng, số liệu và thứ tự bước trong excerpt. Các nhóm block nguyên vẹn
được xếp theo lexical overlap, không phải semantic reranker hoặc chứng minh đủ bằng chứng.
Block quá lớn vẫn có thống kê loại. Chưa hỗ trợ chia lại bảng lớn hoặc khôi phục phần provider bỏ sót.

Số Source trong response là số nguồn thật sự được mô hình trích, không phải số kết quả Search.
Một nguồn có thể đủ cho một câu đơn; không ép thêm nguồn chưa dùng. Ảnh web vẫn chưa được nối:
Search/Extract hiện không yêu cầu ảnh, cơ chế ảnh local vẫn hoạt động theo citation corpus.
Để bổ sung ảnh web cần xử lý URL/metadata/liên hệ với đáp án, contract media và UI riêng;
không dùng logo, icon điều hướng hay ảnh bất kỳ như ảnh minh họa nội dung.

## Dùng trên web

Nút **Web: OFF / ON / ALWAYS** nằm trong ô chat. Mỗi lần bấm chuyển tuần tự
**OFF → ON → ALWAYS → OFF**; ON ánh xạ tới `auto`. Mặc định khi mở trang vẫn là ON (auto).

| Trạng thái | Request | Hành vi |
|---|---|---|
| OFF | `options.web_search=off` | Chỉ local, tuyệt đối không gọi Tavily |
| ON (mặc định) | `options.web_search=auto` | Local trước, đánh giá coverage; thiếu mới Search → Extract |
| ALWAYS | `options.web_search=always` | Search → Extract cho mỗi câu hỏi game hợp lệ, kết hợp local |

OFF là tắt hoàn toàn tìm kiếm web cho request, ON là tìm tự động khi cần.
Lựa chọn áp dụng theo request, không sửa `.env`,
không restart, không thay CHAT_MODE. Nút bị khóa khi request đang chạy; retry dùng lựa chọn hiện tại.
Lựa chọn giữ trong state trang, mặc định lại auto khi tải lại trang.

Frontend đọc `GET /api/v1/chat/capabilities`:

```json
{"web_search_available": true}
```

Không trả key, endpoint provider hoặc cấu hình nội bộ. Khi false, nút bị vô hiệu hóa và
hiện “Tìm web chưa khả dụng”. Capability được đọc khi mở trang; refresh sau khi restart server.
Demo không giả việc đã search; nút bị khóa trong demo. Khi capability chưa khả dụng,
hiển thị OFF bị khóa và gửi off; không âm thầm gửi always.

Ví dụ request web:

```json
{
  "message": "Moonveil cần bao nhiêu Intelligence?",
  "channel": "web",
  "options": {"lang": "vi", "spoilers": true, "web_search": "always"}
}
```

## Discord

Bot gửi `options.web_search=auto`. Backend ép mọi request `channel=discord` về auto,
kể cả client gửi off/always. Service token và rate limit hiện có vẫn áp dụng.
Không thêm slash command hoặc yêu cầu thành viên TV4 giữ Tavily key. Key chỉ ở backend TV3.

## Server và tương thích

- Có `TAVILY_API_KEY` không rỗng, `CHAT_MODE=rag` và công tắc tổng không bị tắt thì tự khả dụng.
  Không cần chỉnh `.env` mỗi lần chuyển chế độ trên web.
- `WEB_SEARCH_ENABLED=false` là công tắc vận hành khẩn cấp, không phải thao tác người dùng hàng ngày.
- Client cũ bỏ option: dùng mặc định server `WEB_SEARCH_MODE=auto`; thiếu key thì giữ local-only.
- Web yêu cầu always nhưng server chưa khả dụng: 503, không âm thầm giả đã search.
- mock/llm_only không gọi Tavily. Các lời chào/cảm ơn/injection/ngoài phạm vi được xử lý trước tool.
- Mơ hồ cần làm rõ không search; follow-up đã xác định chủ thể thì query gồm chủ thể/history.
- Spoilers=false: web excerpt chưa có nhãn spoiler an toàn không được chọn vào context.

## Evidence và lỗi

Search chỉ tìm URL; Extract mới lấy nội dung để chọn evidence. Không dùng answer tổng hợp của Tavily.
URL phải HTTPS, host đúng danh sách server, không credentials/IP/port lạ. Không tự fetch URL vào mạng backend.
Tavily tự tải trang ở phía dịch vụ của họ; backend không kiểm soát được từng redirect nội bộ của provider.
Chỉ nhận URL trả về trùng tập đã chọn. HTTP client không follow redirect của endpoint API.

Nguồn web có origin=web, title/URL, thời gian lấy, release/patch unknown và trạng thái unreviewed.
Không giả thành source đã approved hoặc đóng dấu pilot để vượt CorpusPolicy. WebHit là kiểu internal;
artifact tự gắn origin=web không được bypass policy. Không ghi web vào PostgreSQL/Qdrant.

Local và web được xen kẽ theo thứ tự, ưu tiên web cho yêu cầu cần bổ sung; không cộng score khác thang đo.
Context vẫn top-5/budget; dedup theo ID và kiểm chọn context hiện có. Markdown chia nguyên block;
block >3500 ký tự được bỏ có thống kê, không cắt bảng/sentence. Tối đa 3 excerpt/trang.
Vì vậy Extract chưa bảo đảm lấy đủ bảng lớn: cần kiểm chứng gameplay/build trên nguồn thật.

Citation [n] và evidence vẫn được kiểm như trước. API Source.origin là corpus/web, URL lấy từ metadata server.
Chỉ nguồn thực sự được trích được trả về. Ảnh web không được tự thêm; ảnh local chỉ xét các citation corpus.
Đánh giá coverage bằng LLM có kiểm reference IDs nhưng không phải chứng minh entailment.

Khi Tavily lỗi, chỉ dùng local nếu assessment cho thấy đủ; nếu chưa đủ trả 503 thay vì giả insufficient.
Search/Extract thành công nhưng không có evidence dùng được có thể trả lời insufficient bình thường.
Local retrieval outage vẫn báo lỗi riêng, không đánh đồng thành local miss để gọi web.
Lỗi generation/citation giữ protocol recovery và 502 hiện có. SSE không retry sau text đã phát,
không gửi done thành công sau lỗi; schema event hiện tại giữ nguyên, chưa thêm progress event từng tool.

## Ngân sách

- Tối đa 1 Search + 1 Extract batch/request; 0 retry Tavily. Mặc định 3 kết quả, tối đa cấu hình 5.
- Search+Extract chia sẻ deadline 8 giây. Assessment tối đa 1 logical call, deadline 3 giây, 512 token.
  Auto local rỗng bỏ qua assessor; always chỉ assess local nếu web lỗi và cần xét fallback.
- Khi web khả dụng: rewrite tối đa 4 giây; retrieval chia sẻ tối đa 5 giây (tối đa 2 query).
- Giữ deadline tổng ChatService (mặc định 45 giây), bot 60 giây. Các deadline con không gia hạn request.
- Generation và recovery dùng ngân sách hiện có. SDK DeepSeek vẫn có transport retry theo cấu hình,
  logical call không đồng nghĩa số HTTP attempt. Timeout tổng có thể cắt request trước khi recovery xong.

## Kiểm thử thủ công (chỉ hướng dẫn)

1. Backend có key và `CHAT_MODE=rag`; restart `make dev`. Không cần embedding/index lại.
2. Refresh web. Nút mặc định ON; hỏi câu local có bằng chứng và quan sát trace coverage.
3. Hỏi “huong dan build katana” hoặc yêu cầu chỉ số thiếu local; auto có thể search, không hứa build tối ưu.
4. Bấm sang ALWAYS, hỏi câu local có đáp án; xác nhận Tavily vẫn được gọi qua trace `web_search`.
   Bấm tiếp về OFF và hỏi lại: trace không được có lượt gọi Tavily. Bấm tiếp trở về ON.
5. Hỏi “gia phả Marika” rồi “nói tiếp về gia phả” trong cùng conversation.
6. TV4 restart `make bot`: Discord luôn auto. Không cần đăng ký lại slash command.

Các bước này tốn API nếu thực hiện. Trong tác vụ triển khai chỉ chạy fake/MockTransport và mock API,
chưa xác nhận live chất lượng Tavily, bảng chỉ số hoặc độ trễ thật.

API chính thức: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search),
[Tavily Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract).
