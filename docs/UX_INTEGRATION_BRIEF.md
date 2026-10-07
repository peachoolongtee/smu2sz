# UX integration brief: `dev` × `test/ui-ux` → the final Business + Demo experience (6 Oct 2026)

The deliverable the owner's fourth brief asks for before large-scale editing (section 40 of the brief: branch state, feature
comparison, P0 truth check, information architecture, hierarchies, ports, deletions, API gaps, implementation order). Made on
`dev` at `53cd1cc` and `origin/test/ui-ux` at `f59149b`. The work itself is charted as a wayfinder map on GitHub (label
`wayfinder:map`, "Wayfinder: Business + Demo UX integration"); each wave is a child ticket. Integration happens on
`feat/ux-integration` (worktree `.claude/worktrees/ux-integration`), branched from `origin/dev`, merged into `dev` with `--no-ff`
when the gate is green. Nothing from `test/ui-ux` is merged wholesale.

## A. Branch state

| Branch | Head | What it holds |
| --- | --- | --- |
| `dev` (= `origin/dev`) | `53cd1cc` | The 5 Oct UX redesign (`feat/ux-redesign`): two shells (Business, Demo), `GET /home`, approval `presentation` fields, Deals, Cash & funding, Receivables, Activity, Limits, the story page `/demo`; mocks re-recorded; engine unchanged |
| `origin/test/ui-ux` | `f59149b` | 15 commits by haoencheo2025, 4 to 6 Oct, from the owner's 5 Oct review ("isaac feedback"): plain-word dictionary rewrite (labels, rule names, operation names), tier badges removed, Next step bar, deal step bar, Verdict glance, simulated Inbox with source and sender, `/documents`, `/simple` owner overview (cash chart with danger zone, buyers, agreements, borrowing options), capex form on home, glossary, `docs/UI_UX_CHANGES.md` |
| `origin/ui-ux-testing` | `698f362` | `test/ui-ux` plus one commit "k" (ignored) |
| `main` | `beb8c66` | 212 behind `dev`; checkpoint only |
| common ancestor | `bac61f3` (3 Oct, "Scorecard: web e2e after the refresh") | the pre-redesign web app, one shell, fifteen engine views |

`dev` has 9 commits since the ancestor; the redesign touched 47 web files and 3 API files. `test/ui-ux` touched 50 files
(4,425 insertions), all under `apps/web` plus `docs/UI_UX_CHANGES.md` and one README line. **Files modified by both** (the
conflict zone): `apps/web/app/page.tsx`, `components/app-shell.tsx`, `components/approval-card.tsx`, `lib/dictionary.ts`
(1,519 changed lines on one side, the `biz.*` namespace on the other), `lib/types.ts`, `lib/mock/handlers.ts`, and the specs
`approvals`, `catchup`, `demo`, `home`, `responsive`. A plain `git merge` would conflict in every one of them and would put the
old single shell back; the two branches implement opposite shells. Hence manual transplant, feature by feature.

Risk areas: the dictionary (both sides renamed the same keys differently; `test/ui-ux` also renamed engine-view titles that the
Demo nav and `demo.spec.ts` still quote), the home (`test/ui-ux` adds cards to the old home that no longer exists on `dev`), the
mocks (`test/ui-ux` hand-edited `handlers.ts` for capex; `dev` re-recorded everything), and `responsive.spec.ts` (the two
branches list different routes). No backend file is touched by `test/ui-ux`. No other branch is active on `apps/web`.

## B. Feature comparison

