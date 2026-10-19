# Wave 8 part A: the release gate (ticket #77, map #65)

Verifier run of 9 Oct 2026 on the final integration head of `feat/ux-remediation`. No product code was changed. Every command below ran from absolute paths in a detached worktree (`.claude/worktrees/w8-gate` under the repository root). The raw summary tails are the `raw-*.txt` files in this folder.

## Result in one line

All gate commands passed with zero failures and zero retries. Two documentation notes and two scope notes are at the end (none blocks the gate).

## Head

- Gate worktree head: `6106c721` ("Ledger: F21 and F28 fixed by Wave 7"), detached from `origin/feat/ux-remediation`.
- The remote branch moved once during the run, to `0861acb` ("Ledger: the F15 row completed"). The only change between the two is one line of `docs/research/ux-remediation-ledger-2026-10-09.md` (`git diff --stat 6106c72 0861acb`: 1 file, 1 insertion, 1 deletion). The cold start (step 6) was cloned after the move, so it ran on `0861acb`; every other step ran on `6106c72`. The product code is identical.

## Machine

- `uname -a`: `Darwin Ians-MacBook-Pro.local 25.5.0 Darwin Kernel Version 25.5.0: Mon Apr 27 20:41:15 PDT 2026; root:xnu-12377.121.6~2/RELEASE_ARM64_T6041 arm64`
- node v24.11.1, pnpm 12.4.1, uv 0.12.5 (Homebrew 2026-08-14 aarch64-apple-darwin), system python3 3.13.7, the API project's own interpreter (`uv run python -V`) Python 3.12.14, sqlite3 3.51.0, Playwright `@playwright/test ^1.63.0`, Next.js 16.3.7 (Turbopack).
- Setup in the worktree: `uv sync` (0.6 s) and `pnpm install` (1.4 s), both clean.

## Commands, durations and summary lines

Durations are wall-clock seconds as measured by the shell wrapper (`EXIT` lines in each raw file). The web unit, typecheck, lint and build ran while the API suite was still running in the background, so their durations are slightly inflated by contention; nothing else overlapped.

| # | Command (all prefixed with the absolute `--project/--directory` or `--dir` forms) | Duration | Full summary line | Raw file |
|---|---|---|---|---|
| 1 | `SKIP_PERF_BENCH=1 uv run --project <w8-gate>/services/api --directory <w8-gate>/services/api pytest -o addopts= -q -p no:cacheprovider tests` | 967 s | `6398 passed, 37 skipped in 965.51s (0:16:05)` | `raw-1-api-pytest.txt` |
| 1b | `git status --short` after the suite (nothing under `services/api/evals` changed, so no `git checkout` was needed) | - | only `?? docs/research/ux-remediation-2026-10-09/gate/` | - |
| 2a | `pnpm --dir <w8-gate>/apps/web test:unit` | under 1 s | `ℹ tests 76`, `ℹ pass 76`, `ℹ fail 0`, `ℹ cancelled 0`, `ℹ skipped 0` | `raw-2-web-test-unit.txt` |
| 2b | `pnpm --dir <w8-gate>/apps/web typecheck` (`tsc --noEmit`) | 4 s | no output, exit 0 | `raw-2-web-typecheck.txt` |
| 2c | `pnpm --dir <w8-gate>/apps/web lint` (`eslint .`) | 5 s | no output, exit 0 (0 warnings, 0 errors) | `raw-2-web-lint.txt` |
| 2d | `pnpm --dir <w8-gate>/apps/web build` | 9 s | `Compiled successfully in 2.7s`, `Generating static pages using 11 workers (23/23)`, exit 0. No CSS warning (the word "warn" appears 0 times in the output). | `raw-2-web-build.txt` |
| 3a | `E2E_TARGET=mock E2E_PORT=3251 pnpm exec playwright test --retries=0` | 131 s | `33 skipped` / `135 passed (2.2m)` | `raw-3a-mock-default.txt` |
| 3b | `E2E_TARGET=mock E2E_STRATEGY=1 E2E_PORT=3252 pnpm exec playwright test --retries=0` | 135 s | `24 skipped` / `144 passed (2.2m)` | `raw-3b-mock-strategy.txt` |
| 4a | `E2E_TARGET=live E2E_LIVE_PORT=3253 E2E_API_PORT=8181 pnpm exec playwright test --retries=0` | 105 s | `12 skipped` / `69 passed (1.8m)` | `raw-4a-live-default.txt` |
| 4b | `E2E_TARGET=live E2E_STRATEGY=1 E2E_LIVE_PORT=3254 E2E_API_PORT=8182 pnpm exec playwright test --retries=0` | 158 s | `4 skipped` / `77 passed (2.6m)` | `raw-4b-live-strategy.txt` |
| 5a | `E2E_DATABASE_URL=sqlit<repo>/.claude/worktrees/w8-gate/gate.db E2E_TARGET=live E2E_LIVE_PORT=3253 E2E_API_PORT=8181 pnpm exec playwright test --retries=0` | 105 s | `12 skipped` / `69 passed (1.8m)` | `raw-5a-live-default-sqlite.txt` |
| 5b | same as 5a on a fresh `gate.db`, plus `e2e/live.spec.ts --grep-invert 'Activity: each row says what changed'` | 37 s | `23 passed (37.0s)` | `raw-5b-live-spec-no-final-reset.txt` |
| 5c | same env on a fresh `gate-cure.db`, `e2e/live.spec.ts --grep 'on day 34 the cure needs the owner'` | 8 s | `1 passed (8.0s)` | `raw-5c-live-day34-cure-only.txt` |
| 5d | same env on a fresh `gate-demo.db`, `e2e/demo.spec.ts --grep 'the six scenes run with Next'` | 9 s | `1 passed (9.1s)` | `raw-5d-live-demo-six-scenes-only.txt` |

