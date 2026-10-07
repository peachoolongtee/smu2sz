# Handover: frontend UI/UX fixes, 7 Oct 2026 by Dylan

The frontend-only fixes that came out of a UI/UX review of the web app (`apps/web`). Read this before touching the
Business pages again, then `docs/HANDOVER.md` for everything else.

## 1. State

| | |
| --- | --- |
| Branch | `ui-ux-testing` (the owner's branch), on top of `1bd8089`; the work was started on a separate branch and moved here |
| Committed | **No.** All changes are in the working tree (36 files: 35 modified, 1 new) |
| Scope | `apps/web/` only. Nothing in `services/api`, no recorded mock in `apps/web/mocks/`, no fixture, no financial figure or decision changed |
| Verified | Lint clean, typecheck clean, unit tests 13/13, mock e2e **44 passed, 7 skipped, 0 failed** (desktop and phone) |
| Not verified | The live e2e project (needs the API on :8000). Its two affected call sites were updated (section 5) but not run |

The rule this work kept: the web app renders the server's display strings and never computes money (INVARIANT 13). The
only new arithmetic counts days ("in 12 days") or lays out text; no amount is added, compared or reformatted.

## 2. How to check it

From `apps/web`:

```bash
pnpm lint && pnpm typecheck && pnpm test:unit
E2E_TARGET=mock pnpm exec playwright test           # 44 passed, 7 skipped
E2E_TARGET=live pnpm exec playwright test           # not yet run on this branch
```

If the pinned Playwright browser is not downloaded, point it at an installed one with `PW_CHROMIUM_PATH=<path to Chromium>`.
Playwright reuses a server already listening on :3100; stop any stale one first (`lsof -ti tcp:3100 | xargs kill`) or it
tests an old build.

Screenshots of every Business and Demo page, desktop and phone:
`SHOTS_DIR=$PWD/shots E2E_TARGET=mock pnpm exec playwright test e2e/screenshots.spec.ts`.

## 3. Behaviour changes a reviewer should know about

These change what the owner does or sees, not only wording.

1. **Running a funding plan needs a confirmation.** On Home and Cash & funding, "Run funding plan" (or "Prepare it for my
   approval") now opens an inline "Run this plan?" panel with what the owner receives and the estimated cost. "Confirm and
   run" sends exactly the same bound request as before (`POST /alerts/{id}/act` with the state version and suggestions
   shown); "Cancel" sends nothing. After any answer, including a 409, the panel closes, so a changed alert is re-confirmed.
   Test ids: opener `fix-open-<alert>`, panel `fix-confirm-<alert>`, confirm `fix-<alert>` (unchanged), cancel `fix-cancel-<alert>`.
   The Demo Alerts page button is unchanged (one press).
2. **What-if and Capex stay in the Business shell** when opened from Cash & funding (`/whatif` and `/capex` added to
   `BUSINESS_ROUTES` in `lib/mode.ts`). In Demo mode they still render in the Demo shell, as before.
3. **Cash & funding options are re-ordered on screen**: the recommended plan first, then the dearer plans that work, then
   those that fall short, then sources that are not available. Same rows, same server figures. The "#1, #2" ranks are gone.
   When there is no gap today, the list is titled "Options considered when the plan was chosen" instead of showing stale
   options as current.
4. **Unknown-sender messages on Deals.** The line used to say "1 suspicious message was blocked. See what was refused" and
   linked to Activity, which showed nothing: the message is filtered in the browser and never reaches the server. It now says
   the message from an unknown sender was set aside, and "Show it" opens the sender and text in place.
5. **Receivables lists an early payment once**, under Payments received. Expected early payments shows only promises still
   awaited or lapsed.
6. **Signed out**, owner pages show "Sign in to see your books" with a sign-in button instead of a red
   "Something went wrong (401)" box (`ErrorState` handles 401 and 403).
7. **Header navigation is left-aligned** next to the brand, so the approvals badge appearing never moves or covers it.
8. **The chat button is a round icon** (label only on very wide screens), to cover less content.

## 4. Changes by area

### Shared

- `lib/i18n.ts`: plural support in templates, `{n|day|days}`. All `(s)` plurals in Business strings now use it.
- `lib/business-words.ts` (new):
  - `plainDays(text, today, t)` rewrites day references in server sentences for Business pages: "on day 0" to "today",
    "on or before day 2" to "within 2 days", bracketed ranges such as "(day 37 to day 47)" are dropped, "2 day(s)" to
    "2 days", "still OPEN" to "still unpaid". Demo views keep the server's words.
  - `idsToNames(text, named)` replaces ids with names only as whole tokens (fixes "RI:Foshan Home Retail Co.:2").
  - `sentenceCase`.
- `lib/dictionary.ts`: reworded keys and about 45 new keys, English and Chinese. In Chinese, 业主 became 老板 and 代理
  became 助手 throughout. The Tier 2 example list no longer includes "Generate the borrower file" (the borrower file is
  read-only and never queued, per `docs/HANDOVER.md` section 5).
- `lib/chart-helpers.ts`: axis ticks read "¥0" and "¥1M" instead of "¥0k" and "¥1000k".
- `components/ui.tsx`: `ErrorState` sign-in prompt for 401/403; `KeyValueList` stacks label over value on phones.
- `components/app-shell.tsx`: header grid (section 3.7); account menu wraps its text (it overflowed the screen) and links to
  Limits; Limits in the phone menu; per-page `document.title` ("Deals · FLOW 流"); `<html lang>` follows the language;
  more bottom padding so content scrolls clear of the chat button.
- `components/chat/chat-panel.tsx`: compact chat button.

### Home (`app/page.tsx`, `components/business/*`, `components/home/fix-alert.tsx`)

- Figures: Cash today first, then the reserve, first breach and worst point. Anything below the reserve is red. When the
  first breach and the worst point fall on the same day they show as one figure. On phones label and value line up.
- Recommendation: cost breakdown as a list of legs; the full-precision repeat of the plan moved into "Show the
  calculation"; the confirmation (section 3.1); while an approval waits, one "Review and approve" button and one line.
- "What the agent did" (`FixResult` with `plain`): no tier, sequence number or hash; zero counts hidden; names and
  distances from today in the sentence; a queued request shows one line. It scrolls into view when it appears.
- Warnings are a visible block instead of being hidden in Details.
- Recent changes: day references rewritten; a "waiting" entry reads "decided since" once nothing is pending.
- Who owes you takes the full width when there are no recent changes.

### Cash & funding (`app/cash/page.tsx`, `components/business/cash-forecast.tsx`)

- Options: order and history title (section 3.3); "Costs more than the recommended plan" instead of "admissible but dearer";
  the total leads and "a + b" sits beneath it; rows stack on phones.
- Risk card: the worst-point line that repeated the figure removed; "Cash becomes unsafe" reads "Not in the next 120 days"
  instead of "None"; unsafe figures in red.
- Chart: short event labels ("Payment in ¥420k", not "Receipt the ¥420 ¥420k"); labels that would overlap, sit on the
  breach or lowest marker, or fall off the right edge are dropped; at most two labels on phones; the danger zone reaches
  the bottom of the axis; the line is called "Forecast" when nothing needs fixing.

### Deals (`app/deals/page.tsx`, `components/deals/*`)

- The empty state under an inbox that has messages now says "Open a message to see what the buyer asks for".
- Unknown-sender line (section 3.4).
- The asks card names the app the message came from (WeChat), matching the inbox.
- The recommendation says "If you accept the offer as asked:" above its three figures; the worst point is red.
- Counter texts say "paid within 2 days", not "paid on or before day 2".
- The selected inbox message is shown whole on phones (was truncated).
- Steps read Received · Checked · Reply · Agreed; next steps reworded ("See the counter-offer").

### Receivables, Activity, Approvals, Limits

- Receivables (`app/receivables/page.tsx`): a list on phones instead of a clipped table; ids in plain small text;
  "(commitment CMT-…)" removed from sentences; early payment listed once.
- Activity (`app/activity/page.tsx`): whole-token id replacement; day references rewritten; "Records verified" instead of
  "Chain valid · 2 entries" (the count is in the tooltip); a queued entry shows "Approved later" or "Declined later" once
  decided, matched by operation id or by the approval number in its text (the mock gives the logged entry its own id);
  plainer subtitles; one empty-state style.
- Approvals (`app/approvals/page.tsx`, `components/approval-card.tsx`): one explanation banner instead of two; no "0 pending"
  badge; one column; "Back to Home" after a decision; reasons start with a capital and use distances from today.
- Limits (`app/limits/page.tsx`): "Borrow alone up to" and "Needs you above" instead of "Maximum all-in rate" and
  "Tier 2 threshold"; the threshold rule added as a sentence.

### Demo pages

- `app/demo/page.tsx`: the duplicate "Start demo" button in the page header removed (the story bar has it).
- `app/trajectory/page.tsx`: negative amounts in the cash-events table no longer wrap across lines.

### Chat

- Owner placeholder, empty state and hint no longer mention "EX01", "Tier 1" or "mandate". Chip labels are plainer
  ("Check the Foshan offer", "Where do I stand?"); the text each chip sends is unchanged, because the recorded mock replies
  are keyed to it. The role switch reads "Test as a buyer".

## 5. Test changes (`apps/web/e2e`)

- `helpers.ts`: `runPlan(scope, alertId)` presses the opener, then the confirm button. Used in `home`, `activity`,
  `approvals`, `catchup`, `screenshots` and `live` specs wherever the Home or Cash plan is run.
- `home.spec.ts`: asserts the confirmation shows ¥405,000.00 and ¥3,113.93 and that Cancel runs nothing; new labels.
- `deals.spec.ts`: the unknown-sender line and "Show it"; step "Reply"; "See the counter-offer".
- `receivables.spec.ts`: the early payment appears once, under Payments received, without the commitment id.
- `approvals.spec.ts`: "Nothing waiting for approval" instead of the "0 pending" badge; reason matched case-insensitively.
- `chat.spec.ts`: role radio "Test as a buyer".
- `responsive.spec.ts`: the phone chat-panel test waits for the 0.18 s slide-in to finish before measuring. This was the
  known failure in `docs/HANDOVER.md` ("431 px on a 412 px viewport"): the mock answers in 10 ms, so the panel was measured
  mid-slide. The layout itself was always 412 px.
- Plural wording in assertions ("2 days late", "1 approval waiting").

## 6. Still open: needs the backend

These come from sentences or values the server writes. The frontend shows them as sent, so fixing them needs an API
change, which was out of scope.

| What the owner sees | Where |
| --- | --- |
| The approval says the fix keeps cash safe "for the next 12 days"; the recommendation says "120 days" | `GET /home` next action vs the queue's `presentation.protects` |
| "Why this" names a different plan and cost (¥336,000, ¥2,994.08) from the recommended one (¥255,000, ¥3,113.93) | `next_action.why` / `detail` |
| "Cash stays above your reserve … it comes close: cash sits exactly on the reserve", under a WATCH badge with "You're covered" | home `headline`, `note`, `status` |
| Formula-style reasons ("annualised = 32.52%"), 32.52% in one place and 32.5% in another | approval `reason`, executor messages |
| The same breach stated three or four times (headline, note, worst, "if you do nothing") | home sentences |
| Raw codes and snake_case inputs in chat replies, Verdict and the engine Funding page | `/nl`, verdict, router |
| Chinese mode is half English: every server sentence stays English in the recordings | `GET /home?lang=zh` and others |
| "1 days" on the engine Funding page | `time_to_cash_display` |
| Activity on day 34 shows "No agreements with buyers yet" while Receivables shows the agreed early payment | the recorded mock ledger; check in live mode |

## 7. Ideas not done

- A dark theme: the app ignores the system dark setting.
- An action on a late invoice (remind the buyer).
- Approve or decline directly from Home; the owner's earlier decision keeps the buttons on the approval card.
- The cheaper two-approval option named on Home cannot be chosen.
- Capex takes no input: one fixed "Evaluate the ¥600k machine" button.
- The Verdict page (about 5 screens on desktop, 10 on phone) and the engine Funding table are still engineer-facing.

## 8. Business redesign (second pass, same day)

The owner asked for the Business pages to be simpler and to look and move like Revolut: details behind a click,
calmer pages, a banking-app feel. Same rules as above: `apps/web` only, no API or architecture change, no figure computed.
Mock e2e after this pass: **44 passed, 7 skipped, 0 failed**; unit tests 13/13; lint and typecheck clean.

**Where the look lives**

- `app/globals.css`, section "Business theme": every token is redefined under `.biz` (the Business shell's root), so the
  Demo shell keeps its old look. Grey canvas `#f4f5f7`, white cards, `--radius-card: 1.25rem`, soft two-layer shadows, one
  blue `#0666eb`, near-black ink `#121417`, pill buttons (`--radius-btn`), a deep-navy hero with a status-tinted glow.
- Motion, all in that CSS: buttons and pressable rows scale to 0.97 on press; cards marked `.lift` rise 2 px on hover
  (only on devices that really hover); `<details>` chevrons turn and their content eases in (220 ms); page sections rise in
  with a 40 ms stagger (`.rise`). All ease-out, under 400 ms, transform and opacity only; the global
  `prefers-reduced-motion` rule turns them off.
- Inter is loaded with a `<link>` in `app/layout.tsx`, not `next/font`, so an offline build falls back to the system font
  instead of failing.
- Shared primitives (`PageHeader`, `Card`, `Badge`, `Button`, `Segmented`, `NextStep`) got class hooks (`page-head`, `card`,
  `card-head`, `badge`, `btn-*`, `seg`, `next-step`) that the `.biz` CSS restyles. Their markup is otherwise unchanged.

**New pieces**

- `components/business/kit.tsx`: `BizCard`, `SectionHead`, `Avatar` and `initials`, `Row` (list row: avatar, title, quiet
  line, amount on the right, optional link and chevron), `Disclosure` (a styled native `<details>`), `Figure`, `Chip`,
  `BizPageHeader`, `Tile`, and pill link classes.
- `components/icons.tsx`: a 24-unit icon set for the Business shell (home, deals, wallet, inbox, activity, user, chevrons,
  alert, clock, shield, sliders, cart, spark).

**What changed on each page**

- Shell: frosted sticky header; the five sections as pills on a white track (the current one black); a round account button
  whose sheet holds sign-out, Your limits, language, the Business/Demo switch (moved there from the header) and the demo
  note. Phones get a bottom tab bar with icons; "Cash" and "Owed to you" are the short tab labels, the full names stay as
  each link's accessible name. The brand tagline shows only on very wide screens.
- Home: a navy hero card with the status chip, the headline, the note, today's cash in large type, three small figures,
  round shortcuts (Deals, Cash & funding, Receivables, Ask), and the worst point and drivers behind "Why". The recommendation
  is one card: title, amounts, three facts (cost, when the money arrives, who decides), the button, and everything else
  behind "Details". Decisions, warnings, who owes you and recent changes are list rows; recent changes show three, the rest
  behind "Show N more".
- Cash & funding: one risk card with four figures; the same recommendation card; each option is a row (name, chips,
  total) that opens to its reasons; the chart in its own card; What-if and Equipment as two tiles; debt readings closed.
- Approvals: the amount large, the cost and landing day on one line, the buttons, and the source, invoice, reason, after and
  if-declined behind "Why it needs you".
- Activity: the timeline is a divided list instead of boxed entries.
- Deals, Receivables and Limits take the new look through the shared hooks; their structure is as in sections 3 and 4.

**Specs touched in this pass**

- `demo.spec.ts`: opens "Why it needs you" before reading the approval reason.
- `responsive.spec.ts`: clicks "Cash & funding" inside the main navigation (the hero has a shortcut with the same name).

## 9. Third pass: translation, Equipment page, walkthrough, colour

Asked for by the owner: finish the Chinese translation, fix the Capex page (text breaking into single letters) and make it
a real Business page, add a first-visit walkthrough, and give the pages more colour. Frontend only. Mock e2e after the main
changes: **44 passed, 7 skipped, 0 failed**; unit tests 13/13; lint and typecheck clean. The walkthrough's placement was
adjusted after that run (lint and typecheck clean; the walkthrough never runs in the test browser, see below).

**Chinese**

- The dictionary was already complete. What stayed English were the server's sentences: in mock mode the six Home
  recordings existed only in English. `scripts/record-mocks.mjs` now also records `GET /home?lang=zh` at each of those
  points (reads only, so the books are unchanged), giving `mocks/home_summary_*_zh.json`; `lib/mock/home.ts` serves them when
  the language is Chinese. Recorded from the unchanged API on :8011 (in-memory store, cached model answers); every existing
  mock file came out byte-identical. Re-record with the usual command in `apps/web/README.md`.
- `localNames(text, lang)` in `lib/business-words.ts`: in Chinese mode, names stored in English on the books (facilities,
  scheduled cash events, a few alert titles) and the commonest executor and reconciliation sentences are shown in Chinese.
  Names and sentence shapes only; amounts are carried through untouched. Applied on Home, Cash & funding, the chart, the
  approval card, Activity, Receivables and the Deals counter texts.
- Still English in Chinese mode: sentences the API writes without a language parameter (the verdict, counters' rationale
  beyond the patterns above, some reconciliation details) and the buyers' own messages, which are shown as received.

**Equipment (Capex) page** (`app/capex/page.tsx`)

- The single-letter text was the last column of the financing-structures table, squeezed until words broke letter by
  letter. The table is gone.
- Rebuilt for the owner: before evaluating, a hero card with the question and one button, and three short explanations;
  after, a verdict card ("Worth doing" with the server's recommendation and four figures; the basis behind "How this was
  worked out"), "Ways to pay" as rows (monthly payment on the right; the monthly cover checks as coloured pills, the charges
  and notes one tap away), the decision card (Apply, Prepare the borrower file, Tier 2 explained behind a disclosure), the
  borrower file with its downloads, and "Why a structure fails" and the assumptions behind disclosures. Test ids kept.
- "Equipment" is in the Business navigation on wide screens and in the account menu on phones (the tab bar keeps five).

**Walkthrough** (`components/business/tour.tsx`)

- Seven steps on the first visit to Home: welcome; the status card; the recommendation (what "Run funding plan" and
  "Details" do); the sections and what each is for; the account menu (limits, language, approvals badge); the chat; done.
  A spotlight with a dimmed page, a card placed beside, below or above the element (or pinned to the bottom when the element
  is very tall), progress dots, Back / Next / Skip, arrow keys and Esc.
- Shown once per browser (`localStorage` key `tl-tour-done-v1`), replayable from the account menu ("Show the tour again").
- It never starts when `navigator.webdriver` is true, so Playwright sees the page itself. To look at it in a script, define
  `navigator.webdriver` as false in an init script.

**Colour**

- A soft blue, violet and teal glow behind every Business page; a more vivid hero (navy to royal blue to violet).
- Each section has a gradient icon tile beside its title: Cash teal, Deals violet, Receivables and Equipment orange, Activity
  pink, Approvals amber, Limits blue (`PageIcon` in the kit; `PageHeader` takes an optional `icon`).
- Primary buttons are a blue-to-violet gradient with a soft glow; the hero's round shortcuts are coloured; the
  recommendation's three facts are tinted; buyers get a stable avatar colour (`toneFor`); summary tiles get a tint each.
- New avatar and chip tones in the kit: violet, teal, orange, pink, sky.

**Follow-up (same day)**

- The page is labelled **Capex** in the navigation (it was "Equipment" and only on wide screens). It is in the desktop pill
  navigation and in the phone tab bar, which now has six tabs (short labels: Cash, Owed, Capex); the account-menu link to it
  was removed as redundant.
- Background art behind every Business page (`components/business/backdrop.tsx`, styles `.biz-dots`, `.biz-blob*` in
  `globals.css`): a dot grid that fades out from the top, three large soft glows (blue, violet, teal) drifting over 26 s,
  thin concentric rings in the top-right corner, a rounded square on the left and a wave line along the bottom. Fixed, behind
  the content (`-z-10` inside the shell's `isolate`), hidden from pointers and screen readers; the drift stops under reduced
  motion. Lint and typecheck clean.

## 10. Logic-gap pass (in progress, paused)

Found by walking the whole demo story and reading every Business page at each stage. Frontend only; lint and typecheck
clean; the e2e suite was not rerun after these changes.

Fixed:

- Deals after the buyer answers: the headline, the response card, the step line and the inbox label follow the
  negotiation. DEAL shows "Agreed with the buyer" and the accepted counter marked "Accepted by the buyer"; NO_DEAL shows
  "No deal", each round with the buyer's refusal, and, when the funding plan ran anyway, what ran (it no longer says
  "nothing changed on your books"). No "Recommended" or "Compare another option" after an outcome.
- Capex: the application's status comes from the approvals queue (waiting, approved, declined), with the decision's
  result in words; a decided capex approval links back to Capex.
- Home: "Needs your decision" lists the approvals queue (the header badge's source), so a capex application shows there.
- Mock mode: the hard-line negotiation marks the mock home as funded, so Home and Cash & funding stop asking to run a plan
  that already ran.
- Receivables shows an agreed early payment the home names even before reconciliation lists it.
- Plain words for raw executor text on Business pages ("Commitment CMT-… is ACTIVE", "it is PENDING", RESERVE_BREACH).
- Approval card: the reason no longer repeats its own label.

Not finished:

- `scripts/record-mocks.mjs` now records the capex approve/reject decisions on the stepper's books, so the approved row will
  name the 36-month loan like the queued request (today the recorded row says "Equipment lease"). The mocks were **not**
  re-recorded yet: run the recorder (README) and check that only `mocks/ops.json` changes.
- Rerun the mock e2e suite; specs that read the old Deals wording after a negotiation may need updating.
- Backend items found so far (not changed): none that block these fixes. The API's verdict and counter texts have no
  language parameter, so they stay English in Chinese mode.
