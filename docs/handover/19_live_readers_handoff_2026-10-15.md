# Handoff, 15 Oct 2026: live-mode readings and opening the books once

Branch `fix/live-readers-and-books-once`, from `dev` at `833d3050`; not merged. The code and its own tests are done; the wider
checks under "Still to run" are not.

## What the branch changes

- **Live mode reads the recordings first** (`app/compiler/service.py`). With `LLM_MODE=live` the chain is now the fixture cache,
  then the models, then the rules grammar. The demo's own messages and documents (all 19 are recorded) replay their recorded
  readings, so they cost no model call and read as they were tested; only text with no recording reaches a model.
- **A model's reading of a buyer message is checked against the rules grammar's** (`app/compiler/cross_check.py`). A term the
  rules read that the model read differently, or missed, is abstained on (`offer.readers_disagree.<TYPE>`; ABSTAINED; not eligible
  for autonomy): nothing is decided on it, the buyer is asked to restate the terms (`app/nl/offers.py`), and the owner gets a
  sentence and the passages (`app/api/presentation.py`). A term only the model read stands. Offers only: contracts and term sheets
  get the recording first but no check.
- **`LLM_LIVE_RAW=1`** (`app/config.py`) turns both off, to measure a model on its own; `scripts/evaluate.py --live` and
  `scripts/evaluate_contracts.py` set it.
- **The books open once** (`app/api/runtime.py`). The first calls after a start each opened a runtime of their own (four at once
  in a simulation; in live mode each read the demo documents through the model). Calls that arrive during an opening now wait and
  share it, or share its error; the next call after a failure opens again; a call made from inside the opening raises
  `StartupError` at once instead of hanging. The opening body is unchanged (now `_open_runtime`), so `fix/setup-guard` (with
  `feat/setup-books`) merges cleanly; checked with `git merge-tree`.
- `docs/SYSTEM_WALKTHROUGH.md`: the two lines on the live chain.

## Checked

- `tests/compiler/test_cross_check.py`, `tests/compiler/test_backends.py`, `tests/api/test_runtime_open.py`: 39 passed.
- Ruff is clean on the changed files. Already there before and left alone: ISC004 in `app/nl/offers.py`, RUF100 in
  `scripts/evaluate_contracts.py`, mypy's "Cannot infer type of lambda" at `app/compiler/service.py:142`.
- The full suite was stopped at about 245 of 8,233 tests, all passing until then.

## Still to run

All offline. **Never call DeepSeek in a test: the owner pays for the key.** The repo-root `.env` holds `LLM_MODE=live` and the
key, so run every command below (Git Bash) with it ignored:

    export TERMSLEDGER_NO_DOTENV=1 LLM_MODE=cache DEEPSEEK_API_KEY= ANTHROPIC_API_KEY= SKIP_PERF_BENCH=1 PYTHONUTF8=1

1. **The backend suite.** On the Windows machine it ran about 10 tests a minute in `tests/api`, so run the folders the branch
   touches first, then the whole suite overnight or in chunks. From `services/api`:

       uv run pytest -o addopts= -q -p no:cacheprovider tests/compiler tests/nl tests/security tests/certification
       uv run pytest -o addopts= -q -p no:cacheprovider tests/api
       uv run pytest -o addopts= -q -p no:cacheprovider tests

2. **The 49 scenarios and the demo script.** From the repo root, then drop the evidence files they rewrite:

       uv run --project services/api python scripts/run_scenarios.py --inproc    # expect 49/49
       uv run --project services/api python scripts/demo_run.py                  # expect exit 0
       git checkout -- services/api/evals

3. **One live run with DeepSeek, only when the owner chooses** (it costs money). Root `.env`: `DEEPSEEK_API_KEY` (or
   `DEEPSEEK_API`), `LLM_MODE=live`, `LLM_PRIMARY=deepseek`. Start the API without `scripts/dev-api.sh` (it ignores `.env` and
   forces cache mode) and with `DATABASE_URL=memory` (otherwise the `.env`'s Supabase URL becomes the database). Expect:
   - at startup, the three demo documents log `compiler.call backend=cache` and nothing logs `backend=deepseek`;
   - a new buyer message logs `compiler.cross_check` with `outcome=agree` or `outcome=disagree`; how often it disagrees is the
     number to watch;
   - a chat question the rules miss ("Am I safe?") answers with `parse_source` `llm:deepseek-flash`.

## Open

- There is no screen to choose between the two readings: the owner sees the passages and a sentence, and the buyer is asked to
  restate the terms.
- `scripts/certify_language_boundary.py` builds its own reader chain, so its runs do not include the check.
- Merge into `dev` with `--no-ff` once 1 and 2 pass; 3 can follow.
