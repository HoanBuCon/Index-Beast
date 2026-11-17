# Rà soát mã nguồn Index-Beast

Ngày 17/11/2026 · Mốc `origin/develop` đã fetch: `00d64de03182a3c564878736116eb47e9aa4b194`.

Phạm vi gồm API, xác thực, PostgreSQL, DevOps, ingest, retrieval/LLM/eval, web và bot. Bản này là báo cáo review. Chủ sở hữu được đề xuất theo phân vai trong tài liệu và chú thích module. Các kết luận bảo mật dựa trên đường đi của mã, với điều kiện áp dụng ghi ở từng mục.

**P1** cần ưu tiên do mất dữ liệu hoặc lộ dữ liệu có tác động rõ. **P2** có tác động đáng kể với điều kiện cụ thể. **P3** là vấn đề bảo trì hoặc sai lệch quy ước có tác động cục bộ.

## P1

### 1. Lịch sử tài khoản có thể hiện với sai phiên trên cùng trình duyệt · TV4, phối hợp TV1

- **Bảo mật và riêng tư.** Hook lưu lịch sử qua một khóa browser storage. Bản sao chat của tài khoản có cả tin nhắn và `ownerUserId`. Trang chat khôi phục và liệt kê lịch sử local mà chưa lọc theo danh tính đã xác thực. Logout có dọn lịch sử của người dùng hiện tại, nhưng hết phiên, mở lại trang và phản hồi tải lịch sử đến sau đổi danh tính là các đường khác. Người dùng chung browser profile có thể nhìn thấy bản sao thuộc tài khoản trước.
- **Đề xuất.** Giữ hội thoại tài khoản trên server/in-memory theo phiên. Lọc cả sidebar, active chat và kết quả truy vấn theo danh tính hiện hành. Dọn bản sao cũ khỏi storage và vô hiệu hóa phản hồi đang tải khi đổi tài khoản. Kiểm bằng test giao diện với auth giả, gồm hết phiên, chuyển tài khoản và phản hồi đến muộn.
- **Bằng chứng.** `web/src/hooks/useConversations.ts:8`, `web/src/lib/storage.ts:8,50`, `web/src/pages/ChatPage.tsx:69,77,111,259,331`.

### 2. Khôi phục PostgreSQL có thể xóa bản hiện hành trước khi xác minh bản thay thế · TV1

- **Độ tin cậy vận hành.** Script đọc mục lục dump, dừng API/bot rồi commit thao tác thay schema trước khi thực hiện restore. Nếu restore lỗi sau bước đó, database có thể dở dang và các dịch vụ vẫn dừng. Đọc được mục lục chưa đủ để chứng minh restore thành công.
- **Đề xuất.** Restore vào DB tách biệt, xác minh schema, migration và dữ liệu rồi chuyển đích có rollback. Kiểm bằng DB tạm và lỗi restore giả lập. Tài liệu vận hành cần ghi rõ điểm chuyển và quay lại.
- **Bằng chứng.** `scripts/restore.sh:41–55`.

### 3. Batch size âm có thể hoàn tất update dù chưa xử lý trang mới · TV2

- **Tính đúng đắn dữ liệu.** CLI nhận số nguyên cho batch size và chưa kiểm giá trị dương. Vòng lặp dùng trực tiếp bước nhảy. Với batch âm và có trang cần dựng, vòng lặp có thể rỗng trong khi báo cáo vẫn hoàn tất, mốc quét vẫn tiến. Đây là lỗi có thể bỏ sót dữ liệu khi vận hành thủ công.
- **Đề xuất.** Kiểm giá trị dương tại lớp CLI và điểm vào pipeline cho giá trị từ config. Chặn trước tác động lên nguồn hoặc kho đích. Test dùng adapter giả để xác nhận checkpoint và index giữ nguyên với tham số ngoài miền.
- **Bằng chứng.** `backend/ingest/__main__.py:39–40,59–60`, `backend/ingest/update.py:266–269,286–293`.

## P2

### 4. Đọc lịch sử ở chế độ memory thiếu kiểm tra quyền tương đương PostgreSQL · TV1, phối hợp TV3

- **Bảo mật có điều kiện.** Route truyền ngữ cảnh xác thực vào service nhưng nhánh memory đọc lịch sử theo ID hội thoại mà chưa kiểm quyền theo phiên/token/service như đường lưu trữ. Rủi ro áp dụng nếu môi trường chạy chat với memory persistence. Compose production trong repo cấu hình PostgreSQL.
- **Đề xuất.** Áp dụng cùng hợp đồng phân quyền qua hai chế độ hoặc tắt đọc lịch sử riêng tư khi memory không có metadata quyền. Kiểm chủ sở hữu và phiên khác bằng fixture nội bộ cho mỗi chế độ.
- **Bằng chứng.** `backend/app/api/routes/conversations.py:36`, `backend/app/services/chat.py:105–109,220–239`, `backend/core/config.py:93`, `docker-compose.prod.yml:47`.

