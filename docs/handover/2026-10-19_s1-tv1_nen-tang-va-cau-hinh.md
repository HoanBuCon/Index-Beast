# Bàn giao S1 · TV1 — Nền tảng backend, hạ tầng dev và cấu hình

| | |
|---|---|
| Người thực hiện | TV1 (Hoanbucon) — Tech Lead · Backend & DevOps |
| Ngày | 2026-10-19 (Sprint 1, ngày 1) |
| Trạng thái | 4 thẻ đã merge vào `develop`; bản sửa lỗi + tài liệu này nằm ở `fix/s1-tv1-env-config-cleanup` |
| Đọc kèm | [`README.md`](../../README.md) (chạy local, cấu hình) · [`04_ARCHITECTURE.md`](../04_ARCHITECTURE.md) · [`quy_uoc.md`](../quy_uoc.md) |

## 1. Phạm vi

| Thẻ Trello | Nhánh | PR | Checklist |
|---|---|---|---|
| [S1][TV1] CI GitHub Actions cơ bản | `feature/s1-tv1-ci` | gộp trong #8 | 4/4 |
| [S1][TV1] Khởi tạo monorepo & quy ước code | `feature/s1-tv1-repo-conventions` | #8 | 4/5 — còn branch protection |
| [S1][TV1] Docker Compose môi trường dev | `feature/s1-tv1-docker-compose` | #9 | 5/6 — còn "cả 4 thành viên chạy được" |
| [S1][TV1] Skeleton FastAPI | `feature/s1-tv1-fastapi-skeleton` | #10 | 6/6 |
| Rà soát & sửa lỗi cấu hình (ngoài kế hoạch) | `fix/s1-tv1-env-config-cleanup` | chưa mở | — |

CI trên GitHub xanh ở #8, #9, #10 và trên `develop` (gồm cả integration test với PostgreSQL/Redis/Qdrant thật).

## 2. Quy tắc làm việc (bắt buộc)

### Git & PR

- Nhánh tách từ `origin/develop`, đặt tên `feature|fix|docs|refactor/s<sprint>-tv<n>-<ten-ngan>`; PR luôn về `develop` (chi tiết: [`quy_uoc.md`](../quy_uoc.md)).
- Commit theo Conventional Commits; mỗi commit một mục đích.
- **CODEOWNERS = `@HoanBuCon`**: Mentor review mọi PR. PR do chính Mentor tạo phải nhờ thành viên khác review.
- Khi nhiều nhánh nối tiếp nhau (nhánh sau tách từ nhánh trước): mở PR và **merge đúng thứ tự** để mỗi PR chỉ hiện phần của nó.
- Điền đủ [PR template](../../.github/pull_request_template.md): link thẻ Trello, cách kiểm tra, checklist.

### Trước khi commit

- Chạy `pre-commit install` một lần. Hook gồm: ruff check + format (backend), prettier (web, bot), chặn private key, chặn file > 1 MB, sửa khoảng trắng/xuống dòng.
- Hook **bỏ qua** `docs/export/`, `docs/presentation/`, `docs/03_SPRINT_PLAN.md` và mọi `.docx/.pptx/.pdf` (file sinh tự động hoặc nhị phân — từng bị hook sửa hỏng file `.docx`).
- Docstring/comment ≤ 120 ký tự mỗi dòng (ruff E501) — 18 docstring dài từng làm đỏ CI ở mọi PR.

### Comment & docstring

- Đầu mỗi module: một docstring ngắn nói **file làm gì** + dòng `Phụ trách: TVx · [Sx] <tên thẻ>`; sửa lại dòng này khi phạm vi đổi.
- Comment giải thích **vì sao** (ràng buộc, lỗi đã gặp), không lặp lại điều code đã nói.

## 3. Môi trường dev

| Công cụ | Phiên bản | Ghi chú |
|---|---|---|
| Python | 3.11.9 | venv tại `backend/.venv` |
| pip | 26.2.1 | cài kèm `-c constraints.txt` |
| Node.js | **24.22.0** | Node 22 chạy được web nhưng bot cần ≥ 24 để chạy thẳng `.ts`; react-router 8 cần ≥ 22.22 |
| Docker | Compose v2 | PostgreSQL 18.6, Qdrant v1.19.2, Redis 8.10.2 |

