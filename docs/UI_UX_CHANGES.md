# UI and UX changes

The living record of changes to the web app's interface (`apps/web`). It covers what changed, why, where in
the code, and what is still open. It covers presentation only. Engine, API and financial changes belong in
`docs/CONTINUOUS_OPTIMIZATION.md` and the ADRs.

Contents:

1. [How to update this document](#1-how-to-update-this-document)
2. [Design principles](#2-design-principles)
3. [Current state](#3-current-state)
4. [Label map](#4-label-map)
5. [Change log](#5-change-log)
6. [Open items](#6-open-items)

---

## 1. How to update this document

Every interface change updates this file in the same commit. Follow these rules:

- **Section 3 (Current state)** describes the app as it is now. Edit it in place; do not append to it.
- **Section 4 (Label map)**: add a row whenever a visible label is renamed. The old label stays in the table, so
  people who knew the old screens can find the new one.
- **Section 5 (Change log)**: add one entry per change set, **newest first**, using the template below. Never
  rewrite an old entry. If a later change reverses one, say so in the new entry.
- **Section 6 (Open items)**: give each item the next free `UX-n` number. When an item is done, move it to
  "Closed" with the change-log entry that closed it. Do not reuse numbers.

Change-log entry template:

```markdown
### YYYY-MM-DD: <short title>

Commits: `<hash>` <message>, ...
Goal: <the user problem, in one or two sentences>

| Change | Where |
| --- | --- |
| <what changed, from the user's point of view> | [file](../apps/web/...) |

Tests: <specs updated and why; the result of the runs, e.g. "mock e2e 35 passed, 1 skipped">
Not checked: <anything not run or not verified>
Follow-ups: <UX-n items opened or closed>
```

All UI text lives in `apps/web/lib/dictionary.ts` (`en` and `zh`). A new key must be added to both; the
typecheck fails otherwise.

---

## 2. Design principles

These rules came out of the owner's request of 4 Oct 2026: *a CEO who is not versed in accounting should
understand what is happening*. Every new screen and label should follow them.

1. **Answer first, working second.** Each screen opens with the conclusion in one plain sentence. Formulas,
   inputs, IDs and hashes sit behind a "Show the calculation" or "Reference numbers" toggle, or in a section
   for the finance team at the bottom.
2. **Plain words, with the finance term in brackets the first time.** For example "Loan payments covered
   (DSCR)" and "Safety minimum (reserve floor)". The home glossary explains each term in one sentence.
3. **Name actions after the user's task, not the code.** "Read this message", not "Compile"; "Check against my
   limits", not "Evaluate against the mandate".
4. **Say which way is good.** Ratios carry "higher is safer" or "lower is safer" next to the limit.
5. **Show the journey.** A multi-step task shows where the user is and what comes next (the deal step bar).
6. **Use neutral action names for operations**, e.g. "Borrow from a credit line" rather than "Borrowed…". The
   same name labels executed, pending and refused operations, and the status pill says which.
7. **The UI never computes money** (INVARIANT 13). Show only server display strings (`*_display`). The UI may
   count, order and compare days, but never add or compare amounts.
8. **Keep the honest wording** required by `docs/HANDOVER.md` section 5: "simulation", "a reading for you, not a
   bank's test" for DSCR, and no compliance claims.
9. **Demo controls look like demo controls.** Simulation knobs, such as the clock and the simulated buyer's
   reaction, are labelled "Demo" and never take the top of a screen.

---

## 3. Current state

### Navigation

The sidebar is grouped by job ([app-shell.tsx](../apps/web/components/app-shell.tsx)). Every link has a one-line
hover hint (`nav.hint.*`), and the logo opens Home.

| Group | Links (route) |
| --- | --- |
| *(no heading)* | Home `/`, Chat `/chat`, Approvals `/approvals`, Alerts `/alerts` |
| Deals with buyers | Buyer offers `/inbox`, Our decision `/verdict`, Try other terms `/whatif`, Agreements and log `/ledger` |
| Cash and borrowing | Cash forecast `/trajectory`, Borrowing options `/funding`, Payments received `/reconciliation`, Big purchases `/capex` |
| Rules and records | Your limits `/mandate`, Blocked messages `/security`, Audit trail `/evidence` |

### Home (`/`)

[app/page.tsx](../apps/web/app/page.tsx). The header carries a "Today is day N" badge. Cards in order:

1. **What needs you**: the agent's opening message, with Go ahead / Not now.
2. **Waiting for you**: approvals waiting for the owner.
3. **Where we stand**: a one-line verdict in green or red ("All clear…" or "Heads up: cash is forecast to
   drop below your safety minimum on day N, by up to ¥X"), then cash, safety minimum, lowest cash ahead,
   loan payments covered and debt ÷ yearly earnings, each with which way is safer.
4. **Your agreements**: one entry per deal: buyer, status, what was agreed in plain sentences, ongoing value
   given to the buyer, expiry and days left, progress on promised payments, invoices whose terms changed, and
   the exact wording behind a toggle. Past deals are folded away.
   [agreements-card.tsx](../apps/web/components/home/agreements-card.tsx)
5. **Warnings**: alerts from the cautious forecast, each with its fix button. The alert whose cure the agent's
   message is already offering shows "Answer it in What needs you" instead, so one cure has one button on home.
   The Alerts page keeps every button.
6. **What the agent did**: the last five operations.
7. **Demo clock**: move the simulated calendar forward.
8. **Words you'll see**: a folded glossary of 10 terms. [glossary.tsx](../apps/web/components/home/glossary.tsx)

### The deal journey

The offer and decision pages show the deal step bar ([deal-steps.tsx](../apps/web/components/deal-steps.tsx)):
**1 Read the offer → 2 Check it → 3 Respond → 4 Agreed**. Steps are worked out from the session's current offer,
verdict and negotiation. Finished steps get a tick, and the current one is highlighted.

Each page in the journey shows a **Next step** bar at the top when the next move is clear
([next-step.tsx](../apps/web/components/next-step.tsx)).

**Buyer offers** (`/inbox`): paste or pick a message → **Read this message** → a Next step bar with **Check
against my limits** and "See what it does to our cash" → the highlighted text, with "What the buyer is asking for"
and "Warnings" beside it.

**Our decision** (`/verdict`), top to bottom:

1. The answer: outcome badge plus one plain sentence per outcome (`verdict.plain.*`). The server summary and
   the IDs are folded under "Technical summary and reference numbers".
2. The Next step bar: with counter-offers, "choose what to offer back" (jumps to them); once the buyer agrees,
   "See it on your home page" (opens home scrolled to Your agreements); after no deal, "Back to Buyer offers".
   When the next move is not clear (for example a rejection with nothing to offer back), there is no bar.
3. Why the agent may or may not accept alone (autonomy panel).
4. **Rules this breaks**: each card leads with the plain rule name, then the server's message, then "This
   offer" against "Your limit". The formula and inputs sit behind "Show the calculation"; the cost of a fix
   and the quoted clause stay visible.
5. **What we would offer back**: counter-offers with their cost to us. Their pricing formula is behind "Show the
   calculation".
6. **Send our response**: the "Demo: how the simulated buyer reacts" switch and **Send our counter-offer**.
7. The plan to cover the shortfall.
8. **The working behind this decision**, for the finance team: early-pay discounts as yearly rates, the rules
   the offer keeps, and what each promise gives the buyer.

---

## 4. Label map

The old label is what the screens said before 4 Oct 2026. Translation keys are in
`apps/web/lib/dictionary.ts`.

### Navigation and page titles

| Old | New | Key |
| --- | --- | --- |
| Mandate | Your limits | `nav.mandate`, `mandate.title` |
| Inbox | Buyer offers | `nav.inbox`, `inbox.title` |
| Trajectory | Cash forecast | `nav.trajectory`, `traj.title` |
| Funding | Borrowing options | `nav.funding`, `fund.title` |
| Verdict | Our decision | `nav.verdict`, `verdict.title` |
| What-if | Try other terms | `nav.whatif` |
| Capex | Big purchases | `nav.capex`, `capex.title` |
| Ledger | Agreements and log | `nav.ledger`, `ledger.title` |
| Reconciliation / Receipt reconciliation | Payments received | `nav.reconciliation`, `recon.title` |
| Security / Security and audit | Blocked messages | `nav.security`, `sec.title` |
| Evidence | Audit trail | `nav.evidence`, `evid.title` |
| Owner and audit (nav group) | Deals with buyers / Cash and borrowing / Rules and records | `nav.group.*` |

Home, Chat, Approvals and Alerts kept their names. The Alerts page title stays "Cash-flow alerts".

### Buttons and actions

| Old | New | Key |
| --- | --- | --- |
| Compile | Read this message | `inbox.compile` |
| Evaluate against the mandate / Evaluate | Check against my limits | `inbox.evaluate`, `verdict.evaluate` |
| Run the negotiation | Send our counter-offer | `neg.run` |
| Buyer behaviour: Buyer accepts / Buyer refuses every counter | Demo: how the simulated buyer reacts: Agrees to a counter / Refuses every counter | `neg.profile`, `neg.cooperative`, `neg.hardLine` |
| Negotiation (card) | Send our response | `neg.title` |

### Permission levels

| Old | New | Key |
| --- | --- | --- |
| Tier 1 | Agent can act | `tier.TIER_1` |
| Tier 2 | Needs your OK | `tier.TIER_2` |
| Tier 3 | Never allowed | `tier.TIER_3` |

### Home cards and figures

| Old | New | Key |
| --- | --- | --- |
| Today | Demo clock (moved to the bottom) | `home.today` |
| Position | Where we stand | `home.position` |
| Reserve floor | Safety minimum | `home.position.floor` |
| Lowest projected cash | Lowest cash ahead | `home.position.lowest` |
| DSCR, month 1 | Loan payments covered, month 1 | `home.position.dscr` |
| Leverage, month 1 | Debt ÷ yearly earnings, month 1 | `home.position.leverage` |
| At risk | Warnings | `home.risk` |
| Done by the agent | What the agent did | `home.done` |
| *(new)* | Your agreements | `deal.*` |
| *(new)* | Words you'll see, in plain English | `gloss.*` |

### Operation names (`opkind.*`)

| Old | New |
| --- | --- |
| Draw facility | Borrow from a credit line |
| Repay facility | Repay a credit line |
| Submit invoice for financing | Get cash early on an invoice |
| Record commitment | Record an agreement |
| Accept offer / Counter offer / Reject offer | Accept an offer / Send a counter-offer / Decline an offer |
| Receive payment | Receive a payment |
| Request owner approval | Ask for your OK |
| Apply for facility | Apply for a loan |

### Rule and alert names

Rule names (`violation.*`) and alert kinds (`alertkind.*`) were rewritten as plain sentences, e.g.
`RESERVE_BREACH` → "Cash drops below your safety minimum" and `RECEIVABLE_PAST_DUE` → "A buyer is late paying".
Eight rule codes that had no label at all now have one: `DISCOUNT_ABOVE_BREAK_EVEN`, `EARLY_PAY_NOT_NEEDED`,
`EARLY_PAY_DEARER_THAN_PLAN`, `NEW_BORROWING_NOT_ALLOWED`, `PRECONDITION_FAILED`, `STALE_OPERATION`,
`STALE_VERDICT`, `CONFLICTING_COMMITMENT`. The decision outcome badges (ACCEPT, COUNTER, REJECT, NO DEAL…) kept
their wording; the plain sentence beside them explains them.

---

## 5. Change log

### 2026-10-04: A Next step bar on the deal pages (UX-2)

Commit: "Next step bar on the offer and decision pages" (branch `test/ui-ux`)
Goal: after the agent read an offer, the button to continue sat below a long message; on the decision page,
nothing said what to do once the answer was read, or where the agreed deal went.

| Change | Where |
| --- | --- |
| Reusable Next step bar: one sentence and the action that does it | [next-step.tsx](../apps/web/components/next-step.tsx) |
| Buyer offers: "Check against my limits" and "See what it does to our cash" moved from below the message into the bar at the top of the results (moved, not duplicated) | [inbox/page.tsx](../apps/web/app/inbox/page.tsx) |
| Our decision: a bar under the answer for three states: counter-offers to choose, deal agreed, no deal | `VerdictNextStep` in [verdict/page.tsx](../apps/web/app/verdict/page.tsx) |
| The negotiation result links to "See it on your home page" beside "Open the ledger" | [verdict/page.tsx](../apps/web/app/verdict/page.tsx) |
| Home scrolls to Your agreements when opened at `/#home-agreements`, once the card has loaded (also fixes the step bar's "Agreed" link) | [agreements-card.tsx](../apps/web/components/home/agreements-card.tsx) |

Tests: `demo.spec.ts` checks the bar before the negotiation ("choose what to offer back") and after it ("the buyer
agreed", the home link and its target). Mock e2e 35 passed, 1 skipped; unit 13 passed; typecheck and lint clean.
Not checked: the live e2e project (the demo spec also runs there).
Follow-ups: closed UX-2.

### 2026-10-04: One cure, one button on home (UX-1)

Commit: "One cure, one button on home: the Warnings card points to the agent's message" (branch `test/ui-ux`)
Goal: on day 34 home offered the same cure twice, "Go ahead" in What needs you and "Let the agent fix this" in
Warnings, and it was not clear whether they were the same thing or whether to press both.

| Change | Where |
| --- | --- |
| What needs you publishes whether its message is offering a cure (not when the cure is already queued) | [needs-card.tsx](../apps/web/components/home/needs-card.tsx), `openerOfferStore` in [fix-alert.tsx](../apps/web/components/home/fix-alert.tsx) |
| On home, that alert shows "The agent has already proposed this fix in its message to you. Answer it in What needs you" instead of its button; other alerts keep theirs | [lists.tsx](../apps/web/components/home/lists.tsx), `AlertCure` in [fix-alert.tsx](../apps/web/components/home/fix-alert.tsx) |
| The Alerts page is unchanged: every actionable alert keeps "Let the agent fix this" | [alerts/page.tsx](../apps/web/app/alerts/page.tsx) |

The opener does not return the id of the alert it is curing, so `openerAlertId` mirrors the API's rule in
`services/api/app/nl/alerts.py` (`alerts_turn`): among critical and warning alerts, the first
`RESERVE_BREACH_AHEAD`, otherwise the first `FACILITY_REPAYABLE`. **If that rule changes, change both.** A
cleaner fix is for the API to return the alert id (UX-9).

Tests: `home.spec.ts` now expects the pointer instead of the button on day 34 and starts the approval test with
Go ahead. The two "books moved" tests in `catchup.spec.ts` press the button on the Alerts page, and check on home
that nothing is waiting for approval. Mock e2e 35 passed, 1 skipped; unit 13 passed; typecheck and lint clean.
Not checked: the live e2e project.
Follow-ups: closed UX-1; opened UX-9.

### 2026-10-04: The deal journey and a decision page that answers first

Commits: `8218314` changes, `2274fb0` new interface (branch `test/ui-ux`)
Goal: the first pass made the words plain, but the flow still felt like separate modules. Answering "should I
accept this offer?" meant visiting up to five pages with no sense of order, and the decision page buried the
answer and the next action under technical detail.

| Change | Where |
| --- | --- |
| Deal step bar (Read → Check → Respond → Agreed) on the offer and decision pages | [deal-steps.tsx](../apps/web/components/deal-steps.tsx), [inbox](../apps/web/app/inbox/page.tsx), [verdict](../apps/web/app/verdict/page.tsx) |
| Decision page reordered: plain answer → why → what we'd offer back → send it → plan → "The working behind this decision" | [verdict/page.tsx](../apps/web/app/verdict/page.tsx) |
| One plain sentence per outcome; the server summary and IDs folded under "Technical summary and reference numbers" | [verdict/page.tsx](../apps/web/app/verdict/page.tsx) |
| Rule cards lead with the plain rule name; the formula and inputs sit behind "Show the calculation" | [verdict-parts.tsx](../apps/web/components/verdict-parts.tsx) |
| Counter-offer pricing formula folded behind "Show the calculation" | [verdict-parts.tsx](../apps/web/components/verdict-parts.tsx) |
| Task-named buttons: Read this message, Check against my limits, Send our counter-offer; the simulated-buyer switch labelled as a demo control | `lib/dictionary.ts` |
| Home reordered (what needs you first, demo clock last) with a "Today is day N" badge in the header | [app/page.tsx](../apps/web/app/page.tsx) |
| Plain labels for the 8 rule codes that showed as raw codes | `lib/dictionary.ts` |

Tests: `approvals.spec.ts` (button names) and `home.spec.ts` (card titles) updated. Mock e2e 35 passed, 1
skipped; unit 13 passed; typecheck and lint clean.
Not checked: the live e2e project against the real API.
Follow-ups: opened UX-1 to UX-5.

### 2026-10-04: Plain-language pass, grouped navigation and an agreements summary

Commits: `478a186` uiux dumbed down (branch `test/ui-ux`)
Goal: the owner asked that a CEO with no accounting background could follow the app, and that home should
remind them what was agreed and how it is going.

| Change | Where |
| --- | --- |
| "Your agreements" card on home: each deal in plain sentences, value given, expiry, payment progress, changed invoices, exact wording | [agreements-card.tsx](../apps/web/components/home/agreements-card.tsx) |
| Plain one-line verdict at the top of "Where we stand"; ratio labels with which way is safer | [position-card.tsx](../apps/web/components/home/position-card.tsx) |
| Folded glossary of 10 terms at the bottom of home | [glossary.tsx](../apps/web/components/home/glossary.tsx) |
| Navigation grouped by job, plain page names, hover hints, logo links to Home | [app-shell.tsx](../apps/web/components/app-shell.tsx) |
| Plain wording across pages, permission levels, operation names, rule and alert names, in English and Chinese | `lib/dictionary.ts` |

Tests: label expectations updated in `alerts`, `approvals`, `catchup`, `chat`, `demo`, `home` and `responsive`
specs. Mock e2e 35 passed, 1 skipped; unit 13 passed; typecheck and lint clean.
Not checked: the live e2e project. The agreements card's "Progress" section was checked in code but not seen on
screen (the demo deal shown had no promised payments in the mock).
Follow-ups: UX-6 (Chinese review).

---

## 6. Open items

### Open

| ID | Item | Size | Notes |
| --- | --- | --- | --- |
| UX-3 | Fold Cash forecast and Borrowing options into the decision page as "Why?" sections, so the deal path is two pages | Large | Do after the video is recorded; the project is in stability mode |
| UX-4 | Hide "Waiting for you" when nothing is waiting | Small | `home.spec.ts` uses `home-waiting-empty`; update the test with it |
| UX-5 | Link chat answers to the matching screen (a decision in chat opens Our decision) | Medium | |
| UX-6 | Native review of the Chinese strings added on 4 Oct | Small | Written by the agent, not reviewed |
| UX-7 | Run the live e2e project after both 4 Oct passes | Small | Needs the API running; see `apps/web/README.md` |
| UX-8 | "AI-generated, for reference" label on agent replies | Small | A gap listed in the README and `docs/HANDOVER.md` |
| UX-9 | Have `POST /nl/opener` return the id of the alert it proposes to cure, and drop the mirrored rule in `openerAlertId` | Small | An API change; wait until stability mode is lifted |

### Closed

| ID | Item | Closed by |
| --- | --- | --- |
| UX-1 | Merge the two fix buttons on home | 2026-10-04: One cure, one button on home |
| UX-2 | A Next step bar on each step of the deal | 2026-10-04: A Next step bar on the deal pages |