### 5. Xóa tài khoản có thể dừng giữa các bước mà mất đường retry · TV1, phối hợp TV3

- **Riêng tư và độ tin cậy.** Các phiên bị xóa ở transaction đầu. Các lô PostgreSQL/Qdrant sau đó có thể lỗi khi một phần công việc đã hoàn tất. Nhánh xử lý hội thoại còn sót xóa user trong PostgreSQL rồi mới dọn vector. Nếu bước sau cùng lỗi, phiên cũ đã mất và ID cần dọn không còn lưu ở nơi retry có thể đọc. Thông báo “chưa có dữ liệu nào bị xóa” không phản ánh mọi đường lỗi.
- **Đề xuất.** Dùng trạng thái dọn bền vững hoặc outbox giữ các ID còn phải đồng bộ, hỗ trợ retry idempotent và trả trạng thái chính xác. Kiểm lỗi giả ở giữa lô và cuối đường xử lý hội thoại phát sinh.
- **Bằng chứng.** `backend/app/services/privacy.py:56–70,88–115`, `backend/app/api/routes/auth.py:210`, `docs/privacy.md:30`.

### 6. Chính sách miền Tavily mặc định mềm hơn SRS · TV3, phối hợp TV1

- **Bảo mật theo yêu cầu sản phẩm.** FR-RET-08 yêu cầu giữ miền allowlist. Giá trị mặc định `prefer` cho phép đường tìm và khôi phục evidence vận hành với phạm vi rộng hơn `restrict`. Điều này ảnh hưởng nguồn chứng cứ được nhận. Rà soát này xác minh sai lệch chính sách tin cậy qua mã.
- **Đề xuất.** Đồng bộ SRS và mặc định triển khai. Áp cùng chính sách vào kết quả mới và evidence lấy lại từ state. Kiểm bằng provider giả và fixture ngoài danh sách.
- **Bằng chứng.** `docs/02_SRS.md:150`, `backend/core/config.py:134`, `.env.example:138`, `docker-compose.yml:121`, `backend/app/adapters/tavily.py:37,92,113`, `backend/app/rag/task_plan.py:48`.

### 7. Hai đường chat Discord xử lý thông tin định danh không đồng nhất · TV4

- **Riêng tư.** Đường xử lý tin nhắn thường ẩn ID trong mention người dùng, role, channel và custom emoji trước khi gửi backend. Slash command `/ask` gửi text option trực tiếp. Cùng nội dung có thể đi qua hai mức làm sạch khác nhau.
- **Đề xuất.** Dùng chung tiện ích chuẩn hóa/redact đầu vào Discord ở cả hai đường. Kiểm payload gửi service bằng dữ liệu giả.
- **Bằng chứng.** `bot/src/commands/ask.ts:40–49`, `bot/src/handlers/message.ts:20–26,64,84`.

### 8. Cache kênh có thể ghi lại kết quả cũ sau khi cấu hình thay đổi · TV4

- **Tính đúng đắn và cấu trúc mã.** Invalidate xóa mục đã resolve. Một truy vấn đang chạy từ trước có thể ghi lại tập kênh cũ và trả kết quả sau khi lệnh disable hoàn tất. Bot có thể tiếp tục áp cấu hình cũ trong thời gian cache.
- **Đề xuất.** Ràng buộc in-flight result theo phiên bản cấu hình theo guild hoặc hủy và đọc lại khi invalidate. Kiểm thứ tự sự kiện bằng deferred promise.
- **Bằng chứng.** `bot/src/utils/guildChannelCache.ts:14–31,42–44`, `bot/src/commands/setup.ts:78–86`.

### 9. Deploy cấp quyền đọc rộng cho toàn cây dữ liệu và model · TV1

- **Bảo mật có điều kiện.** Script bổ sung quyền đọc cho nhóm “other” đối với file, cùng quyền traverse thư mục trên toàn bộ hai cây dữ liệu. Trên VPS có tài khoản local khác và path truy cập được, phạm vi file có thể đọc lớn hơn dữ liệu container cần.
- **Đề xuất.** Dùng group/ACL và đường dẫn mount tối thiểu theo service. Kiểm quyền đọc thực tế bằng danh tính runtime và tài khoản test riêng trên môi trường triển khai.
- **Bằng chứng.** `scripts/deploy.sh:60–62`.

