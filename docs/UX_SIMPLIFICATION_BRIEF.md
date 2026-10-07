# FLOW simplification: execution brief

7 October 2026. The owner's fifth brief ("aggressively simplify") asked for this document before any large implementation (its section 46). It is the plan every wave of [wayfinder map #26](https://github.com/peachoolongtee/smu2sz/issues/26) works from. The baseline it reads from is `docs/screenshots/baseline-2026-10-07/` (desktop 1440 px and Pixel 7, every Business page in every state the recorded demo path reaches, plus the Demo pages; `manifest.json` in each folder holds the page heights), taken with `apps/web/e2e/screenshots.spec.ts`, which reruns after every wave. The truth research behind sections 1 to 3 is `docs/research/ux-truth-2026-10-07.md` on branch `research/ux-truth` ([ticket #27](https://github.com/peachoolongtee/smu2sz/issues/27)).

Rules in force: the engine is in stability mode and the browser computes no money (INVARIANT 13). Every fix below is a presentation read over results the engine already produces, or a change of words and layout. Nothing moves a verdict, a cure, an admission or a cost.

## 1. Which apparent contradictions are real

The truth research traced every number to code and to the recorded API answers, re-ran the engine on the golden scenario where needed, and measured the Deals page. Result: the brief's four contradictions are real, and all four are presentation faults. One more is a real mapping defect (the business action), and two more surfaced from the baseline.

