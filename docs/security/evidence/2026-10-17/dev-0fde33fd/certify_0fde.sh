#!/usr/bin/env bash
# Certification of dev 0fde33fd: SEC-08 executor check, OUT-1b, RT-2, RT-1 on top of the certified 719c9dcf.
S=/c/Users/ian/AppData/Local/Temp/claude/C--Users-ian-Documents-Projects-smu2sz/aa96fbfb-4038-45c2-8bb9-e28d412a5861/scratchpad
W=/c/Users/ian/Documents/Projects/smu2sz/.claude/worktrees/cert-719c
A=$W/services/api
E=/c/Users/ian/Documents/Projects/smu2sz/.claude/worktrees/sec-fix3/docs/security/evidence
O=$S/cert0fde; mkdir -p $O; : > $O/steps.txt
cd $A
git rev-parse HEAD > $O/commit.txt; git status --porcelain > $O/tree_status.txt
export SKIP_PERF_BENCH=1 PYTHONUTF8=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache
step() { echo "$1 exit=$2 $(grep -E '[0-9]+ (passed|failed|error)' $3 2>/dev/null | tail -1)" >> $O/steps.txt; }
# 1. the four regression tests of this merge, then the suites they live in
DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rfE --tb=short tests/operations/test_sec08_decided_in_log.py tests/security/test_out1b_raw_operations.py tests/security/test_rt2_malformed_documents.py > $O/regressions.txt 2>&1; step regressions $? $O/regressions.txt
for d in operations verifier security persistence; do DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rfE --tb=line tests/$d > $O/t_$d.txt 2>&1; step "tests/$d" $? $O/t_$d.txt; done
# 2. the authorization sweep in three modes
for m in demo prod unset; do SWEEP_MODE=$m uv run --no-sync python $S/authz_sweep_v3.py $O/sweep_$m.json > $O/sweep_$m.txt 2>&1; echo "sweep $m exit=$?" >> $O/steps.txt; done
# 3. every earlier reproduction, the approval flip, OUT-1 scripts
for r in r3 r4_bounded repro1 repro2 repro3; do DEMO_MODE=1 timeout 600 uv run --no-sync python $S/$r.py > $O/$r.txt 2>&1; echo "$r exit=$?" >> $O/steps.txt; done
DEMO_MODE=1 uv run --no-sync python $E/2026-10-14/approval_flip.py > $O/approval_flip.txt 2>&1; echo "approval_flip exit=$?" >> $O/steps.txt
for r in r_nl r_paths r_edge; do DEMO_MODE=1 uv run --no-sync python $E/2026-10-16/dev-b8c65b24/$r.py > $O/$r.txt 2>&1; echo "$r exit=$?" >> $O/steps.txt; done
# 4. the attack catalogue
DEMO_MODE=1 uv run --no-sync python -m app.security.attacks --report > $O/attacks.txt 2>&1; echo "attacks exit=$?" >> $O/steps.txt
cp evals/security/latest_report.md evals/security/latest_report.json $O/; git checkout -- evals/security/latest_report.json evals/security/latest_report.md
# 5. issue #161: its four tests alone
DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rfE --tb=line "tests/operations/test_redteam_d.py::test_f1_negotiate_runs_nothing_from_a_plan_that_cannot_run" "tests/books/test_modules_on_books.py::test_no_commitments_trajectory_and_router_plan_are_unchanged" tests/deals/test_lang.py > $O/issue161.txt 2>&1; step issue161 $? $O/issue161.txt
# 6. PostgreSQL 17: concurrency three times, the guards
for i in 1 2 3; do TERMSLEDGER_TEST_DATABASE_URL="$(sed 's#/postgres$#/termsledger_sectest#' $S/pg_url.txt)" DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rA --tb=line tests/concurrency > $O/pg_concurrency_$i.txt 2>&1; echo "pg concurrency $i: $(grep -E '[0-9]+ (passed|failed)' $O/pg_concurrency_$i.txt | tail -1) postgres-passed=$(grep -c 'PASSED.*postgres' $O/pg_concurrency_$i.txt)" >> $O/steps.txt; done
TERMSLEDGER_TEST_DATABASE_URL="$(sed 's#/postgres$#/termsledger_sectest3#' $S/pg_url.txt)" DEMO_MODE=1 uv run --no-sync pytest -p no:cacheprovider -q -o addopts= -rA --tb=line tests/persistence/test_audit_guards.py tests/operations/test_sec08_decided_in_log.py > $O/pg_guards.txt 2>&1; echo "pg guards: $(grep -E '[0-9]+ (passed|failed)' $O/pg_guards.txt | tail -1)" >> $O/steps.txt
# 7. dependency audits on the merged lockfiles
(cd $W/apps/web && pnpm audit --prod --json > $O/pnpm_audit_prod.json 2>&1; echo "pnpm audit --prod exit=$?" >> $O/steps.txt; pnpm audit --json > $O/pnpm_audit_all.json 2>&1; echo "pnpm audit all exit=$?" >> $O/steps.txt; grep -E '"(next|source-map-js)"' -A2 pnpm-lock.yaml | head -20 > $O/lock_versions.txt)
uv run --no-sync --with pip-audit pip-audit --strict > $O/pip_audit.txt 2>&1; echo "pip-audit exit=$?" >> $O/steps.txt
sed -i -E 's#://[^@ ]*@#://***@#g' $O/*.txt
echo "ALL DONE" >> $O/steps.txt
