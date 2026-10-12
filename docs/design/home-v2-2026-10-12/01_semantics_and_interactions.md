# Home V2, third cut: the four semantics settled, the drill-downs and the motion (12 Oct 2026)

The owner's third review: keep the three KPIs, one action, the compact chart and the customer selector; the cash-composition and
headroom panels leave the default Home for Cash & Funding; the selector is compact rows; customer mode shows the relationship
value, one recommendation and one cash-impact comparison, with the stress hidden until asked; critical emphasises, healthy shows
less; semantics before animation; nothing removed from the workspaces. Boards: canvas v21.

## 1. Semantics, settled before any motion

1. **Money expected** = every receipt and financing landing inside the window, each with its basis word, summed once:
   owed (an issued invoice; "owed: invoiced 13 days ago, due in 32 days"), scheduled (a recurring billing not yet invoiced),
   arranged (financing the plan has run; lands on its day), planned (financing the plan proposes; counted only if the plan runs,
   and the KPI's note says so). Never an expected order, never a pending deal's receipt. Overdue stays in the figure with the
   word "overdue by N days". (#116 `basis`, #111 `planned`.)
2. **Proposed vs executed funding**: planned (the plan is ready, nothing has run), arranged (run, not landed), received (landed),
   repaid. One vocabulary (`state_of` + PLANNED), the same word on the KPI note, the chart legend ("If you run FLOW's plan" /
   "With FLOW's plan"), the action bar and Cash. A planned landing never reads as money you have.
3. **Gross receivables vs net collection**: "owes you ¥420,000" is gross and is the figure in Money expected; "about ¥163k
   becomes available cash at collection, after the financing is repaid" is net and appears only beside a financed invoice, never
   in a KPI. The phrase is always "at collection, if paid on the due day".
4. **Current vs hypothetical**: the KPIs and the solid plan line are current (the books plus the plan as it stands). Everything
   conditional on a buyer's choice or a test carries the HYPOTHETICAL tag and a dashed line: "if Foshan accepts Option A",
   "if Foshan pays 30 days late". A hypothetical never changes a KPI; it changes a comparison card and a dashed line only.

## 2. Drill-downs (each opens in place, keeps the URL context, and never leaves Home unless it says so)

| Where | Gesture | What opens | Read |
| --- | --- | --- | --- |
| Cash available | click | a drawer "Where the cash goes": money in and out by kind for the window, the net; "Full detail in Cash & Funding ›" | the Home read's `cash.flows` (new, additive) |
| Lowest forecast cash | click | the chart scrolls into view and the low point pulses once; the cause and the effect rows show under the chart; the action bar is highlighted if it is the fix | `cash.lowest_*`, the cause event, `effect_rows` |
| Money expected | click | a drawer listing each item with its basis word and day, grouped owed / scheduled / arranged / planned, with the net-at-collection line on financed invoices | `cash.events_rail` receipts with `basis` |
| The chart | hover / tap a day | the tooltip: cash before, after, the room above the minimum, the event | `effect_rows` |
| The chart | click the low point | the same inspector pinned, with "What would fix it ›" pointing at the action | as above |
| The chart legend | click "If you do nothing" | the comparator line fades in or out (crossfade 220 ms) | `counterfactual_series` |
| The action bar | the primary | the existing confirm, then the run; the status word moves Ready → Running → Arranged only on the server's answer; Money expected and its note update on the same answer | `next_action`, `usePlanRun` |
| A customer row | click / Enter | the left column crossfades to that customer (200 ms); the KPI strip does not move, which is the cue that it is company-wide | `/customers/{id}/overview`, the exposure read |
| A customer row | hover / focus | the receipt belonging to that customer is highlighted on the chart (a ring, one pulse); leaving clears | `events_rail[].ref` |
| The comparison card | "Show the late-payment test" | the card extends with the stressed figures and the dashed red line is drawn on the chart (300 ms, interruptible); "Explore in Cash ›" carries `from=home` | `/buyers/{id}/exposure` |
| Any customer name | click | the Customer overview page with context | existing |
| The link row | click | the Cash & Funding sections (where the cash goes, headroom, the ageing strip, the full timeline), each with a back link | existing + `cash.flows` |
| Keyboard | ↑ ↓ in the rows | moves the selection; the chart highlight follows; Enter opens; Esc returns to "Your company" | |

## 3. Motion, from the #112 tokens (reduced motion: opacity only)

- Row selection and the left-column swap: 200 ms crossfade; the KPI strip is static.
- Chart comparator and hypothetical lines: 220–300 ms draw or fade; never a morph between two cash values.
- The low-point pulse and the row-to-chart highlight: one 400 ms ring, no bounce.
- Drawers: 240 ms slide from the card, focus moved inside, Esc closes, focus returns.
- Status transitions on the action bar: 220 ms, only on the server's confirmation.
- Value changes on a KPI after a confirmed action: a 300 ms tabular-numeral transition; never on load.
- Nothing else moves. No decorative motion on cards.

## 4. The five-second test (cold user, desktop and 390 wide)

Within five seconds, a reader who has never seen FLOW answers three questions from the default Home: "Is my cash all right?"
(the status word and the lowest KPI's colour), "What should I do?" (the action bar's one sentence and one button), and "Who
matters right now?" (the amber row on top of the customers). The critical state must answer the first two in the first
viewport at 390 wide; the healthy state must answer them with no filled button on the page. Verified on each of the four states,
in both languages, with the canonical figures checked against Cash & Funding and the deal (the same strings).