| Apparent contradiction | Verdict | Where it comes from | Smallest truthful fix |
|---|---|---|---|
| Deals: "Cannot run until the invoice is issued … issued on day 32" beside Requested day 0, Cash lands day 3 | Presentation-only. The engine lands the advance on day 35 (issue day 32 + 3-day lead) and prices ¥2,406.67 on days 35 to 92, the "57 days billed as 2 × 30-day period" in the cost formula. Only the display stamp is wrong. | `verdict_ex01.json → plan.actions[0]` (`day: 0`, `lands_day: 3`). `app/funding/router.py::_with_landing` looks the receivable up in `search.state.receivables`; the recurring invoice `RI:BUYER-1:32` exists only in `search.rcvs`, so the issue day falls back to the request day. `FundingAction.lands_day` is documented display-only; the pricing path (`search.py::action_pricing`) uses `search.rcvs` and gets 35. `day: 0` is the day the router priced the plan on, not a day anything happens. | `_with_landing` reads `search.rcvs` (a display stamp in the router file; no figure or test reads it, so it is within stability mode). Add `available_from_day` / `available_from_when` to the plan and each leg; Business mode says "Funding available from <date>, once the invoice is issued; cash arrives <date>; nothing to run today". A test asserts, on every fixture plan, that no leg is shown requested or landing before its eligibility day. |
| Cash & funding: "You're covered. No funding is needed" above "Other options: every way to cover the gap" | Presentation-only | `apps/web/app/cash/page.tsx` renders the options card unconditionally from the decision-time snapshot or a fresh plan. `GET /home` already carries `next_action: null`, `cash.in_transit` (lots not yet settled, with `arrival_when`), `facilities[]` with drawn and available per facility, and `changes[]` with a LANDED item per lot; `GET /state` carries `state.lots` (principal, request day, arrival day, settled). | When `next_action` is null the page leads with the current funding position (drawn per facility, lots in transit) and folds the comparison under "Other plans considered". |
| Cash & funding: "Credit line only ¥841.64" ranked #5 under "Cheapest committed plan ¥3,113.93" | Presentation-only, but the uncovered amount is not on the row | `funding.json → comparison`: `line_only` is `NOT_ADMISSIBLE` with `reasons: [RESERVE_BREACH]`, `breach_day: 12`; `line_guaranteed_loan` is `NOT_ADMISSIBLE` with `UNCOMMITTED_FACILITY`, `LEAD_TIME_TOO_LONG` and the note "not applied; cash on day 21, gap opens on day 12". The router's `Eval.shortfall` (the deepest shortfall: ¥255,000 on day 30 for line only) is dropped by `router.py::_row`. `executable_now` is true on the unavailable row only because it has no evaluation; read it on admissible rows only. The web ranks every row `#n` and marks only a `—` cost as "Not possible". | `shortfall_fen` on `ComparisonRow` from `ev.shortfall` (`displayed()` yields `shortfall_display`); a presentation `status` (`recommended`, `alternative`, `dearer`, `insufficient`, `unavailable`) from `result` and `reasons`; rows grouped by status and numbered within the feasible group only; an insufficient row says "breaks the reserve in 12 days; ¥255k short at worst"; an unavailable row says from when. |
| Deals: Option B "Cost to the supplier ¥0.00" | Presentation-only, the parts untyped | `app/verifier/counters.py::_price_adjustment_at`: `net = ext_v + price_v` (¥16,217.95 − ¥16,380.00 = −¥162.05), `supplier_cost_fen = max(0, net)` on purpose. The parts live only in the formula string; `CounterProposal` carries `supplier_cost_fen`, `forward_value_fen`, `rationale`, `formula`. Re-running `value_concessions` on the counter's obligations gives the two parts exactly. | Per-counter `components` (obligation id, type, value) and `net_fen` in the verdict view, from `value_concessions` on the counter's obligations; `supplier_cost_fen` unchanged. The card says "Net economic cost ≈ ¥0 · Funding cost of the longer terms ¥16,217.95 · Offset by the 0.30% price adjustment ¥16,380", and "the price adjustment covers the cost of the longer terms". It does not claim a gain: the floor at zero is the verifier's deliberate reading. |
| Deals: unsafe in 47 days, cash ¥209,960 on day 47, lowest ¥164,960 on day 60 | Not a contradiction, under-labelled | `trajectory.first_breach_day` 47; cash on day 47 is in `violations[RESERVE_BREACH].observed` and in `trajectory.days[47]`, not as a trajectory-level field; `min_cash` / `min_cash_day` 60. The Deals page prints both without saying they are two days. | `first_breach_cash` on `TrajectoryView`; two named facts, "First breach" and "Worst point", wherever both show. |
| Home after funding: "Lowest cash ahead: ¥300k 34 days ago" | Presentation-only | `home.py::_headline` reads `traj.min_cash_day` over the whole absolute series (days 0..154); the closed days 0..33 hold the opening ¥300k, equal to the minimum, so day 0 wins and reads "34 days ago". `_after_words` and `after_lowest` already restrict to `d.day >= today`. | The lowest point over `d.day >= today` feeds `cash.lowest_*` and `worst`: "Lowest cash ahead: ¥300k today". |
| Deals: REJECT shown as "Decline, and counter" | Real mapping defect | `app/deals/page.tsx::recommendationKey` maps REJECT to "Decline, and counter" regardless of `counters.length`. REJECT with no counters is reachable from the Business inbox (the FastCapital message `verdict_sec.json`, and EX06, EX09 in the fixtures). The raw code shows on deal list rows (`OutcomeBadge`), the Why disclosure, the chat and the security page. | A server `business_action` (`accept`, `counter`, `decline`, `needs_owner`, `cannot`) keyed on outcome and counters; rows show the action words; a REJECT without counters reads "Decline" with "Nothing we could offer back stays within your limits"; the badge lives only inside disclosures and Demo views. |
| Cash & funding, day 0: "Cannot run until the invoice is issued" on the early-payment options | Presentation-only (baseline) | One fixed string (`plan.notExecutable`) for every `executable_now: false`; on these rows the leg that cannot run is the buyer's early payment, which is not an executor operation. | The row carries the server's reason in words ("needs the buyer to pay early"); the invoice sentence appears only when an invoice is the reason. |
| Cash forecast annotations "Advance on the ¥420 ¥255k", "Receipt the ¥420 ¥420k" | Presentation-only (baseline) | `cash-forecast.tsx` truncates the server sentence to make a label. | A short server `label` per event beside `amount_short`; no truncation. |

Verified once, not yet twice: Option A's "funding the rest of the gap ¥841.57 (committed plan: ¥841.57)" on Deals against the line cost ¥841.64 on Cash & funding. The two are different plans (the line after an early payment on part of the invoice versus the line beside the full advance), so different repayment days are plausible. Wave 1's second-agent check covers it.

Decisions taken here under the brief's section 45, on the research's open questions: the `_with_landing` stamp may change (display-only, documented as such); an insufficient row states the deepest shortfall and the breach distance; Option B reads "costs you nothing over the year" with both lines, never "a gain"; a REJECT without counters reads "Decline" with the no-offer sentence; the inbox collapses to the current message once one is shown; counter texts and rationales pass through `relative_days` in the Business verdict view (Wave 4).

