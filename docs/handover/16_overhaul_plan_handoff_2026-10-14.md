# FLOW overhaul: the whole plan, for a teammate joining (14 Oct 2026)

Read this first. It is the one document that says what FLOW is becoming, why, what is already on `dev`, what is in
flight, what is left, and the rules every change follows. Everything it references lives in the repo; nothing here needs
the chat transcript that produced it.

## 1. The idea in one paragraph

FLOW is an AI working-capital agent for a small company. A buyer asks for better terms; FLOW prices the ask, says what it
does to cash, recommends the one reply it may send within the owner's signed mandate, and records what was agreed, funded,
received and reconciled. The product's promise is trust: the owner can always **find the work, understand the money, and
know exactly what a click authorizes**. The 12 Oct independent audit found the facts were right but presented as separate
cards; the overhaul (wayfinder map #121) rebuilds the connected workflows so each page has one job and every page shows the
same record when you select the same thing.

## 2. The direction (fixed)

**Home = attention. Deals = commercial decisions. Customer = relationship intelligence. Approvals = exact authorization.
Cash = liquidity consequences. Receivables = collections. Activity = the record. Demo = the story and the books.**

Each page owns one decision and links to the others by the address. No page duplicates another's decision. Home is the hub.

## 3. The rules every change follows

- **INVARIANT 13.** The browser computes no money, date, share or percentage word. Every string is the server's or the
  dictionary's, in English and Chinese (您 voice). Business mode shows no ids and no "day N" (relative words). A null word
  is omitted, never rendered, never invented. Nothing financial below 13 px.
- **The engine stability set is read-only**: `services/api/app/{financial,verifier,funding,alerts,operations,clock,books,
  mandate,covenants}` and `app/domain/models.py`. Overhaul work reads them and adds words around them. Changing a rule in
  them is an engine ticket with full verification, not a slice.
- **The selection contract** (ticket #126, `app/api/selection.py`, `apps/web/lib/selection.ts`): the address is the only
  selection: `customer`, `decision` (`deal:<offer>`), `path`, `invoice`, `scenario`, `from`. Every page read echoes
  `context` (what it honoured, `back {label, href}`, `irrelevant_text`); a selection a page cannot honour asks ("Which
  negotiation?"), never substitutes a sample. A row's link carries that row's own ids, never the selected row's.
- **The commitment receipt** (ticket #128, `CommitmentReceipt`): every action that authorizes or moves money carries a
  server `receipt` with eleven fields in order (authorizes, executes now, who else must agree, in hand vs future, gross,
  fees, net, when, assumptions, authority, remaining); it is shown above ONE named button; a comparison never binds a
  commit. Approve has no second step; Send keeps one confirmation because it moves money at once.
- **The recommendation rule (#131)**: FLOW recommends the first reply it may send within the mandate; it never ranks
  replies by cost, and every page says so. **The asked path's footing (#132)**: reply paths carry their own admissible
  funding plan, the request carries none; every comparison shows a "Funding assumption" row. Both are engine tickets if
  they are ever to change.
- **Process (owner, 13 Oct, "delivery over process")**: vertical slices, one frontend owner per connected workflow, a
  server implementer for additive words, an independent verifier for anything that touches money, authority, execution
  or settlement; focused tests while building; the full mock suite + the whole live project + `tests/api` only at
  integration and release checkpoints; `--no-ff` merges into `dev`; plain one-line commits; one worktree per agent; never
  the same branch name on two machines (it happened once; see §9).
- **Design language of record**: `docs/design/flow-mockup-2026-10-13/00_design_language_of_record.md` (the owner's
  mockup, Home screens only): canvas `#e5e8e8`, panel cards, white 24 px cards, ink primary button, amber (needs you) /
  lavender (waiting, selection) / green (agreed) pills, purple current line, one soft shadow; the app's side rail and
  fonts stay; a chart only where it adds clarity (a donut only for shares of one whole; bars for money along a line; a
  step line for money over time; text when one number says it).

## 4. What is on `dev` (4804370d, 14 Oct)

| Area | What it is | Where to read |
|---|---|---|
| Home V2, rounds 2–5 | headline → three cards (cash today, what we recommend with the funding legs bar and the buttons at the bottom, outlook) → the worklist table + upcoming movements + the owed-by-customer donut; a worklist selection crossfades into the selected card beside one cash-impact card; Ask FLOW in the header with six answerable examples; "FLOW action ready" said once | `docs/design/flow-mockup-2026-10-13/01_*`, `02_*`, `03_*`; `apps/web/DESIGN.md` "Home (V2) as built" |
| Slice B + round two | Deals = negotiations only with distinct subjects, lifecycle pills, group/sort, the terms table with the three scopes, the payment-terms timing diagram, the switchable cost/cash cards, the four-row cash comparison, Full analysis with "why FLOW recommends this", the three-statement send review, a receipt for every sendable reply, lapsed siblings after a send; Customer = the relationship sentence, exact metrics, the receivable→financing→net flow, the primary decision block, the exposure comparison; Approvals = statement titles, the authorize sentence, the three-stage lifecycle, the six-row summary, the split layout; Ask FLOW with a scope chip and scoped Business-worded reads; What-if on the addressed negotiation | `04_slice_b_round_two.md`; `DESIGN.md` "The seams" |
| Slice D | Activity as one record (business first, "Open this decision", benign sign-ins summarised, search and filters that remove nothing, evidence links to the trust views and back); Demo with "Which books?" cards first, one Next control, the guarded alternate books with a loss preview and Restore, Operator tools folded, the proof with the chain check and its scope | `docs/handover/15_slice_d_brief_2026-10-13.md`; `DESIGN.md` "Activity and Demo" |
| Busy books | `POST /demo/reset?scenario=busy` or the Demo's "Busy company" card: three customers, six negotiations, an approval, overdue invoices; day 0 counts needs_you 7 / waiting 1 / agreements 0 / customers 3 | `fixtures/scenarios/busy*.json` |
| Dev scripts | `scripts/dev.sh live` (API :8000 with in-memory books + web :3000, sign-in prefilled), `scripts/dev.sh mock` | README |

## 5. In flight (14 Oct)

**Accept as asked** (branches `feat/accept-as-asked-api`, `feat/accept-as-asked-web`): a negotiation whose request needs
the owner's review (Zhuhai, Dongguan on the busy books) had no control. Server: `POST /offers/{id}/accept` and
`/decline` under the owner's authority (the click is the approval, recorded as the owner's decision; 409 OVER_MANDATE
when only a new mandate could allow it; stale/lapsed 409s as `negotiate`), an `accept` block on the picture with the
receipt and the labels. Web: "Review the request" opens the receipt as three statements, then the terms and cost, then
one filled "Accept as asked" and a quiet "Decline the request"; Home and Customer link into the open review. Plus the
queue's expand cue (a chevron on every row, the selected row's edge joining the workspace, the empty state's sentence, a
200 ms slide, a one-time pulse). A verifier walks it on the busy books before merge.

## 6. What is left, in order

### Slice C: Receivables → Cash (one journey; the audit's journey 3, the AR late-payment response)
Receivables = collections: a compact invoice list with one focused invoice and a persistent return; rows with the
customer, amount, due/overdue words and a lifecycle pill (not due, due soon, overdue, promised, part paid, financed); the
focused invoice reconciles gross outstanding, what is still owed to the funder, and net to you at collection (the
reconciliation section from Dylan's `ui-ux-testing` branch, `apps/web/components/business/reconciliation-section.tsx`,
restyled); collection as an action with a receipt (prepare the reminder, see that nothing was sent, send or copy, see the
event afterwards on the same invoice); Ask FLOW carries the exact invoice; the late-payment stress on the same customer
with escalation to the owner's approval when funding beyond authority is needed. Cash = liquidity consequences, in this
order: the position (today, the lowest point with day and cause, the reserve gap) → one funding decision (sources with
arrival, all-in cost, authority, its receipt, one "Review and run the plan") → "Compare this scenario" as an explicit
read-only mode beside the committed baseline (never binds the commit; the executed plan always named by the server) →
committed facilities apart from conditional options (a buyer's early payment is never "available") → the chart last, the
Financial Timeline (#113) as its full form; the decision summary before the chart at every width. The seams: the Deals
comparison's "Funding assumption" cell links to Cash with that plan selected; Cash's lowest-point cause links to the
deal; a sent counter's funding shows on Cash as a committed source "from the Foshan agreement". Also: the 88 px content
gutter aligned on Cash, Receivables and Activity (Home is the reference); the Home words batch (facility headroom and
concessions against the mandate cap as Home figures, the Home chart title using the new subject words). Decisions:
tickets #133 (Cash) and the audit's UX08/09/13/14/22/28/31. Verifier: journey 3, busy and golden books.

### Slice E: consolidation and release
The kit restyled once so no page hand-rolls a card or pill (`components/ui`); Documents, What-if, Capex, Limits and the
engine views reachable only from the workflow that needs them, with `from` context; tablet (820) compact rows; the
bilingual pass (every zh word checked, English only in names and the buyers' quoted words); keyboard, 200 % zoom,
reduced motion and screen-reader checks; the five audit journeys walked on `dev` at 390/820/1280/1440 in both languages;
the release checkpoint (full gates) and handoff 17. Tickets #146, audit UX25/27/29/30/32.

### Round three on Deals (after C or in parallel if a second owner is free)
**Multi-deal comparison**: "Compare deals" selects two to four negotiations → one table (customer, requested change,
economic cost with its basis, cash effect, FLOW's reply); the combined effect on cash reads "Not yet evaluated" until the
engine evaluates a combined scenario on the same books (an engine ticket); "best" is never computed in the browser or by
cost alone. **The proposing sandbox**: What-if opened from the deal with its terms preset, a third column "FLOW's counter"
beside "Buyer request" and "Your terms", the live verdict, then "Use these terms as my counter" drafting an owner-authored
counter that goes through the same verifier, pricing and receipt as FLOW's (a new server route, not an engine change; the
owner's authority applies). Recorded in `04_slice_b_round_two.md` §6.

### Engine tickets (after the overhaul, full verification)
The fair funding comparison (same books + same funding + different terms, or each path with its cheapest admissible
plan); ranking sendable replies by net impact over one horizon; a combined multi-deal scenario.

## 7. How to run and test

- Local: `scripts/dev.sh live` (or `mock`). The repo-root `.env` points at a hosted database; the scripts ignore it.
  Owner header `X-Owner-Token: demo-owner-token` (DEMO_MODE on, OWNER_TOKEN unset). Busy books: the Demo card or
  `POST /demo/reset?scenario=busy`.
- Gates: API `cd services/api && SKIP_PERF_BENCH=1 uv run --project "$PWD" --directory "$PWD" pytest -o addopts= -p no:cacheprovider tests/api -q` (≈1317); web `pnpm run typecheck`, `pnpm run lint`, `pnpm run test:unit` (145); mock
  `E2E_TARGET=mock E2E_PORT=<port> pnpm exec playwright test --output <own dir>` (≈419); live `SKIP_PERF_BENCH=1 E2E_TARGET=live E2E_LIVE_PORT=<p> E2E_API_PORT=<p> pnpm exec playwright test --project=live --output <own dir>` (≈132).
  Two Playwright runs in one worktree need different `--output` dirs. A fresh worktree needs `pnpm install --offline`.
- Mocks are recorded, never hand-edited: `node scripts/record-mocks.mjs --api http://localhost:<port> --no-exposure`
  against an exposure-off API for the standard set; `--exposure`, `--buyer-exposure`, `--overview`, `--home-v2`,
  `--strategy`, `--inputs`, `--slice-d` against the matching API (env in `DESIGN.md` / the recorder).
- Agents: never an unscoped `pkill`; never ports 3000/8000; never bare `git stash`; `code-reviewer`/`design-reviewer`
  agent types have no Bash (use general-purpose with a saved diff).

## 8. Decisions the owner made that a newcomer might re-open (do not)

- Home keeps the headline sentence first; every other page has a stable short title first.
- Approve = the receipt above one named button, no second step. Send keeps one confirmation.
- The Demo's alternate books are a guarded reload with a loss preview and Restore, not isolated per-session books.
- Deals lists negotiations only (amends #127); Home keeps the cross-functional worklist.
- Business mode shows no invoice or offer ids in subjects; Demo mode may append them.
- The simulated-buyer control is Demo-only; Business says the reply is simulated.
- The lavender selection colour stays (the mockup's own).
- A donut only for shares of one whole (the owed-by-customer donut); no pie for a two-slice split or a 99/1 split.
- The Deals tab word is "Agreed"; the queue is 380 px; the workspace fluid to 850 px; content max 1400 px.

## 9. Known gaps and notes

- A bare `POST /demo/reset?scenario=` without the guard parameters replaces worked books silently (the page always goes
  through the guard; API scripting does not).
- The Deals pane's Full analysis shows the envelope's packages only with `NEXT_PUBLIC_STRATEGY_MVP` (flag-gated).
- The Ask FLOW opener in the header does not take focus on mouse click (`onMouseDown preventDefault`), so Escape returns
  focus to the body; a Slice E item.
- Content gutters differ by page (Home 88 px; Cash, Receivables, Activity centred wider): Slice C aligns them.
- Branch naming: the owner's PC and this machine both used `feat/slice-d-web`; use distinct names or say which machine
  owns a slice before starting.
- Handoffs 14 and 15 (`docs/handover/`) hold the earlier state and the Slice D brief; the map is GitHub issue #121 with
  the decision tickets #126–#138 closed with their resolution comments.
