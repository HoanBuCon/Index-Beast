# Sprint 5 · TV1 · Deploy production, script deploy, backup

| | |
|---|---|
| Thẻ | 5.1 Deploy production + HTTPS, 5.2 Script deploy đơn giản, 5.3 Backup & monitoring |
| Ngày | 16/11/2026 |
| Nhánh | `feature/s5-tv1-production-deploy` (từ `origin/develop`) |
| Hướng dẫn vận hành | [`docs/production.md`](../production.md) |

## 1. Đã làm

- `docker-compose.prod.yml`: overlay cho 1 VPS 4 vCPU/8 GB, tên miền `tarnished.liemdai.io.vn`. `ENVIRONMENT=prod`, `CHAT_MODE=rag`, `CHAT_PERSISTENCE=postgres`, `CHAT_AGENT_ENABLED=true` đặt cứng; `WEB_URL`, `CORS_ORIGINS`, `AUTH_REDIRECT_URI` suy ra từ `DOMAIN`; cookie `Secure`; bỏ cổng `127.0.0.1` của PostgreSQL/Qdrant/Redis (`ports: !reset []`), chỉ Caddy công khai 80/443; healthcheck cho mọi container (bot chỉ kiểm tiến trình sống, Caddy hỏi admin API nội bộ); giới hạn CPU, log driver `local` xoay vòng.
- `infra/Caddyfile.prod`: `DOMAIN` từ env (mặc định `tarnished.liemdai.io.vn`), HTTPS và chuyển HTTP→HTTPS tự động, không basic auth, `-Server`, HSTS (1 năm, không preload), `nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY` + `frame-ancestors 'none'`, `Permissions-Policy`, CSP viết theo bản build Vite (không script nội tuyến, không font/CDN ngoài; `style 'unsafe-inline'` vì React; `img-src https:` cho ảnh wiki), SSE `flush_interval -1`, cache vô hạn cho `/assets/*`, `no-cache` cho HTML.
- `.env.prod.example` (toàn placeholder, kèm URL callback Discord, `AUTH_ADMIN_DISCORD_IDS`, `DOMAIN`, ghi chú `chmod 600`) và `!.env.prod.example` trong `.gitignore`.
- `backend/Dockerfile`: CMD chạy `alembic upgrade head && exec uvicorn ...` (trước đó thiếu, staging phải chạy tay). Lệnh `docker compose run --rm api <lệnh>` ghi đè CMD nên không đổi hành vi.
- `scripts/deploy.sh` (thay stub): từ chối khi `.env` thiếu/quyền ≠ 600/còn `change-me`/thiếu biến bắt buộc, từ chối khi working tree bẩn, `git pull --ff-only` hoặc checkout tag/ref (rollback), backup trước khi đổi nếu PostgreSQL đang chạy, `up -d --build`, chờ api healthy, kiểm tra HTTPS, in lệnh rollback và lưu ý migration.
- `scripts/backup.sh` (thay stub): `daily` = `pg_dump -Fc` giữ 7 bản (kiểm `pg_restore --list` trước khi xoay vòng), `weekly` = snapshot Qdrant của collection api đang dùng giữ 4 bản, ghi vào `$HOME/indexbeast-backups` (cấu hình `BACKUP_DIR`, từ chối đường dẫn trong repo), quyền 700, không đọc hay in secret.
- `scripts/restore.sh` (mới) và `scripts/qdrant_snapshot.py` (mới, chạy trong container api vì Qdrant không công khai cổng và không có curl).
- `docs/production.md`: DNS, cài VPS (dùng lại `scripts/staging/bootstrap.sh`), Discord OAuth, `.env`, deploy lần đầu và nạp dữ liệu, deploy/rollback, crontab, khôi phục và cách thử khôi phục, giám sát, xử lý sự cố.

## 2. Quyết định

- **Overlay, không sửa `docker-compose.yml`/`.env.example`/khối RAG_*.** Không đụng `config.py`, `factory.py`, `chat.py`, `rag/*`.
- **Hardcode các biến an toàn** thay vì `${VAR:-default}` như staging: `.env` sao từ máy dev không thể đưa production về mock/dev.
- **Log driver `local`** thay vì `none` mặc định của repo: không có log thì không điều tra được sự cố; API đã tắt access log nên không lưu IP. Tắt được bằng `DOCKER_LOG_DRIVER=none`.
- **Snapshot Qdrant qua API từ container api**, không giả định đường dẫn lưu snapshot bên trong container qdrant (đường dẫn mặc định có thể nằm ngoài volume).
- **Caddy tách `Caddyfile.prod`** (giống staging) và mount đè lên file đã nằm trong image, nên không phải build lại image Caddy khi chỉnh cấu hình, nhưng web tĩnh vẫn nằm trong image (cần `--build`, deploy.sh đã có).
- Không làm: Kubernetes, registry, Terraform, GitHub Actions deploy (mục tùy chọn của thẻ 5.2).

## 3. Các mục từ rà soát bảo mật `develop` (đã gộp vào nhánh)

