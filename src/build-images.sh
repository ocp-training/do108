#!/bin/bash
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"

echo "=== building fids-api ==="
podman build \
  -t ghcr.io/ocp-training/fids-api:latest \

  -f "$SRC/fids-api/Containerfile" \
  "$SRC/fids-api"

echo "=== building fids-web ==="
podman build \
  -t ghcr.io/ocp-training/fids-web:latest \
  -f "$SRC/fids-web/Containerfile" \
  "$SRC/fids-web"

echo BUILD_OK
podman images | grep fids || true
