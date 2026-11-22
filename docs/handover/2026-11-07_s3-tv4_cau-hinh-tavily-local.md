# TV4 · Cấu hình key Tavily local

Ngày: 07/11/2026 (Asia/Saigon). Nhánh: `feature/s3-tv4-hoan-thien-web-bot`. Chưa commit/push.

Người dùng cung cấp key Tavily và yêu cầu cập nhật file env mẫu. Đã lưu key vào biến `TAVILY_API_KEY` trong `.env` local được Git bỏ qua; `.env.example` giữ giá trị trống và bổ sung ghi chú nơi điền key thật. Không ghi key vào tài liệu hoặc file được theo dõi bởi Git.

Không sửa code backend, bot, web, dependency hoặc pipeline của thành viên khác. Không đổi mode chat hay các lựa chọn tìm web khác. Backend đọc key khi khởi động nên cần restart API để áp dụng; không tự khởi động thêm server nền.

Kiểm tra local: dotenv đọc được key đã cung cấp, Settings nhận key; `.env` được Git bỏ qua và `.env.example` không chứa key thật. Không gọi Tavily hoặc LLM, chưa xác minh hiệu lực/số dư của key bằng request thật.

## Bổ sung `.env` từ `.env.example`

Sau đó người dùng yêu cầu cập nhật `.env` theo file mẫu. Đã bổ sung 45 biến còn thiếu bằng các dòng cấu hình và ghi chú tương ứng từ `.env.example`, theo thứ tự của mẫu; giữ nguyên toàn bộ phần nội dung `.env` đã có trước khi bổ sung.

- Sao lưu nguyên bản trước thao tác vào `.env.before-sync-*`, cùng được Git bỏ qua.
- Kiểm tra bằng dotenv: đủ mọi tên biến của mẫu; toàn bộ 38 biến cũ giữ nguyên giá trị, bao gồm key/mật khẩu và cấu hình corpus local.
- `Settings()` đọc và validate thành công; key Tavily vẫn tồn tại. Kiểm tra Git ignore cho `.env`/backup, UTF-8, liên kết handover và `git diff --check` đạt.
- Các biến mới nhận mặc định của mẫu; không tự chạy migration, tải model, bật agent, gọi API hoặc khởi động thêm tiến trình trong lượt đồng bộ này. Người dùng cần restart backend để tiến trình đang chạy đọc lại cấu hình mới; schema database cần đáp ứng các chế độ mới nếu chúng được sử dụng.
- Không sửa thêm `.env.example` hoặc mã nguồn thành viên khác trong bước đồng bộ. Không commit/push.

## Thay key Tavily theo yêu cầu tiếp theo

Đã thay `TAVILY_API_KEY` trong `.env` bằng key mới do người dùng cung cấp. Đối chiếu dotenv và Settings thành công; mọi biến khác giữ nguyên. Key mới không xuất hiện trong `.env.example` hoặc tài liệu và `.env` vẫn được Git bỏ qua. Không gọi API để xác minh hiệu lực; cần restart backend để dùng key mới.
