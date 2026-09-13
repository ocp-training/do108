#!/bin/bash
set -euo pipefail

pod="${POD_NAME:-${HOSTNAME:-unknown}}"
host="${HOSTNAME:-unknown}"
api="${FIDS_API_BASE:-/api}"

escape() {
  printf '%s' "$1" | sed -e 's/[&|]/\\&/g'
}

sed -e "s|__POD_NAME__|$(escape "$pod")|g" \
    -e "s|__HOSTNAME__|$(escape "$host")|g" \
    -e "s|__API_BASE__|$(escape "$api")|g" \
    /usr/share/fids/index.html > /var/www/html/index.html

exec container-entrypoint "$@"
