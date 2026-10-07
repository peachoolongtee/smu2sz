# UX integration: final report (7 Oct 2026)

The report the owner's fourth brief asks for (section 44). The brief itself, the branch comparison and the P0 findings are in
`docs/UX_INTEGRATION_BRIEF.md`; the work was charted and resolved as the wayfinder map, GitHub issue #13, one ticket per
wave, each closed with STATUS / FILES / TESTS / NOT CHECKED / FOLLOW-UPS. Nothing from `test/ui-ux` was merged as a branch.

## Final branch and commits

`dev` (pushed). The waves merged into `dev` with `--no-ff`, one at a time after the integration loop: Wave 1 `6f1a765`, the
eight delegated tasks T7 / T2 / T1 / T6 / T5 (`22:56` to `23:00` on 6 Oct), Wave 2 `8978870`, T8, T4 `ce29f34`, Wave 3
`6f770ab`, Waves 4 and 5 `d0a06ca`, Waves 6 and 7 `30bf4ca`, Wave 8 (this report, the Deals fold and the documents).
The integration branch `feat/ux-integration` carries the same commits.

## What came from the current branch (`dev`, the 5 Oct redesign)

The two shells and the persisted mode, `GET /home` as the one owner read and the approvals queue's `presentation` fields,
the home's block order and test ids, the approval card as a question, the Deals / Cash & funding / Receivables / Activity /
Limits pages, the story page, the mock recorder and every spec, the Chinese dictionary, loading / error / sign-in states.

## What came from `test/ui-ux`

The cash forecast chart (area, danger zone, breach and lowest marks, event tooltip, table for screen readers), the Verdict
glance (asked / why not / what we offer back), the Next step bar, the deal step bar, the simulated inbox with source and
sender, the plain names for rule codes, alert kinds and operations (38 / 16 / 18, both languages), the tier-badge removal,
the plain-sentence agreements (`obligationSentence`), the facility explainer (how it works / good for / watch out for), the
`Segmented` wrap fix, the one-cure-one-button principle.

## What was newly designed

- `app/funding/recommend.py`: which plan the owner is shown (the router's cheapest runnable plan, priced all-in; the alert's
  cure as the fallback; the single-approval cure when the cheaper plan would need several approvals, with the cheaper option
  named) and the operations a click on it sends, bound by the act route.
- `GET /home`: the projection series behind every figure (`cash.series`, `cash.plan_series`), the all-in cost with its lines
  and basis, the conclusion-first headline / detail / worst point, `cash.drivers` from the projection's own events, short
  overview figures, the outcome title and components of the recommendation, the authority line, every day as a distance
  (`*_when`, `relative_days`), `since_day`, `overdue_total_display`, `if_decline`.
- The home as one decision story, the Cash & funding order, the Receivables summary, the header (FLOW 流, the approvals badge,
  one account menu, one Demo data pill), Business copy without "Day N", "safe level" or "the agent can do this alone".

## What was removed

The per-page simulation footer, the "Day N" chip and labels on Business pages, the "not included" cost footnote, the
"cheapest" claim where it was not true, the "Router optimum" label, the "Cash with committed cure" legend, the static "if you
decline" sentence, the standing empty panels on Receivables and the empty "Needs your decision" / "Recent changes" cards,
"Terms Guard + Debt Desk" as the global tagline, Approvals as a permanent navigation entry, the `/simple` fourth home and the
capex card and clock on the home from `test/ui-ux` (never ported).

## Financial-presentation bugs found

1. The Business Cash & funding chart plotted the trajectory **with the EX01 offer applied** (recorder line 170) under a
   headline from today's books, and its y axis started at zero, so the −¥105,000 trough was never drawn. Fixed by one series
   on `GET /home` and an axis that extends below zero.
