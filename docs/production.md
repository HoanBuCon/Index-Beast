# Production trên VPS

Chạy IndexBeast thật tại **https://tarnished.liemdai.io.vn** trên **1 VPS Ubuntu 24.04, 4 vCPU, 8 GB RAM** (thẻ Sprint 5: 5.1, 5.2, 5.3). Dùng lại phần lớn công việc staging ([`staging.md`](staging.md)): cùng compose gốc, cùng script cài VPS, cùng ngân sách tài nguyên.

> Trạng thái: toàn bộ file bên dưới đã kiểm cú pháp (`bash -n`, `docker compose config`) nhưng **chưa chạy trên VPS thật** và **Caddyfile.prod chưa qua `caddy validate`** (máy soạn không có Docker daemon). Lần deploy đầu tiên phải đi theo từng bước ở mục 3 và 4, và điền kết quả vào handover.

## 1. Kiến trúc và file

```text
Internet ──443/80──▶ Caddy (HTTPS tự động, header bảo mật)      infra/Caddyfile.prod
                       ├─ /api/*  ──▶ api (FastAPI + RAG, 3 GB)  ──▶ PostgreSQL · Qdrant · Redis · DeepSeek/Tavily
                       └─ còn lại ──▶ file tĩnh của web
bot Discord ─────────────────────────▶ api (mạng Docker, X-Service-Token)
```

| File | Việc |
|---|---|
| `docker-compose.prod.yml` | overlay chồng lên `docker-compose.yml`: `ENVIRONMENT=prod`, RAG thật, lưu hội thoại vào PostgreSQL, không công khai cổng DB, healthcheck, giới hạn CPU/RAM |
| `infra/Caddyfile.prod` | tên miền từ `DOMAIN`, HTTP→HTTPS, HSTS/CSP/..., SSE không đệm, chặn `/api/docs`, `/api/v1/dev/*` |
| `infra/caddy/snippets.caddy` | đoạn proxy `/api` và web tĩnh dùng chung cho ba Caddyfile (COPY vào image Caddy) |
| `.env.prod.example` | mẫu `.env` (không có giá trị thật) |
| `scripts/deploy.sh` | deploy và rollback |
| `scripts/backup.sh`, `scripts/restore.sh` | backup cho cron và khôi phục |
| `scripts/qdrant_snapshot.py` | chạy trong container api để chụp/tải/nạp snapshot Qdrant (image qdrant không có curl, cổng Qdrant không công khai) |

**Cổng công khai: chỉ 22 (SSH, chỉ khóa), 80, 443.** Overlay còn bỏ cả cổng `127.0.0.1` của PostgreSQL/Qdrant/Redis mà compose gốc mở cho dev; vào DB bằng `docker compose ... exec`. Docker bỏ qua `ufw` với cổng nó công khai, nên tuyệt đối không thêm `ports` công khai vào overlay.

Quyết định đáng biết:

- `ENVIRONMENT`, `CHAT_MODE`, `CHAT_PERSISTENCE`, `CHAT_AGENT_ENABLED` đặt **cứng** trong overlay; `WEB_URL`, `CORS_ORIGINS`, `AUTH_REDIRECT_URI` **suy ra từ `DOMAIN`**. Đặt chúng ở `.env` không có tác dụng, nên một `.env` sao từ máy dev không làm production chạy mock hay `dev`.
- Log container ghi bằng driver `local` (xoay vòng 5×20 MB) để còn xem được khi sự cố. API không ghi access log và Caddy không ghi access log mặc định, nên IP người dùng không lưu lại. Muốn tắt hẳn: `DOCKER_LOG_DRIVER=none`.
- uvicorn chạy với `--forwarded-allow-ips "*"` (trong `backend/Dockerfile`): chấp nhận được vì api không công khai cổng, chỉ Caddy trong mạng Docker chạm tới nó, và Caddy ghi đè `X-Forwarded-For`. Nếu sau này có thêm service khác trong mạng, đổi `*` thành IP của Caddy.
- `no-new-privileges` + `cap_drop: [ALL]` cho api, bot, Caddy (Caddy thêm lại `NET_BIND_SERVICE`). PostgreSQL/Qdrant/Redis **không** bỏ capability vì entrypoint của image cần `chown`/hạ quyền; chưa thử nên không liều.
- Caddy chặn ở lớp proxy `/api/v1/dev/*`, `/api/docs`, `/api/redoc`, `/api/openapi.json` (404), phòng khi backend lỡ chạy chế độ dev. Giới hạn thân yêu cầu: 64 KB cho `/api/*` (lớn nhất là `/chat`, tin nhắn ≤ 2.000 ký tự), 512 KB cho `/api/v1/answer-shares` (câu trả lời tới 100.000 ký tự).
- Bot không có healthcheck (không mở cổng, một kiểm tra giả sẽ luôn "healthy"): sức khỏe bot = `docker compose ... logs bot` + trạng thái online trên Discord; `restart: unless-stopped` chỉ lo trường hợp tiến trình thoát.

