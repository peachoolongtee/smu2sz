# Handoff, 15 to 16 Oct 2026: live-mode readings and opening the books once

Branch `fix/live-readers-and-books-once`, from `dev` at `833d3050`; not merged. The code is done and the offline checks pass
(below); the one check left is a live run with DeepSeek, which is the owner's call because it costs money.

## What the branch changes

- **Live mode reads the recordings first** (`app/compiler/service.py`). With `LLM_MODE=live` the chain is now the fixture cache,
  then the models, then the rules grammar. The demo's own messages and documents (all 19 are recorded) replay their recorded
  readings, so they cost no model call and read as they were tested; only text with no recording reaches a model.
- **A model's reading of a buyer message is checked against the rules grammar's** (`app/compiler/cross_check.py`). A term the
  rules read that the model read differently, or missed, is abstained on (`offer.readers_disagree.<TYPE>`; ABSTAINED; not eligible
  for autonomy): nothing is decided on it, the buyer is asked to restate the terms (`app/nl/offers.py`), and the owner gets a
  sentence and the passages (`app/api/presentation.py`). A term only the model read stands. Offers only: contracts and term sheets
  get the recording first but no check. Whether to check is decided from the reading's model id (`fixture-cache` and `rules-v1`
  are not checked), so every reading still goes through `Compiler._run`, which the certification harness overrides.
- **`LLM_LIVE_RAW=1`** (`app/config.py`) turns both off, to measure a model on its own; `scripts/evaluate.py --live` and
  `scripts/evaluate_contracts.py` set it.
- **The books open once** (`app/api/runtime.py`). The first calls after a start each opened a runtime of their own (four at once
  in a simulation; in live mode each read the demo documents through the model). Calls that arrive during an opening now wait and
  share it, or share its error; the next call after a failure opens again; a call made from inside the opening raises
  `StartupError` at once instead of hanging. The opening body is unchanged (now `_open_runtime`), so `fix/setup-guard` (with
  `feat/setup-books`) merges cleanly; checked with `git merge-tree`.
- `docs/SYSTEM_WALKTHROUGH.md`: the two lines on the live chain.

## Checked (15 and 16 Oct, Windows machine, all offline)

- **The branch's own tests** (`tests/compiler/test_cross_check.py`, `tests/compiler/test_backends.py`,
  `tests/api/test_runtime_open.py`): 39 passed. Ruff is clean on the changed files. Already there before and left alone: ISC004 in
  `app/nl/offers.py`, RUF100 in `scripts/evaluate_contracts.py`, mypy's "Cannot infer type of lambda" at `app/compiler/service.py`
  (the contract-chunk line).
- **The whole backend suite**: 8,179 passed, 13 failed, 41 skipped, in 1 h 28 min on 16 workers (one worker would take many hours
  on this machine). The 13:
  - 6 timing tests that fail only under the parallel load and pass when run alone: `test_ex01_evaluates_under_two_seconds`,
    `test_the_runtime_of_the_day0_curve`, `test_day34_answer_is_fast_when_warm`, `test_two_requests_for_one_key_compute_once`, and
    the cold-read budgets in `tests/api/test_exposure_routes.py` and `tests/api/test_slice_b_round_three.py`;
  - 3 in `tests/certification/test_language_boundary.py`: a regression of this branch (buyer messages had stopped going through
    `Compiler._run`, where the harness records the answering reader), fixed in `Buyer messages go through Compiler._run again`.
    After the fix, `tests/certification` (41) and `tests/compiler` (702) pass;
  - 4 that fail on `dev` at `833d3050` as well, so they are not this branch's: `tests/deals/test_lang.py` (2: "Foshan" is counted
    as English in the Chinese Deals read), `tests/operations/test_redteam_d.py::test_f1_negotiate_runs_nothing_from_a_plan_that_cannot_run`
    (a draw executes after NO_DEAL), and `tests/books/test_modules_on_books.py::test_no_commitments_trajectory_and_router_plan_are_unchanged`
    (the router plan's golden digest).
- **The 49 scenarios**: 49/49, 87 turns. **`scripts/demo_run.py`**: exit 0. Both run again after the fix, same results.

To re-run (Git Bash). The repo-root `.env` holds `LLM_MODE=live` and the DeepSeek key, so ignore it; **never call DeepSeek in a
test: the owner pays for the key.**

    export TERMSLEDGER_NO_DOTENV=1 LLM_MODE=cache DEEPSEEK_API_KEY= ANTHROPIC_API_KEY= SKIP_PERF_BENCH=1 PYTHONUTF8=1
    cd services/api && uv run --with pytest-xdist pytest tests -o addopts= -q -p no:cacheprovider -n 16 --dist loadfile -rfE
    cd ../.. && uv run --project services/api python scripts/run_scenarios.py --inproc --out <a scratch folder>   # 49/49
    uv run --project services/api python scripts/demo_run.py                                                     # exit 0

`--with pytest-xdist` adds the parallel runner for that run only (it is not a project dependency). `--out` keeps the scenario
evidence out of `services/api/evals`; without it, run `git checkout -- services/api/evals` afterwards.

## Left to do

1. **One live run with DeepSeek, only when the owner chooses.** Root `.env`: `DEEPSEEK_API_KEY` (or `DEEPSEEK_API`),
   `LLM_MODE=live`, `LLM_PRIMARY=deepseek`. Start the API without `scripts/dev-api.sh` (it ignores `.env` and forces cache mode) and
   with `DATABASE_URL=memory` (otherwise the `.env`'s Supabase URL becomes the database). Expect:
   - at startup, the three demo documents log `compiler.call backend=cache` and nothing logs `backend=deepseek`;
   - a new buyer message logs `compiler.cross_check` with `outcome=agree` or `outcome=disagree`; how often it disagrees is the
     number to watch;
   - a chat question the rules miss ("Am I safe?") answers with `parse_source` `llm:deepseek-flash`.
2. Merge into `dev` with `--no-ff`; the live run can follow.
3. The four failures already on `dev` (above) belong to their own areas, not to this branch.

## Open

- There is no screen to choose between the two readings: the owner sees the passages and a sentence, and the buyer is asked to
  restate the terms.
- `scripts/certify_language_boundary.py` builds its own reader chain, so its runs do not include the check.