Lệnh hằng ngày: `make up`, `make api`, `make test`, `make lint` — bảng đầy đủ (kèm lệnh gốc cho máy không có `make`) ở README → "Chạy local".

Quy tắc hạ tầng dev:

- **Không dùng cổng mặc định của công cụ** (cập nhật 2026-10-20): cổng dự án = cổng gốc + 10000 — API `18000`, web `15173`, PostgreSQL `15432`, Qdrant `16333`, Redis `16379`; mỗi cổng là một biến `*_PORT` trong `.env` ([`quy_uoc.md`](../quy_uoc.md) §8). Trong Docker, container api nghe `18000`. Không dùng `--host 0.0.0.0` khi dev (mở API, kể cả endpoint gọi DeepSeek, cho cả mạng LAN).
- **Cổng chỉ mở trên `127.0.0.1`** (15432, 16333, 16379): chỉ máy mình truy cập được; mỗi người có dữ liệu dev riêng. Không đổi thành `0.0.0.0` — Redis/Qdrant chưa có mật khẩu.
- **Dùng `127.0.0.1`, không dùng `localhost`** cho địa chỉ dịch vụ: Windows phân giải `localhost` sang IPv6 (`::1`) trước, Docker chỉ mở IPv4 → kết nối timeout ~2 s.
- **Container không ghi log xuống đĩa** (`logging.driver: none`). Muốn xem log: `make debug-up` rồi `make logs` (driver `local`, xoay vòng 5×20 MB). Đổi lại, mặc định `docker compose logs` trống.
- PostgreSQL 18: volume mount vào `/var/lib/postgresql` (không phải `.../data` như bản ≤ 17).
- Qdrant dashboard: http://localhost:16333/dashboard.

## 4. Cấu hình (`.env`)

**Một file `.env` duy nhất ở gốc repo**, sao chép từ `.env.example` (file mẫu là hợp đồng cấu hình, được commit).

| Thành phần | Đọc thế nào |
|---|---|
| Backend | `core/config.py` (pydantic-settings) đọc `<gốc repo>/.env` theo **đường dẫn tuyệt đối**. Ưu tiên: biến môi trường thật > `.env` > giá trị mặc định trong code |
| Bot (dev) | `node --env-file=../.env` |
| Docker Compose | Lấy `${...}` từ `.env`; mỗi container **chỉ** nhận biến liệt kê trong `environment:` của nó (bot không biết mật khẩu DB/key LLM). Địa chỉ hạ tầng trong Docker là tên service (`postgres`, `qdrant`, `redis`) |
| Test | Không đọc `.env` — `Settings(_env_file=None)` |
| CI | `env:` trong workflow; secret thật đặt ở GitHub Secrets |
| Production | `.env` trên VPS, `chmod 600`, `ENVIRONMENT=prod` |

Quy tắc:

- **Chú thích đặt trên dòng riêng.** Không viết `KEY=  # chú thích`: docker compose đọc phần chú thích thành giá trị khi giá trị để trống (đã gặp với `DISCORD_GUILD_ID`). Test `test_env_example.py` chặn lỗi này.
- **PostgreSQL chỉ khai báo qua `POSTGRES_HOST/PORT/USER/PASSWORD/DB`**; backend tự ghép URL (tự mã hoá ký tự đặc biệt trong mật khẩu). Không còn `DATABASE_URL`.
- Mật khẩu là `SecretStr` — không hiện khi in/log `Settings`.
- **Production từ chối khởi động** nếu còn giá trị `change-me`; thông báo lỗi chỉ nêu tên biến, không in giá trị.
- Biến chưa dùng tới được để dạng comment trong `.env.example`, ghi sprint sẽ bật.

**Thêm một biến mới (4 bước):**

1. Thêm trường vào `backend/core/config.py` (đúng nhóm) hoặc `bot/src/config.ts`.
2. Thêm dòng mẫu + chú thích vào `.env.example` (test sẽ báo nếu quên).
3. Container cần biến đó → thêm vào `environment:` của service trong `docker-compose.yml`.
4. Ghi trong mô tả PR để mọi người cập nhật `.env`.

