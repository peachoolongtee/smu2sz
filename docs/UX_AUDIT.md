# UX audit of the TermsLedger web app (5 Oct 2026)

The audit the owner's third brief asks for (`docs/handover/03_ux_redesign_brief.md`, sections 3, 4 and 20). It was made
on `dev` at `682a610` by reading every file under `apps/web` (14 pages, 30 components, the dictionary, the client and the
mocks), reading the API views the pages consume, and then running the real application (the API in memory with the cached
model, the web app in live mode) and walking it as the five readers the brief names: an SME owner, a finance manager, a
first-time user, a judge, and someone who did not build it. Every screen was captured at 1440 px and on a Pixel 7 in four
states: the opening books on day 0, each of the fifteen demo steps, the quiet books after the Scene 1 deal, and day 34 with
the late invoice, the queued cure and the approval. The findings below quote what the screens showed.

The design reference is `docs/handover/03_ux_reference_dashboard.webp`: a top navigation of a few sections, KPI tiles with
a sparkline and a comparison, one chart with series toggles, a cost list, one filterable table, one primary button, calm
green on white.

## 1. Current user journey

**As shipped, there is one journey, and it is the demo's.** The shell pins a "DEMO" stepper bar under the header on every
page (Setup, Scene 1, Scene 2, Scene 3, Security, Start demo, Reset). The brand link opens the Mandate page. The home page's
first card is "Today", a day counter with a "Demo control" badge and four buttons that move the simulated clock. The header
carries a "Live API" or "Mock data" pill, an "Owner" pill, Sign out, and the language switch. The sidebar lists fifteen
destinations in two groups, "screens" and "Owner and audit".

An owner who opens `/` on day 0 sees, in order: the clock control; a 70-word paragraph from the agent that starts "Day 0. On
current books cash falls ¥240,000.00 below your ¥300,000.00 floor on day 12" and ends "Go ahead?"; five tiles (Cash today,
Reserve floor, Lowest projected cash −¥105,000.00 in red, DSCR month 1, Leverage month 1); "Waiting for you: nothing";
"At risk" with a Critical card whose body repeats the paragraph and adds the formula `¥2,994.08 / ¥336,000.00 × 365/29 =
11.2% a year` in monospace; and "Done by the agent: nothing yet". Nowhere does the page say "you are not safe" in two words,
nor "finance the invoice" as a labelled recommendation, nor what happens if the owner does nothing. The answer is in the
paragraph; the reader has to extract it.

On a phone the first viewport shows the header (four chips on two rows), "Home", the subtitle, and the clock card with its
number input and four buttons. The agent's sentence begins at the bottom edge. The status, the recommendation and the
approval are all below the fold, and the floating "Ask the agent" button sits on top of the stepper bar.

A judge following the stepper hops through seven pages (Mandate, Inbox, Trajectory, Funding, Verdict, Verdict again, Ledger,
Verdict, Funding, Ledger, Verdict, Capex, Approvals, Security, Evidence), each a full module view: the Verdict page at step 5
is 4,246 px tall at 1440 px wide and opens with the whole verdict sentence in a grey box, then "Early-pay discounts as a yearly
rate", then four violation cards each with a Formula block and an Inputs table of 10 to 20 rows, then "Checks that held",
then a valuation table keyed by obligation id (`OFF-f806f79b6c21-02`), then two counters with their pricing formulas, then
the negotiation card, then the committed plan with cost lines and formulas. The Funding page is 2,790 px: an eight-row menu
table with covenant definitions in a cell, the plan, cost lines, rejected candidates, marginal cost, the extension cost, and
the comparison. Every one of these is level 4 of the brief's disclosure ladder, shown at level 1.

## 2. Primary UX failures

1. **No answer at the top.** The home has no status, no sentence, no verdict on "am I going to run out of money". The
   closest things are a red negative tile ("Lowest projected cash −¥105,000.00, Day 30") with no conclusion attached, and a
   paragraph. The brief's ten-second test fails for every reader except the person who built the engine.
2. **Business and demo are the same shell.** The stepper, the scene buttons, the clock card, the "Live API"/"Mock data"
   pill, the "Synthetic fixture data" footer and the sample-message composer all sit inside the owner's screens. An owner
   sees test controls first; a judge cannot tell the product from the walkthrough.
