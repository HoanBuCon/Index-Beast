# TV4 · Cập nhật venv local sau khi pull LangGraph

Ngày: 07/11/2026 (Asia/Saigon). Nhánh bàn giao hiện tại: `feature/s3-tv4-hoan-thien-web-bot`. Chưa commit/push.

Hai thay đổi handover ban đầu được tạo khi ở `docs/s3-tv4-cap-nhat-venv-langgraph`; người dùng sau đó chuyển sang nhánh feature trên và yêu cầu giữ chúng tại đây. Đã xác minh nhánh hiện tại và hai file còn chưa commit; không tạo commit hoặc push vào `develop`. Thay đổi chưa commit thuộc working tree, chỉ được lưu vào lịch sử nhánh khi người dùng commit trên nhánh feature.

## Sự cố và phạm vi

Người dùng chạy `make dev`, Uvicorn thất bại khi import `app.rag.generator` với `ModuleNotFoundError: No module named 'langgraph'`. Code mới của TV3 đã khai báo LangGraph trong requirements và constraints, nhưng venv local của TV4 chưa cập nhật.

Đã đọc hướng dẫn repo và handover LangGraph/migration của TV3 ngày 06/11. Đây là sửa môi trường chạy trên máy TV4, không phải thay đổi phần triển khai graph của TV3. Không sửa code backend/bot/web, requirements, constraints, cấu hình `.env`, database hoặc index.

## Thực hiện

Từ gốc repo, chạy đúng Python trong `backend/.venv`:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt -c backend/constraints.txt
```

Pip cài LangGraph 1.2.20, langgraph-checkpoint 4.3.1, langgraph-prebuilt 1.1.1, langgraph-sdk 0.4.13 và ormsgpack 1.13.0 theo pin hiện có; các dependency còn lại đã đáp ứng. Không chạy nâng cấp pip hoặc freeze lại constraints.

## Kiểm tra thực tế

- `python -m pip check` trong venv: `No broken requirements found`.
- Import `END`, `START`, `StateGraph` và gọi `create_app()`: thành công; phiên bản LangGraph đúng 1.2.20.
- Chạy lifespan FastAPI và GET `/api/v1/health` qua HTTPX ASGITransport: HTTP 200, PostgreSQL/Redis/Qdrant đều true; đóng tài nguyên sau kiểm tra.
- Không mở thêm server nền hoặc chiếm cổng của người dùng. Chưa chạy lại toàn bộ `make dev`, chưa kiểm thử trình duyệt/Discord hoặc gửi câu hỏi thật.
- Không gọi LLM, chạy embedding, reindex hoặc migration trong tác vụ này.
- Kiểm tra UTF-8, liên kết handover và `git diff --check` đạt.

## Cách dùng

Chạy lại `make dev` từ gốc repo. Nếu code mới sau một lần pull có thêm dependency, cập nhật venv bằng lệnh requirements-dev + constraints ở trên trước khi chạy. Việc thiếu thư viện lần này không yêu cầu nạp lại corpus hoặc tạo lại index.
