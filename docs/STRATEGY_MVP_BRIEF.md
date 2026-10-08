# FLOW strategy MVP: execution brief

Wayfinder map #47, Wave 0 (ticket #48), 8 October 2026. The lead's architecture for the read-only MVP the synthesis
(`docs/STRATEGY_RESEARCH.md` on `research/strategy`, sections F, K, L and the three implementation plans) recommended
and the owner authorised. Every later wave builds exactly what a section here names and pins exactly the figures its
pin table lists. Vocabulary is CONTEXT.md's; quantities are `docs/FINANCIAL_SEMANTICS.md`'s; the rules are
`docs/HANDOVER.md` sections 3 and 5 and the map's Notes.

## 1. What is being built, in one paragraph

Three read-only answers over the existing kernel (`evaluate`, `plan`, `project`, `alerts`), each a thin layer of
sweeps, deltas and rankings over the kernel's outputs on labelled copies of the books: the Safe Deal Envelope (what we
can offer a named buyer before they ask, as approved packages), the cash price curve (what ¥10,000 arriving 30 days
earlier is worth, by arrival day, as one sentence) and collections marginal value (what each open receivable is worth
to collect and what to do about it). Three shared types carry them: `ScenarioState` (a labelled copy with its
assumption), `CandidatePackage` (a buyer-addressed package with no inbound offer) and `MarginalImpact` (the delta
between two books). `Capacity` is deferred (map decision 2). Nothing acts: no operation, no tier, no mandate change,
no engine change. Everything is behind flags that default off, so the demo path, the mocks and the screenshots of `dev`
do not change.

## 2. Module layout

```
services/api/app/strategy/
    __init__.py          exports the public names below; imports nothing at module import time that the app does not already load
    types.py             ScenarioState, CandidatePackage, MarginalImpact (frozen Contract models)
    impact.py            marginal_impact(), scenario_received(), scenario_inflow()
    price_curve.py       PriceCurve, price_curve(), price_sentence()                  (Wave 2)
    envelope.py          EnvelopeAnswer, envelope(), the sweep and the package grid    (Wave 3)
    collections.py       ReceivableWorth, receivables_worth(), the action rules       (Wave 4)
    words.py             the sentence builders (en and zh) the three modules share; Business words only
services/api/app/api/strategy.py        one APIRouter with the three routes, each calling require_feature() first
services/api/app/api/features.py        require_feature(name): 403 FEATURE_DISABLED (the alerts router's shape)
services/api/scripts/research/          the spikes (the oracle's source; never imported by the app)
services/api/scripts/strategy_backtest.py                                             (Wave 6)
fixtures/strategy/                      the recorded oracle JSON (never edited by hand)
services/api/tests/strategy/            every test of this map
apps/web/components/deals/before-they-ask.tsx, app/cash/page.tsx, app/receivables/page.tsx,
apps/web/components/business/blocks.tsx, lib/api.ts, lib/types.ts, lib/live/index.ts, lib/mock/handlers.ts,
apps/web/mocks/strategy/*.json, apps/web/e2e/strategy.spec.ts                        (Wave 5)
```

Rules for `app/strategy/`: it calls `current_books`, `evaluate`, `plan`, `compare`, `project`, `alerts`,
`reconcile`, `past_due_invoices`, `value_concessions`, `marginal_cost`, `smallest_step_covering`, `infeasibility`,
`whatif.offer.build` and `context`, and the display helpers (`displayed`, `fmt_yuan`, `fmt_pct`, `when_text`,
`relative_days`, `business_text`), and edits none of them. The one permitted change outside `app/strategy/` and
`app/api/` is the what-if builder's generalisation to a buyer id (Wave 3), which must leave `POST /whatif`'s results
identical (its tests pin them). A function the verifier keeps private (`_early_pay_vs_plan`) is reached through a
public wrapper in `app/strategy/collections.py` that reproduces its call, not by editing the verifier. Every state
passed to the kernel is a `model_copy`; nothing is stored (`put_verdict` is never called); every function is pure in
(state, mandate, day, commitments) so the per-state caches are sound.

## 3. The shared types (Wave 1)

`ScenarioState` (frozen `Contract`): `state: FinancialState` (the copy), `label: str` (short: "RCV-A received today"),
`assumption: str` (the sentence the UI may show: "assumes the ¥162,800 from Foshan arrives today"), `hypothetical:
Literal[True]`, `source_state_version: int`, `day: int`. Constructors in `impact.py`:

