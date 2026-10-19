# Index Beast

[![CI](https://github.com/HoanBuCon/Index-Beast/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/HoanBuCon/Index-Beast/actions/workflows/ci.yml)

![Index Beast Banner](assets/onion_ring.jpg)

Dự án **IndexBeast** của nhóm **4 Hollows**: chatbot hỏi đáp lore **Elden Ring base game** trên Website và Discord (RAG: hybrid search + rerank + DeepSeek).

Trello: https://trello.com/b/mZEBMPGV/elden-ring

> Repo đang ở giai đoạn **khung xương**: mỗi file mới chỉ ghi nhiệm vụ và người/thẻ phụ trách, chưa có code xử lý.

**Phạm vi:** lore Elden Ring base game.

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [docs/01_TECHSTACK.md](docs/01_TECHSTACK.md) | Công nghệ & phiên bản |
| [docs/02_SRS.md](docs/02_SRS.md) | Yêu cầu (living SRS) |
| [docs/03_SPRINT_PLAN.md](docs/03_SPRINT_PLAN.md) | Kế hoạch 6 sprint |
| [docs/04_ARCHITECTURE.md](docs/04_ARCHITECTURE.md) | Kiến trúc thư mục, pipeline dữ liệu, debug, mở rộng |
| [docs/quy_uoc.md](docs/quy_uoc.md) | Quy ước nhánh Git, Conventional Commits, PR và Mentor review |

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
cp .env.example .env                      # điền DEEPSEEK_API_KEY, DISCORD_TOKEN… khi cần

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
| Chạy API (auto-reload) | `make api` | `cd backend && uvicorn --factory app.main:create_app --reload --no-access-log` → http://localhost:8000/api/docs |
| Chạy web | | `cd web && npm run dev` → http://localhost:5173 |
| Migration DB | `make migrate` | `cd backend && alembic upgrade head` |
| Test backend | `make test` | `cd backend && pytest` (thêm `-m integration` khi đã `make up`) |
| Lint toàn repo | `make lint` | `pre-commit run --all-files` |

Cổng chỉ mở trên `127.0.0.1`: PostgreSQL `5432`, Qdrant `6333` (dashboard: http://localhost:6333/dashboard), Redis `6379`.

### Thêm / nâng cấp thư viện Python

Sửa `backend/requirements*.txt`, cài vào một venv **mới**, rồi khoá lại toàn bộ phụ thuộc:

```bash
pip install -r requirements-dev.txt
pip freeze > constraints.txt      # giữ 2 dòng chú thích ở đầu file
```

Commit cả `requirements*.txt` và `constraints.txt` trong cùng PR.

### Lỗi hay gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `port is already allocated` | Máy đang chạy PostgreSQL/Redis khác: tắt dịch vụ đó hoặc đổi cổng bên trái trong `docker-compose.yml` |
| `read-only file system` / `input/output error` khi pull image | Docker Desktop bị lỗi đĩa ảo: Quit Docker Desktop rồi mở lại (hoặc Troubleshoot → Restart) |
| Muốn xoá sạch dữ liệu dev | `docker compose down -v` (xoá volume, **mất toàn bộ dữ liệu**) |
| API báo `postgres: false` / timeout trên Windows | Dùng `127.0.0.1` thay vì `localhost` trong `.env` (Docker chỉ mở cổng IPv4) |
| VS Code báo thiếu type (`vite/client`, `node`) | Chạy `npm ci` trong `web/` hoặc `bot/`, rồi "TypeScript: Restart TS Server" |
