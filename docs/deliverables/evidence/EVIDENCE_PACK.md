# FLOW: verified evidence pack for the final technical document

This pack holds the numbers for the final technical document (FinTechathon 2026, International AI Track, Topic E). The writer
should take every figure from here, with the source quoted beside it.

**Ground rules for every run in this pack.**

| Item | Value |
| --- | --- |
| Build | `origin/dev` at **`975e082f`** ("merge(int): Attach deals, capex hub, redaction, security doc v2"). Branch `docs/evidence-pack` adds only this file and `scripts/analysis/*.py`; no product code changes |
| Date | **17 Oct 2026** (runs started 16:17 +08:00) |
| Machine | Windows 11 Pro, Git Bash, `uv`, Python 3.12 (`services/api/uv.lock`) |
| Configuration | `LLM_MODE=cache TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1`. Offline, with no network and no live model calls. `.env` was never read |
| Store | In-memory store (`InMemoryLedgerStore`) on a fresh `Runtime`; no database |
| Outputs | Scratchpad `…/scratchpad/ev/` (the session scratchpad, not committed). Tracked report files were not changed: `attacks --report` rewrites `services/api/evals/security/latest_report.*`, which were copied to the scratchpad and then restored with `git checkout --` |

How to read the tables: "file:line" means a path in the repo at `975e082f`. **unverified** means this session could not reproduce
the figure, and the reason is given.

---

## 1. Headline evidence table

