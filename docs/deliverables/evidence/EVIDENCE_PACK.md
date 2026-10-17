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

---

## 5. The router against a fair baseline

**Why the E9 gate's baseline is not like-for-like.** `line_first_baseline` (`services/api/evals/suites/funding.py:450-483`)
draws the line first and then the cheapest other committed source, taken from `levers(o)`, which is *every* committed lever.
That includes a buyer's early payment (`EARLY_PAY`) and bank-bill discounting (`DISCOUNT_BILL`). For those,
`Oracle.kind_unrunnable` (`funding.py:235-238`) says: "No operation asks a buyer to pay early or discounts a bill." The router,
by contrast, ranks such legs as "cannot run today". So the gate's "saving vs line first" (**¥−3,491.40 over 21 scenarios**,
`evalfull/latest_report.md:24`) compares a runnable router against a baseline that uses levers no operation can pull.

**The like-for-like baseline (this pack).**
- `scripts/analysis/stress_and_baseline.py --only baseline` runs the suite's own `line_first_baseline` again on the same 26
  scenarios (`scenarios(16)`, seed 20261001).
- `levers` is restricted to `runnable_only=True`: the same committed facilities, an advance only on an invoice that exists, no
  buyer early pay and no bills.
- Everything else is the same: day-0 requests with lead times, the same mandate and the same full check.
- The router's plan is `app.funding.plan(state, [], mandate)`.

**Category of each router plan.**

| Category | Count | Scenarios |
| --- | --- | --- |
| Executable now (no owner, no future event, every leg an operation) | **19** | F00, F01, F02, F03, F05, F07, F08, F09, R03–R09, R11, R12, R15, R16 |
| Needs the owner (`needs_owner_approval`) | **1** | R10 (overlaps the rows below) |
| Needs a future event (a leg on an invoice not yet issued, `RI:…`) | **4** | R01, R02, R10, R14 (overlap) |
| Modelled, but no operation exists ("cannot run today": an `EARLY_PAY` or `DISCOUNT_BILL` leg) | **6** | F04, R01, R02, R10, R13, R14 |
| No admissible plan | **1** | F06 (the router says so) |

A plan can fall in several of the last four rows. Each plan's primary category is the first that applies in this order: no
operation, future event, needs owner. That gives 19 executable + 6 cannot run today + 1 none = 26.

