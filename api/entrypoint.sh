#!/bin/sh
set -eu

storage="${QALAM_STORAGE_DIR:-/var/lib/qalam/uploads}"
hf_home="${HF_HOME:-/var/lib/qalam/hf-cache}"
mkdir -p "$storage" "$hf_home"

if [ "$(id -u)" = "0" ]; then
  chown -R qalam:qalam "$storage" "$hf_home"
  exec gosu qalam "$@"
fi

exec "$@"
