# Home in the mockup language, round four (owner, 13 Oct 2026, after seeing dev 5a9f55d2 on the busy books, live)

Owner: "where are the pie charts I requested; the worklist has no alignment and no proper information hierarchy; in What we
recommend put the buttons at the bottom; is there any way to make use of the remaining real estate of the gap". The lead
looked at the same page (busy books, 1440): the recommendation card has its buttons mid-card with empty space under them and
its consequence sentence truncated with an ellipsis; the worklist's Next step column wraps to five lines on the lapsed Foshan
rows so no two rows align; no pie appears until a deal with an `ask_breakdown` is selected; and the "FLOW action ready" row
still shows beside the recommendation card (round three's section 5 keyed the row to funding state NONE, which the busy books
have WITH a card: the rule was wrong).

## 1. The pies the owner asked for (round two's words: "clicking a worklist row changes the cash available today and the other
## cards to pie charts with animations and clickable breakdowns, and always a clear way back")
On ANY selection (deal, invoice or customer) the two side cards become donuts; the overview comes back with Dismiss, Back to
overview, Escape and browser Back exactly as today. Every slice is a server row (label, amount word, share word); the browser
computes no share.
- **Cash available today → the cash donut.** Centre: the cash figure. Slices: the server's `kpis.cash_available.composition[]`
  (server words batch 9: `[{key: "reserve"|"buffer"|"shortfall", label, amount_display, share_text, note}]`, reserve
  ¥300,000 / 75%, buffer ¥100,000 / 25%; when cash is below the minimum the slices are cash and the shortfall). Slice or legend
  row click highlights both and shows `note` under the donut ("Your minimum reserve; FLOW never plans below it."); second click
  clears. Draws in over 300 ms on first paint; none under reduced motion.
- **Company cash outlook → "What you are owed, by customer".** For a deal or customer selection the outlook card becomes a donut
  of the customers' outstanding receivables from `GET /customers` rows (`name`, `outstanding_display`, `share_text`; the server
  already sends "19.5% of what you are owed"), the selected customer's slice lifted 4 px and labelled in the centre
  ("Zhuhai · ¥150,000 · 19.5%"); other slices clickable: a click SELECTS that customer (the address changes, the cards follow).
  For an invoice selection the same donut with the invoice's customer lifted. The deal's own cash impact (as asked vs
  recommended, round two's deal mode of the outlook) moves INTO the Deal context panel as its first block, with the same
  mini chart, so nothing is lost.
- **The selected card** keeps its own donut (the ask breakdown for a deal, the invoice breakdown for an invoice); a customer
  selection's card shows the customer's negotiations as rows (no third pie).
- Legend rows under each donut: dot, label, amount at the right, share word muted; 13 px; the rows are buttons (keyboard
  reachable, `aria-pressed`).

## 2. The worklist is a table with a hierarchy
- Three fixed columns at ≥ lg: Customer · deal 36%, Next step 44%, Status 20% right-aligned; row height 56 px, never more;
  Next step is ONE line, truncated with an ellipsis, the whole sentence in `title` and read aloud, and the selected card says
  it in full. Below lg: two lines (subject + status on the first, next step on the second), still 64 px fixed.
- Hierarchy per row: subject 15 px semibold ink; the quoted differentiator 13 px muted after it; Next step 13 px muted; the
  pill at the right, never moving when "Select →" appears: the affordance has its own 72 px column at ≥ lg (hidden below).
- Under "All", group headings in the table: "Needs you (6)", "Waiting (2)" as 12 px uppercase section rows (allowed: not a
  financial qualifier), the Customers tab unchanged.
- The server's long lapsed sentence ("This offer can no longer be drawn…") leaves the rows with Slice B's fix (those decisions
  leave the queue); until then it truncates like any other.

## 3. The recommendation card: buttons at the bottom, the gap used
- The card is a flex column; the ActionGroup is pinned to the bottom (`mt-auto`), the quiet approval row directly above it.
- The consequence sentence is never truncated: up to two lines at 14 px (the card grows; the three-card row's 260 px cap
  becomes "the tallest card decides, ≤ 300 px").
- The space between the facts row and the buttons shows the funding composition INLINE, no disclosure: one thin stacked bar of
  the plan's legs (widths from `legs[].amount_fen`, labels `legs[].label` + `amount_display`, `lands_when`, `share_text`
  from the server), the total at the right end; for a single-leg plan (an application: "¥288,570 Equipment lease · after
  approval") one full bar with its one label. Hover/focus on a segment opens the leg card round two already has. When the
  action carries no legs, the row shows the server's `cost_basis_text` alone.
- Cost to you stays the bold fact; "Needs your approval before it runs" stays the one quiet line above the buttons.

## 4. "FLOW action ready" once, the right rule
The worklist's alert row is shown only when the Home renders NO recommendation card (`home_v2.action` has no title and no
control), never keyed to the funding state. On the busy books (an application waiting for approval) the row must be absent.
Spec it on the busy books live and in the state matrix.

