# TermsLedger v2

An agent owned by a small supplier that controls both of its debt books under an owner-signed mandate. **Terms Guard** covers the credit the supplier gives buyers through payment terms. **Debt Desk** covers the credit it takes from lenders to survive those terms. It's our FinTechathon 2026 entry, International track, Topic E: SME Finance Copilot.

The language model only interprets text. Deterministic code decides and executes: a buyer's offer becomes typed obligations, then a dated cash and debt trajectory, then a funding plan, then covenant and mandate checks, then a verdict, then typed operations in a hash-chained log. The agent may accept a buyer's offer on its own only when it can prove it read every figure and request in it (ADR-0005); everything else waits for the owner. It does not stop at the decision: on current books and a simulated clock it watches for a late receipt, tells the owner first, and proposes a cure inside the mandate with its cost. Free text executes only as a closed affirmative command, and a plan is proposed first and run only on the owner's "go ahead", as exactly the operations shown. A cure that costs more a year than the mandate's ceiling is queued, and runs only when the owner approves it as a second step (in the demo: go ahead, approve, and the cash lands on day 37).

All data is synthetic (`fixtures/`). This is a simulation: the agent is decision support under the owner's own limits, not a lender, broker or adviser, and it executes no real payment; every facility, the buyer and the bank feed are simulated. It screens the entered obligations only, and it makes no claim of bank-covenant compliance. Nothing below needs an API key or the network once dependencies are installed: the default `LLM_MODE=cache` replays recorded model outputs and falls back to a deterministic rules grammar.

## Quickstart for judges

