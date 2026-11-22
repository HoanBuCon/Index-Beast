# Production trên VPS

Chạy IndexBeast thật tại **https://tarnished.liemdai.io.vn** trên **1 VPS Ubuntu 24.04, 4 vCPU, 8 GB RAM** (thẻ Sprint 5: 5.1, 5.2, 5.3). Dùng lại phần lớn công việc staging ([`staging.md`](staging.md)): cùng compose gốc, cùng script cài VPS, cùng ngân sách tài nguyên.

> Trạng thái: **đã deploy lần đầu ngày 22/11/2026** (VPS Viettel IDC 4 vCPU / 8 GB, Ubuntu 24.04.3, `main` 825437f): `caddy validate` đạt, chứng chỉ Let's Encrypt, header và chặn đường dẫn đạt, corpus nạp đủ. Kết quả và các bước thật đã làm: [handover deploy](handover/2026-11-22_s5-tv1_deploy-production.md). Chưa chạy trên VPS thật: `restore.sh`, cron backup.
>
> Production dùng reranker **API Jina** (`RAG_RERANKER_PROVIDER=jina`, cần `JINA_API_KEY`) thay model L12 cục bộ, nên không cần chép model L12. `RAG_COLLECTION=indexbeast_s4_wiki_ca98c06b`.

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

- **Cổng nội bộ 18000 của api là hợp đồng cố định, không phải biến cấu hình.** Nó nằm ở bốn nơi phải cùng giá trị: `backend/Dockerfile` (`--port`, `EXPOSE`), `infra/caddy/snippets.caddy` (`reverse_proxy api:18000`), healthcheck và `BOT_API_URL` trong `docker-compose.yml` (mỗi nơi có comment trỏ về đây). `backend/tests/unit/test_ports.py` kiểm chúng khớp nhau. Đổi cổng = sửa cả bốn nơi trong cùng một commit, không thêm biến môi trường (sai lệch giữa các nơi chỉ lộ ra khi deploy). `API_PORT` trong `.env` chỉ dành cho chạy api ngoài Docker.
- `ENVIRONMENT`, `CHAT_MODE`, `CHAT_PERSISTENCE` đặt **cứng** trong overlay (cờ `CHAT_AGENT_ENABLED` đã bị bỏ: `rag` luôn dùng Agent); `WEB_URL`, `CORS_ORIGINS`, `AUTH_REDIRECT_URI` **suy ra từ `DOMAIN`**. Đặt chúng ở `.env` không có tác dụng, nên một `.env` sao từ máy dev không làm production chạy mock hay `dev`.
- Log container ghi bằng driver `local` (xoay vòng 5×20 MB) để còn xem được khi sự cố. API không ghi access log và Caddy không ghi access log mặc định, nên IP người dùng không lưu lại. Muốn tắt hẳn: `DOCKER_LOG_DRIVER=none`.
- uvicorn chạy với `--forwarded-allow-ips "*"` (trong `backend/Dockerfile`): chấp nhận được vì api không công khai cổng, chỉ Caddy trong mạng Docker chạm tới nó, và Caddy ghi đè `X-Forwarded-For`. Nếu sau này có thêm service khác trong mạng, đổi `*` thành IP của Caddy.
- `no-new-privileges` + `cap_drop: [ALL]` cho api, bot, Caddy (Caddy thêm lại `NET_BIND_SERVICE`). PostgreSQL/Qdrant/Redis **không** bỏ capability vì entrypoint của image cần `chown`/hạ quyền; chưa thử nên không liều.
- Caddy chặn ở lớp proxy `/api/v1/dev/*`, `/api/docs`, `/api/redoc`, `/api/openapi.json` (404), phòng khi backend lỡ chạy chế độ dev. Giới hạn thân yêu cầu: 64 KB cho `/api/*` (lớn nhất là `/chat`, tin nhắn ≤ 2.000 ký tự), 512 KB cho `/api/v1/answer-shares` (câu trả lời tới 100.000 ký tự).
- Bot không có healthcheck (không mở cổng, một kiểm tra giả sẽ luôn "healthy"): sức khỏe bot = `docker compose ... logs bot` + trạng thái online trên Discord; `restart: unless-stopped` chỉ lo trường hợp tiến trình thoát.

## 2. Ngân sách tài nguyên

