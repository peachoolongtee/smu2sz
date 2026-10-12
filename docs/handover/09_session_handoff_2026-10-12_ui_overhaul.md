# Handoff 09: the UI overhaul of 12 October 2026 (Windows lead session)

Written by the lead session that ran on the owner's Windows machine on 12 Oct 2026. It follows handoff 08 (same day, the Mac
session) and replaces this session's private memory. Read it first, then `docs/HANDOVER.md` for the standing rules.

## 1. What the owner asked for, in order

1. Carry on with the API half of ticket #103 (the debt of the contracts merge). This lifted the commit hold for that work.
2. A UI overhaul, page by page, starting with Home: the page was "too overloading", with no chart, no hierarchy and no motion.
   The owner supplied two screenshots as a template, asked for mockups, chose mockup **A · One picture**, then its refinement
   **A1 · Seamless** ("go with A1 with the frosted plan bar and do the frosted top bar on scroll"), and asked for deals to be visible
   on Home.
3. "Implement all these first, afterwards do the same for the rest of the other pages, make sure it is consistent … if there are any
   ambivalence that needs my decisions on any screens, create mockups of the screens so I can review them and build the others first."
4. Yes to bundling the headline font as a package.

The mockups are a design canvas in the owner's Claude account ("FLOW Home Mockups": Home A / B / C, A1 and A2, and two Deals layouts);
all nine boards are kept in the repository under `docs/design/mockups-2026-10-12/` with a README that names each and its status (canvas files, not pages; `SeamlessA` is the approved A1).

## 2. What was built (all on `dev` after this merge)

**The page pattern (written into `apps/web/DESIGN.md`, last four sections).** Every Business page: the answer is the `h1` and sits on
the page with no card; one picture where the data supports one; one raised surface, the action (frosted, sticky at the bottom from
`lg`, in flow on a phone); everything else unboxed, small-caps captions and hairlines; the top bar is the canvas colour at 70% with
blur, so it reads as frosted glass only when content passes under it; the sidebar is seamless with counts; headlines are Plus Jakarta
Sans Variable, bundled with the app (`@fontsource-variable/plus-jakarta-sans`, about 27 KB for an English page, no font host).
The mockups of the Deals page and of the callouts are `DealsCompare` and `HomeCallouts` in that folder. Three rules of the old guide changed on the owner's instruction and are rewritten there: the navy "deep block" is the Demo strip only;
the chart's one line-draw is an allowed motion; a labelled chart fed by the server's series is not a sparkline.

