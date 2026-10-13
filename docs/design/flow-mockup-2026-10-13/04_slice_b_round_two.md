# Slice B round two: Deals, Customer, Approvals after the owner's review (13 Oct 2026, evening)

Source: the owner's review of the Slice B screenshots (busy books, 1440), pasted 13 Oct. Verdict: "individual financial facts
competently, not yet a convincing business decision-making experience". Direction, adopted: **Home = attention. Deals =
commercial decisions. Customer = relationship intelligence. Approvals = exact authorization. Cash = liquidity consequences.
Receivables = collections.** Home (rounds two to five) is the design language: the panel-on-canvas cards, one filled ink
primary, StatusPill, the table rows, bars for money along a line, a donut only for shares, text when one number says it.

The lead's decisions follow the review except where marked **FLAG** (for the owner to overrule). Every word, figure, day and
share is the server's (INVARIANT 13); where the review asks for a new figure or sentence, the server batch below adds it.

## 0. The three P0 "verify" items (answered on the books, 13 Oct)
- **"Sending a counter records an agreement."** True in the engine: a send records a PROPOSED commitment that stands only if the
  buyer accepts (ADR-0011). The receipt's words were wrong, not the behaviour. Fix (server): the send receipt's three
  statements (§3) say "Records the proposed counter", "the terms take effect only when Foshan accepts", "no payment and no
  financing settles because the counter is sent"; the funding that DOES run on send (the gap plan) is said in its own line.
- **"Approval needed when terms change" beside "no approval needed."** The authorizes line carried a generic parenthetical.
  Fix (server): the line is specific to this send; the authority sentence is the only place authority is said.
- **"Scenarios use different funding assumptions."** True by design (#132: reply paths carry their own admissible plan, the
  request carries none). Fix (web + server words): the comparison gets a "Funding assumption" ROW ("No new funding" / "Funding
  plan required: ¥150k draw today"), so the difference is in the table, not a footnote. **FLAG:** the fair comparison the
  review asks for (same books + same funding + different terms, or each with its cheapest admissible plan) is the engine
  ticket #147 (stability set, full verification); not in this round.

## 1. Deals = commercial decisions
- **The queue holds negotiations only** (DECISION, BUYER_REPLY, AGREEMENT rows). The approval goes to Approvals, the
  collection to Receivables, the promise to Agreements; Home keeps the cross-functional worklist. The company funding
  warning stays as one compact line above the queue, counted nowhere. The server's `queue` gains `deals` counts (negotiations
  only) so the tabs' numbers are server words. **This amends decision #127** ("Deals adopts the worklist read as its
  queue"): Deals adopts the queue's negotiation rows; the worklist remains Home's.
- **Every negotiation has a distinct subject** (server `subject_text`): the obligation and its scope in words, never an id in
  Business ("Foshan · Early settlement on the ¥420k invoice", "Foshan · Early payment, 1.5% off", "Foshan · 60-day terms on
  future invoices", "Dongguan · 1% rebate next quarter", "Zhuhai · 75-day terms on the next invoice"). **FLAG:** the review
  suggests invoice ids (RCV-A); Business mode shows none (INVARIANT 13), so the amount and scope differentiate instead;
  Demo mode may append the id.
- **Group and sort**: a control above the rows: Group by customer (default off), Sort by urgency (default) / latest
  activity; a compact-rows / table switch at ≥ 20 rows (the table is the Home worklist's table).
- **Status is lifecycle only**: the pill vocabulary is Counter ready / Owner review needed / Awaiting buyer / More
  information needed / Agreed / Declined / Lapsed (server `status_text` + `lifecycle` key); financial risk is a separate
  mark (the severity dot and a "below your minimum" word), never a red cross on a ready row.
- **Widths**: the rail 56 px collapsed; the queue 340 px; the workspace fluid to 850 px; content max width 1400 px; 24 px
  between sections; the workspace's inner analysis uses open sections with dividers, not nested rounded cards.

## 2. The selected deal: terms you can compare
- **Commercial terms table** (replaces the two paragraphs): rows Payment period / Early-payment discount / Invoice amount
  eligible / Future rebate / Authority / Status; columns Buyer requests · FLOW recommends; the changed values highlighted
  (bold ink with a 2 px lavender underline), not whole columns. Rows from the server's `paths[*].terms[]` (`value_text`,
  `instead_of_text`) plus the authority and status words; the buyer's own message stays as a quote under "What Foshan asks".
- **Three scopes named**: Existing invoice (early settlement) · Future invoices (payment terms) · Next quarter (rebate), as
  the table's row groups; a scope the ask does not touch says "Unchanged".
- **Timing diagram** (one small SVG): three bars from day 0, Current terms 45 · Buyer requests 60 · FLOW counter 45, the
  difference labelled "+15 days requested by buyer"; days are server numbers (`terms_days` per path, `current_terms_days`),
  the labels server words; no bar for a path without a terms change.
- **Cost breakdown table** (replaces the two cost lines): rows per `cost_components` (immediate discount, forward
  payment-term cost, rebate, funding cost), columns Buyer request · Option A, a total row with each total's basis words
  exactly as the server states them (the horizons are NOT normalised; the row says "over 12 months" / "once"). No
  waterfall, no pie.
- **Cash comparison simplified**: four rows Lowest cash · Cash reserve (Breached / Preserved + days) · Owner authority ·
  Funding assumption; the full table behind "More".
- **The send review = three statements** then the terms and cost, the rest under disclosure: What you are authorizing
  (`authorizes_text`), What happens immediately (`executes_now_text`), What does not happen yet (`remaining_text`); then the
  commercial terms table and the cost; then one button "Send Option A to Foshan"; Authority, Assumptions, Audit evidence in
  a disclosure. **FLAG:** the simulated-buyer control (Open to a counter / Holds firm) is hidden in Business mode (the send
  uses the cooperative kernel and the review says "The buyer's reply is simulated in this environment") and stays in Demo
  mode; say if you want it visible in Business.

## 3. Customer = relationship intelligence
- **One sentence first** (server `relationship_text`): "Foshan contributes an estimated ¥1.09m a year, owes ¥420k (54.5% of
  your open receivables), and has three negotiations that could change your cash."
