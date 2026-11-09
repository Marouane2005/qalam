#!/bin/sh
set -eu

storage="${QALAM_STORAGE_DIR:-/var/lib/qalam/uploads}"
mkdir -p "$storage"

if [ "$(id -u)" = "0" ]; then
  chown -R qalam:qalam "$storage"
  exec gosu qalam "$@"
fi

exec "$@"