3. **Navigation by engine module.** Fifteen entries that map one to one onto API routers and code packages: Inbox is the
   compiler, Trajectory the projection, Funding the router, Verdict the verifier, Ledger the log, Security the audit table,
   Evidence the JSONL export, Reconciliation the matcher. The same cash gap is explained three times in three places
   (Trajectory tiles, Funding plan, Verdict violation) and the owner has to know which page holds which third.
4. **The recommendation and the approval speak the executor's language.** The queue card's title is "submit invoice for
   financing FAC-IF", its subtitle "APR-000001 · Submit invoice for financing · Agent · Created on day 34", its body the
   admission sentence with "32.52%" and "annualised". The amount is there (¥200,000.00); the cost in yuan (¥1,782.19), the
   day the money lands (37), what the money protects (payroll on day 42) and what happens after approval are not on the
   card. The alert card leads with the code `RESERVE_BREACH_AHEAD`, the badge "A committed cure exists", "Amount at stake",
   the formula, then "Suggested operations: Submit invoice for financing · FAC-IF · RI:BUYER-1:2". The economic consequence
   is discoverable but not stated.
5. **Everything is shown at once.** Formulas, inputs tables, hashes, nonces, state versions, calc versions, prompt
   versions ("Compiled by fixture-cache, prompt offer-v4"), compiler confidence, operation ids and reason codes are in the
   default rendering of nearly every page. There is one disclosure control in the whole app (the approval card's "Show
   details") and one `<details>` in the chat verdict. Density and colour (five badge tones, red, amber, blue, green and
   violet on one screen) make every element equally loud, so nothing is.

Secondary failures, each real but less damaging:

