#!/usr/bin/env bash
# Đo RAM/CPU của từng container khi trả lời 1 câu hỏi RAG thật (chạy trên VPS sau deploy.sh).
# CẢNH BÁO: gọi DeepSeek (và Tavily nếu bật) nên tốn một ít phí API.
# Dùng:  STAGING_PASS='mật-khẩu' scripts/staging/measure.sh ["câu hỏi"]
# Biến: STAGING_URL (mặc định https://$STAGING_HOST, đọc từ .env: Caddy chỉ phục vụ đúng host đó),
#       STAGING_USER (mặc định lấy từ .env, rồi "staging"), SAMPLE_SECONDS (mặc định 1)
# Phụ trách: TV1 · [S3] Staging trên VPS
set -euo pipefail
cd "$(dirname "$0")/../.."

env_value() { sed -n "s/^$1=//p" .env 2>/dev/null | head -1; }

QUESTION=${1:-"Marika là ai?"}
HOST=${STAGING_HOST:-$(env_value STAGING_HOST)}
URL=${STAGING_URL:-https://${HOST:-localhost}}
USER_NAME=${STAGING_USER:-$(env_value STAGING_USER)}
USER_NAME=${USER_NAME:-staging}
PASS=${STAGING_PASS:?Đặt STAGING_PASS (mật khẩu basic auth)}
INTERVAL=${SAMPLE_SECONDS:-1}
SAMPLES=$(mktemp)
trap 'kill "${SAMPLER:-0}" 2>/dev/null || true; rm -f "$SAMPLES"' EXIT

echo "== Trước khi hỏi"
free -m | sed -n '1,3p'
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'

(while true; do
  docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' >>"$SAMPLES" || true
  sleep "$INTERVAL"
done) &
SAMPLER=$!

BODY=$(python3 -c 'import json,sys; print(json.dumps({"message": sys.argv[1], "channel": "web"}))' "$QUESTION")
echo "== Gửi câu hỏi: $QUESTION"
RESULT=$(curl -sk -o /dev/null -u "$USER_NAME:$PASS" -H 'Content-Type: application/json' -d "$BODY" \
  -w 'http=%{http_code} thoi_gian=%{time_total}s' "$URL/api/v1/chat" || true)
echo "$RESULT"
sleep "$INTERVAL"
kill "$SAMPLER" 2>/dev/null || true

echo "== Sau khi hỏi"
free -m | sed -n '1,3p'

echo "== Đỉnh trong lúc hỏi (MiB, % của một vCPU)"
awk -F'\t' '
  function mib(s,  n, u) { n = s + 0; u = s; gsub(/[0-9.]/, "", u)
    if (u == "GiB") return n * 1024; if (u == "MiB") return n; if (u == "KiB") return n / 1024; return n / 1048576 }
  { split($2, m, " / "); v = mib(m[1]); c = $3 + 0
    if (v > mem[$1]) mem[$1] = v; if (c > cpu[$1]) cpu[$1] = c; limit[$1] = m[2] }
  END { printf "%-28s %10s %8s  %s\n", "container", "RAM", "CPU%", "giới hạn"
        for (k in mem) printf "%-28s %10.1f %8.1f  %s\n", k, mem[k], cpu[k], limit[k] }' "$SAMPLES" | sort
