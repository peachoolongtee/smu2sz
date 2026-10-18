#!/usr/bin/env bash
# Certification of dev 29fa0ea2, the assessed build of the self-assessment v3 (Appendix A, E1 to E8).
S=/c/Users/ian/AppData/Local/Temp/claude/C--Users-ian-Documents-Projects-smu2sz/aa96fbfb-4038-45c2-8bb9-e28d412a5861/scratchpad
W=/c/Users/ian/Documents/Projects/smu2sz/.claude/worktrees/cert-719c
A=$W/services/api
E=/c/Users/ian/Documents/Projects/smu2sz/.claude/worktrees/sec-fix3/docs/security/evidence
O=$S/cert29fa; mkdir -p $O/shards; : > $O/steps.txt
log() { echo "$(date -u +%H:%M:%SZ) $*" >> $O/steps.txt; }
cd $A
git rev-parse HEAD > $O/commit.txt; git status --porcelain --untracked-files=no > $O/tree_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ > $O/started_utc.txt
uv sync --frozen -q
export SKIP_PERF_BENCH=1 PYTHONUTF8=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUNBUFFERED=1
# E5: the full suite, one process per test directory and per tests/api file, counts recorded
( export DEMO_MODE=1
  shards=$( (ls -d tests/*/ | sed 's#/$##' | grep -v '^tests/api$'; ls tests/api/test_*.py; ls tests/test_*.py 2>/dev/null) )
  run() { s="$1"; n=$(echo "$s" | tr '/' '_'); uv run --no-sync pytest -o addopts= -q -p no:cacheprovider -rfE --tb=line "$s" > "$O/shards/$n.txt" 2>&1
          echo "$s exit=$? $(grep -E '[0-9]+ (passed|failed|error)|no tests ran' "$O/shards/$n.txt" | tail -1)" >> "$O/shards/summary.txt"; }
  export -f run; export O
  : > $O/shards/summary.txt; echo "$shards" | xargs -P 8 -I{} bash -c 'run {}' )
python - "$O/shards/summary.txt" > $O/suite_totals.txt <<'PY'
import re, sys
t = {"passed": 0, "failed": 0, "skipped": 0, "error": 0, "xfailed": 0, "deselected": 0}; bad = []
for line in open(sys.argv[1], encoding="utf-8"):
    for n, k in re.findall(r"(\d+) (passed|failed|skipped|errors?|xfailed|deselected)", line):
        t["error" if k.startswith("error") else k] += int(n)
    if "exit=0" not in line: bad.append(line.strip())
print(t); print("non-zero shards:", len(bad)); [print(" ", b) for b in bad]
PY
log "full suite: $(head -2 $O/suite_totals.txt | tr '\n' ' ')"
# E1, E2, E4: the catalogue report (tests/security ran above, including positive controls, mutations and the route policy)
DEMO_MODE=1 uv run --no-sync python -m app.security.attacks --report > $O/attacks.txt 2>&1; log "attacks exit=$? $(grep -E '^detection_rate' $O/attacks.txt)"
cp evals/security/latest_report.md evals/security/latest_report.json $O/; git checkout -- evals/security/latest_report.json evals/security/latest_report.md
# E3: the sweep in three modes, the policy check and the diff against 0fde33fd
for m in demo prod unset; do SWEEP_MODE=$m uv run --no-sync python $S/authz_sweep_v3.py $O/sweep_$m.json > $O/sweep_$m.txt 2>&1; log "sweep $m exit=$?"; done
(python $E/tools/sweep_policy.py $O/sweep_demo.json $O/sweep_prod.json $O/sweep_unset.json; for m in demo prod unset; do python $E/tools/sweep_diff.py $E/2026-10-17/dev-0fde33fd/sweep_$m.json $O/sweep_$m.json; done) > $O/sweep_policy.txt 2>&1; log "sweep policy and diff exit=$?"
# the earlier reproductions
for r in r3 r4_bounded repro1 repro2 repro3; do DEMO_MODE=1 timeout 600 uv run --no-sync python $S/$r.py > $O/$r.txt 2>&1; log "$r exit=$?"; done
DEMO_MODE=1 uv run --no-sync python $E/2026-10-14/approval_flip.py > $O/approval_flip.txt 2>&1; log "approval_flip exit=$?"
for r in r_nl r_paths r_edge; do DEMO_MODE=1 uv run --no-sync python $E/2026-10-16/dev-b8c65b24/$r.py > $O/$r.txt 2>&1; log "$r exit=$?"; done
# E6: the language boundary, recorded and scripted answers
for be in cache fake; do DEMO_MODE=1 uv run --no-sync python ../../scripts/certify_language_boundary.py --backend $be --out $O/lb_$be > $O/lb_$be.txt 2>&1; log "language boundary $be exit=$? $(grep -E 'WRONG_MATERIAL' $O/lb_$be.txt | tail -1 | sed 's/.*run: //')"; done
# E7: PostgreSQL 17
for i in 1 2 3; do TERMSLEDGER_TEST_DATABASE_URL="$(sed 's#/postgres$#/termsledger_sectest#' $S/pg_url.txt)" DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rA --tb=line tests/concurrency > $O/pg_concurrency_$i.txt 2>&1; log "pg concurrency $i: $(grep -E '[0-9]+ (passed|failed)' $O/pg_concurrency_$i.txt | tail -1) postgres-passed=$(grep -c 'PASSED.*postgres' $O/pg_concurrency_$i.txt)"; done
TERMSLEDGER_TEST_DATABASE_URL="$(sed 's#/postgres$#/termsledger_sectest3#' $S/pg_url.txt)" DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rA --tb=line tests/persistence/test_audit_guards.py tests/operations/test_sec08_decided_in_log.py > $O/pg_guards.txt 2>&1; log "pg guards: $(grep -E '[0-9]+ (passed|failed)' $O/pg_guards.txt | tail -1)"
# E8: dependency scans
uv export --frozen --no-hashes --no-emit-project --no-dev > $O/requirements.txt 2>/dev/null
uvx pip-audit -r $O/requirements.txt --no-deps --disable-pip > $O/pip_audit.txt 2>&1; log "pip-audit exit=$? $(tail -1 $O/pip_audit.txt)"
(cd $W/apps/web && pnpm audit --prod --json > $O/pnpm_audit_prod.json 2>&1; echo "pnpm audit --prod exit=$?" >> $O/steps.txt; pnpm audit --json > $O/pnpm_audit_all.json 2>&1; echo "pnpm audit all exit=$?" >> $O/steps.txt)
# the mock browser suite, typecheck, lint, unit
(cd $W/apps/web && pnpm install --frozen-lockfile > $O/pnpm_install.txt 2>&1); bash $S/web_gate.sh cert-719c 3418 $O/web > /dev/null 2>&1; log "web gate: $(cat $O/web/web_gate.txt | tr '\n' ' ')"
date -u +%Y-%m-%dT%H:%M:%SZ > $O/finished_utc.txt
sed -i -E 's#://[^@ ]*@#://***@#g' $O/*.txt
log "ALL DONE"
