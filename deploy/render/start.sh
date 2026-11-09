#!/bin/bash
# Starts Redis, the API and the web app in one container, and exits as soon as
# any of them stops so the platform restarts the whole container.
set -euo pipefail

alive() { kill -0 "$1" 2>/dev/null; }

mkdir -p "${QALAM_STORAGE_DIR:-/var/lib/qalam/uploads}"

redis-server --port 6379 --bind 127.0.0.1 --save "" --appendonly no \
  --maxmemory 32mb --maxmemory-policy allkeys-lru &
redis_pid=$!

python -m qalam.cli serve &
api_pid=$!

# Wait for the API to finish migrations before the web app takes traffic.
for _ in $(seq 1 120); do
  alive "$redis_pid" && alive "$api_pid" || break
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${QALAM_PORT:-8000}/health')" 2>/dev/null; then
    break
  fi
  sleep 1
done

(cd "${QALAM_WEB_DIR:-/app/web}" && exec node server.js) &
web_pid=$!

while alive "$redis_pid" && alive "$api_pid" && alive "$web_pid"; do
  sleep 5
done

echo "a Qalam process stopped, exiting" >&2
kill "$redis_pid" "$api_pid" "$web_pid" 2>/dev/null || true
exit 1
