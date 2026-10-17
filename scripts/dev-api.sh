#!/usr/bin/env bash
# The API for local development on :8000 (or $1): in-memory books, the Demo scenarios, cached LLM outputs, every feature flag
# the web app expects, and the repo-root .env ignored (it points at a hosted database). Usage: scripts/dev-api.sh [port]
set -euo pipefail
PORT="${1:-8000}"
WEB_ORIGIN="${CORS_ORIGINS:-http://localhost:3000}"
cd "$(dirname "$0")/../services/api"
exec env \
  TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 LLM_MODE=cache PYTHONUTF8=1 SKIP_PERF_BENCH=1 \
  FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 FEATURE_CAPEX_CONTRACTS=1 FEATURE_CONTRACT_TERMS=1 \
  CORS_ORIGINS="$WEB_ORIGIN" \
  uv run --project "$PWD" --directory "$PWD" uvicorn app.main:app --port "$PORT" --reload
