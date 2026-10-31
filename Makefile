# Lệnh dev thường dùng. Windows: chạy trong Git Bash/WSL (cài make: `winget install ezwinports.make`)
# hoặc gõ thẳng lệnh tương ứng trong README (mục "Chạy local").
# API và test-unit tự dùng backend/.venv khi có; không cần activate.

COMPOSE := docker compose
INFRA   := postgres qdrant redis
# TV4: npm.cmd tránh npm.ps1 trên Windows; Linux/macOS dùng npm, có thể ghi đè BOT_NPM.
BOT_NPM ?= $(if $(filter Windows_NT,$(OS)),npm.cmd,npm)
PYTHON ?= $(if $(wildcard backend/.venv/Scripts/python.exe),$(CURDIR)/backend/.venv/Scripts/python.exe,$(if $(wildcard backend/.venv/bin/python),$(CURDIR)/backend/.venv/bin/python,python))
# Cổng API dev: lấy API_PORT từ .env (chỉ đọc đúng dòng đó), mặc định 18000 — không dùng cổng mặc định 8000
# của uvicorn (docs/quy_uoc.md → "Quy ước cổng"). Ghi đè: `make api API_PORT=18001`
API_PORT ?= $(or $(shell "$(PYTHON)" -c "from dotenv import dotenv_values; print(dotenv_values('.env').get('API_PORT') or '')"),18000)
# Đọc host chia sẻ web từ .env; override: make web WEB_HOST=<IP-LAN-hoac-VPN>.
WEB_HOST ?= $(or $(shell "$(PYTHON)" -c "from dotenv import dotenv_values; print(dotenv_values('.env').get('WEB_HOST') or '')"),127.0.0.1)

.PHONY: help up debug-up down logs ps migrate openapi test test-unit lint format api web dev health constraints
.PHONY: bot bot-deploy bot-check bot-dev

help:            ## Liệt kê lệnh
	@grep -E '^[a-z][a-z-]*:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ —/'

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

test-unit:       ## Chỉ test unit offline, không gọi LLM hoặc index corpus thật
	cd backend && "$(PYTHON)" -X utf8 -m pytest -c pyproject.toml tests/unit -q

lint:            ## Kiểm tra lint/format cho backend, web, bot
	cd backend && ruff check . && ruff format --check .
	cd web && npm run format:check && npm run typecheck
	cd bot && npm run format:check && npm run typecheck

format:          ## Tự format code
	cd backend && ruff check --fix . && ruff format .
	cd web && npm run format
	cd bot && npm run format

api:             ## Chạy API local (auto-reload) tại http://127.0.0.1:$(API_PORT)
	cd backend && "$(PYTHON)" -X utf8 -m uvicorn --factory app.main:create_app --reload --host 127.0.0.1 --port $(API_PORT) --no-access-log

# Frontend TV4: Vite đọc WEB_PORT và proxy API_PORT từ .env gốc, không ghi cứng cổng ở đây.
web:             ## Chạy Vite theo WEB_HOST trong .env; cổng và proxy do Vite đọc
	cd web && npm run dev -- --host "$(WEB_HOST)"

# Bot TV4: chỉ chạy client Discord; backend dùng make api ở terminal riêng.
bot:             ## Chạy bot Discord dev, đọc .env gốc và tự khởi động lại khi sửa code
	cd bot && $(BOT_NPM) run dev

bot-deploy:      ## Đăng ký slash commands global; chạy khi thêm hoặc sửa định nghĩa lệnh
	cd bot && $(BOT_NPM) run deploy-commands

bot-check:       ## TypeScript + test giả lập + Prettier của bot; không cần Discord/backend
	cd bot && $(BOT_NPM) run typecheck && $(BOT_NPM) test && $(BOT_NPM) run format:check

# TV4: một lệnh cho bot S2; biến chỉ truyền cho lệnh này/các tiến trình con, không sửa .env.
bot-dev: export CHAT_MODE := mock
bot-dev: export BOT_API_URL = http://127.0.0.1:$(API_PORT)
bot-dev: up      ## Bật hạ tầng, API mock và bot cùng terminal; cần Docker Desktop đang chạy
	$(MAKE) --no-print-directory -j2 api bot

dev: up          ## Bật hạ tầng, API và web; Ctrl+C dừng API/web, giữ dữ liệu Docker
	$(MAKE) --no-print-directory -j2 api web

health:          ## Đọc health API đang chạy; không gọi LLM hoặc load embedding
	@"$(PYTHON)" -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:$(API_PORT)/api/v1/health', timeout=10).read().decode())"

constraints:     ## In pip freeze trên Linux (Docker) để cập nhật backend/constraints.txt
	docker run --rm -v "$(CURDIR)/backend:/src:ro" python:3.11.9-slim-bookworm sh -c "\
	  pip install -q --root-user-action=ignore pip==26.2.1 && \
	  pip install -q --root-user-action=ignore -r /src/requirements-dev.txt && \
	  pip freeze"
