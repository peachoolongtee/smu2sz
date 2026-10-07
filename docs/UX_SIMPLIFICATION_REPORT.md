# FLOW simplification: final report

8 October 2026. The owner's fifth brief ("aggressively simplify", 7 October) was charted as [wayfinder map #26](https://github.com/peachoolongtee/smu2sz/issues/26) and worked in Waves 0 to 7, plus an inventory of the teammate's branch `feat/upgrading` and Wave 8 that ports its best components. This report follows the brief's section 47. The execution brief that preceded it is `docs/UX_SIMPLIFICATION_BRIEF.md`; the truth research is `docs/research/ux-truth-2026-10-07.md` (branch `research/ux-truth`); the branch inventory is `docs/research/upgrading-inventory-2026-10-08.md` (branch `research/upgrading-inventory`); the cold-user walk is `docs/research/cold-user-walk-2026-10-08.md`. Screenshots per wave live under `docs/screenshots/<wave>-2026-10-0N/` with page heights in each `manifest.json`.

Way of working: the lead architected each wave, wrote its spec and acceptance criteria, reviewed the result on screenshots and merged into `dev` with `--no-ff`; Waves 1 to 3 were coded by the lead, Waves 4 to 8 by delegated implementers; the truth research, the inventory, the cold-user walk and the code review ran as independent agents; every material financial figure derived by one agent was checked by another from the engine's own functions.

## Financial display bugs found

| # | Where | What was wrong | Source |
|---|---|---|---|
| 1 | Deals plan | An advance on an invoice issued on day 32 was shown requested on day 0 and landing on day 3. | `router.py::_with_landing` read the receivables on the books, not the recurring invoices the engine sees; the engine itself landed and priced the advance on day 35. |
| 2 | Cash & funding | "Credit line only" (¥841.64, reserve broken on day 12, ¥255,000 short at the worst point) ranked #5 among full plans. | The router's `Eval.shortfall` never reached the comparison row; the web ranked every row. |
| 3 | Deals | Option B read "Cost to the supplier ¥0.00" where the net is extension ¥16,217.95 minus a ¥16,380.00 price adjustment. | `supplier_cost_fen = max(0, net)` by design; the parts lived only in the formula string. |
| 4 | Home after funding | "Lowest cash ahead: ¥300k 34 days ago". | `_headline` read the minimum over the closed days before today. |
| 5 | Deals | "unsafe in 47 days" (cash ¥209,960) beside "lowest cash ¥164,960 on day 60" with nothing saying they are two days. | The trajectory view had no first-breach cash. |
| 6 | Deals | A REJECT with no counters still read "Decline, and counter" (FastCapital, EX06, EX09). | `recommendationKey` ignored the counters. |
| 7 | Cash & funding | Early-payment options wore "Cannot run until the invoice is issued". | One fixed string for every `executable_now: false`. |
| 8 | Cash forecast | Annotations truncated to "Advance on the ¥420 ¥255k". | The browser truncated a server sentence. |
| 9 | Cash & funding (review) | "No additional funding is needed" could show while the alert was critical with no runnable fix. | `covered` keyed on `next_action` alone. |
| 10 | Deals inbox (review) | The unknown sender was listed in Business mode before the registry loaded. | `unknown()` failed open while `known` was null. |
| 11 | Calculation words (review) | A price adjustment read as income regardless of sign; a terms shortening read "add -15 days". | The interpretation ignored the sign of the value and the delta. |
| 12 | Backend test | The golden trajectory digest failed on `dev`. | It digested a view that gained the display field `first_breach_cash` (¥60,000 on day 12); the figures were unchanged. |

## Financial display bugs fixed