2. The home priced the alert's greedy cure (¥486,000, "¥2,994.08" without the line's interest) and called it the cheapest,
   while the router's plan for the same gap (¥405,000, ¥3,113.93 all-in) is what the documents, deck and video quote. Fixed by
   the recommendation policy (#15) and the all-in presentation with the basis in words.
3. The router's label for the day-34 two-invoice plan reads "¥1,425.75 + ¥1,069.32 = ¥1,706.10", a net total (the plan repays
   the drawn line 30 days sooner, −¥788.97). Found by the independent check; the home now lists the lines and that offset so
   they add up, and says "including ¥788.97 less interest on balances already drawn".
4. The Cash page read `GET /home` in English regardless of the language switch.

## API changes (presentation reads; the engine is unchanged)

`GET /home`: `since_day` query; `headline`, `note`, `worst`, `plan_note`, `since_day`; `cash.series[]`, `cash.plan_series[]`
(day, closing fen and display, events with kind, label, amounts and `amount_short`), `cash.first_breach_cash_*`, `cash.*_short`,
`cash.drivers[]`, `cash.lowest_when`, `cash.first_breach_when`; `next_action.plan_source`, `outcome_title`, `components[]`,
`receive_short`, `after_lowest_*`, `cost_total_display`, `cost_breakdown[]`, `cost_basis`, `cheaper_option`, `lands_when`,
`authority_text`, legs with `lands_when`; `approvals[]`, `changes[]`, `receivables.*`, `warnings[]`, `in_transit.lots[]` carry
distances; `receivables.overdue_total_display`. `GET /approvals/queue` `presentation`: `lands_when`, `decided_when`, `if_decline`,
relative reason and result. `POST /alerts/{id}/act`: accepts the recommended router plan's suggestions as the bound cure
(409 `ALERT_CHANGED` otherwise). `POST /nl/opener`: proposes the same plan with the router's costs. From the delegated tasks:
`POST /offers` and buyer turns capped per day (`INTAKE_CAPPED`, setting `INTAKE_CAP_PER_DAY`), invoice ids in words inside
server sentences, the EX01 benchmark target 350 ms. No engine module changed.

## Files changed

Backend: `app/funding/recommend.py` (new), `app/api/home.py`, `app/api/alerts.py`, `app/api/operations.py`,
`app/api/presentation.py`, `app/nl/alerts.py`, `app/api/offers.py`, `app/api/nl.py`, `app/api/runtime.py`, `app/config.py`;
tests `tests/api/test_home.py`, `test_presentation_words.py`, `test_intake_cap.py`, `tests/security/test_intake_cap.py`,
`tests/alerts/test_cure_cost.py`, `tests/funding/test_benchmark.py`. Web: `app/page.tsx`, `app/cash/page.tsx`,
`app/receivables/page.tsx`, `app/deals/page.tsx`, `app/approvals/page.tsx`, `app/activity/page.tsx`, `app/layout.tsx`,
`components/app-shell.tsx`, `components/business/*` (status block, next action, blocks, cash forecast, facility explainer),
`components/deals/*`, `components/next-step.tsx`, `components/approval-card.tsx`, `components/chat/assistant-turn.tsx`,
`components/charts.tsx`, `components/badges.tsx`, `components/verdict-parts.tsx`, the engine pages touched by T7 and T8,
`lib/when.ts`, `lib/inbox.ts`, `lib/types.ts`, `lib/api.ts`, `lib/live/index.ts`, `lib/chart-helpers.ts`, `lib/dictionary.ts`;
specs `home`, `live`, `cash`, `receivables`, `deals`, `activity`, `approvals`, `chat`, `demo`, `alerts`, `whatif`; the mocks
re-recorded after every wave. Documents: this file, `docs/UX_INTEGRATION_BRIEF.md`, `docs/research/ux-port-inventory-2026-10-06.md`,
`docs/research/ex01-benchmark-profile-2026-10-06.md`, `docs/UX_AUDIT.md` section 18, `docs/CONTINUOUS_OPTIMIZATION.md` (UX2),
`docs/HANDOVER.md` section 6, `apps/web/README.md`.

