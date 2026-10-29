# Index Beast

[![CI](https://github.com/HoanBuCon/Index-Beast/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/HoanBuCon/Index-Beast/actions/workflows/ci.yml)

![Index Beast Banner](assets/onion_ring.jpg)

Dự án **IndexBeast** của nhóm **4 Hollows**: trợ lý hỏi đáp **Elden Ring và nội dung liên quan trong corpus**, gồm DLC, trên Website và Discord (RAG: hybrid search + optional rerank + DeepSeek). Hỗ trợ lore, gameplay, quest, trang bị và gợi ý build khi có bằng chứng.

Trello: https://trello.com/b/mZEBMPGV/elden-ring

> Repo đang ở giai đoạn nền tảng: API health, cấu hình và adapter DeepSeek đã có triển khai.
> Pipeline dữ liệu và RAG đang được phát triển theo kế hoạch sprint.

Chat hiện có ba mode server: `mock` (mặc định), `llm_only` và `rag`. Xem
[hướng dẫn LangChain + DeepSeek và tích hợp corpus thử nghiệm](backend/app/rag/README.md).
`llm_only` dùng được khi dữ liệu chưa sẵn sàng. Xem [báo cáo kiểm thử offline và tích hợp thật](docs/testing/2026-10-29_rag-integration-report.md) để biết kết quả, lỗi đã phát hiện và cấu hình máy thử.

**Phạm vi hiện tại:** Elden Ring có nguồn, gồm lore, gameplay và tư vấn build định tính; giữ rõ game/release và mức độ chưa xác minh. Corpus thử nghiệm dùng policy `pilot`, mặc định chọn chunk tiếng Anh. Dữ liệu gameplay còn thiếu bảng stat/acquisition/combat đã bị lọc; xem [audit khả năng thực tế và cách thử](docs/testing/2026-10-29_elden-ring-assistant-capabilities.md). Các tài liệu SRS/ADR cũ cần nhóm đồng bộ riêng.

## 4 con Hollows

| Mã | Thành viên | Vai trò |
|---|---|---|
| TV1 | Hoanbucon | Tech Lead · Backend & DevOps |
| TV2 | UncleThing | Data Engineer |
| TV3 | MinhMuc | AI / RAG Engineer |
| TV4 | QuyVuiVe | Frontend & Discord Bot |

## Tài liệu

Notebook baseline: [E5 ONNX + BM25 + Qdrant RRF](backend/notebooks/01_rag_baseline_e5_bm25.ipynb).
Xem [hướng dẫn tự chạy](backend/notebooks/README.md). Notebook chưa được thực thi khi bàn giao.

| Tài liệu | Nội dung |
|---|---|
| [docs/01_TECHSTACK.md](docs/01_TECHSTACK.md) | Công nghệ & phiên bản |
| [docs/02_SRS.md](docs/02_SRS.md) | Yêu cầu (living SRS) |
| [docs/03_SPRINT_PLAN.md](docs/03_SPRINT_PLAN.md) | Kế hoạch 6 sprint |
| [docs/04_ARCHITECTURE.md](docs/04_ARCHITECTURE.md) | Kiến trúc thư mục, pipeline dữ liệu, debug, mở rộng |
| [docs/quy_uoc.md](docs/quy_uoc.md) | Quy ước nhánh Git, Conventional Commits, PR và Mentor review |
| [docs/handover/2026-10-19_s1-tv3_deepseek-llm.md](docs/handover/2026-10-19_s1-tv3_deepseek-llm.md) | Cấu hình, sử dụng và kiểm tra DeepSeek LLM |
| [backend/app/rag/README.md](backend/app/rag/README.md) | LangChain, ba mode chat, prompt, hướng dẫn tự chạy và nối artifact RAG |

## Cấu trúc

| Thư mục | Vai trò | Phụ trách chính |
|---|---|---|
| `backend/core/` | Dùng chung: config, DB, Qdrant, encoder, xử lý văn bản | TV1, TV2, TV3 |
| `backend/app/` | API online (FastAPI) + lõi RAG | TV1, TV3 |
| `backend/ingest/` | Pipeline offline: crawl → filter → transform → chunk → index | TV2, TV3 |
| `backend/eval/` | Đánh giá chất lượng | TV3 |
| `web/` | Website React | TV4 |
| `bot/` | Discord bot | TV4 |
| `infra/`, `scripts/`, `docker-compose.yml` | Triển khai | TV1 |

## Chạy local

Chạy nhanh API + web + hạ tầng: `make dev`. Kiểm tra: `make health`; unit offline: `make test-unit`.
Xem [hướng dẫn test và cấu hình DeepSeek](docs/testing/indexbeast-local-guide.md).

### Cần cài

| Công cụ | Phiên bản | Ghi chú |
|---|---|---|
| Git | bất kỳ bản mới | Windows: dùng Git Bash cho các lệnh bên dưới |
| Python | 3.11.9 | |
| Node.js | 24.22.0 (LTS) | Bot chạy thẳng file `.ts` nên cần Node ≥ 24 |
| Docker Desktop / Docker Engine | có Compose v2 | Chạy PostgreSQL, Qdrant, Redis |
| make (tuỳ chọn) | | macOS/Linux có sẵn; Windows: `winget install ezwinports.make` |

### Lần đầu

```bash
git clone https://github.com/HoanBuCon/Index-Beast.git && cd Index-Beast
git switch develop
cp .env.example .env                      # điền giá trị thật khi cần (xem mục Cấu hình)

# Backend
cd backend
python -m venv .venv
source .venv/Scripts/activate             # macOS/Linux: source .venv/bin/activate · PowerShell: .venv\Scripts\Activate.ps1
python -m pip install pip==26.2.1
pip install -r requirements-dev.txt -c constraints.txt
cd ..

# Web và bot
(cd web && npm ci) && (cd bot && npm ci)

# Hook kiểm tra trước khi commit
pre-commit install
```

### Hằng ngày

| Việc | Với make | Lệnh gốc |
|---|---|---|
| Bật PostgreSQL, Qdrant, Redis | `make up` | `docker compose up -d --wait postgres qdrant redis` |
| Xem trạng thái | `make ps` | `docker compose ps` |
| Xem log container (mặc định **không** ghi log xuống đĩa) | `make debug-up` rồi `make logs` | `DOCKER_LOG_DRIVER=local docker compose up -d --force-recreate` rồi `docker compose logs -f` |
| Tắt (giữ dữ liệu) | `make down` | `docker compose down` |
| Chạy API (auto-reload) | `make api` | `cd backend && uvicorn --factory app.main:create_app --reload --host 127.0.0.1 --port 18000 --no-access-log` → http://127.0.0.1:18000/api/docs |
| Chạy web | | `cd web && npm run dev` → http://localhost:15173 (proxy `/api` sang API ở cổng `API_PORT`) |
| Migration DB | `make migrate` | `cd backend && alembic upgrade head` |
| Test backend | `make test` | `cd backend && pytest` (thêm `-m integration` khi đã `make up`) |
| Lint toàn repo | `make lint` | `pre-commit run --all-files` |

Cổng khi dev — tất cả chỉ mở trên máy mình (`127.0.0.1`):

| Dịch vụ | Cổng | Biến trong `.env` |
|---|---|---|
| API (FastAPI) | `18000` | `API_PORT` — `make api`, proxy của web và bot dev cùng đọc biến này |
| Web (Vite) | `15173` | `WEB_PORT` (nhớ sửa cả `CORS_ORIGINS`, `WEB_URL`) |
| PostgreSQL / Qdrant / Redis | `15432` / `16333` / `16379` | `POSTGRES_PORT` / `QDRANT_PORT` / `REDIS_PORT` (Qdrant dashboard: http://localhost:16333/dashboard) |

Dự án **không dùng cổng mặc định** của công cụ: cổng dự án = cổng gốc + 10000 ([`docs/quy_uoc.md`](docs/quy_uoc.md) → "Quy ước cổng"). Mọi cổng đổi trong `.env`, không sửa code.
Trong Docker, container `api` nghe `18000` (Caddy và bot gọi `api:18000`); PostgreSQL/Qdrant/Redis giữ cổng gốc **bên trong** mạng Docker.

> ⚠️ **Không chạy API với `--host 0.0.0.0` khi dev.** Mặc định uvicorn chỉ nghe `127.0.0.1` (chỉ máy mình gọi được).
> `0.0.0.0` mở API cho mọi máy cùng mạng Wi-Fi/LAN — kể cả endpoint dev `/api/v1/dev/llm/test` gọi DeepSeek
> bằng key của bạn (tốn credit). Chỉ dùng khi thật sự cần thử từ thiết bị khác, và tắt ngay sau đó.

### Thử Discord bot (Sprint 1)

Điền `DISCORD_TOKEN`, `DISCORD_CLIENT_ID` (Application ID), `DISCORD_GUILD_ID` (Server ID) trong `.env`
ở gốc repo; mời bot vào server đó với scopes `bot`, `applications.commands` và quyền xem kênh, gửi tin nhắn,
nhúng liên kết. Nếu token bị lộ, đặt lại trong Developer Portal trước khi chạy.

```bash
cd bot
npm ci
npm run deploy-commands
npm run dev
```

Trong server thử nghiệm, chọn lệnh `/ping` của bot → nhận `Pong!`. S1 không cần API hay Docker để thử `/ping`.
Giữ terminal mở để bot online; nhấn Ctrl+C để dừng. PowerShell chặn `npm.ps1` thì dùng `npm.cmd` thay `npm`.
Đăng ký lại lệnh khi thay đổi định nghĩa lệnh, không cần đăng ký mỗi lần khởi động bot.
Dev đăng ký vào `DISCORD_GUILD_ID`; `ENVIRONMENT=prod` đăng ký global. Lệnh deploy thay thế toàn bộ danh sách
slash command của ứng dụng trong phạm vi đó bằng registry hiện tại (S1 chỉ có `/ping`).
`npm start` dùng biến môi trường đã được nạp (ví dụ Docker Compose); chạy local dùng `npm run dev`.

### Cấu hình (`.env`)

Chỉ có **một** file `.env` ở gốc repo (sao chép từ `.env.example`); backend, bot và docker compose cùng đọc file này.

| Thành phần | Đọc cấu hình thế nào |
|---|---|
| Backend | `core/config.py` (pydantic-settings) đọc `<gốc repo>/.env` theo đường dẫn tuyệt đối; biến môi trường thật luôn được ưu tiên |
| Bot (dev) | `node --env-file=../.env`; `BOT_API_URL` để trống thì gọi `http://127.0.0.1:<API_PORT>` |
| Docker Compose | Lấy `${...}` từ `.env`, rồi truyền cho mỗi container **chỉ** các biến liệt kê trong `environment:` của nó (bot không biết mật khẩu DB) |
| Test | Không đọc `.env` (`Settings(_env_file=None)`) để chạy giống nhau trên mọi máy |
| CI | `env:` trong workflow; secret thật đặt ở GitHub Secrets |
| Production | `.env` trên VPS (`chmod 600`), `ENVIRONMENT=prod` — API từ chối khởi động nếu còn giá trị `change-me` |

Quy ước khi sửa `.env.example`: chú thích đặt trên **dòng riêng** (docker compose hiểu `KEY=  # chú thích` thành giá trị),
dev dùng `127.0.0.1` thay cho `localhost`.

**Thêm một biến mới:**

1. Thêm trường vào `backend/core/config.py` (đúng nhóm) hoặc `bot/src/config.ts`.
2. Thêm dòng mẫu kèm chú thích vào `.env.example` — test `tests/unit/test_env_example.py` sẽ báo nếu quên.
3. Nếu container cần biến đó: thêm vào `environment:` của service tương ứng trong `docker-compose.yml`.
4. Ghi trong mô tả PR để mọi người cập nhật `.env` của mình.

### Thêm / nâng cấp thư viện Python

Sửa `backend/requirements*.txt`, rồi khoá lại toàn bộ phụ thuộc. Phải freeze **trên Linux** (image Docker và CI chạy Linux;
freeze trên Windows sẽ thiếu gói chỉ có ở Linux như `uvloop`):

```bash
make constraints > /tmp/linux.txt   # pip freeze trong container python:3.11.9-slim-bookworm
```

Thay nội dung `backend/constraints.txt` bằng kết quả đó, giữ phần chú thích đầu file và các dòng chỉ dành cho Windows
(`colorama`, `pywin32`, `win32-setctime`). Sau đó cài lại venv để kiểm tra trên máy mình.

Commit cả `requirements*.txt` và `constraints.txt` trong cùng PR.

### Lỗi hay gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `port is already allocated` | Cổng đã có chương trình khác dùng: đổi `POSTGRES_PORT` / `QDRANT_PORT` / `REDIS_PORT` trong `.env` |
| `make api` báo cổng đã dùng (`[Errno 10048]` / `address already in use`) | Đặt `API_PORT` khác trong `.env` (vd. `18001`), không sửa Makefile hay code |
| Web báo `502` / `http proxy error … ECONNREFUSED` khi gọi `/api` | API chưa chạy, hoặc chạy ở cổng khác `API_PORT`. Khởi động lại `npm run dev` sau khi đổi `.env` |
| `read-only file system` / `input/output error` khi pull image | Docker Desktop bị lỗi đĩa ảo: Quit Docker Desktop rồi mở lại (hoặc Troubleshoot → Restart) |
| Muốn xoá sạch dữ liệu dev | `docker compose down -v` (xoá volume, **mất toàn bộ dữ liệu**) |
| API báo `postgres: false` / timeout trên Windows | Dùng `127.0.0.1` thay vì `localhost` trong `.env` (Docker chỉ mở cổng IPv4) |
| Sau khi pull, API/web không kết nối được dịch vụ | `.env` còn cổng cũ (5432, 6333, 6379, 8001…): tạo lại từ `.env.example` rồi `docker compose up -d --force-recreate postgres qdrant redis` |
| VS Code báo thiếu type (`vite/client`, `node`) | Chạy `npm ci` trong `web/` hoặc `bot/`, rồi "TypeScript: Restart TS Server" |
