#!/usr/bin/env bash
# Backup production: pg_dump hằng ngày (giữ 7 bản) + Qdrant snapshot hằng tuần (giữ 4 bản); chạy bằng cron.
# Dùng:  scripts/backup.sh daily      pg_dump -Fc của PostgreSQL (hội thoại, trace, corpus)
#        scripts/backup.sh weekly     snapshot collection RAG của Qdrant
#        scripts/backup.sh all        cả hai
# Ghi vào BACKUP_DIR (mặc định $HOME/indexbeast-backups, NGOÀI repo, quyền 700). Biến tùy chọn:
#   BACKUP_DIR, KEEP_DAILY=7, KEEP_WEEKLY=4
# Không đọc, không in secret: pg_dump chạy trong container postgres (thông tin đăng nhập nằm sẵn ở đó).
# Ví dụ crontab và cách khôi phục: docs/production.md. Phụ trách: TV1 · [S5] Backup & monitoring
set -euo pipefail
umask 077
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO"

MODE=${1:-daily}
BACKUP_DIR=${BACKUP_DIR:-$HOME/indexbeast-backups}
KEEP_DAILY=${KEEP_DAILY:-7}
KEEP_WEEKLY=${KEEP_WEEKLY:-4}
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app)

die() { echo "$(date -Is) LỖI: $*" >&2; exit 1; }
log() { echo "$(date -Is) $*"; }

case "$MODE" in daily | weekly | all) ;; *) die "Chế độ không hợp lệ: $MODE (daily | weekly | all)" ;; esac
case "$BACKUP_DIR" in /*) ;; *) die "BACKUP_DIR phải là đường dẫn tuyệt đối" ;; esac
BACKUP_DIR=${BACKUP_DIR%/}
# Thư mục được xóa bản cũ: không cho là gốc, không cho nằm trong repo (git clean/checkout có thể đụng tới)
case "$BACKUP_DIR" in "" | "$HOME" | "$REPO" | "$REPO"/*) die "BACKUP_DIR không hợp lệ: $BACKUP_DIR" ;; esac
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# Giữ $2 bản mới nhất khớp mẫu $1 trong BACKUP_DIR (tên có dấu thời gian nên sắp theo tên = sắp theo thời gian)
rotate() {
  local pattern=$1 keep=$2 f
  # shellcheck disable=SC2012
  ls -1 "$BACKUP_DIR"/$pattern 2>/dev/null | sort -r | tail -n +"$((keep + 1))" | while IFS= read -r f; do
    rm -f -- "$f" && log "Xóa bản cũ: $(basename "$f")"
  done
}

backup_postgres() {
  local out="$BACKUP_DIR/pg-$(date +%Y%m%d-%H%M%S).dump"
  log "pg_dump -> $(basename "$out")"
  "${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' >"$out.part" \
    || { rm -f -- "$out.part"; die "pg_dump thất bại"; }
  # Kiểm tra bản dump đọc lại được (mục lục hợp lệ) trước khi coi là thành công và xoay vòng
  "${COMPOSE[@]}" exec -T postgres pg_restore --list <"$out.part" >/dev/null \
    || { rm -f -- "$out.part"; die "Bản dump không đọc lại được, đã xóa"; }
  mv -- "$out.part" "$out"
  log "Xong pg: $(du -h "$out" | cut -f1)"
  rotate 'pg-*.dump' "$KEEP_DAILY"
}

backup_qdrant() {
  local snap="$REPO/scripts/qdrant_snapshot.py" collection name out
  collection=$("${COMPOSE[@]}" exec -T api printenv RAG_COLLECTION | tr -d '\r\n')
  [ -n "$collection" ] || die "Không đọc được RAG_COLLECTION từ container api (api đang chạy?)"
  qd() { "${COMPOSE[@]}" exec -T api python -c "$(cat "$snap")" "$@"; }
  log "Qdrant snapshot collection $collection"
  name=$(qd create "$collection" | tr -d '\r\n')
  out="$BACKUP_DIR/qdrant-$collection-$(date +%Y%m%d-%H%M%S).snapshot"
  qd download "$collection" "$name" >"$out.part" || { rm -f -- "$out.part"; qd delete "$collection" "$name" || true; die "Tải snapshot thất bại"; }
  [ -s "$out.part" ] || { rm -f -- "$out.part"; die "Snapshot rỗng"; }
  mv -- "$out.part" "$out"
  # Snapshot phía server nằm trong container, không có trong backup dir: xóa để khỏi đầy đĩa
  qd delete "$collection" "$name" || log "Cảnh báo: không xóa được snapshot phía server $name"
  log "Xong qdrant: $(du -h "$out" | cut -f1)"
  rotate "qdrant-$collection-*.snapshot" "$KEEP_WEEKLY"
}

case "$MODE" in
  daily) backup_postgres ;;
  weekly) backup_qdrant ;;
  all) backup_postgres; backup_qdrant ;;
esac
