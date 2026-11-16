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

Để trả lời, câu hỏi của bạn (cùng đoạn wiki liên quan) được gửi tới dịch vụ mô hình ngôn ngữ (DeepSeek) và, khi bạn bật tìm web, tới dịch vụ tìm kiếm (Tavily). Đừng nhập thông tin cá nhân vào câu hỏi.

## Lưu trong bao lâu

- **Hội thoại và mọi thứ gắn với nó** (tin nhắn, đánh giá, ký ức, trace) bị xóa tự động sau **90 ngày kể từ hoạt động cuối** của hội thoại đó.
- **Phiên đăng nhập** bị xóa khi hết hạn.
- **Tài khoản** giữ đến khi bạn xóa.
- Bản sao lưu cơ sở dữ liệu của người vận hành (nếu có) cũng không được giữ quá thời hạn trên; nhóm sẽ ghi rõ ở mục vận hành.

## Cách xóa dữ liệu của bạn

- **Xóa tài khoản trên web** (gọi `DELETE /api/v1/me` khi đã đăng nhập): xóa tài khoản, mọi phiên và các hội thoại **đã gắn với tài khoản** (kể cả hội thoại khách bạn đã "nhận" sau khi đăng nhập), cùng tin nhắn, đánh giá và ký ức, kể cả vector tìm kiếm. Không hoàn tác được. Hội thoại khách chưa nhận (ví dụ trên thiết bị khác) và hội thoại Discord **không gắn với tài khoản** nên không bị xóa ở bước này; chúng tự xóa sau 90 ngày không hoạt động, hoặc bạn xóa Discord bằng `/clear`. Nếu việc xóa lỗi giữa chừng, hệ thống trả lỗi và chưa xóa gì, bạn thử lại được.
- **Trong Discord**: lệnh `/clear` của bot (dự kiến, chưa có ở thời điểm viết) sẽ xóa ngữ cảnh hội thoại của bạn với bot. Trong lúc chờ, dữ liệu hội thoại Discord tự xóa sau 90 ngày không hoạt động.
- **Liên kết chia sẻ câu trả lời**: khi bạn tạo liên kết chia sẻ, bản sao câu trả lời được lưu tạm (Redis) và tự hết hạn sau **24 giờ** (`SHARE_TTL_SECONDS`); xóa tài khoản hay hội thoại không xóa bản sao này trước hạn. Nếu muốn nó biến mất sớm hơn, đừng chia sẻ, hoặc liên hệ quản trị viên để xóa.
- **Hội thoại của khách** không gắn với tài khoản: tự xóa sau 90 ngày không hoạt động, hoặc liên hệ nhóm để xóa sớm kèm mã hội thoại.

Muốn hỏi thêm hay yêu cầu xóa dữ liệu mà không đăng nhập được, liên hệ nhóm qua kênh hỗ trợ trên máy chủ Discord của dự án.

---

## Dành cho người vận hành

### Dọn dữ liệu quá 90 ngày (NFR-PRIV-01)

Lệnh chạy từ `backend/`, dùng `DATABASE_URL`, `QDRANT_*` và `CHAT_MEMORY_COLLECTION` như backend, chỉ in số đếm:

```bash
python -m scripts.retention --days 90 --dry-run   # đếm trước, không xóa
python -m scripts.retention --days 90             # xóa thật, theo lô 500 hội thoại
```

Xóa: hội thoại có hoạt động cuối (tin nhắn mới nhất, hoặc lúc tạo nếu chưa có tin) cũ hơn N ngày, kèm tin nhắn, đánh giá, ký ức, trace (`messages.rag_trace`, không có bảng trace riêng) và điểm Qdrant của hội thoại; cùng các phiên đăng nhập đã hết hạn. Điểm Qdrant xóa trước PostgreSQL: Qdrant lỗi thì lệnh dừng, chưa xóa lô đó và chạy lại được.

Cron mẫu (3 giờ sáng hằng ngày; thay đường dẫn cho khớp máy chủ, và dùng cùng biến môi trường với dịch vụ API):

```cron
0 3 * * * cd /opt/index-beast/backend && /opt/index-beast/backend/.venv/bin/python -m scripts.retention --days 90 >> /var/log/index-beast/retention.log 2>&1
```

Chạy trong Docker Compose: `docker compose exec api python -m scripts.retention --days 90` (hoặc `docker compose run --rm api ...`). Đầu ra chỉ có một dòng, ví dụ: `deleted: conversations=12 messages=88 feedback=3 expired_sessions=5`.

### Việc còn lại

- Bản sao lưu PostgreSQL phải có vòng đời không quá 90 ngày (PR hạ tầng #109), nếu không dữ liệu đã xóa vẫn nằm trong bản sao lưu.
- `/clear` của bot chưa có; khi làm cần xóa hội thoại và điểm Qdrant qua `app.services.privacy`.
- Web cần nút "Xóa tài khoản" gọi `DELETE /api/v1/me` (hợp đồng ở `docs/api/auth-tv4.md`) và dẫn tới văn bản này.