### 10. Image catalog mặc định trỏ bản dữ liệu lịch sử · TV1, phối hợp TV2 và TV3

- **Hardcode và cấu hình.** Settings, Compose và mẫu env dùng `data/clean_runs/s2-full-v2/images.csv`. File đó vắng trên máy đã kiểm, trong khi alias `data/delivery/final/clean/images.csv` tồn tại. Với mặc định trên bản bàn giao này, bộ phân giải ảnh có thể đi vào `catalog_unavailable` và text chat vẫn tiếp tục.
- **Đề xuất.** Chọn catalog theo release manifest hoặc cấu hình đích cụ thể. Preflight kiểm artifact khi bật ảnh. Test với fixture catalog của release. Trạng thái ảnh ở VPS cần kiểm riêng.
- **Bằng chứng.** `backend/core/config.py:120`, `docker-compose.yml:133`, `.env.example:157`, `backend/app/services/images.py:96,125,181,280`.

### 11. Tavily adapter phụ thuộc lớp orchestration RAG · TV3

- **Import và kiến trúc.** Adapter mang cả helper web-content từ `app.rag`. Helper kéo tiếp normalization từ overview/rewrite. Điều này làm transport phụ thuộc mã orchestration, trái hướng phân lớp được mô tả trong kiến trúc. Đây là sai lệch tầng con bên trong `app`.
- **Đề xuất.** Đưa xử lý text thuần vào `core/text` hoặc đặt bước lọc/excerpt ở phía gọi adapter. Giữ adapter tập trung vào giao tiếp provider. Bổ sung kiểm tra hướng phụ thuộc và chạy lại các test excerpt/adapter.
- **Bằng chứng.** `backend/app/adapters/tavily.py:12`, `backend/app/rag/web_content.py:6`, `docs/04_ARCHITECTURE.md:66–78`.

### 12. Nhánh build RAG cũ dùng bảng số Samurai/Moonveil gắn cứng · TV3, phối hợp TV2

- **Hardcode và provenance.** Nhánh fallback kiểm phân bổ với chỉ số cơ bản và điều kiện Moonveil khai báo trong code. Agent/generator vẫn có đường dùng fallback khi không có structured build data. Điều này làm kết quả kiểm trong trường hợp được hỗ trợ phụ thuộc hằng số mã nguồn.
- **Đề xuất.** Dùng chung luồng kiểm dữ liệu có chứng cứ đã có. Thiếu dữ liệu thì trả trạng thái thiếu bằng chứng cho bước generation. Giữ hằng số mẫu trong fixture nếu cần test toán học.
- **Bằng chứng.** `backend/app/rag/build_math.py:5–7,21–32`, `backend/app/rag/tool_agent.py:470–479`, `backend/app/rag/generator.py:254–266`.

### 13. Khôi phục local storage giữ clarification chưa được xác thực · TV4

- **Độ ổn định.** Lớp đọc kiểm các trường message cơ bản nhưng giữ trường clarification tùy chọn từ object lưu. MessageList dùng `question.trim()` theo kiểu dữ liệu mong đợi. Dữ liệu cũ hoặc hỏng có thể làm gián đoạn render lịch sử.
- **Đề xuất.** Dùng lại validator `readClarification` khi khôi phục. Giữ message cơ bản hợp lệ, kiểm fixture dữ liệu cũ và trường tùy chọn sai dạng.
- **Bằng chứng.** `web/src/lib/storage.ts:25–45`, `web/src/components/chat/MessageList.tsx:46–51,69,131–135`, `web/src/api/clarification.ts`.

### 18. Deploy có thể báo thành công khi health check HTTPS thất bại · TV1

- **Độ tin cậy vận hành.** Health check nội bộ chạy trước. Nếu kiểm HTTPS công khai thất bại, script in trạng thái chưa đạt rồi vẫn in thông báo hoàn tất và kết thúc thành công. Công cụ gọi script có thể ghi nhận deploy đạt dù ingress gặp lỗi.
- **Đề xuất.** Trả trạng thái lỗi cho health check HTTPS. Nếu cần hỗ trợ bootstrap chứng chỉ, dùng lựa chọn có chủ ý và báo rõ trạng thái. Kiểm script với dịch vụ giả.
- **Bằng chứng.** `scripts/deploy.sh:85–105`.

### 19. Bộ xác minh chỉ số build có thể ghép số với sai chủ thể · TV3, phối hợp TV2