Như staging: api 3 GB / 2,5 CPU, Qdrant 1 GB / 1,5, PostgreSQL 1 GB / 1,0, Redis 192 MB / 0,5, bot 192 MB / 0,5, Caddy 256 MB / 0,5 (overlay prod nâng từ 64 MB sau sự cố dội request 22/11/2026). Tổng giới hạn RAM ≈ 5,6 GB, chừa ~2,4 GB cho hệ điều hành. Số liệu đo thật ở [`staging.md`](staging.md) mục 7; nếu OOM giảm `API_WORKERS=1` trước.

**Reranker chạy trong api (Hybrid + MiniLM-L12 ONNX, mặc định của overlay prod):** mỗi worker uvicorn nạp một bản model riêng, tốn thêm **~0,3-0,4 GB RAM mỗi worker** (đo process đầy đủ ở handover TV3: ~1,27 GB so với ~0,9 GB khi chỉ RRF). Với `API_WORKERS=2`, thêm ~0,6-0,8 GB vào trần `mem_limit: 3g` của api: còn dư nhưng không rộng, theo dõi `docker stats` sau deploy đầu và giảm `API_WORKERS=1` hoặc đặt `RAG_RERANKER_ENABLED=false` nếu api gần chạm trần. Model **phải có sẵn trong `backend/models/fastembed` (cache FastEmbed) trước khi deploy**: container chỉ đọc thư mục này nên không tự tải được; thiếu model thì reranker lỗi nạp và giữ thứ tự RRF (câu trả lời vẫn chạy, chất lượng tìm giảm; xem log `jina_reranker_outcome`). Chuẩn bị trên máy dev: chạy một lần reranker (`eval/measure_retrieval.py --rerank`, hoặc nạp `Xenova/ms-marco-MiniLM-L-12-v2` qua FastEmbed với `RAG_MODELS_DIR=models/fastembed`) để cache có model (~120 MB), rồi `rsync` như mục 4.1.

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

`backend/models` phải chứa cả model encoder E5 lẫn model reranker L12 (mục 2). `deploy.sh` cấp quyền ĐỌC cho uid 10001 (user `app` của container api) trên `backend/data` và `backend/models` bằng ACL (`setfacl -R -m u:10001:rX`, cả ACL mặc định cho file mới), hoặc `chgrp -R 10001` + `g+rX` nếu máy không có `setfacl`; không mở quyền cho "other" nên dữ liệu không world-readable. Nên `sudo apt install acl` trên VPS. Quyền "other" có sẵn từ lần deploy cũ (bản trước dùng `chmod o+r`) không tự bị gỡ: thu lại một lần bằng `chmod -R o-rwx backend/data backend/models` sau khi ACL đã đặt.

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
scripts/restore.sh pg ~/indexbeast-backups/pg-20261122-031500.dump          # nạp DB tạm, kiểm tra, rồi dừng api/bot, đổi tên DB, bật lại (bot chỉ bật nếu có DISCORD_TOKEN)
scripts/restore.sh qdrant ~/indexbeast-backups/qdrant-lore_chunks-20261122-040000.snapshot
```

Cả hai hỏi xác nhận (gõ `restore`) và chỉ nhận file nằm trong `BACKUP_DIR`.

Khôi phục PostgreSQL **không đụng DB đang chạy cho tới khi bản khôi phục đã được kiểm chứng**:

1. Tạo lại DB tạm `${POSTGRES_DB}_restore` (xóa bản cũ cùng tên nếu có), `pg_restore --no-owner --exit-on-error` vào đó. Lúc này api/bot vẫn chạy.
2. Kiểm tra DB tạm: `pg_restore` thoát 0, có bảng `alembic_version` và các bảng lõi (`documents`, `chunks`, `conversations`, `messages`); in phiên bản alembic và số dòng từng bảng để đối chiếu với DB hiện tại.
3. Chỉ khi đạt: dừng api/bot, ngắt kết nối còn lại, `ALTER DATABASE` đổi `${POSTGRES_DB}` thành `${POSTGRES_DB}_prev_<thời-gian>` rồi `${POSTGRES_DB}_restore` thành `${POSTGRES_DB}`, bật lại api (bot nếu có `DISCORD_TOKEN`). Api chạy `alembic upgrade head` nên schema khớp mã hiện tại.

Lỗi ở bước 1-2 thì DB đang chạy nguyên vẹn và dịch vụ không dừng. Lỗi lúc đổi tên thì script tự đưa DB cũ về chỗ cũ và bật lại dịch vụ. Cách này cũng thay `DROP SCHEMA public` trước đây, và không dùng `pg_restore --clean` (chỉ xóa bảng có trong dump nên bảng của migration mới hơn còn sót, `alembic upgrade head` báo "relation already exists").

**Quay lại DB trước khi khôi phục** (script in sẵn lệnh): `docker compose ... stop api bot`, vào `psql -d postgres`, ngắt kết nối tới `${POSTGRES_DB}`, `ALTER DATABASE "<db>" RENAME TO "<db>_bad"; ALTER DATABASE "<db>_prev_<thời-gian>" RENAME TO "<db>";`, rồi `up -d api bot`. DB `_prev_` chiếm đĩa: sau khi yên tâm thì `DROP DATABASE "<db>_prev_<thời-gian>";`. Mỗi lần khôi phục thêm một DB `_prev_`, nhớ dọn. Cần dung lượng đĩa dư gấp đôi DB trong lúc khôi phục.

**Thử khôi phục một lần (thẻ 5.3, bắt buộc trước khi tin backup):** sau khi chạy `backup.sh all` lần đầu, (1) ghi số dòng bảng chính: `docker compose ... exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) from chunks"'`; (2) `scripts/restore.sh pg <dump mới nhất>`; (3) đếm lại, phải bằng; (4) hỏi một câu RAG qua web để chắc api đọc được. Làm trước khi mở cho người dùng thật, hoặc trên một VPS tạm. Với Qdrant: `restore.sh qdrant` bản mới nhất rồi hỏi một câu RAG. Ghi ngày và kết quả vào handover.

