# TV1 · Sửa review: ops (restore, deploy, cổng, reranker compose)

Nhánh `fix/s5-tv1-review-ops` (từ `develop` 4bb9e46). Nguồn: mục 2, 9, 14, 18 của `2026-11-17_s5-tv2_ra-soat-ma-toan-he-thong.md` + hai việc lead giao thêm.

## Đã sửa

- **#2 (P1) `restore.sh pg`:** không còn `DROP SCHEMA public` trên DB đang chạy. Nạp vào `${POSTGRES_DB}_restore` (tạo lại mới), kiểm tra (`pg_restore` exit 0; có `alembic_version`, `documents`, `chunks`, `conversations`, `messages`; in phiên bản alembic và số dòng), rồi mới dừng api/bot, ngắt kết nối, `ALTER DATABASE` đổi live -> `<db>_prev_<thời-gian>` và restore -> live, bật lại (giữ quy tắc `DISCORD_TOKEN`), in lệnh quay lại. Lỗi trước bước đổi tên: DB đang chạy nguyên vẹn, api/bot không dừng. Lỗi lúc đổi tên: tự đưa DB cũ về và bật lại dịch vụ.
- **#9 `deploy.sh`:** bỏ `chmod o+rx/o+r`. Cấp đọc cho uid 10001 chỉ trên `backend/data` và `backend/models` (hai thư mục api mount) bằng `setfacl` (kèm ACL mặc định), không có `setfacl` thì `chgrp -R 10001` + `g+rX`; không được thì dừng với hướng dẫn.
- **#18 `deploy.sh`:** kiểm tra HTTPS lỗi thì thoát 1 (kèm lệnh rollback). `ALLOW_HTTPS_PENDING=1` cho lần deploy đầu: cảnh báo rõ rồi thoát 0.
- **#14 cổng 18000:** chốt là hợp đồng cố định của container api, không thêm biến. Ghi ở `docs/production.md` mục 1 và comment tại `backend/Dockerfile`, `infra/caddy/snippets.caddy`, `docker-compose.yml` (đầu file, healthcheck, `BOT_API_URL`), `.env.example`. `test_ports.py` thêm `test_internal_api_port_is_one_fixed_contract` (Dockerfile `--port` và `EXPOSE`, Caddy snippet, healthcheck, `BOT_API_URL` cùng 18000; docs có ghi).
- **Reranker trong compose:** `docker-compose.yml` truyền `RAG_RERANKER_PROVIDER` (mặc định `local`) và `RAG_RERANKER_LOCAL_{MODEL,THREADS,MAX_CANDIDATES,MAX_CHARS,BATCH_SIZE}`; `ENABLED` vẫn mặc định `false` ở compose gốc. Overlay prod: `ENABLED=${...:-true}`, `PROVIDER=${...:-local}`. `.env.prod.example` có mục reranker. `docs/production.md`: model L12 phải có sẵn trong `backend/models/fastembed` trước deploy; RAM ~0,3-0,4 GB mỗi worker so với `mem_limit` 3g, `API_WORKERS=2`.
- **#10 mirror:** `RAG_IMAGES_CATALOG` mặc định `data/delivery/final/clean/images.csv` ở `docker-compose.yml` và `.env.example` (khớp thay đổi của agent D2 trong `core/config.py`; cần kiểm khi merge).

## Quyết định

- Reranker bật bằng default trong overlay (`:-true`) chứ không đặt cứng, để `.env` tắt được khi api gần chạm trần RAM.
- ACL ưu tiên hơn chgrp vì user deploy không root thường không thuộc nhóm 10001.
- Quyền "other" đã đặt bởi bản deploy cũ không tự gỡ; `docs/production.md` ghi lệnh thu lại một lần.

## Kiểm tra

- `bash -n scripts/deploy.sh scripts/restore.sh`: đạt.
- Harness docker giả (ngoài repo, không commit) chạy `restore.sh pg`: thành công (CREATE_TMP, RESTORE, VERIFY, STOP, 2 lần RENAME, UP); `pg_restore` lỗi và kiểm tra lỗi: thoát 1, không STOP, không RENAME; đổi tên lần 2 lỗi: đưa DB cũ về và UP.
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod.example --profile app config --quiet`: đạt; `config` cho thấy RERANKER ENABLED true / PROVIDER local và catalog mới.
- Backend: `ruff check` đạt, `ruff format --check` 284 file đạt, `pytest tests/unit` 953 passed, 20 skipped.

## Chưa kiểm chứng

- Chưa chạy trên PostgreSQL thật: các câu SQL (`DROP DATABASE ... WITH (FORCE)`, DO block kiểm bảng, `pg_terminate_backend` + `ALTER DATABASE RENAME`, biến psql `:"x"`) chỉ qua `bash -n` và harness giả. Cần một lần thử restore trên VPS/staging theo mục 6 trước khi tin.
- `setfacl`/`chgrp` chưa chạy trên Linux thật (máy soạn là Windows).
- Mặc định bot dev ở `bot/src/config.ts` còn literal 18000 (thuộc agent B), test_ports chưa kiểm file đó.
