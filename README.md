# TermsLedger v2

An agent owned by a small supplier that controls both of its debt books under an owner-signed mandate. **Terms Guard** covers the credit the supplier gives buyers through payment terms. **Debt Desk** covers the credit it takes from lenders to survive those terms. It's our FinTechathon 2026 entry, International track, Topic E: SME Finance Copilot.

The language model only interprets text. Deterministic code decides and executes: a buyer's offer becomes typed obligations, then a dated cash and debt trajectory, then a funding plan, then covenant and mandate checks, then a verdict, then typed operations in a hash-chained log. The agent may accept a buyer's offer on its own only when it can prove it read every figure and request in it (ADR-0005); everything else waits for the owner. It does not stop at the decision: on current books and a simulated clock it watches for a late receipt, tells the owner first, proposes a cure inside the mandate with its cost, and runs it only on the owner's "go ahead".

All data is synthetic (`fixtures/`). The agent is decision support under the owner's own limits, not a lender, broker or adviser, and it executes no real payment: every facility and the bank feed are simulated. Nothing below needs an API key or the network once dependencies are installed: the default `LLM_MODE=cache` replays recorded model outputs and falls back to a deterministic rules grammar.

## Quickstart for judges

Requirements: Python 3.12 with [`uv`](https://docs.astral.sh/uv/); for the web app, Node with `pnpm`. Run everything from the repository root.

**1. Verify the submitted evidence** (standard library only, no install):

```bash
for f in services/api/evals/e2e/latest/evidence/*.jsonl; do python3 scripts/verify_evidence.py "$f"; done
```

Expect 46 lines starting `VALID`, one per scripted task. Each file is one task's hash chain; the script recomputes every `entry_hash = sha256(prev_hash + payload_json + result_json)`. (The concatenated `evidence.jsonl` holds 46 separate chains, so verify the per-task files.)

**2. Run it.**

```bash
cd services/api && uv sync && uv run uvicorn app.main:app --reload      # API on :8000 (demo credentials, cache mode)
cd apps/web && pnpm install && NEXT_PUBLIC_API_MODE=live pnpm dev        # UI on :3000; omit the variable for offline mock mode
```

Click **Start** in the demo bar and sign in as the owner when asked (the local demo token is `demo-owner-token`; add `NEXT_PUBLIC_DEMO=1` to prefill it). The chat panel opens from the header on every page, and the owner home at `/` shows the day, the agent's opener and what is waiting. To see the whole path from the deal to the repaid credit line without the UI (17 steps, in process, exit 0): `PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py`.

**3. Test.**

```bash
cd services/api && uv run pytest                     # 4,044 passed, 26 skipped on 1 Oct 2026 (Windows, SKIP_PERF_BENCH=1: the 7 latency benchmarks skipped; about 6 min)
cd apps/web && pnpm lint && pnpm typecheck && pnpm build && pnpm test:unit && pnpm test:e2e
                                                     # Playwright mock e2e: 29 passed on 1 Oct 2026
                                                     # (once: pnpm exec playwright install chromium)
```

**4. Evaluate.**

```bash
python3 scripts/run_scenarios.py --inproc                         # 46 scripted /nl tasks + evidence → services/api/evals/e2e/latest/
cd services/api && uv run python -m app.security.attacks --report # 182 attacks (122 API + 60 chat), 0 with harm; the report file covers the 122 API attacks
uv run --project services/api python scripts/evaluate.py          # full offline evaluation (about 4–5 min) → services/api/evals/latest_report.md
uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout3   # the independent held-out set
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
| Natural-language harness and chat | `POST /nl`: 19 intents (including financing comparison, alerts, reconciliation, covenant ratios, capex and the borrower file), plans, clarification, correction, nearest-capability fallback; `POST /nl/opener` (the agent speaks first); `/chat` page and slide-over panel | core | on |
| Permission tiers and executor | Tier 1 / 2 / 3, signed mandate, nonce, idempotency, circuit breaker, hash-chained log, `GET /evidence` | core | on |
| Security scenes | FastCapital and other hostile-message scenes in the demo | `FEATURE_SECURITY_SCENES` | on |
| What-if sandbox | Read-only hypothetical verdicts (terms slider, discounts) | core | on |
| Capex | NPV, payback and financing-structure comparison | `FEATURE_CAPEX` | on |
| Borrower file | Lender-ready file from verified state (HTML / DOCX), Tier 2; a bullet term loan is serviced on a level basis for DSCR (ADR-0008), so a request that misses the covenant says so | `FEATURE_BORROWER_FILE` | on |
| Alerts and reconciliation | Cash-flow alerts from the conservative trajectory, each with an executable cure (`POST /alerts/{id}/act`); receipt reconciliation, including promised early payments (AWAITED, RECEIVED, LAPSED, SETTLED_OTHERWISE) | `FEATURE_ALERTS` | on |
| Current books and clock | Accepted commitments change every later projection; a simulated clock (`POST /clock/advance`); partial settlement; re-verification of a verdict at the moment of commitment (ADR-0006) | core | on |
| Expected-mode plans | Display-only expected-basis funding plan beside the committed one | `FEATURE_EXPECTED_PLANS` | on |
| After signing | Statutory due dates, late interest, 确权 draft | `FEATURE_AFTER_SIGNING` (stub only) | **off** |

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
- `docs/adr/`: decisions (storage, rounding, fixture timeline and router, evidence, autonomy requires proof, current books and the clock, the early-payment rule, DSCR for bullet loans)
- `services/api/evals/`: evaluation reports (`latest_report.md`, `accuracy_summary.md`, held-out reports, `security/`, `e2e/latest/`)
- `CONTEXT.md`: the glossary
- `fixtures/golden/`: the independent oracle and golden values

## Data, compliance and licence

- **Data flows.** In live mode (opt-in) a buyer's message and attached documents go to the configured model provider (DeepSeek or Anthropic) for extraction only; the model never receives the mandate, the floor, facility limits or other buyers' terms. In the default cache mode nothing leaves the machine. Real buyer documents can contain personal information; sending them abroad would need a legal basis under China's PIPL and, where required, a security assessment or standard contract before any production use. That is an obligation on a deployer, not legal advice, and we do not claim compliance. The demo uses synthetic data only.
- **AI-generated content.** Outbound text to a counterparty is template-filled from typed fields. The web UI does not yet label replies as AI-generated, for reference (a known gap).
- **Known limits.** The hash chain's head is not anchored outside the system, and three medium items found through chat are open (threshold probing, the agent key reading status through chat, "go ahead" not bound to the plan shown). See `docs/SECURITY_SELF_ASSESSMENT.md`.
- **Licence.** [TEAM: licence to be chosen by the owner]