## 7. Giám sát

- **Healthcheck và tự khởi động lại:** mọi container có `restart: unless-stopped` và healthcheck (xem `docker compose ... ps`). Docker **không** tự khởi động lại container `unhealthy`, chỉ container thoát; thấy `unhealthy` thì xem log rồi `docker compose ... restart <service>`.
- **Ping ngoài (miễn phí, khuyến nghị):** dùng UptimeRobot hoặc Better Stack (gói free) ping `https://tarnished.liemdai.io.vn/api/v1/health` mỗi 5 phút, báo về Discord qua webhook của kênh `#ops` (tạo trong Cài đặt kênh → Tích hợp). Chỉ ping URL công khai này, đừng đưa token vào. Lưu ý đây là dịch vụ bên thứ ba biết tên miền của bạn.
- **Log:** `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app logs --tail 100 api`. Disk: `df -h`, `docker system df` mỗi tuần; dọn ảnh cũ bằng `docker image prune -f` (an toàn, không đụng volume).
- **Hết hạn chứng chỉ:** Caddy tự gia hạn; theo dõi bằng ping ngoài (chứng chỉ hỏng thì ping HTTPS lỗi).
- Chưa làm: fail2ban, cập nhật bảo mật tự động (`unattended-upgrades`), GitHub Actions gọi `deploy.sh` qua SSH (mục tùy chọn của thẻ 5.2; cần khóa SSH deploy nằm trong GitHub Secrets nên chưa làm).

## 7b. Chống DoS và dội request

Sự cố 22/11/2026: một IP dùng công cụ `fasthttp` gửi ~1.400 request/phút vào `/api/v1/answer-shares`, `/api/v1/images/<id giả>` và `/chat/stream` trong gần 2 giờ. Caddy chạm trần 64 MB, unhealthy, ngừng nhận 443. `ufw deny` không có tác dụng vì Docker mở cổng bằng iptables riêng.

Các lớp, từ ngoài vào:

| Lớp | Chặn gì | Ở đâu |
|---|---|---|
| Nhà mạng / CDN (Anti-DDoS Viettel IDC, Cloudflare) | Tấn công băng thông, nhiều IP | Chưa có. Cloudflare cần chuyển nameserver của cả `liemdai.io.vn` |
| iptables `DOCKER-USER` | Một IP mở quá nhiều kết nối mới | Root trên VPS, bên dưới |
| Caddy | Kết nối chậm (slowloris), header lớn | `infra/Caddyfile.prod` (timeout `read_header` 10 s, `read_body` 30 s, `idle` 2 phút), `mem_limit` 256 MB |
| api: `RATE_LIMIT_API_PER_MINUTE` (240) | Một IP gửi quá nhiều request `/api/*`, kể cả đường dẫn không tồn tại; trả 429 trước khi chạm DB | `app/middleware.py`, đếm trong Redis |
| api: `RATE_LIMIT_PER_MINUTE` (10) | Câu hỏi tốn tiền LLM | `app/api/guard.py` |
| api: hạn mức ngày (mục 7c) | Một IP hay tài khoản hỏi quá nhiều trong ngày, tổng token cả hệ thống | `app/services/quota.py`, đếm trong Redis |

