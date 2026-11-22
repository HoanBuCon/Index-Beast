# Chính sách quyền riêng tư của IndexBeast

Văn bản này dành cho người dùng cuối (trang "Giới thiệu" của web hiển thị lại). Phần "Dành cho người vận hành" ở cuối chỉ dành cho nhóm.

IndexBeast là chatbot hỏi đáp về Elden Ring, làm ra cho mục đích học tập và không thu tiền. Chúng tôi chỉ lưu những gì cần để chatbot chạy và để bạn xem lại hội thoại của mình.

## Chúng tôi lưu gì

| Dữ liệu | Khi nào có | Lưu như thế nào |
|---|---|---|
| Định danh Discord | Bạn đăng nhập bằng Discord | Chỉ lưu **mã băm HMAC-SHA256** của Discord ID, không lưu ID thô, không lưu email hay mật khẩu. Kèm tên hiển thị Discord và giờ đăng nhập gần nhất. Không thể suy ngược mã băm thành ID nếu không có khóa bí mật của máy chủ |
| Phiên đăng nhập | Bạn đăng nhập | Cookie `httpOnly` giữ token ngẫu nhiên; máy chủ chỉ giữ mã băm SHA-256 của token, hết hạn tự động |
| Hội thoại | Bạn hỏi trên web hoặc trong Discord | Câu hỏi, câu trả lời, nguồn trích dẫn, đánh giá 👍/👎 (nếu có) và một số dấu vết kỹ thuật của lần trả lời (trace) để tìm lỗi. Hội thoại của khách (chưa đăng nhập) gắn với một token giữ trong trình duyệt, máy chủ chỉ giữ mã băm của token đó |
| Ký ức hội thoại | Bạn hỏi nhiều lượt trong một hội thoại | Vài ý chính rút từ hội thoại để trả lời mạch lạc hơn, kèm vector tìm kiếm tương ứng. Chỉ truy hồi trong chính hội thoại đó |
| Nhật ký máy chủ | Mọi yêu cầu | Giờ, đường dẫn, mã trạng thái và thời gian xử lý. Không ghi nội dung câu hỏi, token hay cookie |

Chúng tôi **không** lưu Discord ID thô, email, mật khẩu, số điện thoại, vị trí hay dữ liệu thanh toán, và không bán hay chia sẻ dữ liệu để quảng cáo.

Để trả lời, câu hỏi của bạn (cùng đoạn wiki liên quan) được gửi tới dịch vụ mô hình ngôn ngữ (DeepSeek), tới dịch vụ xếp hạng lại kết quả tìm (Jina, khi máy chủ đặt `RAG_RERANKER_PROVIDER=jina`; production đang dùng) và, khi bạn bật tìm web, tới dịch vụ tìm kiếm (Tavily). Đừng nhập thông tin cá nhân vào câu hỏi.

## Lưu trong bao lâu

- **Hội thoại khách trên web** và dữ liệu gắn với nó bị xóa sau **90 ngày không hoạt động**, khi job lưu giữ được vận hành. Hội thoại gắn tài khoản và hội thoại Discord được giữ; trace RAG của mọi hội thoại được xóa sau 90 ngày tính từ lúc tạo tin nhắn.
- **Nhật ký vận hành** có thời hạn lưu 90 ngày theo chính sách. Xem phần vận hành để biết các loại log được CLI xử lý và các loại cần cấu hình riêng.
- **Phiên đăng nhập** bị xóa khi hết hạn.
- **Tài khoản** giữ đến khi bạn xóa.
- Bản sao lưu cơ sở dữ liệu của người vận hành (nếu có) cũng không được giữ quá thời hạn trên; nhóm sẽ ghi rõ ở mục vận hành.

## Cách xóa dữ liệu của bạn

