#!/usr/bin/env bash
# The FLOW release gate, portable (Linux, macOS): the checks of the 66c31e7e gate, in the same order.
# usage: gate.sh <clean checkout of the candidate> <output folder> <folder with the baseline sweep_{demo,prod,unset}.json>
set -u
W=$(cd "$1" && pwd); O=$(mkdir -p "$2" && cd "$2" && pwd); B=$(cd "$3" && pwd)
PG_URL_FILE=${PG_URL_FILE:-$HOME/flow-gate/pg_url.txt}
API_PORT=${API_PORT:-8420}; WEB_PORT=${WEB_PORT:-3420}; DEMO_PORT=${DEMO_PORT:-3419}; MOCK_PORT=${MOCK_PORT:-3418}; LIVE_PORT=${LIVE_PORT:-3421}
TO=$(command -v timeout || command -v gtimeout)
T=$W/docs/security/evidence/2026-10-19/dev-03215a20/tools      # sweep, reproductions, web check, CSP check, secret scan
ET=$W/docs/security/evidence/tools                              # sweep policy and diff
E14=$W/docs/security/evidence/2026-10-14                        # approval flip
E16=$W/docs/security/evidence/2026-10-16/dev-b8c65b24           # r_nl, r_paths, r_edge
A=$W/services/api; WEB=$W/apps/web
mkdir -p "$O/shards"
log() { echo "$(date -u +%H:%M:%SZ) $*" >> "$O/steps.txt"; }
for p in $API_PORT $WEB_PORT $DEMO_PORT $MOCK_PORT $LIVE_PORT; do lsof -ti tcp:$p >/dev/null 2>&1 && { echo "port $p is in use"; exit 1; }; done
cd "$A"
export SKIP_PERF_BENCH=1 PYTHONUTF8=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUNBUFFERED=1

log "step 13 re-run: the first run found port 8420 still held by step 12's API (lsof -ti tcp:A tcp:B checks only the first port)"
cd "$W"
# 13. CSP on the development server pnpm demo runs
mkdir -p "$O/csp_dev"
node scripts/demo.mjs --web-port $DEMO_PORT --api-port $API_PORT > "$O/csp_dev/demo.log" 2>&1 & DEMO_PID=$!
for i in $(seq 1 150); do grep -q "Ready\." "$O/csp_dev/demo.log" && break; sleep 2; done
curl -sI http://127.0.0.1:$DEMO_PORT/ | grep -i "content-security-policy" > "$O/csp_dev/header.txt"
( cd "$WEB" && cp "$T/csp_check.mjs" .csp_check.mjs && node .csp_check.mjs http://localhost:$DEMO_PORT "$O/csp_dev/csp_browser.json" > "$O/csp_dev/csp_check.txt" 2>&1; rm -f .csp_check.mjs )
log "csp dev server: $(tail -1 "$O/csp_dev/csp_check.txt") header: $(grep -o "script-src[^;]*" "$O/csp_dev/header.txt")"
for p in $DEMO_PID $(pgrep -f "demo.mjs --web-port $DEMO_PORT") $(lsof -ti tcp:$DEMO_PORT tcp:$API_PORT 2>/dev/null); do kill "$p" 2>/dev/null; done

git status --porcelain > "$O/tree_after.txt"
sed -i.bak -E 's#://[^@ ]*@#://***@#g' "$O"/*.txt && rm -f "$O"/*.txt.bak
log "ALL DONE (after the step 13 re-run)"