iptables: rule phải ở chain `DOCKER-USER`, không phải ufw. Rule nạp bằng service systemd `indexbeast-firewall` (file trong `infra/firewall/`), chạy sau `docker.service` nên còn sau khi khởi động lại; script kiểm tra trước khi thêm nên chạy lại không trùng. Không dùng `iptables-persistent`: nó lưu cả rule Docker tự sinh, khôi phục lúc khởi động có thể xung đột với Docker.

- Mỗi IP tối đa ~20 kết nối mới/giây vào 80/443 (dư cho trình duyệt: HTTP/2 dùng chung một kết nối).
- IP/CIDR chặn hẳn: `/etc/indexbeast/blocked-ips`, mỗi dòng một.

Cài một lần (root; user `deploy` thuộc nhóm `docker` nên chạy được qua container đặc quyền, như dòng `R=` bên dưới):

```bash
# Từ ~/Index-Beast trên VPS. Không có sudo thì thay `sudo` bằng:
#   R="docker run --rm --privileged --pid=host --network host --entrypoint nsenter caddy:2.11.7-alpine -t 1 -m -u -n -i"
# và chạy lệnh dạng: $R sh -c "<lệnh>" (đường dẫn /tmp của máy chủ dùng chung được)
sudo install -m 0755 infra/firewall/indexbeast-firewall.sh /usr/local/sbin/indexbeast-firewall.sh
sudo install -m 0644 infra/firewall/indexbeast-firewall.service /etc/systemd/system/indexbeast-firewall.service
sudo install -d -m 0755 /etc/indexbeast && sudo install -m 0644 infra/firewall/blocked-ips.example /etc/indexbeast/blocked-ips
sudo systemctl daemon-reload && sudo systemctl enable --now indexbeast-firewall
```

Khi đang bị dội:

```bash
echo 203.0.113.7 | sudo tee -a /etc/indexbeast/blocked-ips && sudo systemctl restart indexbeast-firewall
sudo iptables -L DOCKER-USER -n -v --line-numbers     # cột pkts của dòng chặn phải tăng
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app restart caddy   # bỏ kết nối cũ Caddy còn giữ
# Gỡ một IP: xóa dòng trong blocked-ips, rồi `iptables -D DOCKER-USER -s <ip> -j DROP` (restart service chỉ thêm, không gỡ)
```

**Lưu log trước khi deploy hay tạo lại container** (log Docker mất cùng container; sự cố 22/11 mất log đợt 1 vì deploy lại):

```bash
mkdir -p ~/incident && chmod 700 ~/incident
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app logs --no-log-prefix caddy > ~/incident/caddy-$(date +%F-%H%M).log
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app logs --no-log-prefix api > ~/incident/api-$(date +%F-%H%M).log
```

