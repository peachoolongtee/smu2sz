# Home V2: the owner's third review (13 Oct 2026) and the build amendments

Owner's verdict on refined2: the default Home is approved as drawn (8.8/10); the selected-deal states need one focused
simplification; no more mockups, build now. These amendments override the matching parts of 09 and of the build spec.

## Keep exactly as refined2 (do not redesign)
The header, the metric strip, the recommendation with its action group, the company cash chart with the fixed inspector,
the worklist architecture (underline tabs, search, rows, the one-line alert), the typography, the compact controls.

## Selected-deal Home: three levels, only the first two shown by default
**Level 1, Decision.** Breadcrumb; verdict word; "{Customer} · {subject}"; the customer line with "View customer →"; the
buyer's ask in one line (the server's ask sentence); then the recommendation block: "FLOW recommends Option A" with the
option's own description sentence and its cost with the basis word ("Estimated one-off cost ¥3,027.77"); the ask's cost
line with its basis ("The request costs ¥28,326.92 over 12 months, plus ¥5,040.00 once"); the ActionGroup
[Review counter] filled, [Compare responses] outline (a toggle). Nothing else.
**Level 2, Consequence.** One compact table, As requested vs the recommended option only: Lowest projected cash (figure +
when), Reserve status (the breach/at-minimum word), Authority (the limit word). Above it "Payment timing assumption" with
the compact scenario control and its one line. No chart here by default.
**Level 3, Investigation, only on request.** "Compare responses" expands, in place and without scrolling the page, the
full ComparisonTable (all paths) and under it the "Why FLOW recommends Option A" lines; clicking again collapses the same
block. "Cash impact" (an outline button in the same ActionGroup, or the table's own link) expands the deal-scoped chart
with its inspector; clicking again collapses it. "Open in Deals →" carries customer, decision and scenario. Drop
"Explore comparison", "Detailed economics" and "Compare cash outcomes" everywhere (also on the default Home: the only chart
link is "Full timeline in Cash & Funding →").

## Financial clarity (words from the server, never derived in the browser)
- The ComparisonTable's economic row keeps each path's basis word; no derived total is added until the engine defines one.
- Authority splits into two rows: "Within your limits" (the limit word: Within / Exceeded) and "Approval" (`decides_text`:
  "FLOW can send it" / "Needs your approval"), so Option B reads feasible AND approval-required without contradiction.
- Option B's row header in the expanded table carries its authority evidence (`authority_reason_text`) directly under the
  name; Option A's header carries `recommended_reason_text` (batch 3). Never a browser sentence about which cost is lower.
- The deal chart (level 3): the recommended option SOLID brand blue; the buyer's request grey with its below-reserve
  segments red; the reserve a thin line. Its inspector is a same-day comparison ("In 60 days · same day": As requested,
  Option A, and the server's `difference_display` when present, else no difference line) and says in its label that each
  option's own lowest point may fall on another day (the level-2 table carries those).
- The deal scenario's funding assumption must be visible: one line under the level-2 table, from the server's assumption
  words (`scenario_assumption_text`, batch 3b: whether the company plan is assumed to run, and that the option assumes the
  buyer accepts). Until the field lands, show the exposure read's existing basis/assumption sentence if any, else nothing.
  (P0 verification in flight: why the deal's lowest is ¥300k when the company's current-books lowest is −¥105k.)

## Health band in deal focus
"Cash risk · 12 days remaining" as the eyebrow words the alert already carries, the alert sentence, and the OUTLINE
"Review funding plan" button. One filled button on the page (the deal's).

## Worklist rows
Three lines: "Customer · Decision", status, the one most important consequence. The differentiator (batch 3) in plain
business words when two subjects collide, never an opaque id. Tab counts neutral; the dot and severity word carry severity.

## Behaviour
Expansion is predictable (toggle, no scroll jump, focus stays on the toggle). Opening Deals or the Customer page keeps
customer, decision and scenario in the URL. The comparison table scrolls with a sticky first column at narrow widths and
stacks below 1024 px; the text never shrinks.

## Spacing
Tighter vertical rhythm in the deal preview (16 px between the ask, the recommendation and the consequence; 32 px only
before the level-3 blocks). Headings: "Estimated economic impact" (commercial economics) and "Financial consequence"
(liquidity) keep their names; each gets one quiet line saying which it is.