## Test results (the gate on `dev` at `30bf4ca`, then the Wave 8 fixes, 7 Oct, Mac, `SKIP_PERF_BENCH=1`)

| Check | Result |
| --- | --- |
| Backend chunk A (alerts, api, books, borrower file, capex, clock, commitments, compiler, counterparties, covenants, egress, evals, financial, funding) | 3,460 passed, 22 skipped |
| Backend chunk B (mandate, nl, operations, persistence, security, verifier, what-if, concurrency, certification, fixtures, money) | 2,017 passed, 11 skipped |
| `scripts/run_scenarios.py --inproc` | 49/49 scenarios, 87 turns |
| `scripts/demo_run.py` | exit 0 |
| `python -m app.security.attacks --report` | 0 attacks with harm, 0 commitments activated by attacks |
| `scripts/evaluate.py` | every target PASS (task completion 49/49, attacks through /nl 0/133, protected fields disclosed 0, unauthorised operations 0) |
| Web mock e2e (desktop + phone) | 42 to 43 passed, 1 skipped, the one known slide-over width failure (see technical debt) |
| Web live e2e (uvicorn + live build on 3005/8005) | 34 passed |
| `pnpm typecheck`, `pnpm lint`, `ruff check app` (the touched files) | clean |
| `tests/api tests/alerts tests/nl` after the review fixes | 1,019 passed |

