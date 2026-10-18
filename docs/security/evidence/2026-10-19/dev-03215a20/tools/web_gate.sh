#!/usr/bin/env bash
# usage: web_gate.sh <worktree name> <port> <out dir>: the hand-in web gate (docs/agents/integration.md rule 4)
W=/c/Users/ian/Documents/Projects/smu2sz/.claude/worktrees/$1/apps/web; P=$2; O=$3; mkdir -p $O
cd $W || exit 1
E2E_TARGET=mock E2E_PORT=$P pnpm exec playwright test --workers=6 --reporter=line > $O/mock_e2e.txt 2>&1; echo "e2e exit=$? $(grep -E '^\s+[0-9]+ (passed|failed|flaky|skipped)' $O/mock_e2e.txt | tr -s ' ' | tr '\n' ' ')" > $O/web_gate.txt
pnpm typecheck > $O/typecheck.txt 2>&1; echo "typecheck exit=$?" >> $O/web_gate.txt
pnpm lint > $O/lint.txt 2>&1; echo "lint exit=$?" >> $O/web_gate.txt
pnpm test:unit > $O/unit.txt 2>&1; echo "unit exit=$? $(grep -E '^# (pass|fail) ' $O/unit.txt | tr '\n' ' ')" >> $O/web_gate.txt
cat $O/web_gate.txt
