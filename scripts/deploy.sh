#!/usr/bin/env bash
# Deploy production trên VPS: lấy mã → (backup trước khi đổi) → docker compose up -d --build → chờ api healthy.
# Dùng:
#   scripts/deploy.sh              cập nhật nhánh hiện tại: git pull --ff-only (VPS nên đứng ở nhánh main)
#   scripts/deploy.sh v1.0.1       checkout tag/commit/nhánh đó rồi deploy (rollback = deploy lại tag cũ)
# Migration: api tự chạy `alembic upgrade head` khi khởi động (backend/Dockerfile).
# Biến tùy chọn: SKIP_PRE_BACKUP=1 bỏ qua backup trước deploy; HEALTH_TIMEOUT=300 (giây) chờ api healthy;
#   ALLOW_HTTPS_PENDING=1 chỉ cho lần deploy ĐẦU (DNS chưa trỏ / Caddy đang xin chứng chỉ): kiểm tra HTTPS lỗi thì cảnh báo và thoát 0.
#   Mặc định kiểm tra HTTPS lỗi => thoát khác 0 (deploy chưa xong, chưa tới được người dùng).
# Hướng dẫn đầy đủ và rollback: docs/production.md. Phụ trách: TV1 · [S5] Script deploy đơn giản
set -euo pipefail
cd "$(dirname "$0")/.."

REF=${1:-}
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app)
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-300}

die() { echo "LỖI: $*" >&2; exit 1; }

# --- .env: có, quyền 600, đủ biến bắt buộc, không còn giá trị mẫu (không in giá trị, chỉ tên biến) ---
[ -f .env ] || die "Thiếu .env. Chạy: cp .env.prod.example .env && chmod 600 .env, rồi điền (docs/production.md)."
perm=$(stat -c '%a' .env)
[ "$perm" = 600 ] || die ".env đang có quyền $perm, phải là 600. Chạy: chmod 600 .env"
if grep -qE '^[A-Za-z_]+=["'"'"']?change-me["'"'"']?[[:space:]]*$' .env; then
  echo "Còn giá trị mẫu change-me trong .env:" >&2
  grep -E '^[A-Za-z_]+=["'"'"']?change-me["'"'"']?[[:space:]]*$' .env | cut -d= -f1 | sed 's/^/  /' >&2
  exit 1
fi
missing=()
for var in DOMAIN POSTGRES_PASSWORD API_SERVICE_TOKEN ADMIN_TOKEN DEEPSEEK_API_KEY \
           DISCORD_CLIENT_ID DISCORD_CLIENT_SECRET AUTH_SECRET AUTH_ADMIN_DISCORD_IDS; do
  grep -qE "^${var}=.+" .env || missing+=("$var")