All twelve, as presentation reads over results the engine already produces: `available_from_day` and a corrected `lands_day` on every funding leg, with a display invariant tested on every fixture plan (no leg shown requested or landing before it is eligible) and a regression test that the new fields never feed `plan_id`, costs or the comparison order; `status`, `shortfall_display`, `worst_day`, `reason_kind`, `note_when`, `not_executable_reason` and stamped actions on comparison rows; counter `economics` (gross, offset, net, `net_words`); `first_breach_cash`; the home's lowest point from today, headroom and `status_text`; `business_action`; `label_short` on chart events; the Cash page's `covered` rule; the inbox's loading state; the interpretation's sign handling; the digest test excludes display-only fields. Verified figures: landing day 35 and ¥2,406.67 priced on days 35 to 92; shortfall ¥255,000 on day 30; Option B's parts; the ¥841.57 versus ¥841.64 difference (a ¥13.80 smaller draw beside an early payment, both correct for their own plan); the minimum from day 34 on is ¥300k on day 34.

## Deals before / after

Before: 2.8 desktop screens and 5.5 phone screens for one deal; the ask shown three times, the breach three times, the concession cost three times, the counter three times (¥3,027.77 four times); formulas (`d/(1−d)`, "smallest whole-5bp rate") at level 1; "Decline, and counter" over a REJECT tone; "Checks: 4 failed, 4 held"; a "Messages in this session" list beside a "Simulated inbox"; the FastCapital phishing message beside the buyer's offer.

After: 1.7 desktop screens, 2.3 phone (Wave 7 walk); one inbox thread per buyer with the earlier messages folded and "1 suspicious message was blocked · See what was refused"; the ask in plain words ("1.20% discount for paying the ¥420,000.00 invoice early", "45 → 60 day payment terms going forward", "1.00% rebate on the next period's purchases") with "View parsed terms" behind it; "Counter recommended" over the three numbers: 12-month cost of concessions ¥28,326.92 against your ¥5,000.00 limit, first reserve breach in 47 days with cash falling to ¥209,960.00, worst point ¥164,960.00 in 60 days, plus one sentence on the discount being dearer than funding; "Recommended response" with Option A as a business card (what changes, estimated cost, "Send this counter", Details with why it works and the terms the buyer would agree to) and Option B behind "Compare another option" with net economic cost ≈ ¥0 beside its ¥16,217.95 funding cost and ¥16,380.00 offset; "Why FLOW recommends this" with three reasons in the owner's words and "Show all checks (8)"; the calculation reads as a sentence ("60-day terms add 15 days of financing to 13 expected invoices, about ¥1,871.30 each at your cheapest committed source: ¥24,326.92 over 12 months.") before its formula; the stepper as one quiet line.

## Cash & funding before / after

Before: "You're covered" above "Other options: every way to cover the gap"; options ranked #1 to #5 across feasible and infeasible rows; "Cheapest committed plan"; "Cannot run until the invoice is issued" on early-pay rows; truncated chart labels; "day N" in the plan's calculation lines.

After: headroom said directly ("Available headroom ¥100k", "Lowest forecast headroom −¥405k"); the recommended plan first under its facility names ("Bank credit line + Invoice financing (onboarded platform) · Recommended · Fully protects your cash and can run today"), then the dearer full plans with the server's own note; "Insufficient or not currently available" apart and unnumbered ("Credit line only · Does not cover the gap · Cash still falls below your reserve in 12 days; ¥255,000.00 short at the worst point"; "Credit line plus the guaranteed loan · Not available · not applied; cash in 21 days, gap opens in 12 days"); after funding a "Current funding" card (¥150,000.00 Bank credit line · Received today; ¥255,000.00 Invoice financing · Arrives in 3 days · On its way; drawn and available per source; "No additional funding is needed.") and the comparison folded under "Other plans considered" with "Why this plan was selected"; the forecast with "Receipt from Foshan Home Retail Co. ¥420k" and "Invoice financing lands ¥255k". Day 0 is 2.7 desktop screens and 4.5 phone screens (the recommended plan's detail; Wave 8's three-fact card folds it), funded 1.8 and 2.4.

## Components removed

