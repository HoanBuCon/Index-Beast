# Staging trên VPS

Môi trường chạy thử trên máy thật để phát hiện sớm vấn đề tài nguyên (thẻ Sprint 3, mục 3.3). Cấu hình dự kiến: **1 VPS Ubuntu 24.04, 4 vCPU, 8 GB RAM, chưa có tên miền.**

> Trạng thái: toàn bộ file bên dưới đã kiểm tra cú pháp (Caddyfile, `docker compose config`, `bash -n`) nhưng **chưa chạy trên VPS thật** vì chưa có máy. Số đo RAM/CPU ở mục 7 phải được điền sau lần chạy đầu tiên.

## 1. Kiến trúc

```text
Internet ──443/80──▶ Caddy (basic auth + danh sách IP, HTTPS)
                       ├─ /api/*  ──▶ api (FastAPI + RAG, 3 GB)
                       │               ├─▶ PostgreSQL  (hội thoại, trace, corpus)
                       │               ├─▶ Qdrant      (vector lore_chunks, bộ nhớ hội thoại)
                       │               ├─▶ Redis       (rate limit)
                       │               └─▶ DeepSeek / Tavily (Internet, chiều đi)
                       └─ còn lại ──▶ file tĩnh của web
bot Discord ─────────────────────────▶ api (trong mạng Docker, X-Service-Token)

Cổng công khai: 22 (SSH, chỉ khóa), 80, 443. Mọi cổng khác chỉ gắn 127.0.0.1 hoặc nằm trong mạng Docker.
```

## 2. Ngân sách tài nguyên (8 GB RAM)

| Service | `mem_limit` | `cpus` |
|---|---|---|
| api | 3 GB | 2,5 |
| Qdrant | 1 GB | 1,5 |
| PostgreSQL | 1 GB | 1,0 |
| Redis | 192 MB | 0,5 |
| bot | 192 MB | 0,5 |
| Caddy | 64 MB | 0,5 |
| **Tổng giới hạn** | **≈ 5,4 GB** | (tổng > 4 vì là trần, không phải phần giữ chỗ) |

Còn khoảng 2,6 GB cho hệ điều hành, Docker và bộ nhớ đệm tệp; thêm 2 GB swap cho lúc build ảnh web. Giới hạn của api (3 GB) là con số cần kiểm chứng đầu tiên: mỗi worker nạp encoder E5 và BM25, mặc định 2 worker (`API_WORKERS`). Nếu OOM thì giảm `API_WORKERS=1` hoặc `RAG_ENCODER_THREADS`, đừng nâng giới hạn trước khi đo.

## 3. Chuẩn bị (làm một lần)

**Trên máy bạn:** tạo khóa SSH riêng cho staging, rồi mang khóa công khai lên VPS.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/indexbeast-staging -C "staging-deploy"
scp ~/.ssh/indexbeast-staging.pub root@<ip-vps>:/root/deploy.pub
```

**Trên VPS (root):** chạy script cài đặt. Script cài Docker, tạo user `deploy` (không có sudo, nhưng thuộc nhóm `docker` nên **tương đương root trên VPS**: giữ kín khóa SSH), bật `ufw` chỉ mở 22/80/443, tắt đăng nhập SSH bằng mật khẩu và bằng root, thêm 2 GB swap.

```bash
git clone https://github.com/HoanBuCon/Index-Beast.git /tmp/ib && bash /tmp/ib/scripts/staging/bootstrap.sh /root/deploy.pub
```

**Trước khi đóng phiên root,** mở cửa sổ khác và kiểm tra `ssh -i ~/.ssh/indexbeast-staging deploy@<ip-vps>` vào được. Nếu không vào được thì sửa ngay trong phiên root, nếu không bạn sẽ tự khóa mình ngoài VPS.

## 4. Cấu hình và dữ liệu

Đăng nhập bằng `deploy`:

```bash
git clone https://github.com/HoanBuCon/Index-Beast.git ~/Index-Beast && cd ~/Index-Beast
cp .env.staging.example .env && chmod 600 .env
# Tạo băm mật khẩu basic auth, dán vào STAGING_PASSWORD_HASH (trong dấu nháy đơn)
docker run --rm caddy:2.11.7-alpine caddy hash-password
# Sinh token: openssl rand -hex 32 (cho POSTGRES_PASSWORD, API_SERVICE_TOKEN, ADMIN_TOKEN)
nano .env
```

**Model E5 (~465 MB):** `.dockerignore` không đưa model vào ảnh, nên chép từ máy bạn (hoặc để lần chạy đầu tự tải từ Internet):

```bash
rsync -a backend/models/ deploy@<ip-vps>:~/Index-Beast/backend/models/
```

**Corpus** (4.164 trang, 23.765 chunk, 18.368 chunk tiếng Anh được index). Dữ liệu chỉ cần chép các bảng corpus, **không chép hội thoại của máy dev**. Làm sau lần deploy đầu tiên (cần schema đã có):

```bash
# Trên máy dev (thư mục gốc repo)
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --data-only -t documents -t chunks -t entities' > corpus.dump
curl -s -X POST http://127.0.0.1:16333/collections/lore_chunks/snapshots   # ghi lại tên snapshot trong kết quả
curl -s -o lore.snapshot http://127.0.0.1:16333/collections/lore_chunks/snapshots/<tên-snapshot>
scp corpus.dump lore.snapshot deploy@<ip-vps>:~/

