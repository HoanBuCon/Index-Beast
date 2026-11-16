#!/usr/bin/env bash
# Cron hằng tuần ngoài giờ cao điểm: cập nhật tăng dần wiki.gg (chỉ trang đổi/mới/xoá) rồi re-index phần đó.
# Crontab mẫu (Chủ nhật 03:30): 30 3 * * 0 /opt/indexbeast/scripts/ingest-weekly.sh
# Biến tuỳ chọn: INGEST_LOG_DIR (mặc định /var/log/indexbeast hoặc ~/.local/state/indexbeast), INGEST_LOCK_FILE,
# INGEST_ARGS (vd. "--max-pages 500" hoặc "--dry-run"). Thoát 0 khi hoàn tất, khác 0 khi lỗi/partial/đang có lượt khác.
# Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Log nằm ngoài repo để git pull/deploy không đụng tới.
LOG_DIR="${INGEST_LOG_DIR:-/var/log/indexbeast}"
if ! mkdir -p "$LOG_DIR" 2>/dev/null || [ ! -w "$LOG_DIR" ]; then
  LOG_DIR="$HOME/.local/state/indexbeast"
  mkdir -p "$LOG_DIR"
fi
LOG="$LOG_DIR/ingest-weekly-$(date -u +%Y%m%d-%H%M%S).log"
LOCK="${INGEST_LOCK_FILE:-$LOG_DIR/ingest-weekly.lock}"

# Khoá chống chạy chồng (cron trễ, chạy tay trùng giờ): flock không chờ, tự nhả khi tiến trình chết.
command -v flock >/dev/null || { echo "ingest-weekly: thiếu flock (gói util-linux)" >&2; exit 1; }
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date -u +%FT%TZ) ingest-weekly: lượt trước còn chạy ($LOCK), bỏ qua" | tee -a "$LOG_DIR/ingest-weekly.skipped.log" >&2
  exit 75
fi

# Giữ 12 log gần nhất.
ls -1t "$LOG_DIR"/ingest-weekly-*.log 2>/dev/null | tail -n +13 | xargs -r rm -f -- || true

{
  echo "$(date -u +%FT%TZ) ingest-weekly: bắt đầu"
  cd "$ROOT"
  set +e
  # -T: cron không có TTY. INGEST_ARGS cố ý không đặt trong ngoặc kép để tách từ.
  # shellcheck disable=SC2086
  docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile app run --rm -T api \
    python -m ingest update --source wikigg ${INGEST_ARGS:-}
  code=$?
  set -e
  echo "$(date -u +%FT%TZ) ingest-weekly: kết thúc, mã thoát $code"
  exit "$code"
} >>"$LOG" 2>&1