| # | Claim | Build / date | Configuration | Command (from) | Result | Known exceptions |
| --- | --- | --- | --- | --- | --- | --- |
| 1.1 | API tests collected | 975e082f / 17 Oct | in-memory, demo mode | `uv run pytest --collect-only -q` (services/api). `tail -1` prints the last per-file line here, because the config prints one line per file; the total is the sum | **9,085 tests in 360 files** (25.8 s) | Collected, not run. See 1.2 |
| 1.2 | API suite passed | 975e082f / 17 Oct (the lead's gate, **accepted as given**, not re-run here) | full gate | lead's full-gate record | **9,040 passed**; the only failure is **#161** (a hash pin, `docs/SECURITY_SELF_ASSESSMENT.md:286`) | 9,085 collected − 9,040 passed = 45 not passed, so 44 are skips or deselections besides #161. **unverified** here: the split was not recorded in this pack |
| 1.3 | Web unit tests | 975e082f / 17 Oct, lead's record (accepted) | `pnpm test:unit` | lead | **169** passed | not re-run here |
| 1.4 | Playwright, mock | 975e082f / 17 Oct, lead's record (accepted) | `E2E_TARGET=mock` | lead | **445 passed / 0 failed** | not re-run here |
| 1.5 | Playwright, live | 975e082f / 17 Oct, lead's record (accepted) | `E2E_TARGET=live` | lead | **139 passed** | known failures `live.spec:333` and `live.spec:347` |
| 1.6 | Adversarial attacks | 975e082f / 17 Oct | cache | `uv run python -m app.security.attacks --report` (services/api), 76 s | **259 attacks, 0 with harm**: 126 API + 133 chat (43 as the owner, 64 as a counterparty, 26 with the agent key). Detection **98.41%** of the 126 API attacks, with a security-event rate of 73.02%. Injection 0/42, exfiltration 0/22, escalation 0/21, replay 0/21; money moved by attacks 0 fen | 0 attacks documented as findings. Undetected API attacks are PE-07 and PE-14 (`SECURITY_SELF_ASSESSMENT.md:208-222`). Across all 259, detection is 81.08% (judge pack, 1.8): most of the rest are the owner's own negated or conditional chat instructions (NL-CS37 to CS41 "MISSED (no harm)") |
| 1.7 | Scripted tasks | 975e082f / 17 Oct | in-process | `uv run --project services/api python scripts/run_scenarios.py --inproc --out <scratch>/scen` | **49/49 passed**, 0 skipped, 87 turns, median 14.6 ms a turn (18 s) | none |
| 1.8 | Judge pack | 975e082f / 17 Oct | in-process | `uv run --project services/api python scripts/judge_eval.py --out <scratch>/judge/judge-report.md --artifacts <scratch>/judge/art` (84 s) | 49/49 tasks, 87 turns. 259 attacks, 0 caused harm. Detection 98.41% (API) and 81.08% (all 259). 2 attacks contained (queued for the owner, nothing changed). 17-step demo walk OK. Audit chain **VALID** (14 operations, 8 security events). A tampered copy is **rejected** (seq 1 `entry_hash` mismatch) | by attack class: privilege-escalation detection 82.14% (23/28) |
| 1.9 | Offline evaluation, all suites | 975e082f / 17 Oct | cache, default flags (`--funding-random 16`, `--funding-budget 180`, default workers) | `uv run --project services/api python scripts/evaluate.py --out <scratch>/evalfull` | **Completed in 7 min 41 s; 0 targets missed in every suite.** **The funding brute force ran** (funding suite 382.4 s; 26 scenarios: 10 designed and 16 seeded random). Highlights: financial exactness **67/67**; covenant and capex golden **27/27**; boundaries **20/20**; runnable optimality **26/26**; priced optimality **26/26**; router flags agree with the oracle on **26/26**; E9 **9/26** with a gap; 0 committed plans on an uncommitted facility; E5 hard-line buyer to NO_DEAL with the gap still funded, **7/7**; intent 42/47 (89%); slots 30/30; clarification 6/6 | Brute-force budget hit on F09 (priced) and R03 (priced); the router is judged "no worse than what it found" there. Offers suite on the default `fixtures/heldout`: 45/50 verdict agreement, material errors 0/36. See section 2 for held-out 2 and 3 |
| 1.10 | Latency (same evaluate report, `evalfull/latest_report.md:26,27,41,42`) | as 1.9 | cache, in-process | as 1.9 | Router **p50 81 ms / p95 238 ms**. Slowest `verifier.evaluate` **0.5 s** (`reserve_unsafe_1fen`). `/nl` turn **p50 9 ms / p95 567 ms** (87 turns). E2E golden Scene 1 (compile, evaluate, negotiate, execute) **p50 1,078 ms / p95 1,128 ms** over 5 cold runs | In-process TestClient, no network and no model. Not a production latency |
| 1.11 | Route count | 975e082f / 17 Oct | source only (`python -I`, imports nothing) | `python -I scripts/security_route_inventory.py . <scratch>/routes.json` | **99 routes** under `services/api/app/api`; 0 new since baseline; 3 with no auth marker found (`POST /offers/{offer_id}/accept`, `POST /offers/{offer_id}/decline`, `GET /activity`, …: auth comes from router dependencies the marker scan does not read) | **Reconciliation with "100 routes"** (`SECURITY_SELF_ASSESSMENT.md:92,104,284,298`): the inventory reads only `app/api`. The 100th is `GET /health`, declared directly on the app (`services/api/app/main.py:108`). An independent count of `@router/@app.<verb>(` decorators under `services/api/app` also finds exactly 100. Mounting was not checked route by route. `/docs`, `/redoc` and `/openapi.json` are separate (demo-only, SEC-13, `main.py:47-50`) |
| 1.12 | Alembic head | 975e082f | source | `grep revision migrations/versions/*.py` | **Head `0009`** (`0009_audit_guards.py:20-21`, `down_revision="0008"`). Linear chain 0001 → 0009: initial, enable_rls, append_only_triggers, approval_decided_day, pilot_journal, decision_facts, contract_records, customer_inputs, audit_guards | none |

### 1.13 Section-2 inputs (held-out offer sets, current code)

| Set | Command | Verdict agreement (compiler) | Form baseline | Material error rate | Silent material errors | Abstention P / R | Wording invariance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| held-out 3 | `scripts/evaluate.py --suite offers --heldout fixtures/heldout3 --out <scratch>/eval_heldout3` | **44/63 (70%)** | **56/63 (89%)**, gap +19 pts | **3/51 (5.9%)** (type 3, contingency 1): **FAIL** against ≤ 5% | **4** (3 material + 1 booked on a must-abstain item): **FAIL** against 0 | 14/16, 14/15 | 13/13 |
| held-out 2 | same, `fixtures/heldout2` | **38/47 (81%)** | **40/47 (85%)**, gap +4 pts | **0/37** PASS | **0** PASS | 12/14, 12/12 | 7/8 |

**The technical document's accuracy table is stale.** `docs/deliverables/technical_document.md:377-383` copies
`services/api/evals/accuracy_summary.md` (1 Oct, commit 389cfd9). It quotes held-out 3 at 46/63 and held-out 2 at 41/47, with a
form baseline of 61/63 and "2 correct" and "4 correct" autonomous accepts. On 975e082f the figures are 44/63, 38/47, 56/63, and
1 and 2 correct. The cause is the early-payment rule of ADR-0007 (section 2.4), not a regression in the compiler.

---

## 2. Autonomy funnel

**Command.** `uv run --project services/api python scripts/analysis/autonomy_funnel.py fixtures/heldout3 fixtures/heldout2 --out <scratch>/funnel`
(on this branch).
- The script runs the offers suite's own pipeline: `compile_offer` in cache mode, then `app.verifier.evaluate` on the golden
  state with the signed demo mandate, as `services/api/evals/suites/offers.py:120-131` does.
- For each offer it also records the verdict's `required_tier`, the plan's `needs_owner_approval` and `autonomy_gaps`.
- Every one of the 115 offers was compiled by **`rules-v1`** (the rules grammar). None is in the compiler cache. So this is the
  offline path, with no model.

### 2.1 Definitions

These come from the evaluator and product code.

- **Autonomous (FLOW may act without the owner).** The verdict is `ACCEPT` **and** `required_tier == TIER_1` **and** the funding
  plan is not flagged `needs_owner_approval`. This is exactly the rule of `app/api/offer_picture.py:243-252`
  (`_asked_authority`: `owner = verdict.required_tier != Tier.TIER_1 or plan.needs_owner_approval`).
  - The verifier gives `ACCEPT, TIER_1` only when all of these hold (`app/verifier/evaluate.py:731-758`):
    - no hard, price or security code;
    - no terms lengthening;
    - new forward value ≤ `tier2_single_commitment_fen`;
    - only an early-payment discount on a named invoice;
    - no ADR-0005 autonomy gap;
    - no past-due buyer.
- **Eligible for autonomous handling** (the funnel's denominator). The label is `ACCEPT`, every booked label is
  `IMMEDIATE_DISCOUNT` and the item has no `claims`. Under the held-out-3 labelling policy
  (`fixtures/heldout3/offers.yaml:10-16`) an ACCEPT label means a pure early-pay discount on the named whole invoice, strictly
  below 0.88%, with APR ≤ 15%.
- **Escalation.** The verdict is `NO_VERDICT` (a clarification is asked) or `NEEDS_OWNER_APPROVAL`, or it is `ACCEPT` but the
  tier or plan sends it to the owner.
  - **Owner interactions** = 1 per escalation. This is the minimum: one decision or clarification per item.
- **Verdict agreement** (`evals/suites/offers.py:13,151,178-179,234`). `outcome == label`, counted over the *labelled* items only.
  An item whose label is `unlabelled` is left out (`UNLABELLED`, line 30).
- **Form baseline** (`offers.py:135-143,163,236`). The labels themselves are typed into the verifier as a `CompileStatus.COMPILED`
  offer: `evals/forms.py`, with no compiler. A must-abstain item gets `NO_VERDICT` by construction (line 137), so it always
  agrees. What remains measures the verifier's policy against the labeller's policy.
- **Material error** (`offers.py:7-8,64-84,170-172,211`). Only items *not* labelled abstain count: 51 in held-out 3 and 37 in
  held-out 2. An item counts when the system booked a verdict and a booked obligation differs from the label in any of:
  - type (missing or spurious);
  - `rate_bp`;
  - amount (`base_amount_fen`, `amount_fen`);
  - days (`days_delta`, `invoices`, `duration`);
  - `contingency`.

  Obligations are matched by type, in order. An abstention (`NO_VERDICT`) books nothing and is not a material error.
- **Silent material error** (`offers.py:9,173,223-225`). The material errors, plus the must-abstain items where the system did
  *not* abstain and booked something.
- **Wrong autonomous accept.** The suite does not compute this; the funnel script and `accuracy_summary.md` do. It is an
  autonomous ACCEPT (as defined above) where the label is not ACCEPT, or the booked terms carry a material error.

### 2.2 Why 66 offers give 63 verdict comparisons and 51 material-error cases (held-out 3)

- **63 verdict comparisons.** 66 items, less 3 whose outcome is `unlabelled`: `counts.unlabelled_outcome = 3` in
  `eval_heldout3/latest_report.json`. Verdict agreement is taken over `labelled` (`offers.py:178`).
- **51 material-error cases.** 66 items, less the 15 labelled `abstain: true` (`counts.must_abstain = 15`, `non_abstain = 51`).
  The material error rate is computed over `non_abstain` (`offers.py:170,211`).
- **Held-out 2:** 49 items, 2 unlabelled, so 47 comparisons; 12 must-abstain, so 37 material-error cases.

### 2.3 Why the form baseline was 61/63, and is 56/63 today

- **61/63** is the 1 Oct figure (`accuracy_summary.md:8`, `heldout3_report.md`, commit 389cfd9 / a4c902c).
  - The 2 form misses then: the labels were written to a 0.88% break-even policy.
  - One was H3-C02 (0.88% passed the exact 0.8832% break-even; the report notes it), plus one other. Those runs are not
    reproduced here.
- **56/63 on 975e082f.** The 7 form misses are listed below, from `eval_heldout3/latest_report.json` (rows with `form_ok` false).
  They are policy differences, not reading errors. The labels were fixed on 1 Oct, before ADR-0007's third test
  (`EARLY_PAY_DEARER_THAN_PLAN`).

| Item | Label | Verifier on the labels | Why |
| --- | --- | --- | --- |
| H3-A03, A04, A07, A08 | ACCEPT (0.75%–0.87%) | COUNTER, `EARLY_PAY_DEARER_THAN_PLAN` | 0.75% on ¥420,000 = ¥3,150.00, more than the standing plan C0 ¥3,113.93. Accept only below 0.7414% (ADR-0007, `docs/adr/0007-early-pay-acceptance-rule.md:150`) |
| H3-N6B | COUNTER | ACCEPT | the labeller's counter; the verifier finds the package acceptable |
| H3-T01, T01Z | NEEDS_OWNER_APPROVAL | REJECT, `RESERVE_BREACH` | the verifier finds a reserve breach that the labeller treated as approvable |

Held-out 2's form misses (7 of 47) have the same cause. H2A01, H2A02, H2A04, H2I01, H2I03 (0.80%–0.85%), H2P05 and H2A06 (partial
invoice to NEEDS_OWNER_APPROVAL) are all `EARLY_PAY_DEARER_THAN_PLAN` or scope policy.

### 2.4 The funnel (975e082f, cache, rules grammar, no network)

| Step | Held-out 3 | Held-out 2 | Both |
| --- | --- | --- | --- |
| Offers | 66 | 49 | 115 |
| **Eligible by label** (pure early-pay ACCEPT) | **14** | **9** | **23** |
| … of which the current mandate counters as dearer than the plan (0.75%–0.87%; `EARLY_PAY_DEARER_THAN_PLAN`) | 4 (A03, A04, A07, A08) | 5 (H2A01, A02, A04, I01, I03) | 9 |
| **Eligible under today's economics** (label ACCEPT, and the discount is below the plan cost ¥3,113.93) | **10** | **4** | **14** |
| **Handled autonomously and correctly** | **1** (H3-A10) | **2** (H2A03, H2A05) | **3** |
| **Escalated unnecessarily** (eligible, but sent to the owner) | **9** | **2** | **11** |
| … reason | 9 × ADR-0005 "autonomy not proven": the compiler could not account for every figure and request, usually a stated settlement date ("tmrw", "国庆后", "next Mon") that is not read into the terms (`autonomy_gaps`, `app/verifier/evaluate.py:796-818`) | H2A07 (same gap); H2A06 (`UNRESOLVED_SCOPE`: partial invoice) | |
| Eligible by label but countered (not escalated; FLOW sends a counter at Tier 1) | 4 | 5 | 9 |
| **Escalations, all** (`NO_VERDICT` + `NEEDS_OWNER_APPROVAL`) | **36** | **22** | **58** |
| **Escalated correctly** (the item is not eligible) | **27** | **20** | **47** |
| … where the label itself also escalates (`NO_VERDICT` or `NEEDS_OWNER_APPROVAL`) | 25 | 20 | 45 |
| Autonomous non-accepts (Tier-1 COUNTER / REJECT, no owner) | 10 counter, 19 reject | 10 counter, 15 reject | 54 |
| **Autonomous ACCEPTs, all** | 1 | 2 | 3 |
| **Wrong autonomous accepts** | **0** | **0** | **0** |
| **Owner interactions** (1 per escalation) | **36 of 66** (55%) | **22 of 49** (45%) | **58 of 115** (50%) |

**Reading.**
- On the rules-grammar path, FLOW handles **3 of 14** (21%) economically eligible early-pay offers on its own, and makes no
  wrong autonomous accept.
- **11 of 14** go to the owner unnecessarily. 10 of those 11 escalate because the coverage proof (ADR-0005) cannot account for a
  stated settlement date.
- "Zero unsafe accepts" therefore holds, but the useful-autonomy rate on these sets is low. The remedy that would move it is
  reading settlement dates into the terms; this pack does not claim it.
- The silent material errors on held-out 3 (H3-X09, T05, M03, I05) all landed at `NEEDS_OWNER_APPROVAL` or `REJECT`, never as
  an autonomous accept.

Raw rows: `<scratch>/funnel/funnel_heldout3.json`, `funnel_heldout2.json`. **unverified:** the live DeepSeek path. No live call
was allowed, and the held-out messages are not in the compiler cache.

---

## 3. The EX01 worked example, reconciled

**Command.** `uv run --project services/api python scripts/analysis/ex01_reconcile.py --out <scratch>/ex01` (this branch).
- It runs a fresh in-memory `Runtime`, then `POST /offers {fixture_id: EX01_PACKAGE}`, `POST /offers/{id}/evaluate`,
  `GET /offers/{id}/picture`, `GET /trajectory` and `POST /router/plan` through FastAPI's TestClient, as the owner.
- All figures below come from that response (`<scratch>/ex01/EX01_PACKAGE.json`).
- Evaluated on **day 0** (`evaluated_day`); state version 1; floor ¥300,000; current terms 45 days.

**The package** (bound obligations):
1. 1.20% early payment on RCV-A (¥420,000, effective day 2);
2. terms 45 → 60 days on all future invoices (RECURRING_PERPETUAL, FIRM);
3. a 1% rebate on ¥400,000 of purchases (CONTINGENT, counted at its maximum).

### 3.1 Canonical table

| Row | State day | Accepted terms | Funding assumption | Lowest cash (day) | Breach: max amount, days below ¥300k | Discount (immediate) | Interest and fees | Forward-concession value | Executable | Approval tier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Books today, no offer | 0 | 45-day terms | **no funding** | **−¥105,000** (day 30) | ¥405,000 short; 20 days (12 to 31) | — | — | ¥0 | — | — |
| Books today + standing plan | 0 | 45-day terms | line ¥150,000 (repaid day 32) + invoice financing ¥255,000 on RCV-A | ¥300,000 | none | — | **¥3,113.93** = ¥841.64 + ¥2,272.29 | ¥0 | yes | Tier 1 |
| **EX01 accepted as asked, no new funding** | 0 | 1.2% early pay + 60 days + 1% rebate | **none** | **¥164,960 (day 60)**. Day 47 is **¥209,960**; days 12 ¥474,960, 20 ¥354,960, 30 ¥309,960 | **max ¥135,040 (day 60); first breach day 47 short ¥90,040; 15 days below** (47 to 61; recovers day 62) | **¥5,040.00** (1.20% × ¥420,000) | — | **¥28,326.92** = ¥24,326.92 (terms: 13 invoices × ≈¥1,871.30) + ¥4,000.00 (rebate at maximum); cap ¥5,000 | — | verdict **REJECT, TIER_1** (`AGG_CONCESSION_EXCEEDED`, `RESERVE_BREACH`, `DISCOUNT_ABOVE_BREAK_EVEN`, `EARLY_PAY_DEARER_THAN_PLAN`) |
| EX01 + the verdict's **cure** plan (`verdict.plan` = `cure_plan`) | 0 | as above | invoice financing **¥135,040** on **RI:BUYER-1:32** (an invoice *issued on day 32*), lands day 35 | ¥300,000 (day 60) | none | ¥5,040.00 | **¥2,406.67** = 135,040 × 7.8% × 60/365 (57 days billed as 2 × 30) ¥1,731.47 + 0.25% × 2 ¥675.20 | ¥28,326.92 | **no**: "RI:BUYER-1:32 is not an invoice the executor can finance today; it is issued on day 32" | the reserve breach is "curable at ¥2,406.67; the cure cannot run today" |
| EX01 + the router's **committed** plan (`plan_committed`) | 0 | as above | line draw **¥135,040** today, repaid day 62 | (floor held; display) | none | ¥5,040.00 | **¥1,468.05** = 135,040 × 6.4% × 62/365 | ¥28,326.92 | yes | Tier 1 for the draw |
| Early-pay test (ADR-0007), inside the verdict | 0 | the package with vs without its early-pay leg | committed plans | — | — | — | **C1 = ¥6,508.05** (with the offer: ¥5,040.00 discount + ¥1,468.05 line). **C0 = ¥3,873.58** (without the early-pay leg, but with the 60-day terms: ¥1,467.62 + ¥2,405.96) | — | — | C1 ≥ C0, so `EARLY_PAY_DEARER_THAN_PLAN` |
| **Option A** (FLOW's recommended counter) | 0 | early pay 0.85% on up to ¥260,000 of RCV-A, terms stay 45 | the router's plan: line ¥147,210 today | ¥300,000 ("Held, no buffer at the lowest point", day 30) | none | ¥2,210.00 | ¥825.99 (line), total **¥3,035.99** < C0 ¥3,113.93 | ¥0 | yes | **ACCEPT, TIER_1** ("Option A is the reply within your mandate") |
| Option B | 0 | 55-day terms, 0.30% price change | — | ¥300,000 (day 30) | none | — | — | stated ≈ ¥0 net over 12 months | — | **needs the owner's approval** (terms lengthen) |

Sources:
- `RESERVE_BREACH.inputs` in the evaluate response: `day 47`, `closing_cash ¥209,960.00`, `shortfall ¥90,040.00`,
  `max_shortfall ¥135,040.00`, `max_shortfall_day 60`, `days_below_floor 15`, `recovery_day 62`, `cure_plan "committed plan:
  ¥2,406.67 (cannot run today)"`, `cure_executable_now false`.
- `EARLY_PAY_DEARER_THAN_PLAN.inputs`: `cost_with_offer ¥6,508.05`, `cost_without_offer ¥3,873.58`.
- `DISCOUNT_ABOVE_BREAK_EVEN.inputs`: `break_even 0.8832%`, `router_optimum ¥841.64 + ¥2,272.29 = ¥3,113.93`,
  `line_plus_partial_at_offered_rate ¥3,938.81`.
- `concession_values` (3 rows).
- The picture's `asked` and `replies`, which give lowest ¥164,960 day 60, and ¥300,000 day 30 for A and B.
- Option A's cost and draw: `apps/web/e2e/deals-queue.spec.ts:94,107-108` (¥3,035.99, "¥147k credit-line draw today") and
  `docs/adr/0007-early-pay-acceptance-rule.md:195`. Its face and discount: `fixtures/golden/golden_values.json:40-42`
  (26,000,000 / 221,000 / 303,599 fen).
- The pinned specs: `apps/web/e2e/contract.spec.ts:33-50`, which asserts min ¥164,960 on day 60, first breach day 47,
  shortfall_display ¥135,040 and day 47 ¥209,960.

### 3.2 Why the two shortfall figures differ (¥90,040 against "Breached by ¥135k for 15 days")

**Both are correct readings of the same trajectory.** They measure different days.

- **¥90,040** is the shortfall on the **first breach day**, day 47: ¥300,000 − ¥209,960.
  - The next invoice, RI:BUYER-1:2 (issued day 2), would have paid on day 47 at 45 days. Under 60-day terms it moves to day 62.
  - Meanwhile the ¥100,000 "Operating bill" due on day 47 still leaves.
  - RCV-A itself is already settled early on day 2, at a 1.2% discount.
  - These are the trajectory's own events (`verdict.trajectory.days[*].events`).
  - The verifier's `RESERVE_BREACH` headline (`observed ¥209,960`, `inputs.shortfall`) reports this day
    (`app/verifier/reserve.py:106`).
- **¥135,040** is the **maximum** shortfall, on day **60**: ¥300,000 − ¥164,960.
  - The existing loan's ¥45,000 monthly payment leaves on day 60, taking ¥209,960 down to ¥164,960.
  - That reading is `inputs.max_shortfall` (`reserve.py:107-108`).
- The owner-facing sentence comes from `app/api/picture_words.py:51-60` (`reserve_state`). It takes `floor − lowest` (¥135,040,
  shown as "¥135k") and `_days_below`: the first day below (47) to the first day back at or above (62), which is **15 days**.
- **The cure is sized to the maximum, not to day 47.** The cure plan and the committed plan both move ¥135,040 (`need_fen
  13,504,000`). The cured trajectory's lowest is exactly ¥300,000 on day 60.

**What the document must change.**
- `technical_document.md:301` says "¥209,960 on day 47: a ¥90,040 shortfall", then "cures it for ¥2,406.67". That is true but
  incomplete. The breach deepens to **¥135,040 on day 60** and lasts 15 days. The ¥2,406.67 cure covers ¥135,040, not ¥90,040.
- The ¥2,406.67 cure **cannot run today**: it finances an invoice not issued until day 32. The executable committed plan for
  the accepted offer is the line draw at **¥1,468.05**.

**Bug check: one inconsistency, display only.** In `apps/web/lib/live/trajectory.ts:98-102` (`shortfall()`), the web's
`shortfall_display` takes `inputs.max_shortfall` (¥135,040) but `shortfall_fen` takes `inputs.shortfall_fen` (9,004,000 =
¥90,040). So one view object holds a fen value and a display string that disagree.
- No decision depends on it: the verdict, the cure and the owner's sentence all use the maximum.
- It is still a defect in the view model. Flagged here and not fixed (no product changes).
- The verifier's own naming (`shortfall` = first-day value, `max_shortfall` = worst) is the root of the confusion.

### 3.3 The four costs, explained

| Figure | What it is | Formula (from the response) |
| --- | --- | --- |
| **¥3,113.93** | The **standing plan C0** on today's books with no offer: the gap ¥405,000 before day 32 | line ¥150,000 × 6.4% × 32/365 = ¥841.64; invoice financing ¥255,000 on RCV-A = ¥2,272.29 |
| **¥2,406.67** | The verdict's **cure** of EX01's reserve breach, on the *committed marginal source* (invoice financing at 10.8417%, because clean-down excludes the line for a permanent need) | ¥135,040 × 7.8% × 60/365 = ¥1,731.47, plus 2 × 0.25% × ¥135,040 = ¥675.20. Not executable today (future invoice RI:BUYER-1:32) |
| **¥6,508.05** | **C1** of ADR-0007's third test: the package *with* its early payment and the committed plan it needs | ¥5,040.00 discount + ¥1,468.05 line (¥135,040 × 6.4% × 62/365) |
| **¥3,873.58** | **C0 for this package**: the same books with the 60-day terms and the rebate but *without* the early-pay leg | ¥1,467.62 (line) + ¥2,405.96 (invoice financing). It differs from ¥3,113.93 because the 60-day terms move later receipts |

The router's selected plan for the accepted offer (¥1,468.05) and the verdict's cure (¥2,406.67) are different plans. The
difference is documented in `docs/CUSTOMER_ECONOMICS_BRIEF.md:331`.

---

## 4. The ¥100,000 Tier-2 threshold

- **Value.** `tier2_single_commitment_fen = 10,000,000` (¥100,000) in the signed mandate. Sources:
  `fixtures/scenarios/golden_sme.json:360` and `golden_sme.mandate.signed.json:16`. The field is defined at
  `services/api/app/domain/models.py:496`.
- **What it is measured on.** The commitment's **forward-concession value** (`forward_value_fen`). It is not the invoice face,
  not the immediate discount and not the cash moved.
  - **Executor.** `app/operations/executor.py:825-843` (`_tier`). Line 832 takes `value = c.forward_value_fen`, and lines
    834-835 call `tier_for`.
  - **Tier rule.** `app/mandate/tiers.py:107-116` returns Tier 2 when
    `commitment_value_fen > mandate.tier2_single_commitment_fen` (line 114).
  - **How `forward_value_fen` is set.** `propose_commitment` (`executor.py:595-627`) uses `verdict_forward_value(verdict)`
    (`executor.py:194-203`): concession values net of FIRM gains, floored at 0, "never an immediate cost".
  - **Verifier.** It applies the same quantity: `new_value = res.forward_total − existing`, then `new_value >
    tier2_single_commitment_fen` gives NEEDS_OWNER_APPROVAL at Tier 2 (`app/verifier/evaluate.py:731-742`).
- **An early-payment discount has forward value 0.** `app/financial/concessions.py:270-275` values `IMMEDIATE_DISCOUNT` with
  basis "immediate discount: settled in cash now and capped separately". The EX01 response shows `value_fen 0` for it. Its own
  cap is `max_immediate_discount_bp = 150` (`app/mandate/predicates.py:199-201`).
- **Dead branch.** `tiers.py:105` compares an `ApplyForFacility` amount with the same limit. It never decides anything:
  `ApplyForFacility` is already Tier 2 at `tiers.py:45,93-94`.
- **Wording risk.** The owner-facing sentence "a commitment of up to ¥100,000" (`app/api/offer_picture.py:314`) does not say
  which quantity it means. The 3 Oct audit recorded the same point (`docs/research/independent-principal-audit-2026-10-03.md:226`).

**Does 0.74% on the whole ¥420,000 invoice mean Tier 1 or Tier 2?**
- **Tier 1, autonomous**, when the offer is owner-built or typed (an `nl-` or `whatif` compiler), or is a buyer message that
  passes ADR-0005's coverage proof.
- **The ¥100k threshold never applies** to it: the forward value is 0.

The code path:
1. The discount is valued at 0, so `new_value` = 0 (`concessions.py:270-275`).
2. ADR-0007:
   - 74 bp is below the 0.8832% break-even;
   - the cash is needed;
   - ¥3,108.00 (310,800 fen) < C0 ¥3,113.93 (311,393 fen).

   So no price code is raised (`evaluate.py:694-697`).
3. No lengthening, `only_early_pay` true, no autonomy gap (`evaluate.py:802`: an `nl-` or `whatif` compiler is exempt) and no
   past due give `Outcome.ACCEPT, Tier.TIER_1` (`evaluate.py:758`).
4. `propose_commitment` sets `forward_value_fen = 0`.
5. `_tier`:
   - no terms change;
   - value 0 ≤ 10,000,000;
   - only early pay (`executor.py:184-187`).

   So `tier_for` gives Tier 1, which the verdict's Tier 1 does not raise (`executor.py:841-842`).
6. `_screen_commitment` and `_check_binding` pass (the forward cap is 0 + booked ≤ 500,000). `_commit` makes the commitment
   ACTIVE (`executor.py:945-986,1046-1140`).

**Caveat.** A *buyer message* at 0.74% that does not state the invoice amount, or carries text the compiler cannot account
for, becomes `NEEDS_OWNER_APPROVAL, TIER_2` through ADR-0005 (`evaluate.py:749-753,805-817`), not through the ¥100k threshold.
The security probe NL-OP01 shows exactly this: "answered (acceptance awaiting the owner) up to 74 bp"
(`services/api/evals/security/latest_report.md:352`).

**Tests.**
- `tests/verifier/test_early_pay_handcalc.py::test_row3_whole_invoice_75bp_costs_3150_and_is_countered` (lines 129-139): 74 bp
  gives ACCEPT, with (310,800, 311,393); 75 bp gives COUNTER.
- `tests/verifier/test_redteam_e.py:93-99`: a fixed ¥3,108.00 gives ACCEPT.
- Tier 1 for whole-invoice early pay:
  - `tests/verifier/test_display_and_tier.py:79-81` (0.6%);
  - `tests/operations/test_commitments.py:62-68`.
- The threshold boundary:
  - `tests/mandate/test_tiers.py:93-98` (LIMIT gives Tier 1, LIMIT+1 gives Tier 2);
  - `tests/operations/test_commitment_contracts.py:80-85`.
- **No test pins the *tier* at exactly 74 bp.** The tests above pin the outcome, and the tier on neighbouring rates.