- The healthy state is not calm. After the deal on day 0 the home still shows the clock control, a one-line opener ("Day
  0. 1 warning: Reserve headroom thin on day 30."), five tiles and a Warning card. "You're covered" is never said.
- Abstentions and refusals surface as codes: `NO_VERDICT`, `UNRESOLVED_SCOPE`, `CONFLICTING_SOURCES` as badges, the
  abstention list as "field: reason" bullets.
- "Who has not paid me" has no home: the past-due invoice is a Warning card in the alerts list and a row on the
  Reconciliation page under "Outstanding".
- "What changed" has no home: ledger rows, receipts and alerts are three lists on three pages, none framed as news.
- The chat shows the intent code as its first badge (`SHOW_ALERTS`, `EVALUATE_OFFER`), then the plan with status pills,
  then operations with hashes. It is a trace viewer that also talks.
- Mobile is the desktop stacked. The header is two rows of chips; the stepper is fixed to the bottom and the chat button
  overlaps it; tables scroll sideways inside their region (correct) but the Funding page is 4,439 px tall on a phone.
- Minor: the brand link goes to Mandate; "Cash today" changes label to "Cash in hand today" when a lot is in transit;
  `Leverage, month 1` is cut off by the floating chat button at 1440 px; the alerts note quotes an HTTP route
  ("executed only through POST /alerts/{id}/act").

## 3. Information architecture failures

- **Destination equals module.** The IA is the dependency graph of `services/api/app`. A user's question ("can I afford
  this deal", "who owes me", "what did the agent do") has no page; a module ("Verdict", "Reconciliation") has one.
- **The demo path is the only path.** `lib/demo.ts` defines fifteen steps that navigate across pages; the pages are
  designed to be arrived at from the stepper (Verdict is empty until the stepper or Inbox ran; Funding shows a snapshot
  "as it stood when the decision was made"; Capex is empty until "Evaluate").
- **Three screens for one decision.** A buyer offer is split over Inbox (text and obligations), Trajectory (the cash line
  with the offer), Funding (how the gap would be funded) and Verdict (the decision, the counters, the plan). The owner's
  question is one: "what does this ask cost me and what should I answer".
- **Home is a feed of module summaries.** Six cards, each a window onto one API read (clock, opener, state + trajectory,
  approvals, alerts, ledger), in a fixed order that does not change with the situation.
- **No hierarchy between modes.** Demo controls (clock, reset, scenes, sample messages, buyer personality, attack message,
  evidence download) are peers of owner actions (approve, go ahead).
- **Chinese and English are both module language.** The dictionary translates "Verdict", "Trajectory", "Tier 2" faithfully
  into 裁决, 现金轨迹, 第 2 层; the problem is upstream of translation.

## 4. Screens to delete

- **Today card on the home** (`components/home/today-card.tsx`): the clock is a demo control. It moves to Demo mode.
- **Evidence page as a destination** (`app/evidence/page.tsx`): a JSONL preview with a download button. It becomes a
  section of the Demo story ("the audit trail") and a download link in Activity.
- **The sample-message composer on Inbox** (the "Submit a message" card with the segmented sample picker): a demo
  control. It moves to Demo mode; the Business Deals page receives messages from the buyer channel and the demo.
- **"Done by the agent" as a card**: merged into "What changed".
- **Position tiles for DSCR and leverage on the home**: level 4 for an owner. They stay in Cash & funding under the
  details disclosure, labelled as the reserve-coverage reading the documents require.
- **The "Live API / Mock data" pill, the "Owner" pill and the synthetic-data footer in the Business shell**: demo and
  developer information. They move to the Demo shell (the sign-in state stays as a plain "Signed in / Sign in" control).

## 5. Screens to merge

- **Inbox + Verdict + Trajectory-with-offer + Funding-with-offer → Deals.** One page per buyer ask: what they ask, what it
  costs, the recommendation and the counter, the original message, and the calculation behind a disclosure. The existing
  components (`AnnotatedText`, `ViolationCard`, `CounterCard`, `PlanCard`, `CashChart`, `AutonomyPanel`) render inside the
  disclosure levels, so nothing is rebuilt; they are reordered and hidden by default.
- **Trajectory + Funding + What-if + Capex → Cash & funding.** The cash line first, with the answer above it; then the
  options to cover a gap as a short list (amount, cost, when it lands, needs you or not), then the what-if sandbox and the
  equipment purchase as sections.
- **Reconciliation + the past-due alerts → Receivables.** Who owes what, who is late, what was promised and what arrived.
- **Ledger + Security events + alert history → Activity.** One timeline in business words, with the hash chain, ids and
  codes under "Audit details".
- **Approvals stays**, redesigned as the one place the owner decides.

## 6. Screens to redesign

- **Home**: see section 11.
- **Approvals**: the card leads with the question ("Approve ¥200,000.00 of invoice financing?"), then receive / cost /
  when the money lands / why it needs you / what happens after / what happens if you decline, then the two buttons; ids,
  tier, operation id, terms hash and the clause quotes are under "Audit details".
- **Alerts** become the "At risk" list inside Home and Cash & funding; the alerts page itself remains in Demo mode as the
  engine's view.
- **Chat**: the intent badge, the plan pills and the operation hashes move behind "Details"; the reply, the confirmation
  buttons and the clarification options stay.
- **Mandate → Limits**: a read-only page in business words ("The agent may borrow alone up to 15.00% a year; it must keep
  ¥300,000.00 in cash; it may give away at most ¥5,000.00 of future concessions") with the signature and tiers under
  details.
- **Mobile**: status, next action and approvals first; the navigation becomes a top bar with a menu; no fixed stepper in
  Business mode.

## 7. Terminology problems

Every term below appears in the default rendering. Decision per term: rename, explain, hide, or keep for finance users.

| Term as shown | Where | Decision |
| --- | --- | --- |
| Reserve floor, floor | Home, Trajectory, alerts | Rename to **safe cash level** in labels; keep "reserve" in server sentences (the documents use it). |
| Lowest projected cash | Home tile | Explain: "Lowest cash ahead, day N" and lead with the sentence above it. |
| Trajectory | Nav, page | Rename: **Cash & funding**; the chart is "Cash ahead". |
| Conservative mode (decides), Expected mode | Trajectory, alerts basis | Hide in Business (always the deciding view); keep the toggle in Demo with the note. |
| Forward concession, forward-concession meter, concession exposure | Trajectory, Verdict, Ledger | Rename in labels to **future give-aways** with the cap; keep "forward concession" in the calculation level. |
| Headroom | Alerts | Explain: "Cash stays above your safe level by only ¥X on day N". |
| DSCR, leverage | Home tiles, Trajectory table, Capex | Hide from Home; keep in Cash & funding details as "Debt service cover (reserve-coverage reading)" and "Debt to earnings", with the limits. |
| Committed cure, cure | Alerts, opener | Rename: **the fix**, "a fix the agent can run"; keep "cure" in server text. |
| Tier 1 / Tier 2 / Tier 3 | Everywhere | Hide at level 1; replace with "the agent can do this alone" / "needs your approval" / "only you can do this"; show the tier under Audit details. |
| All-in APR, annualised, effective annual cost | Funding, approvals | Keep for finance users as "yearly cost rate", always next to the cost in yuan. |
| Obligation, compiled, compiler, prompt version, confidence | Inbox | Rename "obligation" to **what the buyer asks for**; hide compiler, prompt version and confidence under details. |
| Verdict, REJECT / COUNTER / ACCEPT | Verdict, chat | Rename to **Recommendation: decline / counter / accept**; keep the outcome code under details. |
| NO_VERDICT, UNRESOLVED_SCOPE, CONFLICTING_SOURCES, abstention | Verdict, chat, Inbox | Replace with "I can't safely evaluate this yet" plus the question; code under details. |
| Current books | Docs, chat | Hide; say "on today's books" only in server text. |
| Commitment, nonce, terms hash, state version, calc version, mandate version | Verdict header, Ledger, negotiation card | Hide under Audit details. |
| RESERVE_BREACH_AHEAD and every reason code badge | Alerts, Verdict, Funding, Ledger | Hide at level 1; show under "Why" with the sentence first and the code last. |
| FAC-IF, FAC-LINE, RCV-A, RI:BUYER-1:2, BUYER-1 | Everywhere | Replace with the facility name, the invoice ("the ¥420,000.00 invoice to Foshan Home Retail Co.") and the buyer name; ids under details. The API already sends names in `state.facilities` and `state.counterparties`. |
| Mandate | Nav | Rename: **Limits** ("what the agent may do alone"). |
| Ledger, hash chain, evidence, JSONL | Nav, pages | Rename: **Activity**; the chain and the export are "Audit trail" details. |
| Opener, "the agent's opening message" | Home | Hide; the message is simply the recommendation. |
| Go ahead / Not now | Home, chat | Keep; add "Review" before it on the home so the owner sees the figures before the button. |
| Day N | Everywhere | Keep (the simulation has no calendar), but always with a distance: "day 42 (8 days from now)". Needs a server string. |

## 8. Navigation problems

- Fifteen entries; an owner needs six. "Chat" is a page and a slide-over; "Verdict", "Funding" and "Trajectory" are three
  views of one decision; "Alerts", "Approvals" and the home's "What needs you" overlap; "Security", "Evidence" and "Ledger"
  are three views of the audit trail.
- The sidebar groups are "screens" (unlabelled) and "Owner and audit", which is not a user distinction.
- The active page is not always the page the stepper shows (steps 5 and 6 both land on Verdict, with a hash scroll).
- No breadcrumb or back link from a detail (a deal) to its list; the demo store decides which offer is "current".
- The brand link opens Mandate.

## 9. Owner vs demo collisions

| Collision | Where |
| --- | --- |
| The stepper bar on every page, fixed to the bottom on phones | `components/app-shell.tsx` |
| The clock control as the first card of the owner's home | `components/home/today-card.tsx` |
| The sample-message picker and composer on the owner's inbox | `app/inbox/page.tsx` |
| "Run the negotiation" with a buyer-personality switch inside the verdict | `app/verdict/page.tsx` |
| "Run the FastCapital scene" as the primary action of Security | `app/security/page.tsx` |
| "Live API" / "Mock data" pill and "Synthetic fixture data" footer | shell |
| Demo-step copy as the page's framing ("5/15 Verdict: REJECT with two counters") | stepper |
| A failed step's error shown in the stepper bar on whichever page the owner is on | stepper |

## 10. Missing user questions

The brief's three questions are not answered at the top. Of its candidates, these earn a place on the home:

- **What needs my approval?** Yes: the queue count and the first item, as a question. (Exists as a card; needs language.)
- **Who has not paid me?** Yes: past-due invoices by buyer name and days late, and the next expected receipt. (Exists only
  as an alert and a reconciliation row.)
- **What changed?** Yes: receipts, late payments, executed operations, new commitments, since the last visit. (Missing: the
  API has the ledger and the receipts but no "since" view.)
- **What happens if I do nothing?** Yes, as part of the recommendation: "cash falls ¥200,000.00 below your safe level on
  day 42". (The alert detail has it; it needs a label.)
- **What commitment is consuming my liquidity?** Only when there is one: the live commitments with their cash effect, in
  Deals. (The ledger has them with a forward value; no cash effect per commitment is available and none will be computed in
  the browser.)

Not added: covenant ratios, the funding menu, the concession meter, the hash chain. They exist, but they are answers to
questions an owner asks only after the first three.

## 11. Proposed new information architecture

Two modes, chosen with one switch in the header and remembered: **Business** and **Demo**.

**Business** (the product): top navigation of six sections, in the reference's style.

| Section | Route | Question it answers | Built from |
| --- | --- | --- | --- |
| Home | `/` | Am I safe, what should I do, what does it cost, what needs me, what changed | new `GET /home` (section 14) + approvals + alerts |
| Deals | `/deals` | What is the buyer asking, what does it cost me, what should I answer | offers, verdicts and negotiations of the session; the existing verdict components under disclosure |
| Cash & funding | `/cash` | When does cash become unsafe, what are my options, what would a change do | trajectory, router plan, what-if, capex |
| Receivables | `/receivables` | Who owes me, who is late, what was promised, what arrived | reconciliation, state receivables |
| Approvals | `/approvals` | What requires my decision, exactly | approvals queue with the new presentation fields |
| Activity | `/activity` | What happened, what did the agent do, what was refused | ledger, audit, alerts history |

Plus **Limits** (`/limits`, from the account menu), the chat slide-over ("Ask the agent") on every page, and sign-in.

**Demo** (for judges): a different shell. The story page `/demo` lists the fifteen steps as the brief's narrative (buyer asks
→ read → consequences → recommendation → commitment → time passes → late payment → unsafe cash → detection → funding →
approval → landing → payment → reconciliation → audit trail), with Start, Next, Back, Reset, the clock, the scenario
switch (golden books / short facilities), the buyer channel, the attack message and the evidence download. The stepper
bar stays in this shell only. The existing engine pages (Mandate, Inbox, Trajectory, Funding, Verdict, What-if, Capex,
Ledger, Alerts, Reconciliation, Security, Evidence) remain reachable from the Demo navigation as the "engine views": they
are the level-4 evidence a judge wants and they already work.

Rule for the stepper: it renders only in Demo mode. The demo walk visits Approvals (a Business route) at step 13; in Demo
mode that page keeps the Demo shell, so the walk is unbroken.

## 12. Proposed Business home

Top to bottom, each block one server answer, no card chrome between the first three:

1. **Status**: a word (SAFE, WATCH, ACTION NEEDED, CRITICAL) and one sentence. "Cash falls ¥200,000.00 below your safe
   level of ¥300,000.00 on day 42, 8 days from now." or "Cash stays above your ¥300,000.00 safe level for the next 90
   days." Beneath it, three small figures: cash today, safe level, lowest cash ahead (with its day). No chart.
2. **Best next action** (only when one exists): "Finance ¥200,000.00 of the ¥420,000.00 invoice to Foshan Home Retail
   Co." Receive ¥200,000.00 · Cost ¥1,782.19 (32.5% a year for 10 days) · Money lands day 37 · Needs your approval
   because the yearly rate is above your 15.00% limit · If you do nothing: ¥200,000.00 below your safe level on day 42 ·
   After: cash stays above your safe level. Buttons: **Go ahead** (queues it when it needs approval, runs it when it does
   not; the label says which) and **See alternatives** (Cash & funding). "Why" and "Calculation" are disclosures.
3. **Needs your decision**: each pending approval as a question with the amount and cost, and an Approve / Decline pair
   that opens the full card (never a one-click approve from the home).
4. **What changed**: receipts, late invoices, executed operations, new commitments, funding that landed, in sentences the
   server already writes, newest first, at most five.
5. **Receivables**: who has not paid (name, amount, days late) and the next expected receipt.
6. **Details** (collapsed): the cash chart with the fix as a dashed line, the debt service cover and debt-to-earnings
   readings with their limits, the facilities and what is drawn.

Healthy state: block 1 says "You're covered" with the sentence, block 2 is absent, block 3 says "Nothing needs your
decision", block 4 shows the last few things that happened, block 5 shows the next receipt. The page is short.

## 13. Proposed Demo flow

The story page, in the brief's order, each step with one sentence of what the judge will see and a "Show me" that runs the
step and opens the engine view the current stepper opens. The clock, the bank receipt and the approval are steps in the
story, not controls the judge has to discover: "Day 34: the buyer is late" advances the clock and reports the receipt the
way `scripts/record-mocks.mjs` and `scripts/demo_run.py` do. The security scene and the evidence download close the story.
The Business switch is always one click away so the judge can see the product the owner sees after each step.

## 14. High-priority changes (in implementation order)

1. **Mode split** (P0): a persisted mode, two shells, the stepper only in Demo, a `/demo` story page, the clock and
   reset moved there, the Business top navigation.
2. **`GET /home`** (P0, backend presentation field): one owner read that returns the status word, the headline sentence,
   the three figures, the best next action (from the actionable alert and its priced suggestion, with the landing day and
   the after-state), the pending approvals with a headline each, the recent changes, the receivables summary and the
   next receipt. Every string is written by the server from the engine's existing results; the engine is not changed.
3. **Business home** (P0) on that read.
4. **Approval card** (P0): the question, receive / cost / lands / why / after, audit details collapsed. Needs
   `headline`, `cost_display`, `lands_day` and `after` on the queue row (backend presentation fields).
5. **Deals** (P1): the business view of an offer with the existing components under disclosure; the original message as
   a disclosure; abstentions in words.
6. **Cash & funding** (P1): the answer, the chart, the options list, the what-if and capex sections.
7. **Receivables and Activity** (P1).
8. **Terminology** (P1): the dictionary changes of section 7 across both modes where the term is a label.
9. **Mobile** (P1): the top bar, the order of blocks, no fixed stepper in Business.
10. **Mocks, specs and documents** (gate): re-record with `pnpm mocks:record`; rewrite `home.spec.ts` and
    `responsive.spec.ts` for the new routes; keep `demo.spec.ts`, `chat.spec.ts`, `alerts.spec.ts`, `whatif.spec.ts`,
    `approvals.spec.ts`, `catchup.spec.ts`, `contract.spec.ts`, `live.spec.ts` green with the golden figures.

## 15. Low-value or do-not-build changes

- A calendar instead of day numbers: the simulation has no dates; a fake calendar would be false precision.
- Sparklines on the KPI tiles (the reference has them): there is no history series on the server for cash today, and the
  browser will not build one from the ledger.
- Period comparison ("vs previous period"): no previous period exists in a simulation that starts on day 0.
- Animations, transitions, a dark theme: P2 by the brief's own order.
- Rewriting the chat as a chat product: the slide-over stays as the owner's way to ask; the trace details move behind a
  disclosure.
- Recomputing anything in the browser (headroom, days to breach, after-state, cost totals): forbidden by INVARIANT 13 and
  the brief's section 22; every new number comes from `GET /home` or an existing read.
- Removing the engine views: judges need them, and the specs and documents quote them. They move to Demo mode, they are
  not deleted.
- Changing the alert, verdict or approval semantics: the engine is in stability mode. The redesign presents; it does not
  decide.

## 16. What is already good and must survive

The server already writes most of the sentences the new home needs: the opener names the buyer, the amount, the day it
lands, the cost, the rate and why it needs approval; the alert carries the cost, the rate and "needs your approval" before
any click; the approval reason names the ceiling; the executor's result says when the cash lands. The annotated source text
with numbered spans is the right level-4 view of a message. Every page has loading, error and empty states; owner actions
open a sign-in dialog on 401; the chat retries safely; no page overflows horizontally on a phone; the palette is calm; the
labels are bilingual in one file. The redesign keeps all of it and changes where it is shown and in what order.

## 17. After implementation (5 Oct, `feat/ux-redesign`)

**Before vs after.** Before: one shell, fifteen navigation entries named after engine modules, the stepper bar and the
clock control on the owner's screens, a home of six cards whose answer was inside a 70-word paragraph, approval cards
titled with the operation and the facility id, formulas and codes at level 1 on every page. After: two shells chosen in
the header. Business: six sections named after questions (Home, Deals, Cash & funding, Receivables, Approvals, Activity,
plus Limits), no clock, no stepper, no mock pill. The home opens with a status word and one sentence ("Cash falls
¥200,000.00 below your ¥300,000.00 safe level on day 42 (in 8 days)."), then the best next action with what the owner
receives, the cost and its yearly rate, the day the money lands, who decides and why, what happens if nothing is done and
the after-state, then what needs a decision as questions, what changed, who has not paid, and the details behind one
disclosure. Approval cards ask "Approve ¥200,000.00 of invoice financing?" with amount, cost, landing day, source,
invoice, why, after, and what declining does; ids, tier and terms are under Show details. Demo: the story page with the
fifteen steps, the clock, the scenario switch and the side doors; the story bar on every page; the engine views unchanged.
On a phone the first screen holds the status, the sentence and the three figures; the next action follows.

**Key UX decisions.** The mode is a persisted choice, and running a story step switches it on, so the demo walk keeps its
bar on the approvals page. The engine views were kept, not deleted: they are the judge's level 4 and the specs and
documents quote them. Every new sentence is written by the server (`GET /home`, the queue's `presentation`), so the
browser still computes nothing. The home's "Go ahead" is the same bound act as the alerts page; when the cost is above the
owner's limit the button says "Queue it for my approval" and the server queues. The cash chart is on Cash & funding, not
the home: the home gives the answer, the chart proves it. Day numbers stay, with a distance in days.

**Files changed.** Backend: `services/api/app/api/home.py` (new), `app/api/presentation.py` (new), `app/api/operations.py`
(the queue's `presentation` fields), `app/main.py`, `tests/api/test_home.py` (new). Web: `components/app-shell.tsx` (two
shells), `lib/mode.ts`, `lib/demo-control.ts` (new), `components/demo-stepper.tsx`, `app/demo/page.tsx` (new),
`app/page.tsx` and `components/business/*` (new home), `components/approval-card.tsx`, `app/deals`, `app/cash`,
`app/receivables`, `app/activity`, `app/limits` (new pages), `components/home/today-card.tsx` (moved to the story page),
`lib/types.ts`, `lib/api.ts`, `lib/live/*`, `lib/mock/*`, `lib/dictionary.ts` (English and Chinese), `scripts/record-mocks.mjs`,
seven new mock recordings and the re-recorded approvals, `e2e/home.spec.ts`, `catchup.spec.ts`, `responsive.spec.ts`
(rewritten), `approvals.spec.ts` and `demo.spec.ts` (wording). Documents: this file, `apps/web/README.md`,
`docs/SYSTEM_WALKTHROUGH.md` section 6, `docs/ARCHITECTURE.md`, `docs/HANDOVER.md`, `docs/CONTINUOUS_OPTIMIZATION.md`
(UX1), `docs/NEXT_FIXES.md`, `README.md`.

**API changes.** `GET /home?lang=en|zh` (owner): status, headline, note, cash figures, next action, approvals, changes,
receivables, warnings, facilities. `GET /approvals/queue`: each row gains `presentation` (headline, what, facility and
buyer names, invoice, cost, rate, cost due day, landing day, protects, reason and result in business words).
`POST /demo/reset?scenario=` is now reachable from the story page. No engine module changed.

**User task results** (the brief's section 24, on the day-34 books, live mode): A "Is this business going to run out of
money?": the status word and the sentence, first screen. B "What should I do?": the best next action, one block. C "How
much does that option cost?": the Cost row, with the yearly rate. D "Why are you recommending this?": "Why this", one
click. E "What happens if I do nothing?": the "If you do nothing" row, visible. F "What requires my approval?": "Needs
your decision", with the question. G "Who has not paid me?": "Who owes you", by name with the days late. H "What changed
since yesterday?": "What changed", the last week. I "Show me the actual calculation": "Show the calculation" and the
engine views. J "Run the hackathon demo": the Demo switch and the story page.

**Responsive results.** Pixel 7 project: no horizontal overflow on any of the seven Business routes nor the twelve engine
routes after the demo; the status and the headline are in the first viewport; the chat slide-over fits. The macOS-only
431 px measurement of the slide-over was not reproduced on Linux Chromium.

**Remaining UX debt.** The engine views keep their old density by design, and the Demo nav still names them by module.
The chat turn still opens with the intent badge and the plan pills. The Deals page lists the session's latest offer only.
"What changed" has no "since my last visit" marker, only the last week. The server's sentences carry ids in a few places
(an invoice id such as RI:BUYER-1:2 inside the executor's message), replaced by names where the books know them.
Terminology inside the engine views (Tier, DSCR, forward concession) is unchanged there.

**Deliberately not built.** A calendar, sparklines and period comparisons (no history series exists in a simulation that
starts on day 0), animations, a dark theme, any money arithmetic in the browser, any change to alert, verdict or approval
semantics, removal of the engine views, a rewrite of the chat.


## 18. The integration of 6 and 7 October (`feat/ux-integration`, Waves 1 to 8)

The owner's fourth brief (6 Oct) asked for the best of `dev` and `test/ui-ux`, feature by feature, with financial presentation
truth first. The decisions and the comparison are in `docs/UX_INTEGRATION_BRIEF.md`; the work was charted and resolved as the
wayfinder map, GitHub issue #13 (one ticket per wave, each closed with its files, tests and follow-ups). In short:

- **One canonical trajectory and an all-in cost.** `GET /home` now carries the projection it quotes (`cash.series`, and
  `cash.plan_series` with the recommended plan applied); the Cash & funding chart draws only these and its axis goes below
  zero, so the −¥105,000 trough on day 30 is visible under the headline that quotes it. The recommendation is the router's
  cheapest runnable plan priced all-in on the router's own convention (`app/funding/recommend.py`; day 0: ¥405,000 at
  ¥3,113.93, the figure the documents quote), the alert's cure when the router has none, and the single-approval cure when the
  cheaper plan would need several approvals (day 34), with the cheaper option named. "Run funding plan" binds to the legs shown
  (`POST /alerts/{id}/act` accepts the recomputed router plan). An independent agent checked every figure against the golden
  values and the router.
- **Business language.** Distances from today instead of "Day N" (server `*_when` strings, `relative_days`, a counting helper in
  the browser), "minimum cash reserve" instead of "safe cash level", authority as the owner's signed limits, one Demo data pill
  instead of a footer on every page; Demo mode keeps "Day N" and the engine views.
- **The home as one decision story.** Conclusion first ("Your cash reserve becomes unsafe in 12 days."), the detail, the worst
  point, three short figures, what is driving it from the projection's own events, then the recommendation led by its outcome
  ("Secure ¥405k of funding") with components, estimated total cost and its lines and basis, funds available, lowest cash after
  action, the authority line and buttons that say what they do; empty sections are hidden; "You're covered." when healthy;
  changes since the owner's last visit.
- **Cash & funding** in the owner's order (risk, plan, options in business names, forecast) with the `test/ui-ux` chart ported
  onto the home's series (danger zone, annotations, 30 / 60 / 120 horizon) and the facility explainer. **Receivables** leads with
  outstanding, overdue and the next payment; the early-payment and payments-received sections appear only with data.
- **Navigation and header.** Home · Deals · Cash & funding · Receivables · Activity; Approvals is a header badge present only
  while something waits; one account menu; the brand is FLOW 流 · AI working-capital agent (the TermsLedger engine behind it).
- **Deals, Approvals, Activity.** Consequence first on Deals with the `test/ui-ux` glance, step and next-step bars, simulated
  inbox and active commitments; approval buttons name the amount and "If you decline" is a server sentence; Activity leads with
  the executor's sentence. From the delegation handoff: the chat turn answers first, the Deals offer list, invoice ids in words,
  the DSCR reading label, the engine-view terminology, the intake cap and the benchmark target.

Taken from `test/ui-ux`: the cash chart, the Verdict glance, the Next step bar, the deal step bar, the simulated inbox, the
plain names for rule codes, alert kinds and operations, the tier-badge removal, the plain-sentence agreements, the facility
explainer, the Segmented wrap fix. Left behind: the single shell, the `/simple` fourth home, the capex card and the clock on the
home, `/documents` (fog on the map). Remaining debt is listed on the map's open items and in `docs/UX_INTEGRATION_REPORT.md`.
