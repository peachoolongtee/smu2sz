# Ticket #90 (map #88): capability map and data availability matrix

Researcher's resolution, 10 October 2026. Repository `/Users/ianpong/Hackathons/smu2sz`, branch `dev` at `0cd60cb`.
Read-only: no repository file changed; `git checkout -- services/api/evals` was run after the scripts and `git status
--short` is empty. Paths below are relative to `services/api/app/` unless they start with `docs/`, `fixtures/`,
`services/` or `apps/`. The buyers' hidden state in `fixtures/counterparties/buyers.yaml` was not used as a data source
(its header, lines 3-5, was read to confirm the rule).

## 0. How the facts were established (commands)

Two read-only scripts, kept in the scratchpad (`map-econ/r1-scripts/`), not in the repository:

```bash
cd /Users/ianpong/Hackathons/smu2sz/services/api
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache \
  uv run --project "$PWD" --directory "$PWD" python <scratchpad>/map-econ/r1-scripts/count_fixtures.py
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache \
  uv run --project "$PWD" --directory "$PWD" python <scratchpad>/map-econ/r1-scripts/stress_probe.py
git -C /Users/ianpong/Hackathons/smu2sz checkout -- services/api/evals && git -C /Users/ianpong/Hackathons/smu2sz status --short   # empty
```

`count_fixtures.py` loads each scenario with `app.domain.fixtures.load_scenario`, counts receivables, past-due invoices,
recurring invoices, expected orders, flows, computes open AR per buyer and the 365-day recurring run rate with the
engine's own `financial.concessions.recurring_issue_days`, then advances an `InMemoryLedgerStore` 120 days with
`app.clock.advance` and counts what the books and the log hold. `stress_probe.py` builds a labelled `ScenarioState` with
one buyer's open and recurring invoices moved 30 days later (the mechanism of `strategy/impact.py::_received_on`, lines
81-89, applied past the due day) and runs the unmodified `strategy.impact.marginal_impact`. Other facts come from `grep`
and `git show` (cited inline).

### What the fixtures actually cover

| Fixture | Invoices (receivables) | Receipts | Recurring invoices | Expected orders | History horizon | Forward horizons |
| --- | --- | --- | --- | --- | --- | --- |
| `fixtures/scenarios/golden_sme.json` (day 0 = 2026-10-01) | 1 (RCV-A, Foshan, ¥420,000, issued day −13, due day 32), OPEN | **0** (`golden_sme.events.json` note: "Receipts are never in this file: they come from the bank feed") | 1 (Foshan ¥420,000 every 30 d from day 2, 45-d terms): 13 issues in [0, 365) = ¥5,460,000 | 1 (Foshan "next quarter" ¥400,000, days 92-182, not firm) | 13 days back (one invoice) | trajectory `horizon_days` 120; concession window 365 |
| `fixtures/scenarios/short_facilities.json` | same as golden (only facilities differ) | 0 | same | same | 13 days | same |
| `fixtures/scenarios/public_sme.json` (day 0 = 2026-01-01; a real filing, `public_sme.SOURCES.md`) | 8, all OPEN, issued days −96..−15; **3 past due on day 0** (RCV-B1 35 d, RCV-F1 20 d, RCV-D1 10 d; ¥13,049,267.35 = 35.2% of ¥37,060,947.54) | **0** | 4 (Buyers A, B, C, "Other buyers (aggregate)"), 12 issues each in [0, 365), ¥106,208,491.44 incl. VAT; Buyers D and E have none | 1 (Buyer A ¥6,459,789.13, days 92-182, not firm) | 96 days back (open invoices only; nothing settled) | 120 / 365 |
| After `clock.advance` to day 120, no receipt posted | golden 5, public 24 (all OPEN) | **0**; the log holds one `ADVANCE_CLOCK` entry | issued as receivables by the clock (`clock/__init__.py:89-102`) | unchanged | grows only with simulated time | |
| 49 e2e scenarios (`services/api/evals/e2e/scenarios.yaml`) | all start from `POST /demo/reset` on golden (file header, line 3) | 2 setup receipts in one scenario (S49, lines 534-538: ¥50,000 each on RCV-A, the second refused for a reused bank reference) | | | | |
| Pilot rehearsal `docs/pilot/dry-a` (public SME, 8 weeks) | | **0** (`dry-a/summary.md`: "Operations other than the clock's: before 0, after 0") | | | | |
| `docs/pilot/receipts.example.yaml` | | 4 synthetic receipts over 8 weeks, labelled invented | | | | |

Golden: 12 × monthly EBITDA (¥90,000) = ¥1,080,000 = 19.78% of the ¥5,460,000 run rate. Public: ¥9,771,555.24 = 9.20%
of its run rate. Open AR concentration: golden Foshan 100.00%; public "Other buyers (aggregate)" 48.63%, B 14.57%,
A 14.56%, C 9.13%, D 6.88%, E 6.22%. Run-rate shares (public): Other 51.72%, A 24.33%, B 15.88%, C 8.07%.

---

## A. Capability map

