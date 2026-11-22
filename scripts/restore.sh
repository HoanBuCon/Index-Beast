#!/usr/bin/env bash
# Khôi phục production từ bản backup của scripts/backup.sh. GHI ĐÈ dữ liệu hiện tại.
# Dùng:  scripts/restore.sh pg <file.dump>                  khôi phục PostgreSQL (nạp DB tạm, kiểm tra, rồi hoán đổi; api/bot chỉ dừng lúc hoán đổi)
#        scripts/restore.sh qdrant <file.snapshot>          khôi phục collection RAG (tên collection lấy từ tên file)
#        scripts/restore.sh list                            liệt kê backup hiện có
# Thêm --yes (đứng cuối) để bỏ qua câu hỏi xác nhận. Đường dẫn file phải nằm trong BACKUP_DIR (mặc định $HOME/indexbeast-backups).
# pg: nạp vào DB tạm <POSTGRES_DB>_restore, kiểm tra, rồi mới dừng api/bot và đổi tên DB (DB cũ giữ lại làm đường lui). Thử khôi phục an toàn: docs/production.md → "Thử khôi phục". Phụ trách: TV1 · [S5] Backup & monitoring
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

  # Chạy lệnh sh trong container postgres (biến POSTGRES_* nằm sẵn ở đó); đối số của host truyền qua $1.. , không nội suy vào chuỗi lệnh
  pgsh() { "${COMPOSE[@]}" exec -T postgres sh -c "$@"; }
  LIVE=$(pgsh 'printf %s "$POSTGRES_DB"') || die "Không đọc được POSTGRES_DB từ container postgres (postgres đang chạy chưa?)"
  [ -n "$LIVE" ] || die "POSTGRES_DB rỗng trong container postgres"
  RESTORE_DB="${LIVE}_restore"
  PREV_DB="${LIVE}_prev_$(date +%Y%m%d-%H%M%S)"

  confirm "Sẽ nạp $(basename "$FILE") vào DB tạm '$RESTORE_DB', kiểm tra, rồi (chỉ khi đạt) dừng api/bot và đổi tên: '$LIVE' -> '$PREV_DB' (giữ nguyên để quay lại), '$RESTORE_DB' -> '$LIVE'. Hội thoại sau thời điểm backup sẽ không còn trong DB mới."

  # Giai đoạn 1: chỉ động tới DB tạm. Lỗi ở đây thì DB đang chạy KHÔNG bị đụng và api/bot vẫn chạy.
  echo "==> [1/4] Tạo DB tạm $RESTORE_DB (xóa bản cũ nếu có)"
  pgsh 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q -v "rdb=${POSTGRES_DB}_restore"' <<'SQL' \
    || die "Không tạo được DB tạm. DB đang chạy chưa bị đụng, api/bot vẫn chạy."
DROP DATABASE IF EXISTS :"rdb" WITH (FORCE);
CREATE DATABASE :"rdb";
SQL
  echo "==> [2/4] pg_restore vào $RESTORE_DB (--no-owner: không phụ thuộc tên role lúc dump; dừng ngay khi lỗi)"
  pgsh 'pg_restore -U "$POSTGRES_USER" -d "${POSTGRES_DB}_restore" --no-owner --exit-on-error' <"$FILE" \
    || die "pg_restore lỗi (exit khác 0). DB đang chạy chưa bị đụng, api/bot vẫn chạy. DB tạm $RESTORE_DB còn lại để xem; lần chạy sau sẽ tự xóa."
  echo "==> [3/4] Kiểm tra DB tạm"
  # alembic_version và các bảng lõi phải có; in số dòng để so với backup/log
  pgsh 'psql -U "$POSTGRES_USER" -d "${POSTGRES_DB}_restore" -v ON_ERROR_STOP=1 -q' <<'SQL' \
    || die "DB tạm không đạt kiểm tra (thiếu alembic_version hoặc bảng lõi). DB đang chạy chưa bị đụng, api/bot vẫn chạy."
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['alembic_version', 'documents', 'chunks', 'conversations', 'messages'] LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE EXCEPTION 'thiếu bảng public.%', t;
    END IF;
  END LOOP;
END $$;
SELECT 'alembic_version' AS bang, version_num AS gia_tri FROM alembic_version;
SELECT 'documents' AS bang, count(*) AS so_dong FROM documents
UNION ALL SELECT 'chunks', count(*) FROM chunks
UNION ALL SELECT 'conversations', count(*) FROM conversations
UNION ALL SELECT 'messages', count(*) FROM messages;
SQL

  # Giai đoạn 2: hoán đổi. Từ đây api/bot dừng; lỗi thì cố đưa DB cũ về chỗ cũ rồi bật lại dịch vụ.
  start_services() {
    echo "==> Khởi động lại api (và bot nếu có DISCORD_TOKEN); api chạy alembic upgrade head nên schema khớp mã hiện tại"
    SCALE=()
    grep -qE '^DISCORD_TOKEN=.+' .env || { echo "    (không có DISCORD_TOKEN: bỏ qua bot)"; SCALE=(--scale bot=0); }
    "${COMPOSE[@]}" up -d "${SCALE[@]}" api bot
  }
  rename_dbs() {  # rename_dbs <từ> <sang>: ngắt kết nối rồi đổi tên
    pgsh 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -q -v "from=$1" -v "to=$2"' _ "$1" "$2" <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'from' AND pid <> pg_backend_pid();
ALTER DATABASE :"from" RENAME TO :"to";
SQL
  }
  echo "==> [4/4] Dừng api và bot, hoán đổi DB"
  "${COMPOSE[@]}" stop api bot
  if ! rename_dbs "$LIVE" "$PREV_DB" >/dev/null; then
    start_services || true
    die "Không đổi tên được '$LIVE'. DB đang chạy vẫn là '$LIVE' (chưa đổi); đã bật lại api/bot."
  fi
  if ! rename_dbs "$RESTORE_DB" "$LIVE" >/dev/null; then
    echo "Đổi '$RESTORE_DB' -> '$LIVE' lỗi; đưa DB cũ về chỗ cũ" >&2
    rename_dbs "$PREV_DB" "$LIVE" >/dev/null || die "KHÔNG đưa được '$PREV_DB' về '$LIVE'. Làm tay: ALTER DATABASE \"$PREV_DB\" RENAME TO \"$LIVE\"; (api/bot đang dừng)."
    start_services || true
    die "Hoán đổi lỗi; đã trả DB cũ về '$LIVE' và bật lại api/bot."
  fi
  start_services
  echo "Xong. DB mới: $LIVE (từ $(basename "$FILE")). DB cũ giữ ở: $PREV_DB. Kiểm tra: docker compose ps và /api/v1/health."
  echo "Quay lại DB cũ (nếu bản khôi phục không như ý):"
  echo "  ${COMPOSE[*]} stop api bot"
  echo "  ${COMPOSE[*]} exec postgres sh -c 'psql -U \"\$POSTGRES_USER\" -d postgres'    # rồi gõ trong psql:"
  echo "    SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$LIVE' AND pid <> pg_backend_pid();"
  echo "    ALTER DATABASE \"$LIVE\" RENAME TO \"${LIVE}_bad\";"
  echo "    ALTER DATABASE \"$PREV_DB\" RENAME TO \"$LIVE\";"
  echo "  ${COMPOSE[*]} up -d api bot"
  echo "Khi đã yên tâm, giải phóng dung lượng: DROP DATABASE \"$PREV_DB\"; (psql -d postgres). Mỗi lần restore thêm một DB _prev_ nên nhớ dọn."
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
