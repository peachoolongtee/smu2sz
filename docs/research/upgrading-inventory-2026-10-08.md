# Inventory of `feat/upgrading` against `dev` (Waves 0 to 6)

8 October 2026. Read-only research for the lead: what `origin/feat/upgrading` (6 commits on `95c83d8`, the merge base with `dev`) contains, how it looks, where it collides with Waves 0 to 6 on `dev` (`009fcbe`), and what to port. Rules applied: `docs/UX_SIMPLIFICATION_BRIEF.md` (levels 1 to 6, owner's words at level 1, each fact once, calm healthy states) and `docs/HANDOVER.md` sections 3 and 5 (the browser computes no money; every figure is a server display string).

Screenshots: `docs/screenshots/upgrading-2026-10-08/{desktop,phone}/`, from the branch's own `e2e/screenshots.spec.ts` (6 of 6 passed, mock mode, port 3105) plus an uncommitted one-off script for the pages it does not cover. The branch typechecks and lints clean; its mock e2e suite was not rerun.

## 1. Commits and files

| Commit | Author | What it does | Files |
|---|---|---|---|
| `698f362` k | Dylanhzl | Adds `apps/web/AGENTS.md` and `CLAUDE.md` (the Next 16 agent-rules block) | 2 |
| `1bd8089` | Dylanhzl | Merges `origin/dev` as of 7 Oct (pre-wave) | merge |
| `68fc82e` Updates in ui | Dylanhzl | The whole redesign: `.biz` theme in `globals.css`, `kit.tsx`, `tour.tsx`, `backdrop.tsx`, 16 icons, hero home, pill nav + phone tab bar, account sheet, run-plan confirmation, Capex rebuild, Chinese home recordings, `business-words.ts`, plural i18n, 401 state, about 45 new dictionary keys, the handover note | 57 (+13,037/−1,063) |
| `4cf0462` Business pages follow deal outcomes and capex approval status; logic-gap fixes | Dylanhzl | Deals after the buyer answers (DEAL / NO_DEAL), Capex status from the approvals queue, home decisions from the queue, early payment on Receivables, raw executor codes in words, recorder records capex decisions on the stepper's books | 13 (+270/−47) |
| `29fcc33` added new features and edited the navbar spacing | haoencheo2025 | What-if reduced to one summary card, Capex in the nav and tab bar (six tabs), partial-settlement control removed | 8 (+207/−312) |
| `3157f90` edited navbar | haoencheo2025 | Header grid, badge shows a count only on mid widths, a temporary header-check spec | 2 |

Total 65 files, +13,495/−1,357; 6,000 of the added lines are the six `home_summary_*_zh.json` recordings.

File by file. "Collides" means `dev` also changed the file since `95c83d8` (Waves 1 to 6), so the branch edits a pre-wave version; a plain merge conflicts or silently regresses the wave.

| File | State | One line | Collides with dev |
|---|---|---|---|
| `app/globals.css` | changed (+349) | `.biz` token overrides, hero, backdrop, motion, pill buttons, tinted stats | no |
| `app/layout.tsx` | changed | Inter from Google Fonts via `<link>` | no |
| `app/page.tsx` | changed | Home reads `GET /approvals` for "Needs your decision"; `rise` stagger; warnings block; receivables full width | no |
| `app/cash/page.tsx` | changed (rewrite) | Risk card with four figures, option rows as `<details>`, sorted by status, "considered" title once covered, tiles | **yes** (Wave 5: `FundingOptions`, `CurrentFunding`, human plan names, grouped options) |
| `app/deals/page.tsx` | changed | WeChat as channel, status words after negotiation, no chat link in the empty state, page icon | **yes** (Wave 2/3 page) |
| `app/receivables/page.tsx` | changed | Phone list instead of a table, promise shown once, ids de-emphasised, "(commitment …)" stripped | **yes** (Wave 6) |
| `app/activity/page.tsx` | changed | Divided list, "Records verified", "Approved later" by reading the queue, whole-token id replacement | **yes** (Wave 6: `event_text`) |
| `app/approvals/page.tsx` | changed | One banner, no "0 pending", one column, "Back to Home", passes today | no |
| `app/capex/page.tsx` | changed (rewrite) | Hero question, verdict card, "Ways to pay" rows, decision card, status from the queue | no |
| `app/limits/page.tsx` | changed | Owner wording for the APR and Tier 2 stats, Tier 2 sentence, page icon | no |
| `app/whatif/page.tsx`, `components/whatif-results.tsx`, `whatif-controls.tsx` | changed (−312) | Verdict in words plus three figures; meter, covenants, counters, tested-terms cards and the partial-settlement slider removed | no |
| `app/demo/page.tsx`, `app/trajectory/page.tsx` | changed | Duplicate Start button removed; amounts no-wrap | no |
| `components/app-shell.tsx` | changed (rewrite) | Frosted header, pill nav, phone tab bar (6 tabs), round account sheet (limits, tour, language, mode), `document.title`, `<html lang>`, backdrop and tour mounted | **yes** (Wave 6: Ask FLOW, account identity) |
| `components/approval-card.tsx` | changed | Amount large, cost and landing on one line, reason behind "Why it needs you", Capex link | **yes** |
| `components/business/kit.tsx` | **new** (267) | `BizCard`, `SectionHead`, `Avatar`, `Row`, `Disclosure`, `Figure`, `Chip`, `Tile`, `PageIcon`, pill classes, `toneFor`, `initials` | no |
| `components/business/tour.tsx` | **new** (246) | Seven-step first-visit walkthrough, localStorage flag, skipped under `navigator.webdriver` | no |
| `components/business/backdrop.tsx` | **new** | Dot grid, three drifting glows, rings, wave | no |
| `components/business/status-block.tsx` | changed (rewrite) | Navy hero: status chip, headline, cash today 5xl, three minis, round shortcuts, "Why" | **yes** (Wave 1/6: headroom, `status_text`, in-transit headlines) |
| `components/business/next-action.tsx` | changed (rewrite) | Three tinted facts, confirmation panel, everything else behind "Details" | no (text), but dictionary keys collide |
| `components/business/blocks.tsx` | changed (rewrite) | Rows with avatars, three changes then "Show N more", `WarningsBlock`, "decided since" | **yes** |
| `components/business/cash-forecast.tsx` | changed | Short event labels, collision-dropping, two labels on phones, "Forecast" name when covered | **yes** (Wave 1: server `label_short`) |
| `components/business/facility-explainer.tsx` | changed | `localNames` on facility names | no |
| `components/deals/response.tsx` | changed | DEAL and NO_DEAL cards, rounds list, "gap still covered" box, `plainDays` on counter text | **yes** (Wave 3: send button, obligations list) |
| `components/deals/decision.tsx`, `deal-steps.tsx`, `inbox-list.tsx` | changed | Headline follows the outcome; "No deal" step; blocked message shown in place; current message unclipped | no |
| `components/home/fix-alert.tsx` | changed | `plain` mode: zero counts hidden, `OperationResultBox` with rewritten sentences, scroll into view | **yes** |
| `components/chat/chat-panel.tsx`, `next-step.tsx`, `icons.tsx`, `ui.tsx` | changed | Round chat button; class hooks; 16 icons; `PageHeader.icon`, `ErrorState` 401/403, stacked `KeyValueList` | no |
| `lib/business-words.ts` | **new** (100) | `plainDays` (regex rewrite of "day N" in server sentences), `idsToNames`, `sentenceCase`, `localNames` (Chinese names) | no |
| `lib/dictionary.ts` | changed (+512) | New keys, plural templates, 代理 → 助手, 业主 → 老板 | **yes** |
| `lib/i18n.ts`, `lib/chart-helpers.ts`, `lib/mode.ts` | changed | `{n\|one\|other}` plurals; "¥1M" ticks; `/whatif` and `/capex` as Business routes | no |
| `lib/mock/home.ts`, `lib/mock/handlers.ts` | changed | Serves zh recordings; `markFunded()` after a NO_DEAL negotiation | handlers **yes** |
| `mocks/home_summary_*_zh.json` (6) | **new** | Chinese home recordings from the pre-wave API | no (dev has none) |
| `scripts/record-mocks.mjs` | changed | Records zh homes; capex decisions on the stepper's books | **yes** |
| `e2e/*` (13 specs, `helpers.ts`) | changed | `runPlan` helper for the confirmation; new wording; one new temporary spec | 9 of 13 **yes** |
| `docs/handover/05_frontend_ux_fixes.md` | **new** | The teammate's own handover | no |

## 2. Screenshots

Dev's latest set is `docs/screenshots/wave6-2026-10-07/` (no `wave6-2026-10-08` exists); names 01 to 26 match one to one. Heights are viewport screens from each `manifest.json`.

| Branch file | Dev counterpart (`wave6-2026-10-07/`) | Desktop branch / dev | Phone branch / dev |
|---|---|---|---|
| 01-home-day0 | 01-home-day0 | 1.8 / 1.6 | 2.2 / 2.4 |
| 02-deals-inbox | 02-deals-inbox | 1 / 1 | 1 / 1 |
| 03-deals-read | 03-deals-read | 1 / 1 | 1.4 / 1.1 |
| 04-deals-evaluated | 04-deals-evaluated | 1.8 / 1.7 | 2.6 / 2.3 |
| 05-cash-day0 | 05-cash-day0 | 2.4 / 2.7 | 3.2 / 4.5 |
| 06-receivables-day0 | 06-receivables-day0 | 1 / 1 | 1 / 1 |
| 07-activity-day0 | 07-activity-day0 | 1 / 1 | 1 / 1 |
| 08-home-after-go-ahead | 08-home-after-go-ahead | 1.6 / 1.2 | 2.1 / 1.9 |
| 09-home-funded | 09-home-funded | 1.4 / 1 | 1.8 / 1.5 |
| 10-cash-funded | 10-cash-funded | 2.1 / 1.8 | 2.7 / 2.4 |
| 11-activity-funded | 11-activity-funded | 1 / 1 | 1.3 / 1.2 |
| 12-home-day34 | 12-home-day34 | 1.9 / 1.6 | 2.6 / 2.5 |
| 13-receivables-day34 | 13-receivables-day34 | 1 / 1.1 | 1.4 / 1.8 |
| 14-home-day34-pending | 14-home-day34-pending | 2.3 / 2.1 | 3.3 / 3.4 |
| 15-approvals-pending | 15-approvals-pending | 1 / 1 | 1 / 1.3 |
| 16-approvals-approved | 16-approvals-approved | 1 / 1 | 1.1 / 1.1 |
| 17-home-day34-approved | 17-home-day34-approved | 1.6 / 1 | 2.1 / 1.6 |
| 18-cash-day34-approved | 18-cash-day34-approved | 2.1 / 1.8 | 2.7 / 2.4 |
| 19-activity-day34-approved | 19-activity-day34-approved | 1.1 / 1 | 1.5 / 1.2 |
| 20 to 25 (Demo story, mandate, verdict, funding, trajectory) | same names | equal | equal |
| 26-deals-two-offers-demo-walked | 26-deals-two-offers-demo-walked | 1.9 / 1.8 | 2.9 / 2.8 |
| 27-navbar, 27b-tabbar (phone), 27c-account-menu | header of 01-home-day0 | — | — |
| 28-limits | none on dev | 1 | 1.3 |
| 29-whatif | none (dev's what-if is a Demo view) | 1 | — |
| 30-capex-before, 31-capex-evaluated, 32-capex-applied | none (dev's Capex is a Demo view) | 1 | — |
| 33-tour-step1, 34-tour-step2 | none | viewport | viewport |

The branch is longer than dev on every Home state (hero, tinted facts and open warnings add 0.2 to 0.6 screens) and shorter on Cash & funding. Phone captures show the fixed tab bar mid-page: a full-page capture artefact, not the layout.

## 3. Component assessment

Per component: what the owner gains, intuitiveness, load at level 1, palette, hard rules, duplication, verdict.

**`.biz` theme (`globals.css`) and `kit.tsx`.** A banking-app look: grey canvas, 1.25 rem white cards, pill buttons, native `<details>` with turning chevrons, 220 ms reveals, hover lift. Familiar, calm, adds no numbers. Palette: it redefines every `--color-*` token under `.biz` (`#0666eb` brand against dev's `#1558c0`, `#121417` ink against `#0f1c2e`, softer status colours), puts a blue-to-violet gradient on primary buttons, and `kit.tsx` plus `status-block.tsx` use 45 raw Tailwind palette classes (`violet`, `teal`, `orange`, `pink`, `sky`, `fuchsia`, `emerald`, `rose`, `indigo`, `amber`, `red`) that exist nowhere on dev. No money, no day numbers. **TAKE WITH CHANGES**: port `Disclosure`, `Row`, `SectionHead`, `Figure`, `Chip`, `Tile` and the motion rules on dev's token values; map the extra hues onto two or three named accent tokens; drop the gradient buttons unless the owner wants them.

**`backdrop.tsx`.** Decorative glows, rings and a wave drifting behind every page. Adds nothing usable; the brief asks for calm. **LEAVE**.

**`tour.tsx`.** Seven-step first-visit walkthrough, replayable, keyboard and Esc, hidden from Playwright. Explains what "Run funding plan", "Details" and each section do: the product's only onboarding, in the owner's words, no figures. Step 4 lists six sections including "Buy equipment". **TAKE WITH CHANGES**: re-key the copy to dev's labels (Ask FLOW, five sections), tokenise the avatar hues, let the owner set the trigger.

**Header, pill nav, phone tab bar, account sheet (`app-shell.tsx`).** Pills on a white track, approvals badge, round account button opening a sheet (sign-out, Your limits, Show the tour, language, Business/Demo, demo note), `document.title`, `<html lang>`; phones get a bottom tab bar. Tidy and the right phone idiom. Flaws: six tabs truncate ("Buy equi…", `phone/27b-tabbar.jpg`); the Business/Demo switch is hidden from a judge; the chat button loses its label below 1536 px, undoing Wave 6's "Ask FLOW". Collides with Wave 6. **TAKE WITH CHANGES**: port the tab bar (five tabs), pill nav, title and lang, and the sheet's limits and tour rows; keep dev's labelled Ask FLOW, account identity and a visible mode switch in Demo.

**Home hero (`status-block.tsx`).** Chip, headline, note, cash today in 5xl, three minis (reserve; cash at first breach; worst point, merged when the same day), four round shortcuts, "Why" holding the worst sentence and drivers. Reads well cold. Day 0: 10 figures and about 45 words at level 1 (dev: 11 figures, 60 words, including headroom and "What changed"). All server strings, no day numbers; but it drops dev's `status_text`, `headroom_short`, `lowest_headroom_short` and per-lot in-transit headlines, and hard-codes `red-300`, `emerald-400`, `sky-300`, `amber-300` and three gradient tints. **TAKE WITH CHANGES**: port the card shape onto dev's data; drop the desktop shortcuts (the nav is one line above); tokenise; the owner picks navy or white.

**Recommended next step (`next-action.tsx`).** Title, components, three tinted facts (cost, when the money arrives, who decides), the button, everything else behind "Details". Then the **confirmation**: the first press shows "Run this plan? You receive ¥405,000.00; the estimated total cost is ¥3,113.93", the second sends the identical bound request, Cancel sends nothing, a 409 closes it. The brief's section 6 shape and a real safety gain. Level 1: 4 figures, about 30 words (dev: 9 and 90). No arithmetic; `fix-*` test ids unchanged, `fix-open-*`, `fix-confirm-*`, `fix-cancel-*` added. **TAKE AS IS** once the kit is in (tint classes aside).

**Home blocks (`blocks.tsx`).** Rows with avatars and a right-hand amount, three changes then "Show N more", warnings open on the page, a fuller details summary. Rules: a WAITING change is relabelled "decided since" when the queue is empty (a browser inference about an approval), and server sentences pass through `plainDays`. Collides with dev's `event_text` rows. **TAKE WITH CHANGES**: port the row layout and "Show N more"; keep `event_text`; drop the inference; keep warnings closed on a healthy day (day 0 shows "Reserve headroom thin in 32 days" on a covered home).

**`lib/business-words.ts`.** `plainDays` rewrites "on day 0", "on or before day 2", "(day 37 to day 47)", "2 day(s)", "still OPEN", "Commitment CMT-… is ACTIVE", `RESERVE_BREACH` by regex in the browser; `localNames` maps facility names and common executor sentences to Chinese by regex. Day counting only, so not INVARIANT 13; but it is the browser rewriting server sentences, which dev refused: Waves 1, 4 and 6 added `*_when`, `event_text`, `label_short` and row `status` for the same sentences, and every string `plainDays` fixes in the branch's screenshots is already fixed on dev by a server field. `idsToNames` (whole-token replacement, fixing "RI:Foshan Home Retail Co.:2") is a real bug fix dev still lacks (`activity/page.tsx` uses `split/join`). **TAKE WITH CHANGES**: port `idsToNames` and `sentenceCase`; leave `plainDays`; park `localNames` until the owner decides how Chinese server sentences are produced.

**Cash & funding (`app/cash/page.tsx`).** Risk card with four figures (the fourth: "Cash becomes unsafe: in 12 days" or "Not in the next 120 days"), the recommendation card, options as rows that open to their reasons, sorted recommended → alternative → insufficient → unavailable, "Options considered when the plan was chosen" once covered, forecast, two tiles, readings closed. Shorter than dev (2.4 vs 2.7 screens; phone 3.2 vs 4.5). It splits `total_display` at "=" to lead with the total (string layout, no arithmetic). Regressions against Wave 5: "Cheapest committed plan" instead of plan names by source, no `CurrentFunding` after funding, shortfalls visible only when a row is opened, stale rows re-shown with totals. **TAKE WITH CHANGES**: port the row-as-disclosure layout, the fourth figure and the tiles into dev's page; keep `FundingOptions`, `optionName`, `CurrentFunding`, "Why this plan was selected".

**Cash forecast.** Short labels, collision dropping, two labels on phones, "Forecast" when covered, the zone to the axis bottom. Dev's `label_short` already covers the labels; two labels still overlap in `desktop/10-cash-funded.jpg`. **TAKE WITH CHANGES**: port `useNarrow` and the series name; keep `label_short`; fix or drop the collision rule.

**Deals (`decision.tsx`, `response.tsx`, `deal-steps.tsx`, `inbox-list.tsx`, page).** After the buyer answers, the headline is the outcome ("Agreed with the buyer" / "No deal"), the accepted counter is marked, NO_DEAL lists each round with the buyer's words and what still ran on the books with a link to Cash, the stepper ends "No deal" in red; the blocked FastCapital message opens in place ("Show it"); the current message is unclipped. Stops the page recommending a counter after the negotiation ended. Rules clean. Collides with Wave 3's send button and obligations list; the blocked-message change reverses ticket #28. **TAKE WITH CHANGES**: port the DEAL / NO_DEAL branches, the "No deal" step and the unclipped message into dev's components; ask the owner about "Show it".

**Approvals (`approval-card.tsx`, page).** Amount in 3xl, cost and landing on one line, reason and if-declined behind "Why it needs you", one banner, "Back to Home", a decided capex application links to Capex. One screen, clear. The reason the owner approves against is now one click away. **TAKE WITH CHANGES**: port the layout; keep the reason visible on a pending card.

**Capex (`app/capex/page.tsx`).** From the broken table to: a hero question, a verdict card ("Worth buying: it pays for itself by month 31. Best way to pay: 36-month term loan at 5.60%, ¥18,144.62 a month"), three figures, "Ways to pay" rows with monthly checks as pills, the decision card, the file behind a disclosure. The first Capex page a finance director can read. `wayName` reads the rate out of the server label (string only); status comes from `GET /approvals`; "Computed on day N" and "Generated on day N" stay inside disclosures, and the page is now a Business route, so day numbers reach Business mode at level 3. **TAKE WITH CHANGES**: port it; replace the two day-N strings with server `*_when`; nav placement per the owner.

**What-if (`whatif-results.tsx`, controls, page).** One card: the verdict in words ("Breaks your limits"), the codes as chips, three figures (give-aways vs limit, cash vs reserve, cost to cover the gap with the break-even), then the chart. The meter, covenant tiles, counters, tested-terms card and the partial-settlement slider are removed outright. Simpler, but as a Business route its axis reads 0 to 120 absolute days and its chips expose engine codes. **TAKE WITH CHANGES**: port the card as the top of the Demo what-if; keep the removed cards behind disclosures; keep `/whatif` out of `BUSINESS_ROUTES` until the axis speaks in dates.

**Receivables, Activity, Limits.** Phone list instead of a table; quiet ids; "Records verified"; "Approved later" by reading the queue; "Borrow alone up to" / "Needs you above" and the Tier 2 sentence. Presentation; Receivables and Activity collide with Wave 6. **TAKE WITH CHANGES**: port the phone list, the Limits wording and the chain badge words; leave "Approved later" to a server flag.

**`ErrorState` 401/403, plural i18n, "¥1M" ticks, stacked `KeyValueList`, `document.title`, Inter via `<link>`.** Small, correct, no collisions. **TAKE AS IS** (Inter only if the owner accepts a Google Fonts request).

**Chinese home recordings and `lib/mock/home.ts`.** Six zh recordings served in Chinese, taken from the pre-wave API; dev records none. **TAKE WITH CHANGES**: port the recorder lines and `mockHome(dealt, lang)`, re-record on dev's API.

**`zz-header-check.spec.ts`, `docs/handover/05_frontend_ux_fixes.md`, `AGENTS.md`/`CLAUDE.md`.** The spec is marked TEMPORARY. **LEAVE** the spec; keep the handover note as history; the agent files are Next's generated block.

## 4. Logic changes in `4cf0462`

| Change | File | Kind | Dev's answer |
|---|---|---|---|
| Deals headline, response card, step line and inbox label follow the negotiation outcome | `deals/decision.tsx`, `response.tsx`, `deal-steps.tsx`, `deals/page.tsx` | Presentation (reads `negotiation.outcome`, `accepted_counter_id`, `rounds`) | Not fixed: dev still shows "Recommended" and the compare button after a DEAL; dev's one-line `dealDone`/`noDeal` sentence stays |
| NO_DEAL card lists the operations that still ran ("gap still covered") | `response.tsx` | Presentation (filters `operations` by `EXECUTED`) | Not fixed; dev's text says "nothing changed on your books", which is wrong when the plan ran |
| Capex application status from the approvals queue, with the result sentence | `app/capex/page.tsx` | Presentation, but the browser joins two reads (`capexApplication.approval_id` against `GET /approvals`) | Not fixed (Capex is a Demo view on dev) |
| Home "Needs your decision" lists `GET /approvals` instead of the home read's `approvals` | `app/page.tsx` | Decision surface composed in the browser; replaces the server's home view with a second read and a field mapping | Dev keeps `h.approvals`; if a capex application is missing there, the fix belongs in `home.py` |
| "Waiting" change reads "decided since" when the queue is empty | `blocks.tsx` | Inference about an approval's state in the browser | Dev: `event_text` from the server |
| Receivables shows the agreed early payment from the home read before reconciliation lists it; a RECEIVED promise is hidden under the promise list | `app/receivables/page.tsx` | Presentation, but merges two server reads and hides a server row | Dev shows reconciliation's `promised` with status badges; the gap, if real, is a server-side one |
| Plain words for "Commitment CMT-… is ACTIVE", "it is PENDING", `RESERVE_BREACH`, `DSCR_BREACH` | `lib/business-words.ts` | Presentation by regex over server sentences | Dev: `event_text` and `message_when` (Wave 6), `status` on rows (Wave 1) |
| Approval reason no longer repeats its label; sentence case | `approval-card.tsx` | Presentation | Not needed on dev |
| Mock: a NO_DEAL negotiation marks the mock home funded | `lib/mock/handlers.ts` | Mock state only | Dev's mock does the same only through the chat path; a real gap in mock mode |
| Recorder: capex approve/reject recorded on the stepper's books | `scripts/record-mocks.mjs` | Recording fidelity (the approved row names the 36-month loan, not the lease) | Dev's recorder still uses `runCapex(); runCapexApply()` on fresh books; worth taking |

No change computes, compares or reformats money. Two replace a server-composed view with a browser composition (home decisions, receivables promise) and one infers a decision state: not INVARIANT 13 breaks, but the pattern the brief avoids.

## 5. Mocks and e2e

A fresh recording with the branch's recorder against dev's API (port 8009, memory store, cached model) was diffed against both mock sets:

- Fresh vs dev's `mocks/`: identical except `ops.json` (dev's recorder copies `message_when`/`event_text` into each entry) and the six zh files dev does not record. Dev's mocks are true recordings.
- Fresh vs the branch's `mocks/`: 24 files differ. The branch's English mocks are byte-identical to the merge base (`git diff 95c83d8..HEAD -- apps/web/mocks` lists only the six zh additions), so **nothing was hand-edited**; the branch simply carries the pre-wave recordings, which lack `label_short`, `components_when`, `note_when`, `summary_when`, `interpretation`, `*_when` on counters and plan costs, and so on. The six zh files were recorded from that same older API.
- Any port must re-record on dev's API; the branch's `mocks/` must not be merged over dev's.

E2e: the branch changed 12 existing specs (`runPlan` helper for the two-press confirmation in `home`, `activity`, `approvals`, `catchup`, `live`, `screenshots`; new wording in `deals`, `receivables`, `approvals`, `chat`, `whatif`, `demo`; the chat-panel animation wait in `responsive`) and added one temporary spec. Nine of the twelve collide with dev's Wave 2 to 6 spec changes. The `runPlan` helper and the `responsive` animation wait are worth taking with the confirmation.

## 6. Recommendation

Port in this order, each as its own branch off `dev`, smallest form, mocks re-recorded, the integration loop after each:

1. **Run-plan confirmation** (`next-action.tsx` panel, dictionary keys, `runPlan` e2e helper, `home.spec` assertions). Safety gain; no design debate.
2. **Small correct fixes**: `ErrorState` 401/403, plural templates, `axisYuanK`, stacked `KeyValueList`, `document.title` and `<html lang>`, `idsToNames`, the `responsive.spec` wait, the recorder's capex-on-stepper-books change, `markFunded()` on NO_DEAL in the mock.
3. **Deals after the buyer answers**: DEAL/NO_DEAL branches of `RecommendedResponse`, the outcome headline in `DealDecision`, the "No deal" step, the unclipped current message; merged into dev's Wave 3 components (keep the send button and obligations).
4. **Business kit and motion** (`Disclosure`, `Row`, `SectionHead`, `Figure`, `Chip`, `Tile`, reveal/press/chevron CSS) on dev's tokens, with two or three named accent tokens instead of Tailwind palette classes. Then re-skin dev's existing Home, Cash, Approvals, Activity with them, page by page, keeping dev's data fields (`event_text`, `status_text`, headroom, `CurrentFunding`, `FundingOptions`).
5. **Capex page**, with the two day-N strings replaced by server `*_when`, as a Demo view first; Business nav only after the owner's answer below.
6. **Phone tab bar and pill nav** (five tabs), account sheet rows for Your limits and the tour, keeping dev's "Ask FLOW".
7. **Tour**, re-keyed to dev's labels.
8. **What-if summary card** as the top of the Demo what-if, the removed cards behind disclosures.
9. **Chinese home recordings** via the recorder and `mockHome(dealt, lang)`, re-recorded on dev's API.

Leave: `backdrop.tsx`; `plainDays` and `localNames` (server fields do this on dev); the hero's round shortcuts on desktop; the open warnings block on a healthy day; the "decided since" and "Approved later" inferences; the home's `GET /approvals` composition; the receivables promise merge; the branch's `mocks/`; `zz-header-check.spec.ts`; the blue-to-violet gradient buttons.

Open questions only the owner can answer:

1. **Look**: navy hero and gradient accents (the branch) or the flat white card and one blue (dev)? The kit can carry either; the token values must be chosen once.
2. **Blocked messages on Deals**: show the unknown sender's text in place ("Show it", the branch) or keep ticket #28's one line linking to Activity's refused section (dev)?
3. **Capex and What-if in Business mode**: are they owner tools (nav items, tab bar) or Demo engine views reached from Cash & funding's doors? If owner tools, the API needs `*_when` for "computed on day N" and the what-if axis needs dates.
4. **Approval reason behind a click**: may the reason ("32.5% a year, above the 15% limit you signed") sit behind "Why it needs you" on a pending card, or must it stay visible beside the Approve button?
5. **Chinese server sentences**: add a `lang` parameter to the verdict, counter and reconciliation reads, or accept a browser-side name map (`localNames`) as a stopgap?
6. **First-visit tour**: on by default for every new browser, or only from the account menu?
7. **Google Fonts**: may the page request Inter from `fonts.googleapis.com`, or must it stay self-hosted / system?