Truy nguồn khi site chậm hoặc timeout (Caddy chỉ ghi lỗi, không ghi access log; api không ghi IP):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app logs --no-log-prefix --since 30m caddy   | python3 -c "import sys,json,collections as c; n=c.Counter(json.loads(l).get('request',{}).get('client_ip') for l in sys.stdin if l.startswith('{')); print(n.most_common(5))"
```

## 7c. Hạn mức hỏi đáp mỗi ngày

Sự cố 22/11/2026: một IP lạ nhận 234 câu trả lời thật (~2,34 triệu token prompt, 112 nghìn token completion, 115 lượt tìm corpus có Jina rerank, 10 lượt Tavily) vì giới hạn mỗi phút không chặn được người hỏi chậm đều. Từ nay có thêm hạn mức theo ngày (giờ Việt Nam, làm mới 0 giờ):

| Đối tượng | Câu hỏi/ngày | Token/ngày | Biến |
|---|---|---|---|
| Khách (theo IP) | 5 | 100.000 | `CHAT_GUEST_DAILY_QUESTIONS`, `CHAT_GUEST_DAILY_TOKENS` |
| Tài khoản đăng nhập Discord | 30 | 500.000 | `CHAT_USER_DAILY_QUESTIONS`, `CHAT_USER_DAILY_TOKENS` |
| Cả hệ thống (kể cả bot, trừ admin) | không | 5.000.000 | `CHAT_DAILY_TOKEN_BUDGET` |
| Admin (`AUTH_ADMIN_DISCORD_IDS`) | không giới hạn | không giới hạn | |

Hết hạn mức: API trả 429 `quota_exceeded` + `Retry-After` (giây đến 0 giờ VN). `0` = tắt giới hạn đó. Token chỉ được cộng sau khi trả lời xong nên ngân sách có thể vượt tối đa một câu trả lời. Redis lỗi thì `/chat` trả 503.

Đổi hạn mức: sửa biến trong `.env` rồi `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app up -d api`.

Xóa bộ đếm của một người (`<khóa>` là `user:<uuid>` hoặc `guest:<ip>`; `<YYYYMMDD>` theo giờ VN):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec redis redis-cli DEL quota:questions:<khóa>:<YYYYMMDD> quota:tokens:<khóa>:<YYYYMMDD>
# Xem bộ đếm hiện có
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec redis redis-cli --scan --pattern 'quota:*'
```

## 8. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Trình duyệt báo chứng chỉ sai / không vào được | DNS chưa trỏ, cổng 80 bị chặn, Let's Encrypt giới hạn | `dig`, `ufw status`, `docker compose ... logs caddy`; đợi, đừng deploy dồn dập |
| `deploy.sh` thoát 1 sau "CHƯA qua được HTTPS" | DNS chưa trỏ hoặc Caddy chưa lấy được chứng chỉ | Dịch vụ đã chạy nhưng chưa tới được người dùng nên deploy tính là lỗi. Lần deploy ĐẦU (bootstrap chứng chỉ): `ALLOW_HTTPS_PENDING=1 scripts/deploy.sh` (cảnh báo và thoát 0); sau đó kiểm tra HTTPS bằng tay. Các lần sau không dùng cờ này |
| `deploy.sh`: ".env đang có quyền ..." | quyền file | `chmod 600 .env` |
| `deploy.sh`: "Working tree có thay đổi" | sửa tay trên VPS | `git status`; hoàn tác (`git restore <file>`) hoặc commit từ máy dev. Không sửa tay trên VPS |
| api không lên, log có `change-me` | `ENVIRONMENT=prod` từ chối giá trị mẫu | điền biến đã nêu trong log (chỉ in tên biến) |
| api restart liên tục, log alembic lỗi | migration lỗi hoặc PostgreSQL chưa sẵn sàng | đọc log; mã cũ chạy tiếp được: `deploy.sh <tag-cũ>` |
| api bị OOM (`docker inspect` → `OOMKilled`) | encoder + model vượt 3 GB | `API_WORKERS=1` trong `.env`, deploy lại |
| Đăng nhập Discord báo `invalid redirect_uri` | URL trong Portal khác `AUTH_REDIRECT_URI` | sửa Portal theo mục 3.3 |
| Đăng nhập xong vẫn như chưa đăng nhập | cookie không `Secure`, hoặc truy cập qua `http://` | luôn dùng https; xem `AUTH_COOKIE_SECURE` (overlay đặt true) |
| Chữ trả lời hiện một lần thay vì chạy dần | Cloudflare/proxy trung gian đệm SSE | tắt proxy (đám mây xám) hoặc tắt buffering cho `/api/*` |
| Console trình duyệt báo `Refused to ...` (CSP) | nguồn ngoài chưa được cho phép | xem directive trong `infra/Caddyfile.prod`; nới tối thiểu |
| `restore.sh pg`: dừng ở bước 1-3 với "DB đang chạy chưa bị đụng" | dump hỏng/thiếu bảng lõi, hoặc hết đĩa | dịch vụ vẫn chạy; xem thông báo, thử bản dump khác. DB tạm `_restore` tự bị xóa ở lần chạy sau |
| `restore.sh`: "File phải nằm trong ..." | file ngoài `BACKUP_DIR` | `mv` file vào `BACKUP_DIR` (hoặc đặt `BACKUP_DIR`) |
| Hết dung lượng đĩa | log, ảnh Docker cũ, backup | `docker system df`, `docker image prune -f`, giảm `KEEP_DAILY` |
