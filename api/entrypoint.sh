#!/bin/sh
set -eu

storage="${QALAM_STORAGE_DIR:-/var/lib/qalam/uploads}"
hf_home="${HF_HOME:-/var/lib/qalam/hf-cache}"
bake_cache="${QALAM_HF_BAKE_CACHE:-/opt/qalam/hf-cache}"

mkdir -p "$storage" "$hf_home"

# Named volumes start empty and hide the baked cache. Seed once when empty.
if [ -d "$bake_cache" ] && [ -n "$(ls -A "$bake_cache" 2>/dev/null || true)" ]; then
  if [ -z "$(ls -A "$hf_home" 2>/dev/null || true)" ]; then
    cp -a "$bake_cache"/. "$hf_home"/
  fi
fi

if [ "$(id -u)" = "0" ]; then
  chown -R qalam:qalam "$storage" "$hf_home"
  # Ensure the runtime user can write hub locks / temp files on first mount.
  chmod -R u+rwX "$hf_home" 2>/dev/null || true
  exec gosu qalam "$@"
fi

exec "$@"
