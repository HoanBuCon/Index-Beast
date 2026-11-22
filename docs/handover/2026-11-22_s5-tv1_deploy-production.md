# TV1 · Deploy production lần đầu tại tarnished.liemdai.io.vn (22/11/2026)

Sprint 5, thẻ 5.1–5.3. Release v2 (PR #143, `main` 825437f) chạy thật trên VPS. Tài liệu vận hành: [`docs/production.md`](../production.md).

## Hạ tầng

| Mục | Giá trị |
|---|---|
| VPS | Viettel IDC, gói CS3: 4 vCPU, 8 GB RAM, 79 GB SSD, Ubuntu 24.04.3. **Gói dùng thử hết hạn 27/11/2026** |
| IP | 27.71.17.172 |
| DNS | Bản ghi A `tarnished` → 27.71.17.172 trong Zone Editor của cPanel LANIT (nameserver `ns1/ns2.lanit.com.vn`), không dùng mục "Subdomains" |
| Cài đặt | `scripts/staging/bootstrap.sh`: Docker 29.10, Compose v5.8, user `deploy` (nhóm `docker`), ufw 22/80/443, SSH chỉ khóa, root không đăng nhập. Swap 2 GB có sẵn (`/swap.img`) |
| SSH | Khóa ed25519 riêng mỗi người trong `/home/deploy/.ssh/authorized_keys`, comment theo tên (hiện có TV1 và `tv3-thosan`). Thu hồi: xóa dòng. Nhóm `docker` tương đương root, nên chỉ cấp cho người cần |

## `.env` (không ghi giá trị)

- Secret sinh mới bằng `secrets.token_hex(32)`: `POSTGRES_PASSWORD`, `API_SERVICE_TOKEN`, `ADMIN_TOKEN`, `AUTH_SECRET`.
- `RAG_COLLECTION=indexbeast_s4_wiki_ca98c06b`.
- Reranker **Jina** thay L12 cục bộ: `RAG_RERANKER_ENABLED=true`, `RAG_RERANKER_PROVIDER=jina`, `JINA_API_KEY`. Thiếu key hoặc hết token thì api lặng lẽ giữ thứ tự RRF.
- `AUTH_ADMIN_DISCORD_IDS`: 4 ID thành viên. `DISCORD_CLIENT_ID` đã đối chiếu: cùng Application với token bot.
- Discord Portal: thêm redirect `https://tarnished.liemdai.io.vn/api/v1/auth/discord/callback` (thiếu là lỗi "redirect_uri không hợp lệ").
- Bản dự phòng `.env.prod` ở máy TV1 (bị git bỏ qua).

## Dữ liệu

`data.zip` (17 GB, TV2 duyệt) là thư mục `backend/data` thô, **không có snapshot Qdrant hay dump PostgreSQL**. Bản đang phục vụ được xác định bằng mã băm: đuôi collection `ca98c06b` = SHA-256 của `chunk_runs/s4-wiki-release/chunks.jsonl`. `delivery/final` là bản 09/11 (`structured-release`, "offline_validated_not_production_indexed") nên không dùng.

Chỉ giải nén `chunk_runs/s4-wiki-release`, `chunk_runs/s5-origins-addon`, `raw/` và `crawl_runs/s2-full-20261028` (khoảng 0,5 GB; `load_full` cần raw snapshot để kiểm provenance). Không chép ảnh (`RAG_IMAGES_ENABLED=false`).

```bash
C="docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app"
setfacl -R -m u:10001:rwX -m d:u:10001:rwX backend/data backend/models
$C run --rm api python -m ingest.chunk.load_full data/chunk_runs/s4-wiki-release --validate-only
$C run --rm api python -m ingest.chunk.load_full data/chunk_runs/s4-wiki-release
$C run --rm api python -m ingest index --input data/chunk_runs/s4-wiki-release/chunks.jsonl --policy pilot --languages en --collection indexbeast_s4_wiki_ca98c06b
$C run --rm api python -m ingest index --input data/chunk_runs/s5-origins-addon/chunks.jsonl --policy pilot --languages en --collection indexbeast_s4_wiki_ca98c06b
$C run --rm api python -m scripts.memory_admin setup --apply
```

Model E5 + BM25 chép từ máy dev bằng `tar | ssh` (VPS và Git Bash không có rsync).

## Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| `caddy validate` Caddyfile.prod (lần đầu trên máy thật) | Valid configuration |
| `deploy.sh` | thoát 0; mọi container `healthy` (bot không có healthcheck, online) |
| `/api/v1/health` qua HTTPS | postgres, redis, qdrant `true` |
| Chứng chỉ | Let's Encrypt, hết hạn 20/02/2027 |
| Header | HSTS, CSP, X-Frame-Options DENY, nosniff; không có `Server` |
| `http://` | 308 sang https |
| `/api/docs`, `/api/openapi.json`, `/api/v1/dev/*` | 404 |
| PostgreSQL | 4.164 documents, 39.574 chunks (khớp `postgres-report.json` của TV2) |
| Qdrant `indexbeast_s4_wiki_ca98c06b` | 34.138 điểm (34.070 + 68 addon), green. Index mất ~90 phút trên VPS, container index chạm ~2,99/3 GiB nhưng không bị OOM |
| Hỏi thử "Who is Malenia and where do I fight her?" | 200, 6 s, 5 trích dẫn đúng trang wiki; Jina reranker `ok` |
| Slash command | Đăng ký global đủ 6: `/about`, `/ask`, `/clear` (user, all), `/help`, `/ping`, `/setup` (enable, disable, disable-all) |
| RAM lúc chạy | api ~385 MB, cả hệ thống < 1 GB khi rảnh |

## Sửa trong nhánh này (`fix/s5-tv1-prod-logging`)

1. **Access log ghi IP người dùng dù có `--no-access-log`.** uvicorn ghi access log khi `logging.getLogger("uvicorn.access").hasHandlers()`; `setup_logging` đặt `propagate=True` nên logger này kế thừa handler của root. Sửa: `uvicorn.access` không handler, `propagate=False`. Middleware `app.http` vẫn log method/path/status/ms, không IP.
2. **Log "Reranker outcome" mất chi tiết.** `JsonFormatter` chỉ in `data`, còn reranker truyền `extra={"event": ..., "status": ...}`. Sửa: mọi extra ngoài thuộc tính chuẩn của `LogRecord` được gộp vào `data` (bỏ `color_message` của uvicorn). Đã rà: chỉ reranker và `privacy.py` dùng extra kiểu này, toàn số đếm/trạng thái, không có câu hỏi hay IP.
3. `docs/privacy.md`: thêm Jina vào danh sách dịch vụ nhận câu hỏi. `docs/production.md`: cập nhật trạng thái.

Kiểm tra: `ruff check` đạt, `ruff format --check` đạt, `pytest tests/unit` 1018 passed (3 test mới trong `test_logging.py`, viết trước và thất bại trước khi sửa).

## Chưa làm / cần quyết định

- VPS đang chạy `main` 825437f, **chưa có hai bản sửa log ở trên** (cần merge vào develop → main rồi `scripts/deploy.sh`). Log hiện tại trên VPS đã có IP từ lúc deploy; xoay vòng theo driver `local` (5×20 MB).
- Chưa gắn tag `v2.0.0` (việc của TV1).
- 11 trang Origins chỉ có trong Qdrant, chưa có trong PostgreSQL (giống máy TV2). Lần dựng toàn bộ sau nên nạp cả hai.
- Chưa cài crontab backup (`docs/production.md` mục 6), chưa thử `restore.sh`, chưa có ping ngoài.
- `~/release-data/data.zip` (17 GB) còn trên VPS; xóa khi không cần.
- Gói VPS dùng thử hết hạn 27/11: gia hạn hoặc chuyển máy (chuyển máy = làm lại toàn bộ, kể cả index ~90 phút; nên chụp snapshot Qdrant bằng `scripts/backup.sh weekly` để lần sau chỉ restore).
- NFR-PERF-01 (p95 ≤ 10 s) chưa đo trên production.