## Server words batch 9 (feat/home-words-9, services/api only)
`home_v2.kpis.cash_available.composition[]` as in §1 (shares from the same fen the KPI already has; `share_text` via
`strategy/words.share_text(..., whole=True)`; en/zh; `note` per key). Nothing else: the customers donut and the legs bar use
words the server already sends. Tests in test_home_v2.py (golden day 0: reserve 75% / buffer 25%; a state below the minimum:
cash + shortfall; zh).

## Gates
Focused: the Home batch under mock (re-recorded `--home-v2` once the words land), `home-v2-states` live (+ the busy alert-row
case), `ask-header`, design-system; the full pair at the merge.

## 6. Be intentional (owner, after reading §1): a chart only where it adds clarity
Owner: "make sure the pie charts and donuts actually add visual clarity to what I intend to showcase; if not, replace them with
other visualisation techniques, animations or other graphs; if text is the best way, that is fine." The lead's rules, which
amend §1:
- A donut ONLY for shares of one whole with two to six slices that are all worth reading. "What you are owed, by customer"
  (three customers, the selected one lifted, clicks that select) qualifies and stays. Reserve vs buffer does NOT: two slices
  repeat the thin bar the card already has. The deal's ask breakdown (99% / 1%) does NOT: a 1% slice says nothing.
- A stacked or segmented BAR for parts along a line of money: the funding legs (§3) and the deal's "¥420,000 invoice → ¥5,040
  discount → ¥414,960 net" (the selected deal card's donut becomes this bar, the amounts the server's `ask_breakdown` rows,
  animated in from the left on first paint, each segment clickable to show its row's sentence).
- A step line for money over time (the outlook, as today). Text when one number says it.
- So on selection: the Cash available card keeps its figure and bar and gains ONE marker on the bar for the selected item's
  effect: for a deal, the as-asked lowest cash and the recommended reply's lowest cash (the picture's `paths[*]` lowest words,
  two labelled ticks, the recommended in purple, animated sliding into place), with the sentence "As asked ¥165k in 60 days
  · Option A ¥300k in 30 days" under it (server words); for an invoice, the net after repayment as the tick; for a customer,
  no marker (the owed donut carries the story). The server words batch 9 (cash composition) is cancelled: nothing new is
  needed for this.
- Every motion: `--dur` 200–300 ms, opacity or a single transform, none under reduced motion; never a decorative animation.

## 7. The deal view's right column is one card (owner, after seeing round four's screenshot 02; lead's recommendation chosen)
Owner: "what you are owed by customers is presented in a very awkward manner; if the cash available today is of no use to the
current information in the deal it can be left on the default view and replaced." Decision: on a DEAL selection the right
column is ONE card, "Cash impact of this deal": the deal's own cash as the step chart (as asked in grey, FLOW's reply in purple,
the minimum as the hairline, the 36/60/120 window control as on the company chart), and under it the two lowest points named in
the server's words ("As asked ¥11k in 30 days · Option A ¥300k in 30 days"; the recommended in purple), then one quiet line
"Company cash stays separate from selected deals." The company cash card (with its ticks) and the owed-by-customer donut leave
the deal view. The deal card and this card share one height (the taller decides; ≤ 600 px). The Deal context panel beside the
worklist keeps the customer line, the stage, Customer profile and the evidence disclosure; the deal's cash block that round
four put there is removed (it is now the right card). The donut stays for a CUSTOMER selection, where shares are the story,
with the cash card beside the customer card as today. Nothing changes for the default view. Specs: the deal view at 1440/1100/
820/390 shows exactly one card right of the deal card, its chart and the two named points; the customer view unchanged.

## 8. The owed-by-customer donut lives on the default page too (owner, after §7)
- The donut "What you are owed, by customer" is a card of its own in the right column, directly BELOW "Upcoming cash
  movements", on the default page and on every selection (so it never moves): the three customers' slices and legend rows
  from the `/customers` rows (`name`, `outstanding_display`, `share_text`), the selected customer's slice lifted when one is
  selected, every slice and row a button that SELECTS that customer (the address changes to `?customer=`, the cards follow,
  Dismiss and Escape revert as today). On a deal selection the centre names the deal's customer. With fewer than two
  customers owed the card shows the one figure and no ring.
- The side card that round four swapped in on selection is therefore gone: a customer selection shows the customer card
  beside the cash card (as the default's left pair) and the donut stays in its place below the movements.
- One more figure where the server already has the word: "Upcoming cash movements" gains a last row "Overdue from
  customers ¥200k · 2 invoices" (the hybrid read's `overdue_short` and the collection rows' count), linking to Receivables
  with `?from=home`; omitted when nothing is overdue. Facility headroom and "concessions promised against your limit" are
  candidates for a later words batch (Cash and the envelope hold the figures); not in this round.