| Feature | Current (`dev`) | `test/ui-ux` | Final choice | Why |
| --- | --- | --- | --- | --- |
| Business / Demo separation | Two shells, persisted mode, stepper and clock only in Demo | One shell, sidebar of 17 links grouped by job, stepper on every page, "Demo clock" card on the home | **Keep current** | The brief's P0; the one-shell model is the thing the 5 Oct audit removed |
| Home hierarchy | One read (`GET /home`): status word + sentence, best next action, decisions, what changed, receivables, details | Nine cards: agent message, waiting, position (with a plain headline), agreements, capex form, warnings, done, clock, glossary | **Keep current, redesign** into one causal story (section E) | The current order is right; the cards still read as independent; `test/ui-ux` returns to a feed |
| Cash-risk sentence | "Cash falls ¥240,000.00 below your ¥300,000.00 safe level on day 12 (in 12 days)." | "Heads up: cash is forecast to drop below your safety minimum on day N, by up to ¥X" | **Redesign** (conclusion first, server strings) | Both need arithmetic; the brief's wording is better than either |
| Recommendation card | Operation sentence as title, receive / cost / lands / authority rows, if-nothing, after, why, calculation | Agent's chat opener with Go ahead | **Keep current structure, rewrite language**, all-in cost (section C) | The structure answers the brief's list; the title and the cost are wrong |
| Cash chart | `CashChart`: line, y axis from 0 (negative cash is clipped), 120 days, "Cash with committed cure", floor line, breach dot | `SimpleCashCard`: area with danger zone, y axis extends below zero, breach marker, lowest-point dot, event tooltip, weekly table for screen readers, colour-coded figure boxes as legend | **Take from `test/ui-ux`**, then add owner-language series, event annotations, 30/60/120-day horizon | It is the better chart and it renders the negative trough the headline quotes |
| Funding comparison | Router comparison list, "Router optimum" label, calculation under details | Borrowing options by availability with plain "what / good for / watch out" per facility kind | **Combine**: ranked options in plain names on Cash & funding; the facility explanations as a disclosure | Both are partial; the ranking must be the engine's |
| Deals flow | One page, latest offer only: ask → recommendation → why / calculation / original | Inbox simulation (WeChat / Email, company, contact), step bar, Next step bar, Verdict glance (asked / why not / offer back), rule cards with figures folded, plain rule names | **Combine**: keep the Deals page; port the glance, the Next step bar, the plain rule names and the inbox list as the Deals list | Each `test/ui-ux` piece reduces load; the Inbox gives Deals a list it lacks |
| Receivables | Three cards, two usually empty ("Promised early payments — none", "What arrived — none") | None (Reconciliation renamed "Payments received") | **Redesign** (section G) | The weakest current page |
| Approvals | Card as a question with cost, lands, source, why, after, if-decline; ids under details | Tier badges removed everywhere; approve / turn down from the agreements card | **Keep current, take the tier removal**; no one-click approve outside the card | The card already answers the brief's eight questions |
| Activity | Timeline in the executor's sentences with names; chain status; refused list | Ledger with plain operation names ("Borrow from a credit line") | **Combine**: take the plain operation names; lead with the sentence | Human-readable first, hashes under details (already so) |
| Navigation | Top bar: Home, Deals, Cash & funding, Receivables, Approvals, Activity | Sidebar: 17 links in four groups with hover hints | **Keep current; move Approvals to a header badge** (test both, section D) | Approval is an attention state |
| Header | Business / Demo, Owner pill, Sign out, English / 中文 | Live / Mock pill, Owner, Sign out, language | **Redesign**: mode switch + account menu | Too administrative on both |
| Branding | "TermsLedger — Terms Guard + Debt Desk" | same | **Redesign**: one product, "AI working-capital agent"; name pending the owner (ticket) | Two module names describe the old product |
| Chat launcher | Slide-over on every page | same | **Keep** | |
| Responsive | Phone project green except the macOS slide-over width | `Segmented` wraps instead of overflowing | **Keep current, take the wrap fix** | |
| Empty states | Full cards saying "nothing" | Empty "Waiting for you" shrinks to one line | **Take the principle, go further**: hide, or one line when the absence is the news | Brief section 15 |
| Loading / error | Skeletons, `ErrorState` with retry, sign-in on 401 | same | **Keep** | |
| Demo controls | Story page: steps, clock, scenario switch, doors | Clock card on the owner's home | **Keep current** | |
| Terminology | "safe cash level", "the agent can do this alone" | "Safety minimum (reserve floor)", "Needs your OK", plain names for 38 rule codes, 16 alert kinds, 18 operations; glossary | **Combine**: "minimum cash reserve" (section 9 of the brief), plain rule / alert / operation names from `test/ui-ux`, mandate language for authority | |
| Capex on the home | Not on the home; a door on Cash & funding | Form and result card on the home | **Leave behind on the home; take the form** into `/capex` and the Cash & funding section | A calm home has no calculator |
| `/simple` overview | n/a | A fourth home | **Remove**; its chart and borrowing card are ported | Three homes is the problem, not the fix |
| `/documents` | n/a | Owner uploads text documents; offers are read and checked | **Fog** (not in this map's first pass) | A real owner need, but intake belongs in Deals; needs its own decision |
| Agreements in plain sentences | n/a | `obligationSentence` for every obligation type; promised payments progress | **Take** for the "Active commitments" view in Deals (brief section 27) | |
| API presentation fields | `GET /home`, queue `presentation` | none | **Keep and extend** (section L) | |

## C. P0 truth check

**1. The chart and the headline disagree: real, and it has two causes.**

- *Mock data mixes two trajectories.* `scripts/record-mocks.mjs` line 170 records `trajectory_conservative.json` as
  `getTrajectory("CONSERVATIVE", verdictEx01)`: the projection **with the EX01 offer applied** (early settlement of RCV-A on
  day 2 at 1.2%; first breach day 47; lowest ¥164,960 on day 60). `home_summary_day0.json` is today's books (first breach
  day 12; lowest −¥105,000 on day 30). The Business Cash & funding page plots the first and quotes the second. In live mode the
  page calls `getTrajectory("CONSERVATIVE")` without a verdict, so live is consistent; every screenshot from mock mode is not.
  (`trajectory_expected.json`, recorded the same way, happens to match the home because the expected mode ignores the offer.)
