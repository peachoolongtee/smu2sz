# Home V2, fourth round: the worklist, three separate selections, the prototype (12 Oct 2026)

Owner's fourth review: keep the KPIs, one action, the compact chart; the right panel becomes a **worklist** (Needs you / Waiting /
Customers) of actions, not a customer directory; one customer with several negotiations appears once per decision; customer,
deal and scenario are three separate selections that persist across Deals and Cash; the company KPIs never change; no
sparklines (a buffer indicator where it tells something the number cannot); "Money expected" becomes "Next cash event"; the
chart states its scope; critical warnings persist while a customer is selected; a multi-deal case is designed and tested.

Prototype: `HomeV2Proto.dc.html` (canvas v22, interactive): the worklist rows, the breadcrumbs, the scenario buttons and the
before/after-plan toggle work. Extra buyers (Shenzhen Fixtures, Zhuhai Interiors) are illustrative; Foshan and Dongguan are
the demo's.

## Decisions taken from the review

- **KPIs:** Cash available (number, note, a thin buffer scale from the minimum: not a progress bar); Lowest cash ahead
  (current books, nothing run, with its distance from the minimum; the proposed plan's effect as a hint line, never as the
  figure); Next cash event (one event with its state word: "+¥150k proposed · if you run the plan" / "+¥255k · arranged,
  expected in 3 days" / "+¥163k estimated net collection · Foshan invoice, in 32 days"). No gross-plus-financing total.
- **Two dimensions on every worklist row:** who acts next (needs you amber; FLOW handling blue; waiting grey; completed green;
  blocked red only when material) and the cash impact as a sentence ("as asked, below your minimum for 15 days"; "without it,
  the reserve is breached in 3 days"). Never one badge for both.
- **Ordering:** deterministic rules, explained on the row ("Why first: cash falls below your minimum before any other item
  matters"): cash-safety first, then deadlines and expiring approvals, missed receipts, material consequences, ordinary replies;
  deadline as the tiebreaker. New items get a quiet "new" marker and the list reorders only when the owner is not reading it.
- **Three levels:** overview (open Home) → customer focus (the relationship summary and all its decisions; never a deal chosen
  silently) → decision focus (one deal, the recommendation, the cost, the incremental impact; "Open the full deal" keeps buyer,
  deal and counter). The three selections are URL state: `customer`, `deal`, `scenario`.
- **The chart's scope is always named:** COMPANY CASH FORECAST; … · FOSHAN EXPOSURE (receipt highlighted, no hypothetical);
  IMPACT OF FOSHAN'S PROPOSED TERMS (current books vs one hypothetical path, dashed); IF FOSHAN PAYS 30 DAYS LATE. Pending
  deals never enter the live forecast; each deal is compared against the current books on its own; a portfolio view, if ever,
  is an explicit "analyse these together" (the kill criterion stands).
- **Popups:** none for browsing; a drawer for secondary facts (an invoice, the financing breakdown, payment history); a modal
  only for consequential actions (send, approve, run), with exact terms.
- **Critical while a customer is selected:** a slim persistent red bar above the workspace with "Back to the action".
- **Calculating:** switching customers stays instant on cached relationship facts; a recommendation that needs re-checking is
  marked "last valid result, re-checking" until the server answers; nothing stale is shown as current.
- **Mobile:** KPIs, the action, the chart; a "Worklist (3)" button opening a searchable bottom sheet; selecting closes it and
  the workspace switches, with the relationship named near the top and "All business" to return. Tablet: a collapsible panel.
- **Motion:** row highlight 150–180 ms; workspace crossfade 180–220 ms; scenario path crossfade 250–350 ms with the figures
  updating together (never two scenarios' numbers at once); drawer 220–280 ms; modal 180–220 ms; status change only on the
  server's confirmation; no pulsing rows, no count-ups on switch.

## Component system (shared, no per-screen custom UI)

FinancialStatusHeader · FinancialMetricCard · CashBufferIndicator · CashForecastPreview (the #113 timeline's compact variant) ·
WorklistPanel · CustomerRow · ActionRow · CustomerFocusPanel · DealFocusPanel · ScenarioComparison · FinancialActionReview.

## Reads (nothing new beyond two small lists)

`GET /home` (KPIs, the action, the series, the basis words, the pending path); NEW `GET /worklist?lang=` (the attention
ranking the Home read already derives, extended to every open offer, approval, overdue invoice and blocked item, each with its
two dimensions and its "why first" sentence); NEW `GET /customers?lang=`; `GET /customers/{id}/overview`; `GET /offers/{id}`
and `/offers/{id}/exposure` (the deal focus and its scenarios); `GET /buyers/{id}/exposure` (the late-payment test).

## States to test before the swap

No pending decisions; one deal; five deals sorted; three deals from one customer; a buyer reply pending (nothing resendable);
an approval required; funding proposed; funding submitted (not shown as cash); a payment overdue; cash critical; a customer
selected during the crisis (the warning persists); a scenario still calculating. Desktop and 390 wide, en and zh, the figures
checked against Cash & Funding and the deal, and the five-second test.

## Round five (owner's fifth review, 12 Oct): the five targeted changes, in the prototype (canvas v23)

1. The chart legend renders as text, never markup; series labelled "Current books · no new funding" and "If FLOW's plan
   executes (proposed)" before the run, "Current books · the plan ran" after; the proposed line subordinate (grey dashed).
2. Counts are derived from the rows shown: Needs you = decisions only a person can take; Waiting = what FLOW waits for
   (buyers, banks, settlements, promises); Customers = relationships. The company cash alert is pinned above the tabs and
   counted nowhere ("an alert, not a queue item"). Illustrative rows say so and never contradict the company forecast.
3. The third KPI is PROPOSED FUNDING ¥405,000 (the two legs, "conditional on you running the plan; not counted as cash");
   after the run FUNDING ARRANGED with what landed and what is pending.
4. Three row shapes, one per tab: a decision row (subject · status with who acts · consequence or deadline, plus a
   severity word Critical / Caution / Normal separate from ownership); a waiting row (what FLOW waits for, since when, what
   follows); a customer row (negotiations, how many need you, outstanding, share). Clicking a customer opens the relationship;
   clicking a deal opens the decision; clicking the company alert restores the company analysis; "All business" returns.
5. A busy-worklist toggle: seven customers (Foshan with three negotiations, two needing decisions; Dongguan with a pending
   contract and an overdue invoice; an approval; a counter awaiting reply; a funding settlement pending; a payment promised for
   tomorrow; one with nothing), long names, Needs you 4 / Waiting 5 / Customers 7. The lowest point on the chart is clickable
   and shows: projected cash, the minimum, the shortfall, and "with FLOW's proposed plan: ¥300,000, assuming it executes".
   The six-event rail stays off Home. New items never reorder the list under the owner's selection.
