# Handoff 14: the overhaul mid-Slice B, Home round three (13 Oct 2026, evening)

Read this first on a new machine. It carries everything a session needs to continue map #121 without the transcript that
wrote it. The standing protocol: the lead architects, writes the brief, reviews and merges; implementation is delegated
(sonnet `implementer` / `frontend-engineer`), review and verification to independent agents; one worktree per agent;
`--no-ff` merges into dev; plain one-line commits, no attribution lines; the engine stability set is read-only
(app/financial, verifier, funding, alerts, operations, clock, books, mandate, covenants, domain/models.py); INVARIANT 13
(the browser computes no money/date/share/percentage word; every string is the server's or the dictionary's, en and zh,
您 voice; no ids or day numbers in Business; 13 px floor for a financial qualifier). The owner's process rules
(13 Oct): delivery over process; vertical slices; one frontend owner per connected workflow; focused tests while
building, the full mock suite + whole live project + API suite at integration and release checkpoints only; money /
authority / execution / settlement changes always get an independent verifier.

## Where dev stands (origin/dev f2cd77ef and later)

- Home V2 is the Home, in the owner's mockup language, round two merged (4fdad9ae): the selection transform with the
  donut, the context panel, Ask FLOW in the header. Round three is in flight (below).
- Slice B SERVER is on dev (e728867f): the selection contract (`context` on every page read, app/api/selection.py), the
  Deals `queue` in tiers, the commitment `receipt` block, Ask FLOW `scope` / `scope_used`, zh timing words.
- Slice B WEB is NOT on dev. It is on `feat/slice-b-web` (b4cb713a, pushed): Deals (queue + three levels + receipt),
  Customer, Ask FLOW scope chip, What-if, Approvals receipt, plus a fix for a real crash (Ask FLOW called the Home ROUTE
  function directly, leaving FastAPI `Query` defaults in place; `test_chat_home_reads.py` pins it). Gates were green
  (mock 353, live 104, unit 128) but the independent verifier's walk of the audit's journeys 1–2 found defects, so a fix
  batch runs on two branches (below). Merge order: fixes → Slice B → dev; then Home round three (it will need dev merged).
- One command to run locally: `scripts/dev.sh live` (API :8000 with in-memory books + the web :3000 against it, the
  sign-in prefilled) or `scripts/dev.sh mock`. The repo-root `.env` points at a hosted database; the scripts ignore it.
  The owner header is `X-Owner-Token: demo-owner-token` (DEMO_MODE on, OWNER_TOKEN unset). Busy books:
  `POST /demo/reset?scenario=busy`.

## Gates (copy exactly)

- API: `cd services/api && SKIP_PERF_BENCH=1 uv run --project "$PWD" --directory "$PWD" pytest -o addopts= -p no:cacheprovider tests/api -q` (≈1100).
- Web: `pnpm run typecheck`, `pnpm run lint`, `pnpm run test:unit` (128).
- Mock e2e: `E2E_TARGET=mock E2E_PORT=<free port> pnpm exec playwright test --output <own dir>` (≈353 + 40 skipped).
- Live e2e: `SKIP_PERF_BENCH=1 E2E_TARGET=live E2E_LIVE_PORT=<p> E2E_API_PORT=<p> pnpm exec playwright test --project=live --output <own dir>` (≈104 + 20 skipped; a single file is `<file> --project=live`).
- Two Playwright runs in one worktree must have different `--output` dirs (they share test-results otherwise). Never ports 3000/8000 for agents. Never an unscoped `pkill`. Never bare `git stash`.
- Mocks are recorded, never hand-edited: `node scripts/record-mocks.mjs --api http://localhost:<port> --no-exposure`
  against an API WITHOUT FEATURE_EXPOSURE for the standard set; `--exposure` / `--buyer-exposure` against one WITH it;
  `--home-v2`, `--inputs`, `--overview`, `--strategy` strategies. Recording API env: `FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 [FEATURE_EXPOSURE=1] SKIP_PERF_BENCH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1`.

## In flight when this was written (three agents on this Mac; their branches are pushed as they stood)

### A. Slice B fix batch, server: `feat/slice-b-fixes-api` (from b4cb713a; services/api only)
Decided by the lead from the verifier's findings; each fix has a test; tests/api green at the end.
- S1 A receipt for every sendable reply: `workspace.priced_responses[]` beside `priced_response`, one per sendable
  counter in verdict order, each with its OWN send plan and `receipt` (eleven fields); `executes_now_text` names the draw
  and says the funding runs on send whether or not the buyer agrees (verify in decide.py `_negotiate_locked`; do not
  change it). The verifier saw Option B of EX01 send ¥405k of funding with no "runs now" line.
- S2 `LAPSED` decision state (the invoice the offer was about has since been settled under another agreement; the fact
  offer_picture.py uses for "can no longer be drawn"): out of every queue tier; the customer overview says Lapsed with no
  reply ready and no concession figure; the exposure block says why in words, not a transient error.
