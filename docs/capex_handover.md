# CAPEX buy-side handover

The living record of the CAPEX buy-side work: what was asked, what was decided, what is built, and what is left.
**Update this file with every change.** If you are picking this up in a new session, read sections 1 to 4, then
continue from the first row of section 5 that is not DONE.

- Branch: `feat/capex-buy-side` (cut from `test/for-latest` at `4804370d`).
- Feature flag: `FEATURE_CAPEX_CONTRACTS` (API). It stays **off by default** until the web half and the full gate pass;
  section 7 says how to switch it on locally.
- ADR: `docs/adr/0013-capex-buy-side.md`. Its status changes from "proposed" to "accepted" only when the work merges.

## 1. What the owner asked for (14 Oct 2026)

A second kind of deal, where **the SME is the buyer**: a capital-equipment (CAPEX) contract with a vendor. The existing
sell-side deal analysis and the way it optimises for the owner must keep working unchanged. The buy side must also say:

1. whether the company's cash flow is healthy;
2. which ways there are to pay: cash, the committed credit line, buying on the vendor's credit terms, bank loans and
   leases;
3. the best options and their combinations (permutations) for the company's long-term plans;
4. the company's liquidity ratio;
5. for higher-value loans, which loans the company is eligible for.

The owner approved the architecture in conversation and asked for a thorough, critical implementation, with this
file kept current in case the work changes hands.

## 2. Ground truths found in the code (read before changing anything)

These were checked against the code on 14 Oct 2026 and shape every decision below.

| Fact | Where | Consequence |
|---|---|---|
| The daily projection runs `mandate.horizon_days` = **120 days** | `fixtures/scenarios/golden_sme.json`, `app/financial/trajectory.py` | Any vendor payment after day 120 is invisible to the conservative reserve test. The buy side must say so, and long-term plans need a separate **monthly estimate** (phase 7), never presented as the conservative test. |
| EBITDA is the constant `state.monthly_ebitda_fen`; flows never change it | `trajectory.py` (month points) | Booking vendor payments as scheduled `CashFlow`s moves cash only, so DSCR is not distorted by a capital payment. |
| The clock posts every scheduled flow on the day it falls | `app/clock/__init__.py` `close_days` | Committed vendor payments are paid by the simulated bank like payroll, with no new clock code. |
| `contract_records.kind` is a `String(32)` column, not an enum | `migrations/versions/0007_contract_records.py` | A new document kind needs **no migration**. |
| The demo confirms **every** fixture in `fixtures/contracts/contracts.yaml` at start | `app/api/documents.py` `confirm_demo_documents` | A capex sample contract must **not** go into that file, or the demo's hash chain and recorded mocks change. It lives in `fixtures/capex/`. |
| The golden books have no `SUPPLIER` counterparty and there is no route to register one | `golden_sme.json`, `app/api/*` | A vendor is accepted at upload for a capex contract (owner-only route) and added to the registry when the owner's purchase commitment executes. |
| The contract reader (`compile_contract`, the rules grammar) already reads PRICE, MILESTONE (share + trigger), RETENTION (share + period), PAYMENT_TERMS (days + basis), EARLY_PAYMENT (discount + window) and LATE_INTEREST, party-neutrally | `app/compiler/contract.py`, `contract_rules.py` | A vendor contract reuses the reader unchanged. **No new `ContractField`**: adding one would change `not_found` on every existing reading (and the recorded mocks). What a contract cannot fix (delivery and acceptance days) is the owner's timeline, entered with the evaluation. |
| `CapexRequest` is echoed inside `CapexResult` | `app/capex/models.py` | Any new request field must be omitted from the serialised form while unset, so existing capex outputs stay byte-identical. |
| `ApplyForFacility` is always Tier 2; `AddFacility` from the owner is Tier 2 and registers the lender | `app/mandate/tiers.py`, `executor._add_facility` | Eligibility results can be acted on through operations that already exist. |