Skips: the 33 mock default skips and the 12 live default skips are the strategy-flag tests (they need `E2E_STRATEGY=1`); with the flag the skips drop to 24 (mock) and 4 (live), the remainder being mock-only or live-only tests that skip in the other mode by design. 0 tests failed, 0 flaked, retries were 0 in every run.

Demo timing JSON (the Demo story's rapid-click and guarded runs), all in `demo-timing.txt`:

```
3a-mock-default: DEMO_TIMING {"project":"desktop","steps":11,"rapid":{"clicks":30,"ms":1972,"ledgerEntries":5,"progress":[1,2,3,4,5,6,7,8,9,10,11]},"guarded":{"ms":1079,"ledgerEntries":5}}
3b-mock-strategy: DEMO_TIMING {"project":"desktop","steps":11,"rapid":{"clicks":30,"ms":1959,"ledgerEntries":5,"progress":[1,2,3,4,5,6,7,8,9,10,11]},"guarded":{"ms":1092,"ledgerEntries":5}}
4a-live-default: DEMO_TIMING {"project":"live","steps":11,"rapid":{"clicks":30,"ms":1846,"ledgerEntries":8,"progress":[1,2,3,4,5,6,7,8,9,10,11]},"guarded":{"ms":1879,"ledgerEntries":8}}
4b-live-strategy: DEMO_TIMING {"project":"live","steps":11,"rapid":{"clicks":30,"ms":1903,"ledgerEntries":8,"progress":[1,2,3,4,5,6,7,8,9,10,11]},"guarded":{"ms":2679,"ledgerEntries":8}}
5a-live-default-sqlite: DEMO_TIMING {"project":"live","steps":11,"rapid":{"clicks":30,"ms":1851,"ledgerEntries":8,"progress":[1,2,3,4,5,6,7,8,9,10,11]},"guarded":{"ms":2042,"ledgerEntries":8}}
```

(Reading: 30 rapid clicks on Start and Next end at step 11 in about 1.9 s in every run, with the ledger entries of a single walk: 5 in mock, 8 in live.)

### What the live project does and does not include

`apps/web/playwright.config.ts` gives the live project only `demo|whatif|alerts|contract|live|chat|strategy|slow|lang`. The responsive and phone projects, axe (`a11y.spec.ts`), the record spec and the trust spec are matched only by the mock `desktop` and `phone` projects. They did run, in 3a and 3b: in 3a `a11y.spec` 7 tests on desktop and 7 on phone, `responsive.spec` 12 and 12, `record.spec` 12 on desktop, `trust.spec` 5 on desktop, all passed (record.spec skips itself in live by design: "mock-mode spec ... the live equivalent is in live.spec.ts"). Demo in live: 14 tests in 4a, slow.spec 6, lang.spec 1, chat.spec 15, all passed.

## Step 5: the real configured database (SQLite file)

The switch is `E2E_DATABASE_URL` in `apps/web/playwright.config.ts` (merged in ddd77ea): the API Playwright starts gets `DATABASE_URL=<that value>` instead of `memory`.

- 5a: the whole live default suite on `gate.db` passed (69 passed, 12 skipped). The file ended with the seed state only (rows files `rows-after-5a-full-suite.txt`): operations 0, decision_facts 0, approvals 0, commitments 0, obligations 0, offers 0, pilot_journal 0; seed tables facilities 8, counterparties 7, organizations 1, mandates 1, states 1. 17 tables exist. This is expected: the specs reset the books.
- 5b (as asked, the live spec minus the test that resets at the end): the test that resets the session at the end is `Activity: each row says what changed, why it matters (Now) and what remains; ...` (`live.spec.ts:671`). Running `live.spec.ts` without it passed (23 passed) but the file still holds 0 operations, 0 decision_facts, 0 approvals, 0 commitments (`rows-after-5b-live-spec-minus-final-test.txt`). Reason, read from the spec: 14 of the 24 tests in `live.spec.ts` end with `/demo/reset` (every test that drives the books through a walk), and the Cash test, which becomes the last test to run once the Activity test is excluded, resets at its start and writes nothing. So excluding only the last test leaves nothing on disk, and no `-g` selection on `live.spec.ts` alone was found that leaves written rows.
- 5c: the day-34 cure test alone (`live.spec.ts:172`, which also ends with a reset) left 0 rows in `gate-cure.db` (`rows-after-5c-day34-cure-test-only.txt`). Recorded as a negative result.
- 5d (the workable proof): `demo.spec.ts` "the six scenes run with Next" (no final reset) against a fresh `gate-demo.db`. After Playwright stopped its API, the file on disk holds: operations 8, decision_facts 3, approvals 1, commitments 1, obligations 3, offers 1, evaluation_runs 0, security_events 0 (`rows-after-5d-demo-six-scenes-only.txt`). The 8 operations in sequence are ACCEPT_OFFER, DRAW_FACILITY, ADVANCE_CLOCK, RECEIVE_PAYMENT, ADVANCE_CLOCK, SUBMIT_INVOICE_FOR_FINANCING, SUBMIT_INVOICE_FOR_FINANCING, ADVANCE_CLOCK (`rows-after-5d-operations-kinds.txt`). So writes persist on the SQLite file, and the 8 matches the `ledgerEntries: 8` the demo timing reports.

The `.db` files are git-ignored and are not in the commit.

## Step 6: the documented cold start from a clean clone

- `git clone --branch feat/ux-remediation --single-branch https://github.com/peachoolongtee/smu2sz.git <scratchpad>/map65/w8-clone-final` succeeded with no credentials. Head `0861acb`.
- Root README commands as now written, with the other-ports variables the README documents: `cd services/api && uv sync` (ok), `cd apps/web && pnpm install` (ok, 773 ms), then
  - `cd services/api && CORS_ORIGINS=http://localhost:3255 uv run uvicorn app.main:app --reload --port 8183`
  - `cd apps/web && NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8183 pnpm dev -p 3255`
  - No `.env`, no `DATABASE_URL` (the README default: SQLite file `services/api/termsledger.db`, which exists afterwards).
- HTTP status of each page (curl against `:3255`): `/` 200, `/deals` 200, `/cash` 200, `/receivables` 200, `/activity` 200, `/approvals` 200, `/decisions/deal:OFF-x` 200. API `GET /health` 200 (`"ok":true`, `llm_mode":"cache"`), `GET /state` with `Origin: http://localhost:3255` and `X-Owner-Token: demo-owner-token` 200.
- The unknown decision id: curl only sees the shell (the page renders client-side). A headless Chromium probe (`cold-start/notfound-probe.cjs`, with the owner token placed in `sessionStorage` exactly as the e2e fixture does) shows status 200 and the text "That record is not here / No decision with this address is on the books. It may have been cleared by a reset. / Back to Home" (`cold-start/notfound-signed-in.txt`). Signed out, the same page shows "Sign in to see your books" with an "Owner sign-in" action (`cold-start/notfound.txt`). The only browser console errors were the API's 401 (signed out) and 404 (unknown id), which are the expected answers.
- Dev server output, complete (`cold-start/web.log`): `Next.js 16.3.7 (Turbopack)`, `Ready in 248ms`, `Running next.config.mjs took 8ms`, `Generated AGENTS.md and CLAUDE.md for AI agents. Set agentRules: false in next.config to disable.`, then only `GET ... 200` lines. 0 matches for "warn" in either the web log or the API log (`cold-start/api.log`). No CSS warning.
- `git status --short` in the clone after the run: empty, so the two generated agent files are git-ignored as the README now says.
- README step 1 (extra): the per-task evidence chains verify, `49 VALID:` (`cold-start/verify-evidence.txt`).
- Both servers were stopped by port; no listener remains on 8183 or 3255.

## The mission flows and the test that covers each

Paths are under `apps/web/e2e/`. "mock" = the mock projects (3a/3b), "live" = the live project (4a/4b/5a). All tests listed passed in the run named.

| Flow | Spec : line, test name | Run |
|---|---|---|
| Approval | `trust.spec.ts:14` "an agreement approval shows the buyer, the terms and the amount above the buttons" | mock |
| Approval | `trust.spec.ts:38` "when the server cannot present the terms, Approve is disabled, the reason is shown and Decline stays"; `trust.spec.ts:56` "an approval the executor refuses ends as 'could not run', with no buttons and no money moved" | mock |
| Approval | `record.spec.ts:155` "the approval card shows what was quoted, and once decided what happened and how it differs"; `record.spec.ts:186` "a refused approval ends in the record's words: it could not run, no money moved" | mock |
| Approval | `live.spec.ts:44` "the borrower file downloads as HTML and Word, and the owner approves the one pending application"; `live.spec.ts:445` "approving after the mandate has expired is refused: the card ends as 'could not run', with no buttons and no money moved"; `live.spec.ts:483` "a buyer's agreement that expired before the owner looked cannot be approved: the card says why and keeps Decline" | live |
| Counter | `record.spec.ts:59` "the send names its option, says the reply is simulated, and carries what was shown; Option B has its own send"; `record.spec.ts:77` "COUNTER_CHANGED, the verdict was replaced: ..."; `record.spec.ts:98` "COUNTER_CHANGED, the books moved: the old proposal is withdrawn and Check again gets a current one" | mock |
| Counter | `live.spec.ts:521` "Deals: Send carries what was shown, and the record's state follows: Agreed, then Fulfilled once the receipt came"; `live.spec.ts:576` "Deals: if the books moved after the proposal was shown, Send is refused, nothing is sent, and Check again gets a current one"; `live.spec.ts:632` "Deals: the workspace is the API's, in its order, and ?buyer= selects the buyer's deal" (Counter recommended) | live |
| Funding | `live.spec.ts:172` "on day 34 the cure needs the owner: the alert says so, the click queues it, approval runs it, the cash lands on day 37" (the day-34 cure); `live.spec.ts:82` "the day-0 plan: 'go ahead' brings cash now and leaves the advance in transit until its landing day"; `live.spec.ts:653` "Cash: the comparison arrives grouped and ordered by the API, ..." | live |
| Receipt | `live.spec.ts:403` "day 34 after a half receipt: the early-payment window for the rest is said as ended, not 'by today'"; `live.spec.ts:421` "day 34 after a half receipt: Chase payment opens the API's handoff, its balance is the API's own, and the receipt row names its four facts"; `live.spec.ts:521` (Fulfilled once the receipt came) | live |
| Receipt | `receivables.spec.ts:126` "day 34 after the half receipt: the chase dialog's balance is the one the page shows, and the receipt row names its four facts"; `trust.spec.ts:90` "a part-paid promise: Home says it once in the server's sentence, Receivables names the four facts and the window" | mock |
| Late-payment cure | `demo.spec.ts:43` "the six scenes run with Next: the buyer asks, FLOW decides, the agreement acts, reality diverges, the owner stays in control, the proof" | mock and live |
| Late-payment cure | `live.spec.ts:172` (day-34 cure to SETTLED); `live.spec.ts:382` "day 34 with no receipt: the Home says below the reserve today, the promise is history, and no page says 'by today'"; `live.spec.ts:601` "Home: a cure that cannot restore the reserve leaves a remaining task with the routes it names, ..."; `live.spec.ts:671` "Activity: ..." (approved cure, record, chain check) | live |
| Late-payment cure | `record.spec.ts:114` / `:125` day 34 with and without the receipt; `record.spec.ts:202` "Home: after the cure is approved, 'Waiting on' lists what is open and links to its record; ..." | mock |
| Ask FLOW contextual queries | `chat.spec.ts:303` "the chat button says Ask FLOW, and a Business page offers only the questions it can answer"; `chat.spec.ts:357` "the Deals question about the deal explains the verdict the page evaluated, and the panel says what it is discussing"; `chat.spec.ts:398` "Home's 'What changed today?' is a read of the books, not a list of what the agent can do"; `chat.spec.ts:333` "Business chat is the owner's alone: no role switch, no Tier 1 hint, no fixture or approve-it chips"; `chat.spec.ts:411` "Business chat says one outcome in the owner's words: ..."; `chat.spec.ts:432` "a refresh keeps the draft and the conversation, and a pending plan points to the Approvals page" | mock and live |
| Ask FLOW in Chinese | `chat.spec.ts:251` "the Chinese UI offers Chinese prompts and gets a Chinese answer" | mock and live |
| Language of the record | `lang.spec.ts:49` "in Chinese the approvals queue and the decision record read in Chinese with the same amounts as in English" (this spec covers the Approvals queue and the Decision record, not Ask FLOW; the Ask FLOW Chinese check is `chat.spec.ts:251`) | mock and live |

Other coverage in the same runs: axe on every page (`a11y.spec.ts`, desktop and phone, mock), responsive and phone widths (`responsive.spec.ts`, mock), the slow path (`slow.spec.ts`, live, 6 tests), and the Demo story's rapid-click run, Show/Replay/Reset (`demo.spec.ts:298`, `:346`, `:275`, live and mock).

## Failures

None. No test failed, none was retried (`--retries=0` throughout), and no test was re-run to make it pass. The only reruns were intentional different selections in step 5 (5b, 5c, 5d), which are listed above with their results, including the two that showed no persisted rows.

## Notes (not failures)

1. Documentation drift: the root README test block says `pnpm test:e2e:mock ... 133 passed, 33 skipped` and `pnpm test:e2e:live ... 67 passed, 12 skipped`. This head gives 135 passed, 33 skipped (mock) and 69 passed, 12 skipped (live). The README's sentence that on a SQLite file the spec leaves the seed state matches what 5a and 5b show.
2. Scope: the mission list says the live run includes the responsive, phone, axe and record specs. By the Playwright config those run in the mock projects only; they were run and passed there (3a, 3b). The live project covers the Demo story, slow, lang, chat, alerts, contract, whatif, live and strategy specs.
3. `pnpm test:unit` prints a Node `MODULE_TYPELESS_PACKAGE_JSON` warning about `lib/demo-store.ts` (performance note, tests pass).
4. The remote branch gained one docs-only commit during the run (see Head).

## The merged `dev` head (8041d1f, 10 Oct)

Run by the lead from the main checkout after the owner merged `feat/ux-remediation` into `dev`, all with `--retries=0`:

| Check | Result |
| --- | --- |
| Whole API suite on 5bb667b (the last API change before the merge; only web and docs commits followed) | 6413 passed, 37 skipped (16 min) |
| Web unit, typecheck, lint | 76 passed; clean; clean |
| Mock e2e, default / strategy build | 140 passed, 36 skipped / 149 passed, 27 skipped |
| Live e2e, default / strategy build | 71 passed, 12 skipped / 79 passed, 4 skipped |

A first live run on this head, made while the machine's load average was above 8, failed the two slow-path tests of `e2e/slow.spec.ts` (the hung write and the hung chat reply, each taking about 17 minutes) and the strategy build timed out waiting for `next build`; a re-run with the load at 5 to 6 passed every test. The failures are recorded here as a load effect, not a code finding; the same spec passed in the Wave 8 gate on 6106c72 and in the final web branch's own run.