The gap column uses the ticket's three kinds: **P** presentation (the figure exists, nobody shows it), **D** a
derivation over existing state (no new input), **N** new data (an input the books do not hold).

### A. Customer economics: no customer figure exists; the run rate and a floor do

What serves it today:

- `Counterparty` (`domain/models.py:454-458`): `id`, `name`, `role`, `known`; nothing else. Stored in `counterparties`
  with a `payload_json` column (`persistence/tables.py:48-57`), but `Contract` is `extra="forbid"`
  (`domain/models.py:32-33`), so a new field is a model change.
- `RecurringInvoice` (`domain/models.py:392-399`) and the engine's own window arithmetic: the concession valuation counts
  a recurring invoice's issues in `[today, today + forward_concession_horizon_days)` (`financial/concessions.py:95-108`;
  the window is the mandate's `forward_concession_horizon_days`, 365 by default, `domain/models.py:321`). The same
  function gives a **forward 12-month invoiced run rate** per buyer: golden Foshan ¥5,460,000 (13 invoices).
- `Receivable` rows are kept after settlement (`status` SETTLED, `settled_fen`; `domain/models.py:360-389`), and the
  clock issues each recurring invoice as a receivable and logs the ids in its `ADVANCE_CLOCK` payload
  (`clock/__init__.py:89-102`, payload at about line 307). Invoice history therefore accrues in the books from the day
  they start; nothing older is loaded.
- `monthly_ebitda_fen` (`domain/models.py:492`): one company-level figure. With fixed costs at or above zero, the sum of
  customer contributions is at least 12 × monthly EBITDA. That gives a **floor** on any owner-entered margin (section D,
  surprise 2).
- The concession cost the mission quotes exists and is exact: EX01's forward concessions ¥28,326.92
  (`fixtures/golden/golden_values.json:31` `forward_ledger_total` 2832692), rebate ¥4,000 plus the extension's funding
  cost on 13 invoices (`docs/SYSTEM_WALKTHROUGH.md:398-402`). It excludes the 1.2% immediate discount, which is valued 0
  forward and capped separately (`financial/concessions.py:270-275`).
- `ForwardConcession` per counterparty (`domain/models.py:415-422`) and `Mandate.per_buyer_caps_fen`
  (`domain/models.py:322`): the per-buyer policy hook the mission's section 22 wants later.