## 3. Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Buy side is a **new document kind** `CAPEX_CONTRACT` plus a **new typed operation** `CommitPurchase`; the sell-side verifier, `Obligation`, `Offer` and commitment lifecycle are not touched | They assume the supplier makes the promises; overloading them risks every pinned sell-side figure |
| D2 | A confirmed capex contract is still never booked by confirmation (ADR-0012 holds). Only the owner-approved `CommitPurchase` (always Tier 2) writes the payment schedule into `state.flows` | Keeps INVARIANT 1: code derives every amount from spans the code parsed, the owner confirmed the reading, and the owner approves the commitment |
| D3 | Payments are `CashFlow`s of a new `FlowKind.CAPEX`, ids `CAPEX:<document id>:<n>` | Engine, clock, alerts and router see them with no new code; the id makes a second commitment of the same contract detectable |
| D4 | The schedule is derived by code from the confirmed reading + the owner's timeline (signing, delivery, acceptance, invoice days). An unknown milestone trigger, shares that do not add to 100%, or a price that is not a lump sum make the schedule **not derivable** (abstain, INVARIANT 10) | No guessing on material semantics |
| D5 | A milestone falls due on its trigger day plus the offset its own words state ("within 45 days after delivery" = delivery + 45); separately stated payment terms are never added on top of a milestone; business days are counted as calendar days | When the due day is ambiguous, earlier is the conservative reading for an outflow; each rule is stated in the result's assumptions |
| D6 | The 90-day **cash coverage ratio** is computed from the books; a balance-sheet current or quick ratio only from owner-entered inputs, labelled `OWNER_ESTIMATE` | The books hold no inventory or trade payables; inventing them would be a wrong number |
| D7 | The lender catalogue is a **synthetic fixture** (`fixtures/lending/catalogue.json`), every product labelled illustrative; eligibility is **indicative**, never a lender's decision | Recommended in conversation; no real lender data is available |
| D8 | A catalogue product never counts for a hard constraint. "Add to my funding menu" is the existing owner-only `AddFacility` (Tier 2), which adds it as NOT_APPLIED; applying is the existing `ApplyForFacility` | INVARIANTS 3 and 4 unchanged |
| D9 | Long-term plans use a **monthly estimate** model over 60 months (the capex default life), labelled EXPECTED/estimate. Decisions inside the 120-day horizon still come only from the conservative daily engine | Daily 1,800-day projections per permutation are too slow, and the engine's horizon is the mandate's |
| D10 | Plans are ranked on **NPV to the owner at the hurdle** of all the plan's cash flows (payments, uplift, loan proceeds, debt service); ties go to the higher lowest headroom | One consistent metric; the single-purchase screen keeps its existing ranking (lowest total charges) unchanged |
| D11 | Feature flag `FEATURE_CAPEX_CONTRACTS`, default off; every change additive, so with the flag off every existing output is unchanged | Engine stability mode (docs/HANDOVER.md section 3); the owner's go-ahead on 14 Oct 2026 is the exception, recorded in ADR-0013 |
| D12 | A vendor not on the registry is accepted for `CAPEX_CONTRACT` only (owner-only route), with an id pattern check; a counterparty id that exists with another role is refused | The owner is shopping, so vendors are new by nature; the buyer and lender paths keep their registry check |

## 4. Architecture (target)

```
 vendor contract ─► POST /documents kind=CAPEX_CONTRACT ─► compile_contract (unchanged reader)
                         │                                   material: PRICE + (MILESTONE or PAYMENT_TERMS)
                         ▼
                ContractRecord CAPEX_CONTRACT, PROPOSED ─► owner confirms (CONFIRM_DOCUMENT, no money)
                         │
                         ▼
   app/capex/schedule.py: confirmed reading + owner timeline ─► PaymentSchedule (or not derivable, with reasons)
                         │
                         ▼
   evaluate_capex(request.schedule=…)  NPV/payback on the schedule; each structure's daily cash test posts the
                         │             real payment days; payments past day 120 reported, not hidden
                         │             + vendor early-pay discount priced against the cost of funds
                         ▼
   POST /capex/commit ─► CommitPurchase (Tier 2) ─► owner approves ─► flows CAPEX:<doc>:<n> on the books,
                                                                      vendor registered as SUPPLIER
   app/health      : cash health, 90-day cash coverage, owner-input current/quick ratio, debt capacity
   app/lending     : catalogue + indicative eligibility (largest eligible amount by bisection)
   app/capex/plans : permutations of projects × structures × start months on the monthly estimate
   GET /deals      : direction SELL | BUY; BUY rows from the committed and proposed capex contracts
```

## 5. Phases and status

Status: TODO, IN PROGRESS, DONE (with the commit), BLOCKED (with the reason).

| Phase | Scope | Status |
|---|---|---|
| 0 | This file, ADR-0013 draft, feature flag | DONE |
| 1 | `CAPEX_CONTRACT` reading: domain kind, reader material rule per kind, `read_document`, `POST /documents`, record views, fixture in `fixtures/capex/` | DONE |
| 2 | Payment schedule derivation (`app/capex/schedule.py`) with tests | DONE |
| 3 | Schedule-aware `evaluate_capex` (+ vendor early-pay option) without changing any existing output | DONE |
| 4 | `CommitPurchase` operation, executor handler, tier, `POST /capex/contracts/{id}/commit` | DONE |
| 5 | Financial health: cash health, 90-day cash coverage, owner-input ratios, debt capacity (`app/health`, `GET/POST /finance/health`) | DONE |
| 6 | Lender catalogue + eligibility (`app/lending`, `GET/POST /lending/eligibility`, add-to-menu) | DONE |
| 7 | Long-term plan permutations (`app/capex/plans.py`, `POST /capex/plans`) | DONE |
| 8 | Deals read: the buying side (`purchases`, `GET /purchases[/{id}]`) | DONE |
| 9 | Web: Deals → Buying link, /buy, /buy/contract, /finance, /plans, recorded mocks, e2e | DONE |
| 10 | Gate: chunks A and B (+ decisions, pilot, reliability, strategy), web e2e mock suite, scenarios, demo run; then the owner decides the flag default and the commit | DONE: green apart from pre-existing failures (section 10) |

