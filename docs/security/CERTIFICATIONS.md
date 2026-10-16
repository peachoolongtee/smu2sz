# Security certifications

Each entry is the Security Lead's independent sign-off on one exact commit. A certification covers what is listed under "Evidence" and
nothing else; it is not a claim of absolute security. Scope words follow `RELEASE_GATE.md` (S = local simulation on loopback).

| Date | Commit | What | Verdict |
|---|---|---|---|
| 16 Oct | `0ba8e4c1` (dev) | security fixes 1-5 (SEC-01..05, 09, 10, 16..18) as merged | **CERTIFIED** |
| 16 Oct | `081541d1` via dev head `a6de32a2` | SEC-12/13 headers as merged; all security fixes as they stand on dev with round three and Dylan's UI | **CERTIFIED** (one stale test fixed on `sec/redteam-d-patch-target`) |
| 16 Oct | `8911fb21` (`feat/capex-buy-side`) | CAPEX-1..4 fixes, setup feature | pre-merge: GO to merge dev into it |
| 16 Oct | `b6d1e519` (`int/capex-fixes`: capex buy side + dev `bbbfb7ce` + `fix/capex4-setup1`) | the capex buy side as it would land on dev | **CERTIFIED** for scope S |
| 16 Oct | `0f92d433` (dev) | the owner's decisions on R-11, R-10 and `DEMO_MODE` (`sec/owner-decisions-16oct`), with the capex buy side merged | **CERTIFIED** for scope S |

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