The Deals session list; the consequence card; the three-column verdict glance (component deleted); the counters card with formulas at level 1; the "N failed, N held" count; the raw outcome badge on rows and on the decision card; the "Owner" text in the header pill; the dead home components `lists`, `needs-card`, `position-card`; the `.biz.option.dearer` and `cheapestFull` claims the browser could not make.

## Components collapsed

The inbox's earlier messages and other threads; the stepper into one line; the engine verdict and the verifier's summary into "Show all checks"; formulas into "Formula" disclosures; the decision-time comparison into "Other plans considered"; tier, sequence, operation id and hash into "Audit details" on the home and Activity; the first breach and the worst point into one tile when they are the same day; the raw executor sentence behind the business sentence everywhere in Business mode.

## New disclosure hierarchy

Level 1 conclusion: the status words ("Covered, but tight"), the headline, headroom, the business action. Level 2 recommended action: the response card, the funding plan, "Run funding plan", "Send this counter". Level 3 cost, timing and consequence: the three numbers, the lots, the options' status and what they leave uncovered, "If you do nothing" and "After". Level 4 reasoning: the three reasons, "Why it works", "Why this plan was selected". Level 5 calculation: the interpretation, then the formula. Level 6 engine and audit evidence: the engine verdict, all checks, audit details, the engine views in Demo mode. Business interactions stop at level 3 by default.

## API changes

All presentation reads; the engine unchanged (confirmed by the independent review and by `tests/funding/test_display_fields_inert.py`). Added: on funding actions and plans `available_from_day`, corrected `lands_day`; on comparison rows `shortfall_fen`, `worst_day`, `status`, `reason_kind`, `note_when`, `components_when`, `not_executable_reason`, stamped `actions`; on counters `economics` and `text_when` / `rationale_when`; on violations `message_when` / `cure_note_when`; on the verdict `business_action`, `summary_when`, concession `interpretation`, plan `*_when` twins, `TrajectoryView.first_breach_cash`; on `GET /home` the lowest point from today, `headroom_*`, `lowest_headroom_*`, `status_text`, `funding_lots`, `facilities[].drawn_fen`, `event_text` / `event_detail` on changes, `in_transit.lots[].headline`, `label_short` on series events, `worst` omitted when the breach is the worst point; on `GET /ledger`, `GET /audit` and the act results `message_when` and `event_text`; on the approvals queue `created_when`; `relative_days` widened; `owner_words` for the ceiling clause; `operation_words` for operation kinds in Business sentences.

## Copy changes

The table in `docs/UX_SIMPLIFICATION_BRIEF.md` section 7, applied, plus: the business event sentences ("¥255,000.00 of invoice financing drawn … Funds arrive in 3 days.", "Waiting for your approval: … above the 15.00% limit you signed for funding without your approval.", "You approved …"); "Ask FLOW"; the page prompts, five of them rewritten to sentences the NL layer answers; "Covered, but tight"; "2 days late"; "Cash at first breach (also the lowest point)"; the owner's words for operation kinds ("draw on", "finance an invoice on").

## Business / Demo differences

Business: distances from today, one inbox thread per buyer, the suspicious message blocked with one line, business sentences, no tier, hash, code or day number at level 1, the raw sentences only behind "Audit details". Demo: "Day N", the simulated inbox with every message and the unknown-sender flag, the engine views, the raw sentences beside their twins.

## Test results

On `dev` at `b3fe741` (after the Wave 7 fixes), 8 October 2026:

| Check | Result |
|---|---|
| Backend suite, one run with `SKIP_PERF_BENCH=1` | 5,541 passed, 33 skipped, 0 failed (8 min 50 s) |
| Chat scenarios (`scripts/run_scenarios.py --inproc`) | 49/49, 87 turns |
| Demo path (`scripts/demo_run.py`) | exit 0; the cure executed and the alert cleared |
| Attacks (`app.security.attacks --report`) | 255 attacks (122 API, 133 chat), 0 with harm |
| Web typecheck, lint | clean |
| Web unit (`check-mocks`, fallbacks) | 17 passed |