# Trên VPS
cd ~/Index-Beast
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.staging.yml --profile app"
$COMPOSE exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --exit-on-error' < ~/corpus.dump
curl -s -X POST "http://127.0.0.1:16333/collections/lore_chunks/snapshots/upload?priority=snapshot" -F "snapshot=@$HOME/lore.snapshot"
$COMPOSE run --rm api python -m scripts.memory_admin setup --apply   # collection bộ nhớ hội thoại
```

Ảnh minh họa (`backend/data/media`, ~7,5 GB) **không** được chép mặc định; staging chạy với `RAG_IMAGES_ENABLED=false`. Muốn bật thì rsync `backend/data/media`, `clean_runs/s2-full-v2/images.csv`, `chunk_runs/s2-full-v1/documents.jsonl` và thư mục media manifest của lượt crawl, rồi đặt `RAG_IMAGES_ENABLED=true`.

## 5. Deploy

```bash
cd ~/Index-Beast && scripts/staging/deploy.sh develop
```

Script lấy mã theo nhánh hoặc tag, build, khởi động PostgreSQL/Qdrant/Redis, chỉnh quyền thư mục, chạy `alembic upgrade head`, rồi khởi động toàn bộ và chờ healthy. Không có `DISCORD_TOKEN` thì bỏ qua container bot. **Rollback:** chạy lại với tag hoặc commit cũ; dữ liệu trong volume được giữ.

Kiểm tra:

```bash
curl -sk -u "staging:<mật-khẩu>" https://<ip-vps>/api/v1/health
```

Trình duyệt sẽ cảnh báo chứng chỉ khi truy cập bằng IP, vì Caddy dùng CA nội bộ. Mật khẩu vẫn đi qua HTTPS. Thông báo chỉ xuất hiện một lần cho mỗi trình duyệt.

## 6. Bảo vệ

- **Caddy:** basic auth bắt buộc (không có `STAGING_PASSWORD_HASH` thì Caddy không khởi động) và tùy chọn `STAGING_ALLOW_IPS` để chỉ cho IP nhóm vào.
- **ENVIRONMENT=prod:** API từ chối khởi động nếu còn `change-me`, và ẩn Swagger/OpenAPI.
- **`/api/v1/admin/*`:** thêm một lớp `X-Admin-Token`, tắt cho tới khi đặt `ADMIN_TOKEN`.
- **ufw:** chỉ mở 22/80/443. Docker thêm luật iptables riêng và **bỏ qua ufw** với cổng nó công khai, nên compose staging chỉ công khai 80/443, các cổng khác gắn `127.0.0.1`. Đừng thêm `ports` công khai.
- **Chưa làm:** fail2ban, cập nhật bảo mật tự động, giám sát và backup (thẻ Sprint 5).

## 7. Đo RAM và CPU

Sau khi deploy và nạp dữ liệu, chạy một câu hỏi RAG thật. **Lệnh này gọi DeepSeek (và Tavily nếu bật) nên tốn một ít phí API.**

```bash
STAGING_PASS='<mật-khẩu>' scripts/staging/measure.sh "Marika là ai?"
```

Script in RAM/CPU trước và sau, đỉnh của từng container trong lúc hỏi, mã HTTP và thời gian trả lời. Dán kết quả vào đây:

| Container | RAM đỉnh | CPU đỉnh | Giới hạn |
|---|---|---|---|
| _chưa đo_ | | | |

Câu hỏi đầu tiên chậm hơn vì encoder nạp lười; hãy đo cả lần đầu và lần thứ hai.

## 8. Khi có tên miền

Trỏ DNS A về IP VPS, đặt `STAGING_HOST=<tên-miền>` trong `.env` rồi `scripts/staging/deploy.sh`. Caddy tự xin chứng chỉ Let's Encrypt và hết cảnh báo trình duyệt. Production (Sprint 5) dùng `infra/Caddyfile` và không có basic auth.