## 5. Backend skeleton — cách dùng & điểm mở rộng

```
uvicorn --factory app.main:create_app
  create_app()      → kiểm tra cấu hình, setup log JSON, middleware, router
  lifespan          → build_context() lúc khởi động, ctx.aclose() lúc tắt
  GET /api/v1/health→ chạy mọi health check đã đăng ký (song song, có timeout) → 200 / 503
```

| Muốn | Làm ở đâu |
|---|---|
| Thêm tài nguyên dùng chung (LLM, encoder, client mới) | `app/context.py`: thuộc tính + khởi tạo trong `build_context()` + `ctx.register(name, close=…, check=…)` → tự có trong `/health` và tự đóng khi tắt app. Tên trùng sẽ báo lỗi |
| Thêm endpoint | `app/api/routes/<tên>.py` (một `APIRouter`) + schema `app/api/schemas/` + một dòng `include_router` trong `app/api/router.py` |
| Thêm middleware | `app/middleware.py` → `install_middleware()`. Viết dạng **ASGI thuần**, không dùng `BaseHTTPMiddleware` (nó làm mất request id khi stream SSE) |
| Ghi log | `log.info("msg", extra={"data": {...}})` → một dòng JSON có `request_id` (API) hoặc `job_id` (ingest) |
| Lấy tài nguyên trong route | `ctx: AppContext = Depends(get_ctx)` |
| Test với tài nguyên giả | Fixture `ctx`, `client`, `fakes` trong `tests/conftest.py`; `fakes["redis"].fail = True` / `.hang = True` |

Hành vi đã chốt:

- API vẫn khởi động khi một dịch vụ tạm chết; `/health` trả 503 và liệt kê dịch vụ lỗi.
- `X-Request-ID` từ web/bot được giữ lại nếu an toàn (≤ 64 ký tự `[A-Za-z0-9._-]`), ngược lại tự sinh; luôn trả về trong header.
- Request `/health` thành công không được log (Docker gọi mỗi 15 s).
- Timeout: `CLIENT_TIMEOUT_SECONDS` (kết nối/đọc DB, Qdrant, Redis — asyncpg mặc định chờ 60 s) tách khỏi `HEALTH_TIMEOUT_SECONDS`.
- Swagger `/api/docs` tắt khi `ENVIRONMENT=prod`.

## 6. Thư viện Python

- Khai báo trực tiếp ở `requirements.txt` / `requirements-dev.txt`; **`constraints.txt` khoá toàn bộ phụ thuộc gián tiếp**.
- **Freeze trên Linux**, không freeze trên Windows: bản freeze Windows thiếu gói chỉ có ở Linux (`uvloop`, kéo theo bởi `uvicorn[standard]`) → image Docker cài bản không pin. Dùng `make constraints`, giữ thêm các dòng chỉ dành cho Windows (`colorama`, `pywin32`, `win32-setctime`).
- Đổi thư viện: commit `requirements*.txt` và `constraints.txt` trong cùng PR.

## 7. Test & CI

| Loại | Chạy | Ghi chú |
|---|---|---|
| Unit | `pytest` | 25 test, không cần service ngoài; mặc định bỏ qua marker `integration` |
| Integration | `make up && pytest -m integration` | Gọi `/health` với PostgreSQL/Redis/Qdrant thật |
| CI backend | ruff check + format, unit, integration (service containers) | |
| CI web / bot | prettier, `npm run build` / `tsc --noEmit` | Node 24.22.0, `npm ci` theo lockfile |

CI chạy khi mở/cập nhật PR và khi push `main`/`develop` — **push lên nhánh feature thì chưa chạy**.

## 8. Docker & triển khai

- `backend/Dockerfile` multi-stage, chạy bằng user `app` (không phải root); số worker lấy từ `WEB_CONCURRENCY` (đặt qua `API_WORKERS`).
- `.dockerignore` ở gốc repo giữ build context của Caddy ~117 KB và không gửi `.env`, `node_modules`, `.venv` vào Docker; `backend/`, `bot/`, `web/` có `.dockerignore` riêng, đều loại `.env`.
- Chạy cả stack: `docker compose --profile app up -d --build`. Riêng `api`: `docker compose --profile app up -d api`.