| Page | What it is now |
| --- | --- |
| Home | Pill, headline, note; the cash picture (do nothing against FLOW's plan, reserve, shortfall, labelled events, cause chips, a toggle); the plan bar; Your deals (an open offer leads its row with FLOW's read and cost); who owes you; Also on your radar |
| Receivables | The headline sentence with a status pill; a facts row; the chase bar; "Who pays when" (a time axis centred on today); the table on hairlines |
| Activity | The "now" sentence as the heading; a rail with day captions, actor icons, time-passed separators, filter chips, one Details toggle; document rows in words |
| Approvals | The question as the heading; the pending approval as the raised card: three facts, why it needs you, the two cash lines (decline / approve) with the server's sentences as captions, the quote behind a fold |
| Cash & funding | Headline; the picture first with a 30 / 60 / 120 switch; ways to cover the gap as a radio group with cost and coverage bars (choosing a row draws its line); the plan bar; funding sources with utilisation bars |
| Documents, Limits, the decision record, What-if, Equipment | The same pattern, no change of content |
| Deals | Built on 12 Oct after the owner chose ("Deals 1 with the three-column comparison", then the lead's "three paths on one chart"): the verdict as the heading; each ask with its cost bar and the total against the limit; **three paths on one chart** (the offer as asked and each reply, always drawn as ghosts; the picked one thick with a band and a subtitle that says what it means); six stops and Play that move a cursor, with each column showing its cash that day; three columns (cost, terms with "instead of", who decides); the reply in the bar, in flow |

**Shared components.** `components/business/cash-picture.tsx` (plain SVG; baseline and alternative series, the server's axis, label
placement by priority: lowest points, the reserve, line names, events; a label that would collide is skipped), `action-bar.tsx`,
`who-pays-when.tsx`, `components/deals/stage-track.tsx`, `Card flat`, `Stat bare`. The recharts forecast on Cash is gone; recharts
remains for the Demo and What-if charts.

**The server side (additive presentation reads; the engine stability set is untouched; `app/domain/models.py` gained one optional
field, `ContractRecord.superseded_by`).**
- #103 API half: a later confirmed buyer contract marks the earlier one superseded and says "replaces …"; ids out of the Deals read;
  whole status sentences; the outbound guard also protects a contract's dates, window days, retention months, party names and clause
  text for its own counterparty; a slim projection of contract records for the guard; rollback, double-confirm and oversize-upload tests;
  `cash.lowest_tone`.
- New for the pages: "at or above" when the lowest point is the reserve itself; ledger sentences without ids and `document_id`,
  `day_when`; `GET /deals` `open_offer` (FLOW's read, cost, five stages), `needs_you`; `GET /nav/counts`; `POST /router/plan` rows carry
  `series` (the cash line if that plan ran); `GET /approvals/queue` `presentation.series_if_declined|approved` and their lowest points;
  `GET /offers/{id}/picture` (the offer as asked and each reply, as cash lines); `receivables.headline|headline_tone|headline_note`;
  axis ticks from the server wherever a series is returned (`cash.axis`, `cash.axes[window]`, `series_axis`, `series_axes[window]`,
  `presentation.series_axis`, picture `axis`); `cash.picture_days`, `cash.picture_title`; `next_action.components[].amount_fen`.
  The golden router digest is unchanged once the display-only `series*` keys are left out (`tests/books/test_modules_on_books.py`).

## 3. The gate on the merged tree (this machine, Windows, zero retries)

Run by the lead on `int/ui-overhaul` (the tree merged into `dev`), one command after another on an otherwise idle machine: the backend rows at 5490ebd, the web rows again at f8a317f after a last web-only fix (on Cash the plan bar sits in flow, so nothing covers the chart), with the same counts both times:

| Check | Result |
| --- | --- |
| Backend, `SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider` | 6,881 passed, 37 skipped (25 min) |
| `scripts/run_scenarios.py --inproc` | 49/49, 87 turns |
| `scripts/demo_run.py` | exit 0 |
| `python -m app.security.attacks --report` | 259 attacks (126 API, 43 + 64 + 26 chat), 0 with harm |
| Web `pnpm typecheck`, `pnpm lint`, `pnpm build` | clean |
| Web `pnpm test:unit` | 91 passed |
| Mock e2e (`E2E_TARGET=mock`) | 201 passed, 41 skipped; 210 passed, 32 skipped with `E2E_STRATEGY=1` |
| Live e2e (`E2E_TARGET=live E2E_LIVE_PORT=3183 E2E_API_PORT=8183`) | 86 passed, 14 skipped; 94 passed, 6 skipped with `E2E_STRATEGY=1` |

Not run in this session: `scripts/evaluate.py`, the language-boundary certification, the PostgreSQL concurrency cases (they are among the
37 skipped) and `scripts/build_deliverables.py`; no engine figure moved, so the evidence under `services/api/evals` was not regenerated.

**After the Deals page** (run on `int/deals`, the tree merged into `dev` last): backend 6,895 passed, 37 skipped; scenarios 49/49; the demo run
exit 0; 259 attacks, 0 with harm; web typecheck, lint and build clean, unit 91; mock e2e 211 (221 with `E2E_STRATEGY=1`); live e2e 96 (104
with the flag, run twice); no server error in any live log. The first run of this gate failed and was right to: the offer picture read
answered 500 for an offer that could no longer be drawn (now `available: false` with a sentence), and the send confirmation was unmounted
when the picture arrived (now a placeholder until it does). Both have regression tests.

The EX01 evaluation benchmark (`tests/funding/test_benchmark.py`, 350 ms) fails on this machine at about 400 ms on `dev` before the
overhaul and on the merged tree alike (measured twice each on a quiet machine): the known loose end of `docs/HANDOVER.md`, not a
regression. `SKIP_PERF_BENCH=1` hides it.

## 4. Outstanding

**The owner**
- **"What moves your cash"**: the lead proposed replacing the chip row under the cash picture (Home and Cash) with callout pills joined to
  their steps by leader lines, a flow strip of money in and out on the chart's own day axis, and one card that follows the focus (press a
  pill, step, or Play). The mockup is `docs/design/mockups-2026-10-12/HomeCallouts.dc.html`; nothing is built until the owner says go. It
  needs one small read addition (per movement: below the minimum or not, and a status sentence).
- The owner items of handoff 08 section 3 stand (map #88's build, #104, the readers and interviewers, a Postgres run, fonts are now done).

**Known and accepted, with the reason**
- The outbound guard matches a protected contract date or "N months" as plain text: a reply to a different counterparty that happens
  to contain the same date is blocked. It fails closed (U-014). A context-bound match (next to the owner's name, as payment days are)
  is the fix.
- An offer that has arrived but has not been evaluated is known to the Deals read only from the session's documents, so it is not
  listed after a restart (U-015). A store `offers()` listing is the fix; in the Demo an offer is evaluated at once.
- Approvals with several pending show several filled Approve buttons (as before the overhaul). Every Demo state has one.
- In mock mode a Chinese page shows English sentences on Cash, Home's deal rows and Receivables (those recordings are English only);
  the live app sends `lang`.
- What-if draws its own chart, not the shared picture. Equipment is titled "Capex" on its page.
- The Chase button on Receivables is a secondary button: existing strategy specs require no filled button there.
- The sticky bar can cover content on a very short window; the consistency pass found no covered control at 1280x800 and 390x844.

**Small follow-ups**
- `approval presentation` could carry the floor, today and the horizon so Approvals can drop its extra home read.
- The web half of #103 that is not a page redesign (Documents page focus and scroll, the tokens `--color-new`, the deal picture's
  internals) is still on the ticket.

## 5. How this session worked (unchanged protocol, with what was learnt on Windows)

The lead specified, reviewed in the browser and from screenshots, gated and merged; sonnet implementers built in their own worktrees
under `.claude/worktrees/` from spec files (kept beside each worktree, not committed). What was learnt:
- An implementer stops after about 50 tool calls; resume it with a message that names the committed tasks and what remains. Ask for
  the report explicitly; twice a finished agent's report did not arrive and the lead read the branch instead.
- Two web implementers can run at once if each has its own ports: `E2E_PORT` moves the mock web server (default 3100),
  `E2E_LIVE_PORT` / `E2E_API_PORT` the live pair. Port 3000 and 8000 belong to other programs on this machine and are never used.
- Keep shared-file additions (`lib/dictionary.ts`, `lib/types.ts`, `DESIGN.md`) in one marked block per branch; the only conflict in
  six merges was two blocks appended to `DESIGN.md`.
- An API change that alters sentences is not merged on its own: it goes into an integration branch with the web catch-up and
  re-recorded mocks, and the whole gate runs once on the result (`int/ui-overhaul` here, as `int/contracts` before it).
- The lead's review caught what the suites did not: a line's name drawn beside the other line, an axis scaled to the whole horizon,
  a dropped "lowest" label, a heading coloured by tone. Look at the page.
- A full backend run takes about 27 minutes here, the four browser suites about 15.

## 6. Kickoff text for the next session

"Read `docs/handover/09_session_handoff_2026-10-12_ui_overhaul.md`, then `docs/HANDOVER.md` section 3 and `apps/web/DESIGN.md`'s last
sections. `dev` holds the A1 overhaul of every Business page, Deals included. Continue with the outstanding list in section 4; its first
item is the owner's go on the callouts for "What moves your cash"."