| Mục | Trạng thái |
|---|---|
| H1: production không chạy `ENVIRONMENT=dev` | Xong: `ENVIRONMENT: prod` đặt cứng trong overlay (kiểm bằng `docker compose config`: `ENVIRONMENT: prod`). Thêm lớp Caddy trả 404 cho `/api/v1/dev`, `/api/v1/dev/*`, `/api/docs*`, `/api/redoc*`, `/api/openapi.json`. Chưa kiểm bằng request thật |
| M1: giới hạn thân yêu cầu | Xong, 64 KB cho `/api/*` (lớn nhất là `/chat`: tin nhắn ≤ 2.000 ký tự ≈ 6 KB UTF-8). **Ngoại lệ 512 KB cho `/api/v1/answer-shares`**: schema cho phép câu trả lời tới 100.000 ký tự và 100 nguồn (~400 KB xấu nhất); 64 KB sẽ làm hỏng chia sẻ câu trả lời dài. Chưa thử `413` thật |
| M4: header bảo mật | Xong: HSTS, nosniff, X-Frame-Options, `frame-ancestors`, Referrer-Policy, Permissions-Policy, CSP. **CSP chưa thử trên trình duyệt với bản build thật**; dự kiến có thể phải nới sau lần chạy đầu |
| Low: `no-new-privileges`, `cap_drop` | Xong cho api, bot, Caddy (`cap_drop: ALL`, Caddy thêm `NET_BIND_SERVICE`). **Không áp dụng** cho PostgreSQL/Qdrant/Redis (entrypoint cần chown và hạ quyền, chưa thử, đã ghi trong overlay). Chưa chạy container thật để xác nhận Caddy/api/bot khởi động được với `cap_drop: ALL` |
| `--forwarded-allow-ips "*"` | Giữ nguyên (`backend/Dockerfile`, file thuộc nhánh này); đã ghi lý do và điều kiện đổi vào `docs/production.md` mục 1 |

## 4. Kiểm tra đã chạy

| Kiểm tra | Kết quả |
|---|---|
| `bash -n` trên `deploy.sh`, `backup.sh`, `restore.sh` | đạt (cả ba) |
| `python -I -m py_compile scripts/qdrant_snapshot.py` | đạt |
| `qdrant_snapshot.py` với máy chủ HTTP giả (create, list, download, upload multipart đúng `Content-Length`, từ chối tên collection có `/`) | đạt; **không phải Qdrant thật** |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod.example --profile app config --quiet` | đạt (Compose v2.39.4); cấu hình đã render chỉ có `ports` của Caddy (80, 443), `WEB_URL`/`CORS_ORIGINS`/`AUTH_REDIRECT_URI` đúng tên miền, `CHAT_MODE: rag`, `ENVIRONMENT: prod` |
| Tách tên collection từ tên file snapshot trong `restore.sh` (`qdrant-lore_chunks-...`, `qdrant-indexbeast_s4_wiki_ca98c06b-...`) | đạt |
| `git diff --check` | xem lệnh cuối trong commit; không có lỗi khoảng trắng |
| `shellcheck` | **không chạy**: máy soạn không có |
| `caddy validate infra/Caddyfile.prod` | **không chạy được**: Docker Desktop không chạy (daemon không kết nối) trên máy soạn. Cú pháp đã đối chiếu thủ công với `Caddyfile.staging`; phải chạy lệnh ở `docs/production.md` mục 4.2 trước lần deploy đầu |

## 5. Chưa kiểm chứng

- **Chưa chạy trên VPS thật**: không build image, không khởi động stack, không xin chứng chỉ Let's Encrypt, không thử đăng nhập Discord, không chạy backup/restore thật (mới thử logic với máy chủ giả). **Chưa thử khôi phục từ backup** (mục cuối của thẻ 5.3): làm theo `docs/production.md` mục 6 và ghi kết quả.
- Chưa xác nhận Compose trên VPS ≥ 2.24 (cần cho `!reset`).
- `wget` có trong `caddy:2.11.7-alpine` (busybox) cho healthcheck Caddy và admin API ở `127.0.0.1:2019`: suy luận, chưa chạy.
- Chưa có bản chạy thật của migration trên DB rỗng qua CMD mới của api; thời gian chạy migration lần đầu có thể vượt `start_period` 60 s của healthcheck api (deploy.sh chờ tối đa 300 s).
- GitHub Actions gọi `deploy.sh` qua SSH (tùy chọn thẻ 5.2): không làm.

## 6. Câu hỏi cho TV1

1. Bot production dùng guild cụ thể (`DISCORD_GUILD_ID`) hay đăng ký global? Hiện để trống `DISCORD_TOKEN` thì bỏ qua bot.
2. Collection Qdrant cho release là `lore_chunks` hay `indexbeast_s4_wiki_ca98c06b` (handover S4 nói chưa chốt)? `backup.sh` chụp theo `RAG_COLLECTION` của api; nếu đổi thì đặt `RAG_COLLECTION` trong `.env` (đã comment sẵn trong mẫu).
3. Có chép ảnh minh họa (~7,5 GB) lên production không? Hiện tắt (`RAG_IMAGES_ENABLED=false`).
4. Có cần sao lưu ra ngoài VPS (rsync/snapshot đĩa của nhà cung cấp)? Backup hiện chỉ nằm trên chính VPS.
5. Chọn dịch vụ ping ngoài (UptimeRobot/Better Stack) và kênh Discord nhận cảnh báo.