- **Tính đúng đắn của bằng chứng.** Nhánh kiểm văn xuôi trả kết quả khi nhãn và giá trị khớp trước khi kiểm chủ thể. Việc xuất hiện tên class/weapon ở một hit khác chưa gắn được giá trị với chủ thể đó. Hậu quả là validator có thể chấp nhận số từ thực thể khác khi các hit trộn ngữ cảnh.
- **Đề xuất.** Ràng buộc chủ thể, thuộc tính, giá trị và locator trong cùng đơn vị nguồn. Thêm regression fixture hai chủ thể cùng nhãn nhưng giá trị khác.
- **Bằng chứng.** `backend/app/rag/build_data.py:59–84,135–153`.

### 20. Lệnh full pipeline và update có thể lấy tokenizer từ hai nơi · TV2

- **Hardcode và tính tái lập.** Helper full tìm tokenizer dưới `models/fastembed` khi thiếu `--tokenizer`. Update dùng `settings.rag_models_dir`. Cấu hình cache riêng có thể khiến full không tìm được tokenizer hoặc dùng bản khác với update.
- **Đề xuất.** Dùng chung helper theo settings và giữ ưu tiên đường dẫn chỉ định. Kiểm với hai thư mục cache giả khác nhau.
- **Bằng chứng.** `backend/scripts/data_pipeline.py:35,81–86,123`, `backend/ingest/update_cli.py:102–104`.

## P3

### 14. Cổng API nội bộ được khai báo lặp ở nhiều consumer · TV1, phối hợp TV4

- **Hardcode và quy ước.** Cổng listener, healthcheck, Caddy upstream và bot nội bộ cùng dùng literal 18000 ở nhiều file. Bảng quy ước ghi `API_PORT` cho local, trong khi nguyên tắc chung yêu cầu một nguồn cấu hình. Trạng thái mặc định hiện khớp nhau. Rủi ro phát sinh nếu đổi một consumer hoặc muốn cấu hình cổng container.
- **Đề xuất.** Chốt hợp đồng cổng container. Dùng một biến chung nếu cần đổi được, hoặc ghi rõ đó là hằng số giao tiếp nội bộ và kiểm đồng nhất xuyên các consumer. Giữ ngoại lệ cổng gốc của DB/Redis/Qdrant theo quy ước.
- **Bằng chứng.** `docs/quy_uoc.md:123–145`, `backend/Dockerfile:30`, `infra/caddy/snippets.caddy:6`, `docker-compose.yml:146,162`.

### 15. Bot cố định thời hạn chia sẻ trong thông báo · TV4, phối hợp TV1

- **Hardcode.** Hai thông báo ghi 24 giờ, dù API trả `expires_at`. Giá trị hiện khớp TTL mặc định. Copy sẽ sai nếu hợp đồng TTL thay đổi.
- **Đề xuất.** Hiển thị thời điểm từ API hoặc dùng nội dung trung tính về thời lượng. Kiểm response giả với TTL khác.
- **Bằng chứng.** `bot/src/commands/ask.ts:74,79`, `bot/src/api/client.ts:262–266`, `backend/app/services/answer_shares.py:14,36,46`.

### 16. Import động thư viện chuẩn làm khó đọc trong ingest · TV2

- **Chất lượng mã.** `__import__` được gọi trực tiếp cho `itertools` trong vòng đọc CSV và `re` lặp lại trên một biểu thức. Module chuẩn có thể import tĩnh. Đây là đề xuất dọn mã, Ruff hiện đạt cấu hình repo.
- **Đề xuất.** Import `re` và `zip_longest` ở đầu module. Chạy lại test xử lý bảng/CSV để giữ hành vi.
- **Bằng chứng.** `backend/ingest/chunk/full.py:278`, `backend/ingest/transform/full.py:246`.

### 17. Kiểu dữ liệu transport quảng bá turn ID mà transport không dùng · TV4

- **Hợp đồng mã.** `turnId` được tiêu thụ trong hook cho retry, nhưng cũng có trong kiểu option transport. Caller của transport có thể hiểu rằng tùy chọn đó điều khiển request. Rà soát chưa xác định lỗi mất lượt chat từ điểm này.
- **Đề xuất.** Đặt retry ID trong kiểu đầu vào của hook hoặc biểu diễn rõ nó được chuyển thành trường nào. Kiểm hợp đồng typing của hai lớp.
- **Bằng chứng.** `web/src/api/chat.ts:8–14`, `web/src/hooks/useChatStream.ts:19,44–45`.

### 21. Hai service ảnh có vòng phụ thuộc qua import trì hoãn · TV3, phối hợp TV2

