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