## 9. Sự cố đã gặp & cách xử lý

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| CI đỏ ở mọi PR (`ruff check`) | Docstring khung xương > 120 ký tự | Ngắt dòng docstring; hook pre-commit giờ bắt lỗi này trước khi push |
| `input/output error`, `read-only file system`, container tự dừng, cổng PostgreSQL/Redis timeout | **Ổ đĩa chứa disk image của Docker Desktop hết dung lượng** | Giải phóng ổ đó, khởi động lại Docker Desktop. Kiểm tra vị trí: Docker Desktop → Settings → Resources → Disk image location. Xem dung lượng: `docker system df`; dọn build cache: `docker builder prune` (kiểm tra kỹ trước khi xoá image của dự án khác) |
| `/health` báo postgres/redis `false` trên Windows | `localhost` → IPv6 | Dùng `127.0.0.1` |
| Bot nhận `DISCORD_GUILD_ID = "# server test…"` | Chú thích cuối dòng trong `.env` | Chú thích lên dòng riêng |
| VS Code báo `Cannot find type definition file for 'vite/client'` | Chưa cài `node_modules` | `npm ci` trong `web/` (hoặc `bot/`), rồi "TypeScript: Restart TS Server" |
| Lệnh `make constraints` hỏng | Ký tự `\n` bị ghi thay cho xuống dòng trong Makefile | Đã sửa; kiểm tra Makefile bằng `make -n <target>` |
| Hook pre-commit sửa hỏng `.docx` | Hook xử lý file nhị phân như văn bản | Đã loại trừ `docs/export/` và `.docx/.pptx/.pdf` |

## 10. Việc còn lại & nợ kỹ thuật

| Việc | Ai | Khi nào |
|---|---|---|
| Mở PR `fix/s1-tv1-env-config-cleanup`, thành viên khác review, merge | TV1 + 1 reviewer | S1 |
| **Sau khi merge: mọi người tạo lại `.env` từ `.env.example`** (đổi `DATABASE_URL` → `POSTGRES_HOST`, thêm biến timeout, `API_WORKERS`) | Cả nhóm | S1 |
| Bật branch protection cho `main`, `develop` (PR + 1 approval + Code Owner review + CI `backend`, `web`, `bot`) | TV1 (thiết lập GitHub) | S1 |
| Cả 4 thành viên chạy được môi trường dev, gửi kết quả `/health` | Cả nhóm | S1 |
| `migrations/env.py` còn là khung → `make migrate` chưa chạy được; Dockerfile chưa chạy migration | TV1 | S2 — Schema PostgreSQL |
| Dockerfile chưa tải sẵn model ONNX vào `/models` | TV3 | S2 — Embedding & indexing |
| Định dạng lỗi chung cho API (`core/errors.py`) | TV1 | S2 — Xử lý lỗi & logging |
| Redis/Qdrant chưa có mật khẩu (an toàn nhờ chỉ bind `127.0.0.1`) | TV1 | S5 — Deploy production |
| Image `api` ~750 MB (onnxruntime, numpy) — chấp nhận, xem lại khi thêm model | TV1 | S5 |

## 11. File chính

| File | Vai trò |
|---|---|
| `backend/core/config.py` | Cấu hình, kiểm tra an toàn production |
| `backend/core/logging.py` | Log JSON, `request_id_var`, `job_id_var` |
| `backend/core/db/session.py` | Engine/sessionmaker PostgreSQL |
| `backend/app/main.py` | `create_app()`, lifespan |
| `backend/app/context.py` | `AppContext`, `register()`, `build_context()` |
| `backend/app/middleware.py` | Request id, CORS |
| `backend/app/api/router.py`, `routes/health.py` | Router `/api/v1`, health check |
| `backend/tests/` | `conftest.py` (bản giả), `unit/`, `integration/` |
| `docker-compose.yml`, `Makefile`, `.env.example` | Hạ tầng dev, lệnh, hợp đồng cấu hình |
| `.pre-commit-config.yaml`, `.github/` | Hook, CI, CODEOWNERS, PR template |
