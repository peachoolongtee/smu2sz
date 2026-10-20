#!/usr/bin/env bash
# After the final gate on 78b211f0: the judge pack (written to its own folder), the secret scan, the CSP check on a production
# build and on the development server `pnpm demo` runs. Ports: API 8420, web 3420 (production) and 3419 (demo).
S=$SCRATCH
W=<repo-root>/.claude/worktrees/cert-live3
O=$S/cert_live3
TOOLS=<repo-root>/.claude/worktrees/sec-fix3/docs/security/evidence/2026-10-19/dev-03215a20/tools
log() { echo "$(date -u +%H:%M:%SZ) $*" >> $O/steps.txt; }
cd $W
# the judge pack, into its own folder (the committed report is not touched)
mkdir -p $O/judge
PYTHONUTF8=1 uv run --project services/api python scripts/judge_eval.py --out "$(cygpath -w $O/judge/judge-report.md)" > $O/judge/judge_stdout.txt 2>&1
log "judge pack exit=$? $(grep -iE 'tasks|attacks|chain|tamper' $O/judge/judge-report.md | head -4 | tr '\n' ' ')"
git status --porcelain > $O/tree_after_judge.txt
# the secret scan
PYTHONUTF8=1 python -I $TOOLS/secret_scan.py 78b211f0 $O/secret_scan.txt > $O/secret_scan_stdout.txt 2>&1; log "secret scan: $(cat $O/secret_scan_stdout.txt)"
# CSP, production build (the flags pnpm demo sets)
sed -e 's#O=$S/cert0321/csp#O=$S/cert_live3/csp#' $S/csp_0321_live3.sh > $S/csp_live3.sh
bash $S/csp_live3.sh; log "csp production: $(tr '\n' ' ' < $O/csp/csp_steps.txt) $(cat $O/csp/csp_check.txt)"
powershell.exe -NoProfile -Command "foreach (\$p in 3420,8420) { Get-NetTCPConnection -State Listen -LocalPort \$p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force } }"
git checkout -- apps/web/tsconfig.json 2>/dev/null
# CSP, the development server pnpm demo runs
mkdir -p $O/csp_dev
node scripts/demo.mjs --web-port 3419 --api-port 8420 > $O/csp_dev/demo.log 2>&1 &
for i in $(seq 1 150); do grep -q "Ready\." $O/csp_dev/demo.log && break; sleep 2; done
curl -sI http://127.0.0.1:3419/ | grep -i "content-security-policy" > $O/csp_dev/header.txt
(cd apps/web && cp $S/csp_check.mjs .csp_check.mjs && node .csp_check.mjs http://localhost:3419 "$(cygpath -w $O/csp_dev/csp_browser.json)" > $O/csp_dev/csp_check.txt 2>&1; rm -f .csp_check.mjs)
log "csp dev server: $(cat $O/csp_dev/csp_check.txt | tail -1) header: $(grep -o "script-src[^;]*" $O/csp_dev/header.txt)"
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Where-Object { \$_.CommandLine -like '*demo.mjs --web-port 3419*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }; Start-Sleep 3; foreach (\$p in 3419,8420) { Get-NetTCPConnection -State Listen -LocalPort \$p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force } }"
git status --porcelain > $O/tree_after_post.txt
date -u +%Y-%m-%dT%H:%M:%SZ > $O/post_finished_utc.txt
sed -i -E 's#://[^@ ]*@#://***@#g' $O/*.txt
log "POST DONE"
