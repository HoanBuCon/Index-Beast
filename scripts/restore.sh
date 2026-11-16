#!/usr/bin/env bash
# Khôi phục production từ bản backup của scripts/backup.sh. GHI ĐÈ dữ liệu hiện tại.
# Dùng:  scripts/restore.sh pg <file.dump>                  khôi phục PostgreSQL (dừng api/bot trong lúc khôi phục)
#        scripts/restore.sh qdrant <file.snapshot>          khôi phục collection RAG (tên collection lấy từ tên file)
#        scripts/restore.sh list                            liệt kê backup hiện có
# Thêm --yes (đứng cuối) để bỏ qua câu hỏi xác nhận. Đường dẫn file phải nằm trong BACKUP_DIR (mặc định $HOME/indexbeast-backups).
# Thử khôi phục an toàn: docs/production.md → "Thử khôi phục". Phụ trách: TV1 · [S5] Backup & monitoring
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO"

BACKUP_DIR=${BACKUP_DIR:-$HOME/indexbeast-backups}
BACKUP_DIR=${BACKUP_DIR%/}
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app)

die() { echo "LỖI: $*" >&2; exit 1; }

ASSUME_YES=0
args=()
for a in "$@"; do if [ "$a" = --yes ]; then ASSUME_YES=1; else args+=("$a"); fi; done
set -- "${args[@]:-}"

MODE=${1:-}
if [ "$MODE" = list ]; then ls -lh "$BACKUP_DIR"; exit 0; fi
[ "$MODE" = pg ] || [ "$MODE" = qdrant ] || die "Cách dùng: restore.sh pg|qdrant <file> [--yes]  |  restore.sh list"
FILE=${2:-}
[ -n "$FILE" ] || die "Thiếu đường dẫn file backup"
# Chỉ nhận file thật nằm trong BACKUP_DIR (đã giải symlink): không khôi phục từ đường dẫn tùy ý
FILE=$(realpath -e -- "$FILE") || die "Không thấy file: $2"
ROOT=$(realpath -e -- "$BACKUP_DIR") || die "Không thấy BACKUP_DIR: $BACKUP_DIR"
case "$FILE" in "$ROOT"/*) ;; *) die "File phải nằm trong $ROOT" ;; esac
[ -s "$FILE" ] || die "File rỗng: $FILE"

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  echo "$1"
  read -r -p 'Gõ "restore" để tiếp tục: ' answer
  [ "$answer" = restore ] || die "Đã hủy."
}

if [ "$MODE" = pg ]; then
  case "$FILE" in *.dump) ;; *) die "Mong đợi file .dump (pg_dump -Fc)" ;; esac
  "${COMPOSE[@]}" exec -T postgres pg_restore --list <"$FILE" >/dev/null || die "File không phải bản dump hợp lệ"
  confirm "Sẽ XÓA và nạp lại toàn bộ cơ sở dữ liệu PostgreSQL từ $(basename "$FILE"). Hội thoại sau thời điểm backup sẽ mất."
  echo "==> Dừng api và bot"
  "${COMPOSE[@]}" stop api bot
  echo "==> pg_restore --clean --if-exists"
  # --no-owner: không phụ thuộc tên role lúc dump. Lỗi giữa chừng thì dừng ngay (--exit-on-error) và báo rõ.
  "${COMPOSE[@]}" exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' <"$FILE" \
    || die "pg_restore lỗi. api/bot đang dừng; kiểm tra rồi chạy lại restore hoặc khôi phục bản khác."
  echo "==> Khởi động lại api và bot (api chạy alembic upgrade head nên schema khớp mã hiện tại)"
  "${COMPOSE[@]}" up -d api bot
  echo "Xong. Kiểm tra: scripts/deploy.sh không cần chạy lại; xem docker compose ps và /api/v1/health."
else
  name=$(basename "$FILE")
  case "$name" in qdrant-*.snapshot) ;; *) die "Mong đợi tên qdrant-<collection>-<thời-gian>.snapshot" ;; esac
  collection=${name#qdrant-}
  collection=${collection%-[0-9]*-[0-9]*.snapshot}
  [ -n "$collection" ] || die "Không suy ra được tên collection từ $name"
  confirm "Sẽ GHI ĐÈ collection Qdrant '$collection' bằng $name."
  size=$(stat -c %s "$FILE")
  echo "==> Tải snapshot lên Qdrant ($size byte)"
  "${COMPOSE[@]}" exec -T api python -c "$(cat scripts/qdrant_snapshot.py)" upload "$collection" "$size" <"$FILE"
  echo "Xong. Kiểm tra số điểm: ${COMPOSE[*]} exec -T api python -c \"import os,urllib.request as u;print(u.urlopen('http://%s:%s/collections/$collection'%(os.environ['QDRANT_HOST'],os.environ['QDRANT_PORT'])).read()[:300])\""
fi
