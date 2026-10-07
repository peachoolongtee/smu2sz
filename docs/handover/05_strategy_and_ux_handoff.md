# Handoff: FLOW after the simplification and the strategy research (8 October 2026)

For the next session's lead. Read this file, then the two wayfinder maps on GitHub, then the documents it points to. Nothing here restates a decision; the tickets hold the detail.

## 1. Where things are

- **Branch `dev`** is the integration branch. The UI simplification (wayfinder map [#26](https://github.com/peachoolongtee/smu2sz/issues/26)) merged Waves 0 to 8 into it; Wave 9 (the expressive layer, [#46](https://github.com/peachoolongtee/smu2sz/issues/46)) was in flight when this was written: see section 6 for its state. The final report of the simplification is `docs/UX_SIMPLIFICATION_REPORT.md`; its brief is `docs/UX_SIMPLIFICATION_BRIEF.md`; the previous map's report is `docs/UX_INTEGRATION_REPORT.md`.
- **The strategy research** (wayfinder map [#39](https://github.com/peachoolongtee/smu2sz/issues/39)) lives on research branches only and must stay off `dev` until the owner authorises a build: `research/strategy-repo` (01 repo primitives), `research/strategy-market` (02 market map), `research/strategy-deep` (03 deep dives), `research/strategy-spikes` (04 spikes, scripts under `services/api/scripts/research/` behind `FLOW_RESEARCH_SPIKES=1`), `research/strategy` (05 synthesis, `docs/STRATEGY_RESEARCH.md`). Section 7 says what was decided and what comes next.
- **Other research branches** worth knowing: `research/ux-truth` (the P0 truth findings), `research/upgrading-inventory` (the inventory of the teammate's `feat/upgrading` branch and the colour direction `docs/research/colour-direction-2026-10-08.md` with its swatch page).
- **Worktrees** under `.claude/worktrees/` are left in place for the lead's review; a fresh session may remove the finished ones (`git worktree remove <path>`; never the one a running agent uses).

## 2. How the owner wants the work done

- **The lead architects, specifies, reviews and merges; implementers code.** The owner said so twice on 7 October after the lead had coded three waves itself. Every wave since then: the lead writes the spec (files, outcomes, tests, rules, what not to touch) and the acceptance criteria; an `implementer` or `frontend-engineer` subagent (model `sonnet`) codes it on its own branch from `origin/dev`; the lead reviews the diff and the screenshots, runs or checks the gate, and merges with `--no-ff`. Research goes to `general-purpose` agents at the default model (with WebSearch for market work); financial figures derived by one agent are checked by a `verifier` agent from the engine's own functions before merge; an independent `code-reviewer` runs over each range before the final report.
- **Wayfinder.** Both efforts are maps of decision tickets on GitHub issues (label `wayfinder:map`; children via the sub-issues API; blocking via `repos/{owner}/{repo}/issues/{n}/dependencies/blocked_by`). A session loads the map, takes the first frontier ticket (open, unblocked, unassigned), claims it by assigning itself, resolves it, posts a resolution comment (STATUS / FILES / TESTS / NOT CHECKED / FOLLOW-UPS), closes it, and appends a one-line gist to the map's "Decisions so far". Research tickets may be resolved by the subagent; grilling tickets only by the owner, live. The maps' Notes carry the standing rules.
- **Standing rules** (`docs/HANDOVER.md` sections 3 and 5, `docs/FINANCIAL_SEMANTICS.md`): the engine is in stability mode (no alert, verdict, executor, mandate or current-books semantic change); INVARIANT 13, the browser computes no money, only server display strings (counting days is allowed); new backend fields are presentation reads; one branch per task merged into `dev` with `--no-ff`, pushed after each merge; plain one-line commit messages, no prefixes, no co-author trailers; `git checkout -- services/api/evals` after scenario, attack or evaluate runs; never edit `apps/web/mocks/*.json` by hand (re-record with `node apps/web/scripts/record-mocks.mjs --api http://localhost:<port>` against `TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port <port>`); the owner cannot waive a hard rule by approving.

## 3. The integration loop (every merge)

From the branch's worktree, with absolute paths (parallel shell calls share the cwd; `uv run --project <abs>` and `pnpm --dir <abs>`):

1. `uv run --project services/api ruff check` on touched files; `SKIP_PERF_BENCH=1 uv run --project services/api pytest -q -p no:cacheprovider services/api/tests/api services/api/tests/nl services/api/tests/alerts services/api/tests/funding` (the full suite, `pytest -o addopts= -q services/api/tests`, takes about nine minutes: 5,541 passed, 33 skipped on `dev` at `b3fe741`).
2. `pnpm typecheck`, `pnpm lint`, `pnpm test:unit` in `apps/web`.
3. Mock e2e: `E2E_PORT=<free port> E2E_TARGET=mock pnpm exec playwright test` (use a port per worktree; `reuseExistingServer` otherwise picks up another worktree's server). Live e2e: `E2E_TARGET=live E2E_API_PORT=8005 E2E_LIVE_PORT=3005 pnpm exec playwright test` (port 3000 is the owner's own dev server; never kill it).
4. Scenarios `PYTHONUTF8=1 uv run --project services/api python scripts/run_scenarios.py --inproc` (49/49), `scripts/demo_run.py` (exit 0), `cd services/api && uv run python -m app.security.attacks --report` (255, 0 harm); then `git checkout -- services/api/evals`.
5. Screenshots: `SHOTS_DIR=<abs docs/screenshots/<wave>-<date>> E2E_PORT=<port> E2E_TARGET=mock pnpm exec playwright test e2e/screenshots.spec.ts` (26 pages per viewport, `manifest.json` with page heights in screens); convert to JPEG (`sips -s format jpeg -s formatOptions 60`, phone with `--resampleWidth 412`) before committing.
6. Design detector once on the changed UI files: `~/.claude/skills/impeccable/scripts/impeccable detect --json <files>`.
7. Clean up: `rm -f apps/web/AGENTS.md apps/web/CLAUDE.md; git checkout -- apps/web/tsconfig.json` (the dev server and builds create or rewrite them).

Known flaky: the phone test "the slide-over chat fits the viewport with a long reply" failed intermittently in full runs until Wave 8 forced the branch's animation wait; Wave 9 sets `reducedMotion: "reduce"` in the Playwright config.

## 4. What the simplification decided (gists; the tickets hold the detail)

- Truth first: every one of the brief's financial contradictions was a presentation fault, fixed at its source as a presentation read, with a second agent confirming each figure (Wave 1, [#30](https://github.com/peachoolongtee/smu2sz/issues/30)).
- Deals reads in the owner's order in 1.7 desktop screens: one inbox thread per buyer, the ask in plain words, "Counter recommended" over the cost of concessions, the first breach and the worst point named apart, Option A as a business card, Option B behind "Compare", the evidence behind three closed disclosures (Waves 2 and 3).
- Business mode says distances from today, never "day N" or engine terms at level 1; Demo keeps "Day N" (Wave 4).
- Cash & funding states the current position when covered and groups options by sufficiency, never ranking an insufficient plan beside full ones (Wave 5).
- Business events replace executor sentences on the home and Activity; "Ask FLOW"; headroom and "Covered, but tight" (Wave 6).
- A 15-finding review and a cold-user walk fed Wave 7 and Wave 8; the teammate's `feat/upgrading` was inventoried and its best components ported in the owner's words; the colour direction option C (one deep brand block with a bright status pill, one filled action per page, status colour only for status, 4.5:1 and 3:1 everywhere) was adopted; then the owner asked for the branch's coloured icons, pill shapes and animations as well, and found the muted palette stale, which became Wave 9.

## 5. Working notes and gotchas

- Parallel Bash calls share the working directory; `cd` in one call moves the others. Always use absolute paths.
- `gh issue create` and `gh api -X POST` returned HTTP 500 for a stretch on 8 October; reads worked. Retry later; create issues with `gh api -X POST repos/<r>/issues --input <json>` when the CLI fails.
- Long-running implementer agents stalled twice during test loops (the harness watchdog, 600 s with no progress). A fresh implementer finishing from the worktree's uncommitted state worked; keep each agent's loop short or let it commit before the loop.
- The Agent tool's worktree isolation fails when the cwd is outside the repo; agents create their own worktrees from `origin/dev` with `git worktree add -b <branch> .claude/worktrees/<name> origin/dev`.
- The mock e2e default port 3100 is shared across worktrees; pass `E2E_PORT` per worktree.
- The browser pane may be closed by the user; take page captures with Playwright from `apps/web` (`import { chromium } from "@playwright/test"`) instead.
- The verdict mock's view fields come from `POST /offers/{id}/evaluate` through the demo stepper; `jq` multi-expression queries with `|` bind right: use separate expressions when checking fields.
- GitHub `gh issue edit --body-file` is the way to update the map body; keep a `/tmp/mapNN.md` copy and patch with Python.

## 6. Wave 9 (the expressive layer) state

See the ticket [#46](https://github.com/peachoolongtee/smu2sz/issues/46) for the spec as given to the implementer (section hues for wayfinding icons, the pill radius scale, the motion kit with reduced motion in tests, a lifted base palette with the soft backdrop, `apps/web/DESIGN.md`). When this file was written the branch `feat/expressive` was in progress; the resolution comment on #46 says whether it finished. If it did not merge: review its screenshots under `docs/screenshots/wave9-2026-10-08/` against the ticket's rules, run the loop, merge with `--no-ff`, add a Wave 9 paragraph to `docs/UX_SIMPLIFICATION_REPORT.md`, close #46 and append to map #26.

## 7. The strategy research and what comes next

Decisions (ticket [#44](https://github.com/peachoolongtee/smu2sz/issues/44)): "commercial capital allocation" is the internal principle, sold under existing categories; owner/CFO stay the user, with the Safe Deal Envelope answering the sales question on the buyer's thread in Deals; the objective is lexicographic (hard safety, mandate, posted cost plus concession value, optionality as a worded tie-break) with owner preferences as constraints; the Safe Deal Envelope as approved packages first, the cash price curve and collections marginal value proceed to a read-only MVP on one kernel (`evaluate` / `plan` / `project` / `alerts`) with four new types (CandidatePackage, Capacity, MarginalImpact, ScenarioState); the multi-deal portfolio is VALIDATE FIRST; validation by a fixture backtest plus a shadow pilot with reachable SMEs (interviews first otherwise); the deep dive's kill criteria accepted.

Next steps for the new session, in order:
1. Read `docs/STRATEGY_RESEARCH.md` on `research/strategy` (deliverables A to L, the implementation plan per winner, the dependency graph, the roadmap). If it is missing, ticket [#45](https://github.com/peachoolongtee/smu2sz/issues/45) says why; finish it from the four numbered documents.
2. Get the owner's authorisation to build the read-only MVP (the brief's section 34: spikes only until authorised), and the names of the SMEs and the month for the shadow pilot.
3. Chart the build as a new wayfinder map (feature-flagged, read-only, presentation reads; the engine stays in stability mode): the kernel's four types first, then the envelope on Deals, the cash price curve on Cash & funding and Receivables, collections marginal value on Receivables; a `verifier` agent checks every figure; the validation experiments run against the fixtures before any pilot.
4. Keep the delegation model of section 2.