**Cost improvement** (only where both are admissible and the router's plan is executable now): **18 scenarios**.
- The router is **cheaper in 3**: F01 by ¥94.87, R03 by ¥28.33, R15 by ¥46.58.
- **Equal in 15**; dearer in 0.
- **Total saving ¥169.78** (median ¥0.00).
- Against the runnable brute force, the router's executable plans are optimal on all 19
  (`evalfull/latest_report.json`, funding `brute_cost_fen == router_cost_fen`).

**Feasibility improvement** (reported separately).
- **1 scenario** (F09, a committed cheap loan that lands late). The router has an executable plan at ¥2,911.71; the runnable
  line-first baseline has **none**.
- In the 6 "cannot run today" scenarios, the runnable baseline also finds nothing. The router at least names a modelled plan
  and flags it, but **neither can execute today**.
- The gate's all-lever baseline looked feasible in 3 more scenarios (R01, R13, R14) only because it used early pay or bills.

**What the gate's "9/26 with a gap" becomes on a fair baseline.** The router is strictly better on **4 of 26**: 3 cheaper and 1
feasible where the baseline is not. Without the unrunnable levers, line-first is optimal in the other 15 executable scenarios.

| Scenario | Router plan category | Router | Line first, gate (all levers) | Line first, runnable only | Gate baseline used |
| --- | --- | --- | --- | --- | --- |
| F00_golden | executable now | ¥3,113.93 | ¥3,113.93 | ¥3,113.93 | |
| F01_dear_line | executable now | ¥3,689.75 | ¥3,784.62 | ¥3,784.62 | |
| F02_cheap_early_pay | executable now | ¥3,113.93 | ¥1,608.94 | ¥3,113.93 | EARLY_PAY |
| F03_bill_held | executable now | ¥3,113.93 | ¥1,569.03 | ¥3,113.93 | DISCOUNT_BILL |
| F04_no_new_borrowing | cannot run today | ¥4,919.03 | — | — | |
| F05_pending_cheap_ggl | executable now | ¥3,113.93 | ¥3,113.93 | ¥3,113.93 | |
| F06_uncovered | no admissible plan | — | — | — | |
| F07_big_line_clean_down | executable now | ¥2,272.44 | ¥2,272.44 | ¥2,272.44 | |
| F08_late_payroll | executable now | ¥3,113.93 | ¥3,113.93 | ¥3,113.93 | |
| F09_committed_cheap_loan_late | executable now | ¥2,911.71 | — | — | |
| R01 | cannot run today | ¥3,586.19 | ¥3,925.23 | — | EARLY_PAY |
| R02 | cannot run today | ¥3,921.81 | — | — | |
| R03 | executable now | ¥3,960.81 | ¥3,982.58 | ¥3,989.14 | DISCOUNT_BILL |
| R04 | executable now | ¥2,426.51 | ¥2,426.51 | ¥2,426.51 | |
| R05 | executable now | ¥3,331.72 | ¥3,331.72 | ¥3,331.72 | |
| R06 | executable now | ¥2,594.21 | ¥2,547.66 | ¥2,594.21 | EARLY_PAY |
| R07 | executable now | ¥1,848.50 | ¥1,780.06 | ¥1,848.50 | DISCOUNT_BILL |
| R08 | executable now | ¥2,609.87 | ¥2,387.30 | ¥2,609.87 | DISCOUNT_BILL |
| R09 | executable now | ¥2,567.33 | ¥1,905.32 | ¥2,567.33 | EARLY_PAY |
| R10 | cannot run today (needs owner) | ¥5,931.81 | — | — | |
| R11 | executable now | ¥2,259.45 | ¥2,259.45 | ¥2,259.45 | |
| R12 | executable now | ¥1,820.89 | ¥1,820.89 | ¥1,820.89 | |
| R13 | cannot run today | ¥2,845.39 | ¥3,063.64 | — | DISCOUNT_BILL |
| R14 | cannot run today | ¥1,808.65 | ¥2,093.76 | — | EARLY_PAY |
| R15 | executable now | ¥5,628.49 | ¥5,227.51 | ¥5,675.07 | EARLY_PAY |
| R16 | executable now | ¥2,384.39 | ¥2,384.39 | ¥2,384.39 | |

Raw: `<scratch>/sb/baseline.json`. The router figures match `evalfull/latest_report.md:442-467` row for row.

---

## 6. Capex: which structures the search evaluates

**What it evaluates.** Standalone structures only, one at a time. In `services/api/app/capex/evaluate.py`, `evaluate_capex`
(lines 795-840) tests:
- **"Cash + credit line"** (`_cash_line`, lines 677-766).
- **Each candidate facility at one term.** These are `LOAN`, or `LEASE` for an equipment lease (`_financed`, lines 474-607;
  `_kind`, 340-341). The defaults (`app/capex/models.py:40-44`) are FAC-ETL 18 months (an illustration only), FAC-ETL 36 months
  and FAC-LEASE 48 months. `StructureKind = Literal["CASH_LINE","LOAN","LEASE"]` (`models.py:26`).
- **Selection** is the lowest `charges_total_fen` (interest + upfront fee) among the feasible, non-hypothetical structures
  (lines 837-840).
- `_liquidity` (lines 413-471) projects only `[draw]` on the candidate facility. No bridge is ever added.
- `app/capex/plans.py` does combine, but only across *projects and start months*: `itertools.product`, line 484, with one
  option per project. It never stacks two facilities on one purchase.
- A cash + line structure that actually draws the line has `charges_total_fen = None` (lines 759-762). It is therefore never
  selectable (line 837).

**Golden result** (re-run in this pack by `scripts/analysis/capex_bridge.py`, which calls `evaluate_capex(CapexRequest(), …)`):

| Structure | Result | Total charges | Reason |
| --- | --- | --- | --- |
| cash + line | INFEASIBLE | — | `RESERVE_BREACH` day 0 (−¥50,000), `CLEAN_DOWN_BREACH` |
| loan 18 m | REJECTED (illustration) | ¥26,950.84 | `DSCR_BREACH` 1.13× (months 1–3) and `RESERVE_BREACH` day 44 |
| **loan 36 m** | **REJECTED** | **¥53,206.14** | `RESERVE_BREACH` **day 44, cash ¥296,855.38**, i.e. **¥3,144.62 short for 3 days** (back above the reserve on day 47) |
| **lease 48 m** | **SELECTED** | **¥92,327.32** | first payment day 40 leaves ¥300,576.51 |

These are pinned by `tests/capex/test_evaluate.py:53-80` and `golden_values.json:52-81`. The lease costs **¥39,121.18** more
than the 36-month loan (`lease_minus_36m_interest` 3,912,118 fen).

**The 36-month loan plus a liquidity bridge** (read-only, computed with existing functions).
- `scripts/analysis/capex_bridge.py` rebuilds the screen's own 36-month scenario: the same granted copy of FAC-ETL,
  `_purchase_flows` and `_Base`, with the same breach rule (`_Base.breach_day`).
- It adds one `FundingAction` DRAW on the committed **FAC-LINE**: ¥150,000 limit, 6.4%, bullet, 0-day lead.
- Results:
  - The **smallest bridge** found is **¥3,144.62** drawn on day 44 and repaid on day 47. Day 47 is when RI:BUYER-1:2's
    receipt arrives.
  - The structure then **has no breach day**. `covenants.evaluate` on that projection reports **no violation**: the DSCR of
    the 36-month loan is 1.43× (months 1–3) and 1.77× after, and no clean-down breach.
  - **Bridge interest** is `line_interest(314,462, 640 bp, 3 days)` = **¥1.65**.
  - **Total charges: ¥53,206.14 + ¥1.65 = ¥53,207.79**, against the lease's **¥92,327.32**. That is **¥39,119.53 cheaper**.
  - The bridge is above the ¥1,000 minimum action. A rounder ¥10,000 bridge for the same 3 days would cost about ¥5.26 (simple
    interest), so the conclusion holds.

**Limits.**
- This combination is **not** a product path. No code in `app/capex` evaluates it, and the screen would still select the lease.
- The cash path relies on the same conservative books the screen uses: the purchase on day 14, RCV-A on day 32 and the next
  receipt on day 47.
- The screen measures breaches *relative to the books without the purchase*. The golden books' own ¥405,000 gap on days 12–31
  is outside the structure's responsibility in both cases.
- **Finding for the document:** "FLOW selects the cheapest feasible structure" is true only *among standalone structures*.
  Describe the search as standalone, and name the 36-month loan + bridge as a known gap.

---

## 7. Conservatism and stress (golden books, read-only)

**Command.** `scripts/analysis/stress_and_baseline.py --only stress`.
- Each stress is a `model_copy` of the golden state (`load_scenario()`), read with the product's own kernel:
  `app.strategy.impact._read_kernel_uncached`, which gives the router's committed plan and the CONSERVATIVE unfunded
  trajectory.
- `covenants.evaluate` is run on the funded projection.
- The product's buyer-wide stress `app.strategy.impact.stress(books, mandate, "BUYER-1", delays=(0, 10))` is run as well.
- RCV-A: ¥420,000, issued day −13, 45-day terms, due day 32. Monthly EBITDA ¥90,000. Reserve ¥300,000.

| Stress | Lowest cash, unfunded (day) | Breach: max shortfall, days below | FLOW's plan (committed) | Plan flags | Funded lowest | Covenants |
| --- | --- | --- | --- | --- | --- | --- |
| **Base** (no stress) | −¥105,000 (day 30) | ¥405,000; 20 days (first day 12) | line ¥150,000 (repaid day 32) + invoice financing ¥255,000 on RCV-A = **¥3,113.93** | executable now; no owner | ¥300,000 | none |
| **RCV-A 10 days late** (terms 45 → 55 on the copy) | −¥105,000 (day 30) | ¥405,000; **30 days** | line ¥150,000 repaid **day 42** (¥1,104.66) + invoice financing ¥255,000 (¥4,544.59) = **¥5,649.25** | executable now; **needs the owner**: the advance's effective annual cost is 16.68%, above the 15.00% ceiling (39 days billed as 2 × 30-day periods) | ¥300,000 | none |
| **RCV-A: only 50% received** (face ¥210,000 on the copy) | −¥105,000 (day 30) | ¥405,000; **35 days** | line ¥150,000 + invoice financing ¥57,400 + **buyer early pay ¥200,000 on RI:BUYER-1:2** = **¥3,753.13** | **cannot run today** (an early-pay leg on a future invoice; no operation exists) | ¥300,000 (modelled) | none |
| **EBITDA −20%** (¥72,000 a month) | −¥105,000 (day 30): cash unchanged (EBITDA does not drive cash in the model) | ¥405,000; 20 days | unchanged, **¥3,113.93** | executable now | ¥300,000 | **none**: funded DSCR 1.60× (months 1, 3, 4), 1.50× in month 2 (≥ 1.25×); leverage 2.15× in month 1 (≤ 2.50×) |
| Product stress: every Foshan invoice 10 days late (`stress()`, delay 10) | −¥105,000 (day 30) | ¥405,000; 40 days | **no admissible committed plan** | — | — | — |
| Product stress, delay 0 (control) | −¥105,000 (day 30) | ¥405,000; 20 days | **no admissible committed plan** | — | — | — |

**Reading.**
- The lowest point (day 30, before RCV-A's day-32 receipt) does not move under any receipt stress. What moves is the duration:
  20 days becomes 30, 35 or 40.
- FLOW's response:
  - *10 days late*: it keeps the same legs longer and **stops to ask the owner**, because the cost crosses the APR ceiling.
  - *Half paid*: its cheapest cover depends on a buyer early payment that **cannot run today**, and it says so.
  - *EBITDA −20%*: the ratios fall but no covenant breaks, so the plan is unchanged.
- The product's `stress()` is **more conservative than the router on purpose**. Its assumption text says it treats none of the
  buyer's invoices as financeable and removes the buyer's early-payment offer ("that understates what could be financed by at
  most ¥1,344,000.00"). So even at delay 0 it finds no committed plan, while the router on the real books does (¥3,113.93).
- The document must not quote `stress()` and the router side by side as if they used the same assumptions.

---

## 8. Counter Option A (¥260,000 face at 0.85%) passes re-evaluation, mandate limits and binding

**Where it is generated.** `services/api/app/verifier/counters.py` `early_pay_counter` (lines 360-489).
- **Rate:** `largest_step_below` the break-even, capped by the offered rate, `max_immediate_discount_bp` and the owner's
  constraints (lines 131-134, 373-381).
- **Face:** (need − line available) / (1 − rate), rounded **up** to the ¥10,000 `early_pay_step` (lines 354-357, 389-398; R-10).
- **Inclusion conditions:** the plan keeps the floor (406-408), the counter beats the standing plan (422-426), and it passes
  its own re-check (473-489).
- **Hand calculation:** `fixtures/golden/compute_golden.py:143-152`, giving `counter_a_face` 26,000,000,
  `counter_a_discount` 221,000 and `counter_a_total` 303,599 (`golden_values.json:40-42`).
- **Total ¥3,035.99** = ¥2,210.00 discount + ¥825.99 line (¥147,210 × 6.4% × 32/365), which is less than C0 ¥3,113.93
  (ADR-0007:195).

| Property | Tests (`services/api/tests/…`) |
| --- | --- |
| **Passes re-evaluation** | `verifier/test_counter_property.py::test_every_golden_counter_passes_its_own_recheck` (83-85; ACCEPT or NEEDS_OWNER_APPROVAL, no DSCR, leverage, clean-down or APR breach); `::test_ex01_offers_option_b_at_55_days` (104-146; Option A = (26,000,000, 85, 303,599)); `verifier/test_early_pay_rule.py::test_reverify_accepts_a_commitment_whose_obligation_is_counter_a` (333-339); `operations/test_state_binding.py::test_every_golden_counter_reverifies_on_unchanged_books` (307-320), `::test_real_hook_accepts_a_counter_after_unrelated_books_movement` (323-333), `::test_real_hook_refuses_terms_that_no_longer_verify_on_todays_books` (336-349, STALE_VERDICT) |
| **Within mandate limits** | `verifier/test_counter_a_floor.py::test_golden_ex01_option_a_is_face_26_000_000_at_85bp` (49-57), `::test_the_floor_holds_every_day_with_the_counter_and_the_routers_plan` (60-70; lowest exactly ¥300,000 on day 30), `::test_cost_is_the_discount_plus_the_plan_and_the_plan_adds_no_early_pay` (73-82; 221,000 / 82,599 / 303,599), `::test_face_nets_at_least_the_gap_and_is_a_whole_step` (85-103); `verifier/test_golden_verdicts.py::test_ex01_counter_a` (117-130); `verifier/test_contract_fields.py::test_ex01_counter_forward_values` (57-61; forward value 0) and `::test_counters_fit_the_cap_with_their_forward_value` (89-92); `api/test_compare.py::test_the_demo_rows_as_pinned` (111-118; ACCEPT, TIER_1, no codes) |
| **Binds to a commitment** | `verifier/test_e2e_commit.py::test_ex01_option_a_then_line_draw_executes_at_tier1` (69-94; `c.obligations == a.obligations`, forward value 0, EXECUTED at TIER_1, ACTIVE, `verify_chain`); `api/test_buyer_message.py::test_the_buyers_yes_makes_the_offered_counters_agreement_under_the_owner` (161-172; `terms_hash`, `verdict_id`, OWNER, AGREED, ALREADY_ACCEPTED); `api/test_negotiate_binding.py::test_a_bound_send_of_option_a_still_works_and_matches_the_unbound_numbers` (55-59) and its stale-state refusals; `operations/test_commitments.py::test_changed_terms_hash_is_refused` (154-159) |

**Caveats.**
- No test directly asserts 85 bp ≤ `max_immediate_discount_bp` (150) for Option A. The cap is enforced in code at
  `counters.py:378-379`.
- Some tests still carry **older Option A faces** that do not pin today's ¥260,000:
  - ¥257,200 in `test_early_pay_handcalc.py:142-149` and `test_early_pay_rule.py:137-141`;
  - ¥211,900 in `operations/test_partial_settlement.py:56-72` and the docstring of `counterparties/builders.py:119-122`.
- The deck outline and the turn logs (`docs/deliverables/deck_outline.md:79`, `evidence/scenarios/turn_logs.md:21`) still say
  "up to ¥257,200". **Use ¥260,000.** `SECURITY_SELF_ASSESSMENT.md:413` explains the R-10 rounding: 0.86% shown as 0.85%, and
  ¥257,200 shown as ¥260,000.

---

## 9. Commercial agreement lifecycle (from the code)

There are no `DRAFT` or `REVIEWED` status literals. The states are these:
- **DealState** (`app/decisions/state.py:51-70`, chosen by `_deal_state` 565-608): RECEIVED, NEEDS_CLARIFICATION,
  RESPONSE_READY, AUTHORIZATION_REQUIRED, DECLINED, FAILED, NO_DEAL, AGREED, EXPIRED, MISSED, FULFILLED, REVOKED,
  AWAITING_BUYER, REPLIED, LAPSED.
- **CommitmentStatus** (`app/domain/models.py:913-919`; transitions in `app/commitments/lifecycle.py:28-37`): PROPOSED →
  ACCEPTED → ACTIVE → FULFILLED, with EXPIRED and REVOKED as exits.
- **Decision facts** (`app/decisions/facts.py:21`): EVALUATED, SENT (`simulated: Literal[True]`, line 73), QUOTED, RECEIVED,
  OFFERED, BUYER_ACCEPTED, REPLIED, BUYER_DECLINED, OFFER_WITHDRAWN.

| # | Step | Route / code | State after | Simulated? |
| --- | --- | --- | --- | --- |
| 1 | **Counter drafted** by the verifier, each counter re-checked as an offer | `POST /offers/{offer_id}/evaluate` (`app/api/decide.py:196`); `make_counters` / `counter_recheck` (`app/verifier/evaluate.py:712-719`; `counters.py:163-175`) | RESPONSE_READY (`state.py:606-607`), or AUTHORIZATION_REQUIRED for Tier 2 | real logic |
| 2 | **Reviewed** by the owner: text, `message_hash`, `terms_hash` | `GET /offers/{offer_id}/counters/{counter_id}/message` (`app/api/outbound.py:329`; `terms_hash` line 268). Blocked for UNVERIFIED_SENDER, NOT_SENDABLE, WINDOW_PASSED, NO_WORDING, OUTBOUND_BLOCKED (80-91, 275-294) | unchanged | real |
| 3a | **Bound send to the simulated buyer** | `POST /negotiate/{offer_id}` with `verdict_id`, `counter_id`, `state_version` (`decide.py:342-350, 405-601`). 409 COUNTER_CHANGED (VERDICT_CHANGED / COUNTER_NOT_IN_VERDICT / BOOKS_CHANGED), ALREADY_SENT, OFFER_SENT_OUTSIDE, NO_SIMULATED_BUYER, lapsed (456-482) | SENT fact; the buyer kernel answers | **simulated buyer** (`app/counterparties/buyer.py`, `negotiation.py`) |
| 3b | **Or marked as sent outside FLOW** by the owner | `POST /offers/{offer_id}/counters/{counter_id}/offered` (`outbound.py:348-396`): verdict_id, state_version, mandate in force, exact `message_hash` (MESSAGE_CHANGED / MESSAGE_LANGUAGE). Correction: `POST …/offered/withdraw` (580-601) | OFFERED fact; AWAITING_BUYER until `valid_until_day`, then NO_DEAL (`state.py:598-599`). The simulator, accept-as-asked and chat then refuse (`decisions.py:101-115`, `nl/pipeline.py:115-123`) | **real but manual**: FLOW transmits nothing |
| 4a | **Buyer response, simulated** | inside 3a: on the kernel's ACCEPT, `propose_commitment` then AcceptOffer as AGENT (`decide.py:514-520`), the gap funded through `_ops_for_plan` (353-370, 548) | → step 5 | simulated |
| 4b | **Buyer response recorded by the owner** | `POST …/buyer-accepted` (`outbound.py:455-513`): needs the OFFERED fact with the same `message_hash` (NOT_OFFERED), the day not past (OFFER_EXPIRED), counter `terms_hash` = sent `terms_hash`, the invoice still owed (OFFER_LAPSED), the state_version (BOOKS_CHANGED), a mandate in force. Then AcceptOffer as OWNER (op id `buyer-yes-`). `…/buyer-declined` (554-572) gives NO_DEAL; `POST /offers/{id}/buyer-reply` (610-646) compiles a reply as a new request (REPLIED) | → step 5 | real, recorded by the owner |
| 5 | **Terms re-verified** in the executor | `_screen_commitment` (`app/operations/executor.py:945-986`): `check_acceptance` (`lifecycle.py:134-157`; REPLAY, COMMITMENT_EXPIRED, TERMS_CHANGED, all `hmac.compare_digest`), MANDATE_VERSION_MISMATCH, F-07 (terms_hash and forward value equal the verdict's or a counter's). `_check_binding` (1046-1115): invoice owed, CONFLICTING_COMMITMENT, caps; if `state_version` moved, `Runtime.reverify` (`app/api/runtime.py:83-101`), else STALE_VERDICT | — | real |
| 6 | **Commitment recorded** | `_commit` (`executor.py:1117-1140`): PROPOSED → ACCEPTED → ACTIVE, invoice adjustments, ForwardConcession, nonce used. A Tier 2 commitment goes to PENDING_APPROVAL (671-676), and the owner decides through `POST /approvals/{approval_id}` (`app/api/operations.py:348-374`) | AGREED | real (hash-chained log) |
| 7 | **Financial execution** | DrawFacility and SubmitInvoiceForFinancing through the same executor (`decide.py:353-370`; `executor.py:1167-1184`); a receipt from the bank feed (or the owner) moves the commitment to FULFILLED (`executor.py:1354`) | FULFILLED | **simulated bank, facilities and clock** (`executor.py:14,312`); demo receipt `POST /demo/bank-receipt` is demo-only and books as SYSTEM (`app/api/demo_bank.py:21-43`) |

Every gate (nonce, terms hash, re-verify, the hash-chained log) runs on both paths, 3a/4a and 3b/4b.

---

## 10. The model's contribution

**Batch-2 contracts, offline rules against DeepSeek (cached).**
- Source: scratchpad `contract-cn2/`. `predictions_offline_rules.json` holds the rules run; `predictions.json` holds the
  DeepSeek reading replayed from `contract-cn2/cache/` (`_flow.compiler: fixture-cache`); `answer_key.json` is the key.
- **Rules: 0/17 party names.** `buyer.name` and `seller.name` are `null` in 17 of 17 text-layer contracts, compiler `rules-v1`.
  All 17 ABSTAINED on parties.
- **DeepSeek: 14/17.** It returns names on 17 of 17; 14 match the key for both buyer and seller. The other 3 have the right
  names with buyer and seller **swapped**: CN-052 (a supplement), and CN-059 and CN-065 (construction subcontracts).
  `b2fix/b2-base.log` shows `buyer.name` and `seller.name` each at `14/17`.
  - After the batch-2 fixes it is 16/17 (`b2fix/b2-final.log`); only CN-052 is still wrong.
- The other 13 of the 30 batch-2 contracts were refused before any model call (`SCANNED_PDF`, `b2-final.log`).

**Why the rules miss the parties.** The party pattern in `services/api/app/compiler/contract_rules.py:56-59` matches only English
forms such as `<Company Co., Ltd> ("Supplier")`. It has no Chinese alternative. The contract-number rule does have one: rules
read `FB-2026-509` from CN-041.

**Examples.**
- **CN-041** (construction subcontract). The source reads "甲方（承包人）：中山市华岳城建集团有限公司" and
  "乙方（分包人）：佛山市瑞丰消防科技有限公司". Rules returned null/null. DeepSeek returned both names, matching the key.
- **CN-068** (equipment lease). The source reads "甲方（承租方）" and "乙方（出租方）". DeepSeek mapped the lessee (承租方, the
  payer) to buyer and the lessor to seller, matching the key. Rules returned null/null.

**Same verifier and grounding for both paths.**
- Every backend's reading goes through `compile_contract` then `build_contract`: cache replay, Claude, DeepSeek and the rules
  (`services/api/app/compiler/service.py:136-150`; the rules backend is last in the chain, lines 70-71, 88-89).
  - The rules path returns the same `ContractResult` type (`compiler/rules.py:371-374`).
- `build_contract` (`compiler/contract.py:611-660`) grounds every term through `_ground_term` (lines 387-391): a term whose quote
  is not found word for word in the document is dropped. Merging, conflict detection, the payer/payee check and cross-checks
  follow (641-645).
- The cache stores the *pre-grounding* reading (`compiler/cache.py:3-4`), so a replay is grounded exactly like a live call.
- **Differences:**
  - Only model backends see **redacted** text (`service.py:15-17, 66-68`).
  - The rules-against-model cross-check runs for *offers* in live mode (`service.py:115-129`), not for contracts.

**Contract-reading scores** (`b2fix/*.log`, "ALL" rows).

| Run | Score | Status | Wrong-value count |
| --- | --- | --- | --- |
| Batch 1 | **502/514 (98%)**, 30 contracts read and 10 refused (e.g. `b1-final.log:87`) | tuned on, not held out | 0 in every run (the "extra" column) |
| Batch 2, first run | **215/285 (75%)** (`b2-base.log`) | **held out** | **31** (contract_no 1, buyer 3, seller 3, end_date 2, retention 1, interest 3, stage percent 3, days 2, unit 4, trigger 9) |
| Batch 2, after fixes | **246/285 (86%)** (`b2-final.log`; also `b2-f6`, `b2-merged`, `b2-redact`); steps f1 230, f2 234, f3 239, f4 241, f5 244, f6 246 | **no longer held out** | **21** (stage fields 3+2+4+9, contract_no 1, buyer 1, seller 1) |
| Digital PDFs only, batch 2 | 138/178 (78%) → 161/178 (90%) | as above | — |

- The **wrong-value counts are derived.** No saved file states them directly. They are the sum of the logs' "extra" column,
  which `services/api/scripts/eval_contracts.py:164-190` defines as a stated value that differs from the key, plus surplus
  stages. `b2fix/sc.py` computes them but printed only to stdout.
- **The repo itself holds none of these figures.** `services/api/evals/contracts_heldout_report.md` says "pending";
  `contracts_heldout_report.json` is `{"pending": true, "contracts": []}`.
- They are reproducible only from the scratchpad. Cite them as "measured in session, 17 Oct, cache replay of recorded DeepSeek
  outputs", not as a committed report.

**Model metadata.** **No: the cache does not record the actual DeepSeek model version.**
- A cache entry holds `doc_ids`, `extraction`, `key`, `kind`, `label`, `prompt_version` (e.g. `contract-v1`) and
  `source_model`.
- Across `fixtures/compiler_cache/` and every scratchpad cache, `source_model` takes only two values: **`deepseek-flash`** (55
  entries) and **`rules-v1`** (57).
- The DeepSeek backend sets `model_id` to its configured alias (`compiler/backends.py:262,266,270`; `DEEPSEEK_MODEL =
  "deepseek-flash"` at `backends.py:34`, `config.py:88`). It does not use the API response's `model`. The Claude backend does
  record `resp.model` (`backends.py:141`).
- Replays report `fixture-cache` (`cache.py:22,85,93,101`). The document must say "DeepSeek, via the `deepseek-flash` alias;
  the underlying model version was not recorded".

---

## 11. Internal inconsistencies, settled

| Item | True value on 975e082f | Source | Documents that disagree |
| --- | --- | --- | --- |
| **Intent count** | **22** | `services/api/app/nl/models.py:16-38` (`class Intent(StrEnum)`): EVALUATE_OFFER, NEGOTIATE, ACCELERATE_RECEIPT, FUND_GAP, REPAY_FACILITY, SHOW_STATUS, SHOW_ALERTS, COMPARE_FINANCING, RECONCILE, SHOW_RATIOS, CAPEX, BORROWER_FILE, **SHOW_DEAL**, EXPLAIN, WHAT_IF, RECORD_FACT, CHANGES, APPROVE, REJECT, COUNTERPARTY_MESSAGE, OUT_OF_SCOPE, AMBIGUOUS. SHOW_DEAL was added in `14324cdf` (5 Oct) and is live (`nl/rules.py:296`, `nl/service.py:346`, `tests/nl/test_show_deal.py`) | "21" (the list without SHOW_DEAL) in `technical_document.md:259`, `README.md:175`, `docs/SYSTEM_WALKTHROUGH.md:1295`, `docs/deliverables/TEST_CASES.md:33`. The LLM classifier's closed vocabulary (`nl/classifier.py:33-34`) is a separate list of 10 |
| **Receipts** | From the **bank feed or the owner**. `ReceivePayment` is Tier 1 for SYSTEM and OWNER and Tier 2 for anyone else (`app/mandate/tiers.py:13-15, 66-67, 98-99`; `executor.py:146, 913-918`) | Route `POST /operations` with the owner token keeps `requested_by: OWNER` (`app/api/operations.py:78-86`); test `tests/mandate/test_tiers.py:89`. No web UI posts an owner receipt, and an owner receipt carries **no** "unverified" or provenance label: Activity shows "You" (`app/api/activity.py:49-79`) | `technical_document.md:42` ("only from the bank feed") contradicts its own `:430`. Also `docs/adr/0006-current-books-and-clock.md:37` and `docs/NEGOTIATION_COMMUNICATION_HANDOFF.md:113` |
| **"The agent never applies for a loan"** | The agent **prepares and queues**; only the owner's Tier-2 approval applies, and the result is a **simulated PENDING facility that counts as zero**. `ApplyForFacility` is always Tier 2 (`tiers.py:45, 93-94`; `models.py:1030-1036`: "the agent prepares; only the owner applies") | `POST /capex/apply` is owner-only (`app/api/capex.py:28`) but builds the operation with `requested_by=Actor.AGENT` (108-112), so it answers PENDING_APPROVAL. Approval moves NOT_APPLIED → PENDING only (`executor.py:1482-1489`). No simulated lender ever commits it. Tests `tests/capex/test_api.py:89,115`, `tests/operations/test_tiers.py:120` | `technical_document.md:87` vs `:431`; `SECURITY_SELF_ASSESSMENT.md:71` says "Requested by: owner". Wording risk: after approval the UI says "FLOW sent it to the lender" (`app/api/presentation.py:980-982`), but no lender integration exists |
| **Route count** | **100** (99 under `app/api` + `GET /health`) | section 1.11 | none, once the 99 is explained |
| **Migrations** | head **0009**, `0009_audit_guards` | section 1.12 | — |
| **SEC-20 rate limiting** | **FIXED.** `services/api/app/api/ratelimit.py`: per-minute defaults owner 3000, agent 1200, bank 600, buyer 120, anon 300 (L36); `RATE_LIMIT_<KIND>` overrides; `RATE_LIMITS=0` off (L51-52). Bucket = credential + client address, one per buyer (L69-82); ≤ 10,000 buckets (L37); 429 `RATE_LIMITED` with `Retry-After`, OPTIONS exempt (L111-120). Mounted at `app/main.py:36,58` | `tests/security/test_rate_limits.py` (L33, 41, 48, 55, 65) | residual: callers behind one proxy share an address (`SECURITY_SELF_ASSESSMENT.md:416`) |
| **SEC-12 headers and CSP** | **FIXED.** API: nosniff, `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `no-referrer` (`app/main.py:53-66`). Web: a per-request nonce CSP in `apps/web/proxy.ts:9-30` (the Next 16 middleware) built by `apps/web/lib/csp.ts:10-23`: `default-src 'self'`; `script-src 'self' 'nonce-…' 'strict-dynamic'` (`'unsafe-eval'` only in development); `style-src 'self' 'unsafe-inline'`; `connect-src 'self' <API>`; `object-src 'none'`; `base-uri 'none'`; `form-action 'self'`; `frame-ancestors 'none'`. Static headers in `apps/web/next.config.mjs:11-21` | `tests/security/test_headers_and_docs.py:11,22`; `apps/web/scripts/csp.test.mjs:9,16,23` (in `test:unit`) | no HSTS and no upgrade-insecure-requests (`csp.ts:7-8`) |
| **SEC-21 session binding** | **FIXED.** A chat session continues only if actor, `owner_auth` and principal all match; otherwise a fresh id is issued (`app/nl/sessions.py:69-70, 109-125`). The principal is owner, agent, `buyer:<id>` (verified key) or anon (`app/nl/service.py:96-112`) | `tests/nl/test_session_binding.py:32,41,51` | — |
| **SEC-08** | **FIXED, both halves.** Database: `app/persistence/guards.py` makes operations, used_nonces and security_events append-only, approvals decide-once and no delete, and blocks TRUNCATE on PostgreSQL (L36, 55-73, 88-135). The reset lifts guards only with the table owner's `DISABLE TRIGGER USER` (L167-188); an advisory lock covers install (PG-1). Executor half (merged after `719c9dcf`, `ec1fbb0c`): a decision already in the log raises `ApprovalAlreadyDecided` (`executor.py:377-385`) | `tests/persistence/test_audit_guards.py:54,65,75,85`; `tests/operations/test_sec08_decided_in_log.py:40,52,64` | the doc calls the executor half "merging" (L132, 272, 408): it is merged |
| **Migration 0009 guard** | **FIXED.** SQLite triggers `trg_security_events_no_update` / `_no_delete`, `trg_approvals_decide_once` (only PENDING → APPROVED/REJECTED, other columns fixed) and `trg_approvals_no_delete` (`0009_audit_guards.py:74-96`). PostgreSQL redefines `termsledger_append_only()` **without** 0003's `termsledger.allow_reset` session bypass, adds `termsledger_decide_once()`, row and truncate triggers, and `REVOKE ALL … FROM PUBLIC` (L27-38, 56-72, 99-119) | `tests/persistence/test_audit_guards.py` | — |

### 11.1 Facts in `docs/SECURITY_SELF_ASSESSMENT.md` (v2) that the technical document must match

Line numbers refer to that file.

**Document control**
- **Version and assessed commit:** v2.0, 17 Oct 2026; assessed `dev` at **`719c9dcf`**, certified 17 Oct (L11).
  - That commit is an ancestor of 975e082f. No certification of 975e082f exists (`docs/security/CERTIFICATIONS.md:13,46`).
- **Product naming:** "TermsLedger v2 (FLOW)". Lenders, buyers and the bank feed are **simulated** (L13).
- **Verdicts:** local simulation **GO**, network demo **conditional GO**, production **NO-GO** (L17, 452-454).

**Attacks and findings**
- **Attacks:** **259** (126 API + 133 chat), **0 harm** (L15). The chat attacks split 43 owner / 64 buyer / 26 agent key (L199).
  - Results table: 126 API attacks, **124 detected (98.4%)**, **92 security events (73.0%)**; PE-07 and PE-14 undetected
    (L208-222).
  - The 133 chat attacks: 86 raised an event or refusal and 47 did not, 39 of those being consent attacks (L224).
- **Findings:** **39, all closed** (A01–A13 plus 26 from red-team rounds 1–5: 3/7/3/7/6) (L16, 27, 239-243).
- **External red team, 16 Oct:** 17 tests; the live DeepSeek tier made 100 calls for about US$0.04 (L29, 247).
  - **The doc contradicts itself:** "three findings" (L29) against "five findings" (L247). Settle this before quoting.

**Routes and callers**
- **Routes:** 76 on `e8e270f8`, 94 on `0f92d433`, **100 on `719c9dcf`**, plus `/docs`, `/redoc` and `/openapi.json` (L92,
  104, 284). About 21 of the 100 are driven by the catalogue (L298).
- **Callers:** "seven kinds of caller" (L30) against "Six kinds of caller" and a 6-row table (L38, 48-55). This is a further
  inconsistency.
- **Buyer limits:** ≤ 5 documents of 4,000 characters; 5 a simulated day across both routes, then 429
  `BUYER_BUDGET_EXHAUSTED` (L53). Anonymous intake: 200 a simulated day (L54).
- **Refused credentials** are logged up to 300 an hour (SEC-10). Demo credentials work only with `DEMO_MODE=1` (SEC-07).
  Without it, an unset credential gives 503 (F-06) (L57).

**Tiers**
- Tier-1 early pay: break-even 0.8832% for 30 days. Its "capped at ¥100,000" (L65) is the *forward-value* threshold (section 4).
  The counter rate is 0.85% (L75).
- `ReceivePayment` is Tier 1 from the bank feed **or the owner** (L69).
- `ApplyForFacility` and `AddFacility` are Tier 2 (L71; see 11 above on "Requested by: owner").
- `CommitPurchase` is Tier 2, owner only (L72).
- Tier 3: guarantee, collateral, equity, mandate change, unknown types (L73).

**Executor, store and invariants**
- The executor has **8 gates**; a unit of work retries at most 8 times, then answers 409 (L140, 144).
- Migration **0003** guards the log; **0009** is SEC-08; **0002** enables RLS with no policies (L144, 358-359).
- **14 invariants** (L108-121), including:
  - SEC-16: 409 for a reused document id;
  - SEC-17: 413 above 5 documents or 4,000 characters;
  - SEC-20: 429.
- SEC-21 is tested in `tests/nl/test_session_binding.py` (L123).
- **Language boundary:** 231 items (76 buyer, 90 owner, 15 agent, 50 malformed; 194 en, 33 zh, 4 mixed), 0
  wrong-and-material, scored 3 Oct, no live run (L31, 292).
- **Concurrency:** 8 invariants, 2 worker processes, SQLite and PostgreSQL 17; 3 of 3 clean on `719c9dcf` (L32, 290).

**Certification and residuals**
- **Suite:** the only failure is **#161**, a hash pin (L286).
- **Stale "merging" labels.** These are all **merged on 975e082f**, so write "merged":
  - SEC-08 executor (L132, 272, 408);
  - OUT-1b (L178, 423);
  - RT-2 422 `DOCUMENT_INVALID` (L177, 424);
  - RT-1 `next` 16.3.8 / `source-map-js` 1.2.2 (L188, 420);
  - PRIV-1 to PRIV-3 (L18, 176, 292, 343, 347, 410).
- **Open:** R-2, R-14, PRIV-4/5, R-3, R-16, SEC-19/R-4, R-5, R-15, CAPEX-NC. **Mitigated:** R-13, R-7, R-10, SEC-20, RT-3
  (partly). SEC-22 is a known limit by the owner's decision. Production blockers: SEC-06, SEC-11, LIVE, OPS (L398-401).
- **Placeholders** still in the doc: team name, submission date, licence (`[TEAM: …]`, L7, 9, 374).

---

## 12. Features to describe

### 12.1 Landing today (on their branches, **not yet on dev** at 975e082f)

Each has `git log origin/dev..origin/<branch>` non-empty.

| Branch (head) | Behaviour |
| --- | --- |
| `feat/attach-fullwidth` (`269d4ded`, with `dbab3412`) | The Attach deals page (`apps/web/app/documents/page.tsx`) drops the side panel and the two-column grid: the upload card becomes one full-width drop zone, followed by "What it is" and "Who it is with". An "Or try a sample:" row shows one button per `GET /fixtures/contracts` entry, with one shared format chooser. It is shown, and the fixtures are fetched, **only on the demo books** (`useSetupStatus().status?.books === "demo"`, replacing the `DEMO_BUILD \|\| API_MODE` build flag) |
| `feat/contract-party-check` (`92ea5d01`) | `POST /documents` checks that the chosen counterparty is a party the uploaded contract names. A deterministic matcher in the new `services/api/app/contracts/parties.py` normalises NFKC width, case, punctuation and whitespace, then accepts equality, word-bounded containment or the registry short name. **`PARTY_NOT_NAMED` blocks** when no named party matches. **`PARTY_UNCHECKED` warns** when the reading found no names. The lender is checked only when one is named. Tests: `tests/contracts/test_parties.py`, `tests/api/test_document_parties.py` |
| `fix/demo-inbox-own-books` (`0ebdb6e2`) | Deals shows the simulated demo inbox (and counts it) **only when the books are the demo books**; on the owner's own books it is empty (`components/deals/flow/deals-page.tsx`, `inbox-list.tsx` `messages` prop). Before, setup numbering the owner's first customer BUYER-1 made Foshan's simulated messages appear on real books |
| `fix/set-aside-count` (`35501455`, `861c2ea9`) | The "messages set aside" count (`/ledger` refusals, `/audit` `refusal_summary`) now **excludes failed sign-ins** (`SEC-AUTH-` events, `_set_aside_events()` in `app/api/read.py`). They are still listed in Security, Activity and the `/audit` event list. Fresh demo books no longer say "12 messages were set aside" from pre-sign-in 401s. The audit mock was re-recorded: 9 → 7 |

### 12.2 Already on dev (975e082f)

- **Capex hub, "Capex & purchases".**
  - The nav label is at `apps/web/lib/dictionary.ts:84`; the route is `apps/web/app/capex/`; the nav entry is
    `components/app-shell.tsx:50`.
  - It is the buy side's single page: health figures, Your purchases, the contract workbench and a quick check.
  - Commits: folded in `e86c1e58` from feat/capex-hub@`d3c3bf18`, renamed in `5a336331`, merged in `3dcbd2d2`.
- **Deals is selling only.** `5a336331` removes the Buying card and its `/purchases` read from Deals. `/buy` opens from, and
  leads back to, Capex & purchases. Covered by `apps/web/e2e/buyside.spec.ts:10`.
- **Mandatory redaction, PRIV-1 to 3** (`817bcaad`, merged in `059ab7cb`).
  - PRIV-1: every provider backend (Claude, DeepSeek, the classifier's CallableBackend) redacts its own input by default,
    unless `redact=False` or `LLM_REDACT=0` (`compiler/backends.py:65`, `nl/classifier.py:126`, `compiler/redaction.py:315`,
    `compiler/service.py:66`).
  - PRIV-2: labelled addresses end at a clause boundary, ≤ 120 characters.
  - PRIV-3: a labelled phone or account number needs 7 or 8 digits.
  - Test: `tests/compiler/test_redaction_mandatory.py`.
  - PRIV-4 and PRIV-5 remain open.
- **Dylan's UI.** `8dc4e441` (15 Oct) is Dylan's redesign of Home, Cash, What-if, Receivables, Activity, the trust pages and the
  shell, on dev's Deals. Later folds: `8a6c4c6b` / `fe56b357` (final UI), `0bb77282` / `719c9dcf` (type sizes and the FLOW
  logo), `eee7ec70` (deal rows as cards), `eb1c9e83` (Attach a deal). The landing page is `/welcome` (`8e80b8bc`).
- **Next 16.3.8.** The lockfile resolves `next@16.3.8` (`apps/web/pnpm-lock.yaml:1737`, RT-1 commit `ce7791bd`). It fixes 7
  advisories, including GHSA-cjq9-62q9-8jv4 (high, SSRF).
  - `apps/web/package.json:25` still declares `^16.3.7`, which resolves to 16.3.8.
  - `eslint-config-next` and `@next/eslint-plugin-next` stay at 16.3.7.
  - Write "Next.js 16.3.8 (lockfile)".
- **Setup lockout fix** (`44ada5b9`, merged in `049ec6a3`, 16 Oct).
  - `_books_are_blank` in `services/api/app/api/setup.py:98-103` ignores refused-sign-in events (`SEC-AUTH-`). A failed
    sign-in no longer counts as use of the books, so a new owner is not locked out of setup.
  - Test: `tests/api/test_setup_books.py`.
