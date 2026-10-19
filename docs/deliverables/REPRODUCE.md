# Reproducing FLOW's central results

This guide is for a judge with a clean machine. Every command below was run on the submission build on 19 Oct 2026, and the
expected output beside it is what that run printed (⟦REPRO-DATE⟧). Every command writes new results into `out/`, a folder the
repository ignores, so the submitted evidence is never overwritten. Compare your results with the submitted ones afterwards.

## 1. Get the submission build

Prerequisites: [uv](https://docs.astral.sh/uv/) (it installs Python 3.12), Node.js 22 or newer and pnpm. No API key, account
or network is needed after installation.

```bash
git clone https://github.com/peachoolongtee/smu2sz.git
cd smu2sz
git checkout ⟦FIN-DOCSHA⟧
```

`git log -1 --format=%H` should print `⟦FIN-DOCSHA-FULL⟧`. The product code is that of `⟦FIN-SHA⟧`; the commits after it
change documentation and its build tooling only (`git diff --stat ⟦FIN-SHA⟧ ⟦FIN-DOCSHA⟧ -- services apps` prints nothing).

## 2. The judge pack: the central result in one command (about 2 minutes)

It runs the 49 scripted conversations, the 279-attack catalogue, the 17-step demo walk, and a hash-chain check of the walk's
log, with a tampered copy that must fail. It sets its own environment (in-memory books, recorded model readings, demo
credentials), reads no `.env` file and calls no model provider.

```bash
uv run --project services/api python scripts/judge_eval.py --out out/judge-report.md
```

Expected: exit code 0, and `out/judge-report.md` reports ⟦REPRO-JUDGE⟧. Compare it with the submitted
[`services/api/evals/judge/judge-report.md`](../../services/api/evals/judge/judge-report.md).

## 3. Verify the submitted evidence without running anything

The demo walk's audit log is a hash chain. A standard-library script recomputes every link:

```bash
python scripts/verify_evidence.py docs/deliverables/evidence/demo_walk/operations_log.jsonl
```

Expected: `VALID` ⟦REPRO-VERIFY⟧. The certification evidence is checksummed. On macOS or Linux, from the evidence folder:

```bash
cd docs/security/evidence/2026-10-19/int-⟦FIN-SHA⟧ && tr -d '\r' < SHA256SUMS | sha256sum -c --quiet - && echo ALL-OK; cd -
```

Expected: `ALL-OK`. The folder's `MANIFEST.json` records the commit, the clean tree, the runtime versions and the assessment
window.

## 4. The API test suite (about 25 minutes on 8 cores, longer in one process)

```bash
cd services/api
SKIP_PERF_BENCH=1 uv run pytest -q
cd ../..
```

PowerShell: `cd services/api; $env:SKIP_PERF_BENCH = "1"; uv run pytest -q; cd ../..`

Expected: ⟦FIN-SUITE⟧ (`tests/conftest.py` sets `TERMSLEDGER_NO_DOTENV=1` and `DEMO_MODE=1` itself).

## 5. The scripted tasks and the demo walk, with their evidence chains

```bash
uv run --project services/api python scripts/run_scenarios.py --inproc --out out/e2e
DEMO_MODE=1 PYTHONUTF8=1 TERMSLEDGER_NO_DOTENV=1 uv run --project services/api python scripts/demo_run.py
```

PowerShell, for the second: `$env:DEMO_MODE = "1"; $env:PYTHONUTF8 = "1"; $env:TERMSLEDGER_NO_DOTENV = "1"; uv run --project services/api python scripts/demo_run.py`

Expected: `49/49 scenarios passed` ⟦REPRO-E2E⟧; the walk ends with `RESULT: … cure executed and alert cleared: True`.
`demo_run.py` prints its result and writes no file.

## 6. Run the product

```bash
pnpm --dir apps/web install
pnpm demo
```

Open http://localhost:3000 when the launcher prints `Ready`. It serves the API and the web app on 127.0.0.1 only, with
in-memory synthetic books, recorded model readings and the published demo credentials. Ctrl+C stops both. Other ports:
`pnpm demo --web-port 3141 --api-port 8041`.

## What is not reproduced here

- **Live model mode** (`pnpm demo --live-llm`) needs a model key and is outside the certification. The live runs are in
  [`services/api/evals/live_frozen/`](../../services/api/evals/live_frozen/README.md) and
  [`services/api/evals/live_unseen/`](../../services/api/evals/live_unseen/README.md), with the commands to repeat them.
- **The browser suites** need Playwright's Chromium (`pnpm --dir apps/web exec playwright install chromium`); the commands
  and the counts on the submission build are in [`VERIFICATION_MANIFEST.md`](VERIFICATION_MANIFEST.md).
- **PostgreSQL concurrency** needs a local PostgreSQL 17; the command is in the Security Self-Assessment, Appendix A (E7).
