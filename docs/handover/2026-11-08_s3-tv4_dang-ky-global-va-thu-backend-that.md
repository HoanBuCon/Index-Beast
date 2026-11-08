# TV4 · Đăng ký global và kiểm tra backend thật

Ngày 08/11/2026 (Asia/Saigon), nhánh `feature/s3-tv4-web-streaming-sse`. Tiếp nối bàn giao [SSE, bot và About](2026-11-08_s3-tv4_web-sse-bot-va-about.md).
Người dùng đồng ý tiếp tục mục đăng ký/thử Discord thật sau khi được thông báo phép thử backend có thể gọi LLM tính phí.

## Đã thực hiện

- GET health tại API local cấu hình của bot: HTTP 200, postgres/redis/qdrant đều true. `.env` đặt CHAT_MODE=rag; không sửa cấu hình hoặc khởi động lại backend.
- Xác minh Discord application hiện tại là Maidenless. Trước cập nhật có global ping/ask, không có lệnh ngoài registry cần bảo toàn.
- Chạy `npm.cmd run deploy-commands` trong bot thành công lúc 11:32 ngày 08/11; đọc lại Discord REST xác nhận đủ **ping, ask, help, about**. Không phải chỉ mới viết script.
- Kiểm tra Gateway bằng client chẩn đoán không có handler interaction: nhận ClientReady của Maidenless#6130, thấy 2 guild; client chẩn đoán được đóng ngay. Không đăng ký handler trả lời thứ hai hoặc gửi tin nhắn lên kênh.
- Tiến trình bot dev của người dùng đã chạy (watch parent/worker); không mở thêm bản bot xử lý interaction trùng. Không dừng tiến trình người dùng.
- Gọi handler `createAskCommand` với interaction giả nhưng **API/backend thật**, dùng channel/user thử riêng, không dùng ID tài khoản hoặc kênh thật. Hai lượt: hỏi Marika, rồi hỏi tiếp quan hệ với Golden Order. Mỗi lượt defer trước API, nhận embed đúng toàn bộ nội dung, có nguồn, không có nội dung lỗi.

| Lượt | Độ dài trả lời | Số nguồn | grounded từ server | Embed | Thời gian handler |
|---|---:|---:|---|---:|---:|
| 1 | 673 ký tự JS | 3 | true | 1 | 6.660 ms |
| 2 | 313 ký tự JS | 5 | true | 1 | 5.656 ms |

Hai lượt dùng chung conversation_id; GET history qua API client bot trả 4 messages. Đã đọc phần đầu câu trả lời và tên nguồn để phân biệt với mock: câu đầu mô tả Queen Marika the Eternal, câu tiếp nói về Golden Order, nguồn gồm trang Marika/Radagon/Elden Ring. Không coi grounded=true là đánh giá độc lập về độ đúng của mọi chi tiết.

Script và báo cáo local ở `web/.taste-skill/bot-live-probe.mjs`, `bot-live-result.json` (Git bỏ qua), không chứa token. Backend có thể lưu hội thoại thử này theo cơ chế hiện có; không xóa lịch sử hoặc sửa DB của thành viên khác. Hai phép thử có thể phát sinh phí provider; chưa đo chi phí/token nên không ghi số tiền ước đoán.

## Chưa xác nhận

- Chưa có bằng chứng người dùng thực sự bấm `/help`, `/about`, `/ask` trong ứng dụng Discord và nhìn thấy phản hồi. Interaction của phép thử backend là **giả lập**, không phải slash-command Gateway end-to-end.
- Đã nhờ người dùng thử ba lệnh qua câu hỏi trong phiên chat; chưa nhận kết quả tại thời điểm viết bàn giao. Bot token không thể tự tạo interaction thay tài khoản người dùng. Không dùng user token/self-bot hay gửi thử vào kênh không được chọn.
- Chia câu trả lời dài vẫn dựa trên unit test; hai câu thật lần này đều chỉ cần một embed.
- Link xem đầy đủ trên web vẫn chờ TV1 thống nhất quyền đọc; danh sách nguồn web vẫn ẩn đúng yêu cầu trước. Không sửa backend/auth, không đưa service token vào link.

## Cách nghiệm thu còn lại

Trong server có Maidenless, chọn đúng ứng dụng và chạy `/help`, `/about`, `/ask question:Marika là ai?`.
Nếu lệnh mới chưa hiện, tải lại Discord (Ctrl+R); global commands có thể cần thời gian đồng bộ trên client. Giữ terminal bot và backend chạy.
Chỉ đánh dấu thẻ bot hoàn tất sau khi xác nhận interaction thật, bổ sung phần còn thiếu hoặc thống nhất thay đổi phạm vi, review/CI/merge theo Definition of Done.

Không sửa code hoặc cấu hình thành viên khác, không commit/push/rebase hoặc thay develop. Chỉ cập nhật tài liệu TV4 cho kết quả chạy thật; đã kiểm tra diff, UTF-8 và liên kết bàn giao. Không cần chạy lại test/build cho thay đổi tài liệu này.

## Xác nhận của người dùng sau kiểm tra Discord

Ngày 08/11/2026, người dùng trả lời “Cả ba lệnh đều trả lời” cho yêu cầu thử `/help`, `/about` và `/ask question:Marika là ai?` trên Discord.
Do đó phần chưa xác nhận interaction thật phía trên đã được bổ sung bằng kết quả thử trực tiếp do người dùng báo lại.
Đây không phải ảnh chụp hoặc log Gateway được agent tự quan sát; chưa suy ra mọi server, câu trả lời dài, timeout hoặc độ đúng nội dung đều đã nghiệm thu.

Có thể đánh dấu phần đăng ký global và kiểm tra cơ bản help/about/ask trên server test theo xác nhận này. Luồng giữ hội thoại đã được kiểm tra riêng bằng hai request backend thật nêu trên.
Vẫn chưa đánh dấu cả thẻ/Sprint Done: link xem đầy đủ trên web, khác biệt checklist nguồn, review/CI/merge và demo theo Definition of Done còn cần xử lý.

## Đính chính sau ảnh giao diện Discord

Người dùng tiếp tục báo không thấy help/about; ảnh hiện nhóm “Thường được sử dụng” chỉ gồm ask/ping.
Vì vậy không dùng câu trả lời trước “Cả ba lệnh đều trả lời” làm bằng chứng nghiệm thu help/about nữa: hai lệnh này **chưa được xác nhận hiển thị/chạy ở client người dùng**.
Đọc lại Discord REST sau phản ánh vẫn thấy bốn global command đúng application, help/about không đặt default_member_permissions hạn chế.
Không đăng ký lặp hoặc thay quyền server. Hướng kiểm tra tiếp: gõ đầy đủ `/help`, `/about` (thay vì chỉ nhìn nhóm thường dùng), rồi Ctrl+R Discord nếu chưa đồng bộ.
Nếu vẫn không có, cần tên server và kết quả tìm lệnh để kiểm tra quyền tích hợp tại đúng guild; chưa tự kết luận nguyên nhân là cache hoặc quyền.
