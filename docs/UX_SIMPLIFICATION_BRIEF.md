# FLOW simplification: execution brief

7 October 2026. The owner's fifth brief ("aggressively simplify") asked for this document before any large implementation (its section 46). It is the plan every wave of [wayfinder map #26](https://github.com/peachoolongtee/smu2sz/issues/26) works from. The baseline it reads from is `docs/screenshots/baseline-2026-10-07/` (desktop 1440 px and Pixel 7, every Business page in every state the recorded demo path reaches, plus the Demo pages; `manifest.json` in each folder holds the page heights), taken with `apps/web/e2e/screenshots.spec.ts`, which reruns after every wave. The truth research behind sections 1 to 3 is `docs/research/ux-truth-2026-10-07.md` on branch `research/ux-truth` ([ticket #27](https://github.com/peachoolongtee/smu2sz/issues/27)).

Rules in force: the engine is in stability mode and the browser computes no money (INVARIANT 13). Every fix below is a presentation read over results the engine already produces, or a change of words and layout. Nothing moves a verdict, a cure, an admission or a cost.

## 1. Which apparent contradictions are real

All four the brief names are real, and all four are presentation faults. Two more surfaced from the baseline.

| Apparent contradiction | Real? | Where it comes from | Smallest truthful fix |
|---|---|---|---|
| Deals: "Cannot run until the invoice is issued … issued on day 32" beside Requested day 0, Cash lands day 3 | Real, presentation | `verdict_ex01.json → plan`: one `FINANCE_INVOICE` on `RI:BUYER-1:32`, `day: 0`, `lands_day: 3`. `app/funding/router.py::_with_landing` reads the issue day from `search.state.receivables`; an expected recurring invoice is not on the books yet, so it falls back to the request day and `rates.invoice_landing_day` gives 0 + 3. The engine itself lands the advance on issue day + lead time (`financial/trajectory._finance_invoice`). The research confirms whether the plan's cost ¥2,406.67 is priced on the engine's day (expected: yes, the cost is computed by the trajectory, the stamp is display-only). | Stamp `lands_day` from the recurring schedule's issue day when the receivable is not yet booked, and add `available_from_day` / `available_from_when` to the plan and each leg. Business mode never shows a request day for a plan that cannot run today; it says "Funding available from <date>". A test asserts no fixture plan shows a leg requested or landing before its eligibility day. |
| Cash & funding: "You're covered. No funding is needed" above "Other options: every way to cover the gap" | Real, presentation | `apps/web/app/cash/page.tsx` renders the options card unconditionally from the decision-time snapshot (`demo.funding`) or a fresh `planFunding()`; `GET /home` already carries `next_action: null`, `in_transit`, and the lots behind `ensure_lots(state).lots`. | When `next_action` is null the page leads with the current funding position (active lots, in transit) and folds the comparison under "Other plans considered". |
| Cash & funding: "Credit line only ¥841.64" ranked #5 under "Cheapest committed plan ¥3,113.93" | Real, presentation | `funding.json → comparison`: `line_only` is `NOT_ADMISSIBLE`, `reasons: [RESERVE_BREACH]`, `breach_day: 12`; `line_guaranteed_loan` is `NOT_ADMISSIBLE`, "not applied; cash on day 21, gap opens on day 12". The web ranks every row `#n` and marks only a `—` cost as "Not possible" (`impossible = total_display === "—"`). | A presentation `status` per row (`recommended`, `alternative`, `dearer`, `insufficient`, `unavailable`) derived from `result`, `reasons`, `breach_day`, `executable_now`; rows grouped by status, numbered within the feasible group only; an insufficient row says what it leaves uncovered (the breach distance, and the shortfall if the research finds the router holds it); an unavailable row says from when. |
| Deals: Option B "Cost to the supplier ¥0.00" | Real, presentation | `app/verifier/counters.py::_price_adjustment_at`: `net = ext_v + price_v` (¥16,217.95 − ¥16,380.00 = −¥162.05), `supplier_cost_fen = max(0, net)`. The gross and the offset exist only inside the formula string. | Typed `cost_lines` on the counter view: funding cost of the extension, offset by the price adjustment, net economic cost; the card says "Net economic cost ≈ ¥0" with both lines, never "Cost ¥0.00". `supplier_cost_fen` unchanged. |
| Deals: unsafe in 47 days, cash ¥209,960 on day 47, lowest ¥164,960 on day 60 | Not a contradiction, under-labelled | `first_breach_day` 47 and `min_cash` / `min_cash_day` 60 are both on the verdict's trajectory view; the cash on the breach day is only inside the violation's observed value. | `first_breach_cash_display` beside `min_cash`; two named facts, "First breach" and "Worst point", wherever both show. |
| Home after funding: "Lowest cash ahead: ¥300k 34 days ago" | Real, presentation (found in the recorded day-34 answer) | `home_summary_after.json → worst`; `app/api/home.py::_headline` describes the lowest point of the series it reads. The research names the index. | Fix the day the sentence reads; when the lowest point is today, say "Cash sits on the reserve today". |
| Cash & funding, day 0: "Cannot run until the invoice is issued" on options #1 and #2 | Real, presentation (baseline) | The badge text is one fixed string (`plan.notExecutable`) for every `executable_now: false`; for the early-payment options the leg that cannot run is the buyer's early payment, which is not an executor operation and depends on the buyer. | The row carries the server's reason; the web shows "Needs the buyer to pay early" or "Available from <date>" from that reason, never the invoice sentence by default. |
| Cash forecast annotations "Advance on the ¥420 ¥255k", "Receipt the ¥420 ¥420k" | Real, presentation (baseline) | `cash-forecast.tsx` shortens the event label by truncating the server sentence; "¥420k" loses its "k". | Use the event's `amount_short` and a short label from the server (`label_short`) instead of truncation. |

