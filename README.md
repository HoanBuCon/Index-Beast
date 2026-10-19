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

## Việc cần làm ở Sprint 1 để chạy được

1. Copy `.env.example` → `.env` và điền giá trị.
2. Backend: tạo venv, cài thư viện, rồi khoá phiên bản phụ thuộc gián tiếp:
   ```bash
   cd backend && python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
   python -m pip install pip==26.2.1 && pip install -r requirements-dev.txt
   pip freeze > constraints.txt
   ```
3. Web, bot: chạy `npm install` để sinh `package-lock.json`.
4. Hạ tầng dev: `docker compose up -d postgres qdrant redis`.