done
[ ${#missing[@]} -eq 0 ] || die "Thiếu hoặc để trống trong .env: ${missing[*]}"

# --- Mã nguồn ---
[ -z "$(git status --porcelain)" ] || { git status --short >&2; die "Working tree có thay đổi chưa commit. Dọn sạch trước khi deploy (không sửa tay trên VPS)."; }
PREV=$(git rev-parse --short HEAD)
PREV_REF=$(git symbolic-ref -q --short HEAD || git rev-parse HEAD)   # nhánh nếu đang ở nhánh, không thì commit
git fetch --tags origin
if [ -n "$REF" ]; then
  echo "==> Mã nguồn: $REF"
  git checkout "$REF"
  # Bản cũ hơn bản production đầu tiên không có overlay/Caddyfile prod: deploy sẽ hỏng giữa chừng, nên hoàn tác ngay
  for f in docker-compose.prod.yml infra/Caddyfile.prod; do
    if [ ! -f "$f" ]; then
      git checkout "$PREV_REF"
      die "$REF không có $f (cũ hơn bản production đầu tiên). Đã quay về $PREV_REF. Chỉ rollback về tag production đầu tiên hoặc mới hơn."
    fi
  done
  # Nhánh thì kéo về bản mới nhất; tag/commit thì giữ nguyên (HEAD tách rời)
  if git show-ref --verify --quiet "refs/remotes/origin/$REF"; then git merge --ff-only "origin/$REF"; fi
else
  git symbolic-ref -q HEAD >/dev/null || die "Đang ở HEAD tách rời (sau rollback?). Chạy: scripts/deploy.sh main"
  echo "==> Mã nguồn: git pull --ff-only ($(git branch --show-current))"
  git pull --ff-only
fi
NEW=$(git rev-parse --short HEAD)
git log -1 --format='    %h %s'

# --- Bind mount phải tồn tại. Container api (uid 10001, backend/Dockerfile) chỉ ĐỌC model và dữ liệu ---
# Chỉ cấp quyền đọc cho đúng uid/gid đó, KHÔNG mở cho "other" (dữ liệu không được world-readable). Các thư mục api mount:
# backend/data (compose gốc) và backend/models (overlay prod). Ưu tiên ACL (user deploy không cần là root hay thuộc nhóm 10001);
# không có setfacl thì dùng chgrp (cần root hoặc user deploy thuộc nhóm 10001). Quyền "other" đã có sẵn thì không bị gỡ ở đây.
APP_ID=10001
mkdir -p backend/data backend/models
if command -v setfacl >/dev/null 2>&1; then
  # rX: đọc mọi file, vào thư mục; -d: file mới tạo sau này (rsync, ingest) cũng đọc được
  setfacl -R -m "u:${APP_ID}:rX" backend/data backend/models \
    && setfacl -R -d -m "u:${APP_ID}:rX" backend/data backend/models \
    || die "setfacl lỗi trên backend/data hoặc backend/models (hệ thống file có hỗ trợ ACL không?)."
else
  chgrp -R "$APP_ID" backend/data backend/models 2>/dev/null \
    || die "Không chgrp được sang nhóm ${APP_ID}. Cài ACL (sudo apt install acl) rồi chạy lại, hoặc: sudo chgrp -R ${APP_ID} backend/data backend/models"
  chmod -R g+rX backend/data backend/models
fi

# --- Backup trước khi đổi: migration chỉ đi tới, quay lại cần bản này (bỏ qua ở lần deploy đầu, khi chưa có PostgreSQL) ---
if [ "${SKIP_PRE_BACKUP:-0}" != 1 ] && [ -n "$("${COMPOSE[@]}" ps -q --status running postgres 2>/dev/null)" ]; then
  echo "==> Backup PostgreSQL trước deploy"
  scripts/backup.sh daily
fi

SCALE=()
if ! grep -qE '^DISCORD_TOKEN=.+' .env; then
  echo "    (không có DISCORD_TOKEN: bỏ qua bot)"
  SCALE=(--scale bot=0)
fi

echo "==> Build và khởi động"
"${COMPOSE[@]}" up -d --build "${SCALE[@]}"

echo "==> Chờ api healthy (tối đa ${HEALTH_TIMEOUT}s; lần đầu chạy migration và nạp model nên lâu hơn)"
api_id=$("${COMPOSE[@]}" ps -q api)
[ -n "$api_id" ] || die "Không tìm thấy container api."
deadline=$((SECONDS + HEALTH_TIMEOUT))
status=starting
while [ "$SECONDS" -lt "$deadline" ]; do
  status=$(docker inspect --format '{{if .State.Running}}{{.State.Health.Status}}{{else}}stopped{{end}}' "$api_id")
  [ "$status" = healthy ] && break
  sleep 5
done
"${COMPOSE[@]}" ps
if [ "$status" != healthy ]; then
  echo "api chưa healthy (trạng thái: $status). Xem log: ${COMPOSE[*]} logs --tail 100 api" >&2
  echo "Rollback: scripts/deploy.sh $PREV" >&2
  exit 1
fi

DOMAIN=$(grep -E '^DOMAIN=' .env | tail -n1 | cut -d= -f2- | tr -d "\"'")
echo "==> Kiểm tra qua Caddy (HTTPS)"
if curl -fsS --max-time 15 "https://${DOMAIN}/api/v1/health" >/dev/null; then
  echo "    OK: https://${DOMAIN}/api/v1/health"
else
  echo "    CHƯA qua được HTTPS: DNS chưa trỏ về VPS hoặc Caddy đang xin chứng chỉ (xem: ${COMPOSE[*]} logs caddy)." >&2
  if [ "${ALLOW_HTTPS_PENDING:-0}" = 1 ]; then
    echo "    CẢNH BÁO: ALLOW_HTTPS_PENDING=1 nên bỏ qua. Deploy CHƯA được xác nhận từ ngoài; kiểm tra lại HTTPS trước khi báo xong." >&2
  else
    echo "Rollback: scripts/deploy.sh $PREV. Lần deploy đầu (chứng chỉ chưa có): chạy lại với ALLOW_HTTPS_PENDING=1 scripts/deploy.sh" >&2
    exit 1
  fi
fi

echo
echo "Xong: $PREV -> $NEW"
echo "Rollback về bản trước:  scripts/deploy.sh $PREV    (hoặc tag đã phát hành, vd. scripts/deploy.sh v1.0.0)"
echo "Lưu ý: rollback KHÔNG hoàn tác migration. Nếu bản mới có migration, hoàn tác bằng backup (scripts/restore.sh) hoặc alembic downgrade (docs/production.md)."
