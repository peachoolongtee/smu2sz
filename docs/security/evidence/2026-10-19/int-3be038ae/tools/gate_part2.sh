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
log "PART 2 START"
# 8. the mock browser suite (desktop and phone), typecheck, lint, unit
mkdir -p "$O/web"
( cd "$WEB"
  E2E_TARGET=mock E2E_PORT=$MOCK_PORT pnpm exec playwright test --workers=6 --reporter=line > "$O/web/mock_e2e.txt" 2>&1
  echo "e2e exit=$? $(grep -E '^\s+[0-9]+ (passed|failed|flaky|skipped)' "$O/web/mock_e2e.txt" | tr -s ' ' | tr '\n' ' ')" > "$O/web/web_gate.txt"
  pnpm typecheck > "$O/web/typecheck.txt" 2>&1; echo "typecheck exit=$?" >> "$O/web/web_gate.txt"
  pnpm lint > "$O/web/lint.txt" 2>&1; echo "lint exit=$?" >> "$O/web/web_gate.txt"
  pnpm test:unit > "$O/web/unit.txt" 2>&1; echo "unit exit=$? $(grep -E '^# (pass|fail) ' "$O/web/unit.txt" | tr '\n' ' ')" >> "$O/web/web_gate.txt" )
log "web gate: $(tr '\n' ' ' < "$O/web/web_gate.txt")"

# 9. the live browser suite: its configured single worker, against a real local API it starts itself
( cd "$WEB" && E2E_TARGET=live E2E_LIVE_PORT=$LIVE_PORT E2E_API_PORT=$API_PORT pnpm exec playwright test --reporter=line > "$O/live_e2e.txt" 2>&1
  log "live e2e exit=$? $(grep -E '^\s+[0-9]+ (passed|failed|flaky|skipped)' "$O/live_e2e.txt" | tr -s ' ' | tr '\n' ' ')" )

# 10. the judge pack, into its own folder (the committed report is not touched)
cd "$W"; mkdir -p "$O/judge"
PYTHONUTF8=1 uv run --project services/api python scripts/judge_eval.py --out "$O/judge/judge-report.md" > "$O/judge/judge_stdout.txt" 2>&1
log "judge pack exit=$? $(grep -iE 'tasks|attacks|chain|tamper' "$O/judge/judge-report.md" | head -4 | tr '\n' ' ')"

# 11. the secret scan: the candidate's tracked files and every branch's history
python3 -I "$T/secret_scan.py" "$(git rev-parse HEAD)" "$O/secret_scan.txt" > "$O/secret_scan_stdout.txt" 2>&1; log "secret scan: $(cat "$O/secret_scan_stdout.txt")"

# 12. CSP on a production build, with the flags pnpm demo sets
mkdir -p "$O/csp"
( cd "$A" && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 LLM_MODE=cache FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 \
  FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 FEATURE_CAPEX_CONTRACTS=1 FEATURE_CONTRACT_TERMS=1 FEATURE_ASK_ROUTER=1 \
  CORS_ORIGINS=http://localhost:$WEB_PORT,http://127.0.0.1:$WEB_PORT \
  uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port $API_PORT > "$O/csp/api.log" 2>&1 & echo $! > "$O/csp/api.pid" )
( cd "$WEB" && export NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:$API_PORT NEXT_PUBLIC_DEMO=1 NEXT_PUBLIC_STRATEGY_MVP=1 \
    NEXT_PUBLIC_STRATEGY_ENVELOPE=1 NEXT_DIST_DIR=.next-csp
  pnpm build > "$O/csp/build.txt" 2>&1; echo "build exit=$?" > "$O/csp/csp_steps.txt"
  node node_modules/next/dist/bin/next start -H 127.0.0.1 -p $WEB_PORT > "$O/csp/web.log" 2>&1 & echo $! > "$O/csp/web.pid"
  for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:$WEB_PORT/ && break; sleep 2; done
  for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:$API_PORT/health && break; sleep 2; done
  cp "$T/csp_check.mjs" .csp_check.mjs; node .csp_check.mjs http://localhost:$WEB_PORT "$O/csp/csp_browser.json" > "$O/csp/csp_check.txt" 2>&1
  echo "csp exit=$?" >> "$O/csp/csp_steps.txt"; rm -f .csp_check.mjs )
log "csp production: $(tr '\n' ' ' < "$O/csp/csp_steps.txt") $(tail -1 "$O/csp/csp_check.txt")"
for p in $(cat "$O/csp/api.pid" "$O/csp/web.pid") $(lsof -ti tcp:$WEB_PORT tcp:$API_PORT 2>/dev/null); do kill "$p" 2>/dev/null; done; sleep 3
git checkout -- apps/web/tsconfig.json 2>/dev/null      # a custom NEXT_DIST_DIR makes Next add its folder to tsconfig.json

# 13. CSP on the development server pnpm demo runs
mkdir -p "$O/csp_dev"
node scripts/demo.mjs --web-port $DEMO_PORT --api-port $API_PORT > "$O/csp_dev/demo.log" 2>&1 & DEMO_PID=$!
for i in $(seq 1 150); do grep -q "Ready\." "$O/csp_dev/demo.log" && break; sleep 2; done
curl -sI http://127.0.0.1:$DEMO_PORT/ | grep -i "content-security-policy" > "$O/csp_dev/header.txt"
( cd "$WEB" && cp "$T/csp_check.mjs" .csp_check.mjs && node .csp_check.mjs http://localhost:$DEMO_PORT "$O/csp_dev/csp_browser.json" > "$O/csp_dev/csp_check.txt" 2>&1; rm -f .csp_check.mjs )
log "csp dev server: $(tail -1 "$O/csp_dev/csp_check.txt") header: $(grep -o "script-src[^;]*" "$O/csp_dev/header.txt")"
for p in $DEMO_PID $(pgrep -f "demo.mjs --web-port $DEMO_PORT") $(lsof -ti tcp:$DEMO_PORT tcp:$API_PORT 2>/dev/null); do kill "$p" 2>/dev/null; done

git status --porcelain > "$O/tree_after.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$O/finished_utc.txt"
sed -i.bak -E 's#://[^@ ]*@#://***@#g' "$O"/*.txt && rm -f "$O"/*.txt.bak      # mask any database URL
log "ALL DONE"