- `scenario_received(books, receivable_id, on_day) -> ScenarioState`: the receipt moved. `on_day == today`: cash
  credited with the outstanding residual, the receivable SETTLED (`settled_fen = face_fen`), as 01 §7.3 did; a FINANCED
  receivable pays the lender first (ADR-0010, through the public `financial.lots.apply_receipt`: the lot is cleared
  with its charges out of the receipt, the facility's drawn balance falls, cash gets the rest). `on_day > today`, up to
  the due day: the receipt is moved the way the collections spike moved it, by ending the receivable's `terms_days` on
  the COPY on that day, so the engine posts the RECEIPT there and the invoice stays financeable until then (Wave 1
  found that an `IMMEDIATE_DISCOUNT` at 0 bp settles the invoice early, so the router can no longer finance it and
  prices another source: ¥146.82 of cost instead of the oracle's ¥532.49 saving on day 27). The books' own receivable,
  the commitments and the contract are untouched; the copy is labelled hypothetical. An overdue receivable (due before
  today), a FINANCED receivable, a day before today or after the due day: only the today case; otherwise `ValueError`.
- `scenario_inflow(books, amount_fen, on_day) -> ScenarioState`: one confirmed `CashFlow` of `amount_fen` on `on_day`
  appended to the state's flows (label "¥10,000 arrives on day d").

`CandidatePackage` (frozen `Contract`): `buyer_id: str`, `terms_days: int`, `price_bp: int = 0`, `early_pay_bp: int = 0`,
`early_pay_face_fen: int | None = None` (None: the whole open invoice), `rebate_bp: int = 0`. Validation: rates on the
5 bp grid, terms on the 5-day grid, within `whatif.params` ranges; a package is a `WhatIfParams` plus a buyer.

`MarginalImpact` (frozen `Contract`), every money field with a sibling `_display` produced by `displayed` at the route:
`label`, `need_delta_fen`, `posted_cost_delta_fen` (after − before: negative is a saving; kept as is), `first_breach_before:
int | None`, `first_breach_after`, `lowest_headroom_delta_fen`, `budget_used_delta_fen`, `breach_days_removed: int`,
`alerts_removed: list[str]` (codes), `alerts_added: list[str]`, `before_needs_owner: bool`, `after_needs_owner`,
`before_executable_now`, `after_executable_now`, `before_cost_fen`, `after_cost_fen`, `before_need_fen`, `after_need_fen`. `budget_used` is the alerts engine's own figure (`_concession_alerts`' total: the maximum forward-concession
value over the trajectory, floored at the booked concessions).
`marginal_impact(before: Books, after: Books, mandate, *, store, day) -> MarginalImpact` runs `plan(state, books.with_([]),
mandate)` (COMMITTED), `project(state, obligations, [], CONSERVATIVE)` and `alerts(state, mandate, store, day)` on each
side, inside one `shared_runs()` block, and subtracts. "Posted cost" is `FundingPlan.total_cost_fen` (interest, fees and
discounts the trajectory posts under the plan, ADR-0007); "need" is `need_fen`; "first breach" is the first day the
conservative trajectory is below `min_cash_fen`; "lowest headroom" is min(cash − floor) over the horizon.

## 4. The routes (Waves 2 to 4) and the flag rule

All three live in `app/api/strategy.py`, owner-authenticated like the what-if routes (`Depends(require_owner)`), each
calling `require_feature("<flag>")` first (403 `FEATURE_DISABLED` when off, the alerts router's shape), each taking
`lang` (`en` | `zh`, default `en`) and returning `hypothetical: True`, `state_version`, `day`, `computed_in_seconds` and
server-formatted strings through `displayed`. A route never writes, never logs an operation, never calls `put_verdict`.

| Route | Flag | Returns |
| --- | --- | --- |
| `GET /cash/price-curve` | `price_curve` | `PriceCurve`: `amount_fen` (10,000 00: the router's `GRID_STEP_FEN`), `window_days` 30, `bands[]` (`from_day`, `to_day`, `from_when`, `to_when`, `value_fen`, `value_bp` of the amount, `varies: bool`), `sentence` (section 6), `flat: bool` (no breach: every band ¥0) |
| `GET /buyers/{buyer_id}/envelope?zone=0|1` | `envelope` | `EnvelopeAnswer`: `buyer_name`, `primary`, `reason`, `money`, `packages[]`, `levers[]`, `zone[]` (only with `zone=1`), `refused: str | None` (the one sentence when the buyer has no lever) |
| `GET /receivables/worth` | `collections_worth` | `rows[]` of `ReceivableWorth` ranked by net value, `top_action` (the first row's action sentence, for the home), `ranking_note` ("ranked by what collecting each saves you, net of any discount that earns it") |

Caching: the envelope is cached by `sha256(state json, mandate json, day, buyer, commitments json, zone)` in a 32-entry
LRU like `whatif.simulate`; the curve and the worth by the same key without the buyer. `clear_caches()` of the verifier
is not called by the routes. No background thread in the MVP.

## 5. The three modules

### 5.1 Cash price curve (Wave 2, estimate 3 agent-days)

For arrival day `d`, the value is the spike's definition (collections_spike, "cash price curve"): the plan's cost with
¥10,000 arriving on `d + 30` minus the plan's cost with it arriving on `d`, i.e.
`marginal_impact(scenario_inflow(books, 10,000 00, d + 30), scenario_inflow(books, 10,000 00, d), ...).posted_cost_delta_fen`
negated is the saving of having the same cash 30 days earlier. Not an inflow-and-outflow pair against the bare books:
Wave 1 showed the two agree on the day-0 books but not on the day-34 books (¥89.11 against the oracle's ¥178.22 for
d = 34), because the plan is not linear in the flows; `test_the_curve_points_are_reproduced_by_the_spikes_pair` pins
the spike's pair at nine arrival days on each book. Bands are cut at the breach episodes' first and recovery days (`alerts()` RESERVE_BREACH_AHEAD items carry
them) and the plan's repayment days; the value is computed at each band's two ends and, when they agree, assigned to
the band; when they disagree the band is bisected recursively until the step sits between two adjacent days (Wave 2: one
midpoint split was not enough on day 34, where the step at day 61 is far from any boundary), within a budget of 120 extra
evaluations; a band the budget cannot settle is `varies: True` with the smaller value. Expected on the golden books: day 0 → ¥89.11 for days 1–30, ¥0 for day 0 and from
day 31; day 34 → ¥178.22 for 34–42, ¥89.12 for 43–60, ¥0 from 61 (so the day-0 answer has at most three bands and the
day-34 answer four). The value never exceeds the cost of funds for TWO whole fee periods (60 days) on the amount
(`break_even_cost_share(state, mandate, 60)` × ¥10,000: FAC-IF bills whole 30-day periods, so moving cash 30 days
earlier can save two periods' fees, which is the day-34 ¥178.22 = 2 × ¥89.11); assert it, and assert that bands
outside the breach episode stay within one period (¥89.11/¥89.12).

### 5.2 Safe Deal Envelope (Wave 3, estimate 8 agent-days)

Inputs: the buyer id, the books (`books_from_store`), the mandate, the day, the commitments. The builder: `whatif.offer.context`
generalised to `context(state, day, buyer_id=None)` (default: today's behaviour, the one buyer with a recurring invoice
and an open receivable); with a buyer id it picks that buyer's recurring invoice (`recurring_for`) and its earliest open
receivable; a buyer with neither is refused with "FLOW has no terms or payment lever to value for <name> yet: no
recurring invoice and no open invoice." A buyer with open receivables but no recurring invoice gets the early-pay levers
only (terms and price levers reported as "no recurring invoice to extend").

The sweep (the spike's method, `envelope_spike.py`): ranges from the what-if grid held to the mandate's immediate-discount
cap; per lever alone, `last_true` bisection with the two neighbours past the boundary checked, a scan of that lever if
a neighbour disagrees; `evaluate(offer, state, mandate, trusted_owner_key_hex, day, commitments, plans="committed")`;
"passes" is outcome ACCEPT or NEEDS_OWNER_APPROVAL with every RESERVE_BREACH curable; the wall per lever from the binding
codes (map decision 2). The package grid: terms in force, +5, +10 × early-pay variants {none; Option A's face at its
whole-5bp rate below the break-even; the whole face at the largest rate that passes inside the package (searched, not the
standalone maximum)}; per cell the smallest passing price, then the largest passing rebate at that price; each package
re-evaluated whole and re-checked with `counters.infeasibility` (None required); a package whose cure cannot run today or
needs the owner is kept and flagged in words. `levers[]`: maximum alone, the wall, what the next step fails with.
`zone[]` on request: terms × price, the smallest passing price per terms value with the Option B rule's price beside it.

Sentences (en and zh, Business words, distances from today): `primary` from the packages (golden books: "Up to 55-day
terms if the price rises 0.30%, or early payment at up to 0.85% on ¥257,200; a rebate up to 1.25%; not 60 days without
an early payment."); `reason` from the binding wall of the next step ("60 days leaves a shortfall in 47 days that no
cure covers; the ¥5,000 budget buys no terms without a price step."); `money` from the curve's sentence builder when the
flag is on, else the posted cost of Option A against the standing plan ("Cost to you ¥0 (price step) or ¥3,027.77
(early payment); without a deal the standing plan costs ¥3,113.93."). "What you can live with", never "what to offer".

### 5.3 Collections worth (Wave 4, estimate 6 agent-days)

Per receivable with outstanding face (OPEN or FINANCED; unissued recurring invoices excluded): scenarios "received
today", "five days before due", "on the first breach day" (only "today" when overdue; only the ones before the due day
otherwise), one `marginal_impact` each; gross saving = −posted_cost_delta of the today scenario (or the earliest
available), need left = `after_need_fen`, with the after plan's approval and executable flags; the early-pay ceiling by
`last_true` over whole-5bp rates on two faces (the whole outstanding; the plan's need rounded to the ¥100 grid), each
rate tested by the ADR-0007 comparison (C1 with the discount obligation against C0 without, both under the router's
plan: the wrapper reproduces `_early_pay_vs_plan`'s inputs through `plan` and `project`), held to the mandate's
immediate-discount cap; never on an overdue invoice. Net saving = gross − the discount posted at the ceiling on the
plan's-need face (what earning the receipt early costs). Action rules in order: call now (past due; "the only free
action"); escalate (a lapsed promise in `reconcile().lapsed_promises`, or days late ≥ 30 when the mandate has no
threshold); reminder (due within the first breach episode and not promised); offer early payment up to X% on ¥Y (due
after the first breach day and the ceiling's saving beats the cure it replaces); finance the invoice (an advance on it
lands before the breach and the discount does not beat it, or the ceiling is 0); wait (due beyond the episode). A
negative delta (RI:BUYER-1:32 five days early: −¥76.09) is displayed "no saving" with the raw figure in the payload.
Ranking by net, gross beside; the order must be identical before and after `clear_caches()`.

## 6. Wording rules (every display string is tested)

- Business words only at level 1: distances from today (`when_text`, `relative_days`), the buyer's name, no engine
  terms (no "verdict", "trajectory", "basis", "fen", violation codes) and no "day N" in English or Chinese.
- The curve (as built in Wave 2): "Cash arriving within the next 30 days is worth 0.89% to you; after that, nothing.";
  two bands: "Cash arriving within the next 8 days is worth 1.78% to you, then 0.89% if it arrives within the next 26
  days; after that, nothing."; flat: "Earlier cash saves you nothing today." Never "rate", "charged", "interest" in
  the sentence. Chinese: 未来 30 天内到账的现金对你价值 0.89%；之后则没有。
- The envelope: "what you can live with", never "what to offer them" or "give them"; "approved" means passes FLOW's
  checks, never that the deal is good; a flagged package says "needs your approval" or "its funding cannot run today".
- Collections: "worth collecting", "saves you", "what you can afford", never "offer them a discount"; "no saving" for a
  negative delta; "hypothetical" or "if it arrived" in every scenario sentence.
- Chinese twins for every sentence through `app/strategy/words.py` with `t(lang, en, zh)`.

## 7. Pin table (the figures every wave must reproduce; the spike is the truth)

| Wave | Figure | Value | Oracle |
| --- | --- | --- | --- |
| 1 | RCV-A received by day 12, day-0 books: saving | ¥3,113.93, breach removed | `fixtures/strategy/collections_both.json` day 0 |
| 1 | RCV-A residual ¥162,800 received today, day-34 books | saves ¥1,374.61; need left ¥37,200 costing ¥331.49, needs approval | collections_both, day 34 |
| 1 | RI:BUYER-1:32 received on day 72 (five days early) | −¥76.09 (kept negative) | collections_both, day 34 |
| 2 | Curve, day 0 | ¥89.11 per ¥10,000 for arrival days 1–30; ¥0 on day 0 and from 31 | collections_both, curve |
| 2 | Curve, day 34 | ¥178.22 for 34–42; ¥89.12 for 43–60; ¥0 from 61 | collections_both, curve |
| 3 | Terms alone | 45 passes; 50 fails AGG (¥8,108.97 against ¥5,000) | `fixtures/strategy/envelope_day0.json` levers |
| 3 | Terms, budget ignored | 55 (cure ¥1,570.36 on FAC-IF, day 47, cannot run today); 60 breaches day 47, no cure | envelope_day0 levers |
| 3 | Smallest passing price | 55 days 0.25% (Option B rule 0.30% beside); 50 days 0.10%; 60 days with Option A from 0.40% | envelope_day0 zone |
| 3 | Early pay | 0.70% whole face; 0.85% on ¥257,200 (0.90% fails DISCOUNT_ABOVE_BREAK_EVEN, C1 ¥3,027.77 vs C0 ¥3,113.93) | envelope_day0 levers |
| 3 | Rebate | 1.25% (¥5,000 exactly); 1.30% fails AGG | envelope_day0 levers |
| 3 | Package grid (30 packages) | the oracle's `packages[]` reproduced to the fen: for each terms value and early-pay variant the smallest passing price and the largest passing rebate, outcome, codes, budget used, the breach with its cure; e.g. 55 days, 0.25%, 0.85% on ¥257,200, rebate 0.60%: NEEDS_OWNER_APPROVAL, cure ¥2,673.04 on day 47 | envelope_day0 `packages` |
| 3 | Interaction packages (nine, from the deep dive, confirmed by the spike) | 50 + 1.25% fails AGG ¥13,108.97; 55 + 0.30% passes ¥0; 55 + 0.30% + 1.25% passes ¥4,837.95 and 1.30% fails ¥5,037.95; 55 + 0.30% + 0.85% on ¥257,200 passes ¥0, cure ¥2,673.04; 60 + 0.45% + 0.85% on ¥257,200 passes; EX01 as asked fails ¥28,326.92, cure ¥2,406.67; 80 + 0.95% + 0.85% on ¥257,200 passes, cure ¥4,009.57; 85 fails AGG ¥10,271.78 | to record in Wave 3 with `envelope_spike.py --package ... --json` into `fixtures/strategy/envelope_packages.json` (the day-0 oracle's `checks` list is empty) |
| 3 | Day-34 books | no extension passes (line ¥13.80 left, headroom ¥0) | deep dive only (not spiked): assert "no extension passes" and record the figures the engine gives |
| 3 | Runtime | default grid under 8 s cold | measured |
| 4 | Day 34 ranking | net: RCV-A ¥1,374.61, RI:BUYER-1:2 ¥77.58, RI:BUYER-1:32 ¥73.68; gross: ¥1,706.10, ¥1,706.10, ¥1,374.61 | collections_both, day 34 |
| 4 | Ceilings | RI:BUYER-1:2: 0.80% on ¥200,000, 0.40% on ¥420,000; RI:BUYER-1:32: 1.20% on ¥200,000, 0.65% whole; 0.40% on ¥200,000 beats the cure by ¥888.28; 0.85% dearer by ¥24.20 | collections_both, day 34 |
| 4 | Actions | RCV-A call now; RI:2 offer early payment or finance; RI:32 wait (rule) | collections_both, day 34 (RI:32 "wait" is the brief's rule, the spike said offer) |
| 4 | Day 0 | RCV-A worth ¥3,113.93 by day 12; whole-face ceiling 0.70%; 0.75% on ¥405,000 | collections_both, day 0 |
| 6 | Portfolio (gate only) | best ¥3,027.77 posted (¥841.57 funding); `evaluate_many` rank 7 of 9 at ¥6,113.93 | `fixtures/strategy/portfolio_default.json` |

Not spiked and therefore not displayed anywhere in the MVP: ¥140,000 exposure at 55 days; DSCR 1.92× and leverage
1.72× at 60 days; the day-0 partial receipts (¥891.09, ¥2,284.63, ¥1,785.91, ¥585.10, ¥26.30); "escalate by day 39".

## 8. Acceptance per wave

Every wave: `git diff feat/strategy-mvp -- apps/web` empty for Waves 1 to 4 and 6; `services/api/app` touched only under
`app/strategy/`, `app/api/strategy.py`, `app/api/features.py`, `config.py`, `main.py` (the router mount) and, in Wave 3,
`app/whatif/offer.py` with the what-if suites unchanged; ruff and mypy clean; `SKIP_PERF_BENCH=1 pytest -q
tests/api tests/nl tests/alerts tests/funding tests/verifier tests/whatif tests/strategy` green with the flags off and
on; a `verifier` agent reproduces the wave's pins from the kernel before the merge; plain one-line commits; the wave
branch merged into `feat/strategy-mvp` with `--no-ff` and pushed; the resolution comment on the ticket.

Wave 5 (UI): the default build renders nothing new (`NEXT_PUBLIC_STRATEGY_MVP` unset: components not mounted, client
functions never called; mock e2e, live e2e and the screenshot walk identical); with the flag, `E2E_STRATEGY=1` mock and
live runs green; the grep gate for money arithmetic in `apps/web` passes; `apps/web/DESIGN.md` rules hold (one brand-filled
action per page: the envelope card's two buttons are secondary pills, the page's one filled action stays where it is);
a `design-reviewer` pass with nothing material open. Wave 6: the full backtest exits 0 with the report committed.
Wave 7: the gate counts in the report.

## 9. The backtest (Wave 6)

`services/api/scripts/strategy_backtest.py [--json] [--quick]` with the three flags set in-process:

1. Envelope: for every offer in `fixtures/offers/offers.yaml` and `fixtures/heldout*/`, compile and evaluate on the golden
   books, compute the envelope for its buyer; assert every counter in the verdict appears among the packages (same
   terms, price, early-pay rate and face, rebate); "as asked" is inside the zone iff the verdict passes; every package
   passes its re-check and `infeasibility`; bisection agrees with the exhaustive grid per lever; count the refusals.
2. Collections: replay `services/api/evals/e2e/scenarios.yaml` in process (the scenario runner's `--inproc` machinery);
   after each turn compute the worth; assert "call now" rows are past due, no ceiling exceeds the cap or the plan
   comparison, the order is stable under `clear_caches()`; count the days the net order differs from the amount order.
3. Curve: at each replayed day, band values equal `marginal_impact` at the ends; the value never exceeds the marginal
   cost of funds; count flat days.
4. Differential: the three modules on the golden day-0 and day-34 books against `fixtures/strategy/*.json`, to the fen.

Writes `docs/research/strategy/06-backtest-<date>.md`; exit 1 on any failure; `git checkout -- services/api/evals` after.
`tests/strategy/test_backtest_short.py` runs `--quick` (the golden fixture's offers and one scenario) under 60 s.

## 10. Integration loop and ports for this map

As `docs/handover/05_strategy_and_ux_handoff.md` section 3, with: worktrees `.claude/worktrees/mvp-w<N>`, branches
`feat/mvp-w<N>` from `feat/strategy-mvp`; mock e2e `E2E_PORT=3107+N`; live e2e `E2E_API_PORT=8011+N E2E_LIVE_PORT=3011+N`;
the strategy live run adds `FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1` to the API's
environment and `NEXT_PUBLIC_STRATEGY_MVP=1 E2E_STRATEGY=1` to the web's; the full API suite `pytest -o addopts= -q
services/api/tests` runs once with the flags off and once on before the Wave 7 report; screenshots with the flag on into
`docs/screenshots/strategy-mvp-<date>/`.

## 11. Where the cards land (recon addendum)

Read-only reconnaissance of `dev` at `bcc67d4` by a research agent (8 October 2026); the page and component names the synthesis used at `d1eadb0` still hold.

Read-only survey of `/Users/ianpong/Hackathons/smu2sz/apps/web` on branch `dev` (8 Oct 2026). All paths below are relative to `apps/web/` unless absolute. Nothing in the repo was changed.

### 1. Deals page (`app/deals/page.tsx`, 266 lines) and `components/deals/*`

#### Render order (page.tsx:121-264)
1. `PageHeader section="deals"` (123).
2. `<DealSteps />` only when an offer is selected (124).
3. `NextStep` band (125-129) from `next` (99-117): "Check against my limits" primary `Button` when `offer && !v` (100-108); after a negotiation, a `nextLinkCls` anchor to `#commitments` / `#inbox-list` (109-113); when counters exist, a `nextLinkSecondaryCls` anchor to `#counters` (114-116, deliberately not brand-filled: the response card holds the page's one primary).
4. `<div className="space-y-5">` (130):
   - `InboxList` (131-142) always first, with `currentDocId`, `readDocIds`, `known`, `busy={reading}`, `today`, `mode`, `statusFor`, `onOpen`, `loadError={books.error}`, `onRetry={books.reload}`.
   - page `error` → `ErrorState` (144).
   - then a 4-way branch (146-262): `cur.error || clock.error` → `ErrorState`; `cur.loading || !clock.data` → `LoadingBlock rows={3}`; `!offer` → `EmptyState` (title `biz.deals.empty`, body `biz.deals.empty.body`, action `ButtonLink /chat`) + `commitments` (156-160); else the thread.
   - Thread (161-261): `Card id="deal-ask"` (163-192) titled `t("biz.deals.ask", { buyer: buyerName(offer.offer.counterparty_id) })`, subtitle `biz.deals.messageWhen` with channel + `whenText(received_day, today)`; **`<BuyerAsks asks={asks} />` is the first child (168)**, followed by the abstentions `Callout` (`data-testid="deal-abstentions"`, 169-191). A "Before they ask" card would sit right after this Card (between 192 and 194) or as a sibling inside it after `BuyerAsks`.
   - `!v` → `commitments` only (194-195); else `DealDecision` (198) → `RecommendedResponse` (199) → `commitments` (200) → three `Disclosure card` folds `deal-why`, `deal-original`, `deal-calc` (202-258).

#### Page state when no message has been read for a buyer
- There is no per-buyer state. Selection lives in the demo store (`lib/demo-store.ts:10-34`): `offerId`, `offers`, `verdicts`, `negotiations`, `version`. `useCurrentOffer()` (`lib/use-current.ts:19-33`) returns `offer=null`, `verdict=null`, `negotiation=null`, `loading=false` when `offerId` is null; the page then renders the `EmptyState` branch (156-160). While a message is being read, `reading` (46) holds its id and is passed as `busy` to the inbox.
- The inbox itself is static: `INBOX` in `lib/inbox.ts:31+` (messages EX01, EX01B, ACC, SEC...), grouped per `counterparty_id` in `inbox-list.tsx:17-26`. A buyer on the books with no inbox message has no thread; `known` (page.tsx:51) is the set of `state.counterparties` ids and gates Business mode (inbox-list.tsx:29-34: nothing shows until the books load).

#### Derivations
- `mode`: `useMode()` (page.tsx:39) from `lib/mode.ts:13-15`, a `createStore` on localStorage key `tl-mode`, `"business" | "demo"`, default business.
- `today`: `clock.data?.day ?? books.data?.day ?? 0` (50) with `books = useAsync(getState, [])`, `clock = useAsync(getClock, [])` (47-48).
- `buyerName(id)`: `books.data?.state.counterparties.find(c => c.id === id)?.name ?? id` (52).
- current offer: `cur = useCurrentOffer()`; `offer = cur.offer`, `v = cur.verdict` (92-93); `asks = v?.bound_obligations?.length ? v.bound_obligations : compiled obligations` (96).
- `evaluate()` (54-65) calls `lib/demo.ts evaluate(offerId)`; `openMessage(m)` (68-81) calls `submitOffer` then `recordOffer`, or `selectOffer` if already read.

#### Testids on the page and in `components/deals/*.tsx`
- page.tsx: `deal-abstentions` (170), `deal-why` (203), `deal-original` (208), `deal-calc` (222), `deal-calc-item` (227); ids `deal-ask`, `deal-plan`, `#counters`, `#commitments`, `#inbox-list` are anchors.
- asks.tsx: `deal-asks` (62), `deal-ask-${o.type}` (64, e.g. `deal-ask-IMMEDIATE_DISCOUNT`), `deal-parsed-terms` (69).
- decision.tsx: `deal-recommendation` + `data-outcome` (48), `deal-if-accept` (53), `deal-fact-cost` (59), `deal-fact-cash` (66), `deal-fact-worst` (79), `deal-discount-dearer` (87); card id `deal-recommendation-card` (46).
- response.tsx: `deal-option-${label with spaces→-}` (26, e.g. `deal-option-Option-A`), `deal-option-text` (31), `deal-option-cost` (39, 56), `deal-option-details` (63), `deal-option-terms` (67), `deal-negotiation` (94, 116), `deal-agreed` (98), `deal-agreed-terms` (100), `deal-rounds` (119), `deal-gap-funded` (129), `deal-nothing-changed` (136), `deal-buyer-words` (143), `deal-no-offer` (185), `deal-send` (199), `deal-send-blocked` (203), `deal-compare` (225).
- inbox-list.tsx: `inbox-msg-${m.id}` (82), `inbox-msg-status` (109), `inbox-thread-${cp}` (128), `inbox-error`/`inbox-loading` (145), `inbox-list` (157), `inbox-others` (161), `inbox-blocked` (170).
- deal-steps.tsx: `deal-steps` (31). commitments.tsx: `commitment-${id}` (84), `commitment-terms` (89), `commitments-live` (128). reasons.tsx: `deal-reasons` (50), `deal-reason-${code}` (52), `deal-all-checks` (60), `deal-technical-summary` (70).

#### How counter cards open (`components/deals/response.tsx`)
- `RecommendedResponse({ v, offerId, today, mode, negotiation })` (163). `counters = v.counters as Counter[]` (168); `[first, ...rest] = counters` (193). Option A is `first`, rendered always (215) with `recommended` and the `sendAction`; Option B and later are `rest`, rendered only while local `compare` state is true (165, 216).
- "Compare another option" is a `Button variant="secondary"` toggling `setCompare` (225-227); label `biz.deals.compare` with `{ n: rest.length }` / `biz.deals.hideCompare`.
- "Send this counter" (196-210) exists only in `mode === "business"`: `Button variant="primary" data-testid="deal-send"` disabled when `first.outbound_blocked`; `send()` (170-180) calls `negotiate(offerId, { buyer_profile: "cooperative" })` then `recordNegotiation`. Once `negotiation` is set the card is replaced by `NegotiationOutcome` (192).
- `CounterBusinessCard({ c, recommended, today, action })` (22) is module-private (not exported); the `Card` wrapping the list has `id="counters"` (213).
- **What a new card would need to open Option A / B**: `compare` is private `useState` inside `RecommendedResponse`, so there is no prop or store to drive it today. Options: (a) an anchor `href="#counters"` already scrolls to the card (the NextStep band does this, page.tsx:116) and Option A is always visible there; (b) to reveal Option B, `RecommendedResponse` would need a new optional prop (e.g. `initialCompare` or a controlled `compare`/`onCompare`) or a lifted state in the page; (c) to point at a specific option by label use the existing testid/anchor pattern `deal-option-Option-B` (there is no `id` on the `<li>`, 26). Any such card must not add a second brand-filled button on Deals (see section 8 and `e2e/colour.spec.ts:86-91`, which asserts exactly one once `deal-send` is visible).

### 2. Cash page (`app/cash/page.tsx`, 231 lines)

- Risk card: `Card id="cash-answer" title={t("biz.cash.risk")} tone=bad|ok|warn actions=<Badge>` (112-158). Inside: headline `<p className="text-xl font-semibold text-ink" data-testid="cash-headline">{h.headline}</p>` (118-120); `<p className="mt-1 text-sm text-ink-2">{h.note}</p>` (121); worst line `mt-1 text-sm` + `text-bad-fg` or `text-ink-3` (122); the four `FactTile`s in `<dl data-testid="cash-figures" className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">` (124-141, tile testid `cash-unsafe-when` at 133); the headroom `<dl data-testid="cash-headroom" className="mt-3 flex flex-wrap items-baseline gap-x-8 gap-y-1 text-sm">` (142-157) with `dt text-ink-3` / `dd font-semibold tabular-nums text-ink`, labels `biz.headroom`, `biz.lowestHeadroom` (dictionary 1088-1089; zh 2687-2688).
- **Where the one sentence goes**: immediately after the headroom `</dl>` closing `) : null}` at line 157, still inside the Card body (before `</Card>` at 158). The flag-gated paragraph would be a sibling of `cash-headroom`.
- Secondary-sentence styles in use on this page: `mt-1 text-sm text-ink-2` (121, the note), `mt-1 text-sm text-ink-3` (122, quiet), `mt-3 text-xs text-ink-3` (67, `cash-cheaper-option`), `mb-3 text-xs text-ink-3` (64, 200), `text-xs text-ink-3` (87). Elsewhere: `text-sm text-ink-2` for a secondary sentence (`decision.tsx:53`, `response.tsx:136`), `text-xs text-ink-3` for captions. DESIGN.md:78: `ink-3` is for captions, never for anything the owner must act on, so an actionable sentence is `text-sm text-ink-2`.
- Other testids on the page: `cash-cheaper-option` (67), `cash-plan-detail` (71), `cash-sources` (94), `cash-options` (168, 173), `cash-chart` (178), `cash-whatif`/`cash-capex` (183, 186), `cash-readings` (192), `cash-readings-now` (196). `e2e/cash.spec.ts:27-34` asserts the four `dt`s of `cash-figures` and the texts inside `cash-headroom`; `e2e/colour.spec.ts:72-75` expects exactly 1 brand-filled control on `/cash` once `cash-forecast` is visible.
- Data: `home = useAsync(() => getHome(lang), [lang])` (32), `h = home.data`; `today = h?.day ?? 0` (50). The whole card is inside `home.error ? ErrorState : !h ? LoadingBlock : (...)` (106-110).

### 3. Receivables page and the home block

#### `app/receivables/page.tsx` (161 lines)
- Data: `recon = useAsync(getReconciliation, [])`, `books = useAsync(getState, [])`, `home = useAsync(() => getHome(lang), [lang])` (17-19). `data = recon.data` (ReconciliationView), `r = home.data?.receivables` (HomeReceivables). `name(id)` from books (22). Sort (24): `[...data.outstanding].sort((a,b) => Number(b.past_due) - Number(a.past_due) || a.due_day - b.due_day)` — late first, then by due day. The page counts days (`whenText`, `daysLate` from `lib/when.ts:8-20`), never money.
- Gate: `error ? ErrorState : !data || !r ? LoadingBlock rows={3} : ...` (30-34).
- Summary `<section id="recv-summary" data-testid="recv-summary">` (36-52): three `Stat`s with testids `recv-outstanding`, `recv-overdue`, `recv-next-amount`, `recv-next-hint`, and `recv-none` (51).
- Late-first table in `Card id="recv-open"` (55-102):
  - **Phone list** `<ul className="motion-rise divide-y divide-line sm:hidden" data-testid="recv-open-list">` (57-72). Each `<li>` (59-70): row 1 name + `face_display`; row 2 (`text-xs text-ink-3`) due `whenText(o.due_day, data.as_of_day)` + `Badge` late/on time. No per-row testid on the phone list.
  - **Desktop table** `<div className="hidden sm:block"><TableWrap><table className={tableCls}>` (73-101). Columns (78-81): `biz.buyer`, `biz.amount` (right), `biz.due`, `common.status`. Rows `<tr data-testid={`recv-${o.receivable_id}`} className={o.past_due ? "bg-bad-bg/40" : ""}>` (86); cells: name + `<span className="block font-mono text-xs ...">{receivable_id}</span>` (87-90), `face_display` (91), `whenText` (92), `Badge` (93-95).
  - Row shape: `OutstandingReceivable` (`lib/types.ts:1263-1271`): `receivable_id, counterparty_id, face_fen, face_display, due_day, status, past_due`. Not `HomeReceivable`; the home's `past_due` rows (`types.ts:1748-1759`) carry `buyer_name, due_when, days_late, invoice` instead.
  - **Adding a column + action cell**: add a `<th>` after `common.status` (81) and a `<td className={tdCls}>` after 95 keyed on `o.receivable_id`; on the phone list add a third line in the `<li>` (after 69). The action should be a text link / secondary `Button size="sm"` or `textLinkClass` (`ui.tsx:248`), not primary: `e2e/colour.spec.ts:74` expects **0** brand-filled controls on `/receivables`. `e2e/receivables.spec.ts:51-58` reads `#recv-open tbody tr` first row, its first `td` and `span.block`, so a new column appended at the end keeps those passing.
- Other cards: `recv-promised` (106-121, `promised-${receivable_id}` + `data-status`), `recv-receipts` (125-155, `receipt-${op_id}`, `receipt-audit-${op_id}`, `receipt-ref-${op_id}`).

#### `components/business/blocks.tsx` `ReceivablesBlock` (110-143)
- Props `{ r: HomeReceivables }`. `Card id="home-receivables"` titled `biz.receivables`, subtitle `biz.receivables.sub {total, n}`, action link `/receivables` with `textLinkClass` (118).
- Body `<div className="-my-1 divide-y divide-line">` (119): late list `<ul className="motion-rise divide-y divide-line" data-testid="home-late-list">` of `Row testId={`home-late-${x.receivable_id}`}` with avatar initials, `title={x.buyer_name}`, `sub={daysLate(x.days_late, t)}`, `tone="bad"`, `right={x.face_display}` (121-127); else `<p className="py-2.5 text-sm text-ink-3" data-testid="home-late-none">` (129-131). Then `Row testId="home-next-receipt"` (134) or the `home-next-receipt` empty `<p>` (136-138).
- One extra line would go either as a `<p className="py-2.5 text-sm text-ink-2">` sibling inside the `divide-y` div (after 139) or as `children` of the late `Row` (Row accepts `children` under the title, kit.tsx:108-135). `e2e/home.spec.ts:206-208` asserts `home-late-RCV-A` text on day 34.

### 4. Adding one GET endpoint end to end

- Client `lib/api.ts`: `API_MODE` import (12), lazy loaders `mock = () => import("./mock/handlers")`, `live = async () => (await import("./live")).live`, `isMock` (54-56). Pattern, quoted (153-156):
  ```ts
  /** GET /reconciliation (flag `alerts`): receipts in the log matched to receivables. */
  export async function getReconciliation(): Promise<ReconciliationView> {
    return isMock ? (await mock()).getReconciliation() : (await live()).getReconciliation();
  }
  ```
  `getAlerts` (148-151) is identical in shape. New types are added to the `import type {...} from "./types"` list (14-49).
- Live `lib/live/index.ts`: the `live` object (60-145). Passthrough: `getAlerts: () => http<AlertsView>("GET", "/alerts")` (99). Unwrapping adapter: `getReconciliation: async () => (await http<{ reconciliation: ReconciliationView }>("GET", "/reconciliation")).reconciliation` (103-104). `http(method, path, opts)` from `./http` (`lib/live/http.ts`; options `body, as, auth: "owner"|"none", buyerKey, token, silent, ownerOn403`, lines 9-22); default sends `X-Owner-Token` when signed in.
- Mock `lib/mock/handlers.ts`: JSON imported relatively, e.g. `import reconciliationJson from "../../mocks/reconciliation.json";` (72) — a file under `mocks/strategy/` would be `"../../mocks/strategy/<name>.json"` (`resolveJsonModule: true` in tsconfig). Helpers: `cast<T>(v)` (83), `clone` (JSON deep copy), `delay()` (MOCK_LATENCY_MS). Handler pattern (548-551):
  ```ts
  export async function getReconciliation(): Promise<ReconciliationView> {
    await delay();
    return clone(cast<ReconciliationView>(home.mockReconciliation() ?? reconciliationJson));
  }
  ```
  `getAlerts` (502-505) does the same with `home.mockAlerts() ?? clone(cast<AlertsView>(alertsJson))`. Clock-dependent swaps live in `lib/mock/home.ts` (`mockReconciliation` 149-151 returns the day-34 recording when `load().day >= NEWS_DAY`). Owner-gated reads check `getOwnerToken()` and throw `ApiError(401)` after `requestSignIn("required")` (handlers.ts:510-513).
- Types `lib/types.ts`: hand-written interfaces with a doc comment naming the route, e.g. `/** GET /reconciliation */ export interface ReconciliationView {...}` (1299-1316); `/** GET /alerts */ export interface AlertsView` (1213-1221). Rule (README.md:24-26): every `<name>_fen` has a sibling `<name>_display`; the web shows strings only.
- `useAsync(load, deps)` (`lib/use-async.ts:18-44`): returns `{ data, error, loading, reload }`; refetches when `deps` change, when the demo store `version` bumps, or on `reload()`; `loading = !settled`, `error` only when settled. Usage: `const recon = useAsync(getReconciliation, [])` (receivables 17), `useAsync(() => getHome(lang), [lang])` (cash 32), conditional load `useAsync(async () => (cond ? await planFunding() : null), [cond, ...])` (cash 47). Rendering idiom: `x.error ? <ErrorState error={x.error} onRetry={x.reload} /> : !x.data ? <LoadingBlock rows={n} /> : (...)` (cash 106-110, receivables 30-34); `LoadingBlock({ rows, label })` and `ErrorState({ error, onRetry })` from `components/ui.tsx:263, 275`.
- Build-time flags `lib/config.ts` (26 lines), all `NEXT_PUBLIC_*` read from `process.env` at module top level and inlined at build:
  ```ts
  export const API_MODE: ApiMode = process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "mock";   // 4
  export const DEMO_BUILD: boolean = process.env.NEXT_PUBLIC_DEMO === "1";                         // 17
  export const MOCK_LATENCY_MS: number = Number(process.env.NEXT_PUBLIC_MOCK_LATENCY_MS ?? 160);    // 10
  ```
  A new flag follows line 17: `export const STRATEGY_MVP: boolean = process.env.NEXT_PUBLIC_STRATEGY_MVP === "1";`. `next.config.mjs` notes NEXT_PUBLIC values are inlined at build time and `NEXT_DIST_DIR` separates builds; `playwright.config.ts:69-73, 94-98` is where the e2e builds' env is set (a flagged e2e build would add `NEXT_PUBLIC_STRATEGY_MVP: "1"` there or use a third dist dir). README.md:19, 45 documents the existing flags.

### 5. `scripts/record-mocks.mjs` (427 lines)

- Header (1-27): run instructions (API on :8011 with `TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1`), the NORMALISED list. `pnpm mocks:record` = `node scripts/record-mocks.mjs --api http://localhost:8011` (package.json).
- Args: `arg(name, fallback)` (37-40), `--help` (41-44), `API` and `OUT` (45-46, default `../mocks`), `OWNER_TOKEN = "demo-owner-token"`, `BANK` headers (47-48).
- Uses the app's own live client: `register("./ts-resolve-hook.mjs")`, sets `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_API_MODE=live`, then `await import("../lib/live/index.ts")` etc. (50-58). So a new live function in `lib/live/index.ts` is callable as `live.getX()` here with no extra plumbing.
- Writing: all recordings accumulate in `files[name] = value` (145), and at the end `for (const name of Object.keys(files).sort()) write(name, files[name])` (426). `write(name, value)` (124-127) = `writeFileSync(join(OUT, name), JSON.stringify(normalise(name, value), null, 2) + "\n")`. `normalise` (99-122) replaces `CMT-<16hex>`, `NL-<16hex>`, 32-hex `nonce`, and re-chains hashes for names in `RECHAIN` / `RECHAIN_BY_APPEARANCE` (65, 69). `mkdirSync(OUT, { recursive: true })` (60) makes only OUT; a `strategy/` subfolder needs its own mkdir (or `name = "strategy/x.json"` with a mkdir of `join(OUT, "strategy")`).
- Sequence: reset → opening books (147-164) → `DEMO_STEPS` walk with snapshots (166-208) → approval decisions (214-228) → typed offer (231-239) → what-if grid (242-266) → `toDay34()` home path (269-352) → chat conversations (363-422) → final `demoReset` (424).
- For a `--strategy` extension: add `const STRATEGY = process.argv.includes("--strategy")` beside 45; after the relevant book state (opening books at 148-155 for day 0, or inside `toDay34` for day 34) record `files["strategy/<a>.json"] = await live.getX()`; either gate the rest of the script off when `--strategy` is given (so only the three files are rewritten) or accept a full re-record.
- **Assertions that throw if the API's path changes** (would break with a feature flag that changes the demo books/alerts): `executed !== 2` on the day-0 fix (160); "no actionable reserve alert on day 34" (320-321); day-34 cure must be `PENDING_APPROVAL` (331); "go ahead" must queue an approval (358-359); nl script keys must match `KEY_ORDER` (420-421). Also `scripts/check-mocks.test.mjs` (run by `pnpm test:unit`) pins golden figures in `verdict_ex01.json`, `funding.json`, alerts/reconciliation (tests at 15, 30, 51, 78, 106); a re-record under different flags that moves those figures fails it. API flags: `services/api/app/config.py:32-52`, `_flag(name, default=True)` so every `FEATURE_*` is on unless set to 0; `/health` returns `features` (`main.py:51`). A new flag added there defaulting on changes nothing for the recorder unless it alters existing responses.

### 6. Dictionary (`lib/dictionary.ts`, 3202 lines)

- One `export const en = {...} as const` (6-1603), `export type DictKey = keyof typeof en` (1605), then `export const zh: Record<DictKey, string> = {...}` (1607-3202): every en key must also exist in zh or `tsc` fails. zh keys are in the same order and same section comments, roughly +1600 lines (e.g. `biz.cash.risk` en 1063 / zh 2662; `biz.recv.subtitle` en 1271 / zh 2870; `biz.headroom` 1088 / 2687; `biz.deals.compare` 1483 / 3082).
- Naming: Business-mode labels are `biz.<page>.<thing>[.<sub>]`: `biz.cash.risk`, `biz.cash.options.title`, `biz.cash.whySelected`, `biz.recv.open`, `biz.recv.open.sub`, `biz.recv.sum.outstanding`, `biz.recv.sum.next.hint`, `biz.deals.ask`, `biz.deals.response`, `biz.deals.send`, `biz.deals.option.recommended`; shared Business words are `biz.<word>` (`biz.buyer`, `biz.amount`, `biz.due`, `biz.headroom`); next-step copy is `next.*`; enum labels `prefix.VALUE` via `te()`. Placeholders `{name}`, plurals `{n|invoice|invoices}` (1279). `useI18n()` (`lib/i18n.ts:29-45`) gives `t(key, vars)` / `te(prefix, value)`; a missing zh value falls back to en at runtime, but the type requires the key.
- Suggested keys for the new cards: `biz.deals.before.*`, `biz.cash.strategy.*` (or `biz.cash.risk.note`), `biz.recv.worth.*` / `biz.recv.action.*`, `biz.receivables.worth` for the home line.

### 7. e2e (`e2e/`, `playwright.config.ts`)

- Specs: activity, alerts, approvals, cash, catchup, chat, colour, contract, deals, demo, home, live, receivables, responsive, screenshots, whatif (`.spec.ts`), plus `fixtures.ts` (signed-in `test`, `proseOf`) and `helpers.ts` (`runPlan`, `resetBooks`).
- Config: `MOCK_PORT = E2E_PORT ?? 3100`, `LIVE_PORT = E2E_LIVE_PORT ?? 3000`, `API_PORT = E2E_API_PORT ?? 8000` (14-16); `process.env.NEXT_PUBLIC_API_URL ??= http://localhost:${API_PORT}` (18); `target = E2E_TARGET ?? "all"`, `wantMock`/`wantLive` (19-21). Projects (35-60): `desktop` (Desktop Chrome 1440x900, `testIgnore /(live|contract)\.spec\.ts/`), `phone` (Pixel 7, `testMatch /(responsive|screenshots)\.spec\.ts/`), `live` (`testMatch /(demo|whatif|alerts|contract|live|chat)\.spec\.ts/`). webServer (61-102): mock = `pnpm build && pnpm start -p 3100` with env `NEXT_PUBLIC_API_MODE=mock, NEXT_PUBLIC_MOCK_LATENCY_MS=10, NEXT_DIST_DIR=.next-e2e-mock`; live = uvicorn on API_PORT + `pnpm build && pnpm start -p 3000` with `NEXT_DIST_DIR=.next-e2e-live`. `reducedMotion: "reduce"` (34). Scripts: `test:e2e`, `test:e2e:mock` (`E2E_TARGET=mock`), `test:e2e:live`.
- Env-gated spec example: `e2e/screenshots.spec.ts:14-15` — `const dir = process.env.SHOTS_DIR; test.skip(!dir, "set SHOTS_DIR to take the screenshots");` plus a per-project skip in `beforeEach` (`test.skip(testInfo.project.name === "live", ...)`, 20-22; same idiom in cash 12, receivables 11, colour 11, home 13). A strategy spec would gate with `test.skip(!process.env.E2E_STRATEGY, ...)` or, since the flag is build-time, on the built app's behaviour (e.g. `test.skip(await page.getByTestId("deal-before").count() === 0)`), and the mock webServer env would carry `NEXT_PUBLIC_STRATEGY_MVP`.
- Screenshot manifest pattern (17-46): `type Shot = { name, url, viewport, height, screens }`, `shots[]`; `shoot(page, name, project)` waits for `networkidle` + 300 ms, measures `scrollHeight`, writes `<SHOTS_DIR>/<project>/<name>.png` full-page and pushes a Shot; `test.afterAll` writes `<project>/manifest.json`. Three walks: day-0 Business pages (48-79, names `01-home-day0` … `11-activity-funded`), day 34 (81-106, `12`-`19`), Demo pages (108-130, `20`-`26`). New states would be appended as new `shoot` calls with the next numbers.
- Related assertions a new card must respect: `colour.spec.ts:70-91` counts brand-filled `main button, main a` per page: `/`=1, `/cash`=1, `/receivables`=0, `/activity`=0, Deals after evaluate=1 (`deal-send`); `deals.spec.ts:119-120` next-step link not `bg-brand-600`, `deal-send` is; `receivables.spec.ts:45` and `deals.spec.ts:38` forbid `/\bDay \d/` in Business prose (`proseOf` strips `<code>`); `responsive.spec.ts` forbids horizontal overflow on every Business route at phone width.

### 8. `DESIGN.md` rules binding a new card

- Fixed rules (line 5): "one brand-filled primary action per page; status colour only for status; … nothing said by colour alone; no gradients on buttons or cards; the browser computes no money; Business mode shows no engine terms and no day numbers."
- Colour roles (74-78): **brand** `brand-600`/`brand-700` = the page's one primary action, links, focus ring, selected toggle, "Never a status"; **status** `ok|warn|bad|info` with `-fg/-bg/-line/-solid/-bright` = "how things are going. Always with a word"; **section hues** `sec-home|sec-deals|sec-cash|sec-recv|sec-activity` with `bg/fg/solid` (classes `bg-sec-deals-bg text-sec-deals-fg`, `bg-sec-recv-solid`; tokens `globals.css:60-68`) = "where you are or where a link goes … Never how things are going"; **ink** `ink/ink-2/ink-3` = text, "`ink-3` is for captions, never for anything the owner must act on".
- Shape (82-90): `rounded-pill` (buttons, badges, chips, inputs), `rounded-card` 16px (cards, disclosure cards, tables), `rounded-tile` 12px ("what sits inside a card: fact tiles, list rows with a border, option rows, callouts"); shadows `shadow-card`, `shadow-lift`, `shadow-pop`; no gradients.
- Components (96-104): `Button` variants primary/secondary/ghost/danger, "**One primary per page**"; `ButtonLink` for a next-step link, `buttonClass()` for a span in a link; `Badge` (status, with dot) vs `Chip` (no status); `Card` "reveals on mount"; `Disclosure` (kit.tsx) is "the one fold … Use it instead of a hand-rolled `<details>`"; icons from `components/icons.tsx` only; never remove a focus outline.
- Motion (111-131): `motion-reveal` (a block on mount: `Card`, disclosure cards, next-step band), `motion-rise` on a list (rows stagger 30 ms, first eight), `motion-lift` (hover lift on rows/tiles/options), `motion-press` (buttons), `motion-pulse` only for ACTION_NEEDED/CRITICAL; transform and opacity only, "nothing animates width, height (but the disclosure), margin or position"; durations `--dur-fast` 120 ms, `--dur` 200 ms, `--dur-slow` 280 ms, `--ease-out`.
- Consequences for the three cards: Deals already spends its primary on `deal-send`, Cash on the next-action button, Receivables has none; so the Deals card's "open Option A/B" and the Receivables action cell must be a secondary `Button`, `textLinkClass` link, or ghost — never `variant="primary"`. A "worth collecting" figure is a server string shown in `tabular-nums`; any emphasis colour must be a status with a word, not a bare tint. Cards inside a card use `rounded-tile border border-line`; a standalone card is `Card` (`rounded-card`), gets `motion-reveal` for free, and lists inside take `motion-rise`.