Verified once, not yet twice: Option A's "funding the rest of the gap ¥841.57 (committed plan: ¥841.57)" on Deals against the line cost ¥841.64 on Cash & funding. The two are different plans (the line after an early payment on part of the invoice versus the line beside the full advance), so different repayment days are plausible. Wave 1's second-agent check covers it.

## 2. Which are presentation-only

Every row above. No engine value is wrong; the display either stamps a day from the wrong source, floors a net at zero without showing the gross, ranks rows that are not comparable, truncates a label, or leaves a fact unnamed. The brief's invariant "an operation cannot be shown as requested or settling before the executor would consider it eligible" is a display invariant and becomes a test in Wave 1.

## 3. Exact sources of the conflicting numbers

| Number | Source |
|---|---|
| ¥2,406.67, "cannot run today", issued on day 32 | `verdict_ex01.json → plan.label / not_executable_reason`; built by `router.py::plan` from `unrunnable_text`; the cure cost in `summary` ("curable at ¥2,406.67") |
| Requested day 0, lands day 3 | `plan.actions[0].day`, `.lands_day` via `router.py::_with_landing` and `rates.invoice_landing_day` |
| ¥3,113.93 = ¥841.64 + ¥2,272.29 | `funding.json → comparison[key=router_optimum].cost_display`, the same plan `GET /home` prices (`next_action.cost_total_display`) |
| ¥841.64 alone, breach on day 12 | `comparison[key=line_only]` (`cost_display`, `breach_day`, `note`) |
| ¥0.00 (Option B) | `counters[1].supplier_cost_display`; the gross ¥16,217.95 and offset −¥16,380.00 in `counters[1].formula` |
| ¥3,027.77 (Option A) | `counters[0].supplier_cost_display`; its formula: discount ¥2,186.20 + funding the rest ¥841.57 |
| 47 days, ¥209,960; 60 days, ¥164,960 | `trajectory.first_breach_day`; violation `RESERVE_BREACH.observed`; `trajectory.min_cash`, `.min_cash_day` |
| ¥28,326.92 against ¥5,000.00 | `forward_concession_total_display`, `forward_concession.cap_display` |
| "¥300k 34 days ago" | `home_summary_after.json → worst` from `home.py::_headline` |

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
- Comparison rows: `status` (`recommended | alternative | dearer | insufficient | unavailable`), `uncovered_text` (the breach distance and, if the router holds it, the shortfall), `available_from_when`, `reason_text` (the leg that cannot run, in words), `name` (the human plan name by key).
- Counter view: `cost_lines` (label, display, sign) and `net_cost_display` with `is_net: true`.
- Verdict trajectory view: `first_breach_cash_display`, `first_breach_when`, `worst_when`.
- `GET /home`: `headroom_display`, `lowest_headroom_display` (+ `_when`), `status_text` for the WATCH band ("Covered, but tight"), a corrected `worst` sentence; `in_transit` kept, plus `funding_lots` (amount, source, landed or lands when) for Cash & funding's current position.
- Changes and ledger entries: `event_text` (the business sentence), with the raw executor sentence kept as `message` for the audit disclosure.
- Verdict view: `business_action` (`accept | counter | decline | needs_owner | cannot`) beside `outcome`.

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
