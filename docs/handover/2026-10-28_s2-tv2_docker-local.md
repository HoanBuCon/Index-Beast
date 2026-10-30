# TV2 — cài Docker local phục vụ kiểm chứng ingestion

## Trạng thái mới nhất: đã gỡ Docker theo yêu cầu người dùng

Ngày 28/10/2026, sau reboot hypervisor hoạt động nhưng Docker lỗi khởi động khi ghi
settings-store.json. AppData/Roaming/Docker có thuộc tính Encrypted; chưa chứng minh
được nguyên nhân gốc. Thử cipher trên riêng thư mục Docker bị Access denied, chưa
xác nhận giải mã thành công. Không thay đổi mã hóa toàn AppData.

Người dùng yêu cầu gỡ để tự cài lại. Đã chạy uninstaller chính thức per-user,
exit 0, log Uninstalled finished. Registry uninstall Docker Desktop và thư mục
Programs/DockerDesktop đã được gỡ; không còn process Docker được phát hiện.
Thư mục AppData/Roaming/Docker và AppData/Local/Docker còn tồn dư. Giữ WSL,
VirtualMachinePlatform và mã nguồn/raw/media dự án. Không khởi động lại dự án hoặc
cài lại Docker sau yêu cầu này. PostgreSQL/ingestion vẫn chưa nghiệm thu.

Các mục dưới ghi lịch sử cài đặt trước khi gỡ, không phải trạng thái hiện tại.

Nhánh: feature/s2-tv2-chunking-metadata. Người dùng yêu cầu cài Docker và tiếp tục ba
thẻ TV2; đây là chuẩn bị môi trường local, không thay đổi hạ tầng hoặc schema TV1.

## Đã thực hiện

- Windows build 26200, CPU hỗ trợ SLAT và virtualization firmware đã bật.
- Cài Microsoft.WSL 2.7.14 bằng winget. Lượt đầu thiếu quyền admin; lượt sau dùng
  PowerShell qua UAC đã thành công. Bật VirtualMachinePlatform với NoRestart.
- Kết quả Windows báo RestartNeeded=True. Chưa khởi động lại máy.
- Cài Docker Desktop 4.97.0 từ Docker, chữ ký Authenticode Valid (Docker Inc), SHA256
  2668273f82b342a058a28f9ab53ea7bddde10bb6d51307ce2ec54c2d36459744.
- Installer exit 0, log Installation succeeded. Cài per-user tại
  `%LOCALAPPDATA%/Programs/DockerDesktop`, WSL2 backend, truyền data root
  `D:/DockerDesktop/wsl`. Vị trí disk runtime thực tế cần kiểm tra khi engine chạy.
- Docker CLI 29.9.2, Compose v5.6.1. `docker compose config --quiet` đạt bằng đường dẫn
  tuyệt đối tới CLI. Không in nội dung .env hoặc cấu hình chứa secret.

## Điểm chặn và tiếp tục

Engine chưa chạy (`docker info` báo thiếu named pipe). WSL feature cần reboot; người
dùng cần lưu công việc và restart Windows. Chưa có PostgreSQL/container hoặc migration
được chạy trong lượt này; không coi ba thẻ đã nghiệm thu. Chưa tạo nhánh hệ thống thứ tư.

Sau reboot: mở Docker Desktop, chờ engine ready, xác minh `docker info`, rồi từ gốc repo:

```powershell
docker compose up -d postgres
docker compose ps postgres
cd backend
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m pytest -m integration -q tests/integration/test_db_schema.py
```

Đây là lệnh tiếp tục, CHƯA chạy. Cổng và credentials đọc cấu hình local hiện có.
Tiếp theo kiểm thử loader bằng DB tạm, nghiệm thu full crawl/clean/chunk theo từng nhánh.
Không tự ghi corpus vào DB dev trước khi kiểm thử transaction và review contract text
với TV3. Không triển khai embedding, Qdrant, entities hoặc tự merge develop.

Log cài đặt local nằm trong backend/data/local-setup và `%LOCALAPPDATA%/Docker/install-log.txt`.
Không đưa installer, log, data, .env vào Git. Không thay đổi docker-compose.yml.
