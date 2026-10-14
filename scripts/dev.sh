#!/usr/bin/env bash
# One command for local development. `scripts/dev.sh live` starts the API (:8000) and the web app (:3000) against it;
# `scripts/dev.sh mock` (the default) starts the web app alone on the recorded mocks. Ctrl-C stops both.
set -euo pipefail
MODE="${1:-mock}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
case "$MODE" in
  mock)
    cd "$ROOT/apps/web" && exec pnpm run dev:mock ;;
  live)
    "$ROOT/scripts/dev-api.sh" 8000 &
    API_PID=$!
    trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
    for _ in $(seq 1 60); do curl -sf http://localhost:8000/health >/dev/null && break; sleep 1; done
    cd "$ROOT/apps/web" && pnpm run dev:live ;;
  *)
    echo "usage: scripts/dev.sh [mock|live]" >&2; exit 2 ;;
esac