After the Wave 8 merge (`dev` at `262db40`): backend 5,544 passed, 33 skipped, 1 failed (the golden router-plan digest, which strips display-only fields before digesting and had not learned Wave 8's new ones; fixed on `fix/golden-router-digest` without touching the golden); scenarios 49/49; demo path exit 0; attacks 255 with 0 harm; typecheck, lint clean; unit 17; mock e2e 64 passed, 7 skipped, 0 failed; live e2e 36 passed.

New tests this map: `tests/api/test_truth_fields.py` (the display invariant on every fixture plan, the semantic tests of the brief's section 43), `test_owner_words.py`, `test_business_dates.py`, `test_ledger_events.py`, `tests/nl/test_business_page_prompts.py`, `tests/funding/test_display_fields_inert.py` (the new fields never feed the engine), and the rewritten Deals, Cash, home, activity, receivables and chat specs.

## E2E results

Mock mode (recorded API answers, desktop 1440 px and Pixel 7): 49 passed, 7 skipped (the screenshot walk runs only with `SHOTS_DIR`), 0 failed in the final run; the phone test "the slide-over chat fits the viewport with a long reply" is flaky across the map's runs (pre-existing, passes alone). Live mode (a fresh API on :8005, the web on :3005): 36 passed. Screenshots of every page and state per wave under `docs/screenshots/`; the walk spec `apps/web/e2e/screenshots.spec.ts` reruns in a minute.

## Screenshot review

The cold-user walk (`docs/research/cold-user-walk-2026-10-08.md`, mock build, both viewports, read from the DOM) answered the brief's questions A to N: A in 1 click (the inbox preview), the itemised ask in 2; B, D, E, F, G and H in 3 (open the message, check it, read the decision card; H is an enabled "Send this counter"); C in 3 ("break-even 0.88%") or 4 for the full concession sentence; I and J in 4 ("Details", "Detailed calculations"); K, M and N in 1 on every state; L in 1 once funding ran (the Current funding card) and 2 before (the home's details). The phone adds one click per page for the navigation sheet. No "day N" at level 1 on any Business page.

Section 44 per page: the eye lands on the status headline (Home), the business action (Deals), the risk headline (Cash); one primary action on each page except the day-34 pending home (fixed in Wave 8); conclusions first on Deals and Cash; the engine terms still visible at level 1 (admissible, verdict, what-if sandbox, hash-chained, executor, annualised, Tier 2, lead time) and the ids on Receivables and the pending home (RCV-A, RI:…, CMT-…, APR-000001) are Wave 8 items 19 and 20; figures repeated three or more times: ¥420,000 six times on the day-0 home, ¥200,000 eight to eleven times on the day-34 home, ¥300,000 five times on Cash (Wave 8's rows and the pending dedupe reduce them). Contradictions found and sent to Wave 8: the day-34 Cash page showed the day-0 comparison snapshot; the approval card's "for the next 12 days" against the home's "120 days"; Activity's "No commitments yet" against Receivables' commitment on day 34; "You approved" and "Waiting for your approval" both listed for one operation; the home's "Why this" quoting the alert cure (¥336,000 at ¥2,994.08) under the ¥255,000 plan; debt to earnings 1.72× on the Home against 1.35× on Cash after funding; the funded chart labelled "If you do nothing". A CFO would trust the level-1 figures on Deals and Cash day 0; the day-34 Cash page and the approval card's horizon were not trustworthy until Wave 8.

## feat/upgrading and the colour direction (Wave 8)

The teammate's branch (6 commits on dev's 95c83d8, 65 files) was inventoried against this design (`docs/research/upgrading-inventory-2026-10-08.md`): a restyle plus features over the pre-wave pages, 23 files colliding with Waves 1 to 6, no money computed in the browser, soft rule breaks (regex-rewritten server sentences, client-side approval inference, day numbers reaching Business mode through new routes, off-palette gradients and 45 raw palette classes). Ported in Wave 8, component by component, in the owner's words and the app's tokens: the three-fact next-step card with a confirm step before the plan runs; the home hero's shape (status pill, headline, cash today large, three tiles, headroom, "Why" folded); home blocks as rows with "Show N more" and a pending approval said twice, not four times; pill navigation with the five sections and a five-tab bar on phones, "Your limits" in the account sheet; Cash & funding's four fact tiles and option rows that open to their reasons; the Deals outcome card (DEAL / NO DEAL), the "No deal" step, "How the agent read it", the set-aside sentence; the Capex and What-if day-number fixes and the What-if summary; the small takes (error words, plurals, page titles and language, ¥1M ticks, stacked key values); a two-step tour started from the account sheet, off by default; the Chinese home recorded in both languages. Left: the gradient hero and buttons, the rainbow shortcut bubbles, Buy equipment as a navigation section, runtime web fonts, the regex sentence rewrites, client-side approval inference, the branch's mocks.

The cold-user walk's contradictions were fixed in the same wave: the day-34 Cash page no longer shows the day-0 comparison (a fresh plan when a gap exists; the one-approval cure is the plan card, the router's two-approval ¥1,706.10 plan the row); the approval card reads the home's "for the next 120 days"; the day-34 ledger is recorded so Activity shows the agreement; a queued operation reads "Queued for your approval" once decided and the home drops it; the alert's cure reads "A fallback also exists: … FLOW recommends the plan above"; the debt readings came from a stale mock trajectory and now follow the story, with Cash showing the home's figures; the funded chart reads "Projected cash"; engine terms at level 1 (verdict, what-if sandbox, hash-chained, executor, annualised, Tier 2, lead time, admissible) read in words; ids moved behind Audit details; one primary action per page.