Requirements: Python 3.12 with [`uv`](https://docs.astral.sh/uv/); for the web app, Node with `pnpm`. Run everything from the repository root.

**1. Verify the submitted evidence** (standard library only, no install):

```bash
for f in services/api/evals/e2e/latest/evidence/*.jsonl; do python3 scripts/verify_evidence.py "$f"; done
```

Expect 49 lines starting `VALID`, one per scripted task. Each file is one task's hash chain; the script recomputes every `entry_hash = sha256(prev_hash + payload_json + result_json)`. (The concatenated `evidence.jsonl` holds 49 separate chains, so verify the per-task files.)

**2. Run it.**

```bash
cd services/api && uv sync && uv run uvicorn app.main:app --reload      # API on :8000 (demo credentials, cache mode)
cd apps/web && pnpm install && NEXT_PUBLIC_API_MODE=live pnpm dev        # UI on :3000; omit the variable for offline mock mode
```

Click **Start** in the demo bar and sign in as the owner when asked (the local demo token is `demo-owner-token`; add `NEXT_PUBLIC_DEMO=1` to prefill it). The chat panel opens from the header on every page, and the owner home at `/` shows the day, the agent's opener and what is waiting. To see the whole path from the deal to the repaid credit line without the UI (17 steps, in process, exit 0; the day-34 cure takes two steps, go ahead then approve, and lands on day 37): `PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py`.

**3. Test.**

```bash
cd services/api && uv run pytest                     # 5,446 passed, 33 skipped on 3 Oct 2026 (Windows, SKIP_PERF_BENCH=1: the latency benchmarks skipped; two sequential chunks, about 14 min)
cd apps/web && pnpm lint && pnpm typecheck && pnpm build && pnpm test:unit && pnpm test:e2e
                                                     # Playwright mock e2e: 35 passed (live project: 30) when last run, per docs/CONTINUOUS_OPTIMIZATION.md; the web mock refresh is in progress
                                                     # (once: pnpm exec playwright install chromium)
```

**4. Evaluate.**

```bash
python3 scripts/run_scenarios.py --inproc                         # 49 scripted /nl tasks + evidence → services/api/evals/e2e/latest/
cd services/api && uv run python -m app.security.attacks --report # 255 attacks (122 API + 133 chat, including the NL-CS consent attacks and each buyer attack with and without the buyer's key), 0 with harm
uv run --project services/api python scripts/evaluate.py          # full offline evaluation (about 5 min) → services/api/evals/latest_report.md
uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout3   # the independent held-out set
PYTHONUTF8=1 uv run --project services/api python scripts/certify_language_boundary.py --backend cache   # 231-item language-boundary certification; also --backend fake; WRONG_MATERIAL 0 in both. --backend live is pending an API key
cd services/api && SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/concurrency   # two-process invariants on SQLite; the PostgreSQL cases run when TERMSLEDGER_TEST_DATABASE_URL is set (pending a database URL)
```

What we claim about the compiler, and what we don't, is in `services/api/evals/accuracy_summary.md`. In short: since ADR-0005 there are 0 wrong autonomous accepts on the held-out sets and both compiler paths, and text the compiler cannot fully read fails closed and goes to the owner. The figures behind that, unchanged: on the only set nobody had tuned for, the first run (before ADR-0005) accepted 8 offers without the owner and 4 were wrong, and about 1 message in 3 is still decided differently from the labels (it goes to the owner, a counter or a clarification).

**5. Rebuild the submission documents.**

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
| Natural-language harness and chat | `POST /nl`: 20 intents (including financing comparison, alerts, reconciliation, covenant ratios, capex, the borrower file, and a read-only RECORD_FACT that says chat cannot record a stated bill or figure), plans, clarification, correction, nearest-capability fallback; `POST /nl/opener` (the agent speaks first); `/chat` page and slide-over panel | core | on |
| Permission tiers and executor | Tier 1 / 2 / 3, signed mandate, nonce, idempotency, circuit breaker, hash-chained log, `GET /evidence` | core | on |
| Security scenes | FastCapital and other hostile-message scenes in the demo | `FEATURE_SECURITY_SCENES` | on |
| What-if sandbox | Read-only hypothetical verdicts (terms slider, discounts) | core | on |
| Capex | NPV, payback and financing-structure comparison; evaluating writes nothing, and `POST /capex/apply` is the owner's explicit step that queues the Tier-2 application | `FEATURE_CAPEX` | on |
| Borrower file | Lender-ready file from verified state (HTML / DOCX), a read-only owner action with provenance and an evidence hash, never queued for approval; a bullet term loan is serviced on a level basis for DSCR (ADR-0008), so a request that misses the covenant says so | `FEATURE_BORROWER_FILE` | on |
| Alerts and reconciliation | Cash-flow alerts from the conservative trajectory, each with an executable cure (`POST /alerts/{id}/act`); receipt reconciliation, including promised early payments (AWAITED, RECEIVED, LAPSED, SETTLED_OTHERWISE) | `FEATURE_ALERTS` | on |
| Current books and clock | Accepted commitments change every later projection; a simulated clock (`POST /clock/advance`); partial settlement; re-verification of a verdict at the moment of commitment (ADR-0006) | core | on |
| Expected-mode plans | Display-only expected-basis funding plan beside the committed one | `FEATURE_EXPECTED_PLANS` | on |

Other switches: `LLM_MODE=cache|live`, `LLM_PRIMARY=claude|deepseek`, `DATABASE_URL` (SQLite by default, `memory`, or Postgres), and `DEMO_MODE`.

## Credentials

| Credential | Header | Variable | Local demo value |
| --- | --- | --- | --- |
| Owner token | `X-Owner-Token` | `OWNER_TOKEN` | `demo-owner-token` |
| Agent key | `X-Agent-Key` | `AGENT_KEY` | `demo-agent-key` |
| Bank-feed key | `X-Bank-Feed-Key` | `BANK_FEED_KEY` | `demo-bank-feed-key` |

The demo values work only while `DEMO_MODE` is on (the default for local runs). The mandate is signed with a published key labelled DEMO ONLY (`fixtures/keys/`).

## Deploy

Copy `infra/.env.example` to `infra/.env`, set `POSTGRES_PASSWORD`, `OWNER_TOKEN` and `AGENT_KEY` to random values, then run `docker compose -f infra/docker-compose.yml up --build`. Compose sets **`DEMO_MODE=0`**, so the demo credentials are rejected and the owner and agent routes fail closed until real ones are set. The API binds to `127.0.0.1:8000`, to sit behind a TLS reverse proxy. Postgres can be the bundled container or Supabase via `DATABASE_URL`; the Alembic migrations enable row-level security on every table and make the operations log append-only.

## Map

- `docs/deliverables/`: the submission documents (technical document, execution evidence, demo video script, deck outline) and their `.docx` builds in `out/`
- `docs/SECURITY_SELF_ASSESSMENT.md`: permission model, attack results, privacy, risk register
- `docs/ARCHITECTURE.md`: modules, contracts, engine and verdict rules, and the API
- `docs/INVARIANTS.md`: the security laws
- `docs/DEMO_FLOW.md`: the scripted demo and its numbers
- `docs/UI_UX_CHANGES.md`: the living record of interface changes, the label map (old → new) and the open UX items
- `docs/adr/`: decisions (storage, rounding, fixture timeline and router, evidence, autonomy requires proof, current books and the clock, the early-payment rule, DSCR for bullet loans read as a reserve-coverage reading, accepted terms written onto invoices, funding lots with dates); the financial rules are in `docs/FINANCIAL_SEMANTICS.md`
- `services/api/evals/`: evaluation reports (`latest_report.md`, `accuracy_summary.md`, held-out reports, `security/`, `e2e/latest/`)
- `CONTEXT.md`: the glossary
- `fixtures/golden/`: the independent oracle and golden values

## Data, compliance and licence

- **Data flows.** In live mode (opt-in) a buyer's message and attached documents go to the configured model provider (DeepSeek or Anthropic) for extraction only; the model never receives the mandate, the floor, facility limits or other buyers' terms. In the default cache mode nothing leaves the machine. Real buyer documents can contain personal information; sending them abroad would need a legal basis under China's PIPL and, where required, a security assessment or standard contract before any production use. That is an obligation on a deployer, not legal advice, and we do not claim compliance. The demo uses synthetic data only.
- **AI-generated content.** Outbound text to a counterparty is template-filled from typed fields. The web UI does not yet label replies as AI-generated, for reference (a known gap).
- **Known limits.** The chain is internally checkable only: its head is not anchored outside the system. Two medium items found through chat are open (an authenticated buyer can probe the accept/counter threshold; the agent key can read protected labels through chat status replies). Between 1 and 3 Oct an independent audit (13 findings) and five red-team rounds (26 findings) were fixed, and the owner then stopped the red-team rounds; the findings, decisions and open backlog are in `docs/CONTINUOUS_OPTIMIZATION.md`. Two certifications are built but not yet run: the concurrency suite on PostgreSQL (needs a database URL) and the language-boundary certification against a live model (needs an API key). See `docs/SECURITY_SELF_ASSESSMENT.md`.
- **Licence.** [TEAM: licence to be chosen by the owner]