- **The four metrics stay**, with exact words: "¥336k financing planned against Foshan's invoice · not yet received";
  "54.5% of currently open receivables" with a small proportion bar under the number (secondary; no donut here).
- **Receivable → financing → net collection flow** (the review's top visual for this page): a vertical step list with the
  server's `receivable_flow[]` (steps: owed ¥420,000 → financing planned ¥336,000, arrives in 3 days if the plan runs →
  customer pays, due in 32 days → repayment and fees ¥X → net available at collection ¥Y; each step a figure and a when
  word from the linked receivable and facility, nothing computed in the browser). Shown for the customer's largest open
  invoice; "no financing linked" collapses it to two steps.
- **Primary action block**: "Foshan has one commercial decision requiring your response. FLOW recommends Option A.
  [Review decision]" (to Deals with the selection), then "Other open negotiations (3)" as a compact list; the detail area
  always shows the SELECTED row's heading, status and recommendation, never the highest-priority one in its place.
- **Exposure as a comparison, not a paragraph**: a two-column table Expected payment · 30 days late with rows Lowest cash /
  Reserve breach / Maximum shortfall / Additional funding needed, every cell the server's `stress.paths[*]` words, then
  "Explore late-payment impact →"; the sentence "a 30-day delay is an assumption, not a prediction" stays.
- **Links**: negotiation → its invoice → its financing → payment status, as one row of linked chips under the flow.

## 4. Approvals = exact authorization (pulled forward from Slice C)
- **Wording**: the button names the act: "Authorize the application" (server `commit_label`); the first sentence: "Approval
  sends an application to the lender. It does not mean the loan is approved or that funds have arrived." (server
  `authorize_text`); "Loan terms are not yet confirmed: you are authorizing an application, not accepting a financing
  offer." when no quote exists (server `terms_state_text`); a real quote's terms are shown when the server has them.
- **Lifecycle diagram**: three stages You authorize → Lender reviews → Funding decision, from server `lifecycle[]`
  (`{label, text, state: done|current|next}`); a stage is never shown done before it is.
- **Compact decision summary** (replaces the long table): Amount requested · Facility · What happens now · Does money move
  now · Who decides whether funds are offered · What if you decline (six rows from the receipt fields); then
  [Authorize the application] [Decline]; "View application details · Authority · Audit evidence" as disclosures.
- **Layout**: with one approval the focused card; with several, a split: the list left (grouped by urgency and type, with
  deadline, amount, authority) and the selected summary right. No "approve all".
- The owner's reconciliation stands: the receipt (now the summary) is the review, one named button, no second step.

## 5. Visual system, every page of this round
- Content max width 1400 px, workspace columns as §1; supporting text never below 13 px; detail panels scroll independently
  where they are taller than the queue.
- One action system: the ink primary everywhere (Approvals' blue goes), outline secondaries, quiet links.
- One selection colour: the lavender row with the purple edge (the design of record). **FLAG:** the review prefers a brand-
  aligned colour; the mockup's lavender is kept unless the owner says otherwise.
- Badges: lifecycle StatusPill (amber = needs you, lavender = waiting, green = agreed, neutral = lapsed/declined) and a
  separate severity dot; no red cross on a ready state.
- Inside the selected-deal analysis: open sections with dividers; rounded cards only for the page's top-level panels.

## Later (recorded, not in this round)
Portfolio view ("three pending requests extend customer credit" table with the combined impact labelled "Not yet evaluated"
until the engine can evaluate a combined scenario); the commercial commitment timeline; the fair-funding comparison (#147);
receivables aging once real histories exist.

## Server words batch (feat/slice-b-r2-api; services/api only)
`queue.deals` counts; distinct `subject_text` per negotiation; `lifecycle` key + `status_text` vocabulary; the comparison's
`funding_assumption_text` short form per path; `current_terms_days` / `terms_days` per path; the send receipt's three
statements reworded (authorizes / executes_now / remaining) and the authority line specific to the send; `cost_components`
rows per path with the basis words; customer `relationship_text`, the metric exact words, `receivable_flow[]`,
`exposure_comparison` rows; approvals `commit_label`, `authorize_text`, `terms_state_text`, `lifecycle[]`, `summary_rows[]`.
Tests for each, en and zh.

## Web (feat/slice-b-r2-web; apps/web only)
Deals queue (negotiations only, subjects, group/sort, table switch, lifecycle pills), the workspace (terms table, timing
SVG, cost table, simplified comparison, the three-statement send review, the Business/Demo buyer control), Customer (the
sentence, the metrics, the flow, the action block, the exposure table, the links), Approvals (wording, lifecycle, summary,
split layout), the widths and the action system. Specs per section, mock and live; the verifier walks journeys 1, 2 and 4.

## Gates
Focused specs while building; the full pair + tests/api at the merge; a verifier pass on journeys 1, 2 and 4 before merge.