- S3 The busy seed negotiates EX08B (Dongguan's rebate) instead of EX03, so EX01/EX02/EX03 stay live on RCV-A and
  Option A is sendable (journey 1 needs a sendable Foshan counter). If the cooperative kernel cannot agree EX08B, no
  negotiated agreement and the lead decides. New day-0 counts go into test_demo_busy / test_deals_queue.
- S4 `/worklist.counts` = `queue.counts` (promises under Agreements, `agreements` added) so Home and Deals agree.
- S5 Ask FLOW: a company-wide read under a narrower scope either filters to that customer (waiting, overdue,
  receivables, arrival, late payment) or reports `scope_used` kind `company` (cash status, changes); Business words in
  those replies (no APR ids, no "day -15", no raw enum).
- S6 `POST /whatif` and `GET /whatif/presets` take `offer_id` (fallback `buyer_id`) and run on that offer's buyer and
  invoice; `invoice_text` and `scope_text` in words.
- S7 Words: the pending approval row's consequence (not the decline outcome); no raw PENDING after approve, no "done";
  an AGREED decision never shows the stale clarification; no serialised "None"; the abstention sentence in zh and
  Business words; "forward" on the ¥0.00 promised-cost footer with the immediate discount on its own line.

### B. Slice B fix batch, web: `feat/slice-b-fixes-web` (from b4cb713a; apps/web only)
Now: W1 the queue's Customers tab clips at 1440/390 (wrap or scroll with a cue); W2 the scope chip's widened choice must
not return on Back (route memory in lib/chat-scope-model.ts goes); W3 12 px financial labels on Approvals and What-if →
13 px; W4 literal "None" lines omitted; W5 the What-if "Which negotiation?" list is DECISION rows only; W6 an AGREED
negotiation's pane shows the agreement record, never "I can't safely evaluate this yet"; W7 a needs-approval ask with no
counter shows the ask's own cost with its basis (the picture's asked path) and the authority sentence, no invented accept
control. After the server branch is merged in: W8 the send review reads the path's own `priced_responses` entry and the
fallback receipt in lib/receipt.ts is deleted (no server receipt → no Send, "FLOW has not priced this reply"); W9 Lapsed
words; W10 What-if passes `offer_id`, shows `invoice_text` / `scope_text`; W11 Home shows the queue's counts, busy specs
follow; W12 approval words render as sent. Decided NOT to change: compare/pick toggles replace history; the phone order;
`scenario=late` client-side.

### C. Home round three: `feat/home-round-three` (from dev 70e1af5e; Home files + the header input)
The brief is docs/design/flow-mockup-2026-10-13/02_home_round_three.md (five sections): a selection always lands with the
company line and the selected card's top at the top of the content on every width (the owner's "it takes me into Deals"
was the page landing mid-card on the comparison table, verified at 1100/768/375); the deal card opens compact (≤ 560 px,
the comparison behind the Cash impact toggle); cards smaller again (16 px padding, 32 px figures, the row ≤ 260 px at
1440, headline 32 px); Ask FLOW centred in the header with six example questions the chat answers, ending on a resting
"Ask FLOW anything…"; "FLOW action ready" said once, in the recommendation card.

## After the three hand back

1. Server batch: read the report, run tests/api, merge `feat/slice-b-fixes-api` into `feat/slice-b-fixes-web` (tell the
   web agent, or do it), the web agent binds W8–W12 and re-records the mocks it needs.
2. Merge `feat/slice-b-fixes-web` into `feat/slice-b-web`; merge dev into it; launch a `verifier` on the audit's journeys
   1–2 (busy AND golden books; the verifier's previous report is summarised in the map memory and in this file); full
   mock + whole live + tests/api; `--no-ff` into dev; close #143 with the counts.
3. Home round three: merge dev into it (expect conflicts in globals.css, chat-panel, cash-preview, helpers, design-system
   spec: prefer the Slice B side for the kit and Home's side for Home); focused gates + the full pair; look at it live on
   the busy books; `--no-ff`; the owner judges.
4. Then Slice C (#144: Receivables → Cash → Approvals as one journey, the reconciliation section from Dylan's
   ui-ux-testing branch, the Cash timeline #113), Slice D (#145: Activity + Demo, the trust views and the tour fix from
   ui-ux-testing, "Load alternate scenario" with loss preview + restore), Slice E (#146: kit consolidation, evidence links
   for Documents/What-if/Capex/Limits/engine views, bilingual/tablet/a11y, the release checkpoint). The decisions for each
   are on tickets #133–#138 of map #121 (closed with the lead's resolution comment).

## Things learned today that are not in the code

- The verifier found the busy books' premise wrong: EX03's agreement changed RCV-A, so EX01/EX02 were undrawable; S3 fixes
  the seed. Check a scenario's day-0 state against the API before writing a brief on it.
- `code-reviewer` / `design-reviewer` agent types have no Bash: use general-purpose with a saved diff.
- Journeys 1–2 (the audit, "Five critical journeys"): journey 1 needs a sendable counter and the receipt; journey 2 needs
  the oldest unanswered negotiation findable (the queue has no age word yet: a words ticket for Slice E) and no conditional
  option shown as runnable.
- The Home live look that shows the donut: golden books, submit + evaluate EX01 (`POST /offers {"fixture_id":"EX01_PACKAGE"}`
  then `POST /offers/{id}/evaluate`), then select the Foshan row.
