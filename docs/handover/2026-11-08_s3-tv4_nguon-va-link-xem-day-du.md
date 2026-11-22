# TV4 · Khối nguồn và link xem đầy đủ câu trả lời

Ngày: 08/11/2026 (Asia/Saigon). Nhánh: `feature/s3-tv4-web-streaming-sse`.

## Phạm vi và quyết định

Người dùng yêu cầu hiện lại khối nguồn `[n]`, tiêu đề + link và hoàn thiện nút xem đầy đủ từ bot.
Người dùng đã cho phép mở rộng đúng phần backend này: **“Cho phép thêm API chia sẻ giới hạn này”**.
Không sửa pipeline RAG/ingestion, schema chat/SSE, quyền history hiện có hoặc migration/database schema.
Không commit, push, rebase hoặc đổi con trỏ `develop` trong tác vụ này.

## Thay đổi

- Web: `MessageList`, `SourceList`, `CitationPopover`, `refinement.css` hiện nguồn cho câu trả lời đã hoàn tất;
  có số `[n]`, tiêu đề, đoạn trích và liên kết HTTP(S) không credentials. Không khôi phục nút feedback đã bỏ trước đó.
- Web: `api/answerShares.ts`, `pages/SharedAnswerPage.tsx`, route `/answer` trong `App.tsx` đọc một bản chia sẻ.
  Trang có loading/lỗi/thử lại, hạn dùng, Markdown an toàn, nguồn và thông báo chỉ đọc; mở đầu trang thay vì tự cuộn xuống cuối.
- Backend: thêm router `answer_shares.py`, schema `answer_share.py`, service `answer_shares.py` và đăng ký router.
  Chỉ dịch vụ có `X-Service-Token` hợp lệ được tạo snapshot của đúng một câu trả lời trong hội thoại Discord.
  Public GET nhận capability qua `X-Answer-Share-Token`, không mở quyền đọc cả lịch sử.
- Bot: client/types/config và handler `/ask` tạo link sau khi nhận answer; nút **Xem đầy đủ trên web · 24 giờ** trên embed đầu.
  Giữ chia embed đầy đủ; tạo link lỗi thì vẫn trả câu trả lời, không gọi lại LLM. Bổ sung hướng dẫn `/help` và log warn.
- Cập nhật `web/IMPLEMENTATION.md`, `bot/IMPLEMENTATION.md`, OpenAPI và [giao kèo API](../api/answer-shares-tv4.md).
  Thêm test backend/bot/web; cập nhật hai test web để khớp yêu cầu hiện lại nguồn.

## Quyền riêng tư và giới hạn

Token ngẫu nhiên 32 byte; Redis dùng khóa SHA-256(token), TTL 24 giờ, đọc không gia hạn.
Snapshot chỉ gồm câu hỏi, câu trả lời, nguồn, grounded và thời hạn; JSON snapshot trong Redis không được mã hóa bởi tính năng này.
Ai có link có thể đọc câu trả lời đến khi hết hạn. Redis mất dữ liệu hoặc evict có thể làm link hết hiệu lực sớm.
Token nằm trong fragment `WEB_URL/answer#token`; frontend gửi qua header API, không query/path hoặc localStorage.
Response thành công đặt `Cache-Control: no-store` và `Referrer-Policy: no-referrer`.
Giới hạn snapshot 1 MB, answer 100.000 ký tự và 100 nguồn. Link lỗi không làm mất phần trả lời Discord.
Không thay cơ chế quyền của TV1 ở các endpoint khác. Không trình bày token chia sẻ như quyền truy cập hội thoại.

## Đã kiểm tra thực tế

- 56 test backend đạt: answer shares, chat API, chat guard, memory graph; Ruff lint/format các file Python thay đổi đạt.
- 33 test bot đạt; sau cập nhật câu chữ `/help`, chạy lại typecheck và 4 test liên quan đạt. Kiểm tra định dạng bot đạt.
- 46 test web đạt; TypeScript/Vite build và kiểm tra định dạng đạt.
- OpenAPI export/check đạt; không khởi động model hoặc gọi LLM để sinh schema.
- Kiểm thử HTTP bằng API mock riêng và Redis thật: tạo snapshot có service auth, đọc qua API thường,
  đúng toàn bộ câu trả lời, không trả các lượt khác; từ chối tạo không auth và đọc không token.
  Token chia sẻ không đọc được lịch sử của probe. Sau khởi động lại API, snapshot vẫn đọc đúng từ Redis.
- Trình duyệt thật ở 1440 px và 360 px: hai nguồn đánh số, link đọc được, không tràn ngang,
  bàn phím mở được đoạn trích; token sai hiện lỗi, không tự dùng demo. Kiểm tra URL qua địa chỉ VPN và proxy Vite.
- Unit test bao gồm hết hạn, token sai, target sai, Redis lỗi/hỏng/timeout và bot fallback khi tạo link lỗi.
  Không chờ thực tế 24 giờ để kiểm tra hết hạn; trường hợp này kiểm tra bằng test.

Không gọi LLM mới trong tác vụ này. Probe RAG cũ không còn tìm thấy sau restart nên dùng API mock riêng để kiểm tra chia sẻ,
không sửa hành vi lưu history của thành viên khác. API mock riêng cổng 18001 đã dừng.
Ảnh `/help` và `/about` người dùng cung cấp xác nhận hai lệnh trả lời trên Discord; chưa xác nhận người dùng bấm nút chia sẻ mới.

## Cách dùng và môi trường local

`.env` local chỉ cập nhật `WEB_URL` từ loopback sang địa chỉ web của máy trên VPN; không sửa key/secret khác.
File `.env` và bản sao local trước chỉnh đều bị Git ignore; không đưa secret vào bàn giao.
Backend cổng 18000 và Vite cổng 15173 đã được mở để kiểm tra; bot có sẵn của người dùng không bị dừng hoặc chạy trùng.

1. Tại terminal bot đang chạy, nhấn `Ctrl+C`; từ thư mục gốc dự án chạy `make bot` để nhận `WEB_URL` mới.
2. Gửi một câu hỏi mới bằng `/ask`; chờ trả lời và bấm **Xem đầy đủ trên web · 24 giờ**.
3. Người mở link phải truy cập được địa chỉ `WEB_URL` (cùng VPN trong cấu hình local hiện tại).
   Khi triển khai public, cấu hình URL HTTPS gốc truy cập được; API dùng proxy cùng origin hiện có.

Không cần đăng ký lại slash command vì không đổi định nghĩa lệnh. Tin nhắn Discord cũ không được tự thêm nút.
Khối nguồn chỉ xuất hiện khi câu trả lời hoàn tất và có nguồn. Review/merge và kiểm thử người dùng thực tế trên Discord còn để nhóm xác nhận.