- *The chart cannot draw the trough.* `components/charts.tsx` sets the y domain to `[0, "auto"]`, so a projection that goes to
  −¥105,000 is clipped at zero even in live mode. The `test/ui-ux` chart extends the axis to `min(0, min_cash)`.
- Fix: one canonical series. `GET /home` already projects the trajectory it quotes; it will carry that series (closing cash,
  display string and events per day, plus the same series with the recommended plan applied) and the Cash & funding page
  will draw **that**, so headline, first unsafe day, lowest point, chart and after-state come from one projection. The
  trajectory mock is re-recorded from the engine views only.

**2. The recommended cost excludes a material part of the plan: confirmed, and the plan itself is not the cheapest.**

- `app/alerts/engine.py` `_cure_costs`: the cure's total is `None` whenever a credit-line draw posts no interest, which is
  the case here because the projection carries the draw open (nothing repays a line unless the owner does; ADR-0006). The home
  then falls back to the first priced leg: **¥2,994.08**, the invoice-financing fee alone, with the footnote "Interest on the
  Bank credit line draw is not included".
- The same day-0 gap (¥405,000) is priced by the router (`POST /router/plan`, shown as "Other options" on Cash & funding and
  quoted by every deliverable: `docs/DEMO_FLOW.md`, the technical document, the deck outline, the video script) as **line
  ¥150,000 (¥841.64, repaid day 32) + advance ¥255,000 (¥2,272.29) = ¥3,113.93**. The home's cure is **line ¥150,000 + advance
  ¥336,000 = ¥486,000**: `committed_cure` is a greedy feasibility search that keeps each source at its maximum (¥336,000 is the
  80% advance cap on the ¥420,000 invoice) and right-sizes only when one source remains. Priced on the router's repayment
  convention it would cost about ¥2,994.08 + ¥841.64 = ¥3,835.72, more than the router's plan, while the home's `why` string
  says "The cheapest committed funding that covers the whole gap in time".
- So the home, the chat opener and the alert recommend one plan (¥486k, "¥2,994.08") and the Cash & funding options, the demo
  script and the documents show another (¥405k, ¥3,113.93) as the optimum. This is the contradictory-figures failure the brief
  warns about, and it predates both branches.
- Fix (a product-policy decision, ticketed as a grilling with a recommendation): the Business recommendation should be the
  router's cheapest runnable plan when one exists (it is already "the standing plan the agent can run"), with every leg priced
  on the router's stated repayment convention and the basis said in words ("estimated through the expected repayment on day
  32"); the alert's cure remains the engine's feasibility proof. If the owner prefers to keep the alert cure as the executed
  action, the minimum is: price the draw on the same convention, show the all-in total with the breakdown, and drop the
  "cheapest" claim. Either way the number on the card and the number in the options list must be the same number.

**3. Smaller truth defects found on the way.** The Cash & funding page reads `getHome("en")` regardless of the language
switch. The reserve-headroom warning and the "lowest cash ahead" figure use the day-0 trajectory while the chart used the
offer-applied one (same cause as 1). `biz.ifDecline.body` is a static dictionary sentence, not the server's.

## D. Final information architecture

