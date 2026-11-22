# Bàn giao web — TV4

Phạm vi: mã nguồn trong `web/`, tương ứng các thẻ web S1–S5. Không triển khai nhiệm vụ backend, RAG, ingestion,
database, bot hay hạ tầng. Các ghi chú đầu tệp được giữ nguyên. README và kế hoạch chung không được chỉnh sửa.

## Chạy và kiểm tra

Tại thư mục `web`, chạy `npm.cmd ci` lần đầu, rồi `npm.cmd run dev`. Cổng đọc từ `WEB_PORT` ở `.env` gốc
(mặc định 15173); proxy `/api` sang `API_PORT` theo cấu hình Vite đã có. Không đưa secret `.env` vào web.

Từ thư mục gốc dự án, có thể chạy `make web` trong Git Bash/WSL để khởi động frontend thay cho việc cd vào web.
Lệnh không tự chạy backend; mở terminal khác chạy `make api` nếu muốn gửi câu hỏi tới API mock.

- `npm.cmd run build`: TypeScript và build tĩnh vào `dist/`.
- `npm.cmd test`: kiểm tra JSON `/chat`, response sai, hủy request, thử lại, mock cục bộ, SSE và HTTP 429 bằng fetch giả.
- `npm.cmd run test:integration`: chạy HTTP thật qua proxy Vite tới API mock nguyên bản của TV1.
  Cần Python có các dependency backend; ưu tiên `backend/.venv`, hoặc chỉ định executable bằng `WEB_TEST_PYTHON`.
  Test tự tạo và dọn server riêng ở cổng do hệ điều hành cấp, chỉ bind `127.0.0.1`; không cần DB, LLM hay secret.
- `npm.cmd run format:check`: kiểm tra định dạng.

## Chức năng

### Giao diện đăng nhập (14/11/2026)

Mở `/` hoặc `/login` hiện màn đăng nhập độc lập, không sidebar; nhấn **Vào website** tới chat tại `/chat`.
Sidebar trong ứng dụng không có mục đăng nhập lặp lại. Bố cục theo ảnh tham chiếu mới: logo trên trái,
nhóm đăng nhập bên trái và ảnh patches đầy đủ bên phải trên desktop; màn nhỏ xếp dọc. Giữ palette/font hiện tại,
có hai lựa chọn Google/Discord và đường dẫn tiếp tục với tư cách khách. Đây là bản UI: hai nút provider bấm được và hiện thông báo chưa sẵn sàng khi bấm;
không redirect OAuth, tạo phiên giả, lưu token hay đồng bộ lịch sử. Chat và lịch sử khách giữ nguyên.
Backend Discord đã có hợp đồng [auth TV4](../docs/api/auth-tv4.md); khi nối thật phải kiểm `auth_available`,
đọc phiên qua API, dùng cookie httpOnly và tuân thủ [ADR-005](../docs/adr/005-dang-nhap.md).
Google chưa có contract được chốt. Bước này không thay backend hoặc quyết định ADR.
Theo yêu cầu mới nhất đã bỏ phần email, chỉ giữ Google/Discord và Vào website.
Các nút có nền trong suốt, dùng chung vệt sáng menu.
Xem [bàn giao UI đăng nhập](../docs/handover/2026-11-14_s4-tv4_giao-dien-dang-nhap-google-discord.md).

