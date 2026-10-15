# Branching and integration rules

These rules apply to everyone, people and agents. They are the owner's rules of 15 Oct 2026.

**Why they exist.** Dylan's redesign was built on a feature branch (`feat/capex-buy-side`), not on dev. It stayed open while dev moved
(round three, the security fixes). Nobody ran the full browser suite until the integration step. When it finally did run, 53 specs
failed in files that no one had checked. The busy-books branch made the demo's busy load 7 times slower, and no test noticed. Both
problems were cheap to catch early and expensive to catch late.

## Rules

1. **Branch from the latest `origin/dev`.** Never branch from another feature branch. If your work needs someone else's unmerged
   work, ask the lead to land it first.
2. **Bring dev into your branch at least once a day,** and again before you hand in. Resolve the conflicts yourself: you know your
   change best.
3. **One task per branch. Keep it small and short-lived.** A redesign lands page by page, not as one change to every page.
4. **Before handing in, run the full mock browser suite, not just the files you think you touched.** From `apps/web`:
   - `E2E_TARGET=mock E2E_PORT=<free port> pnpm exec playwright test --workers=6` (about 11 minutes);
   - then `pnpm typecheck`, `pnpm lint` and `pnpm test:unit`;
   - for server changes, the relevant `tests/` files (see `README.md`).

   Report the exact counts. Never use ports 3000 or 8000.
5. **A failing spec is either a defect or a stale description.**
   - If it is a defect, fix the code.
   - If it is stale, amend the spec to the new design and say why in the commit.
   - Never delete a spec whose subject still exists.
   - Never skip a spec or extend its timeout to make it pass.
6. **Mocks come only from the recorder** (`apps/web/scripts/record-mocks.mjs`). Never edit them by hand. Two recordings in a row must be
   identical; the recorder normalises the random ids.
7. **Watch the cost of demo data.** A change to a scenario or seed reports the time `POST /demo/reset?scenario=<name>` takes, before and
   after. The web gives up on a request after 20 s.
8. **Only the lead merges into dev, with `--no-ff`,** after the integration gate:
   - the full API suite;
   - the full mock suite on desktop and phone;
   - the live suite;
   - unit tests, typecheck and lint.
9. **The GitHub checks** (`.github/workflows/checks.yml`):
   - on every push: typecheck, lint and unit tests on the web;
   - on dev, `int/*`, `ci/*` and pull requests into dev: the API suite and the mock browser suite (they are heavy and spend Actions
     minutes). Run them on your own branch from the Actions tab (Run workflow) before handing in a large change.

   A red check is fixed before anything else lands on that branch.

Everything else (no `git stash`, never read `.env`, never connect to a real database, never kill processes by image name, never route
around a refused command) is in `docs/HANDOVER.md`.