- **Import và chất lượng mã.** Service tải ảnh import helper từ image catalog, còn catalog import hằng số cache ngược lại bên trong hàm. Đây là coupling khi bảo trì, chưa ghi nhận lỗi khởi động.
- **Đề xuất.** Đặt nơi lưu cache và chính sách định dạng ở module dùng chung hoặc inject qua cấu hình. Chạy test resolver và downloader hiện có.
- **Bằng chứng.** `backend/app/services/answer_media.py:24`, `backend/app/services/images.py:206`.

### 22. Semantic memory kiểm schema Qdrant hai lần trên cùng đường đọc · TV3

- **Phân lớp và hiệu năng.** Orchestration chứa phần I/O Qdrant trực tiếp. Cả recall và phương thức search bên dưới đều gọi kiểm schema, tạo hai lượt tuần tự ở đường đọc có vector. Kiểm owner/conversation/revision vẫn tồn tại trong đường xác minh kết quả.
- **Đề xuất.** Dời adapter Qdrant về `core/vector`, đặt một điểm kiểm schema theo lifecycle. Đo số lượt gọi bằng client giả.
- **Bằng chứng.** `backend/app/rag/semantic_memory.py:7,21–99,111,123–131`.

## Kiểm chứng và giới hạn

- Đã đọc source tại worktree detached cùng commit. Ruff check đạt, Ruff format check ghi 299 file đúng định dạng. Backend unit suite đạt **1.292 passed, 20 skipped**, với cảnh báo Qdrant local và Alembic.
- AST quét 159 module trong `backend/core`, `backend/app`, `backend/ingest`; không thấy import trực tiếp vi phạm ba ranh giới package lớn của tài liệu. Kết quả không bao gồm phân tầng bên trong `app` hoặc import động. Mục 11 là đường phụ thuộc bên trong `app`. Hai kiểu module specifier TypeScript được hỗ trợ theo cấu hình và chưa có quy ước cấm.
- Kiểm mã web/bot, CI, deploy và cấu hình. Thấy các cơ chế kiểm admin, chặn raw HTML trong Markdown và kiểm URL trích dẫn ở các đường đã xem. Rà soát bảo mật bằng mã nguồn, chưa chạy tích hợp web/bot, dependency CVE scan hoặc kiểm cấu hình đang phục vụ.
- Checkout chính tại `D:/Index-Beast` giữ trạng thái ban đầu. Báo cáo nằm ngoài repo. Thứ tự duyệt đề xuất trong bản review là xử lý mục 1–3 trước, sau đó rà các P2 theo môi trường và chủ sở hữu.

## Meta prompts đã giao

### Sub-agent backend và vận hành

> Dùng code-review-and-quality. Đọc AGENTS, quy ước và mốc 00d64de. Rà TV1 backend API, auth, service, core DB, Compose, CI, deploy và script. Xem bảo mật, tính đúng đắn, cấu trúc, import và hardcode. Chỉ đọc source. Cho mỗi phát hiện, ghi file/dòng, điều kiện, tác động, mức độ, chủ sở hữu đề xuất, thay đổi nhỏ nhất và cách test an toàn. Ghi nhận các kiểm soát đã thấy. Giữ working tree.

### Sub-agent ingest và RAG

> Dùng code-review-and-quality cùng tài liệu phân lớp. Rà TV2 crawl, clean, bảng, chunk, update, retention và TV3 RAG, provider, vector, LLM, eval. Ưu tiên provenance, quyền riêng tư, chiều import, cấu hình so với hằng số và retry/checkpoint. Chỉ đọc source. Trả bằng chứng file/dòng, impact, mức độ, owner và kiểm thử giả lập phù hợp. Giữ working tree.

### Sub-agent web và Discord bot

> Dùng code-review-and-quality và quy ước dự án. Rà React, Discord bot và đường gọi API của TV4, state phiên, dữ liệu lưu browser, validation, cache, module imports và hardcode. Chỉ đọc source. Báo lỗi có đường đi trong mã, phạm vi liên quan, mức độ, owner, đơn vị sửa và cách kiểm với fixture. Ghi lý do bỏ các ứng viên thiếu bằng chứng.

### Agent tổng hợp

> Chốt commit origin/develop mới nhất bằng Git fetch, đọc độc lập các đường lỗi và quy ước. Gộp phát hiện trùng, hiệu chỉnh ưu tiên theo điều kiện áp dụng, chạy kiểm tra offline có sẵn và xác nhận checkout. Xuất một file Markdown gồm báo cáo và meta prompts. Chờ người dùng duyệt trước khi sửa.
