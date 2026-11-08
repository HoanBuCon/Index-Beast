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

# Bind mount phải tồn tại. Container (uid 10001) chỉ ĐỌC model và dữ liệu nên chỉ cần quyền đọc cho "other";
# không đổi chủ thư mục để user deploy vẫn rsync được dữ liệu mới.
mkdir -p backend/data backend/models
find backend/data backend/models -type d ! -perm -o+rx -exec chmod o+rx {} +
find backend/data backend/models -type f ! -perm -o+r -exec chmod o+r {} +

echo "==> Build image"
"${COMPOSE[@]}" build

echo "==> Hạ tầng (PostgreSQL, Qdrant, Redis)"
"${COMPOSE[@]}" up -d --wait postgres qdrant redis

echo "==> Migration"
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
