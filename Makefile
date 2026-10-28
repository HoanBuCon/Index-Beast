# Lệnh dev thường dùng. Windows: chạy trong Git Bash/WSL (cài make: `winget install ezwinports.make`)
# hoặc gõ thẳng lệnh tương ứng trong README (mục "Chạy local").
# Các lệnh backend giả định venv đã được kích hoạt.

COMPOSE := docker compose
INFRA   := postgres qdrant redis
# Cổng API dev: lấy API_PORT từ .env (chỉ đọc đúng dòng đó), mặc định 18000 — không dùng cổng mặc định 8000
# của uvicorn (docs/quy_uoc.md → "Quy ước cổng"). Ghi đè: `make api API_PORT=18001`
API_PORT ?= $(or $(shell sed -n 's/^API_PORT=\([0-9]*\).*/\1/p' .env 2>/dev/null),18000)

.PHONY: help up debug-up down logs ps migrate openapi test lint format api web constraints

help:            ## Liệt kê lệnh
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ —/'

up:              ## Bật PostgreSQL, Qdrant, Redis và chờ healthy
	$(COMPOSE) up -d --wait $(INFRA)

down:            ## Tắt hạ tầng (giữ dữ liệu trong volume)
	$(COMPOSE) down

logs:            ## Xem log (chỉ có khi chạy với DOCKER_LOG_DRIVER=local)
	$(COMPOSE) logs -f --tail=100

debug-up:        ## Bật hạ tầng KÈM ghi log (driver local, xoay vòng 5×20MB)
	DOCKER_LOG_DRIVER=local $(COMPOSE) up -d --wait --force-recreate $(INFRA)

ps:              ## Trạng thái container
	$(COMPOSE) ps

migrate:         ## Chạy migration database
	cd backend && alembic upgrade head

openapi:         ## Xuất hợp đồng API v1 ra docs/api/openapi.json
	cd backend && python -m scripts.export_openapi

test:            ## Chạy test backend
	cd backend && pytest

lint:            ## Kiểm tra lint/format cho backend, web, bot
	cd backend && ruff check . && ruff format --check .
	cd web && npm run format:check && npm run typecheck
	cd bot && npm run format:check && npm run typecheck

format:          ## Tự format code
	cd backend && ruff check --fix . && ruff format .
	cd web && npm run format
	cd bot && npm run format

api:             ## Chạy API local (auto-reload) tại http://127.0.0.1:$(API_PORT)
	cd backend && uvicorn --factory app.main:create_app --reload --host 127.0.0.1 --port $(API_PORT) --no-access-log

# Frontend TV4: Vite đọc WEB_PORT và proxy API_PORT từ .env gốc, không ghi cứng cổng ở đây.
web:             ## Chạy frontend Vite (cần npm ci trong web ở lần đầu)
	cd web && npm run dev

constraints:     ## In pip freeze trên Linux (Docker) để cập nhật backend/constraints.txt
	docker run --rm -v "$(CURDIR)/backend:/src:ro" python:3.11.9-slim-bookworm sh -c "\
	  pip install -q --root-user-action=ignore pip==26.2.1 && \
	  pip install -q --root-user-action=ignore -r /src/requirements-dev.txt && \
	  pip freeze"