## 6. Change log

Newest last. One entry per change: date, phase, what changed, files, tests, result.

- 14 Oct 2026, phase 0: branch `feat/capex-buy-side` created; code read-through done (section 2); this file written.
  ADR-0013 drafted (`docs/adr/0013-capex-buy-side.md`); flag `capex_contracts` added to `app/config.py` `Features`
  (env `FEATURE_CAPEX_CONTRACTS`, default off) with its message in `app/api/features.py`; AGENTS.md points here.
- 14 Oct 2026, baseline before any engine change: `tests/capex tests/contracts tests/operations tests/compiler` =
  1148 passed, 1 skipped. **Pre-existing failures, not caused by this work** (they fail identically with the changes
  stashed): `tests/deals/test_lang.py::test_the_chinese_read_has_the_same_figures_and_no_english_sentence[/deals]` and
  `[/deals/BUYER-1]` (an English customer name in `queue.needs_you[].customer_short`). Also pre-existing: ruff ISC004 in
  `app/contracts/heldout.py`, mypy `app/compiler/contract.py:374`.
- 14 Oct 2026, phase 1 (capex contract reading):
  - `app/domain/models.py`: `DocumentKind.CAPEX_CONTRACT`; `CONTRACT_READING_KINDS` (buyer + capex); the record
    validator treats both alike (a contract reading, no term sheet, no facility link).
  - `app/compiler/contract.py`: `material_missing(kind, found)`; a capex contract needs PRICE and (MILESTONE or
    PAYMENT_TERMS); `build_contract(..., kind)` (default BUYER_CONTRACT, so every existing call is unchanged);
    `contract_document` gives every non-lender kind the "attachment" channel (buyer contracts unchanged).
  - `app/compiler/service.py`: `compile_contract(doc, kind=BUYER_CONTRACT)`; the kind does not enter the cache key.
  - `app/contracts/records.py`, `views.py`: capex records read and shown like buyer contracts ("Capex contract",
    "设备采购合同"). Only buyer contracts supersede each other (store code unchanged: it already checks the kind).
  - `app/api/documents.py`: `kind=CAPEX_CONTRACT` (403 when the flag is off); the vendor's role is SUPPLIER; a vendor
    not on the registry is accepted for this kind only, with the id pattern `^[A-Z0-9][A-Z0-9_-]{1,63}$` (D12); an id
    on the registry with another role is refused; `GET /fixtures/capex-contracts`; the demo fixture can be uploaded by
    `fixture_id` (md only; other formats 422 FORMAT_NOT_AVAILABLE).
  - `app/domain/fixtures.py`: `load_capex_contract_fixtures`, `capex_contract_fixture_bytes`.
  - Fixture `fixtures/capex/gzpm-2026-114-equipment-purchase.md` (+ `contracts.yaml`): ¥600,000 die-cutting line,
    30% on signing, 60% within 45 days after delivery, 10% retention for 12 months after acceptance, 2% discount for
    paying the delivery payment within 5 days of delivery. The rules grammar reads all of it (status COMPILED).
    Note: clause 4.2 yields both a MILESTONE (offset in its own trigger) and a PAYMENT_TERMS term; the schedule must
    use the milestone's own offset and never add payment terms on top (phase 2).
  - Tests: `tests/api/test_capex_documents.py` (16, all pass). Regression: `tests/api/test_documents.py
    tests/api/test_deals.py tests/compiler tests/contracts tests/deals tests/persistence` = 966 passed + the 2
    pre-existing failures above.
