# Connected views: Deals queue, Receivables layers, Customer overview (plan, 12 Oct 2026)

Decision (owner's review, 12 Oct): keep all three concepts; build them in the review's order. Boards revised to the
review: canvas version 15 (DealsQueue, ReceivablesLayers, CustomerOverview). Nothing below is built yet; the Home
hybrid (sections 1–4) and the exposure API are in flight and come first.

## Architecture
Five tabs stay: Home | Deals | Cash & Funding | Receivables | Activity. Customer overview is a drill-down at
`/customers/{id}`, opened from any customer name, never a tab. Every page reads the SAME comparison: the exposure read
(`GET /offers/{id}/exposure`, one read for all paths: capacity before/after, concentration, payments, stress) is the
canonical scenario comparison; the Deals "Impact on your business" table, the Customer risk card and the Receivables
stress panel render it, none recomputes it (INVARIANT 13: no money or date words in the browser).

## Continuity (the review's §4)
A selection context travels in the URL and is echoed by the server: `customer`, `decision`, `path` (the picked path
key), `invoice`. Deals → Customer → "What if Foshan pays 30 days late?" opens `/business?stress=<buyer>:30&invoice=…`
with the series already loaded; the back link is server-built (`context.back {label, href}`) and restores the deal
with the picked path. The browser keeps nothing it cannot rebuild from the URL. Zero new state stores.

## P0 financial consistency (one function, every page)
1. **Stress on a financed invoice.** Today `scenario_paid_late` leaves a FINANCED invoice unmoved and says "its delay
   is not modelled" (impact.py:272, tests test_stress.py:239/250). The demo's ¥420k invoice IS financed, so the
   "Foshan 30 days late" test moves only the recurring invoices. Fix in the strategy layer (outside the stability set):
   move the financed receipt to due+delay on the copy and settle it through the engine's own `apply_receipt`
   (financial/lots.py:243), so the advance accrues its extra periods (`advance_charges(f, lot, day)`) and the lender is
   paid first; the shortfall, if any, stays owed by the owner (the engine's `orphaned` rule, i.e. recourse). New
   assumption text: "the advance runs N days longer: ¥X more in charges". Tests: the moved financed receipt, the extra
   charges, a receipt that no longer covers the claim, delay 0 reproduces the books.
2. **Estimated net cash at collection** = face − lender's claim on the due day (principal + charges to that day),
   computed once (strategy/collections or a small `net_at_collection(state, receivable, day)`), used by the
   Receivables layer 3, the invoice row, the Customer "financing exposure" line and the stress panel ("net to you, a
   month later"). Never "reaches your cash" as a promise: always "if paid on the due day".
3. **The advance as a liability.** Receivables shows the breakdown (face, − advance, − charges to the due day, = net)
   and one sentence from the facility's terms (per-period fee, interest, what happens on a short receipt). Read from
   the Facility record; no assumption that repayment moves with the receipt.
4. **Collection action by state** (server word `collection_action`): current → "View payment terms" / "Prepare a
   reminder"; due within 7 days → "Prepare a reminder" first; overdue or a promise missed → "Chase payment" first.
5. **Concentration said precisely**: "100% of what you are owed today (one invoice)", never blurred with the share of
   sales or of customers (the share of sales is a separate figure from `customer_inputs`, shown only when known).
6. **Total vs incremental value.** The contribution figure is labelled as what the customer brings under today's
   terms; the request's cost is "the cost of keeping the same sales on softer terms", not against the contribution as
   if it were gained by saying yes. One sentence on the deal and on the customer page.

## P1
- **Shared customer context**: `GET /customers/{id}/overview` composed from existing reads (inputs, receivables,
  funding lots, open decisions, activity, the exposure concentration and stress) → the five lines + three actions +
  the two detail cards + history. Every customer name in Deals, Receivables, Cash and Activity links to it with the
  context params.
- **Deals simplification**: the queue (four counts, the list, the detail) with the decision first and the customer
  compact; "Review and send the counter" binds the exact option and figures shown (the existing `counter_recheck`
  path: if the books moved, the new figures are shown and nothing is sent until the owner says so). The "Impact on
  your business" table from the exposure read (Today | As asked | Option A).
- **Receivables actionability**: the three layers, the net column, the breakdown, the state-driven action.
- **Customer scenario analysis**: the stress button on Customer and Receivables, the deep link into Cash with the
  series loaded, the Home scenario switch (`cash.stress`, already in the Home hybrid API spec).

## P2 motion (restrained)
Select a deal: expand in place, ~200 ms. Open a customer: push with the back context kept. Compare counters: the
columns cross-fade, ~250 ms. Test late payment: the stressed line draws and the new lowest point is highlighted,
~300 ms. Record payment: invoice balance, financing status and net cash update together, one announcement. Send
counter: Ready → Sent → Awaiting buyer, after confirmation only. Funding settles: Pending → Available, never
double-counted. Reduced motion: none of the above animates.

## Order
P0.1 (stress on the financed invoice) and P0.2 (net at collection) first, server only, one implementer, with their
tests; then the Customer overview read + page; then the Deals queue page (it needs the exposure read merged, flag on);
then Receivables. Mocks re-recorded after each server merge; code review + design review before each merge.

## Owner's calls still open
- Gross margin stays a Demo assumption (20%) until confirmed in Inputs.
- The share of sales per customer is unknown today; the concentration line says so rather than inventing one.
- Whether a late receipt on the financed invoice should also lapse the buyer's early-payment agreement (today: yes,
  the stress treats it as lapsed).

## Second review round (12 Oct, canvas v16)
Page purposes: Deals = what should we agree to (request, economics, recommendation, action); Receivables = what money are
we waiting for (outstanding, due, payments, net collection); Customer = what is this relationship worth and what risks
does it create (contribution, exposure, concentration, history); Cash = can we survive the consequences (forecast,
funding, alternatives); Activity = what actually happened. Share data and links; never repeat every calculation.
New P0 (on #107): financing states arranged / received / repaid never mixed; each receivable names the agreement that
governs it and a pending counter says which invoice and amount it would apply to; economic comparisons as separate rows
(one-off now; 12-month on the terms; financing cost caused; lowest cash; spare; limit; share), every counter outcome
worded "if <buyer> accepts", contribution as context only. P2: scenario comparison expected / 15 late / 30 late (that is
#100's comparator); supporting text 13 px minimum, no qualification in small text. P3 transitions.
Mockup fault fixed in v16: the "agreed two days ago" row had reused Option A's figures, so the same early settlement
looked both in force and pending; it is now the supply terms in force, and the invoice says no early payment is agreed.
The closed loop to demonstrate: deal → Why Foshan matters → Customer overview → Stress-test payment → back to the deal
with the counter kept.
