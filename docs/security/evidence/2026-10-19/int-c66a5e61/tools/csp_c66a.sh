#!/usr/bin/env bash
# CSP check on a production build of 03215a20, with the flags `pnpm demo` sets: API :8420 (127.0.0.1), next start :3420 (127.0.0.1).
S=$SCRATCH
W=<repo-root>/.claude/worktrees/cert-9011
O=$S/cert_c66a/csp; mkdir -p $O
cd $W/services/api
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 LLM_MODE=cache PYTHONUTF8=1 SKIP_PERF_BENCH=1 FEATURE_ENVELOPE=1 \
FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 FEATURE_CAPEX_CONTRACTS=1 FEATURE_CONTRACT_TERMS=1 \
FEATURE_ASK_ROUTER=1 CORS_ORIGINS=http://localhost:3420,http://127.0.0.1:3420 \
  uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8420 > $O/api.log 2>&1 &
echo $! > $O/api.pid
cd $W/apps/web
export NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8420 NEXT_PUBLIC_DEMO=1 NEXT_PUBLIC_STRATEGY_MVP=1 \
  NEXT_PUBLIC_STRATEGY_ENVELOPE=1 NEXT_DIST_DIR=.next-csp
pnpm build > $O/build.txt 2>&1; echo "build exit=$?" > $O/csp_steps.txt
node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3420 > $O/web.log 2>&1 &
echo $! > $O/web.pid
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:3420/ && break; sleep 2; done
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:8420/health && break; sleep 2; done
cp $S/csp_check.mjs .csp_check.mjs
node .csp_check.mjs http://localhost:3420 $O/csp_browser.json > $O/csp_check.txt 2>&1; echo "csp exit=$?" >> $O/csp_steps.txt
rm -f .csp_check.mjs
echo "done" >> $O/csp_steps.txt