## 2. Which are presentation-only

Every row above except the mapping defect, which is a web-side rule and also presentation. No engine value is wrong; the display stamps a day from the wrong source, floors a net at zero without showing the parts, ranks rows that are not comparable, reads a minimum over closed days, truncates a label, or leaves a fact unnamed. The brief's invariant "an operation cannot be shown as requested or settling before the executor would consider it eligible" is a display invariant and becomes a test in Wave 1.

## 3. Exact sources of the conflicting numbers

| Number | Source |
|---|---|
| ¥2,406.67, "cannot run today", issued on day 32 | `verdict_ex01.json → plan.label / not_executable_reason`; built by `router.py::plan` from `unrunnable_text`; priced by `trajectory._finance_invoice` on days 35 to 92; also `summary` ("curable at ¥2,406.67") |
| Requested day 0, lands day 3 | `plan.actions[0].day` (the pricing day), `.lands_day` via `router.py::_with_landing` falling back to the request day |
| ¥3,113.93 = ¥841.64 + ¥2,272.29 | `funding.json → comparison[key=router_optimum].cost_display`, the same plan `GET /home` prices (`next_action.cost_total_display`) |
| ¥841.64 alone, breach on day 12; ¥255,000 deepest shortfall on day 30 | `comparison[key=line_only]` (`cost_display`, `breach_day`, `note`); `Eval.shortfall`, not yet on the row |
| ¥0.00 (Option B) | `counters[1].supplier_cost_display` = `max(0, net)`; ¥16,217.95 and −¥16,380.00 from `value_concessions` on the counter's obligations, today only inside `counters[1].formula` |
| ¥3,027.77 (Option A) | `counters[0].supplier_cost_display`; its formula: discount ¥2,186.20 + funding the rest ¥841.57 |
| 47 days, ¥209,960; 60 days, ¥164,960 | `trajectory.first_breach_day`; `violations[RESERVE_BREACH].observed` and `trajectory.days[47].closing`; `trajectory.min_cash`, `.min_cash_day` |
| ¥28,326.92 against ¥5,000.00 | `forward_concession_total_display`, `forward_concession.cap_display` |
| "¥300k 34 days ago" | `home_summary_after.json → worst`, `cash.lowest_day: 0`, from `home.py::_headline` over the absolute series |
| 2.82 screens | `document.body.scrollHeight` 2,540 px at 1440×900 on the evaluated EX01 deal, disclosures closed (5.85 open) |

## 4. The simplified Deals hierarchy

Baseline: the evaluated deal is 2.8 desktop screens (2,540 px) and 5.5 phone screens. The buyer's ask is presented three times (the ask card, the consequence headline, the glance column), the cash breach three times, the concession three times, the counter three times (the consequence card, the glance column, the counter cards). Formulas (`d/(1−d)`, "smallest whole-5bp rate") are visible without opening anything. The primary label is "Decline, and counter" over a REJECT tone, and the footer says "Checks: 4 failed, 4 held".

Target: one to two desktop screens, in this order (levels of the disclosure standard in brackets).