- **Xóa tài khoản trên web** (gọi `DELETE /api/v1/me` khi đã đăng nhập): xóa tài khoản, mọi phiên và các hội thoại **đã gắn với tài khoản** (kể cả hội thoại khách bạn đã "nhận" sau khi đăng nhập), cùng tin nhắn, đánh giá và ký ức, kể cả vector tìm kiếm. Không hoàn tác được. Hội thoại khách chưa nhận (ví dụ trên thiết bị khác) và hội thoại Discord **không gắn với tài khoản** nên không bị xóa ở bước này; hội thoại khách web được xóa sau 90 ngày không hoạt động khi job chạy; hội thoại Discord không thuộc diện xóa tự động này. Phiên đăng nhập của bạn được giữ đến bước cuối cùng, nên nếu việc xóa lỗi giữa chừng, hệ thống trả lỗi, phần chưa xóa vẫn còn và bạn gọi lại được (lần gọi sau tiếp tục từ chỗ còn sót); khi bước cuối thành công, tài khoản, mọi phiên và hội thoại còn lại bị xóa trong cùng một giao dịch.
- **Trong Discord**: dùng `/clear user` để xóa ngữ cảnh riêng của bạn trong server. Thread dùng chung thuộc phạm vi `/clear all`, cần quyền Manage Server.
- **Liên kết chia sẻ câu trả lời**: khi bạn tạo liên kết chia sẻ, bản sao câu trả lời được lưu tạm (Redis) và tự hết hạn sau **24 giờ** (`SHARE_TTL_SECONDS`); xóa tài khoản hay hội thoại không xóa bản sao này trước hạn. Nếu muốn nó biến mất sớm hơn, đừng chia sẻ, hoặc liên hệ quản trị viên để xóa.
- **Hạn mức hỏi mỗi ngày**: để chặn lạm dụng, hệ thống đếm số câu hỏi và token theo ngày. Với khách, bộ đếm gắn với địa chỉ IP (IPv6 gộp theo /64) và chỉ nằm trong Redis tối đa 2 ngày rồi tự hết hạn, không lưu ở nơi khác; với tài khoản đăng nhập, bộ đếm gắn với mã tài khoản, cũng tự hết hạn sau tối đa 2 ngày.
- **Hội thoại của khách** không gắn với tài khoản: tự xóa sau 90 ngày không hoạt động, hoặc liên hệ nhóm để xóa sớm kèm mã hội thoại.

Muốn hỏi thêm hay yêu cầu xóa dữ liệu mà không đăng nhập được, liên hệ nhóm qua kênh hỗ trợ trên máy chủ Discord của dự án.

---

## Dành cho người vận hành

### Dọn dữ liệu quá 90 ngày (NFR-PRIV-01)

Lệnh chạy từ `backend/`. Cấu hình đích bằng `POSTGRES_*`, `QDRANT_*` và `CHAT_MEMORY_COLLECTION` như backend. Kết quả chỉ chứa số đếm.

```bash
python -m scripts.retention --days 90 --dry-run   # đếm trước, không xóa
python -m scripts.retention --days 90             # xóa thật, theo lô 500 hội thoại
python -m scripts.retention --days 90 --dry-run --ingest-log-dir /var/log/indexbeast # thêm log ingest
```

Xóa: hội thoại web chưa gắn tài khoản có hoạt động cuối (tin nhắn mới nhất, hoặc lúc tạo nếu chưa có tin) cũ hơn N ngày, kèm tin nhắn, đánh giá, ký ức, trace (`messages.rag_trace`, không có bảng trace riêng) và điểm Qdrant của hội thoại; cùng các phiên đăng nhập đã hết hạn. Trường log của ingestion job đã kết thúc quá N ngày được xóa, giữ lại trạng thái và số đếm. Trace RAG của mọi tin nhắn cũ hơn N ngày được xóa riêng; tin nhắn, đánh giá và lịch sử tài khoản hoặc Discord được giữ. Điểm Qdrant xóa trước PostgreSQL: Qdrant lỗi thì lệnh dừng, chưa xóa lô đó và chạy lại được.

Cron mẫu (3 giờ sáng hằng ngày; thay đường dẫn cho khớp máy chủ, và dùng cùng biến môi trường với dịch vụ API):

```cron
0 3 * * * cd /opt/index-beast/backend && /opt/index-beast/backend/.venv/bin/python -m scripts.retention --days 90 >> /var/log/index-beast/retention.log 2>&1
```

Chạy trong Docker Compose bằng `docker compose exec api python -m scripts.retention --days 90`. Dòng tóm tắt liệt kê hội thoại, tin nhắn, đánh giá, phiên hết hạn, trace và payload log đã xoá. Khi truyền `--ingest-log-dir`, CLI in thêm số file log.

Log file: `--ingest-log-dir` là tùy chọn và chỉ duyệt trực tiếp file thường tên `ingest-weekly-YYYYMMDD-HHMMSS.log` cũ hơn N ngày theo mtime; không theo liên kết, không duyệt thư mục con. Chạy trên host có thư mục log; container cần mount thư mục đó. Log đang mở, log `ingest-weekly.skipped.log`, journal, Docker, reverse proxy, `retention.log`, report và backup không được lệnh này dọn; vận hành cần cấu hình rotation/retention riêng và kiểm tra thời hạn. Cron mẫu chưa được cài đặt. Không dùng `--no-vectors` khi cần đảm bảo xóa vector.

### Việc còn lại

- Xác minh vòng đời bản sao lưu PostgreSQL và cấu hình rotation của log hạ tầng trên máy triển khai.
- Nghiệm thu lệnh retention với PostgreSQL và Qdrant ở staging trước khi lên lịch.
