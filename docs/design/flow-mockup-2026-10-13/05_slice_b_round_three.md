# Slice B round three: the selected deal as one comparison (owner's review of 14 Oct 2026, golden books, 1440)

> **Superseded (16 Oct 2026).** Round three was built from this brief, reviewed by the owner on 15 Oct and redesigned under #160
> (a deal as its own page; see `docs/handover/18_round_three_checkpoint_2026-10-15.md`, `docs/research/deals-flow-audit-2026-10-15.md`
> and DESIGN.md "Deals, the redesign of 15 October"). §11's entry points and the tracker fold landed; the tabs, rail, breadcrumb, chips,
> outcome table, headroom plot and per-day inspector did not. Kept for the record; do not build from it.

Source: the owner's review of the Deals workspace on dev (after round two). Verdict: "you've organized the page around the
financial engine's outputs instead of the owner's decision"; the owner wants to answer three questions on the first screen
(which response is best for my business, why, what if I choose something else) and verify on the deeper screens.

Round three is therefore the single-deal comparison, not the multi-deal comparison and proposing sandbox round two §6 had
pencilled for it (the review §14: "finish the single-deal comparison UX before building a multi-deal interface"). Those two
move to **round four**, unchanged in substance.

§11 folds the deal tracker (map #148: #152 entry points, #153 one measure, #154 close-out and carry-over) into Deals, at the
owner's request of 14 Oct.

Sequencing: the accept-as-asked batch (feat/accept-as-asked-api / -web, in flight 14 Oct) lands first; round three starts on
top of it because both touch decision-pane, analysis-cards, investigate and the queue. The lead's decisions follow the review
except where marked **FLAG** (for the owner to overrule). Every figure, day and share is the server's (INVARIANT 13).

## 1. Three levels, one comparison model (review §1, §8, §10)
The selected deal has three levels and each adds depth rather than repeating the one above:
- **Summary (the Overview tab):** the buyer's ask in one line, FLOW's reply in one line, the two sentences of §3, the
  compact three-column commercial comparison (§2) and two buttons: [Review the counter] (the send review as today) and
  [Compare responses] (the Compare tab). Nothing else: no cost card, no cash card, no chart on the Overview.
- **Comparison (the Compare responses tab):** the response columns with the default rows Commercial terms · Economic impact ·
  Cash outcome · Authorization · Buyer status; a row expands in place to its calculation (the cost rows, the funding plan,
  the terms per scope) with "View cost calculation →" as the affordance. Then Financial outcomes (§5) and "Why these results
  differ" (§6). Then [Review selected response] [Back to deal].
- **Evidence (disclosures inside Compare, and the Cash impact tab):** the formulas and bases, the funding plan legs, the
  assumption sentences, the envelope packages, the source messages, the verifier's checks. Said once, here.
- One model in the browser (`deal-model.ts` grows; nothing is composed from pieces: each cell is one server word).
- **Repeated words go.** Authority is said in three places only: the Overview's mandate sentence (§3), the comparison's
  Authorization row (short word), and once in full in "Why these results differ". The terms table's Authority row and the
  cash card's "Owner authority" row are removed. The funding assumption is said once per column in the Cash outcome row's
  expansion and once in the chart's Funding line.

## 2. Commercial terms by scope, compact (review §9)
- The three scopes are the rows: Existing invoice (early settlement) · Future invoices (payment terms) · Next quarter
  (rebate or price). Columns: Buyer asks · FLOW counters (Option A) · Option B when it exists. Each cell is the server's
  `value_text`; a changed cell carries the `instead_of_text` as a quiet before→after line under it and a lavender-tinted cell
  background; **no underlines** (the 2 px purple underline of round two §2 goes: it reads as a link).
- The payment-period bars move INTO the Future invoices row as one small inline bar (Current 45 · Buyer wants 60, "+15
  days" · FLOW 45, "no extension"), the words `current_terms_text` / `terms_delta_text`; the standalone timing diagram
  section is removed. Height of the whole terms block ≤ 180 px at 1440.
- Server: `terms[]` gains `scope` (`existing_invoice | future_invoices | next_quarter`) and `scope_label`; a scope the
  response does not touch says "Unchanged" (server word, already the rule).

## 3. The recommendation says what it is (review §3; #131 stands)
The engine is not changed: FLOW still recommends the first reply it may send within the mandate and never ranks by cost
(decision #131). The presentation stops implying "best":
- The Overview's headline is the server's `recommendation.mandate_text`: "Option A is the reply FLOW can send within your
  mandate" (never "best", never "recommended because it is cheaper").
- Under it, when another reply needs the owner, `recommendation.alternative_text`: "Option B needs your approval for 55-day
  terms. Its net economic cost over 12 months is stated as about ¥0 under the model's assumptions." The sentence states the
  figure with its basis and does not call it better.
- In Compare, the column badges are the short authority words: "FLOW can send" · "Needs your approval" · "Outside mandate"
  (server `authority_short_text`, three values).
- The rule sentence ("FLOW recommends the first reply it may send within your mandate; it does not rank replies by cost")
  becomes the server's `recommendation.rule_text`, shown once in "Why these results differ"; the browser dictionary key
  `deals.why.rule` is deleted.
- Engine ticket (recorded, not this round): ranking replies by net impact so FLOW can say "Option A is the best counter I can
  send within your mandate; Option B is worth considering if you approve longer terms".

## 4. Responses apart from scenarios (review §2, §13)
- **Compare responses** holds only commercial packages: Buyer request · Option A · Option B (the picture's `paths[]`, kinds
  `asked` and `reply`). "Do nothing" and "If Foshan stops buying" leave this table.
- **Business consequences** is its own section at the bottom of the Cash impact tab, with three scenario controls
  (SegmentedTabs): Continue current position · Buyer pays 30 days late · Buyer stops placing new orders. Each shows a short
  read-only card: the assumption sentence first (`assumption_text`: "an estimate under the model's assumptions, not a
  forecast that Foshan will leave"), then its rows. Customer loss separates `lost_billings_text` (≈¥5.46m a year), 
  `lost_contribution_text`, `cash_effect_text` and `invoice_remains_text` (the ¥420k invoice stays payable). The late-payment
  scenario applies to the responses: its card shows the lowest cash per response under the delay (`stress.paths`), and the
  chart's Period/Funding line gains "Buyer pays 30 days late" as a toggle that switches every drawn line to its stressed
  series (as `?scenario=late` does today).
- Server: the picture read gains `scenarios[]` composed from the exposure and compare reads it already has (keys
  `no_new_agreement`, `late_30`, `customer_loss`; labels; the sentences above; per-response lowest words under the delay).
  Nothing is computed twice: the same functions, surfaced in one payload so the page makes one read.

## 5. Financial outcomes before the curves (review §5)
At the top of the Cash impact tab and under the comparison table:
- **The outcome table**, one column per response: Lowest cash (`lowest_short`) · When (`lowest_when`) · Reserve
  (`reserve_state_text`: "Breached by ¥135k for 15 days" / "Held, no buffer at the lowest point" / "Held with ¥40k to
  spare") · Financing needed (`financing_needed_text`: "None in this scenario" / "¥150k credit-line draw today") · Can FLOW
  send it? (`authority_short_text`). "Safe ✓" never appears: survival and flexibility are different words.
- **The headroom dot plot** under it: one row per response, a horizontal scale from the lowest value to the highest, the
  reserve as a vertical amber dashed line labelled with `floor_short`, each response a dot at its `lowest_fen` labelled with
  its `lowest_short`; below the reserve the dot is red, on or above it ink. The browser scales positions only; every label is
  a server word. 300 ms slide-in on first paint, none under reduced motion. This is the money-along-a-line case of the
  design language (round four §6), so it is a bar/dot, not a donut.

## 6. The chart compares what you choose (review §6)
- Title "Cash over time". Above it: **Compare** chips, one per response ([As asked ✓] [Option A ✓] [Option B]); two on by
  default (as asked + the recommended reply); a third may be switched on; never more than three lines. **Funding:** one line
  of text, "Each option with its own funding plan", until the engine's fair comparison lands (§8). **Period:** 60 · 120 days
  as today. The chosen set lives in the address (`?lines=asked,<counterA>`).
- Colours (one meaning each): the first chosen response solid ink, the second solid purple, a third muted and dashed; the
  minimum reserve an amber dashed horizontal line; the stretch of a line under the reserve red. Red never identifies a
  response. **FLAG:** the review asked for "FLOW blue" as the primary; the design of record has no blue (ink primary), so the
  lead keeps ink unless the owner wants blue back. The same colours apply to the Home deal card's chart (shared component),
  so the two charts read alike.
- Step changes kept (a cash balance, not a trend).
- **Event markers** on the first chosen line only: a small marker on each day whose point carries `events[]`; hover/focus/
  click shows the server's `events_text` for that day ("Day 2 · Early payment, if accepted"). No event rail.
- **The inspector shows two different comparisons, apart:** "On this day" (the chosen pair's two values and the server's
  `difference_display`, with the note that the difference includes every assumption that differs, not negotiation alone)
  and "Each option's lowest point" (each line's `lowest_short` + `lowest_when`, never subtracted).
- **"What caused the difference?"** under the on-this-day block: the server's `cause_text` for the pair at that day: the
  events up to that day present on one line and not the other, in words ("Option A: ¥150k drawn on day 0; no early payment.
  As asked: ¥414,960 early payment on day 2, no draw."). The browser lists nothing it composed.
- Server: the per-point `comparison` strip (today asked vs recommended only) becomes a map keyed by reply (`comparison[
  <counter_id>] = {asked_display, reply_display, difference_display, cause_text}`) so any pair that includes the asked path
  has its words; a reply-vs-reply pair uses `comparison_pairs[<a>:<b>]` on the same point. Both en and zh.

## 7. No nested scrolling; the queue steps aside (review §7, §12)
- The selected deal has tabs, on one line, under a sticky deal header (customer · subject · lifecycle pill · the lifecycle
  strip of §11 · the mandate sentence of §3). Before agreement: **Overview · Compare responses · Cash impact · Messages**.
  From agreement on: **Overview · Terms · Messages** (§11: the Overview is the tracker). Selecting a tab replaces the
  workspace content; nothing is appended under the page. The address is `?view=overview|compare|cash|terms|messages`;
  `investigate`, `compare`, `chart` and `show` are removed (old links with them land on `view=compare`).
- **One scroll.** The workspace's own `max-h`/`overflow-y-auto` goes; the page scrolls; the queue is sticky beside it. The
  deal header is sticky under the app's sticky box so the primary action never leaves the screen: [Review the counter] sits
  in the header's right end on every tab.
- **The queue collapses to a 72 px rail** when Compare or Cash impact is open (the review's Option 1): each row becomes its
  customer initial + lifecycle dot, the selected one marked; a "Show queue" control at the rail's top; the workspace takes
  the full content width (max 1400 px). The queue returns on Overview and Messages, and on Escape.
- Breadcrumb at the top of Compare and Cash impact: "Foshan / Payment terms / Compare responses", the first two crumbs links
  back.
- **[Choose A] / [Review B] never send.** In Compare, each response column ends with one quiet button that SELECTS it
  (`?path=` as today) and scrolls to [Review selected response], which opens the send review of round two §2 (three
  statements, terms, cost, one named button). The buyer request's column says [Review the request] when accepting is
  possible (the accept-as-asked review) and shows the "Outside mandate" badge otherwise.

## 8. The fair comparison stays an engine ticket (review §4)
Each response's cash is drawn with its own admissible funding plan (decision #132); the request carries none. That is
honest but not equal footing. The two modes the review asks for (Terms-only impact: funding held constant; Fully funded:
cheapest admissible plan per response, with Commercial terms → Financing required → Financing cost → Remaining cash risk →
Authorization per column) are engine ticket #147, verification included; "Unavailable under these terms" when a plan cannot
apply. Until then the chart's Funding line, the Cash outcome row's expansion and "Why these results differ" say the
difference in plans in the server's words, and the on-this-day difference carries the note of §6. The request that breaches
the signed mandate says so in its badge; funding does not cure it.

## 9. The queue and the rest of the page (review §11)
- **Progressive controls:** one negotiation shows the row and nothing else; the lifecycle tabs appear at two or more rows;
  Sort at four or more; Group by customer at six or more; the table switch at twenty (round two §1 amended).
- **The company funding alert** leaves the queue card: it is the page-level alert row under the page header, full width,
  the component Home uses (round three §5's "alert said once"), linking to Cash. It is never in the queue's counts.
- **Buyer messages** move into the selected deal's Messages tab, filtered to the selected customer's thread (the inbox is a
  static demo list today: the tab shows that customer's thread and the deal's own buyer message quote; opening a message
  still submits as today). With no deal selected the inbox card stays under the queue, as the way to start a negotiation.
- **Selection:** the lavender tint stays but lighter (the panel tint, not the chip tint), the thick outline goes; the joined
  edge to the workspace (the expand cue the owner chose on 14 Oct) stays, 1 px. **FLAG:** this amends yesterday's choice by
  weight only, not by colour.

## 11. The whole life of a deal lives in Deals (owner, 14 Oct: "fold the tracker into Deals"; map #148, tickets #152–#154)
The deal tracker (`GET /decisions/{id}/tracker`, merged 14 Oct at 86e8a9bb, its own page under the decision record) is the
after-agreement half of the same deal. Deals shows the whole life, so the owner never leaves the page to learn what a deal
cost, what each side promised and what remains.
- **One lifecycle strip per deal**, in the sticky header, from the server's `lifecycle_stages[]`: before agreement the offer
  stages (Received · Analysed · Reply ready or Owner review · Sent · Agreed), after it the contract stages keyed to this
  deal (Agreed · Early payment · Collecting · Fulfilled); states done / now / still to come / missed / under way with the
  server's words; `when_text` under a done stage. The same component Approvals uses for its three stages. Never more than
  seven steps; a stage the deal does not have (no early payment promised) is absent, not greyed. The three vocabularies on the
  server today (contract stages per buyer, offer stages, the lifecycle key) are not changed; `lifecycle_stages[]` is composed
  from them per decision in one function the tracker read and the deal workspace read both call.
- **An agreed deal's Overview is the tracker**, rendered by the same component the `/decisions/{id}/tracker` route keeps (one
  body, two addresses; the record's link stays): the headline sentence and state pill; "What it cost" as three figures in
  one row, Expected (quoted when agreed) · So far · Still to come, each with its certainty word; the cost lines under
  "More"; the promises of each side as rows with their state pill and evidence link; the buyer block (this deal's kept
  promises, then the payment-behaviour sentence); the one next step as the header's primary button (Chase payment / Review
  the funding approval); the close-out sentence first when the deal has ended. Nothing is computed in the browser: every
  figure is the tracker's.
- **The cost figure and the owner's switch (#155, open).** The headline "So far" shows the tracker's `actual` with its note,
  so funding after a late payment is always visible as its own line labelled "attributed", whether the switch counts it in
  the total (Option A, today) or shows it beside the total (Option B, the lead's recommendation). The switch is not a web
  concern; the page renders either from the data, as the tracker page does now.
- **Terms tab after agreement:** the terms-by-scope table of §2 for the agreed response only (the column "Agreed"), with the
  cost rows quoted at agreement; no comparison, no chart (the deal's cash is history now, and Cash owns the company view).
- **Closed deals stay in the queue (#154).** The Agreed tab lists AGREED rows first and then a "Closed" group (FULFILLED ·
  MISSED · REVOKED · EXPIRED) whose rows carry the tracker's `state_word` as the pill and the close-out sentence as the
  consequence text; the tab's count is agreed + closed ("Agreed 1 · 1 closed" from `queue.deals`). Amends round two §1
  (FULFILLED and MISSED no longer drop out). The lifecycle vocabulary gains `closed` (server `lifecycle` key; `status_text`
  the tracker's state word).
- **Carry-over (#154).** When a buyer with an ended or agreed deal sends a new request, that request's Overview shows one
  quiet line under the buyer's ask, labelled "Last time": the server's `buyer_history_text` ("Last time Foshan agreed 45-day
  terms and paid in 52 days; the deal cost ¥4,809.96 against ¥3,027.77 expected."). Context only: it changes no verdict,
  counter, plan or authority, and says so in its `title`. Absent when the buyer has no prior deal (every book on day 0).
- **Entry points (#152), each with `from` under the selection contract:** the Deals queue row itself (selecting an agreed or
  closed row opens the tracker Overview; no separate link); the Customer page gains "Deals with Foshan" under the open
  negotiations: the buyer's agreed and closed deals as rows (subject, state word, close-out or agreed sentence) linking to
  `/deals?customer=&decision=&from=customer`; Activity's "Open this decision" on an agreed or ended deal links to Deals
  (`from=activity`) with the record as its evidence link; the Demo's agreement and "Outcome and proof" scenes gain "Track the
  deal" to Deals (`from=demo`). The tracker route keeps "Back to the record".
- **One measure of how a buyer pays (#153) comes after round three**, on an integration branch: the buyer block's
  payment-behaviour sentence is the one place the grade will read; whether the grade is a word or only its evidence is the
  owner's (#155). Round three leaves a slot, not a grade.

## 10. What is later
- Round four: multi-deal comparison ("Compare selected deals" from the queue, a separate portfolio view; the combined effect
  "Not yet evaluated" until the engine evaluates a combined scenario), the proposing sandbox (round two §6).
- Engine tickets: #147 fair funding comparison; ranking replies by net impact (§3); the combined multi-deal scenario.

## Server words batch (feat/slice-b-r3-api; services/api only; nothing in the stability set)
Per path: `authority_short_text`, `reserve_state_text`, `headroom_short`, `lowest_day`, `financing_needed_text`,
`buyer_status_text` ("Asked by Foshan" / "Not yet sent" / "Sent, awaiting reply"), `economic_headline_text` with
`economic_basis_text`, `terms[].scope` + `scope_label`. `recommendation {mandate_text, alternative_text|null, rule_text}`.
`scenarios[]` (§4). The per-point `comparison` map and `comparison_pairs` with `cause_text` (§6). For §11: `lifecycle_stages[]`
on the deal workspace read and the tracker read (one function); the queue's closed rows (`lifecycle: closed`, `status_text`,
`consequence_text` = close-out) and the `queue.deals` closed count; `buyer_history_text` on the workspace read; the Customer
overview's `deals_history[]`; Activity's and the Demo story's hrefs to Deals for agreed and ended deals. Every word en and zh;
tests in test_slice_b_round_three.py (golden day 0 with Option B; the busy books' Zhuhai deal with one reply; a state with no
recommendation; zh). The `deal-why-rule` sentence moves server-side.

## Web (feat/slice-b-r3-web; apps/web only)
The tabs and address (§7), the Overview (§1, §3), the terms-by-scope block (§2), the Compare workspace (§1, §4, §5, §7), the
Cash impact tab (§5, §6, §4's Business consequences), the Messages tab (§9), the rail collapse and one-scroll layout (§7),
the queue's progressive controls and the alert row (§9), the selection weight (§9); the lifecycle strip, the tracker body
shared with its route, the Terms tab, the Closed group, the "Last time" line, the Customer history rows and the entry
points (§11); `deal-model.ts` as the one model;
dictionary keys for every label (no composed money words). Specs: slice-b-round-three.spec.ts (each tab and its address,
the rail collapse and return, the chips and the three-line cap, the inspector's two blocks, the headroom plot labels, the
scenario cards, no "Safe", no "best", no underline on changed cells, the alert row outside the queue); the round-two specs
amended where their sections moved; mock re-recorded after the server batch; live on the golden and busy books.

## Verifier (before merge; the independent pass the protocol requires for money and authority)
Journeys: (1) golden books, Foshan: Overview → Compare → choose B → the review shows B's exact terms, authority "needs your
approval", no send without the owner; (2) the chart: chips, the pair's on-this-day words equal the server's, the lowest
points never subtracted; (3) busy books, Zhuhai (one reply, owner review): the Overview's alternative sentence absent, the
Compare has two columns; (4) scenarios: customer loss shows the four sentences and the invoice-remains sentence; (5) every
money word on the page appears verbatim in a server response (grep the recorded reads); (6) the golden story walked to its
end: the agreed deal's Overview in Deals equals the tracker route figure for figure at agreement, the part receipt, the late
day, the cure and settlement; the closed row and its sentence; a new Foshan request shows the "Last time" line and its
verdict is unchanged with and without it. Words: no "best", no "Safe", no
"None", no id in Business.

## Gates
Focused specs while building; at the merge the full pair (mock + live), tests/api, typecheck/lint/unit; DESIGN.md's Deals
section rewritten to the three levels.
