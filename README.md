# TermsLedger v2

An agent owned by a small supplier that controls both of its debt books under an owner-signed mandate. **Terms Guard** covers the credit the supplier gives buyers through payment terms. **Debt Desk** covers the credit it takes from lenders to survive those terms. It's our FinTechathon 2026 entry, International track, Topic E: SME Finance Copilot.

The language model only interprets text. Deterministic code decides and executes: a buyer's offer becomes typed obligations, then a dated cash and debt trajectory, then a funding plan, then covenant and mandate checks, then a verdict, then typed operations in a hash-chained log. The agent may accept a buyer's offer on its own only when it can prove it read every figure and request in it (ADR-0005); everything else waits for the owner.

All data is synthetic (`fixtures/`). Nothing below needs an API key or the network once dependencies are installed: the default `LLM_MODE=cache` replays recorded model outputs and falls back to a deterministic rules grammar.

## Quickstart for judges

Requirements: Python 3.12 with [`uv`](https://docs.astral.sh/uv/); for the web app, Node with `pnpm`. Run everything from the repository root.

**1. Verify the submitted evidence** (standard library only, no install):

```bash
for f in services/api/evals/e2e/latest/evidence/*.jsonl; do python3 scripts/verify_evidence.py "$f"; done
```

Expect 37 lines starting `VALID`. Each file is one task's hash chain; the script recomputes every `entry_hash = sha256(prev_hash + payload_json + result_json)`. (The concatenated `evidence.jsonl` holds 37 separate chains, so verify the per-task files.)

**2. Run it.**

```bash
cd services/api && uv sync && uv run uvicorn app.main:app --reload      # API on :8000 (demo credentials, cache mode)
cd apps/web && pnpm install && NEXT_PUBLIC_API_MODE=live pnpm dev        # UI on :3000; omit the variable for offline mock mode
```

Click **Start** in the demo bar and sign in as the owner when asked (the local demo token is `demo-owner-token`; add `NEXT_PUBLIC_DEMO=1` to prefill it). The chat panel opens from the header on every page.

**3. Test.**

```bash
cd services/api && uv run pytest                     # 3,556 passed, 17 skipped at the submitted commit (about 2.5 min)
cd apps/web && pnpm lint && pnpm typecheck && pnpm build && pnpm test:unit && pnpm test:e2e
                                                     # unit 4/4; Playwright 46 passed, 1 skipped
                                                     # (once: pnpm exec playwright install chromium)
```

**4. Evaluate.**

```bash
python3 scripts/run_scenarios.py --inproc                         # 37 scripted /nl tasks + evidence → services/api/evals/e2e/latest/
cd services/api && uv run python -m app.security.attacks --report # 122 attacks → services/api/evals/security/latest_report.md
uv run --project services/api python scripts/evaluate.py          # full offline evaluation (about 4–5 min) → services/api/evals/latest_report.md
uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout3   # the independent held-out set
```

What we claim about the compiler, and what we don't, is in `services/api/evals/accuracy_summary.md`. In short: on the only set nobody had tuned for, the first run accepted 8 offers without the owner and 4 were wrong; after ADR-0005, 0 wrong autonomous accepts on every set and both compiler paths, while about 1 message in 3 is still decided differently from the labels and goes to the owner, a counter or a clarification.

**5. Rebuild the submission documents.**

```bash
uv run --project services/api python scripts/build_deliverables.py --refresh-evidence   # → docs/deliverables/out/*.docx
```

## Features and flags

Flags are environment variables read by `services/api/app/config.py` (`1` on, `0` off). A disabled feature returns `FEATURE_DISABLED` and never breaks the core.

| Feature | What it does | Flag | Default |
| --- | --- | --- | --- |
| Terms Guard | Compile a buyer's offer (zh + en, message and attachments) into typed obligations with exact spans; verdict with formulas; counters priced from the marginal cost of funds; break-even rule; ADR-0005 autonomy proof | core (`FEATURE_TERMS_GUARD` is declared but not yet checked) | on |
| Debt Desk | Grid-search funding router over committed facilities, marginal cost of funds, break-even discount | core (`FEATURE_DEBT_DESK` declared, not checked) | on |
| Buyer negotiation | Deterministic buyer kernel with a hidden reservation; bounded rounds; NO DEAL | core (`FEATURE_BUYER_NEGOTIATION` declared, not checked) | on |
| Natural-language harness and chat | `POST /nl`: intents, plans, clarification, correction, fallback; `/chat` page and slide-over panel | core | on |
| Permission tiers and executor | Tier 1 / 2 / 3, signed mandate, nonce, idempotency, circuit breaker, hash-chained log, `GET /evidence` | core | on |
| Security scenes | FastCapital and other hostile-message scenes in the demo | `FEATURE_SECURITY_SCENES` (declared, not checked) | on |
| What-if sandbox | Read-only hypothetical verdicts (terms slider, discounts) | core | on |
| Capex | NPV, payback and financing-structure comparison | `FEATURE_CAPEX` | on |
| Borrower file | Lender-ready file from verified state (HTML / DOCX), Tier 2 | `FEATURE_BORROWER_FILE` | on |
| Alerts and reconciliation | Cash-flow alerts from the conservative trajectory; receipt reconciliation | `FEATURE_ALERTS` | on |
| Expected-mode plans | Display-only expected-basis funding plan beside the committed one | `FEATURE_EXPECTED_PLANS` (declared, not checked) | on |
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
- `docs/adr/`: decisions (storage, rounding, fixture timeline and router, evidence, autonomy requires proof)
- `services/api/evals/`: evaluation reports (`latest_report.md`, `accuracy_summary.md`, held-out reports, `security/`, `e2e/latest/`)
- `CONTEXT.md`: the glossary
- `fixtures/golden/`: the independent oracle and golden values