- `VOLUME_COMMITMENT` is a typed obligation already compiled from buyer text and valued at 0 ("no forward cost to the
  supplier", `financial/concessions.py:276-277`): where a buyer's promised volume would enter "contribution if
  accepted", never the cap (INVARIANT 5).

Tests: `tests/financial/test_dated_valuation.py` pins the 13-invoice window (`docs/SYSTEM_WALKTHROUGH.md:1173`). No
test touches any customer-level figure; `grep -ri "concentration|contribution margin|gross margin|annual sales"` over
`services/api/app` and `apps/web` finds nothing.

Missing, and the kind of gap:

| Piece | Gap |
| --- | --- |
| Annual customer revenue, forward (run rate from `RecurringInvoice`, PROJECTED) | D |
| Annual customer revenue, trailing 12 months (INVOICE_HISTORY) | N (the books start at day 0; fixtures hold 13 or 96 days of open invoices) |
| Ex-VAT revenue: invoice faces carry 13% VAT (`public_sme.SOURCES.md:98-99`; Foshan contract cl. 3.2 on `feat/upgrading`) | D given a VAT rate, which is N (one owner or accounting setting) |
| Contribution or gross margin per customer | N (owner input; nowhere in the books) |
| Annual contribution, concession as % of contribution | D once margin exists |
| Strategic classification | N (owner input) |
| A deal-card line | P |

### B. Scenario comparator: the delta primitive exists; no comparator, no buyer scenarios

What serves it today:

- `ScenarioState` (`strategy/types.py:26-34`): a labelled copy, `hypothetical: Literal[True]`, an assumption sentence.
- `read_books` / `marginal_impact` (`strategy/impact.py:159-209`): need, posted plan cost, first breach, breach days,
  lowest cash headroom over the floor, forward budget used, alerts, needs-owner and executable-now flags, before and
  after. Tests: `tests/strategy/test_impact.py` (21 tests; e.g. :122 every recorded effect to the fen, :144 and :155 no
  change against itself, :163 labelled and leaves the books alone).
- `scenario_received` (`strategy/impact.py:91-117`) and `scenario_inflow` (`:120-143`).
- The what-if sandbox (`whatif/simulate.py:272`, `POST /whatif`, `api/whatif.py:65`): the real verifier on a synthetic
  typed package, labelled hypothetical, cached.
- The router's comparison contract on `POST /router/plan` (`api/decide.py:536-542`; `funding/router.py:331` `compare`):
  `group`, `rank`, `router_order`.
- The verdict's counters (`domain/models.py:713-739`) and the decision record (ADR-0011; `decisions/facts.py`).

Missing:

| Piece | Gap |
| --- | --- |
| A comparator over three or more named candidates (accept, counter A, counter B) on one table | D + P (`marginal_impact` per candidate; the verdict already evaluates the original and its counters) |
| Late-payment scenario past the due day | D: `scenario_received` refuses it by design (`strategy/impact.py:108-110`, pinned at `tests/strategy/test_impact.py:212`); the probe in section 0 runs it through the unmodified `marginal_impact` |
| Customer-loss scenario (receipts lost) | D for the receipts; N for the costs that would stop with them (flows carry no counterparty: every fixture flow has `counterparty_id: null`) |
| Annual contribution foregone | N (margin) |
| A horizon long enough for annual figures | the cash view is the mandate's 120 days (`domain/models.py:330`; both fixture mandates); the concession view is 365. A comparator must state both horizons |

Caveats found: `read_books` projects with no funding actions (`strategy/impact.py:168`), so its "lowest headroom" is
cash before funding, not after the plan; `ExpectedOrder` never reaches the cash projection (section C, correction 3); a
NO_DEAL in the repository means the current terms continue (e2e S02, `scenarios.yaml:39-48`), not that the buyer stops
buying.

### C. Safe commercial envelope: built, flagged off, richer than the map credits

What serves it today: `strategy/envelope.py` (1,287 lines), `GET /buyers/{buyer_id}/envelope?zone=0|1&lang=`
(`api/strategy_envelope.py:47`), flag `FEATURE_ENVELOPE` default off (`config.py:55`), the web card
`apps/web/components/deals/before-they-ask.tsx`. Tests: `tests/strategy/test_envelope.py` (51 tests; :143 terms alone
stop at the budget, :151 terms with the budget ignored stop at liquidity, :161 terms with the compensating price, :206
and :218 the zone, :238 the ten interaction packages to the fen, :267 every default-grid package approved, :275 the
verifier's own counters among them), `test_oracle_fixture.py`, `test_search_economy.py`, the backtest
(`docs/STRATEGY_MVP_REPORT.md:66-76`: 89 of 90 verifier counters inside the envelope, 0 re-check disagreements).

Already there, against the mission's sections 10 to 13:

- Largest value per lever with the boundary's neighbours checked and a full scan on disagreement (`envelope.py:574-641`,
  `last_true`/`first_true` at :196-258).
- Packages re-evaluated whole (`_grid`, `envelope.py:676-707`), so individually safe maxima are never combined unchecked
  (section 11).
- The minimum compensating price per term: `ZoneRow.min_price_bp` with the Option-B rule price beside it
  (`envelope.py:491-497`, `_zone` :648-656), and the lever "Terms (days), with the price that compensates it" with its
  smallest passing price (`envelope.py:590-603`). Golden: 55 days, smallest passing 0.25%, rule 0.30%; 60 days fails
  with no price in range (`docs/STRATEGY_MVP_REPORT.md:40-46`).
- **Section 13's FINANCIALLY FEASIBLE is already computed**: `Probe.liquidity_only` ("passes if the forward budget is
  ignored", `envelope.py:113`) and the lever "Terms (days), budget ignored" (`envelope.py:587-589`). Golden: terms alone
  45 days (50 fails the ¥5,000 budget at ¥8,108.97); budget ignored 55 days (60 breaches day 47 with no fix).
- `tier`, `passes`, `cure_needs_owner`, `cure_cannot_run_today`, `binding` per probe (`envelope.py:106-126`);
  `next_terms_passes_with_early_pay` (`:522-523`); this buyer's past-due invoices with days late (`:526`).

Missing:

| Piece | Gap |
| --- | --- |
| The answer keyed to the buyer's actual ask ("you asked 60: no price in range makes it pass; 55 at +0.30%") on the deal card | P (the zone row exists; `zone=1` is opt-in since `0cd60cb`) |
| Off-grid terms such as "52 days" | the grid is 5 days (`whatif/params.py:11`; `CandidatePackage` validator, `strategy/types.py:47-52`); finer steps multiply verifier runs |
| An upfront deposit on future invoices ("60 days with 20% upfront") | N + engine: no `ObligationType` for it (`domain/models.py:79-86`); `early_pay_face_fen` is a discounted early settlement of the open invoice (`strategy/types.py:44`), a cost, not a deposit |
| Mandate result split into "inside the signed caps" versus "outside them" | P over `liquidity_only`; see correction 12 on what "owner approval" can and cannot lift |

### D. Capacity and opportunity cost: every number is in the state; no statement exists, by decision

What serves it today:

- Facility room today: `menu_row` sets `available_fen = limit_fen − drawn_fen` for COMMITTED owner-approved facilities
  (`funding/menu.py:47-48`), served in the menu of `POST /router/plan`.
- Lots with remaining principal (`domain/models.py:461-474`, ADR-0010).
- Per-facility balances day by day are computed inside the engine (`financial/trajectory.py:1006-1040`), but only their
  sum with existing debt leaves it (`DayPoint.debt_outstanding_fen`, `trajectory.py:1055`; `domain/models.py:560-566`).
  Day events carry `kind` (DRAW, ADVANCE, REPAYMENT, INTEREST, FEE; `domain/models.py:537-557`) and a `ref`, so a
  per-facility path can probably be rebuilt outside the engine (to verify: that every principal posting carries the
  facility id as `ref`).
- Forward-concession budget: cap less the projection's peak (`alerts/engine.py:631-672`; `MarginalImpact
  .budget_used_delta_fen`, `strategy/impact.py:178`); per-buyer caps (`domain/models.py:322`).
- Covenant headroom: `covenant_limits` and the monthly DSCR and leverage headroom (`alerts/engine.py:373-436`), emitted
  only when below 0.10×.
- Cash headroom over the floor (`strategy/impact.py:177`), before funding.
- The marginal rate `FundingPlan.marginal_cost_annual` (`domain/models.py:677`) and the cash price curve
  (`strategy/price_curve.py`, `GET /cash/price-curve`, flag off).
- Map #47 deferred a `Capacity` type on purpose (`docs/STRATEGY_MVP_REPORT.md:28`, "map decision 2").

Missing: facility headroom before and after a decision through a date, and the day it recovers (section 38); invoice-
financing capacity over time (advance rate × eligible receivables, which depends on which invoices are open and not
yet due). Gap: **D + P**, no new data. The engine module stays untouched if the per-facility path is rebuilt from the
events of a projection run with the plan's actions (the stability gate, `docs/CONTINUOUS_OPTIMIZATION.md` section 0).

### E. Late payment and concentration: detection and lateness exist; history does not

What serves it today:

- Past-due detection: `RECEIVABLE_PAST_DUE` (`alerts/engine.py:560-588`, formula `today − due_day`) and the missed
  promised early payment (`:589-621`). Test `tests/alerts/test_alerts.py:128`.
- Days late of **open** invoices: Home (`api/home.py:951-961`, `days_late`), the envelope (`envelope.py:526`), the worth
  ranking (`strategy/collections.py:395`, `:544`), the chase handoff (`api/collections.py:95-150`; tests
  `tests/api/test_collections.py:33`, `:61`).
- Receipts: `ReceivePayment` with `bank_reference` and `reported_day` (`domain/models.py:839-853`); `reconcile()`
  replays them into `ReceiptMatch` rows with the receipt `day`, receivable and counterparty (`alerts/models.py:99-117`;
  `alerts/reconcile.py:260-305`). No due day and no lateness on the row.
- The conservative trajectory already treats an overdue invoice as never paid: "overdue before today (no dated receipt
  to rely on)" (`financial/trajectory.py:916-917`).
- The Demo's late-payment loop (`docs/DEMO_FLOW.md:3-5`).

Missing:

| Piece | Gap |
| --- | --- |
| AR concentration (share of open AR, of the next 30 days' receipts) | D |
| Revenue concentration (share of run rate) | D (PROJECTED) |
| Contribution concentration | N (margin) |
| Late-payment stress (contractual vs +N days) | D (probe below); the remediation report calls it "engine work" (`docs/UX_REMEDIATION_REPORT.md:109`), but the probe runs it through the strategy layer with no engine change |
| Days late per paid invoice, mean, median, P75/P90, on-time share, trend | N (payment history: zero receipts in every fixture) |

Probe (labelled hypothetical, the copy's terms moved +30 days for the buyer's open-not-overdue invoices and its
recurring invoice):

| Books | Need before → after | Plan cost before → after | Breach days added | Plan executable today |
| --- | --- | --- | --- | --- |
| golden, Foshan +30 d | ¥405,000 → ¥550,000 | ¥3,113.93 → ¥6,488.98 | 45 | yes → **no** |
| public, Other buyers +30 d | ¥4,282,116.74 → ¥4,937,813.06 | ¥8,094.96 → ¥15,422.21 | 15 | yes → yes |
| public, Buyer A +30 d | unchanged | ¥8,094.96 → ¥23,932.93 | 2 | yes → yes |

Caveat to carry into the spec: moving the copy's terms keeps a late invoice financeable until its new day
(`strategy/impact.py:81-89` docstring says so for the earlier-day case), which flatters the stressed plan; a financed
invoice is refused (`:106-107`).

---

## B. Data availability matrix

Provenance labels follow the mission's section 6. "Contract ingestion" is Chromo369369's work on `origin/feat/upgrading`
(21 commits ahead of `dev`, merge base `95c83d8`, 226 files and 30,547 insertions against `dev`; inspected with `git
log`/`git show`/`git diff --stat`, not merged). Its `ContractRecord` is owner-confirmed, logged as `CONFIRM_DOCUMENT` in
the chain, and "never writes the books"; `ContractTerm` fields include PRICE (with unit), INVOICING cadence, START/END
dates, DURATION, PAYMENT_TERMS (with basis: invoice, delivery, acceptance, month end), EARLY_PAYMENT, LATE_INTEREST,
MILESTONE, RETENTION (`domain/models.py` on that branch).

| Input | Status | Store or fixture now (or would) | Horizon the fixtures cover | Provenance | Notes |
| --- | --- | --- | --- | --- | --- |
| Annual revenue per customer, forward | **DERIVABLE NOW** | `FinancialState.recurring_invoices` × issues in 365 d (`financial/concessions.py:100`) | golden 1 buyer (¥5.46m incl. VAT); public 4 of 6 buyers (D, E have none) | PROJECTED | Includes VAT; omits one-off invoices; a buyer without a recurring invoice reads ¥0. Contract ingestion gives price × cadence × term as a second, owner-confirmed source (Foshan: ¥420,000 per batch every 30 days for 12 months, cl. 2.1, 3.1, 4.1) |
| Annual revenue per customer, trailing 12 months | **NEEDS ACCOUNTING IMPORT** | would be invoice history; today `receivables` from day 0 | golden 13 days, public 96 days, open invoices only | INVOICE_HISTORY / ACCOUNTING_HISTORY | Public SME's filing gives 2025 sales ex VAT for Buyers A, B, C (`public_sme.SOURCES.md:68-75`) but they live in the markdown, not the books |
| VAT rate (to net revenue) | **NEEDS OWNER INPUT** (one setting) | nowhere in the books | n/a | OWNER_ENTERED | 13% in both fixtures' sources; golden synthetic, Foshan contract says the price includes VAT (cl. 3.2) |
| Gross or contribution margin | **NEEDS OWNER INPUT** (prototype) / **NEEDS ACCOUNTING IMPORT** (real) | nowhere | none | OWNER_ENTERED / ACCOUNTING_HISTORY | Floor from the books: Σ contribution ≥ 12 × `monthly_ebitda_fen`. Public filing: company gross margin 23.76% (revenue ¥105,009,214.00, cost of sales ¥80,055,781.69, `SOURCES.md:19, 112`), not per customer. Contract ingestion carries no cost: not a source |
| Annual contribution | **DERIVABLE** once margin is entered | derived | as revenue | DERIVED (ESTIMATED when margin is owner-entered) | |
| Current AR per customer | **AVAILABLE NOW** | `receivables` (`outstanding_fen`), `reconcile().outstanding` | golden ¥420,000; public ¥37.06m | DERIVED from INVOICE_HISTORY | |
| AR share | **DERIVABLE NOW** | sum by `counterparty_id` | golden 100%; public 48.63% / 14.57% / 14.56% / 9.13% / 6.88% / 6.22% | DERIVED | Public's largest row is an aggregate ("Other buyers"): concentration of an aggregate is not a customer's |
| Revenue share | **DERIVABLE NOW** (forward) | run rate by buyer | golden 100%; public 51.72 / 24.33 / 15.88 / 8.07% | PROJECTED | Public fixture omits the 4th and 5th customers' ¥11,019,398.60 (10.5% of the filing's revenue): see surprise 2 |
| Contribution share | **NEEDS OWNER INPUT** (margins for every buyer) | | | DERIVED from OWNER_ENTERED | |
| Share of the next 30 days' receipts | **DERIVABLE NOW** | trajectory RECEIPT events by receivable | 120-d projection | PROJECTED | |
| Payment behaviour statistics (days late mean / median / P75 / P90, on-time %, trend) | **NEEDS PAYMENT HISTORY** | would be `RECEIVE_PAYMENT` log entries joined to the receivable's due day | **zero receipts in every fixture** | INVOICE_HISTORY + bank feed (DERIVED) | Which due day: accepted terms are written onto invoices (ADR-0009), `base_terms_days` keeps the original (`domain/models.py:372-373`); lateness must be measured against the terms in force when paid. Pilot procedure removes paid invoices from the next `state.json` (`docs/pilot/RUNBOOK.md:236-237`), so a pilot never accrues it in the books. Day-0 snapshot only: public 3 overdue (35, 20, 10 days). Contract ingestion's LATE_INTEREST is a term, not behaviour |
| Strategic classification | **NEEDS OWNER INPUT** | nowhere; `Counterparty` cannot carry it without a model change | none | OWNER_ENTERED | Policy link exists: `per_buyer_caps_fen` (`domain/models.py:322`), but it only tightens (the aggregate cap still applies) |
| Commercial history (offers, verdicts, counters sent, commitments, concessions per buyer) | **DERIVABLE NOW**, short | `offers`, `verdicts`, `commitments` tables (all keyed by `counterparty_id`, `persistence/tables.py:59-165`), `decision_facts` (ADR-0011) | from the books' day 0; golden demo has one offer per run | DERIVED | `SentFact.outcome` and `buyer_profile` are produced by the negotiation kernel over the hidden profiles and marked `simulated: Literal[True]` (`decisions/facts.py:72-74`): never a source for acceptance or churn statistics |
| Facility headroom today | **AVAILABLE NOW** | `menu_row.available_fen` (`funding/menu.py:47-48`) | | DERIVED | Uncommitted facilities count as zero (INVARIANT 4) |
| Facility headroom through a date, after a decision, recovery day | **DERIVABLE NOW** | projection with the plan's actions; per-facility path rebuilt from day events (to verify) | 120 d | PROJECTED | Engine computes it internally (`trajectory.py:1006-1040`) and exposes only the total |
| Concession headroom | **AVAILABLE NOW** | cap − booked − projected (`alerts/engine.py:631-672`; `MarginalImpact.budget_used_delta_fen`) | 365-d window | DERIVED | |
| Covenant headroom (DSCR, leverage) | **DERIVABLE NOW** | `covenant_limits` + month points (`alerts/engine.py:373-436`) | 4 months (120 d) | PROJECTED | Shown only when below 0.10× |
| Expected demand | **AVAILABLE NOW as a rebate base only** | `expected_orders` (`domain/models.py:443-451`) | one per fixture, not firm | OWNER_ENTERED (fixture) | Never in the cash projection, no cost or timing attached; see correction 3 |
| Invoice history | **AVAILABLE NOW from day 0 only** | `receivables` (SETTLED rows kept) + `ADVANCE_CLOCK` issued ids | 13 / 96 days | INVOICE_HISTORY | Older invoices need an import |
| Receipt history | **AVAILABLE NOW from day 0 only, empty in fixtures** | `RECEIVE_PAYMENT` entries on the hash chain, `reconcile()` | 0 receipts | bank feed (OBSERVED) | The pilot's receipts file is the existing ingestion path (`services/api/scripts/pilot_dry_run.py --receipts`) |
| Contract terms (price, cadence, terms and their basis, early payment, late interest, duration, notice) | **AVAILABLE on `feat/upgrading`, not on `dev`** | `ContractRecord` (owner-confirmed) | 3 demo documents (Foshan supply agreement, two lender agreements) | ERP-like / OWNER_CONFIRMED | Gives the customer-loss scenario a grounded floor (90 days' notice, cl. 2.2) and a contractual revenue cross-check; gives no margin and no payment behaviour |
| The buyers' reservation values, funding cost, surplus (`buyers.yaml`) | **NOT A SOURCE** | hidden state | | | INVARIANT 7 boundary (file header lines 3-5). It holds the buyer's economics, not the supplier's, so it is also the wrong data |

---

## C. Corrections to the map body's Reconciliation section

Quoted line by line; "Confirmed" lines are listed only where a caveat matters.

**A. Customer economics**

1. "`Counterparty` holds id, name, role and `known`; no annual sales, margin, contribution or classification
   anywhere." Confirmed for the books (`domain/models.py:454-458`). Not true of the repository: the public SME's per-buyer
   2025 sales ex VAT and the company's gross margin (23.76%) are documented in `fixtures/scenarios/public_sme.SOURCES.md`
   (lines 19, 68-75, 112), and contract ingestion on `feat/upgrading` reads contractual price, cadence and term. Both are
   outside the books.
2. "The buyer profiles in `fixtures/counterparties/buyers.yaml` ... are the negotiation kernel's HIDDEN STATE under
   INVARIANT 7 and are not a data source." Confirmed. Add: the decision record's `SentFact.outcome` and `buyer_profile`
   are outputs of that kernel and marked simulated (`decisions/facts.py:72-74`); they are equally not a source for
   acceptance or customer-loss evidence.
3. "What does exist: `ExpectedOrder` (counterparty, window, amount, firm) on `FinancialState`, the defined future demand
   section 15 requires before any 'future order' claim". Wrong in the part that matters. `ExpectedOrder` is read only as a
   rebate base (`verifier/bind.py:218-236`), as the envelope's rebate context (`whatif/offer.py:75`) and by the chat
   context (`nl/context.py:82`). The trajectory never posts it (receipts come from receivables and recurring invoices,
   `financial/trajectory.py:197-211`), it carries no cost, timing or working-capital need, both fixtures' orders are not
   firm, and in golden its size (¥400,000 a quarter) is not the recurring ¥420,000 a month. It names a quantity; it does
   not define demand that a capacity statement could be tested against.
4. "`RecurringInvoice` (a run rate)". Confirmed, with two cautions: the run rate includes VAT, and the concession window
   counts 13 issues in 365 days for a 30-day cadence (¥5,460,000 for Foshan, not 12 × ¥420,000).
5. "receivables and the hash-chained log (invoice history over the books' horizon, which the fixtures keep short)".
   Refine: invoices live in `state.receivables` (settled rows kept) and the clock's `ADVANCE_CLOCK` payload; the log holds
   receipts, not invoices. "Short" is 13 days (golden) and 96 days (public), open invoices only, and **zero** receipts.

**B. Scenario comparator**

6. "`app/strategy/impact.py` (`marginal_impact` of two sets of books ...)". Confirmed; caveat: `read_books` projects
   with no funding actions (`strategy/impact.py:168`), so "lowest headroom" is cash before the plan, and no facility
   headroom is in `MarginalImpact` (`strategy/types.py:69-93`).
7. "A customer-loss scenario is a `ScenarioState` with the buyer's expected orders and recurring invoices removed".
   Incomplete in a way that would mislead. Removing expected orders changes no cash (correction 3). Removing recurring
   invoices removes the receipts and keeps every cost, because no outflow is linked to a customer (all fixture flows have
   `counterparty_id: null`); the cash loss is overstated unless the variable cost that stops with the customer is removed
   too, which needs the margin. Already-issued invoices stay owed. The cash view covers the mandate's 120 days, the
   contribution figure a year. The contract's 90-day notice (Foshan cl. 2.2, `feat/upgrading`) is a grounded earliest
   stop date for the assumption.
8. "a late-payment scenario moves a receipt to a later day. Neither is written." Half right. The move is written
   (`_received_on`, `strategy/impact.py:81-89`) and deliberately refused past the due day (`:108-110`, pinned at
   `tests/strategy/test_impact.py:212`). Lifting the refusal is a strategy-layer change, not engine work (the probe ran
   with the engine untouched, contrary to `docs/UX_REMEDIATION_REPORT.md:109`). The financeability caveat in section A.E
   applies.

**C. Safe commercial envelope**

9. "built (map #47 Wave 3, `app/strategy/envelope.py`, `GET /buyers/{id}/envelope`, flagged)". Confirmed:
   `FEATURE_ENVELOPE` default off (`config.py:55`), web flag `NEXT_PUBLIC_STRATEGY_MVP=1`.
10. "Open against the mission: the minimum compensating price for a requested term as a first-class answer". Mostly
    built: `ZoneRow.min_price_bp` per term with the rule price (`envelope.py:491-497`, `:648-656`) and the lever "with
    the price that compensates it" with its smallest passing price (`:590-603`). What is open is a headline keyed to the
    buyer's actual ask, and the zone is now opt-in (`zone=1`) since `0cd60cb`.
11. "Each setting carries `tier`, `passes`, `cure_needs_owner` and the binding codes, which is the raw material for
    section 13's FINANCIALLY SAFE versus NEEDS OWNER APPROVAL." Partly wrong. The cap codes are hard
    (`verifier/evaluate.py:94`, `_is_hard` at `:190-193`): a package over the forward budget is REJECT or COUNTER, never
    NEEDS_OWNER_APPROVAL, and the executor can commit only a counter from such a verdict (`operations/executor.py:500-510`).
    Changing the mandate is Tier 3, never executable (`mandate/tiers.py:43`; INVARIANT 6). The raw material for "financially
    feasible but outside your signed limits" is `liquidity_only` and the lever "Terms (days), budget ignored"
    (`envelope.py:113`, `:587-589`), already computed. The honest label is "needs a new signed mandate", not "needs owner
    approval".
12. "an upfront-payment dimension (`CandidatePackage` has terms, price, early-pay rate and face, rebate; '20% upfront'
    may be the partial early payment)". Wrong. `early_pay_face_fen` is a discounted early settlement of the open invoice
    (a cost to the supplier, `strategy/types.py:44`); an upfront deposit on future deliveries has no `ObligationType`
    (`domain/models.py:79-86`) and needs the trajectory to split a receipt: an engine change behind the stability gate.
13. "the cost at scale (ticket #78 of map #58: 17 to 78 s on the public-record SME, being halved)". Stale. Merged:
    `ba79762` (reads halved) and `0cd60cb` ("the weekly envelope read without its zone (6.8 to 8.1 s on the public-record
    SME), the zone table cached apart"). The 17-78 s figure is the dry pilot's (`docs/pilot/dry-pilot-report-2026-10-09.md:89`).
14. Not in the map but needed: the mission's "52 days" and "+0.4%" are not representable or not the repo's answer. The
    grid is 5 days (`whatif/params.py:11`); golden's answer is 45 days alone, 55 days at +0.30% (0.25% smallest), not 60
    without an early payment.

**D. Capacity**

15. "the trajectory carries `debt_outstanding_fen` per day". Confirmed, but it is the total of facilities and existing
    debt (`trajectory.py:1055`); the per-facility path is computed internally (`:1006-1040`) and not exposed.
16. "`MarginalImpact` already reports `budget_used_delta_fen` and `lowest_headroom_delta_fen`". Confirmed; the second is
    cash over the floor before funding (correction 6), not credit capacity.
17. "Nothing presents headroom before / after a decision". Confirmed for before/after; today's room per facility is
    shown in the router's menu (`funding/menu.py:47-48`). Add: the deferral was a decision of map #47
    (`docs/STRATEGY_MVP_REPORT.md:28`), so this map reopens it on purpose.

**E. Late payment and concentration**

18. "Alerts detect a late receipt". Precisely: an invoice past due (`alerts/engine.py:560-588`) and a missed promised
    early payment (`:589-621`). Nothing judges a receipt as late when it arrives.
19. "nobody computes days late, medians or percentiles from it". Days late are computed for open invoices (`api/home.py
    :959`, `envelope.py:526`, `strategy/collections.py:395`); none for paid ones; no statistics. Confirmed otherwise.
20. "the fixtures hold too little history for a P90". Understated: they hold none. Zero receipts in every scenario
    fixture, one scenario of 49 posts two, the dry pilot posted none. The only lateness evidence is public SME's day-0
    snapshot of three overdue invoices.
21. "AR concentration is a sum over receivables by counterparty that nobody computes." Confirmed (no hit for
    "concentration" in `app/` or `apps/web`). Note that public SME's largest share (48.63%) is an aggregate row.

**Elsewhere in the map body**

22. Goal: "the signed mandate still decides what FLOW may do alone". Understated: for the caps it decides what may be
    committed at all, by anyone, through FLOW (correction 11). The mission's own sentence "Owner approval is still
    required for anything outside the signed mandate" (section 52) does not match the product and should be reworded in
    the spec.
23. Notes: "21 commits ahead of `dev`". Confirmed (`git log --oneline origin/dev..origin/feat/upgrading | wc -l` = 21);
    its merge base is `95c83d8`, before maps #47 and #65 landed, so the diff is 226 files.

---

## D. The three biggest surprises

1. **The ¥5,000 limit is not an "autonomous limit" the owner can approve past.** It is a signed, hard cap: an over-budget
   package is REJECT or COUNTER (`verifier/evaluate.py:94, 190-193`), the executor commits only counters from such a
   verdict (`operations/executor.py:500-510`), and a mandate change is Tier 3 (`mandate/tiers.py:43`). The mission's
   central UX ("outside your autonomous limit ... owner review recommended") has no in-app path to act on. Customer
   economics therefore informs one of two owner actions FLOW does not execute: send a counter, or re-sign the mandate
   (perhaps with a per-buyer cap, which only tightens today). The envelope already measures the gap between the two
   statements (`liquidity_only`, "budget ignored": golden 45 days within the budget, 55 days on liquidity alone).
2. **The books already contradict the mission's example and bound the answer.** Golden Foshan is 100% of revenue, the
   run rate is ¥5,460,000 (incl. VAT), and 12 × EBITDA is ¥1,080,000; so Foshan's contribution is at least ¥1,080,000
   and the ¥28,326.92 request is at most 2.62% of it, not 7.1% of ¥400,000 (a ¥400,000 contribution would make annual
   EBITDA at most ¥400,000, against the books' ¥1,080,000). Invoice faces carry VAT (13%), so revenue read from invoices
   is high by 13% unless netted. And the public SME fixture drops ¥11,019,398.60 (10.5%) of its filing's revenue: the
   4th and 5th customers are subtracted from "Other buyers" (`SOURCES.md:75`) yet are said to be inside it (`:77-78`), so
   derived revenue shares are biased (Buyer A 24.33% of the run rate against 21.78% in the filing).
3. **There is no payment history anywhere, and the pilot procedure deletes it.** Zero receipts in every fixture; the
   pilot runbook removes each paid invoice from the next week's `state.json` (`docs/pilot/RUNBOOK.md:236-237`) and keeps
   due-versus-arrival dates on paper only. Mission section 20 (observed behaviour outranks estimates) cannot be met by
   any data in the repository, and will not be by the pilot as written. Yet the stress test needs no history: the probe
   shows Foshan 30 days late raises the need from ¥405,000 to ¥550,000, the plan cost from ¥3,113.93 to ¥6,488.98, adds
   45 breach days and makes the plan not executable today, with the engine untouched. The conservative trajectory
   already treats any overdue invoice as never paid (`financial/trajectory.py:916-917`), which is 35.2% of public SME's AR
   on day 0.

---

## E. The one avenue to lead with: buyer exposure (concentration and late-payment stress) on the deal

On the repository's evidence, the avenue with the most value for the least new data is **a per-buyer exposure
reading attached to the deal: the buyer's share of open AR (and of the next 30 days' receipts), and the deal's books
under "contractual" and "+N days late" receipts, each through the unmodified `marginal_impact`.**

- **New data: none.** Every input is AVAILABLE or DERIVABLE NOW (matrix rows: current AR, AR share, 30-day receipts
  share, the stress scenario). Customer economics needs one owner number per buyer (margin) plus a VAT setting before it
  says anything; payment statistics need history that does not exist.
- **Reuse, not a new framework.** It is `ScenarioState` + `marginal_impact`, with one transform ("move a buyer's
  receipts by N days") that is also the first row of the scenario comparator and, with N = ∞ and receipts removed, the
  receipts side of the customer-loss scenario. One primitive serves B and E (the mission's section 47 test of "two
  capabilities share it").
- **It answers two of the five decisive facts of the mission's section 52 with repo-true figures**, on both fixtures:
  "Foshan represents 100% of current receivables" and "if its payment arrives 30 days late, you would need approximately
  ¥145,000 more and the plan stops being runnable today". It is read-only, flaggable like the strategy routes, and runs
  in about a second for three scenarios on the fixtures.
- **It avoids the two traps the evidence shows**: it makes no claim that depends on the cap being approvable
  (surprise 1), and no claim that depends on margin or history the books lack (surprises 2 and 3). Stress is labelled
  STRESSED, never "typical", until receipts accrue.
- **Customer economics comes second**, as the mission's headline: one owner-entered margin per buyer (labelled
  OWNER_ENTERED, netted of VAT), the forward run rate (PROJECTED), and the books' floor (Σ contribution ≥ 12 × EBITDA) as
  an automatic check on what the owner types. Capacity before/after (D) is the third zero-data derivation and joins the
  same reading.

Spec obligations this choice carries: lift `scenario_received`'s past-due refusal only in a new, separately named
transform (the existing refusal and its test stay); state the financeability caveat; count a moved receipt exactly once
(mission section 39); show the 120-day cash horizon beside any annual figure; and add a ticket against the pilot runbook
so paid invoices and their receipt days stay in the books.