## 2. Ngân sách tài nguyên

Như staging: api 3 GB / 2,5 CPU, Qdrant 1 GB / 1,5, PostgreSQL 1 GB / 1,0, Redis 192 MB / 0,5, bot 192 MB / 0,5, Caddy 64 MB / 0,5. Tổng giới hạn RAM ≈ 5,4 GB, chừa ~2,6 GB cho hệ điều hành. Số liệu đo thật ở [`staging.md`](staging.md) mục 7; nếu OOM giảm `API_WORKERS=1` trước.

## 3. Chuẩn bị một lần

### 3.1 DNS

Tạo bản ghi **A** `tarnished.liemdai.io.vn` → IPv4 của VPS (thêm **AAAA** chỉ khi VPS thật sự có IPv6 và đã mở 80/443 cho nó). Kiểm tra từ máy bạn:

```bash
dig +short tarnished.liemdai.io.vn      # phải ra IP của VPS
```

Caddy xin chứng chỉ Let's Encrypt qua cổng 80; DNS chưa trỏ đúng thì lần đầu sẽ thất bại và Caddy thử lại, đừng deploy nhiều lần liên tiếp để khỏi chạm giới hạn của Let's Encrypt.

### 3.2 Cài VPS

Dùng lại script staging (Docker, user `deploy`, ufw chỉ mở 22/80/443, SSH chỉ khóa, swap 2 GB). Làm đúng như [`staging.md`](staging.md) mục 3:

```bash
# Máy bạn
ssh-keygen -t ed25519 -f ~/.ssh/indexbeast-prod -C "prod-deploy"
scp ~/.ssh/indexbeast-prod.pub root@<ip-vps>:/root/deploy.pub
# VPS, root
git clone https://github.com/HoanBuCon/Index-Beast.git /tmp/ib && bash /tmp/ib/scripts/staging/bootstrap.sh /root/deploy.pub
```

Trước khi đóng phiên root, mở cửa sổ khác kiểm `ssh -i ~/.ssh/indexbeast-prod deploy@<ip-vps>` vào được. Docker Compose phải **≥ 2.24** (`docker compose version`); bản `docker-compose-plugin` của kho Docker chính thức đủ mới.

### 3.3 Discord OAuth

