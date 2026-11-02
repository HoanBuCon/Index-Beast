# TV2 — tiếp tục crawl qua Windows Task Scheduler

Nhánh feature/s2-tv2-crawl-toan-bo-wikigg; chỉ vận hành/resume, không merge develop.

## Thực hiện

Xác nhận không có crawler cũ, Docker Engine 29.9.2 hoạt động và PostgreSQL healthy.
Đã đăng ký và start task local IndexBeast-TV2-Crawler, principal là người dùng hiện tại,
Interactive/Limited. Không trigger định kỳ, không lưu password, IgnoreNew và không đặt
giới hạn thời gian chạy. Không đổi Power Plan hoặc yêu cầu máy tự restart.

Task gọi launcher PowerShell dưới data/crawl_runs/s2-full-20261028, dùng Python backend
chạy ingest.crawl.full --run-id s2-full-20261028. Launcher ẩn, stdout/stderr theo timestamp
và scheduled-process.json ghi nhận lần khởi chạy. Task do Windows quản lý thay vì phiên
exec tương tác của Codex. Người dùng phải còn đăng nhập, máy thức, Docker/PG hoạt động.
Không coi đây là service chạy xuyên logout/reboot.

Job mới: crawl-full-02f289b359204e4a9030556add4da79b. Đã xác nhận task Running và report
cập nhật. Bộ đếm report là số trang kiểm chứng lại trong lượt mới, không mất corpus cũ.
Checkpoint trước resume có 2526 trang thành công và các raw đã lưu khi ảnh lỗi.

## Kiểm tra / điều khiển

```powershell
Get-ScheduledTask -TaskName 'IndexBeast-TV2-Crawler'
Get-ScheduledTaskInfo -TaskName 'IndexBeast-TV2-Crawler'
# Chỉ gọi khi đã xác nhận task/crawler cũ không chạy:
Start-ScheduledTask -TaskName 'IndexBeast-TV2-Crawler'
```

Report, checkpoint, history và log nằm trong backend/data/crawl_runs/s2-full-20261028.
Không chạy thêm CLI trực tiếp cùng lúc. Status Running trong JSON phải đối chiếu task,
process và thời điểm cập nhật; Task Scheduler LastTaskResult 267009 là đang chạy, không
phải thành công cuối cùng. Phải đợi report finished_at/status và job DB để nghiệm thu.

Không thay đổi mã xử lý nên không chạy lại unit suite; kiểm chứng vận hành trực tiếp.
Chưa nghiệm thu full corpus/loại DLC, chưa chuyển sang full clean/chunk hoặc nhánh mở rộng.
