# TermsLedger web

Next.js (App Router) + TypeScript + Tailwind v4 + Recharts. The UI never computes money: it renders the
server's `*_display` strings and passes integer fen to charts for axes only (INVARIANT 13).

```
pnpm install
pnpm dev                 # mock mode by default
pnpm lint && pnpm typecheck && pnpm build
pnpm test:unit           # mocks match fixtures/golden/golden_values.json
pnpm exec playwright install chromium   # once
pnpm test:e2e            # mock project + live project (starts the API and both web builds itself)
pnpm test:e2e:mock       # mock project only, no backend needed
pnpm test:e2e:live       # live project only (needs `uv`)
```

## Modes

- `NEXT_PUBLIC_API_MODE=mock|live` (default `mock`), `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
  Mock mode is the offline fallback: answers come from `mocks/*.json` and need no backend.
- All data access goes through `lib/api.ts`. Mock answers live in `lib/mock/handlers.ts`; live answers in
  `lib/live/` (`http.ts` is the only `fetch`). Routes whose response already has the mock shape are
  passthroughs; `lib/live/trajectory.ts` and `lib/live/approvals.ts` reshape the ones that differ. Adapters
  rename fields and copy server strings; they never add, subtract or format money.
- Types are in `lib/types.ts` (hand-written; most API routes return untyped dicts, so there is no useful
  OpenAPI schema to generate from yet). Read views follow one rule: every `<name>_fen` / `<name>_bp` has a
  sibling `<name>_display` (see `Displayed<T>`).
- All labels (English and Chinese) are in `lib/dictionary.ts`.

### Running live locally

```
cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache uv run uvicorn app.main:app --port 8000
cd apps/web && NEXT_PUBLIC_API_MODE=live pnpm dev      # must be on :3000, the API's CORS allow-list
```

### Owner token (demo only)

The API gates its owner-console routes on the `X-Owner-Token` header, so every live request sends it. The
value comes from `NEXT_PUBLIC_OWNER_TOKEN` and defaults to `demo-owner-token`, the API's demo default. It is
**demo-only**: a `NEXT_PUBLIC_*` value is visible to anyone who loads the page, so a real deployment must
authenticate the owner properly and never ship a real secret this way. A 401 shows an "owner token rejected"
state instead of a blank screen. Downloads (borrower file `.html` / `.docx`) are fetched with the header and
saved from an object URL, because a plain link cannot send it.

### Live-mode notes

- The demo stepper compiles the server fixtures (`POST /offers {fixture_id}`) and passes the fixture id back
  to `/evaluate` so the owner-declared costs apply.
- Executing a funding plan changes the books, so a fresh `/router/plan` afterwards is empty. The Funding
  screen therefore shows the snapshot taken when the decision was made (`demo.funding`).
- The reworded offer (EX01B) is evaluated on the same books as EX01 before anything executes; the later
  "reworded" step only switches to it.
- `/nl` is being built elsewhere: a 404 is reported as `intent: "NL_UNAVAILABLE"` rather than thrown.

## Tests

`playwright.config.ts` has three projects. `desktop` and `phone` run against a mock-mode build on :3100.
`live` runs `demo`, `whatif`, `alerts`, `contract` and `live` specs against uvicorn (:8000, in-memory store,
recorded LLM cache, no Supabase) and a live-mode build on :3000. `demo.spec.ts` is the same file in both
modes and asserts the same golden numbers. `contract.spec.ts` calls the live adapters from Node against the
running API. Mock and live builds use separate `NEXT_DIST_DIR`s (`.next-e2e-mock`, `.next-e2e-live`).