Colour (owner, 8 October: "a middle ground"): the researched direction `docs/research/colour-direction-2026-10-08.md` (11 sources, every pair checked for WCAG AA) was adopted as option C: one solid deep-brand block for the Home's answer with a bright status pill as the only element that changes with the state (green quiet when covered, amber or red the brightest thing on the page when action is needed); one brand-filled action per page; status colour only for status (the WeChat chip and the owner disc stop borrowing green; "Recommended" is brand, not a status); surface tiers for hierarchy with status tint only on "Who decides"; five chart tokens and grey for the rest; `-solid` tokens so every boundary passes 3:1 (dev's own warning edge and strong borders had failed it); gradients, rainbow icons and raw palette classes nowhere; Demo mode flat with a deep-brand strip. The design detector reported 0 findings on the changed files.

Measured after Wave 8 (desktop / phone screens): Home day 0 1.4 / 2.0 (baseline 1.5 / 2.3), Deals evaluated 1.7 / 2.5 (2.8 / 5.5), Cash & funding day 0 2.4 / 4.0 (2.6 / 4.0), Cash funded 1.8 / 2.5 (2.0 / 2.9), Home day 34 pending 1.9 / 3.0 (2.1 / 3.3).

## Remaining UX debt

Chinese twins on the routes without `lang` (`GET /ledger`, the verdict view); the Demo story page and the Demo trajectory view against the new Deals and Cash; the slide-over width test (flaky, pre-existing); Cash & funding on a phone at 4.0 screens on day 0; the FLOW visual mark; a Demo-only card-by-card walk of a deal, if the owner wants the old showcase back.

## Known limitations

The utilisation bar reads `limit_fen` on the home's facilities, added for it and not yet seen on a live home; "Show N more" has no recorded state with more than three changes; recorded server sentences still say "still OPEN". "Send this counter" runs the demo's buyer kernel and says so; no outbound channel exists; `GET /ledger` and the verdict view carry English twins only; the mock home's status word stays English when the language switches.

## What was deliberately not changed

Financial, mandate and authority semantics; the cure and `supplier_cost_fen`; the Home's structure (refined, not redesigned); the five navigation sections; the engine views in Demo mode; the deck, the video and deployment (owner items).