1. **Deal header [1]**: the buyer's name, when the message came, where from; the stepper as one quiet line ("Received · Analysed · **Respond** · Agreed") once the agent's stages are done.
2. **Buyer is asking for [1]**: three human lines from the typed obligations ("1.2% discount for paying this invoice early", "45 → 60 day payment terms going forward", "1% rebate on next quarter's purchases"), "View parsed terms" behind a disclosure.
3. **Business action [1 to 3]**: "Counter recommended" (or Accept, Needs your approval, Can't evaluate yet) as the label; under it the three numbers: 12-month cost of concessions ¥28.3k against your ¥5k limit; first reserve breach (date, cash); worst point (date, cash); plus one sentence when the early-payment discount is dearer than funding.
4. **Recommended response [2, 3]**: Option A as a business card (what changes for the buyer, estimated cost, "Send this counter", "Details"); "Compare another option" reveals Option B with its net economic cost, gross funding cost and offset.
5. **Why FLOW recommends this [4]**: the three reasons that matter in owner words, "Show all checks" behind it (the four violations with observed and limit, the four held checks).
6. **Original buyer message [4]**, **Detailed calculations [5]** (interpretation first, formula behind), **Engine view [6]** as closed disclosures.
7. **Active commitments** only when any exist; otherwise absent.

Each fact appears once at level 1 to 3 and once more at most in the evidence.

## 5. What is removed from Deals (Business mode)

- The "Messages in this session" card: the inbox is the one list; messages from one buyer form one thread.
- The FastCapital message from the Business inbox (owner decision, ticket #28): it stays a Demo scenario; Business Deals shows one line, "1 suspicious message was blocked", linking to Activity's refused section.
- The "Simulated inbox" title and the WeChat/email/portal explanation: "Inbox" in Business, the explanation moves to Demo.
- The consequence card (its three facts move into the business-action block).
- The Verdict glance's three columns at level 1 (the ask is already above; the reasons become the "Why" disclosure; the offers become the counter cards).
- The "N failed, N held" count.
- Formula blocks and "Priced from" at level 1 on the counter cards.
- The "Why this / Show the calculation / Original message" trio at the page's foot as separate cards: they become the ordered disclosures of section 4.
- The raw outcome badge (REJECT) from the inbox rows and the page; it lives in the technical summary.

## 6. The Cash & funding hierarchy

Before funding (day 0; day 34):

1. **Cash risk [1]**: the headline and note as today, plus headroom (available today, lowest forecast) as server strings.
2. **Recommended plan [2, 3]** under its human name ("Credit line + invoice financing · Recommended · cheapest plan that fully protects your cash"), the components, cost, when funds land, who decides, "Run funding plan".
3. **Other plans [3]**, grouped: Alternatives (full protection, dearer), Insufficient (what it leaves uncovered and when), Not currently available (from when). No numbers across groups.
4. **Forecast [3]** with corrected annotations.
5. What-if and equipment doors, debt readings closed, as now.

After funding ran or was approved:

1. **You're covered [1]**: headline and headroom; "No additional funding is needed."
2. **Current funding [1 to 3]**: each lot with its amount, source and landing ("¥150k credit line · received today", "¥255k invoice financing · arrives in 3 days"), from the lots and `in_transit`.
3. **Why this plan was selected** and **Other plans considered** as closed disclosures holding the decision-time comparison.
4. Forecast and the doors.

The page never says "no funding is needed" and "ways to cover the gap" together.

## 7. Copy and terminology changes

| Today | After | Where |
|---|---|---|
| Decline, and counter / REJECT | Counter recommended (business action); "Engine verdict: REJECT" at level 4 | Deals |
| Immediate discount 1.20% · One-off | 1.2% discount for paying this invoice early | Deals ask |
| Terms extension Recurring, no end date | 45 → 60 day payment terms going forward | Deals ask |
| Contingent rebate 1.00% · One-off · counted at maximum | 1% rebate on next quarter's purchases | Deals ask |
| Given to the buyer over 12 months | 12-month cost of concessions | Deals, Activity |
| unsafe in 47 days · lowest cash ¥164,960 in 60 days | First breach: 23 Nov, cash falls to ¥209,960 · Worst point: 6 Dec, ¥164,960 | Deals, Cash |
| Checks: 4 failed, 4 held | (removed; "Why FLOW recommends this" with three reasons, "Show all checks") | Deals |
| Cost to the supplier ¥0.00 | Net economic cost ≈ ¥0 · Funding cost ¥16,218 · Offset by price adjustment ¥16,380 | Counters |
| committed plan: ¥2,406.67 (cannot run today) | Funding available from 8 Nov (once the invoice is issued), ¥2,406.67 | Deals plan, Cash |
| Cheapest committed plan | Credit line + invoice financing · Recommended | Cash options |
| Other options: every way to cover the gap | Other plans (grouped by status) / Other plans considered | Cash |
| #1 … #5 | Recommended / Alternative / More expensive / Insufficient / Not currently available | Cash |
| Cannot run until the invoice is issued (on an early-payment option) | Needs the buyer to pay early | Cash |
| Watch (with "You're covered.") | Covered, but tight | Home, Cash |
| ¥255,000.00 on its way | ¥255k funding arriving in 3 days | Home |
| Advance ¥200,000.00 on RI:… from Invoice financing … on day 34; the cash lands on day 37 … | ¥200k invoice financing approved. Funds arrive in 3 days. (details behind the event) | Recent changes, Activity |
| Queued for owner approval (APR-000001): effective annual cost 32.52% is above the mandate's 15.00% ceiling for what the agent may borrow alone … | Waiting for your approval: ¥200k invoice financing at 32.5% a year, above the 15% limit you signed. | Recent changes, Activity, the agent's answer block |
| Simulated inbox | Inbox | Deals |
| Ask the agent | Ask FLOW | shell |
| Read the offer · Check it · Respond · Agreed | Received · Analysed · Respond · Agreed | Deals stepper |
| Day N anywhere in Business mode (plan card, badges, counter text "on or before day 2") | distances or dates | Deals, Cash, Activity, Approvals |

Chinese strings follow for every new key.

## 8. Required backend presentation fields

All on reads that already exist, all strings or small enums, none read by the engine.

- Funding plan and legs (`FundingPlan`, `FundingAction` views): `available_from_day`, `available_from_when`, and a corrected `lands_day` for an advance on an invoice not yet booked.
- Comparison rows: `shortfall_fen` from `Eval.shortfall` (so `shortfall_display`), `status` (`recommended | alternative | dearer | insufficient | unavailable`), `uncovered_text` (the breach distance and the deepest shortfall), `available_from_when`, `reason_text` (the leg that cannot run, in words), `name` (the human plan name by key).
- Counter view: `components` (obligation id, type, value display) and `net_display` from `value_concessions` on the counter's obligations, with `is_net: true`; `supplier_cost_fen` unchanged.
- Verdict trajectory view: `first_breach_cash` (so `first_breach_cash_display`), `first_breach_when`, `worst_when`.
- `GET /home`: `headroom_display`, `lowest_headroom_display` (+ `_when`), `status_text` for the WATCH band ("Covered, but tight"), a corrected `worst` sentence; `in_transit` kept, plus `funding_lots` (amount, source, landed or lands when) for Cash & funding's current position.
- Changes and ledger entries: `event_text` (the business sentence), with the raw executor sentence kept as `message` for the audit disclosure.
- Verdict view: `business_action` (`accept | counter | decline | needs_owner | cannot`) beside `outcome`, keyed on the outcome and whether counters exist.

## 9. Files likely to change

Backend (presentation only): `services/api/app/api/presentation.py`, `app/api/home.py`, `app/api/views.py` (verdict and counter views), `app/api/decide.py` (the funding comparison view), `app/funding/router.py::_with_landing` (display stamp), `app/funding/recommend.py` (plan names), tests under `services/api/tests/api/`.

Web: `apps/web/app/deals/page.tsx`, `components/deals/*.tsx` (inbox list, steps, glance replaced), `components/verdict-parts.tsx` (counter cards), `components/plan-card.tsx`, `app/cash/page.tsx`, `components/business/cash-forecast.tsx`, `components/business/next-action.tsx`, `components/business/status-block.tsx`, `app/page.tsx` (headroom), `app/activity/page.tsx`, `components/app-shell.tsx` (Ask FLOW, account menu), `lib/dictionary.ts`, `lib/types.ts`, the e2e specs (`deals`, `cash`, `home`, `activity`, `responsive`, `screenshots`), and the mocks (re-recorded, never hand-edited).

Documents: `docs/UX_AUDIT.md`, `docs/HANDOVER.md` section 6, `apps/web/README.md`, `CONTEXT.md` (done), and the final `docs/UX_SIMPLIFICATION_REPORT.md`.

## 10. Implementation waves

As charted on map #26, one ticket per wave, each merged into `dev` with `--no-ff` after the integration loop:

| Wave | Ticket | Scope | Depends on |
|---|---|---|---|
| 0 | #29 | This brief and the baseline | #27 research |
| 1 | #30 | Truth: eligibility timing, option status, gross versus net, first breach versus worst point, the "ago" sentence, the semantic tests | 0 |
| 2 | #31 | Deals information architecture in one to two screens | 1, owner decisions #28 |
| 3 | #32 | Recommendation and counters as business cards | 2 |
| 4 | #33 | Business temporal language in the remaining places | 1 |
| 5 | #34 | Cash & funding: current position, grouped options, human names | 1, #28 |
| 6 | #35 | Business events, Ask FLOW, header, Receivables | 4, #28 |
| 7 | #36 | Responsive and regression pass, cold-user test, review, gate, final report | 3, 5, 6 |

Screenshots are retaken after every wave with the same spec and reviewed by the questions of the brief's section 44 before the ticket closes.
