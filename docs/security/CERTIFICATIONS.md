# Security certifications

Each entry is the Security Lead's sign-off on one exact commit: an internal release decision, not accreditation or a penetration test.
The Security Lead is an AI agent working in a separate session and worktree, and it wrote the security fixes it certifies (see the
self-assessment, section 2.6). A certification covers what is listed under "Evidence" and nothing else; it is not a claim of absolute
security. Scope words follow `RELEASE_GATE.md` (S = local simulation on loopback).

| Date | Commit | What | Verdict |
|---|---|---|---|
| 16 Oct | `0ba8e4c1` (dev) | security fixes 1-5 (SEC-01..05, 09, 10, 16..18) as merged | **CERTIFIED** |
| 16 Oct | `081541d1` via dev head `a6de32a2` | SEC-12/13 headers as merged; all security fixes as they stand on dev with round three and Dylan's UI | **CERTIFIED** (one stale test fixed on `sec/redteam-d-patch-target`) |
| 16 Oct | `8911fb21` (`feat/capex-buy-side`) | CAPEX-1..4 fixes, setup feature | pre-merge: GO to merge dev into it |
| 16 Oct | `b6d1e519` (`int/capex-fixes`: capex buy side + dev `bbbfb7ce` + `fix/capex4-setup1`) | the capex buy side as it would land on dev | **CERTIFIED** for scope S |
| 16 Oct | `0f92d433` (dev) | the owner's decisions on R-11, R-10 and `DEMO_MODE` (`sec/owner-decisions-16oct`), with the capex buy side merged | **CERTIFIED** for scope S |
| 19 Oct | `c66a5e61` (fix/review-20oct: `66c31e7e` + the review fixes REV-1 to REV-3; **the submission build**) | the three fixes and their tests | **CERTIFIED** for scope S; evidence `sha256:37ff16748cf56bca`; REV-4 disclosed (R-7) |
| 19 Oct | `66c31e7e` (int/sl-final: `5926ef29` + the demo stepper fix `cc1703cc`; superseded by `c66a5e61`) | everything since `03215a20` | **CERTIFIED** for scope S (the local simulation, API and web app on 127.0.0.1); every check passes, the live browser suite included |
| 19 Oct | `5926ef29` (int/sl-final: 03215a20 + rounds eight and nine, the demo launcher on loopback, the lint and public-release cleanups) | everything since `03215a20` | **NOT RELEASED**: every check passes except the live browser suite (tracker.spec.ts:216, a timing race in the web demo stepper, older than round nine); fixed in `cc1703cc` and gated again |
| 19 Oct | `03215a20` (dev: round seven merged as `c707ee8c`, code `bee9c50d`; certified, then superseded) | everything since `5941e95a`; the SEC-28 reporting fix re-reviewed | **CERTIFIED** for scope S, on a trusted machine and network (DEMO-L1); SEC-28 with FUND-1 to FUND-4 disclosed |
| 18 Oct | `5941e95a` (dev: the owner pause, funding report, small talk, pay everyone, the consent narrowing, round six) | everything since `70f23ac5` | **NOT CERTIFIED**: every automated check passes, but PAY-1 (Medium, consent bound to a plan not shown) is open; fixed by `sec/round-seven` |
| 18 Oct | `70f23ac5` (dev: round five, the owner-approved engine half) | everything since `6d2b6941` | **CERTIFIED** for scope S; REG-8 (Low) disclosed |
| 18 Oct | `6d2b6941` (dev: batches 7 to 10; round five not merged) | everything since `85309b63` | **CONDITIONAL**: certified for scope S only with `FEATURE_CONTRACT_TERMS` off (CT-1, CT-2 open) |
| 17 Oct | `85309b63` (dev: batches 5 and 6, code of `3f0ed53e`) | everything since `29fa0ea2` | **CERTIFIED** for scope S; ASK-1, ASK-2, REG-1 to REG-7 disclosed |
| 17 Oct | `29fa0ea2` (dev: round four, the redaction fix, self-assessment v3) | everything since `0fde33fd` | **CERTIFIED** for scope S; no test exception |
| 17 Oct | `0fde33fd` (dev: SEC-08 executor check, OUT-1b, RT-2, RT-1, the 719c9dcf records) | the four merged branches | **CERTIFIED** for scope S; one test exception (#161, stale digest pin) |
| 17 Oct | `719c9dcf` (dev: the five round-two branches, the OUT-1 fix, Dylan's ui-final) | everything since `0f92d433`: buyer messages, live readers, the setup lockout fix, the owner-approved engine fixes (`_priced`, `_attribute`, the R-10 rounding), model-privacy redaction, SEC-08 (database), SEC-12, SEC-20, SEC-21, SEC-22, OUT-1 | **CERTIFIED** for scope S |
| 16 Oct | `fe56b357` (dev: final UI, R-10 rounding) | R-10 reassessed; the five round-two branches re-checked on it | R-10: **residual Low**; dev itself not certified while OUT-1 is open |
| 16 Oct | `b8c65b24` (dev: buyer messages on the web, live readers, PG-1 merged, demo launcher) | the changes since `0f92d433` | **NOT CERTIFIED: one blocking finding (OUT-1)**; every automated check passes |
| 16 Oct | `0f92d433` + `7f55c0dc` (PostgreSQL 17) | concurrency invariants and append-only triggers on PostgreSQL | **concurrency CERTIFIED** with PG-1 fixed (branch, pending merge); SEC-08 confirmed open |

## `0ba8e4c1`: CERTIFIED

- The five reviewed branch heads (`sec/intake-hardening` d4aebffe, `sec/attack-harness` eaf525b0, `sec/security-event-growth` 0b1f6f4a,
  `sec/one-agreement-per-request` 8616ee31, `sec/authority-boundaries` 9127aef2) are ancestors of `0ba8e4c1`, and `git diff e6863990
  0ba8e4c1` is **empty**: the commit's tree is byte-identical to `sec/candidate` e6863990, which the Security Lead tested on 14 Oct.
- Evidence (on that identical tree): 31 test shards, all exit 0 except `tests/books/test_modules_on_books.py:207` and
  `tests/deals/test_lang.py:77` (×2), which fail identically on `e8e270f8` without the fixes; attack catalogue 126 API + 133 NL attacks,
  0 with harm; every fix's regression test fails before and passes after.
- Limits: the catalogue attacks 21 of the then 76 routes; the other routes are covered by this audit's targeted tests and the
  authorization sweep, not by the catalogue. "0 of 259 attacks caused harm" must be quoted with that scope.

## `a6de32a2` (dev head, contains `081541d1`): CERTIFIED

- `sec/headers` (6ed44ba5) is an ancestor of `081541d1`; `081541d1` and `0ba8e4c1` are on `origin/dev`. From `081541d1` to `a6de32a2`
  only `app/api/worklist.py` and `app/nl/reads.py` change in `services/api/app` (6 lines).
- Evidence on `a6de32a2` (`evidence/2026-10-16/dev-a6de32a2/`):
  - authorization sweep, 78 API routes plus the docs routes, `DEMO_MODE` on and off: no non-owner role passes an owner route; `/docs`, `/redoc`, `/openapi.json`
    404 with `DEMO_MODE=0`; the bank-feed key gets 403 on `/clock/advance`;
  - the 14 Oct reproductions all refused: anonymous document overwrite 409, oversized intake 413, agent-tripped circuit no longer blocks the
    owner's accept, agent pre-claimed decline key no longer blocks the owner's decline, bank-feed clock 403, one live agreement only;
  - attack catalogue: 126 API + 133 NL attacks, 0 with harm;
  - 31 test shards: all exit 0 except the two pre-existing (`tests/books` digest pin, `tests/deals/test_lang.py`) and
    `tests/operations/test_redteam_d.py::test_f1_negotiate_runs_nothing_from_a_plan_that_cannot_run`.
- That red-team test is **stale, not a regression**: `c51a7284` moved the NO-DEAL plan into `app.api.refusal`; the test still patched
  `app.api.decide.plan`, so it ran the real (runnable) plan and failed without testing the guard. Patched at the new site it passes, and
  it fails when `runnable()` is disabled. Fix: `sec/redteam-d-patch-target` 1b58291f (test only) — merge it so the guard is tested again.
- Scope: catalogue figures cover the routes it attacks; quote "0 of 259 attacks caused harm" with that scope.

## `c66a5e61` (fix/review-20oct): CERTIFIED for scope S, 19 Oct: the submission build

`66c31e7e` plus the three fixes of Hao En's review of the submission build (19 Oct): `90116810` (REV-1, a `COUNTERPARTY` claim on
`POST /operations` is the agent's; REV-2, tokens compared as bytes; REV-3, a queued buyer message is answered without the word
"acceptance") and `c66a5e61` (two chat tests updated to the REV-3 wording). A first gate on `90116810` was stopped when those two
tests failed in `tests/nl`; it is not evidence. The documentation commits after `c66a5e61` change documents, evidence and the
document build tooling only.

**Evidence:** [int-c66a5e61/](evidence/2026-10-19/int-c66a5e61/), id `sha256:37ff16748cf56bca` (the sha256 of its `SHA256SUMS`,
LF line endings); gate 19 Oct 2026, 08:41 to 09:33 UTC, on a clean detached checkout. Sandbox runs on the same code:
`run-20261019T093629Z-inproc` and `run-20261019T093658Z-http` in `docs/deliverables/evidence/sandbox-2026-10-19/`.

| Check | Result |
| --- | --- |
| API suite (155 processes) | 11,426 passed, 0 failed, 47 skipped |
| Attack catalogue | 279 cases, 0 harm, 0 not reached; 120 of 128 named controls; detection 97.66% (API), 70.25% (all) |
| Route policy; credential sweep in three modes | 16 tests over 113 routes; 0 policy violations; 0 differences from `66c31e7e` |
| Reproductions; approval flip | refused, as on `66c31e7e` |
| Language boundary | 0 wrong-and-material (cache and fake) |
| PostgreSQL 17 | concurrency 3 of 3; audit guards 10 passed |
| Audits; secret scan | pip-audit clean; `pnpm audit --prod` 0; `braces` only (development, the approved exception); 0 secret findings |
| Mock browser; typecheck, lint, unit | 479 passed, 0 failed, 77 skipped; pass; 197 unit tests |
| Live browser (one worker) | 177 passed, 0 failed, 51 skipped |
| CSP (production build and `pnpm demo`) | 17 pages each, 0 violations, injection blocked |
| Judge pack | 49 of 49; 279 attacks, 0 harm; audit chain VALID |
| Sandbox | in process 159 passed, 0 failed; over HTTP 142 passed, 0 failed, 1 skipped; every export VALID |

**Verdict: CERTIFIED for scope S.** Disclosed, open: R-7 (Moderate) and REV-4 (a reversed payer or a wholly quoted buyer message
is accepted at Tier 1 as the plain discount; found in Hao En's review of `feat/reader-dates`, which is NO-GO for the submission).
The REV-4 fix (`fix/rev4-coverage`) is outside this build. Local paths in the outputs were replaced before sealing
(`tools/scrub_paths.py`).

## `66c31e7e` (int/sl-final, then `dev`): CERTIFIED for scope S, 19 Oct

`5926ef29` (round eight, the demo launcher on loopback, round nine, the API lint and public-release cleanups, the unseen
evaluation set) plus `cc1703cc`, the fix of the demo stepper race that kept `5926ef29` from release. Product code is identical
to `5926ef29` apart from three web files and a web unit test. The documentation commits after it change documents, evidence and
the document build tooling only (`git diff 66c31e7e <tag> -- services/api/app apps/web` is empty).

Evidence: `evidence/2026-10-19/int-66c31e7e/` (`summary.txt`, `tools/`, `MANIFEST.json`, `SHA256SUMS`; id
`sha256:4a418fe4fb4c6c4d`). The gate ran 05:55 to 06:41 UTC and the post-gate checks to 06:46, on a quiet machine.

| Check | Result |
| --- | --- |
| Full suite (155 test processes) | **11,421 passed, 0 failed, 47 skipped**; `tests/__pycache__` ran no tests (exit 5) |
| Attack catalogue | 128 API + 151 chat cases, 0 with harm, 0 NOT_REACHED; 120 of 128 stopped by the named control, 8 known gaps; detection 97.66% (API), 70.25% (all) |
| Route policy | 16 tests pass over 113 routes; owner 96 of 97 (demo mode), 91 of 97 (`DEMO_MODE=0`); the one miss is `POST /documents/{id}/terms/undo` → 404 `UNKNOWN_SET_UP` |
| Sweep, three modes | 112 routes, 0 policy violations, 0 differences from `03215a20` |
| Reproductions; approval flip | refused, outputs identical to `03215a20` apart from timestamps; the database refuses the flip |
| Language boundary | 0 wrong-and-material (cache and fake) |
| PostgreSQL 17 | concurrency 3 of 3; guards 10 passed |
| Dependency scans | `pip-audit` clean; `pnpm audit --prod` 0; `braces` only (development, accepted) |
| Secret scan | 0 findings in the tracked files at `66c31e7e` and every branch's history |
| Mock browser suite | 479 passed, 0 failed, 77 skipped; typecheck, lint pass; web unit 197 passed |
| Live browser suite (one worker, as configured) | **177 passed, 0 failed, 51 skipped** |
| CSP | production build and the development server `pnpm demo` runs: 17 pages each, 0 violations, injection blocked; the development server adds `'unsafe-eval'` |
| Judge pack | 49 of 49 tasks (88 turns); 279 attacks, 0 harm; demo walk OK; audit chain VALID |
| Sandbox (execution evidence) | in process 159 passed, 0 failed, exports 16 of 16 VALID; over HTTP against the API as `pnpm demo` starts it 142 passed, 0 failed, 1 skipped (in-process only), exports 13 of 13 VALID |
| Live model, unseen set (uncertified evidence) | rules 1/6 correct; shipped path 2/6; model alone 2/6; 0 wrong in all (`services/api/evals/live_unseen/`) |

**Verdict: CERTIFIED for scope S.** An internal release decision for the local simulation: `pnpm demo` on one machine, the API
and the web app on 127.0.0.1, one API process, `DEMO_MODE=1`, in-memory books, `LLM_MODE=cache`, synthetic data, contract terms
and the router as the launcher sets them. Live model mode, any network or hosted deployment and production are outside it.
Disclosed: SEC-28 (plans not reversed; FUND-4 wording), PAUSE-2 and PAUSE-Q, SEC-27, SEC-19 (the chat reply), CAPEX-ACCT, OPT-B,
LOG-3 and the open risks of the self-assessment, whose ratings are unchanged. Not a claim of absolute security.

## `5926ef29` (int/sl-final): NOT RELEASED, 19 Oct; a failure in the live browser suite

Since `03215a20`: round eight (FUND-1, FUND-2, FUND-3, FUND-5), the demo launcher on loopback (DEMO-L1), round nine (LOG-2,
SEC-19 display, CON-1 and pinned authority tests), the API lint cleanup, the public-release cleanup and the unseen evaluation set.
An intermediate gate on `eb3c1059` (before round nine) is not a release; its live browser run used four workers against one
shared API, which the suite is not built for, and is not cited.

Evidence: `evidence/2026-10-19/int-5926ef29/` (`summary.txt`, `tools/`, `bisect/`, `MANIFEST.json`, `SHA256SUMS`; id
`sha256:1c728920b7f4559b`). The gate ran 04:14 to 05:05 UTC, the post-gate checks to 05:06.

| Check | Result |
| --- | --- |
| Full suite (155 test processes) | 11,421 passed, 0 failed, 47 skipped; `tests/__pycache__` ran no tests (exit 5) |
| Attack catalogue | 279 cases, 0 with harm, 0 NOT_REACHED; 120 of 128 API cases stopped by the named control, 8 known gaps; detection 97.66% (API), 70.25% (all) |
| Route policy; sweep in three modes | 16 tests pass over 113 routes; 0 policy violations; 0 differences from `03215a20` |
| Reproductions; approval flip | refused; the database refuses the flip |
| Language boundary | 0 wrong-and-material (cache and fake) |
| PostgreSQL 17 | concurrency 3 of 3; guards 10 passed |
| Dependency and secret scans | `pip-audit` clean; `pnpm audit --prod` 0; `braces` (development only); secret scan 0 findings in the tree and every branch's history |
| Mock browser suite | 479 passed, 0 failed, 77 skipped; typecheck, lint, unit pass |
| **Live browser suite** (one worker, as configured) | **176 passed, 1 failed, 51 skipped**. `tracker.spec.ts:216` ("after the owner's approval the page's figures are the API's own") fails, also alone. A bisect first pointed at `a12548fd` (round nine, LOG-2), but reverting that commit does not remove the failure: the cause is a timing race in the web demo stepper (its next button re-enabled before the story read settled, so a quick press re-ran the step and the walk ended one step short of the approval). It predates round nine and shows only under load |
| CSP, production build and development server | 17 pages each, nonce on all, 0 violations, injection blocked; the development server adds `'unsafe-eval'` for hot reload |
| Judge pack | 49 of 49 tasks; 279 attacks, 0 harm; demo walk OK; audit chain VALID |

**Verdict: NOT RELEASED.** The race leaves the web demo one step short of the owner's approval, inside scope S; the books are
not affected (the API replays the same calls correctly). It is fixed in `cc1703cc` (`sec/round-nine-fix`: the next button waits
for a settled story read), with a web unit test that fails before the fix, and the fixed build is gated again before any release.

## `03215a20` (dev): CERTIFIED for scope S, 19 Oct

Since `5941e95a`: round seven (`sec/round-seven` `bee9c50d`, merged as `c707ee8c`), which fixes PAY-1 to PAY-3, PAUSE-1 and APR-1
and regenerates the attack report (NL-AC02 now HELD, LOG-3). The commits after `c707ee8c` change documentation, the document
builder and recorded evaluation outputs only: no file under `services/api/app`, `apps/web` or the tests differs from `bee9c50d`.

Evidence: `evidence/2026-10-19/dev-03215a20/` (`summary.txt`, `tools/certify_0321.sh`, `MANIFEST.json`, `SHA256SUMS`; id
`sha256:712d6bd18b80e1ef`). The run took 16:59 to 17:26 UTC on 18 Oct, stopped when the session closed after the third
reproduction, and resumed on the same clean checkout at 23:27 from the approval flip; the CSP check and the secret scan came after.

| Check | Result |
| --- | --- |
| Full suite (155 test processes) | **11,368 passed, 0 failed, 47 skipped**. One extra shard, `tests/__pycache__`, ran no tests (exit 5) |
| Attack catalogue | 128 API + 151 chat cases, 0 with harm; 0 NOT_REACHED; 120 of 128 API cases stopped by the named control, 8 known gaps; detection 97.66%, security events 74.22% |
| Route-policy test | 16 tests pass over 113 routes; the owner reaches the handler on 96 of 97 owner and demo routes in demo mode and on 91 of 97 with `DEMO_MODE=0`. The one miss in both modes is `POST /documents/{id}/terms/undo`, which answers 404 `UNKNOWN_SET_UP` because the test world holds no set-up to undo; it is not a feature flag |
| Sweep, three modes | 0 policy violations over 112 routes; the only difference from `70f23ac5`: the three pause routes, refused to every caller but the owner |
| Reproductions; approval flip | refused, output identical to `70f23ac5` apart from timestamps; the database refuses the flip |
| Language boundary | 0 wrong-and-material (cache and fake), counts identical to `70f23ac5` |
| PostgreSQL 17 | concurrency 3 of 3; guards 10 passed |
| Dependency scans | `pnpm audit --prod` 0; `braces` (development only); `pip-audit` clean |
| Secret scan | tracked files at `03215a20` and the history of every branch: 0 findings; only the two `.env.example` files are tracked |
| Mock browser suite | 479 passed, 77 skipped; typecheck, lint, unit pass |
| CSP, production build (the flags `pnpm demo` sets) | 17 pages, nonce policy on every page, 0 violations, 0 page errors, injections blocked |
| Code review | round seven was reviewed on its branch (18 to 19 Oct). The SEC-28 reporting fix (`f52870d1`) was reviewed on this build: queued and refused legs are now reported as they are on `/negotiate`, `/alerts/{id}/act` and the chat paths, and the commit changes no engine module. Still misreported: FUND-1 (Medium: a send with no admissible funding plan reads FUNDED), FUND-2 (Medium: the web's send result says the agreement is on the books while it waits for approval or was refused), FUND-3 (Low / Medium: chat "no gap to cover" with a gap open) and FUND-4 (Low). All four are in `70f23ac5` too; they are the remainder of SEC-28, which that build was certified with as a disclosed risk. Nothing runs without the owner's approval on these paths. Fixes for FUND-1 to FUND-3 are on `sec/round-eight` |

**Verdict: CERTIFIED for scope S.** This is an internal release decision for the local simulation, with contract terms and the
router on as `pnpm demo` sets them, on a trusted machine and network (DEMO-L1: the launcher serves the web app on every interface;
fix on `sec/demo-loopback`). Live model mode is excluded. Disclosed: SEC-28 with FUND-1 to FUND-4 (its reporting is partly fixed,
not closed), PAUSE-2 (one process required), SEC-27, LOG-2, LOG-3, CT-2b beyond the borrower file, and the open risks of the
self-assessment, whose ratings are unchanged from `70f23ac5`: the pause limits but does not revoke a mandate (R-14), and a part-run
plan is still not reversed (SEC-28). Not a claim of absolute security.

**Found after the verdict (19 Oct): FUND-5** (Low / Medium), the same misreport as FUND-3 in the early-settlement chat ("no
fallback needed", "no gap to fund" with a gap open). It is in `70f23ac5` too, part of the disclosed SEC-28, and does not change
the verdict. The fix is on `sec/round-eight`.

## `5941e95a` (dev): NOT CERTIFIED, 18 Oct; superseded by round seven

Since `70f23ac5`:
- round six;
- the owner's pause of the agent (`/agent/pause`, `/agent/resume`);
- the funding report and claims wording;
- small talk, "Can I pay everyone?" and the consent narrowing;
- a wording change in `verifier/counters.py`;
- `verify_evidence --checkpoint-save`;
- the LICENSE.

Evidence of the run is in the Security Lead's scratchpad (`cert5941`); it is not committed, because the build is not certified.

**Automated checks:** all pass.

| Check | Result |
| --- | --- |
| Full suite | 11,341 passed, 0 failed |
| Catalogue | 0 harm on 279 cases |
| Sweep | 0 policy violations; only the three pause routes are new, and every non-owner is refused on them |
| Language boundary | 0 wrong-and-material |
| PostgreSQL | 3 of 3 |
| Scans | clean |
| Mock browser suite | 479 passed |

**Code reviews:**
- **Sound:** the consent grammar narrowed and did not widen; the pause is owner-only, enforced in front of the executor (it wraps `Executor.execute`; corrected 19 Oct from "in the executor"), survives a restart and is chained; all 16 verdicts and the golden values are identical to `70f23ac5`; `verify_evidence` is not weakened.
- **Found:**
  - PAY-1 (Medium): "Can I pay everyone?" showed one plan and saved another, and "go ahead" ran the saved one;
  - PAY-2 and PAY-3 (Low);
  - PAUSE-1 (Low / Medium): the bank-feed key could still draw while the agent was paused;
  - APR-1 (Low);
  - PAUSE-2 (open; one process required);
  - LOG-2 and LOG-3 (Info).

**Verdict: NOT CERTIFIED.** `sec/round-seven` (bee9c50d) fixes PAY-1 to PAY-3, PAUSE-1 and APR-1. Its gate: full suite 11,368 passed, 0 failed; mock 479 passed. Its merge commit is the next build to certify.

## `70f23ac5` (dev): CERTIFIED for scope S, 18 Oct (amended 19 Oct: DEMO-L1 applies, see the release gate)

Since `6d2b6941`:
- round five, `sec/batch-r5` with `sec/router-guards`, which fixes every finding of the reviews of batches 5 to 10 (ASK-1 to ASK-2b, RT-L1 to RT-L3, REG-1 to REG-6, CT-1 to CT-5, WARM-1, DEMO-2 and SEC-29's owner path);
- the owner-approved engine commit `1c49ce5e` (`fix/r5-engine`), covering CT-2, CT-6, CT-7 and REG-5's executor half;
- the integration owner's lead fixes: Ask FLOW's customer names (superseded by `e19f7d29`), and the demo lender agreements uploaded unchanged (`_demo_upload_names`);
- the structlog test isolation;
- the REG-1 parity tests;
- the certification records of `docs/certify-29fa`.

Evidence: `evidence/2026-10-18/dev-70f23ac5/` (`certify_70f2.sh`, `MANIFEST.json`, `SHA256SUMS`; id `sha256:3fd43dcd8ffc4721`). The run took 04:58 to 05:45 UTC; the CSP check came after it.

| Check | Result |
| --- | --- |
| Full suite (146 test processes) | **10,674 passed, 0 failed, 47 skipped**. One extra shard, `tests/__pycache__`, ran no tests (exit 5) |
| Attack catalogue | 128 API + 151 chat cases, 0 with harm; 0 NOT_REACHED; 120 of 128 API cases stopped by the named control, 8 known gaps |
| Sweep, three modes | 0 policy violations; one intended difference from `6d2b6941`: the owner's contract-terms undo no longer waits on `FEATURE_CONTRACT_TERMS` (CT-6) |
| Reproductions; approval flip | refused; the database refuses the flip |
| Language boundary | 0 wrong-and-material (cache and fake) |
| PostgreSQL 17 | concurrency 3 of 3; guards 10 passed |
| Dependency scans | `pnpm audit --prod` 0; `braces` (development only); `pip-audit` clean |
| Mock browser suite | 479 passed, 77 skipped; typecheck, lint, unit pass |
| CSP, production build (contract terms and the router on) | 16 pages, 0 violations, 0 page errors, injections blocked |
| Code review of the delta | the engine commit is sound: a set-up stays out of the conservative forecast until its first issue, nothing else confirms it, the flag and owner gates run first, and the golden hashes are identical to `6d2b6941`. The amended tests keep their properties. The review found REG-8, REG-9 and CT-2b, fixed on `sec/round-six` and not in this build |

**Verdict: CERTIFIED for scope S.** This is an internal release decision for the local simulation, with contract terms and the router on as `pnpm demo` sets them, and live model mode excluded. Disclosed: REG-8 (Low), REG-9 (Info), CT-2b (Low, partly accepted design), SEC-27 and SEC-28 (deferred by the owner), and the open risks of the self-assessment. Not a claim of absolute security.

## `6d2b6941` (dev): CONDITIONAL, 18 Oct

Batches 7 to 10 since `85309b63`:
- ADR-0014 contract terms, an engine change;
- contracts on Deals, file-first upload and record a payment;
- the owner-question router (ADR-0015, proposed, `FEATURE_ASK_ROUTER`), the answer cards and the question gate;
- the strategy warm-up worker;
- fixes from the demo recording.

Round five (`sec/batch-r5`, `sec/router-guards`) is **not** in this commit. Evidence: `evidence/2026-10-18/dev-6d2b6941/`.

Every automated check passes:

| Check | Result |
| --- | --- |
| Full suite | 10,375 passed, 0 failed |
| Catalogue | 0 harm; 120 of 128 API cases stopped by the control they name |
| Sweep | 0 policy violations |
| Language boundary | 0 wrong-and-material |
| PostgreSQL | 3 of 3 |
| Dependency scans | clean |
| Mock browser suite | 479 passed, 77 skipped. A first run failed because the Security Lead's own test run had taken the port; it was re-run on a free one |
| CSP in a browser | 0 violations |

The code reviews found nothing Critical or High: the router is owner-only and read-only, record a payment is gated, and no route was added. They also found these, open in this commit:
- **Medium:** CT-1 and CT-2 (contract terms can be set up with no certain end and no bound, and switch off reserve alerts), and ASK-1 (an agent-key Tier-3 request phrased as a question leaves no trail).
- **Low:** ASK-2 and ASK-2b, CT-3 to CT-7, REG-1 to REG-6, RT-L1 to RT-L3, WARM-1, and SEC-29's owner path.

**Verdict: CONDITIONAL.** Certified for scope S **only with `FEATURE_CONTRACT_TERMS` off**; `pnpm demo` turns it on, so demonstrating this commit means turning that flag off. Merge `sec/batch-r5` with `sec/router-guards` and certify that merge commit as the assessed build. The self-assessment v3 stays on `85309b63` until then.

## `85309b63` (dev): CERTIFIED for scope S, 17 Oct

Batches 5 and 6:
- `fcc81a62`: Dylan's Attach page, the party check `PARTY_NOT_NAMED`, the demo inbox, the set-aside count, `--keep`, the outcome card, deals invoices without a contract;
- `3f0ed53e`: `POST /customers` (ADD_CUSTOMER), `POST /documents/{id}/refile` (REFILE_DOCUMENT), `POST /nl/session/reset`, owner questions (ASK_BOOKS, the read-only `app/nl/answers`), DOC-05, PC-06;
- then the technical document (`85309b63`, docs only; the code is that of `3f0ed53e`).

Evidence: `evidence/2026-10-17/dev-85309b63/` (script `certify_8530.sh`). The run took 14:01 to 14:38 UTC; the CSP check came after it.

| Check | Result |
| --- | --- |
| Full suite (135 processes) | **9,740 passed, 0 failed, 46 skipped** |
| Attack catalogue | 128 API + 133 chat, 0 with harm; 0 NOT_REACHED; 120 of 128 API cases stopped by the named control, 8 known gaps |
| Sweep, three modes | 0 policy violations; against `29fa0ea2` only the three new routes differ: every non-owner gets 401 on `POST /customers` and `/documents/{id}/refile`, and `POST /nl/session/reset` is open as a buyer channel |
| Route policy test (in the suite) | 107 routes; no class disagreement; the owner reaches the handler on 91 of 91 in demo mode and 86 of 91 in production mode |
| Reproductions; approval flip | refused; the database refuses the flip |
| Language boundary | 0 wrong-and-material (cache and fake) |
| PostgreSQL 17 | concurrency 3 of 3; guards 10 passed |
| Dependency scans | `pnpm audit --prod` 0; `braces` (development only); `pip-audit` clean |
| Mock browser suite | 453 passed, 71 skipped; typecheck, lint, unit pass |
| CSP, production build | 16 pages with the nonce policy, 0 violations, 0 page errors, injections blocked |
| Code review of the new routes and owner questions (two reviewer agents, probes in the scratchpad) | nothing Critical or High; ASK-1 to ASK-3 and REG-1 to REG-7 recorded in the register |

**Verdict: CERTIFIED for scope S.** It is certified with the review findings disclosed. None lets a non-owner act or read: each needs an owner action, the agent key, or a document the owner uploads. Fixes are built in round five and are not in this build.

## `29fa0ea2` (dev): CERTIFIED for scope S, 17 Oct

The build the self-assessment v3 describes. Contents since `0fde33fd`:
- the redaction fix (`sec/redaction-mandatory` 817bcaad, PRIV-1 to PRIV-3), via `975e082f`;
- Dylan's Attach deals and the capex hub (web only; `pnpm demo` turns on `FEATURE_CAPEX_CONTRACTS`, the buy side certified on `b6d1e519`);
- self-assessment v2, then v3 (`e103bab8`);
- round four:
  - `sec/refusal-budget` 089ff973;
  - `sec/evidence-verifier` aa050d85;
  - `sec/anonymous-intake-switch` d8d22332;
  - `sec/harness-assurance` 28133edc;
  - `sec/route-policy` 3c4bd9ed;
  - `e658ba64` cherry-picked alone.

Every branch head is an ancestor of `29fa0ea2`; `e658ba64` came in as its cherry-pick `fda20f6a`. Since `0fde33fd` the backend changes are exactly those branches. The web changes are layout, a sign-in animation (`lib/ripple.ts`, inline styles set through the CSSOM, allowed by the CSP) and routing, with no change to `proxy.ts` or `lib/csp.ts`.

Evidence: `evidence/2026-10-17/dev-29fa0ea2/` (script `certify_29fa.sh`, `MANIFEST.json`, `SHA256SUMS`). The run took 10:51 to 11:37 UTC.

| Check | Result |
| --- | --- |
| Full suite, one process per test directory and per `tests/api` file (130 processes) | **9,116 passed, 0 failed, 44 skipped**; no shard non-zero; #161 passes |
| Attack catalogue | 127 API + 133 chat cases, 0 with harm; 0 NOT_REACHED; 119 of 127 API cases stopped by the control they name, 8 known gaps (SEC-34) |
| Positive controls, mutation tests, route policy test (in the suite) | pass: 5 controls execute and the oracle sees them; every mutation detected or recorded; 0 route policy deviations |
| Authorization sweep, three modes | 0 policy violations; 0 differences from `0fde33fd`, caller by caller |
| Reproductions | all refused (the scripts that exit 1 crash on the refusal; see below) |
| SQLite approval flip, run correctly | refused by the database: "approvals: a decision is recorded once; UPDATE refused" |
| Language boundary, 231 items | cache: 0 wrong-and-material (1 wrong-harmless); fake: 0 wrong-and-material (3 wrong-harmless) |
| PostgreSQL 17 | concurrency 3 of 3 clean (31 passed, 10 on PostgreSQL each); guards and the SEC-08 executor test 10 passed |
| `pnpm audit --prod` | 0 advisories |
| `pnpm audit` including development | 1 high, `braces` (lint tooling only, no patch) |
| `pip-audit` (production dependencies) | no known vulnerabilities |
| Mock browser suite | 445 passed, 61 skipped; typecheck, lint, unit pass |
| CSP on a production build (live API on loopback) | 16 pages with the nonce policy, `strict-dynamic` and `frame-ancestors 'none'`; 0 violations, 0 page errors; an injected `onerror` handler and a `javascript:` URL blocked (`csp_browser.json`) |

**Verdict: CERTIFIED for scope S.** This is an internal release decision for the local simulation, with the conditions in `RELEASE_GATE.md`. A network demo stays NO-GO until a deployment profile is tested; production stays NO-GO.

**Correction to the `719c9dcf` and `0fde33fd` entries.** In both runs `approval_flip.py` never started, because it needs a scratch folder argument and none was passed. Its exit status 1 was read as a refusal. The database guard was covered on both commits by `tests/persistence/test_audit_guards.py` on SQLite and PostgreSQL 17. On `29fa0ea2` the script ran correctly and was refused.

## `0fde33fd` (dev): CERTIFIED for scope S, 17 Oct

Covers the merge of `security/lead-audit` 4cdda790, `sec/decide-once-log` 2ebb59d0, `sec/out1b-raw-operations` f3392196,
`sec/offers-422` 3158c81c and `sec/next-16-3-8` ce7791bd; all five heads are ancestors of `0fde33fd`. Evidence:
`evidence/2026-10-17/dev-0fde33fd/` (script `certify_0fde.sh`, results `steps.txt`). Unlike earlier entries, counts are recorded.

| Check | Result |
| --- | --- |
| The merged regression tests (SEC-08 executor, OUT-1b, RT-2) | 22 passed |
| tests/operations, verifier, security, persistence | 412 passed 1 skipped; 263 passed; 305 passed; 161 passed 1 skipped |
| Authorization sweep, 103 routes, three modes | 0 policy violations (`tools/sweep_policy.py`); 0 differences from `719c9dcf`, caller by caller (`tools/sweep_diff.py`). Owner answers: 43 to 47 reach a handler (200); the rest stop at validation on the sweep's placeholder ids and empty bodies, so the sweep shows who is refused, not that each owner route works |
| 14 and 16 Oct reproductions | all refused. `r3`, `repro1` and `repro3` exit 1 because they crash printing what a successful attack would have returned (for example `r3` gets 409 and has no offer to print); each output shows the refusal |
| Attack catalogue | 126 API + 133 chat cases, 0 with harm |
| Issue #161 tests alone | 1 failed, 32 passed: `test_no_commitments_trajectory_and_router_plan_are_unchanged`, computed `24f1dc649f4363e3`, pinned `252b9812e99b4aee`. The same value on Linux CI: a stale pin, not machine-dependent as recorded earlier. Cause: "1 days" became "1 day" in one menu display string (`61eb4576`, 13 Oct); nothing the executor uses changed. Golden update `e658ba64` exists on `ci/linux-green` only |
| PostgreSQL 17 | concurrency 3 of 3 clean (31 passed, 10 on PostgreSQL each); guards and the SEC-08 executor test 10 passed |
| `pnpm audit --prod` (apps/web lockfile, `next` 16.3.8, `source-map-js` 1.2.2) | 0 advisories |
| `pnpm audit` including development | 1 high: `braces` (GHSA-vfj7-8cjw-p6xm) via `eslint-config-next` > `fast-glob` > `micromatch`; lint tooling only, no patched version |
| `pip-audit` (production dependencies exported from `uv.lock`) | no known vulnerabilities |

Not re-run here: the full sharded suite and the mock browser suite (the integration owner's gate reports API 9,024 passed with only #161,
mock 444/0), the CSP browser check (to be repeated on the assessed build) and the language-boundary set (no change in its path).

**Verdict: CERTIFIED for scope S**, with the #161 exception. Conditions unchanged.

**Correction to the `a6de32a2` entry.** It says the patched red-team test "fails when `runnable()` is disabled". That was checked by hand
on 16 Oct; no committed test disables `runnable()`.

## `719c9dcf` (dev): CERTIFIED for scope S, 17 Oct

Covers everything since the last certified commit `0f92d433`: buyer messages on the web and live readers (`b8c65b24`), the setup lockout
fix (`049ec6a3`), the owner-approved engine fixes `_priced` (`app/alerts/engine.py`), `_attribute` (`app/funding/search.py`) and the R-10
rounding (`app/verifier/counters.py`), model-privacy redaction, the five round-two branches (SEC-08 database part, SEC-20, SEC-22,
SEC-21, SEC-12), the OUT-1 fix (`fix/out-1` ac838334) and Dylan's ui-final. Merged heads checked: all five branch heads and `ac838334`
are ancestors of `719c9dcf`. Evidence: `evidence/2026-10-17/dev-719c9dcf/`.

| Check | Result |
| --- | --- |
| Authorization sweep, 103 routes × 7 callers, `DEMO_MODE` on, off and unset | identical to the `b8c65b24` baseline in all three modes: no non-owner caller reaches an owner route |
| 14 Oct reproductions (`r3`, `r4_bounded`, `repro1..3`) | all refused, as on `b8c65b24` |
| SEC-08 approval flip (SQLite) | the database refuses the flip ("a decision is recorded once"); PostgreSQL 17 guard tests 4 of 4 |
| OUT-1 (`r_nl.py`, `r_paths.py`; `tests/nl/test_sent_outside.py`) | **fixed**: every chat wording, owner and agent, runs no operation and books no commitment; `/negotiate` 409 `OFFER_SENT_OUTSIDE`; the guard is in each chat entry point (offers, pipeline, and `run_accelerate` for a confirmed early-pay plan) and again in the builders `accept`, `reject`, `send_counters` and `run_negotiation`; the team's 12 regression tests pass, including direct calls to the builders |
| OUT-1 by the raw route (`out1_raw_ops.py`) | RejectOffer and CounterOffer still execute through `POST /operations`: **OUT-1b, Low, open** (no agreement, no money) |
| Attack catalogue (126 API + 133 NL) | 0 with harm |
| Full API suite by directory | every shard passes except the known #161 hash pin in `tests/books`; tests/api 1,729 passed, 2 skipped |
| PostgreSQL 17 concurrency | 3 of 3 clean runs, 31 passed, 10 on PostgreSQL each |
| Content-Security-Policy, production build, in a browser | the nonce policy on every page; 15 Business pages, sign-in and the chat with 0 violations and 0 page errors; injected `<img onerror>` and `javascript:` blocked (`csp_browser.json`) |
| Mock browser suite | 444 passed, 61 skipped; typecheck, lint, test:unit pass (run by the Security Lead) |
| Engine fixes `_priced`, `_attribute` | presentation and attribution only: the executor's rate gate (`funding/admission.py`, `rates.py`) is unchanged since `0f92d433`, so a draw above the ceiling still waits for the owner |
| Setup lockout (`049ec6a3`) | a refused sign-in no longer counts as use of the blank books; only `log_refusal` writes the `SEC-AUTH-` prefix; residual SETUP-8 (Info) |
| Model-privacy redaction | PRIV-1, PRIV-2, PRIV-3 re-checked: **unchanged, still open** (live certification script unredacted; a labelled address swallows its sentence; two digits read as a phone or account) |

**Verdict: CERTIFIED for scope S.** Conditions as before: loopback, the presenter alone holds the demo credentials, simulated buyers,
`LLM_MODE=cache`. **Not for live mode with real customer documents** until PRIV-1 to PRIV-3 are fixed. Open and not blocking: OUT-1b,
OUT-2, OUT-3, OUT-4, DEMO-L1, SETUP-8, RT-1 to RT-3, the SEC-08 executor check (built, `sec/decide-once-log`, pending merge), and the items
the owner deferred past the deadline (SEC-11, R-2, R-14, the capex cancel path, CAPEX-4b, SETUP-2/3/6, SEC-22 derived values).

## R-10 reassessed on `fe56b357` (the early-pay counter's face), 16 Oct

**Change** (`2ab66177`, `app/verifier/counters.py`, owner-approved engine change): the early-pay counter's face is the gap net of the
committed line, rounded **up** to a step of two significant figures of the invoice's outstanding amount, at most that amount; if that
face fails its re-check, the whole outstanding amount is tried; otherwise no Option A. The ¥100 rounding is gone. Golden books:
¥257,200 becomes ¥260,000.

**Checked:** code read; `early_pay_step` evaluated; the API suite on dev (`fe56b357`) and on the branches merged with it.

| Outstanding amount | Step |
| --- | --- |
| below ¥10,000 | ¥100 |
| ¥10,000 to ¥99,999.99 | ¥1,000 |
| ¥100,000 to ¥999,999.99 | **¥10,000** |
| ¥1,000,000 to ¥9,999,999.99 | ¥100,000 |

**Verdict.** The face no longer gives the gap back to the ¥100: a buyer reading it learns only that the gap (net of the line) lies
within one step below it, about 1% to 10% of the invoice. Residual, **Low** for scope S: (1) the counter's rate still shows the
counter cap (break-even), as before; (2) a keyed buyer asking on several days can watch the face move by whole steps, bounded by
the 5 attempts per buyer per day; (3) a face equal to the whole outstanding amount says the gap is at least that large.
**Note for the owner:** the decision was "the nearest ¥10,000"; the code uses two significant figures, which is ¥10,000 only for
invoices of ¥100,000 to ¥999,999.99 (the demo's). Smaller invoices get finer steps (¥1,000, or ¥100 below ¥10,000). If a fixed
¥10,000 floor is wanted: `step = max(10 ** (digits - 2), 1_000_000)` fen, capped at the outstanding amount (engine change, owner's
call). Not blocking.

## `b8c65b24` (dev): NOT CERTIFIED, 16 Oct; blocked by OUT-1 only

New since `0f92d433`: buyer messages on the web (`a2e1d174`: `app/api/outbound.py`, `outbound_record.py`, `app/outbound/`), live mode
replaying the recorded readings first (`4841ab5b`), PG-1 and the security docs merged, and the Windows demo launcher (`scripts/demo.mjs`).

**Passes.**
- Authorization sweep, 100 API routes, `DEMO_MODE` on, off and unset: no non-owner role passes an owner route; the six new outbound
  routes are owner-only in both modes.
- Every 14 Oct reproduction refused; attack catalogue 0 of 259 with harm; 33 shards exit 0 except the #161 hash pin;
  **PostgreSQL concurrency 3 of 3 clean runs** (31 passed, 10 PostgreSQL variants each) with PG-1 merged.
- Outbound letters: a template of typed obligations only, egress-guarded for the stored offer's buyer on read and again at mark-sent;
  the buyer's yes is the executor's AcceptOffer with every gate; recorded readings are keyed on the full document and written only
  offline (no poisoning); model output still goes through grounding and the cross-check.
- Demo launcher: the API on 127.0.0.1 with `DATABASE_URL=memory`, `TERMSLEDGER_NO_DOTENV=1`, `DEMO_MODE=1`, `LLM_MODE=cache` forced over
  the shell's environment; it stops only its own processes by PID.

**Findings** (reviewer, `evidence/2026-10-16/dev-b8c65b24/r_*.py`; OUT-1 reproduced by the Security Lead):

| Id | Severity | Finding | Fix |
| --- | --- | --- | --- |
| **OUT-1** | **Medium, blocking** | After the owner marks a counter as sent outside FLOW, `POST /negotiate` is refused (409 `OFFER_SENT_OUTSIDE`) but the owner's chat ("send the counter to the buyer", then "yes, go ahead") still runs the simulated negotiation: COUNTER_OFFER, ACCEPT_OFFER and a DRAW_FACILITY execute, the deal reads AGREED with an ACTIVE commitment and "accepted as asked", while the real buyer holds an open letter | apply `sent_outside_conflict` in the chat's negotiate, accept and reject paths (`app/nl/offers.py`, `app/nl/pipeline.py`), or in the executor for every path |
| OUT-2 | Low-Medium | The owner's reported edge case: a refused buyer-yes, then a withdraw, reads FAILED / Declined / terminal with "accepted as asked" in history and a stray PROPOSED commitment; after a re-mark the old refusal text shows on the new mark | rule 9 never FAILED for a `BUYER_YES` op; `by_owner` excludes `BUYER_YES`; bind `_refused_yes` to the standing mark |
| OUT-3 | Low | Anyone can block the owner pasting a buyer's reply by filing its predictable document id first (`reply-{sha256(offer|text)[:16]}`) | a random id, as SEC-16 does for evidence |
| OUT-4 | Low | An ambiguous "both invoices" sentence is now read narrowly instead of asking the buyer (`_plural_is_the_discounts`) | release the plural only when it is the other term's own object |
| DEMO-L1 | Low | The demo launcher's web dev server listens on every interface (`next dev` without `-H`); its build embeds the published demo token (the API stays on loopback) | `-H 127.0.0.1` |

**Verdict.** Not certified while OUT-1 is open: it books an agreement and moves money on a simulated reply while the owner's real letter
is outstanding. With OUT-1 fixed (and its regression test), the rest of this run stands; OUT-2 to DEMO-L1 are not blocking.

## `feat/model-privacy` (`5d2ac935`): pre-merge review, 16 Oct

The design is sound: redaction wraps only the model backends, and grounding, the coverage proof, the cross-check and cache keys all
run on the original text (`service.py`; tests pass: `test_redaction.py` 100, compiler + nl + security 1,023). Findings
(reviewer; PRIV-2 and PRIV-3 reproduced by the Security Lead; scripts `evidence/2026-10-16/model-privacy/`):

| Id | Severity | Finding | Fix |
| --- | --- | --- | --- |
| PRIV-1 | Medium | `scripts/certify_language_boundary.py --backend live` builds the backends without redaction; `CallableBackend(redact=False)` by default | wrap there; default `redact=True`; a test that every model backend built outside tests is wrapped |
| PRIV-2 | Medium (product) | A labelled address swallows the rest of its sentence: "Address: 12 Keyuan Road, Shenzhen. We will pay invoice INV-2026-0871 … within 10 days for a 2% discount." reaches the model as "Address: ⟦ADDRESS_1⟧."; contract readings have no cross-check | end the value at a sentence end or clause cue, cap its length |
| PRIV-3 | Low-Medium | Labelled phone/account match any two digits ("采购手机 2000 台" → "手机 ⟦PHONE_1⟧ 台"; "账户 30 天内付清"); `_MIN_DIGITS` is unused; "Tel: +86 (755) 8600 1234" leaks most digits | enforce `_MIN_DIGITS`; longest match wins |
| PRIV-4 | Low | Bare 16-digit references (PO, batch, tracking) are redacted as accounts | keep words before them |
| PRIV-5 | Info | Coverage by pattern only: person and company names, chat ids, full-width digits, IBANs, 12-15-digit accounts and "contact number" phrasings reach the model (leak table: 80 cases) | disclose (done in the paragraphs) |

**Paragraphs:** the Security Lead's version is on `sec/model-privacy-docs` (`255148af`, off `5d2ac935`): it states what is covered and
the limits as the code does them. **Merge recommendation:** merge with those paragraphs; fix PRIV-1 to PRIV-3 before relying on the
redaction for real customer documents (until then, live mode with real documents should not be used).

## PostgreSQL 17: first run, 16 Oct

A throwaway local PostgreSQL 17.11 (the owner's machine; databases `termsledger_sectest` and `termsledger_sectest2`, created empty
for this run; the connection string never printed or committed). Evidence: `evidence/2026-10-16/postgres/` (logs redacted).

- **Concurrency, on `dev` `0f92d433` as it stands:** the eight invariants of `tests/concurrency` (two processes, serial replay to
  byte-identical books) passed whenever both workers started, but the suite was **not clean**: `test_6[postgres]` failed in 2 to 4 of
  5 runs, and once cascaded into tests 7, 7b and 8 (the workers are session-scoped). Cause, found and fixed (**PG-1**): every store
  re-ran CREATE TABLE and the append-only guard's DDL on open; two processes opening at once raced on the catalog ("tuple
  concurrently updated"; on an empty database "duplicate key … pg_type_typname_nsp_index") and one failed to start, and the trigger DDL
  waited behind a killed worker's open transaction until the server reaped it. No invariant was violated in any run: the failures were
  processes that did not start or timed out, with nothing executed.
- **With the PG-1 fix** (`sec/pg-guard-install-lock` 7f55c0dc: table creation and the guard in one transaction under an advisory lock,
  the guard's DDL skipped when already in place): `tests/concurrency` 31 passed in **6 of 6** runs (10 PostgreSQL variants each, and
  the new `test_pg_guard_install.py`, which fails without the fix); `tests/persistence`, startup and security 444 passed.
  **PostgreSQL concurrency: certified for the 8 invariants on `0f92d433` + `7f55c0dc`**, pending that branch's merge.
- **Append-only triggers** (`pg_guard_check.py`): installed on both tables; direct DELETE, UPDATE and TRUNCATE on `operations` refused
  (`insufficient_privilege`), also after the skip path. **SEC-08 confirmed on PostgreSQL:** an ordinary session that runs
  `SET LOCAL termsledger.allow_reset = 'on'` deletes from `operations` (run inside a rolled-back transaction); `security_events` and
  `approvals` have no guard; a rejected approval reset to PENDING in the database was then approved and EXECUTED, with
  `chain_valid: true`. The API connects as the table owner. Needs database write access; not fixed.

## `0f92d433` (dev with the owner's decisions): CERTIFIED, 16 Oct

- Contents verified: `b6d1e519`, `0ba8e4c1`, `081541d1`, `1b58291f`, `a6de32a2` and `sec/owner-decisions-16oct` are ancestors.
- **R-11** (`r11_check.py`): 24 agent-key `/nl` questions (en, zh), every field of each response scanned for cash, the floor, the
  shortfall, line headroom, the concession cap, break-even, counter cap, DSCR, leverage and the rate ceiling. Pure reads answer the
  sign-in sentence; `verdict` and `negotiation` null; counters read "Counter the offer"; the only figures are the agent's own operation
  amounts. Owner chat unchanged. Verified as decided. Residual by design: the agent's own amounts imply line headroom and the gap.
- **R-10** (`r10_check.py`): the sixth keyed message of the day on either route is 429 `BUYER_BUDGET_EXHAUSTED`; one `SEC-BUDGET-`
  event per buyer per day; another buyer unaffected; reset when the day moves; keyless stays proposal-only. Verified as decided.
  Residual: one keyed message at 0.86% still answers "up to ¥257,200 … at 0.85%" (counter cap and, through the size, the funding gap).
- **SEC-07**: `DEMO_MODE` off unless set (`app/config.py`); every dev, test and browser entry point opts in; sweep with `DEMO_MODE`
  unset (`authz_sweep_v3.py`, `sweep_unset.json`): 94 API routes, no non-owner passes, `/docs` 404, demo credentials refused.
- Sweeps in three modes: no non-owner role passes an owner route; the demo owner token is anonymous outside demo mode.
- Every 14 Oct reproduction refused; attack catalogue 126 API + 133 NL, 0 with harm; 33 shards all exit 0 except
  `tests/books/test_modules_on_books.py:207` (#161). `tests/deals` now passes (the Chinese-names fix).
- Evidence: `evidence/2026-10-16/dev-0f92d433/`.

## `b6d1e519` (capex merge): CERTIFIED, 16 Oct

- Contents verified: `8911fb21`, `bbbfb7ce`, `1b58291f` and all of `origin/dev` (`a6de32a2`) are ancestors.
- CAPEX-1..3 re-run (`evidence/2026-10-14/capex_probe_test.py`, `evidence/2026-10-16/capex-b6d1e519/capex_probe_v3_test.py`): every
  original exploit refused (150% retention and discount inflows, double commit, agent-queued purchase).
- CAPEX-4 fixed (company-key comparison): punctuation variant and a changed buyer party refused; different companies, including
  "Lingnan Homeware Trading Co., Ltd.", accepted. **CAPEX-4b (Low, open):** a confirmed contract whose buyer party names a real supplier
  makes later purchases from that supplier refused as "your own business" (fails safe: refuses, never books).
- SETUP-1 fixed (touched blank books refused, nothing erased: 3 ops and 2 security events kept); SETUP-4 (5,000,000-digit amount → 
  validation error, no 500); SETUP-5 (20,000-bill preview rejected in 0.2 s, 3,000-bill open 422); SETUP-7 (owner preview with
  `DEMO_MODE=0` → 403 `SETUP_REFUSED`, `evidence/2026-10-16/t10_preview_prod.py`). SETUP-2, 3, 6 open (Low/Info), as the team stated.
- Authorization sweep, 94 API routes plus the docs routes, `DEMO_MODE` on and off: no non-owner role passes an owner route; the setup
  routes refuse every non-owner role.
- 14 Oct reproductions still refused (anonymous overwrite 409, oversized intake 413, owner accept not blocked by an agent-tripped
  circuit, bank-feed clock 403, one live agreement).
- Attack catalogue: 126 API + 133 NL attacks, 0 with harm. 31 test shards: all exit 0 except `tests/books` (digest pin) and
  `tests/deals/test_lang.py` (×2), the three pre-existing dev items tracked in issue #161.
- Evidence: `evidence/2026-10-16/capex-b6d1e519/`.

## `8911fb21` (capex buy side): pre-merge review, 16 Oct

Re-ran the 14 Oct exploits (`evidence/2026-10-14/capex_probe_test.py`) and new variants (`evidence/2026-10-16/capex_probe_v2_test.py`):

| Finding | Result |
|---|---|
| CAPEX-1 inflow | **fixed**: 150% retention → not derivable, commit 422 `NO_SCHEDULE`; 150% discount → no early schedule; shares adding to 140% refused; executor refuses any payment ≤ 0 |
| CAPEX-2 agent-authored commit, card | **fixed**: agent `COMMIT_PURCHASE` (even claiming OWNER) → REFUSED `INSUFFICIENT_AUTHORITY`, PRIVILEGE_ESCALATION event, nothing queued; card shows vendor, contract, each payment |
| CAPEX-3 double commit | **fixed**: same text twice → refused; near-copy under another vendor id → refused. Residual: a copy with a changed contract reference (`…114A`) commits as a separate purchase; it shows as a different contract on the card (owner's judgment) |
| CAPEX-4 vendor = own business | **partly fixed**: exact name refused, but "Lingnan Homeware Manufacturing Co. Ltd" (punctuation variant) and the exact name with the contract's buyer party changed are both registered as the vendor. Low. Fix: compare with punctuation stripped, and against the business's registered name, not only the contract's buyer party |
| Route authorization | all 94 API routes (15 capex/setup) and the docs routes refuse every non-owner role, `DEMO_MODE` on and off; demo credentials refused with `DEMO_MODE=0` (`evidence/2026-10-16/capex_sweep_*.json`) |
| Branch tests | `tests/api/test_capex_security.py`, `test_capex_attacks.py`, `tests/capex`: pass |

New setup feature (reviewer, two items reproduced by the Security Lead; scripts `evidence/2026-10-16/t*.py`). Every item needs the owner
token; opening is refused outside `DEMO_MODE`; the mandate is signed with the demo key only in demo mode; no Critical or High.

| Id | Finding | Sev | Status |
|---|---|---|---|
| SETUP-1 | `/setup/open` treats books as blank by scenario name only: books with a log, security events and an advanced clock are wiped (reproduced: ops 3 → 1, security events 2 → 0, chain valid); OPEN_BOOKS does not record what it replaced; a failed open has already wiped the log | Low-Med | CONFIRMED |
| SETUP-2 | two processes can both open; the second silently replaces the first (reset and new books in separate transactions) | Low | reviewer |
| SETUP-3 | ten-document cap racy (40 concurrent → 40 held) and held documents survive resets; memory growth, paid reads in live mode | Low | reviewer |
| SETUP-4 | 5,000,000-digit amount → unhandled `decimal.Overflow` 500 on `/setup/preview` | Low | CONFIRMED |
| SETUP-5 | list and string sizes unbounded (3,000 bills → 108,000 flows, `/home` 2.1 s; 20 MB field accepted) | Low | reviewer |
| SETUP-6 | a failed restore is reported as a successful one | Info | reviewer |
| SETUP-7 | `/setup/preview` not gated on demo mode (contradicts its docstring) | Info | reviewer |

**Verdict:** no blocker. GO to merge `dev` into the capex branch. CAPEX-4 remainder and SETUP-1..7 are tracked, not merge-blocking for
scope S; SETUP-1 should be fixed before any demo whose evidence log matters. Certification is on the merge commit, re-running: this
table's probes, the authorization sweep (both modes), `tests/security`, the attack catalogue and the full sharded suite.