Ở [Discord Developer Portal](https://discord.com/developers/applications) → ứng dụng của bạn → **OAuth2 → Redirects**, thêm đúng một URL:

```text
https://tarnished.liemdai.io.vn/api/v1/auth/discord/callback
```

Lấy `Client ID` và `Client Secret` điền vào `.env`. URL phải **khớp từng ký tự** với `AUTH_REDIRECT_URI` (overlay suy ra từ `DOMAIN`); khác một ký tự là đăng nhập báo `invalid redirect_uri`. Bot muốn có trên server cộng đồng thì thêm `DISCORD_TOKEN`, `DISCORD_GUILD_ID` (để trống `DISCORD_TOKEN` thì deploy bỏ qua bot).

### 3.4 Cấu hình `.env`

Đăng nhập bằng `deploy`:

```bash
git clone https://github.com/HoanBuCon/Index-Beast.git ~/Index-Beast && cd ~/Index-Beast
git checkout main
cp .env.prod.example .env && chmod 600 .env
openssl rand -hex 32     # chạy nhiều lần: POSTGRES_PASSWORD, API_SERVICE_TOKEN, ADMIN_TOKEN, AUTH_SECRET (mỗi biến một giá trị)
nano .env
```

Điền mọi dòng `change-me`, `AUTH_ADMIN_DISCORD_IDS` (Discord ID số của quản trị viên: Discord → Cài đặt → Nâng cao → Chế độ nhà phát triển, rồi chuột phải tên mình → Sao chép ID), `DEEPSEEK_API_KEY`. `.env` **phải `chmod 600`**: deploy từ chối chạy nếu quyền rộng hơn. Đừng dán `.env` hay secret vào chat, issue, log. `AUTH_SECRET` không đổi sau khi đã có người dùng; `POSTGRES_PASSWORD` chỉ có tác dụng ở lần tạo volume đầu.

## 4. Deploy lần đầu

### 4.1 Dữ liệu (model, corpus, Qdrant)

Làm như [`staging.md`](staging.md) mục 4, thay `docker-compose.staging.yml` bằng `docker-compose.prod.yml`, và **vì cổng Qdrant không còn trên localhost của VPS** nên nạp snapshot bằng script:

```bash
# Máy dev: model E5 (~465 MB)
rsync -a backend/models/ deploy@<ip-vps>:~/Index-Beast/backend/models/
```

Chạy deploy lần đầu để có schema và Qdrant (api sẽ chưa có dữ liệu, trả lời rỗng cho tới khi nạp xong):

```bash
cd ~/Index-Beast && scripts/deploy.sh
```

Sau đó nạp corpus và vector. Trên máy dev (thư mục gốc repo) tạo `corpus.dump` và tải snapshot `lore.snapshot` như staging.md mục 4, `scp` lên `~/` của VPS và đặt snapshot đúng định dạng tên để `restore.sh` nhận (collection là tên `RAG_COLLECTION`, mặc định `lore_chunks`):

```bash
# Trên VPS
cd ~/Index-Beast
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app"
$COMPOSE exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --exit-on-error' < ~/corpus.dump
mkdir -p ~/indexbeast-backups && chmod 700 ~/indexbeast-backups
mv ~/lore.snapshot ~/indexbeast-backups/qdrant-lore_chunks-20261122-000000.snapshot
scripts/restore.sh qdrant ~/indexbeast-backups/qdrant-lore_chunks-20261122-000000.snapshot
$COMPOSE run --rm api python -m scripts.memory_admin setup --apply   # collection bộ nhớ hội thoại
```

Ảnh minh họa (~7,5 GB) không chép mặc định (`RAG_IMAGES_ENABLED=false`); bật theo staging.md khi cần. Hội thoại của máy dev **không** chép lên production.

### 4.2 Kiểm tra sau deploy

```bash
curl -fsS https://tarnished.liemdai.io.vn/api/v1/health
curl -sI https://tarnished.liemdai.io.vn/ | grep -iE 'strict-transport|content-security|x-frame|x-content|^server'   # Server không được xuất hiện
curl -sI http://tarnished.liemdai.io.vn/ | head -3          # chuyển hướng 308 sang https
curl -s -o /dev/null -w '%{http_code}\n' https://tarnished.liemdai.io.vn/api/docs        # 404
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://tarnished.liemdai.io.vn/api/v1/dev/llm/test   # 404
```

Rồi mở trình duyệt: đăng nhập Discord, hỏi một câu (kiểm streaming chữ chạy dần, tức SSE không bị đệm), mở DevTools → Console xem có lỗi CSP không. Có lỗi CSP thì ghi lại domain bị chặn và nới đúng directive đó trong `infra/Caddyfile.prod`, đừng bỏ CSP.

Ba kiểm tra bắt buộc cho lần đầu (CSP và `caddy validate` chưa chạy trên máy soạn): (1) `docker run --rm -v "$PWD/infra/Caddyfile.prod:/etc/caddy/Caddyfile:ro" caddy:2.11.7-alpine caddy validate --config /etc/caddy/Caddyfile`; (2) đăng nhập OAuth thành công và cookie phiên có cờ `Secure`, `HttpOnly`; (3) `docker compose ... ps` mọi container `healthy`.

## 5. Deploy và rollback

```bash
cd ~/Index-Beast
scripts/deploy.sh               # git pull --ff-only trên nhánh hiện tại (main), build, up, chờ api healthy
scripts/deploy.sh v1.0.1        # checkout tag/commit/nhánh rồi deploy
```

Script từ chối chạy nếu working tree có thay đổi chưa commit, `.env` quyền ≠ 600, còn `change-me` hay thiếu biến bắt buộc. Có PostgreSQL đang chạy thì nó **backup trước** (`SKIP_PRE_BACKUP=1` để bỏ qua). Migration chạy tự động khi api khởi động (`alembic upgrade head` trong CMD của `backend/Dockerfile`); migration lỗi thì api không lên và lỗi hiện trong `docker compose logs api`.

**Rollback mã:** `scripts/deploy.sh <tag-hoặc-commit-cũ>` (script in sẵn commit trước đó khi kết thúc). Chỉ rollback về **tag production đầu tiên hoặc mới hơn** (bản cũ hơn không có `docker-compose.prod.yml` và `infra/Caddyfile.prod`; script tự quay về bản đang chạy và báo lỗi). Sau rollback VPS ở HEAD tách rời; quay lại bình thường bằng `scripts/deploy.sh main`.

**Rollback có migration:** chạy lại bản cũ KHÔNG hoàn tác schema. Nếu bản mới có migration không tương thích bản cũ, hoặc dữ liệu hỏng:

1. `scripts/deploy.sh <tag-cũ>` để chạy mã cũ (nếu schema mới vẫn tương thích, dừng ở đây).
2. Nếu không tương thích: `scripts/restore.sh pg ~/indexbeast-backups/pg-<bản-trước-deploy>.dump` (bản backup tự động trước deploy). Mất hội thoại sau thời điểm đó.
3. Hoặc hạ schema đúng một bước với `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app run --rm api alembic downgrade -1` (chỉ khi migration có `downgrade` và đã đọc nó).

Tag phát hành là việc của TV1 (`git tag -a v1.0.0 -m ... && git push origin v1.0.0` trên máy dev); VPS chỉ checkout.

## 6. Backup và khôi phục

Backup nằm ở `$HOME/indexbeast-backups` (đổi bằng `BACKUP_DIR`, phải ngoài repo), quyền 700, không chứa `.env`. Bản dump PostgreSQL chứa **hội thoại và dữ liệu người dùng**: coi như dữ liệu nhạy cảm, đừng đưa vào repo hay chat; nếu chép sang nơi khác (máy khác, kho lưu trữ) thì mã hóa.

Crontab của user `deploy` (`crontab -e`; giờ theo múi giờ VPS, chọn giờ thấp điểm):

```cron
# PostgreSQL mỗi ngày 03:15, giữ 7 bản
15 3 * * *  /home/deploy/Index-Beast/scripts/backup.sh daily  >> /home/deploy/indexbeast-backups/backup.log 2>&1
# Snapshot Qdrant mỗi Chủ nhật 04:00, giữ 4 bản
0  4 * * 0  /home/deploy/Index-Beast/scripts/backup.sh weekly >> /home/deploy/indexbeast-backups/backup.log 2>&1
```

Tạo thư mục `~/indexbeast-backups` trước (`mkdir -p` rồi `chmod 700`), nếu không cron không ghi được `backup.log`. Script kiểm bản dump đọc lại được (`pg_restore --list`) trước khi xoay vòng, nên một lần dump hỏng không xóa mất bản tốt. Backup chỉ nằm trên VPS: nên chép định kỳ ra ngoài (`rsync`/snapshot đĩa của nhà cung cấp VPS), vì mất VPS là mất cả hai.

**Khôi phục:**

```bash
scripts/restore.sh list
scripts/restore.sh pg ~/indexbeast-backups/pg-20261122-031500.dump          # dừng api/bot, DROP SCHEMA public, pg_restore, bật lại (bot chỉ bật nếu có DISCORD_TOKEN)
scripts/restore.sh qdrant ~/indexbeast-backups/qdrant-lore_chunks-20261122-040000.snapshot
```

Cả hai hỏi xác nhận (gõ `restore`) và chỉ nhận file nằm trong `BACKUP_DIR`.

Khôi phục PostgreSQL xóa hẳn schema `public` (`DROP SCHEMA public CASCADE`) rồi nạp lại, không dùng `pg_restore --clean`: `--clean` chỉ xóa bảng có trong bản dump nên bảng do migration mới hơn sẽ còn sót, và `alembic upgrade head` của api sẽ lỗi "relation already exists" rồi restart liên tục. Sau khôi phục api chạy lại migration để đưa schema về khớp mã hiện tại.

**Thử khôi phục một lần (thẻ 5.3, bắt buộc trước khi tin backup):** sau khi chạy `backup.sh all` lần đầu, (1) ghi số dòng bảng chính: `docker compose ... exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) from chunks"'`; (2) `scripts/restore.sh pg <dump mới nhất>`; (3) đếm lại, phải bằng; (4) hỏi một câu RAG qua web để chắc api đọc được. Làm trước khi mở cho người dùng thật, hoặc trên một VPS tạm. Với Qdrant: `restore.sh qdrant` bản mới nhất rồi hỏi một câu RAG. Ghi ngày và kết quả vào handover.

## 7. Giám sát

- **Healthcheck và tự khởi động lại:** mọi container có `restart: unless-stopped` và healthcheck (xem `docker compose ... ps`). Docker **không** tự khởi động lại container `unhealthy`, chỉ container thoát; thấy `unhealthy` thì xem log rồi `docker compose ... restart <service>`.
- **Ping ngoài (miễn phí, khuyến nghị):** dùng UptimeRobot hoặc Better Stack (gói free) ping `https://tarnished.liemdai.io.vn/api/v1/health` mỗi 5 phút, báo về Discord qua webhook của kênh `#ops` (tạo trong Cài đặt kênh → Tích hợp). Chỉ ping URL công khai này, đừng đưa token vào. Lưu ý đây là dịch vụ bên thứ ba biết tên miền của bạn.
- **Log:** `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app logs --tail 100 api`. Disk: `df -h`, `docker system df` mỗi tuần; dọn ảnh cũ bằng `docker image prune -f` (an toàn, không đụng volume).
- **Hết hạn chứng chỉ:** Caddy tự gia hạn; theo dõi bằng ping ngoài (chứng chỉ hỏng thì ping HTTPS lỗi).
- Chưa làm: fail2ban, cập nhật bảo mật tự động (`unattended-upgrades`), GitHub Actions gọi `deploy.sh` qua SSH (mục tùy chọn của thẻ 5.2; cần khóa SSH deploy nằm trong GitHub Secrets nên chưa làm).

## 8. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Trình duyệt báo chứng chỉ sai / không vào được | DNS chưa trỏ, cổng 80 bị chặn, Let's Encrypt giới hạn | `dig`, `ufw status`, `docker compose ... logs caddy`; đợi, đừng deploy dồn dập |
| `deploy.sh`: ".env đang có quyền ..." | quyền file | `chmod 600 .env` |
| `deploy.sh`: "Working tree có thay đổi" | sửa tay trên VPS | `git status`; hoàn tác (`git restore <file>`) hoặc commit từ máy dev. Không sửa tay trên VPS |
| api không lên, log có `change-me` | `ENVIRONMENT=prod` từ chối giá trị mẫu | điền biến đã nêu trong log (chỉ in tên biến) |
| api restart liên tục, log alembic lỗi | migration lỗi hoặc PostgreSQL chưa sẵn sàng | đọc log; mã cũ chạy tiếp được: `deploy.sh <tag-cũ>` |
| api bị OOM (`docker inspect` → `OOMKilled`) | encoder + model vượt 3 GB | `API_WORKERS=1` trong `.env`, deploy lại |
| Đăng nhập Discord báo `invalid redirect_uri` | URL trong Portal khác `AUTH_REDIRECT_URI` | sửa Portal theo mục 3.3 |
| Đăng nhập xong vẫn như chưa đăng nhập | cookie không `Secure`, hoặc truy cập qua `http://` | luôn dùng https; xem `AUTH_COOKIE_SECURE` (overlay đặt true) |
| Chữ trả lời hiện một lần thay vì chạy dần | Cloudflare/proxy trung gian đệm SSE | tắt proxy (đám mây xám) hoặc tắt buffering cho `/api/*` |
| Console trình duyệt báo `Refused to ...` (CSP) | nguồn ngoài chưa được cho phép | xem directive trong `infra/Caddyfile.prod`; nới tối thiểu |
| `restore.sh`: "File phải nằm trong ..." | file ngoài `BACKUP_DIR` | `mv` file vào `BACKUP_DIR` (hoặc đặt `BACKUP_DIR`) |
| Hết dung lượng đĩa | log, ảnh Docker cũ, backup | `docker system df`, `docker image prune -f`, giảm `KEEP_DAILY` |