**Business** (the product). Top navigation: **Home · Deals · Cash · Receivables · Activity**. Approvals leave the bar and become
a header badge ("2 approvals") that appears only when something waits and opens `/approvals`; the route stays, the badge is the
destination. Both models are tested in Wave 6 on the day-34 books (one approval) and the quiet books (none); if the badge is
missed in the cold-user pass, Approvals returns to the bar. Header, left to right: brand (one product name + "AI working-capital
agent"), navigation, then Business / Demo, the approvals badge, one account menu (signed-in state, sign out, language). One
discreet global indicator "DEMO DATA" in the Business shell replaces the per-page simulation footer; the long simulation
sentence moves to the account menu and the Demo shell.

**Demo** (for judges). Unchanged shape: the story page, the clock, the scenario switch, the story bar, the engine views under
"Engine". Day numbers, codes, formulas and the Live / Mock pill stay here.

Dates: the simulation has no calendar, and the 5 Oct audit ruled a fake one out. Business mode therefore never says "Day 12";
it says **"in 12 days"**, "today", "tomorrow", "N days late", "N days ago" (the server already writes these distances; the UI
may count days, never money). Demo mode keeps "Day N".

## E. Home hierarchy

One continuous story, three blocks that read as one, then only what exists:

1. **Status**: the word (ACTION NEEDED / WATCH / YOU'RE COVERED / CRITICAL) and the conclusion: "Your cash reserve becomes
   unsafe in 12 days." Under it, three figures with no decimals: cash at first breach ¥60k · minimum cash reserve ¥300k ·
   worst point −¥105k in 30 days. Then **What changed**: at most two causes written by the server from the projection's own
   events before the breach ("Payroll of ¥340k falls due in 12 days, before the Foshan invoice is paid"; "The equipment-loan
   payment of ¥45k is due in 30 days").
2. **Recommended**: the business outcome as the title ("Secure ¥405k before 12 days from now"), the components as two short
   lines (¥150k credit line · ¥255k against the Foshan invoice), then estimated total cost with its basis, funds available
   (in 3 days), lowest cash after action, and the authority line ("Within your signed limits. No additional approval
   required." or "Needs your approval: the yearly cost is above your 15% limit."). Buttons: **Run funding plan** / **Queue
   for my approval**, and **Compare options** (Cash). Disclosures: Why this plan · View cash forecast · Show calculation.
3. **Needs your decision**: only when the queue is not empty; each item a question with cost and landing, opening the card.
4. **Receivables**: who has not paid (name, amount, days late) and the next expected receipt; one line when nothing is late.
5. **Recent changes**: receipts, landings, executed operations, newest first; absent when empty.
6. **Details** (closed): in transit, warnings, facilities, debt readings.

Healthy state: block 1 says "You're covered. Cash stays above your ¥300k reserve for the next 120 days. Next expected receipt:
¥420k from Foshan Home Retail in 32 days."; blocks 2 and 3 are absent; the page is three short blocks.

## F. Cash & funding hierarchy

1. **Cash risk**: the same conclusion as the home (short by ¥240k, unsafe in 12 days, worst −¥105k in 30 days).
2. **Recommended plan**: amount, all-in cost, arrival, after-state, authority; the same figures as the home.
3. **Other options**: the router's comparison ranked by total, in plain names ("Take the buyer's 1.2% discount", "Credit line
   only"), each with its total, why it loses, and whether it needs the owner; the facility explanations and the full menu under
   a disclosure.
4. **Forecast**: the chart from `test/ui-ux`, series named "If you do nothing" and "With the recommended plan", the reserve as
   "Minimum cash reserve", a shaded danger zone, annotated events (Payroll −¥340k, Funding lands +¥405k, Foshan invoice
   +¥420k, Loan payment −¥45k), horizon 30 / 60 / 120 days with 60 as the default when the first breach is within 60 days.
5. **What-if** and **Equipment purchase** as doors; the monthly readings closed.

## G. Receivables hierarchy

1. **Summary**: ¥420k outstanding · ¥0 overdue · Next payment: Foshan Home Retail, ¥420k, due in 32 days.
2. **Invoices**: buyer, amount, due (relative), status; late rows first; the invoice id in small type.
3. **Expected early payments**: only when a live promise exists (awaited, received, lapsed).
4. **Payments received**: only when a receipt exists; bank reference under the row.

## H. Approval UX

Keep the card: the question as the title ("Approve ¥200k of invoice financing?"), amount, estimated cost with the yearly rate,
when the money lands, source and invoice, why approval is required (the ceiling it crosses), what happens after, what happens if
declined (server sentence), two buttons that say what they do ("Approve ¥200k financing" / "Decline"), audit details closed
(id, operation, tier, hash, clause quotes). Port the tier-badge removal from `test/ui-ux` for every other screen. The home never
approves in one click.

## I. Ported from `test/ui-ux`

The cash chart (`components/simple/cash-card.tsx` → `components/business/cash-forecast.tsx`), the Verdict glance, the Next step
bar, the deal step bar, the simulated Inbox list and `lib/inbox.ts` (as the Deals list, labelled simulated), the plain names in
the dictionary for rule codes, alert kinds and operations, the tier-badge removal, `obligationSentence` and the agreements
rendering (for Active commitments), the capex form (into `/capex` and the Cash & funding section), the `Segmented` wrap fix, the
borrowing "what / good for / watch out" explanations (as a disclosure), the glossary (into the account menu or Limits), the
principle "one cure, one button".

## J. Kept from current

Both shells and the mode store, `GET /home` and the queue `presentation` fields, the home's block order and test ids, the
approval card, the Deals page skeleton, Cash & funding, Activity, Limits, the story page, the mock recorder, all specs, the
Chinese dictionary.

## K. Deleted or left behind

`/simple` as a page; the capex card and the Demo clock on the Business home; the agent-message card as the home's first block
(the recommendation block already is the agent's message); `/documents` (deferred, see fog); the sidebar shell; the stepper
outside Demo; the per-page simulation footer; "Terms Guard + Debt Desk" as the global tagline; the "Router optimum" label; the
"Cash with committed cure" legend; the static "if you decline" sentence; "Day N" in Business copy; the empty "Promised early
payments" and "What arrived" panels; "Nothing needs your decision" as a card.

## L. API gaps (narrow presentation fields; the engine is not changed)

| Gap | Field | Source |
| --- | --- | --- |
| One trajectory for home and chart | `GET /home` → `cash.series[]` (day, closing_fen, closing_display, events[label, amount_display, kind]) and `cash.plan_series[]` with the recommended plan applied | the projection `GET /home` already runs; `project()` with the plan's actions |
| All-in cost | `next_action.cost_total_display`, `cost_breakdown[]` (label, display, basis), `cost_basis` sentence | pending the plan decision (ticket); the router's pricing or `_priced` on its convention |
| Conclusion-first copy | `headline` (conclusion), `headline_detail`, `first_breach` {cash_display, short_display, day, distance}, `worst_point` {display, day, distance} | alert inputs and the trajectory |
| Relative dates | `distance` strings beside every `*_day` the Business UI shows (`lands`, `due`, `lowest`, `decided`) | `_distance()` in `home.py` |
| What changed (causes) | `cash.drivers[]`: the largest outflows and the missing inflow between today and the first breach, as sentences | trajectory events |
| Authority wording | `next_action.authority_text` ("Within your signed limits" / the ceiling sentence) | `needs_owner_reason`, mandate |
| Decline consequence | `approvals[].presentation.if_decline` | the alert's `if_nothing` for alert-born approvals |
| Receivables summary | `receivables.overdue_total_display` | reconcile report |
| Business option names | `comparison[].name` in business words, `comparison[].rank` | `POST /router/plan` labels (presentation only) |

## M. Implementation order

Wave 0 (worktree, port inventory, mock re-record baseline, dictionary merge plan) → the plan / cost decision (grilling) →
Wave 1 (one trajectory, all-in cost, chart axis) → Wave 2 (Business language: distances, DEMO DATA indicator, mandate-language
authority) → Wave 3 (Home as one story, What changed, hide empty) → Wave 4 (Cash & funding reorder, chart) and Wave 5
(Receivables) in parallel → Wave 6 (navigation, header, branding; name pending the owner) → Wave 7 (Deals, Approvals, Activity;
the `test/ui-ux` ports) → Wave 8 (responsive, cold-user tasks A to P, tests, mocks, gate, screenshots). After each wave: typecheck,
lint, the affected specs, screenshots at 1440 and Pixel 7, a deletion pass. Nothing merges into `dev` before Wave 8's gate.
