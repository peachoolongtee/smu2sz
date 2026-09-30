# TermsLedger v2

An agent owned by a small supplier that controls both of its debt books under an owner-signed mandate. **Terms Guard** covers the credit the supplier gives buyers through payment terms. **Debt Desk** covers the credit it takes from lenders to survive those terms. It's our FinTechathon 2026 entry, International track, Topic E: SME Finance Copilot.

The language model only interprets text. Deterministic code decides and executes: a buyer's offer becomes typed obligations, then a dated cash and debt trajectory, then a funding plan, then covenant and mandate checks, then a verdict, then typed operations.

## Run locally
```bash
cd services/api && uv sync && uv run uvicorn app.main:app --reload     # API on :8000
cd apps/web && pnpm install && pnpm dev                                 # UI on :3000 (mock mode by default)
cd services/api && uv run pytest                                        # tests (no network; LLM_MODE=cache)
```
To deploy, fill in `infra/.env` (see `infra/.env.example`), then run `docker compose -f infra/docker-compose.yml up --build`.

## Map
- `docs/ARCHITECTURE.md`: modules, contracts, engine and verdict rules, and the API
- `docs/INVARIANTS.md`: the security laws
- `docs/DEMO_FLOW.md`: the scripted demo and its numbers
- `docs/adr/`: decisions (rounding, fixture timeline, storage)
- `CONTEXT.md`: the glossary
- `fixtures/golden/`: the independent oracle and golden values
