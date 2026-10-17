# FLOW (TermsLedger v2)

Source code: https://github.com/peachoolongtee/smu2sz · FinTechathon 2026, International track, Topic E: SME Finance Copilot.

Contents: [1. What FLOW is](#1-what-flow-is) · [2. Run it locally](#2-run-it-locally-mock-mode-and-live-mode) · [3. Deploy](#3-deploy) · [4. Run the tests](#4-run-the-tests) · [5. Verify the evidence and evaluate](#5-verify-the-evidence-and-evaluate) · [Features and flags](#features-and-flags) · [Credentials](#credentials) · [Map](#map) · [Data, compliance and licence](#data-compliance-and-licence)

## 1. What FLOW is

FLOW is an agent owned by a small supplier that controls both of its debt books under an owner-signed mandate. **Terms Guard** covers the credit the supplier gives buyers through payment terms. **Debt Desk** covers the credit it takes from lenders to survive those terms. The language model only interprets text; deterministic code decides and executes. A buyer's offer becomes typed obligations, then a dated cash and debt trajectory, then a funding plan, then covenant and mandate checks, then a verdict, then typed operations in a hash-chained log. The agent may accept a buyer's offer on its own only when it can prove it read every figure and request in it (ADR-0005); everything else waits for the owner. It does not stop at the decision: on current books and a simulated clock it watches for a late receipt, tells the owner first, and proposes a cure inside the mandate with its cost. Free text executes only as a closed affirmative command, and a plan is proposed first and run only on the owner's "go ahead", as exactly the operations shown. A cure that costs more a year than the mandate's ceiling is queued, and runs only when the owner approves it as a second step (in the demo: go ahead, approve, and the cash lands on day 37).

All data is synthetic (`fixtures/`). This is a simulation: the agent is decision support under the owner's own limits, not a lender, broker or adviser, and it executes no real payment; every facility, the buyer and the bank feed are simulated. It screens the entered obligations only, and it makes no claim of bank-covenant compliance. Nothing below needs an API key or the network once dependencies are installed: the default `LLM_MODE=cache` replays recorded model outputs and falls back to a deterministic rules grammar.

The stack: a FastAPI service (`services/api`, Python 3.12) with SQLite, in-memory or PostgreSQL storage, and a Next.js 16 web app (`apps/web`, TypeScript) that runs on recorded mocks or against the API.

## For judges

One command runs everything offline, free and deterministic (recorded model readings, in-memory books, no network, no key) and writes a report you can read in a browser or an editor:

```bash
uv run --project services/api python scripts/judge_eval.py     # 2 to 4 minutes; writes services/api/evals/judge/judge-report.md and .json
```

It runs the 49 scripted conversations, the 259-attack catalogue (126 through the API, 133 through the chat), the demo walk, and a hash-chain check of the walk's log with a tampered copy that must fail. The report opens with one headline line, then a table per task area and per attack class, then every task and attack with its prompt, expected and actual outcome. The exit status is non-zero on any failure. Eight questions to ask FLOW live, with the exact input and the real answer: [`docs/deliverables/JUDGING_QUESTIONS.md`](docs/deliverables/JUDGING_QUESTIONS.md).

## 2. Run it locally (mock mode and live mode)

Requirements: Python 3.12 with [`uv`](https://docs.astral.sh/uv/); Node 22 or newer with `pnpm` for the web app. Open a terminal at the repository root and clone first:

```bash
git clone https://github.com/peachoolongtee/smu2sz.git && cd smu2sz
```

One command, the same in PowerShell, cmd, macOS and Linux, from the repository root (install the web packages once first):

```powershell
cd apps/web; pnpm install; cd ../..     # once
pnpm demo                               # API on :8000 + UI on :3000 against it; open http://localhost:3000
pnpm demo:blank                         # the same, opening on a new business with no books (the setup wizard)
pnpm demo:mock                          # UI alone on the recorded mocks: no API, no Python
pnpm demo:keep                          # like pnpm demo, but what you upload, confirm or book survives a restart
pnpm demo:keep --fresh                  # the same, starting again from new demo books
pnpm demo --web-port 3141 --api-port 8041   # other ports, if 3000 or 8000 is taken
```

`--keep` (also with `--blank`) keeps the books in a local SQLite file, `.demo-data/flow-demo.db` (gitignored), instead of in memory: the first start seeds the demo books into it, later starts open what it holds. `--fresh` deletes the file first. Everything else about the API's environment is the same.

The launcher (`scripts/demo.mjs`, Node only) starts the API with in-memory books (`DATABASE_URL=memory`), the repo-root `.env` ignored (`TERMSLEDGER_NO_DOTENV=1`), the demo credentials, cached LLM outputs and every feature flag, and tells it to allow the web port it uses. It checks both ports first, waits for the API before starting the web app, prints the address to open, and stops both on Ctrl+C. The first run installs the API's Python packages (a minute or two).

**"localhost refused to connect"** means nothing is listening on that port, or the web app came up on another port the API does not allow: run `pnpm demo` and open the address it prints; if it says a port is taken, pass `--web-port` / `--api-port` as it suggests.

Or by hand, two terminals (PowerShell; in bash write `NAME=value` before the command instead of the `$env:` lines). Always set `TERMSLEDGER_NO_DOTENV=1` and `DATABASE_URL=memory`, or the API reads the repo-root `.env`:

```powershell
# terminal 1, from services/api
$env:TERMSLEDGER_NO_DOTENV="1"; $env:DATABASE_URL="memory"; $env:DEMO_MODE="1"; $env:LLM_MODE="cache"; $env:CORS_ORIGINS="http://localhost:3000"; $env:FEATURE_ENVELOPE="1"; $env:FEATURE_PRICE_CURVE="1"; $env:FEATURE_COLLECTIONS_WORTH="1"; $env:FEATURE_EXPOSURE="1"
uv run uvicorn app.main:app --port 8000
# terminal 2, from apps/web
$env:NEXT_PUBLIC_API_URL="http://localhost:8000"; pnpm dev:live        # or `pnpm dev:mock` for the recorded mocks alone
```

Switch to **Demo** in the header, click **Start demo** and sign in as the owner when asked (the local demo token is `demo-owner-token`; `NEXT_PUBLIC_DEMO=1` prefills it). The chat panel opens from the header on every page, and the owner home at `/` shows the day, the agent's opener and what is waiting.

**The whole path without the UI** (17 steps, in process, exit 0: the deal, the agreed early payment, the late residual on day 34, the cure that takes two steps, go ahead then approve, landing on day 37, the repaid credit line, an attack through chat):

```bash
DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py
```

Without `DEMO_MODE=1` it stops with a message saying so. Its output from this commit is in `docs/deliverables/evidence/demo_run_output.txt`.

- **Where the data lives.** Without `DATABASE_URL` the API uses the SQLite file `termsledger.db` in the directory it was started from (`services/api/termsledger.db`; the `*.db` pattern is git-ignored). The app creates the file and its tables itself the first time it opens the store (the first request, not at start); there is no Alembic step for local use. `DATABASE_URL=memory` keeps everything in the process and writes no file. For another file use the absolute form `DATABASE_URL=sqlite:////absolute/path/to/file.db` (four slashes: the scheme's three plus the leading `/` of the path).
- **A repo-root `.env`.** The API reads `.env` at the repository root if one exists, and fills in only what the shell has not set. Set `TERMSLEDGER_NO_DOTENV=1` to skip it (the tests and the e2e config do).
- **Other ports.** `pnpm demo --web-port <n> --api-port <n>` handles this for you. The API allows the web origin `http://localhost:3000` by default. For any other web port, start the API with `CORS_ORIGINS=<web origin>` (without it the browser's preflight is refused and every request fails) and the web app with `NEXT_PUBLIC_API_URL=<API origin>`, for example `TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 CORS_ORIGINS=http://localhost:3141 uv run uvicorn app.main:app --port 8041` and `NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8041 pnpm dev -p 3141`.
- **Files `pnpm dev` writes.** Next.js 16 writes `apps/web/AGENTS.md` and `apps/web/CLAUDE.md` when the dev server starts; both are git-ignored.
- More on the web app, the live mode and the e2e switches is in `apps/web/README.md`.

## 3. Deploy

`infra/docker-compose.yml` runs three services: `postgres` (16), `api` (built from `infra/api.Dockerfile`) and `web` (built from `infra/web.Dockerfile`). Secrets come from `infra/.env`, which is never committed; `infra/.env.example` lists them.

**What to set in `infra/.env`** (copy the example first: `cp infra/.env.example infra/.env`):

| Variable | Value |
| --- | --- |
| `POSTGRES_PASSWORD` | a random password |
| `OWNER_TOKEN` | a random secret, for example `openssl rand -hex 32` (the owner's header `X-Owner-Token`) |
| `AGENT_KEY` | a different random secret (`X-Agent-Key`) |
| `BANK_FEED_KEY` | a third one (`X-Bank-Feed-Key`, the simulated bank's receipt feed) |
| `CORS_ORIGINS` | the web origin the browser uses, for example `https://flow.example.com` |
| `LLM_MODE` | `cache` (default) replays recorded outputs; `live` also needs `ANTHROPIC_API_KEY` or `DEEPSEEK_API_KEY` |

**`DEMO_MODE=0` in production.** The compose file hard-codes `DEMO_MODE: "0"`. With it off, the published demo credentials (`demo-owner-token` and the rest) are rejected, the owner and agent routes answer 503 until `OWNER_TOKEN` and `AGENT_KEY` are set, and the demo books are never seeded. The API binds to `127.0.0.1:8000` so that it sits behind a TLS reverse proxy; do not publish it on `0.0.0.0`.

**Database: the bundled Postgres, or Supabase.**

1. Create the schema with Alembic **before the API's first start**. The migrations are in `services/api/migrations/versions/` (`0001` to **`0008`**, the head). `0002` enables row-level security on every table and `0003` makes `operations` and `used_nonces` append-only in the database itself; a database the app created for itself (`metadata.create_all`) has neither.

   ```bash
   # bundled Postgres
   docker compose -f infra/docker-compose.yml up -d postgres
   docker compose -f infra/docker-compose.yml run --rm api uv run --no-dev alembic upgrade head

   # or any Postgres / Supabase, from a checkout: use the session-pooler (IPv4) connection string
   cd services/api && uv sync
   DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME' uv run alembic upgrade head
   alembic current          # expect: 0008 (head)
   ```

   For Supabase, take the connection string from the project's database settings and write it with the `postgresql+psycopg://` scheme (when only `SUPABASE_DB_URL` is set, the API rewrites `postgres://` to that scheme itself). In the compose file replace the `api` service's `DATABASE_URL` and drop the `postgres` service.
2. Start the stack: `docker compose -f infra/docker-compose.yml up -d --build`. The web app is on :3000, the API on 127.0.0.1:8000, health at `/health`.

**Not yet a one-command production deployment (open finding SEC-06, `docs/SECURITY_SELF_ASSESSMENT.md`).** Reading the files: with `DEMO_MODE=0` the API also needs `OWNER_PUBLIC_KEY_HEX` (the owner's Ed25519 public key, 64 hex characters) and a store that already holds books and an owner-signed mandate, because the demo fixture is never seeded outside `DEMO_MODE`; the compose file does not pass the key, and no provisioning command exists yet, so the API refuses to start rather than run on demo values. Counterparty channel keys come from `COUNTERPARTY_KEYS` (`BUYER-1=key,BUYER-2=key`); with none set no buyer can authenticate. The web image bakes `NEXT_PUBLIC_API_URL=http://localhost:8000` at build time and compose passes no build argument, so a web app served from a domain needs `build.args` added. The mandate in `fixtures/` is signed with a published key labelled DEMO ONLY.

**What we ran.** `docker` is not installed on the machine this section was checked on, so the compose file, both Dockerfiles and the compose commands above were read, not run. What was run: `alembic upgrade head` from `services/api` on a fresh SQLite file (it applied `0001` through `0008` and `alembic current` printed `0008 (head)`); the API started on that file with `DEMO_MODE=1` (`/state` answered 200 with the demo owner token and 401 without it); the API started with `DEMO_MODE=0` and made-up `OWNER_TOKEN` and `AGENT_KEY` (it answered `/health` and then failed closed on the first owner route with the `OWNER_PUBLIC_KEY_HEX` message above). No PostgreSQL or Supabase database was used.

**For an evaluation stack on a private network** (synthetic data, published demo credentials, never on the internet): run the two commands of section 2 on the host, or against a migrated database with `DATABASE_URL` set as in step 1 and `DEMO_MODE=1`.

## 4. Run the tests

Run each block from the directory named. The full catalogue by area, with file globs, counts and what each suite proves, is in [`docs/deliverables/TEST_CASES.md`](docs/deliverables/TEST_CASES.md). Last full gate, on `dev` at `0f92d433` (16 Oct 2026): **API 8,556 passed with 1 known failure** (#161, a hash that differs by machine), **Playwright mock 435/435, live 141/141, web unit 163**, `tsc` and `eslint` clean.

```bash
# API: 8,598 tests collected (about 25 minutes in full; Windows gate had SKIP_PERF_BENCH=1)
cd services/api && SKIP_PERF_BENCH=1 uv run pytest
cd services/api && uv run pytest tests/mandate tests/verifier        # one area, seconds to minutes

# web: lint, types, unit tests (163)
cd apps/web && pnpm install && pnpm lint && pnpm typecheck && pnpm test:unit

# end to end (Playwright)
cd apps/web && pnpm exec playwright install chromium   # once
cd apps/web && pnpm test:e2e:mock                    # no backend: 496 listed, 435 run in the gate
cd apps/web && pnpm test:e2e:live                    # needs uv; starts its own API (in-memory) and web build: 191 listed, 141 run in the gate
```

`pytest` needs no environment variables: `tests/conftest.py` sets `TERMSLEDGER_NO_DOTENV=1` and `DEMO_MODE=1` itself. Some listed Playwright tests skip themselves; the strategy specs run only with `E2E_STRATEGY=1`. The live project starts an API on :8000 and a web build on :3000 itself, so those ports must be free; `E2E_API_PORT`, `E2E_LIVE_PORT` and `E2E_PORT` (mock, default 3100) move them. Two switches change the live API: `E2E_DATABASE_URL=sqlite:////absolute/path/e2e.db` makes the API that Playwright starts use that file instead of `memory`, and `E2E_REUSE_API=1` starts no API and runs against one already listening on `E2E_API_PORT` (start it yourself with `CORS_ORIGINS` set to the live web origin; then `E2E_DATABASE_URL` is ignored). `DEMO_MODE=1` for the live API is set by the Playwright config. Details in `apps/web/README.md`.

Known failures and flakes: #161 (one API test whose hash differs by machine) and #157 (a few Playwright specs, for example the two write-conflict retries in `live.spec.ts`, which can fail on this tree). Both are described in `TEST_CASES.md`.

## 5. Verify the evidence and evaluate

**Verify the submitted evidence** (standard library only, no install). Each file is one scripted task's hash chain; the script recomputes every `entry_hash = sha256(prev_hash + payload_json + result_json)`. Expect 49 lines starting `VALID`, one per task (the concatenated `evidence.jsonl` holds 49 separate chains, so verify the per-task files):

```bash
for f in services/api/evals/e2e/latest/evidence/*.jsonl; do python3 scripts/verify_evidence.py "$f"; done
```

A fresh evidence pack from this commit (the demo run, the 49 tasks, the full-walk operations log with its verification, four security refusals) is in [`docs/deliverables/evidence/`](docs/deliverables/evidence/README.md); the narrative is `docs/deliverables/execution_evidence.md`.

**Evaluate.**

```bash
python3 scripts/run_scenarios.py --inproc                         # 49 scripted /nl tasks + evidence → services/api/evals/e2e/latest/ (add --out DIR to keep the committed run)
cd services/api && uv run python -m app.security.attacks --report # 259 attacks (126 API + 133 chat, including the NL-CS consent attacks, each buyer attack with and without the buyer's key, and four on contract ingestion), 0 with harm; rewrites services/api/evals/security/latest_report.*
DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/evaluate_contracts.py   # held-out contract readings → services/api/evals/contracts_heldout_report.md (the set is pending, so the report says so)
DEMO_MODE=1 uv run --project services/api python scripts/evaluate.py          # full offline evaluation (about 5 min) → services/api/evals/latest_report.md
uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout3   # the independent held-out set
PYTHONUTF8=1 uv run --project services/api python scripts/certify_language_boundary.py --backend cache   # 231-item language-boundary certification; also --backend fake; WRONG_MATERIAL 0 in both. --backend live is pending an API key
cd services/api && SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/concurrency   # two-process invariants on SQLite; the PostgreSQL cases run when TERMSLEDGER_TEST_DATABASE_URL is set (pending a database URL)
```

What we claim about the compiler, and what we don't, is in `services/api/evals/accuracy_summary.md`. In short: since ADR-0005 there are 0 wrong autonomous accepts on the held-out sets and both compiler paths, and text the compiler cannot fully read fails closed and goes to the owner. The figures behind that, unchanged: on the only set nobody had tuned for, the first run (before ADR-0005) accepted 8 offers without the owner and 4 were wrong, and about 1 message in 3 is still decided differently from the labels (it goes to the owner, a counter or a clarification).

**Rebuild the submission documents.**

```bash
uv run --project services/api python scripts/build_deliverables.py --refresh-evidence   # → docs/deliverables/out/*.docx
```

## Features and flags

Flags are environment variables read by `services/api/app/config.py` (`1` on, `0` off). A disabled feature returns `FEATURE_DISABLED` and never breaks the core.

| Feature | What it does | Flag | Default |
| --- | --- | --- | --- |
| Terms Guard | Compile a buyer's offer (zh + en, message and attachments) into typed obligations with exact spans; verdict with formulas; counters priced from the marginal cost of funds; break-even rule; the early-payment rule (break-even for the actual days early, the cash must be needed, cheaper than the router's plan; ADR-0007); ADR-0005 autonomy proof | core (`FEATURE_TERMS_GUARD`) | on |
| Debt Desk | Grid-search funding router over committed facilities, marginal cost of funds, break-even discount | core (`FEATURE_DEBT_DESK`) | on |
| Buyer negotiation | Deterministic buyer kernel with a hidden reservation; bounded rounds; NO DEAL | core (`FEATURE_BUYER_NEGOTIATION`) | on |
| Natural-language harness and chat | `POST /nl`: 21 intents (including financing comparison, alerts, reconciliation, covenant ratios, capex, the borrower file, a read-only CHANGES ("what changed?") and a read-only RECORD_FACT that says chat cannot record a stated bill or figure), plans, clarification, correction, nearest-capability fallback; `POST /nl/opener` (the agent speaks first); `/chat` page and slide-over panel | core | on |
| Permission tiers and executor | Tier 1 / 2 / 3, signed mandate, nonce, idempotency, circuit breaker, hash-chained log, `GET /evidence` | core | on |
| Security scenes | FastCapital and other hostile-message scenes in the demo | `FEATURE_SECURITY_SCENES` | on |
| What-if sandbox | Read-only hypothetical verdicts (terms slider, discounts) | core | on |
| Capex | NPV, payback and financing-structure comparison; evaluating writes nothing, and `POST /capex/apply` is the owner's explicit step that queues the Tier-2 application | `FEATURE_CAPEX` | on |
| Borrower file | Lender-ready file from verified state (HTML / DOCX), a read-only owner action with provenance and an evidence hash, never queued for approval; a bullet term loan is serviced on a level basis for DSCR (ADR-0008), so a request that misses the covenant says so | `FEATURE_BORROWER_FILE` | on |
| Alerts and reconciliation | Cash-flow alerts from the conservative trajectory, each with an executable cure (`POST /alerts/{id}/act`); receipt reconciliation, including promised early payments (AWAITED, RECEIVED, LAPSED, SETTLED_OTHERWISE) | `FEATURE_ALERTS` | on |
| Current books and clock | Accepted commitments change every later projection; a simulated clock (`POST /clock/advance`); partial settlement; re-verification of a verdict at the moment of commitment (ADR-0006) | core | on |
| Expected-mode plans | Display-only expected-basis funding plan beside the committed one | `FEATURE_EXPECTED_PLANS` | on |
| Contract ingestion and the deal summary | Upload a signed buyer contract or a lender agreement (Word, PDF with text, or text); the agent reads it with every term beside its quoted clause, labelled "AI-generated, for reference"; the owner confirms or rejects it (an owner-only operation logged in the chain, which changes no books); once a deal is agreed, the Deals page sets the confirmed contract beside the live books; `SHOW_DEAL` in chat ("where are we with Foshan?") | `FEATURE_CONTRACTS` | on |

Other switches: `LLM_MODE=cache|live`, `LLM_PRIMARY=claude|deepseek`, `DATABASE_URL` (SQLite by default, `memory`, or Postgres), and `DEMO_MODE`.

## Credentials

| Credential | Header | Variable | Local demo value |
| --- | --- | --- | --- |
| Owner token | `X-Owner-Token` | `OWNER_TOKEN` | `demo-owner-token` |
| Agent key | `X-Agent-Key` | `AGENT_KEY` | `demo-agent-key` |
| Bank-feed key | `X-Bank-Feed-Key` | `BANK_FEED_KEY` | `demo-bank-feed-key` |

The demo values work only with `DEMO_MODE=1`, which is off by default (since 16 Oct 2026): every local run command here sets it. A deployment sets `OWNER_TOKEN`, `AGENT_KEY` and `BANK_FEED_KEY` itself (section 3). The mandate is signed with a published key labelled DEMO ONLY (`fixtures/keys/`).

## Map

- `docs/deliverables/`: the submission documents (technical document, execution evidence, test cases, demo video script, deck outline), the evidence pack in `evidence/`, and the `.docx` builds in `out/`
- `docs/SECURITY_SELF_ASSESSMENT.md`: permission model, attack results, privacy, risk register
- `docs/ARCHITECTURE.md`: modules, contracts, engine and verdict rules, and the API
- `docs/INVARIANTS.md`: the security laws
- `docs/DEMO_FLOW.md`: the scripted demo and its numbers
- `docs/adr/`: decisions (storage, rounding, fixture timeline and router, evidence, autonomy requires proof, current books and the clock, the early-payment rule, DSCR for bullet loans read as a reserve-coverage reading, accepted terms written onto invoices, funding lots with dates); the financial rules are in `docs/FINANCIAL_SEMANTICS.md`
- `services/api/evals/`: evaluation reports (`latest_report.md`, `accuracy_summary.md`, held-out reports, `security/`, `e2e/latest/`)
- `CONTEXT.md`: the glossary
- `fixtures/golden/`: the independent oracle and golden values

## Data, compliance and licence

- **Data flows.** In live mode (opt-in) a buyer's message and attached documents go to the configured model provider (DeepSeek or Anthropic) for extraction only; the model never receives the mandate, the floor, facility limits or other buyers' terms. In the default cache mode nothing leaves the machine. Real buyer documents can contain personal information; sending them abroad would need a legal basis under China's PIPL and, where required, a security assessment or standard contract before any production use. That is an obligation on a deployer, not legal advice, and we do not claim compliance. The demo uses synthetic data only.
- **AI-generated content.** Outbound text to a counterparty is template-filled from typed fields. The web UI does not yet label replies as AI-generated, for reference (a known gap).
- **Known limits.** The chain is internally checkable only: its head is not anchored outside the system. Two medium items found through chat are open (an authenticated buyer can probe the accept/counter threshold; the agent key can read protected labels through chat status replies). Between 1 and 3 Oct an independent audit (13 findings) and five red-team rounds (26 findings) were fixed, and the owner then stopped the red-team rounds; the findings, decisions and open backlog are in `docs/CONTINUOUS_OPTIMIZATION.md`. Two certifications are built but not yet run: the concurrency suite on PostgreSQL (needs a database URL) and the language-boundary certification against a live model (needs an API key). See `docs/SECURITY_SELF_ASSESSMENT.md`.
- **Licence.** [TEAM: licence to be chosen by the owner]
