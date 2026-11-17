# TV3 · Việt hóa chú thích cấu hình `.env.example` (16/11/2026)

## Phạm vi

- Việt hóa phần văn xuôi trong chú thích của `.env.example`; giữ nguyên tên biến, giá trị, thứ tự, URL, tên model và các dòng cấu hình bị chú thích.
- Không đọc hoặc thay đổi `.env`; không ghi secret. Không commit/push/merge.
- Nhánh: `feature/s4-tv3-api-reranker`; giữ nguyên mọi thay đổi reranker hiện có.

## Kiểm tra

- So sánh với `HEAD`: mọi dòng không phải chú thích và mọi dòng cấu hình bị chú thích giống hệt từng byte.
- Giữ mã hóa UTF-8 không BOM và kiểu xuống dòng LF.
- `backend/.venv/Scripts/python.exe -m pytest tests/unit/test_env_example.py -q` từ `backend/`: 2 passed.
- `git diff --check`: đạt.
