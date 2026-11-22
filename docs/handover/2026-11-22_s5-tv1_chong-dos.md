# TV1 · Chống DoS sau sự cố dội request trên production (22/11/2026)

Sprint 5, sau lần deploy đầu tiên. Nhánh `fix/s5-tv1-dos-hardening`. Runbook vận hành: [`docs/production.md`](../production.md) mục 7b.

## Sự cố

- 12:57–14:48 UTC: một IP (`42.113.159.79`, dải Việt Nam, user-agent `fasthttp`) gửi tới ~1.400 request lỗi/phút. Log api trong 3 giờ: 54.386 `GET /api/v1/answer-shares` (404), 18.805 `POST /chat/stream` (429), 8.579 `GET /api/v1/images/<aaa…/bbb…>` (404). Caddy gửi ra 5,87 GB.
- Caddy chạm trần 64 MB, healthcheck `unhealthy`, ngừng nhận kết nối 443; DNS nội bộ Docker quá tải (`lookup api: i/o timeout`). Người dùng thấy Connection timed out.
- ID giả cố định và đúng endpoint của dự án: có thể là người trong nhóm chạy công cụ benchmark (bombardier dùng fasthttp) vào production, không kết luận được. Không phải `backend/loadtest` (Locust).
- `ufw` không chặn được: Docker mở cổng bằng iptables riêng. Phải dùng chain `DOCKER-USER`.
- Giới hạn `/chat` (10/phút/IP) đã chặn 18.805 câu hỏi nên không tốn tiền DeepSeek.

## Threat model (STRIDE, chữ D)

| Ranh giới | Lạm dụng | Trước | Sau |
|---|---|---|---|
| Internet → Caddy | Nhiều kết nối mới từ một IP | Không giới hạn | iptables hashlimit (root, runbook) |
| Internet → Caddy | Kết nối chậm, header lớn | Không có read timeout | `read_header` 10 s, `read_body` 30 s, `idle` 2 phút, header ≤ 32 KB |
| Caddy | Bộ nhớ | 64 MB | 256 MB |
| Caddy → api | Dội mọi endpoint, kể cả 404 | Chỉ `/chat` và đăng nhập có giới hạn | `RATE_LIMIT_API_PER_MINUTE` 240/IP/phút cho mọi `/api/*`, trả 429 trước router |
| Nhiều IP / băng thông | DDoS thật | Không có | Chưa có: cần Anti-DDoS của nhà mạng hoặc CDN |

## Thay đổi

1. **`ApiRateLimitMiddleware`** (`backend/app/middleware.py`): đếm `ratelimit:api:ip:<ip>:<phút>` trong Redis (đúng cho 2 worker), vượt trần trả 429 + `Retry-After` theo định dạng lỗi chung. Nằm trong RequestContext và CORS nên 429 vẫn có request id, được log và web đọc được.
   - Không tính: `/api/v1/health`, bot có `X-Service-Token` đúng (bot gom mọi người dùng Discord về một IP; `/chat` của bot đã có giới hạn theo external_ref/guild). Token sai bị tính như người thường.
   - Redis lỗi thì cho qua (log `api rate limit unavailable`): lớp này chỉ chống dội request; giới hạn `/chat` vẫn đóng (503) như cũ.
   - IPv6 gộp /64 như giới hạn cũ (`guard.ip_key`, tách từ `_client_ip`). `_retry_after` đổi thành `retry_after` để dùng chung.
   - `RATE_LIMIT_API_PER_MINUTE` (mặc định 240, 0 = tắt) trong `core/config.py`, `.env.example`, `docker-compose.yml`. 240: một lượt tải trang gọi ~5 request, còn dư cho nhiều người sau cùng một NAT.
2. **Caddy** (`infra/Caddyfile.prod`): timeout đọc và giới hạn header như bảng trên. Không đặt `write` timeout vì SSE trả tới 90 s. Caddy bản chuẩn không có module rate limit (đã kiểm `caddy list-modules`); không thêm plugin `caddy-ratelimit` để khỏi phải build Caddy riêng (thêm phụ thuộc cần duyệt).
3. **`docker-compose.prod.yml`**: Caddy `mem_limit: 256m`.
4. **`docs/production.md`**: mục 7b (các lớp, lệnh iptables `DOCKER-USER`, cách truy IP từ log lỗi Caddy), ngân sách RAM.

## Kiểm tra

| Lệnh | Kết quả |
|---|---|
| `pytest tests/unit/test_api_rate_limit.py` (6 test mới, viết trước, 3 test hành vi thất bại trước khi sửa) | 6 passed |
| `pytest tests/unit` | 1021 passed |
| `ruff check`, `ruff format --check` | đạt |
| `caddy validate` Caddyfile.prod mới (trên VPS, bản copy ở /tmp) | Valid configuration |
| `docker compose config` overlay mới | hợp lệ, caddy `mem_limit` 268435456 |

## Chưa làm

- Chưa deploy: cần merge develop → main rồi `scripts/deploy.sh`.
- iptables cần root: TV1 chạy theo runbook mục 7b. Chưa đưa vào `bootstrap.sh` (rule phải nạp sau khi Docker tạo chain `DOCKER-USER`; cần thử trên máy thật).
- Chưa có lớp nhà mạng/CDN cho DDoS nhiều IP. Đã cân nhắc: Anti-DDoS Viettel IDC (hỏi nhà cung cấp) hoặc Cloudflare (chuyển nameserver cả `liemdai.io.vn`, ảnh hưởng dự án khác trên cPanel; cần kiểm SSE không bị đệm).
- Caddy `unhealthy` không tự khởi động lại (Docker chỉ restart khi tiến trình thoát): cần ping ngoài báo về Discord (`docs/production.md` mục 7).
- Observability của Viettel IDC (agent OpenTelemetry) chỉ giám sát, không chặn; có thể cài sau, giữ kín khóa trong lệnh cài.