- Logo ELDEN RING PNG nền trong suốt đã được bỏ khỏi màn hình chat theo yêu cầu người dùng.
  Ba nút Nhân vật / Sự kiện / Thế giới đã bỏ. Hiện có ba câu hỏi gợi ý mới dưới ô nhập:
  “Elden Ring là game gì?”, “Game thuộc thể loại gì?”, “FromSoftware là gì?”; bấm để gửi qua luồng chat hiện có.
  Tệp `src/assets/elden-ring-logo.png` được đóng gói cùng web, lấy từ
  [trang Elden Ring của Bandai Namco](https://en.bandainamcoent.eu/elden-ring/elden-ring)
  ([ảnh nguồn](https://static.bandainamcoent.eu/high/elden-ring/elden-ring/00-page-setup/eldenring_new.png)).
  Logo thuộc thương hiệu gốc, không phải logo do nhóm tạo.

- Logo dùng Agmena Pro Book từ `web/font/Agmena Pro Book/Web Fonts/`.
  WOFF2 được Vite đóng gói cùng web, không tải font từ CDN. Nội dung tiếng Việt dùng Cambria,
  dự phòng Times New Roman/serif để tránh trộn glyph. Giữ `web/font/License.txt` và nguồn font ở trang Về dự án.
  Đã gỡ Mantinia cùng khai báo CSS không dùng, các bản font dư, trang demo, ZIP và shortcut nguồn.

- Icon Grace dùng `src/assets/ERN_Map_Icon_Site_of_Grace.png`. Khi đổi tên hoặc di chuyển ảnh,
  cập nhật import trong Header, ChatPage và MessageList; đường dẫn cũ `grace.png` làm Vite báo thiếu module.

- Bố cục tham khảo ảnh chat do người dùng cung cấp: thanh bên có cuộc trò chuyện mới, liên kết About/Admin
  và lịch sử; màn hình trống đặt lời chào, ô nhập và gợi ý ở giữa. Khi có tin nhắn, ô nhập nằm cuối vùng chat.
  Giữ theme tối/vàng Erdtree, viền vuông và ảnh nền chỉ ở Main Content. Không thêm Shop, Library,
  upload hay voice từ ứng dụng tham khảo vì không thuộc nhiệm vụ UI chat Sprint 2 của TV4.

- Giao diện và phản hồi minh họa dùng tiếng Việt; ngày hiển thị theo `vi-VN`.
  Đã bỏ nút VI/EN và bộ bản dịch tiếng Anh. Lựa chọn ngôn ngữ cũ trong localStorage được bỏ qua.
  Không tự dịch nội dung hội thoại hoặc dữ liệu API; tên riêng và thương hiệu giữ nguyên.

- `/`: chat, Enter/Shift+Enter, dừng sinh, thử lại, Markdown không render HTML thô, nguồn và hộp trích dẫn.
- Lịch sử khách: localStorage, tối đa 30 cuộc trò chuyện, xóa từng cuộc; lỗi lưu trữ không làm hỏng trang.
- Sprint 3: cuộc trò chuyện mới mặc định gọi POST `/api/v1/chat/stream` qua fetch + ReadableStream,
  kiểm tra sự kiện SSE và hiện token dần. Lượt gửi/thử lại/bổ sung trong hội thoại JSON cũ cũng chuyển sang SSE,
  giữ ID/token và lịch sử. Không còn bộ chọn chế độ trên sidebar, không tự chuyển sang mock khi lỗi.
  Có nút Dừng/Esc khi focus ở composer, báo lỗi và Thử lại; lỗi/ngắt trước done giữ nội dung dở dang.
- Các cuộc trò chuyện demo cũ vẫn mở được và giữ nhãn minh họa; tạo mới luôn dùng API.
  Demo cục bộ giữ trong `src/api/demo.ts` để kiểm thử; feedback demo không gửi server.
- Trạng thái “Đang tìm trong lore…” xuất hiện ngay khi gửi, cùng ba chấm chờ, biến mất khi nhận nội dung.
  Đo fixture trình duyệt 1440/768/360 lần lượt 49/13,7/31,2 ms (DOM xuất hiện), chưa phải benchmark backend thật.
  Ngày 08/11 người dùng yêu cầu hiện lại danh sách nguồn sau khi câu trả lời hoàn tất: [n], tiêu đề,
  xem trích đoạn và link mở nguồn HTTP(S). Giữ citation/popover và không hiện khung nguồn rỗng.
- `/answer#<token>`: bản chia sẻ chỉ đọc một câu trả lời Discord, có nguồn và thời hạn 24 giờ.
  Token trong fragment chỉ được gửi qua header `X-Answer-Share-Token` tới GET `/api/v1/answer-shares`,
  không đưa vào path/query API, không lưu localStorage và không dùng service token trên trình duyệt.
  Sai/hết hạn hiện thông báo và nút thử lại, không chuyển sang dữ liệu giả.
- Ô nhập tự giãn, tối đa 2.000 ký tự theo OpenAPI; lý do phản hồi tối đa 500 ký tự. Gửi `options.lang=vi` cho giao diện tiếng Việt.
- `/about`: phạm vi, nguồn, CC BY-SA, nhóm, lưu trữ trên trình duyệt và disclaimer.
- `/admin`: form token, danh sách hội thoại, tra cứu trace, feedback xấu, ingestion, eval. Token chỉ nằm trong memory.
  Quyền truy cập phải do backend kiểm tra; frontend không thay thế xác thực.
- Theme tối/vàng Erdtree, responsive từ 360px, trạng thái focus và dialog dùng bàn phím.

## Kết nối và thử API mock Sprint 2

1. Khởi động API theo hướng dẫn của TV1 ở README gốc (`make api` dùng `API_PORT` trong `.env`).
2. Tại `web`, chạy `npm.cmd run dev`, mở địa chỉ Vite in trong terminal.
3. Bấm **Cuộc trò chuyện mới**, nhập câu hỏi và Enter. Trong Network phải có POST `/api/v1/chat`,
   header `X-Request-ID`, response JSON có câu trả lời, nguồn, UUID và `latency_ms`.
4. Hỏi tiếp: request gửi lại `conversation_id` nhận được; nguồn bấm được để xem trích đoạn.
5. Dùng các câu hỏi đặc biệt của mock để thử:

| Câu hỏi            | Kết quả mong đợi                                                             |
| ------------------ | ---------------------------------------------------------------------------- |
| `/mock-ungrounded` | Không đủ bằng chứng, `grounded=false`, danh sách nguồn rỗng                  |
| `/mock-error`      | Báo lỗi 502 thân thiện, có Thử lại; không chuyển sang demo                   |
| `/mock-429`        | Báo gửi quá nhanh, hiển thị thời gian chờ theo `Retry-After`                 |
| `/mock-slow`       | Hiện đang tìm khoảng 5 giây; Dừng hủy request và không nhận câu trả lời muộn |

`/mock-error` luôn trả lỗi; bấm Thử lại với chính câu này vẫn lỗi là đúng. Để thử phục hồi, gửi câu hỏi bình thường.
Cuộc trò chuyện mock lưu trong RAM backend: sau khi backend khởi động lại, hãy tạo cuộc trò chuyện mới nếu nhận 404.
Nếu API chưa chạy, web hiển thị lỗi kết nối; không tự tạo câu trả lời giả.

## Hợp đồng API đã đối chiếu

Nguồn: [OpenAPI v1](../docs/api/openapi.json) và [bàn giao TV1](../docs/handover/2026-10-28_s2-tv1_api-contract-v1-va-loi-chuan.md).
Type trong `src/api/types.ts` được viết tay, không sửa OpenAPI hoặc schema backend.

| Request                                       | Client web                                                                   |
| --------------------------------------------- | ---------------------------------------------------------------------------- |
| POST `/api/v1/chat`                           | `chat`: JSON, timeout 30 giây, hủy qua AbortSignal                           |
| POST `/api/v1/chat/stream`                    | `chatStream`: đọc status/token/sources/done/error, phát hiện ngắt trước done |
| POST `/api/v1/feedback`                       | `sendFeedback`: rating 1 hoặc -1, lý do tối đa 500 ký tự, response 204       |
| GET `/api/v1/conversations/{conversation_id}` | `getConversation`: kiểm tra UUID và cấu trúc lịch sử                         |

- Câu hỏi có 1–2.000 ký tự sau khi bỏ khoảng trắng đầu/cuối; request hỗ trợ `external_ref` tùy chọn.
- Response bắt buộc UUID `conversation_id`/`message_id`, answer, sources, grounded và latency_ms.
- Source cho phép `section`/`text` là null; `origin` là corpus hoặc web.
- SSE done cũng có UUID, grounded và latency_ms. Lỗi HTTP không hiển thị nội dung nội bộ của provider.
- Giao diện admin và client `/admin/*` hiện là khung S5; các endpoint này chưa nằm trong OpenAPI v1.
  Không coi admin đã được tích hợp, không sửa API để khớp khung frontend.

## Tinh chỉnh giao diện chat (29/10/2026)

Font nội dung tiếng Việt dùng Cambria (fallback Times New Roman/serif); Agmena được giữ riêng cho logo qua biến `--font-brand` để tránh trộn nét chữ có dấu.

UI theo hướng chat hiện đại kết hợp Điểm Ân Điển: ảnh patches giảm bão hòa và dịu hơn khi có hội thoại, ô nhập nền đặc, hover đổi sắc nền nhẹ, câu trả lời không có khung bao. Các chuyển động mới tôn trọng `prefers-reduced-motion`.

Ô nhập hiện có hình đại kiếm theo yêu cầu: chuôi SVG cố định, thân CSS giãn theo nội dung và mũi vát. Phần trang trí không nhận chuột; nút gửi máy bay giấy đen–vàng giữ nguyên và ẩn khi input trống.

Ba gợi ý bên dưới có hình cờ chiến trận, viền vàng xỉn và đuôi chữ V; giữ button HTML và focus bàn phím. Desktop ba cột bằng nhau, mobile xếp dọc.

Lớp `src/styles/refinement.css` được nạp sau CSS cũ để giữ ghi chú gốc. Cột chat tối đa 760 px, ba gợi ý chung chiều rộng với ô nhập; màn hình nhỏ dùng rail và menu phủ nội dung, hỗ trợ Escape và bàn phím. Giữ ảnh patches, font Agmena, icon Grace và góc vuông.

Đợt chỉnh đã qua build, 17 test, Prettier và kiểm tra trình duyệt ở 1440/768/390 px. Chi tiết phạm vi, kiểm tra tương tác và giới hạn nằm trong [handover giao diện TV4](../docs/handover/2026-10-29_s2-tv4_tinh-chinh-giao-dien-taste.md).

## Kiểm tra thực tế và giới hạn

- `npm.cmd run build`: TypeScript và build tĩnh đạt.
- `npm.cmd test`: 17 test đạt, gồm giới hạn OpenAPI, null source, JSON/SSE, retry và hủy request.
- `npm.cmd run test:integration`: 9 test đạt (1 bài tổng và 8 bài con), dùng fetch HTTP thật qua Vite
  tới factory/route/MockChatService nguyên bản của backend trong bộ gá `web/tests/integration/mock_backend.py`.
  Bao phủ hỏi tiếp, lịch sử, feedback, JSON→UI events, SSE, không bằng chứng, 422/429/502/404, chậm, hủy và timeout.
  Timeout ngắn 50 ms trong test kiểm tra đường xử lý timeout; mặc định ứng dụng vẫn là 30 giây.
- Bộ gá chỉ truyền context thử nghiệm để không tạo kết nối DB/Redis/Qdrant/LLM; không thay nội dung response của TV1.
- Chưa kiểm thử thao tác trình duyệt tự động hoặc xác nhận trực quan trên mọi màn hình; không coi kiểm thử HTTP
  là bằng chứng hoàn thành UAT, Lighthouse, production hoặc chất lượng RAG.
- Phạm vi lần này chỉ web S1–S2 của TV4. Bot `/ask` chưa được triển khai; review nhóm được bỏ qua theo yêu cầu.
- [Bàn giao TV4](../docs/handover/2026-10-28_s2-tv4_web-api-mock.md) ghi phạm vi và kết quả kiểm tra.

Nền trang đăng nhập sử dụng `item_/MENU_BaseMain_01.png` và `item_/MENU_FL_MenuBase.png`
chép nguyên bản từ bộ hi_01 người dùng cung cấp: lớp phủ tối, ánh mờ phía dưới và nền mềm sau nhóm nút.
Các lớp trang trí không nhận chuột; ảnh minh họa vẫn giữ đúng tỷ lệ và hiển thị đủ.
