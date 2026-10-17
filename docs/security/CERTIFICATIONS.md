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
| 17 Oct | `29fa0ea2` (dev: round four, the redaction fix, self-assessment v3; **the assessed build**) | everything since `0fde33fd` | **CERTIFIED** for scope S; no test exception |
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

## `29fa0ea2` (dev): CERTIFIED for scope S, 17 Oct: the assessed build

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