Every wave also ran its own loop (API tests, typecheck, lint, mock and live e2e, scenarios, demo run) before its merge,
recorded on its ticket. The independent code review of the whole diff (`53cd1cc..30bf4ca`) returned five major and ten minor
findings; the fixes are in Wave 8: one shared guard and the Debt Desk flag for every caller of the recommendation (the chat
had none), the readiness note follows the plan actually shown, the other fix family is refused with 409 `ALREADY_QUEUED`
while one waits (a repeat of the same fix still replays the executor's DUPLICATE), one documented axis-label formatter with
the right minus sign (the browser still computes no money a reader is asked to trust), the live spec's queue assertion now hits
the real route, the overview rounding lives in `app/domain/money.py` with unit tests for `fmt_yuan_short`, `when_text` and
`relative_days` (which now also rewrites "to day N", "(day N)", ", day N" and English text inside Chinese pages; Wave 4 of the
simplification map, #33, added "on or before day N", "(day A to day B)" and "from day A to day B"), the
last-visit marker is validated and a marker later than today falls back to the week, the approvals badge refetches on
navigation, a facility that is not owner-approved shows ¥0 available as the funding menu does, the repay recommendation's
title and why are relative. Left as noted debt: the rate scraped from the router's prose, the Activity page's unbounded id
replacement (pre-existing), the account menu remounting on sign-out, the badge's silent fallback on an API error.

## Screenshot and user-task review

Walked on the mock build at 1440 px (the browser pane was hidden for part of the work, so the day-0 and day-34 pages were also
read from the rendered DOM). Tasks A to P of the brief's section 32 on the opening books:

| Task | Where the answer is | Clicks |
| --- | --- | --- |
| A, B, C: running out? when? by how much? | Home, first line: "Your cash reserve becomes unsafe in 12 days." then "Cash falls to ¥60k, ¥240k below your ¥300k minimum cash reserve." | 0 |
| D: what should I do? | "Secure ¥405k of funding" with ¥150k credit line and ¥255k against the Foshan invoice | 0 |
| E, F, G: how much, total cost, when | You receive ¥405,000.00 · Estimated total cost ¥3,113.93 (lines and basis) · Funds available in 3 days | 0 |
| H: if I do nothing | "Worst point: −¥105k in 30 days if you do nothing." and the If-you-do-nothing row | 0 |
| I: needs my approval? | "Within your signed limits. No additional approval required." (day 34: "Needs your approval: the yearly cost of 32.5% …" and the header badge) | 0 |
| J: why did this happen? | WHAT CHANGED: "Payroll of ¥340k falls due in 12 days." "The next receipt, ¥420k, lands only in 32 days." | 0 |
| K, L: who owes me, who is late | Who owes you on the home; Receivables summary (outstanding, overdue, next payment) | 0 or 1 |
| M: what changed since yesterday | Recent changes (since the last visit once a marker exists); hidden when nothing happened | 0 |
| N: why this plan | "Why this" disclosure; the Compare options list on Cash & funding | 1 |
| O: the calculation | "Show the calculation" (the router's cost lines and formulas) and the forecast table | 1 |
| P: run the judge demo | Business / Demo switch, the story page | 1 |

Deletion passes removed the empty decision and changes cards, the status chip, the footnote, the raw verdict summary at level 1
on Deals (now a disclosure), and the "Day N" labels.

## Known UX debt

- "If you do nothing" on the recommendation repeats the shortfall in full precision beside the short figures above it.
- The Chinese conclusion has no space before the day count ("将在12 天后"); Chinese parity for the new strings is unreviewed.
- (Closed by Wave 4 of the simplification map, #33.) Executor and ledger sentences said "day N" and "what the agent may borrow
  alone" where the Activity headings and the approval card's "Why it needs you" showed them. `GET /ledger` and
  `POST /alerts/{id}/act` now add `message_when` beside each `message`, the verdict view adds `text_when` / `rationale_when` on
  each counter, `message_when` / `cure_note_when` on each violation, `summary_when`, `message_when` on each note, `*_when` twins
  on the plan's sentences and `note_when` / `components_when` on each comparison row, the queue adds `created_when`, and
  `in_words` says the ceiling clause as "the 15.00% limit you signed for funding without your approval". The raw sentences stay
  for the audit level and the Demo views; the `*_when` fields are English only where the route has no `lang`. Still quoting
  the raw lines, for the owners of those files: the home's "Show the calculation" formula (`next_action.formula`, home.py), the
  Deals glance's counter text and the technical summary (`components/deals`, Wave 2/3), the Cash "Other options" notes and
  components (Wave 5, #34).
- Reconciliation detail text carries commitment ids in brackets; the alert title for a late invoice reads awkwardly after the
  invoice words ("Receivable the ¥420,000.00 invoice to … is 2 day(s) past due").
- The Demo trajectory view keeps the old line chart; the story page was not redesigned against the brief's narrative (fog).
- The healthy state says "You're covered" twice (the status word and the headline).
- Deals shows two empty states when nothing has been read ("No buyer message yet", "No active commitments").

## Known technical debt

- `responsive.spec.ts` "the slide-over chat fits the viewport with a long reply" fails on macOS Chromium (both projects, about
  18 px over); the measurement happens during the slide-in animation. Not touched.
- The mock recorder still records the Demo trajectory mocks with the EX01 verdict applied (by design for the engine view).
- `relative_days` rewrites "on / by / on or before / through / repaid / due day N", "(day A to day B)" and "from day A to day B"
  by pattern; an unexpected phrase keeps its day number.
- The approvals badge reads the queue only when the owner is signed in; the live chat's one-approval-at-a-time rule means a
  multi-leg Tier-2 plan would queue only its first leg from the chat (R02 stays open, hence the #15 refinement).

## What was deliberately not merged, and why

The `test/ui-ux` branch as a branch (its single shell is the thing the 5 Oct audit removed); the `/simple` owner overview (a
fourth home); the capex form and the clock on the Business home (a calm home has no calculator or simulation control); the
"Your documents" page (a real owner need, but intake belongs in Deals; it is fog on the map); the engine-side change of
`committed_cure` to call the router (stability mode; the presentation policy achieves the owner-visible result); the strictly
cheapest two-approval plan on day 34 (the owner's one-approval cure is shown and the cheaper option named, because a multi-leg
plan is not one approval yet).
