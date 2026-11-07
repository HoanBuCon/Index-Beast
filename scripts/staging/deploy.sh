#!/usr/bin/env bash
# Deploy staging trên VPS: lấy mã theo nhánh/tag, build, migration, khởi động, chờ healthy.
# Dùng:  scripts/staging/deploy.sh [nhánh-hoặc-tag]     (mặc định develop)
# Rollback: chạy lại với tag/commit cũ. Dữ liệu trong volume không bị xóa.
# Phụ trách: TV1 · [S3] Staging trên VPS
set -euo pipefail
cd "$(dirname "$0")/../.."

REF=${1:-develop}
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.staging.yml --profile app)

[ -f .env ] || { echo "Thiếu .env. Chạy: cp .env.staging.example .env, rồi điền (xem docs/staging.md)."; exit 1; }
if grep -qE '^[A-Z_]+=change-me$' .env; then
  echo "Còn giá trị mẫu change-me trong .env:"
  grep -E '^[A-Z_]+=change-me$' .env | cut -d= -f1
  exit 1
fi

echo "==> Mã nguồn: $REF"
git fetch --tags origin
git checkout "$REF"
if git show-ref --verify --quiet "refs/remotes/origin/$REF"; then git merge --ff-only "origin/$REF"; fi
git log -1 --format='    %h %s'

# Bind mount phải tồn tại và thuộc uid 10001 (user app trong image) để nạp model và ghi dữ liệu
mkdir -p backend/data backend/models

echo "==> Build image"
"${COMPOSE[@]}" build

echo "==> Hạ tầng (PostgreSQL, Qdrant, Redis)"
"${COMPOSE[@]}" up -d --wait postgres qdrant redis

echo "==> Quyền thư mục và migration"
"${COMPOSE[@]}" run --rm --no-deps --user root api chown -R 10001:10001 /app/data /app/models
"${COMPOSE[@]}" run --rm api alembic upgrade head

SCALE=()
if ! grep -qE '^DISCORD_TOKEN=.+' .env; then
  echo "    (không có DISCORD_TOKEN: bỏ qua bot)"
  SCALE=(--scale bot=0)
fi

echo "==> Khởi động toàn bộ"
"${COMPOSE[@]}" up -d --wait "${SCALE[@]}"
"${COMPOSE[@]}" ps
echo "Xong. Kiểm tra: curl -sk -u \"\$STAGING_USER:<mật khẩu>\" https://\$STAGING_HOST/api/v1/health"
