# Bỏ qua thư mục `.claude/` trong Git

| | |
|---|---|
| Ngày | 02/11/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `chore/s3-tv1-gitignore-claude` (từ `develop`) |

- `.gitignore`: thêm `.claude/`. Thư mục này chứa cấu hình cục bộ của Claude Code (vd. `launch.json` khai báo `make api`/`make web` để xem hệ thống trong khung trình duyệt của ứng dụng), không thuộc dự án và khác nhau giữa các máy.
- Kiểm tra: `git status` không còn hiện `.claude/`. Không có file nào trong `.claude/` từng được commit.