- 14 Oct 2026, phase 2 (payment schedule): `app/capex/schedule.py`.
  - `Timeline` (signing, delivery, acceptance, invoice, retention-release days; the owner's plan),
    `ScheduledPayment`, `EarlyPayOption`, `PaymentSchedule` (with `schedule_hash`), `ScheduleResult` (derivable, or
    reasons + the timeline fields the owner must give).
  - `derive_schedule(reading, timeline, anchor_iso=, today=)`: rules in the module docstring (D4, D5). Signing day =
    the owner's, else the contract's SIGNED_DATE, else today. Invoice day defaults to the delivery day (the earliest,
    so the conservative reading). A payment before today, a timeline out of order, a reading that is not COMPILED,
    a price that is not LUMP_SUM, an unclassifiable or two-event trigger, a "before" offset, or shares that do not
    reconcile -> not derivable with a sentence.
  - Early payment: attached only when the clause names exactly one event and exactly one non-retention payment waits
    for it; priced as discount / (payment - discount) x 365 / days earlier (exact `Ratio`). The demo contract: pay
    ¥352,800 by day 65 instead of ¥360,000 on day 105 = 18.62% a year.
  - Tests: `tests/capex/test_schedule.py` (24, all pass).
- 14 Oct 2026, phase 3 (the screen on the schedule):
  - `app/capex/models.py`: `CapexPayment`; `CapexRequest.payments` (must sum to `price_fen`; omitted from the
    serialised form when None, so the application key and every existing output are unchanged);
    `CapexResult.horizon_end_day` / `beyond_horizon_fen` (omitted when None).
  - `app/capex/appraisal.py`: `payment_month` (the engine's 30-day month from today), `npv_schedule_fen` (each
    payment discounted from its month; one payment in month 0 equals `npv_fen` exactly), `payback_month_schedule`
    (the first month from which the cumulative stays recovered; a payment after the life is never recovered).
  - `app/capex/evaluate.py`: with `payments`, each structure's daily cash test posts the real payment days
    (`_purchase_flows`); a financed structure still draws the whole price on the request day; the cash + line
    structure sizes its line draw on what is paid inside the projection (`_due_in_horizon`); a RESERVE_BREACH before
    the proceeds land carries a `cure_note` saying so; payments after `today + mandate.horizon_days` are reported in
    a Working, an assumption and `beyond_horizon_fen`, never dropped. Without `payments` every code path is the old
    one (the 51 existing capex tests and the golden pins pass unchanged).
  - `app/capex/schedule.py`: the implied annual rate now uses `app.funding.rates.early_pay_rate` (the sell side's).
  - `app/capex/buyside.py`: `CapexEstimate` (the owner's estimate; uplift start defaults to the month after
    acceptance, else delivery), `evaluate_contract(record, timeline, estimate, state, mandate)` ->
    `BuySideEvaluation` (schedule, the screen on it, and `EarlyPayDecision`): take the discount when
    d / (1 - d) > c (c = `break_even_cost_share` of the marginal committed source for the days earlier, the sell side's
    rule) **and** the screen on the early schedule selects a structure.
  - `app/api/capex.py`: `POST /capex/contracts/{document_id}/evaluate` (owner only; needs FEATURE_CAPEX and
    FEATURE_CAPEX_CONTRACTS; 404 unknown, 422 not a capex contract; read-only), with percentage displays for the
    exact ratios.
  - **Finding worth knowing**: on the demo contract signed on its own date (day 7), every financed structure breaks
    the reserve on day 7 (the 30% deposit falls before any loan lands: lease day 10, term loan day 14). The old
    lump-sum model hid this by paying the whole price on the landing day. Signed on day 20, the 36-month term loan is
    selected (¥18,144.62 a month) and the 2% early payment is taken (2.04% return vs 1.78% carrying cost).
  - Tests: `tests/capex/test_buyside.py` (19), `tests/api/test_capex_buyside_api.py` (7); all capex tests 117 pass.
- 14 Oct 2026, phase 4 (the owner's commitment):
  - `app/domain/models.py`: `CommitPurchase` operation (document id + hash, schedule hash, amount, the timeline,
    `take_early_pay`), added to the `Operation` union; `FlowKind.CAPEX`.
  - `app/mandate/tiers.py`: `CommitPurchase` is always Tier 2 (`_ALWAYS_TIER2`).
  - `app/capex/schedule.py`: `early_schedule(schedule)`, the schedule with the discount taken, renumbered and hashed
    on its own; `app/capex/buyside.py` uses it and returns it as `early_pay_schedule` (to commit it).
  - `app/operations/executor.py`: `_commit_purchase` (via `_handle`), reached only after the owner's approval.
    Refuses: unknown document, not a capex contract, not CONFIRMED, document hash not the stored one (TERMS_CHANGED),
    already committed (an EXECUTED COMMIT_PURCHASE for the document in the log, or a `CAPEX:<doc>:` flow on the
    books), the vendor id on the registry with another role, a schedule not derivable today (e.g. a payment day
    already past at approval time), a schedule hash or amount that is not what the owner was shown (TERMS_CHANGED).
    Effect: one `CashFlow` per payment (`FlowKind.CAPEX`, id `CAPEX:<doc>:<n>`, negative), the vendor registered as
    a known SUPPLIER under the contract's PARTY_SUPPLIER name. `_tier2_reason` names the purchase.
  - `app/api/capex.py`: `POST /capex/contracts/{document_id}/commit` (owner only, both flags): pre-checks (404,
    422 NOT_A_CAPEX_CONTRACT / NOT_CONFIRMED / NO_SCHEDULE with `needs` / NO_EARLY_PAYMENT, 409 SCHEDULE_CHANGED),
    then queues one `CommitPurchase` requested by the AGENT with idempotency key `capex-commit:<doc>:<hash16>`; the
    owner approves on `/approvals/{id}` like any Tier-2 operation.
  - `app/api/presentation.py`, `approval_review.py`: owner-facing words for COMMIT_PURCHASE (card headline "Commit to
    the ¥600,000 equipment purchase", what approving does, the button "Authorize the purchase").
  - **Security fix found on the way** (`app/egress/contracts.py`): the outbound guard protected a contract's
    PARTY_BUYER name and exempted PARTY_SUPPLIER, which is right for a buyer contract but backwards for a capex
    contract (there the SME is the buyer): the SME's own name would have been "protected" (blocking its own messages)
    and the vendor's name left unprotected. The guard now swaps the parties for CAPEX_CONTRACT rows. Test
    `tests/egress/test_capex_contract_values.py` (3; 2 of them fail on the old code, checked).
  - Tests: `tests/api/test_capex_commit.py` (10): queue then approve books 3 flows and registers the vendor; the
    early schedule; stale hash 409; unconfirmed 422; missing day 422; committed once (DUPLICATE, then REFUSED for
    another timeline); approval after a payment day passed books nothing; the projection carries the payments and
    the clock pays them; the approval card wording.
- 14 Oct 2026, phase 5 (financial health): `app/health/__init__.py`, route module `app/api/buyside.py` (mounted in
  `app/main.py`; `/health` is the liveness probe, so the read is `/finance/health`).
  - `financial_health(state, mandate, commitments=, inputs=)` -> `FinancialHealth`: (1) cash on the conservative
    projection of current books, the same projection and "first breach ahead" rule as Home, plus whether the router's
    committed plan cures a shortfall and at what cost; (2) the 90-day cash coverage ratio, (cash + money in) / money
    out over the next 90 days from the projection's own events, never called a current ratio; (3) current and quick
    ratios only when the owner gives all four entries (`HealthInputs`: inventory, other current assets, trade
    payables, other current liabilities), labelled OWNER_ESTIMATE, with the debt due within 365 days from the books'
    own schedules (`debt_due_within`) and committed capex payments shown beside, not as a liability; (4) covenant room
    (DSCR and leverage on the worst projected month against the strictest of the mandate and committed facilities'
    covenants) and per-facility borrowing capacity by exact integer bisection (`largest_principal`), each naming what
    binds (LIMIT, DSCR, LEVERAGE) and saying when the facility counts as zero until committed.
  - `app/capex/evaluate.py` now exports `is_term_facility` and `term_service` (the ADR-0008 service rule) for it.
  - Golden figures (checked by hand in the tests): first breach day 12 at ¥60,000; coverage 2.55× (¥1,660,000 in vs
    ¥650,000 out); DSCR room ¥27,000 a month; leverage room ¥1,245,000; debt due within a year ¥540,000; ETL capacity
    ¥600,000 (limit), GGL capacity set by DSCR.
  - Routes: `GET /finance/health`, `POST /finance/health` (body `{"inputs": {...}}`), owner only, FEATURE_CAPEX_CONTRACTS.
  - Tests: `tests/health/test_health.py` (16), `tests/api/test_finance_health_api.py` (6, including the reconciliation
    with `GET /home`'s cash figures).
- 14 Oct 2026, phase 6 (loan eligibility): `app/lending/__init__.py`, `fixtures/lending/catalogue.json`, routes in
  `app/api/buyside.py`.
  - Catalogue: 4 synthetic products, labelled "not a real lender's offer" (term loan 60m BANK-1; guaranteed loan 36m
    BANK-2 with an 80% buyer-concentration cap; lease 60m LESSOR-1; a secured 84m loan from a new lender LENDER-NB that
    needs collateral and a personal guarantee). Generic lender ids only (never a real bank's name).
  - `eligibility(state, mandate, inputs=EligibilityInputs(months_trading, amount_fen))`: per product, the lender's
    amount criteria pro forma with its own loan added (DSCR, leverage; ADR-0008 service), the largest eligible
    principal by exact bisection; the fixed criteria (90-day coverage, largest buyer's share of open receivables,
    months trading: UNKNOWN until the owner says, never assumed); the company's own limit beside it
    (`facility_capacity`); Tier-3 needs named. Status ELIGIBLE / ELIGIBLE_UP_TO / UNKNOWN / NOT_ELIGIBLE; ranked by
    status, then products needing no Tier-3 step first, then the all-in rate.
  - `POST /lending/products/{id}/add-to-menu` queues the **owner's own** `AddFacility` (Tier 2, INVARIANT 3) for a
    NOT_APPLIED facility `FAC-<product>` carrying the lender's DSCR/leverage criteria as covenants (INVARIANT 4: zero
    until committed); the executor registers a new lender. 409 if already on the menu, 422 for an amount outside the
    product, 404 unknown product.
  - `app/capex/buyside.py`: `CapexEstimate.candidates` now defaults to `menu_candidates(state)`: every owner-approved
    term facility on the menu at its own term (no hypothetical terms on the buy side). So the guaranteed loan
    (FAC-GGL, limit ¥500,000) is now screened and refused as over its limit, and a catalogue product the owner added
    is screened automatically. `tests/capex/test_buyside.py` updated for it.
  - Tests: `tests/lending/test_eligibility.py` (10, including the exact bisection boundary), `tests/api/test_lending_api.py` (6).
- 14 Oct 2026, phase 7 (long-term plans): `app/capex/plans.py`, route `POST /capex/plans` in `app/api/buyside.py`.
  - `PlanRequest(projects=[PlanProject...], horizon_months=60, hurdle_bp=1000)`; a project is a capex contract
    (`document_id` + `timeline`) or a `price_fen` paid at its start, with uplift, life, `start_offsets` (months,
    default 0/3/6/12), `options` ("CASH" and term facility ids; default cash + every usable, owner-approved term
    facility without a Tier-3 need) and `optional` (the plan may leave it out).
  - Monthly **estimate** (D9): baseline free cash = EBITDA − existing debt service (`existing_debt_service`, the capex
    screen's own `_Base` rule, now public in `evaluate.py`), from today's cash. Each project-option is precomputed once
    as monthly vectors (cash, uplift, new service, new principal outstanding) and an exact NPV; a permutation is their
    sum. A loan is requested its lead time before the first payment (never before today) so it lands when needed.
    Month 0 (a payment today) is folded into month 1 for the tests, never dropped.
  - Every month: cash >= reserve where the plan makes it worse; DSCR (with uplift) >= the strictest minimum (mandate,
    committed facilities, every facility the plan uses); leverage (without uplift) <= the strictest maximum; each
    facility's limit shared across projects. Exact integer comparisons in the search; ratios built only for the
    plans shown.
  - Result: the top 5 admissible plans by NPV (then higher lowest headroom), each with its 60 months; the best plan
    overall when it is not admissible and why (what the limits cost); the project/option pairs no admissible plan
    uses; and the best plan's contracts re-run through the daily capex screen (`daily_checks`). Capped at 20,000
    permutations (refused above, never sampled). 272 permutations run in about 0.1 s.
  - Findings on the golden books: the line (lease) + the robot (term loan) now is best; doing both now on the term
    loan + the lease fails DSCR in month 2 (1.24×, before any uplift); two projects on the term loan exceed its
    ¥600,000 limit.
  - Tests: `tests/capex/test_plans.py` (16), `tests/api/test_capex_plans_api.py` (4).
- 14 Oct 2026, phase 7 follow-up (found while building the plans page): the plan's baseline ignored purchases
  already committed (CAPEX flows are capital payments, not in EBITDA). The baseline now subtracts every committed
  CAPEX flow in its month. Test `test_a_purchase_already_committed_comes_off_the_baseline`.
- 14 Oct 2026, phase 8 (the buying side of Deals): `app/deals/purchases.py`, routes in `app/api/buyside.py` and
  `app/api/deals.py`.
  - One row per capex contract: stage REVIEW / READY / AWAITING_APPROVAL / COMMITTED / PAID / REJECTED, the next
    action (en and zh), the vendor (and whether it is registered yet), and, once committed, every payment with paid or
    not (paid = the clock has posted its flow). The committed schedule is derived again from the record and the
    committed timeline by the same code that booked it (no second copy of the payments).
  - `GET /purchases`, `GET /purchases/{id}` (owner, flag). `GET /deals` carries `purchases` only when the flag is on
    **and** there is at least one capex contract, so every existing read and recorded mock is unchanged.
  - Tests: `tests/api/test_purchases.py` (7): REVIEW -> READY -> AWAITING_APPROVAL -> COMMITTED -> part paid -> PAID
    (the clock moves at most 366 days a step), rejected, 404s, zh, and the omitted key.
- 14 Oct 2026, phase 9 (web), all under `apps/web`:
  - `lib/types.ts`: the buy-side view types (end of file). `lib/live/index.ts`, `lib/api.ts`: `getPurchases`,
    `getPurchase`, `getCapexContractFixtures`, `evaluateContract`, `commitContract`, `getFinanceHealth`,
    `getEligibility`, `addProductToMenu`, `runCapexPlans`. `lib/mock/buyside.ts` (+ exports and reset in
    `lib/mock/handlers.ts`): serves `mocks/buyside/*.json`, a small session stage (ready -> awaiting).
  - `scripts/record-mocks.mjs --buyside`: records ONLY `mocks/buyside/` (15 files) against an API started with
    `FEATURE_CAPEX_CONTRACTS=1`; recorded twice, byte-identical; no other mock changed.
  - Pages: `/buy` (purchases, read the demo contract when empty), `/buy/contract?id=` (timeline, schedule, early
    payment, financing table with the cure notes, commit), `/finance` (health, the owner's ratio entries, capacity,
    eligibility with add-to-menu), `/plans` (contracts + extra purchases, ranked plans, unconstrained best, daily
    checks). Each shows "switched off" on FEATURE_DISABLED. The Deals page header shows a "Buying" link only when
    `GET /purchases` answers (a live build with the flag off looks exactly as before). No Business nav tab was added
    (the five tabs are pinned by existing specs).
  - Owner entries in yuan are sent as fen by `* 100` on an integer the owner typed (parsing an entry; no money is
    formatted or computed by the UI, INVARIANT 13).
  - `lib/dictionary.ts`: 121 keys in en and zh.
  - Checks: `pnpm exec tsc --noEmit` clean; eslint clean on the new files; `pnpm test:unit` 145 pass; e2e mock
    `e2e/buyside.spec.ts` (6) + `e2e/deals.spec.ts` + `e2e/deals-queue.spec.ts` = 33 pass.
- 14 Oct 2026, hardening after phase 9:
  - `app/operations/executor.py` `_commit_purchase`: refuses FEATURE_DISABLED when FEATURE_CAPEX_CONTRACTS is off,
    whichever route queued the operation (POST /operations is open to the agent and checks no feature flag).
  - `tests/api/test_capex_attacks.py` (12): the agent can queue but never approve; an owner claim from the agent is
    still Tier 2; a forged amount, schedule hash, document hash, timeline or early-pay flag is refused at approval
    (TERMS_CHANGED, or PRECONDITION_FAILED for a timeline out of order) and books nothing; a buyer contract cannot be
    committed; a switched-off feature books nothing; a counterparty key reaches no buy-side route (401); the agent's
    AddFacility for a catalogue product is Tier 3.
  - `tests/api/test_capex_reads_after_commit.py` (5): with a committed purchase on the books, 22 read routes answer
    200 in en and zh, before and after the clock pays the deposit; the approval has a decision record; the trajectory
    shows the payments.
  - `apps/web/app/buy/page.tsx`: an upload card for the owner's own vendor contract (vendor id + file; the Documents
    page form is unchanged); `DocumentKind` in `lib/types.ts` gains CAPEX_CONTRACT with its `dockind.*` labels.
  - Mocks re-recorded from an API on the final code (the plans assumption sentence changed); stable across runs.
  - **Pre-existing, not caused by this work**: `python -m app.security.attacks --report` crashes before any attack
    runs (`CompiledOffer` cannot parse the `reason_when` field that `app/api/offers.py` already adds at the branch's
    starting commit). Fixing the harness is outside this work; the buy side's attacks are covered by the test above.
- Commit state: the web half is `9789a6f3 capex` (committed by the owner); the API, fixtures, ADR, this file, AGENTS.md
  and the tier test followed in the next commit on `feat/capex-buy-side`, at the owner's request (14 Oct 2026).

- 14 Oct 2026, after review by the owner (two defects in phase 9):
  - **Buying switched the app to the Demo shell.** `lib/mode.ts` decides the shell from the path: anything not in
    `BUSINESS_ROUTES` is an engine view and gets the Demo shell. `/buy`, `/buy/contract`, `/finance` and `/plans` were
    never registered. They are now owner detail routes (`OWNER_DETAIL_ROUTES`: `/buy` opens from `/deals`; the other
    three from `/buy`), mirrored in `lib/pre-hydration.ts`; the shell draws "Back to Deals" / "Back to Buying"
    (`BACK_LABEL` in `components/app-shell.tsx`, new key `nav.backToBuying`), so the pages' own back links were removed.
  - **The Deals "Buying" button sat in the page header with no meaning.** Replaced by the product's existing pattern for
    a door to another page (Cash's "quiet doors"): after the page's own work, a link with a chevron and one sentence of
    what is behind it, here built from the server's purchases ("One vendor contract. Next: <the server's next
    action>"). The Buying page's header buttons to Financial health and Long-term plans became the same doors.
  - Specs: `e2e/buyside.spec.ts` (the door and its sentence, not in the header; every buying page in the Business
    shell with its back link), `e2e/responsive.spec.ts` (the three pages added to its Business routes). Mock e2e for
    buyside, deals, deals-queue, documents, responsive: 89 passed, 15 skipped (live-only); `pnpm test:unit` 145.
- 14 Oct 2026, the owner: the door was too small to notice; Deals should show both buying and selling, selling the
  bulk. `components/deals/buying-card.tsx` (`BuyingCard`) replaces the door: a card in the inbox's own style under the
  selling queue (left column), heading "Buying" with the open count and "All purchases", one `Row` per open purchase
  (vendor initials, title, the server's next action, price, stage; each links to where that step is done: the
  reading to review, the approval, or the contract screen), at most three with "and N more", then links to Financial
  health and Long-term plans; with nothing bought, one line and "Read a vendor contract". It shows on the Deals
  overview and steps aside while a selling negotiation is open: the pane is sticky beside the queue at `xl`, and a
  taller queue column scrolled it out of line (caught by `responsive.spec.ts` "side by side", 23.75 px off).
  Specs: the card's test in `e2e/buyside.spec.ts` (under the queue and before the inbox in reading order, the row,
  the links, hidden while a negotiation is open). Mock e2e for buyside, deals, deals-queue, responsive, a11y: all
  pass (one phone deals-queue test failed once and passed on two re-runs: a flake).

## 7. How to run and check

- Switch the feature on locally: `FEATURE_CAPEX_CONTRACTS=1` in the root `.env` (read by `app/config.py`).
- Focused tests (from `services/api`): `SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/capex tests/contracts tests/operations`.
- Full gate: docs/HANDOVER.md section 6, item 2 (chunks A and B, scenarios, demo run, attacks, evaluate, certification).
- Never edit a web mock by hand: start the API and run `pnpm mocks:record` (apps/web/README.md).

## 8. Open questions for the owner

- Lender catalogue: the synthetic fixture (D7) is the starting point; real products would need a source and a refresh
  rule.
- Long-term horizon: 60 months by default (D9); the request can ask for 36.
- Cancelling a committed purchase: not in scope yet (section 9).

## 9. Known limits and follow-ups

- The server's sentences on the new reads (evaluation summary, health, eligibility, plans) are English only; the page
  labels are in both languages and the purchases rows' next actions are in both. Chinese server sentences are a
  follow-up (the existing `engine_zh` / presentation pattern).
- Mock mode: approving the recorded purchase commitment on the approvals page does not move the mock purchase to
  COMMITTED (the approvals mock is a separate recording); `markPurchaseApproved` exists for wiring it.
- The plans page plans each confirmed contract on the demo timeline (signing 20, delivery 60, acceptance 80) moved by
  whole months; a per-contract timeline on that page is a follow-up.
- Eligibility, plans and the capex screen each read covenant room on their own; borrowing on one facility leaves less
  for the others (said in each one's assumptions).

- Instalments stated as fixed amounts (not shares of the price) are not read by the grammar; such a contract is "not
  derivable" until the grammar learns them.
- A committed purchase cannot yet be cancelled; the flows stay until paid. A `CANCEL_PURCHASE` owner action (log kind,
  like REVOKE_COMMITMENT) is the natural next step.

## 10. Where the gate stands (14 Oct 2026, final)

Backend, folder by folder (logs were kept per folder; the old two-chunk run gave no progress and was replaced):

| Folder | Result |
|---|---|
| alerts 76, borrower_file 29, capex 111, clock 9, commitments 90, compiler 688, contracts 9, counterparties 76, covenants 38, egress 975, evals 24, financial 195, funding 1129 (+22 skipped), ingest 33, health 16, lending 10, mandate 74, nl 1088, operations 400 (+1), persistence 158, verifier 262, whatif 51, concurrency 20 (+10), certification 41, api 1390 (+2), root 12 | all pass |
| decisions, pilot, reliability, strategy | 788 pass, 6 skipped |
| books | 82 pass, **1 pre-existing failure**: `test_modules_on_books.py::test_no_commitments_trajectory_and_router_plan_are_unchanged` (the router-plan digest pin; fails identically with every change of this work stashed) |
| deals | 42 pass, **2 pre-existing failures** (`test_lang.py`, see section 6) |
| security | 117 pass, **131 pre-existing failures/errors**: the attack harness cannot parse `reason_when` (fails identically on the starting code; `test_scoreboard` checked with the work stashed). The buy side's attacks are in `tests/api/test_capex_attacks.py` (12 pass) |

`tests/mandate/test_tiers.py` needed the new operation in its coverage table (two cases: Tier 2 for the agent and for the
owner); that is the only existing test edited.

Other checks: `scripts/run_scenarios.py --inproc` 49/49; `scripts/demo_run.py` exit 0 (both with the flag off; the
evidence files the scenarios rewrite were restored with `git checkout -- services/api/evals`); web `tsc` clean, eslint
clean on the new files, `pnpm test:unit` 145 pass, `E2E_TARGET=mock pnpm exec playwright test` **425 passed, 55
skipped, 0 failed**. Not run: the live e2e project (needs the API with the flag on), `scripts/evaluate.py`, the
language-boundary certification.

Commit state: everything is committed on `feat/capex-buy-side` (the web half as `9789a6f3 capex`, the rest in the commit
after it). Nothing is pushed or merged.

Decisions left for the owner: switching `FEATURE_CAPEX_CONTRACTS` on by default (`app/config.py`), merging, and
accepting ADR-0013 (status "proposed").
