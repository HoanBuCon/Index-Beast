# Sửa `make migrate`, `test`, `lint`, `format`, `openapi` khi chưa kích hoạt venv

| | |
|---|---|
| Ngày | 08/11/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `fix/s3-tv1-make-venv` (từ `develop` tại `162aab2`) |

## Vấn đề

`make migrate` báo `alembic: command not found` khi chạy trong terminal chưa kích hoạt `backend/.venv` (ví dụ PowerShell mở mới). Năm target `migrate`, `openapi`, `test`, `lint`, `format` gọi thẳng `alembic`, `python`, `pytest`, `ruff`, trong khi các target khác (`api`, `trace`, `data`, `env`, `test-unit`) đã dùng `$(PYTHON)` của venv.

## Đã sửa

Cả năm target gọi qua `"$(PYTHON)" -X utf8 -m <công cụ>`, cùng cách với `make data` và `make trace`. `PYTHON` tự chọn `backend/.venv` khi có, không thì dùng `python` trong PATH, nên môi trường đã kích hoạt venv vẫn chạy như cũ. Chỉ đổi cách gọi, không đổi lệnh hay tham số.

## Kiểm tra

- `make -n migrate test lint format openapi`: cả năm lệnh dùng Python của venv
- `make migrate` chạy thật trên database dev: nâng 0001 lên 0003 thành công
- Chưa chạy `make test`, `make lint`, `make format` đầy đủ qua make; từng công cụ đã chạy trực tiếp bằng cùng Python trong các PR trước

## Giới hạn

Target `lint` và `format` vẫn gọi `npm run` cho web và bot như cũ; chỉ phần backend được sửa.
