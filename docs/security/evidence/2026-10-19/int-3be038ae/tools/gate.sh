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
mkdir -p "$O/shards"; : > "$O/steps.txt"
log() { echo "$(date -u +%H:%M:%SZ) $*" >> "$O/steps.txt"; }
for p in $API_PORT $WEB_PORT $DEMO_PORT $MOCK_PORT $LIVE_PORT; do lsof -ti tcp:$p >/dev/null 2>&1 && { echo "port $p is in use"; exit 1; }; done
cd "$A"
git rev-parse HEAD > "$O/commit.txt"; git status --porcelain --untracked-files=no > "$O/tree_status.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$O/started_utc.txt"
export SKIP_PERF_BENCH=1 PYTHONUTF8=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUNBUFFERED=1

# 1. the full API suite: one process per test folder and per tests/api file, 8 at a time
( export DEMO_MODE=1 O
  run() { s="$1"; n=$(echo "$s" | tr '/' '_'); uv run --no-sync pytest -o addopts= -q -p no:cacheprovider -rfE --tb=line "$s" > "$O/shards/$n.txt" 2>&1
          echo "$s exit=$? $(grep -E '[0-9]+ (passed|failed|error)|no tests ran' "$O/shards/$n.txt" | tail -1)" >> "$O/shards/summary.txt"; }
  export -f run; : > "$O/shards/summary.txt"
  ( ls -d tests/*/ | sed 's#/$##' | grep -v -e '^tests/api$' -e '__pycache__'; ls tests/api/test_*.py; ls tests/test_*.py 2>/dev/null ) | xargs -P 8 -I{} bash -c 'run {}' )
python3 - "$O/shards/summary.txt" > "$O/suite_totals.txt" <<'PY'
import re, sys
t = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}; bad = []
for line in open(sys.argv[1], encoding="utf-8"):
    for n, k in re.findall(r"(\d+) (passed|failed|skipped|errors?)", line):
        t["error" if k.startswith("error") else k] += int(n)
    if "exit=0" not in line: bad.append(line.strip())
print(t); print("non-zero shards:", len(bad)); [print(" ", b) for b in bad]
PY
log "full suite: $(head -2 "$O/suite_totals.txt" | tr '\n' ' ')"

# 2. the attack catalogue (then restore the committed report)
DEMO_MODE=1 uv run --no-sync python -m app.security.attacks --report > "$O/attacks.txt" 2>&1; log "attacks exit=$? $(grep -E '^detection_rate' "$O/attacks.txt")"
cp evals/security/latest_report.md evals/security/latest_report.json "$O/"; git checkout -- evals/security/latest_report.json evals/security/latest_report.md

# 3. the credential sweep in three modes, the policy check, the diff against the last certified sweep
for m in demo prod unset; do SWEEP_MODE=$m uv run --no-sync python "$T/authz_sweep_v3.py" "$O/sweep_$m.json" > "$O/sweep_$m.txt" 2>&1; log "sweep $m exit=$?"; done
( python3 "$ET/sweep_policy.py" "$O/sweep_demo.json" "$O/sweep_prod.json" "$O/sweep_unset.json"
  for m in demo prod unset; do python3 "$ET/sweep_diff.py" "$B/sweep_$m.json" "$O/sweep_$m.json"; done ) > "$O/sweep_policy.txt" 2>&1
log "sweep policy and diff exit=$?"

# 4. the reproductions and the approval flip (non-zero exits are the refusals: compare the outputs with the baseline folder's)
for r in r3 r4_bounded repro1 repro2 repro3; do DEMO_MODE=1 $TO 600 uv run --no-sync python "$T/$r.py" > "$O/$r.txt" 2>&1; log "$r exit=$?"; done
mkdir -p "$O/flip"; DEMO_MODE=1 uv run --no-sync python "$E14/approval_flip.py" "$O/flip" > "$O/approval_flip.txt" 2>&1; log "approval_flip exit=$?"
for r in r_nl r_paths r_edge; do DEMO_MODE=1 uv run --no-sync python "$E16/$r.py" > "$O/$r.txt" 2>&1; log "$r exit=$?"; done

# 5. the language boundary, recorded (cache) and scripted (fake) answers
for be in cache fake; do DEMO_MODE=1 uv run --no-sync python ../../scripts/certify_language_boundary.py --backend $be --out "$O/lb_$be" > "$O/lb_$be.txt" 2>&1
  log "language boundary $be exit=$? $(grep -E 'WRONG_MATERIAL' "$O/lb_$be.txt" | tail -1)"; done

# 6. PostgreSQL 17: concurrency three times, then the audit guards
for i in 1 2 3; do TERMSLEDGER_TEST_DATABASE_URL="$(sed 's#/postgres$#/termsledger_sectest#' "$PG_URL_FILE")" DEMO_MODE=1 \
  uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rA --tb=line tests/concurrency > "$O/pg_concurrency_$i.txt" 2>&1
  log "pg concurrency $i: $(grep -E '[0-9]+ (passed|failed)' "$O/pg_concurrency_$i.txt" | tail -1) postgres-passed=$(grep -c 'PASSED.*postgres' "$O/pg_concurrency_$i.txt")"; done
TERMSLEDGER_TEST_DATABASE_URL="$(sed 's#/postgres$#/termsledger_sectest3#' "$PG_URL_FILE")" DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rA \
  --tb=line tests/persistence/test_audit_guards.py tests/operations/test_sec08_decided_in_log.py > "$O/pg_guards.txt" 2>&1
log "pg guards: $(grep -E '[0-9]+ (passed|failed)' "$O/pg_guards.txt" | tail -1)"

# 7. dependency audits
uv export --frozen --no-hashes --no-emit-project --no-dev > "$O/requirements.txt" 2>/dev/null
uvx pip-audit -r "$O/requirements.txt" --no-deps --disable-pip > "$O/pip_audit.txt" 2>&1; log "pip-audit exit=$? $(tail -1 "$O/pip_audit.txt")"
( cd "$WEB" && pnpm audit --prod --json > "$O/pnpm_audit_prod.json" 2>&1; log "pnpm audit --prod exit=$?"; pnpm audit --json > "$O/pnpm_audit_all.json" 2>&1; log "pnpm audit all exit=$?" )

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
