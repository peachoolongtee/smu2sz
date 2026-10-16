# Slice C: Receivables = collections, Cash = liquidity consequences, as one journey (lead, 14 Oct 2026)

Source: the owner's 12 Oct audit (map #121, ticket #144; UX08/09/13/14/22/28/31; #133 Approvals already pulled forward in
round two), handoff 16 §6's plan for Slice C, and the direction adopted on 13 Oct: **Receivables = collections, Cash =
liquidity consequences, Home = attention.** The design language is Home's (docs/design/flow-mockup-2026-10-13/00): panel cards
on the canvas, one filled ink primary, StatusPill, the worklist table, a bar for money along a line, a step line for money
over time, text when one number says it. Every figure, day and share is the server's (INVARIANT 13). **FLAG** marks a
decision for the owner to overrule.

Ownership: this machine (the lead's) builds Slice C while the second machine builds Slice B round three. Slice C touches
Receivables, Cash, the shared content container, Home's links and words, and server reads under app/api; it does NOT touch
Deals, Customer, Activity, Demo or the tracker (the PC's). The one seam into Deals is a server-written href the PC renders
(§4). The Cash chart (§3.5) reuses the component round three is changing, so it is built LAST, after round three's chart lands
on dev.

## 0. Amended 16 Oct, after Dylan's redesign of Cash and Receivables landed on dev (a6de32a2)
The brief was written against the pages of 14 Oct. Dylan's pages are the base now (handoff 19 §1); the brief applies to them:
- **Receivables (§2)**: the customer list first is kept (it is Dylan's structure and the owner merged it); §2.1's three cards
  stay on the list page; §2.2's table, lifecycle pill, tabs and `from` apply to the customer view (`?customer=`); §2.3's net
  bar replaces the `<dl>` breakdown in `invoice-detail.tsx`; §2.4 (the reminder with its receipt and recorded event) and §2.5
  (promised and received, last) stand. Dylan's reconciliation tiles live on Activity's Reconciliation tab; §2.5 does not
  duplicate them: Receivables keeps the receipts-vs-promises rows, Activity keeps the tiles, and each links to the other.
- **Cash (§3)**: Dylan already put the plan before the chart at every width (§3 order: done). §3.1 adds the lowest point's
  cause and the reserve pill to his `CashFigures`; §3.2 keeps his run bar and adds the three-statement review on the run and
  the quiet "Compare this scenario"; §3.3 (compare, read-only, `GET /cash/scenarios`, `?scenario=`) is new; §3.4 splits his
  "Your funding" list into committed facilities and conditional options (a buyer's early payment is never "available");
  §3.5 (the full timeline) is last and is the only part that waits on the chart component. His "Try other terms" and "More
  funding" cards stay where he put them. The anchors of §3.4 are added and #163's dangling `#cash-options` is fixed first.
- **Home words and links (§5)**: the recommendation card no longer runs the plan (it goes to Cash), so its buttons link to
  `#cash-plan`; the owed-by-customer donut and the worklist are unchanged.
- **The design of record** for both pages is dev as merged (the No Rail Rule with the alarm-card exception, the section hue
  and backdrop, `home-f` on every main); the brief's "Home's cards" means the cards as Dylan restyled them.
- **Rules**: `docs/agents/integration.md` applies (small branches from dev, the full mock suite before hand-in, the lead
  merges). The Cash chart (§3.5) no longer waits on round three (merged); it waits only on its own design.

## 1. What each page is for
| | Question | Decision it owns |
|---|---|---|
| Receivables | What am I owed, what is at risk, what do I do about it today? | Collect: prepare and send a reminder, see what the invoice nets you, see what a late payment does |
| Cash and funding | Is the company safe, and what funding do I run? | Run (or decline) the one funding plan; compare a scenario against the committed baseline |
Home shows the one-line conclusion of each and links in; neither page repeats Home's worklist or recommendation card.

## 2. Receivables
### 2.1 Header and the three figures
PageHeader "Receivables"; the server's one sentence (`summary.headline` + `headline_second`) as the subheading; three cards as
Home's: **Owed** (`outstanding_total`, "4 invoices · 2 overdue" from `count_text`), **Next expected** (`next_expected`:
amount, buyer, when), **Net to you at collection** (`net_total`, `net_total_text`, the funder's repayment as the quiet line
`repays_line`). 13 px floor for every qualifier.

### 2.2 The invoice table (the Home worklist table)
- Rows from `/receivables.rows[]`; columns at ≥ lg: Customer · invoice (36%: `subject_text`, new: "Foshan · ¥420,000 due in
  32 days"; no id in Business, `subject_demo_text` carries it in Demo), State (the lifecycle pill), Due (`due_when`), Net at
  collection (`net.net_short`, right-aligned); 56 px rows; the chevron + joined-edge cue the Deals queue has.
- **One lifecycle per invoice** (server `lifecycle` + `status_text`, new, composed from `collection_state`, `financing_state`,
  the promises and receipts): `not_due` · `due_soon` · `overdue` · `promised` (an early-payment promise awaited) ·
  `part_paid` · `financed` (an advance outstanding against it) · `paid`. Financial risk stays a separate severity dot.
- Tabs: All · Needs you (overdue, promise missed) · Due soon · Financed, counts from the server (`summary.tabs`, new).
- The address carries the selection (#126): `?invoice=`, `?customer=` (filters the table to the customer and selects their
  first row), `from` honoured for the way back (today the page drops it; Home's `?from=home` and the worklist's `from=deals`
  must land on a "Back to Home / Deals" link via `context.back`).

### 2.3 The focused invoice: what it nets you
- "What you get" as the money-along-a-line bar: **Gross outstanding → owed to the funder (advance repaid + charges) → net to
  you at collection**, the segments from `breakdown[]`, labels and amounts the server's; the basis word under it
  (`basis_text`: owed / scheduled / agreed / pending); the recourse sentence; `condition_text` when the net depends on a
  condition. This is the reconciliation the audit asked for (gross / funder / net); the receipts-vs-promises match is §2.5.
- Facts: terms, due, late by, early payment (if promised), "Financed against <facility> · advance ¥336k arrived 3 days ago"
  linking to `/cash#facility-<id>` (server adds `facility_id` and `facility_href` to the row; today only the Customer page
  builds that link), the pending counter linking to Deals with the selection.
- **"If Foshan pays 30 days late"** beside it: Lowest cash · When · vs your minimum · Funding needed, from the exposure stress
  words; "Explore in Cash →" goes to `/cash?scenario=late:<buyer>:30&invoice=&customer=&from=receivables` (`scenario` under
  the selection contract; the old `stress=` is read for a release and redirected).
- Ask FLOW carries the invoice: the chat scope chip reads "Discussing Foshan's ¥420,000 invoice" (the scope model gains the
  `invoice` kind).

### 2.4 Collection as an action with a receipt
- Primary per state (server `collection_action`, as today): Overdue and promise missed → **Prepare the reminder**; Due soon →
  Prepare the reminder; Not due → View terms. One filled button; the others quiet.
- "Prepare the reminder" opens the review in place (the same Statements component as the send and accept reviews): **What
  this does** ("Prepares a reminder for Foshan with the invoice's facts; FLOW sends nothing."), **What you do** ("Copy it into
  your channel, or mark it sent."), **What is recorded** ("A reminder prepared today, on this invoice and in Activity.");
  then the facts and the request text (copy button); then [Mark as sent] filled and [Copy] quiet. The chase read
  (`GET /receivables/{id}/chase`) stays the source of the facts and words.
- **Recording.** New `POST /receivables/{id}/reminder` (owner), body `{state_version, sent: true|false}`: appends an audit
  event (`collection.reminder_prepared` / `collection.reminder_sent`) with the invoice, buyer and day; moves no money, changes
  no state, 409 on a stale state_version. The invoice's detail shows "Reminder sent today" under its facts (server
  `collection_events[]`, en/zh), and Activity shows it as a business row. **FLAG:** the audit log is append-only and outside
  the operations executor; if the lead finds it inside the stability set when implementing, the record is deferred and the
  third statement says "Not recorded in this version", never a false "recorded".
- The late-payment stress that needs funding escalates: "Funding needed if Foshan pays late: ¥X · needs your approval" links
  to Approvals when a plan is waiting, else to Cash's compare with the scenario preset.

### 2.5 Promised and received
The receipts-versus-promises section stays, last, restyled on the kit from `GET /reconciliation`: one line "7 receipts matched,
1 flagged" (server words), then the flagged rows first (buyer, day, received vs expected, difference, the status pill:
Matched / Short payment / Discount ignored / Unexpected amount / Unmatched), the rest under "Show all"; the promised rows
(Awaited / Received / Lapsed / Settled otherwise); the chain-valid word links to Trust (`/trust?view=evidence&from=receivables`).
Dylan's ui-ux-testing section is the reference for the rows; its hand-rolled tiles and badges are not kept.

## 3. Cash and funding, in this order (every width; the decision before the chart)
### 3.1 The position
Three cards: **Cash today** (`cash_short`, the thin reserve bar as Home's), **Lowest point ahead** (`lowest_short`,
`lowest_when`, and NEW `lowest_cause_text`: "after the ¥288,570 lease payment on day 30", with `lowest_cause_href` when the
cause is a deal or an invoice, so the seam to Deals/Receivables is one click), **Reserve** (`headroom_short` or the shortfall
with `first_breach_when`; the StatusPill: Safe / Tight / Below your minimum, server words). No "Safe ✓" without the headroom.

### 3.2 The one funding decision
Home's "What we recommend" card, the same component (title, the legs bar with `lands_when` and cost per leg, Cost to you,
the one quiet "Needs your approval" line, the buttons at the bottom): **[Review and run the plan]** opens the three-statement
review (what you are authorizing · what happens immediately · what does not happen yet, from the plan's receipt words) and
runs via the existing act route with `state_version`; **[Compare this scenario]** is the quiet second button and opens §3.3.
When nothing is needed the card says so in one sentence and shows the committed baseline's lowest point. When a plan waits
for approval the card's primary is "Review the approval" → Approvals with the selection. The run never runs anything but the
server's recommended plan; running another admissible plan is a ticket (the act route takes no plan choice today).

### 3.3 Compare this scenario (explicit, read-only)
A section with SegmentedTabs: **Committed baseline** · **Late payment** (buyer and days from the address, default the
largest open invoice's buyer, 30 days) · **No new funding** · **Another plan** (one of the router's admissible menu rows, picked
from a list with each row's cost and authority words). The chosen scenario shows the **outcome table** beside the baseline:
Lowest cash · When · Reserve · Financing needed · Cost · Authority (server words per column), and draws as the second line on
the chart (§3.5). It never changes the run control; the section says "Comparing changes nothing; the plan above is what runs."
Address: `?scenario=baseline|late:<buyer>:<days>|none|plan:<key>` so Receivables, Deals and Home can open it preset. Server:
`GET /cash/scenarios?scenario=` (new, composed from the exposure stress read and the router's plan menu; nothing re-derived).

### 3.4 Sources
**Committed facilities** (limit / drawn / available as one bar each, speed word, the `facility-<id>` anchor kept, the explainer
under disclosure) apart from **Conditional options** (a pending application: "¥288,570 equipment lease · waiting for your
approval"; a buyer's early payment: "not available: it depends on Foshan"). Nothing conditional is ever drawn as available.
The anchors Home's server links already point at (`#where-the-cash-goes`, `#facility-headroom`) do not exist today; Cash gets
`#cash-position`, `#cash-plan`, `#cash-compare`, `#cash-sources`, `#cash-timeline` and the server's `links` are repointed.

### 3.5 The chart last: the Financial Timeline (#113)
The CashPreview component in its full variant (the same component Home's compact forecast and round three's deal chart use;
built after round three lands so the colours, chips, event markers and the inspector's two blocks are one implementation):
the committed baseline solid ink, the compared scenario purple, the reserve amber dashed, below-reserve red; event markers on
the baseline with the server's `events_text`; 30 / 60 / 120; the inspector "On this day" with the server's same-day words and
"Each line's lowest point". The readings fold (DSCR, leverage) and the doors to What-if and Capex stay under it as quiet links.

## 4. The seams
- **Deals → Cash:** the picture's reply paths gain `funding_href` = `/cash?scenario=plan:<key>&decision=<id>&from=deal` (server,
  this slice); the PC's round three renders it on the Funding row and the Cash impact card when present (one line; noted on
  #143/#148). Cash's `context.back` from `from=deal` reads "Back to the deal".
- **Cash → Deals / Receivables:** `lowest_cause_href` (§3.1); a committed source that exists because of an agreement says so
  ("from the Foshan agreement", the lot's words) and links to the deal.
- **Receivables → Cash → Approvals:** §2.3 and §2.4's late-payment path; Approvals' way back carries `from=cash|receivables`.
- **Home → both:** the overdue row → `/receivables?from=home` (honoured now); the recommendation's buttons → `/cash#cash-plan`;
  the outlook's "Expand" → `/cash#cash-timeline`; the owed-by-customer donut's rows → Customer (unchanged).

## 5. The shared frame and the Home words batch
- One content container for Home, Cash, Receivables and Activity (the component Home uses; the audit's "88 px gutter aligned");
  a spec measures equal left edges of the four pages' first card at 1440 and 1100. Activity's container change is a one-line
  swap and is coordinated with the PC (it is not editing Activity's layout in round three).
- Home words (server, this slice): the facility headroom sentence for the cash card ("¥486k undrawn across two facilities"),
  "concessions promised against your limit" (`envelope` words) for the deal view's quiet line, and the chart's title word.
  Home renders them where round five left the slots.

## Later (recorded, not this slice)
Running an alternative admissible plan from Compare (the act route takes no plan choice); receivables aging buckets once real
histories exist (#102); a buyer's reliability measure beside the invoice (#153, after the tracker's one measure); the real
accrued charge per lot (engine).

## Server words batch (feat/slice-c-api; services/api only; nothing in the stability set)
Receivables rows: `lifecycle`, `status_text`, `subject_text`/`subject_demo_text`, `facility_id`/`facility_href`,
`collection_events[]`; `summary.tabs`; `context.back` from `from`. `POST /receivables/{id}/reminder` (§2.4) and its audit
event + Activity row. Cash: `position` block (`lowest_cause_text`, `lowest_cause_href`, the reserve pill word),
`GET /cash/scenarios`, the repointed `links`, the plan's three-statement receipt words if missing. Picture paths'
`funding_href`. Home words (§5). The `scenario=` reading of the late-payment address with the `stress=` redirect. Tests in
test_slice_c.py, en and zh, golden and busy books.

## Web (feat/slice-c-web; apps/web only)
Receivables (§2) first; then Cash §3.1–3.4; then the shared container and Home's links (§5, §4); then §3.5 after merging dev
with round three's chart. Specs: receivables-collections.spec.ts (table, lifecycle pills, selection and way back, the net bar
words, the reminder review and its recorded event, the stress aside and its link), cash-decisions.spec.ts (the order of
sections at 1440 and 390, the review and run, compare's four scenarios and that the run control never changes, sources apart,
the anchors), frame.spec.ts (equal gutters); the old cash/cash-stress/receivables-layers specs amended to the new order and
addresses, their pins kept; mocks re-recorded after each server hand-back.

## Verifier (before the merge)
Journey 3 of the audit on the busy and golden books: an overdue invoice → the reminder review → "Mark as sent" → the event on
the invoice and in Activity with no money moved (books byte-identical except the audit log) → the late-payment stress →
Cash's compare preset → the plan's review → run → the receipt, then Approvals when the plan needs the owner. Money: every
figure on both pages verbatim in a server response; the net bar's segments sum to the gross in the server's fen; nothing
conditional shown as available; Compare never commits. Words: no id in Business, no "None", en and zh.

## Gates
Focused specs while building; at the merge: tests/api, typecheck/lint/unit, one whole mock and one whole live run; `--no-ff`
into dev after pulling the PC's round three if it has landed; DESIGN.md's Receivables and Cash sections rewritten; #144
closed with the counts; the UX tickets it answers listed on the map.
