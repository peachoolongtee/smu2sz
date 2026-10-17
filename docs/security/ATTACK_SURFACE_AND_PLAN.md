# Attack surface and investigation plan

Audited code `e8e270f8` (14 Oct 2026). Companion: `FINDINGS_REGISTER.md`, `INTEGRATION_QUEUE.md`.

## 1. Deployment scopes assessed

| Scope | Definition | Status |
|---|---|---|
| **S: hackathon simulation** | local machine, `DEMO_MODE=1`, memory or SQLite store, one uvicorn process, `LLM_MODE=cache`, API and web on loopback, simulated buyers/lenders/bank | assessable now |
| **P: production** | compose (`DEMO_MODE=0`, PostgreSQL 16), TLS proxy, real credentials, possibly `LLM_MODE=live` | **not runnable at `e8e270f8` (SEC-06)**; cannot be certified |

## 2. Attack surface (verified by request, not by scan)

`authz_sweep.py` called every route in the OpenAPI schema (76) plus `/docs`, `/redoc`, `/openapi.json` as anonymous, wrong owner token,
agent, bank feed, buyer-1 and owner, with every feature flag on, a fresh memory runtime per call, in both `DEMO_MODE=1` and
`DEMO_MODE=0` (non-demo credentials; demo values must then be refused). Raw results: `evidence/2026-10-14/authz_sweep_demo*.json`.

| Class | Routes | Who passes authentication (observed) |
|---|---|---|
| Public | `GET /health`, `/clock`, `/fixtures/offers`, `/docs`, `/redoc`, `/openapi.json` | anyone |
| Buyer channels | `POST /offers`, `POST /nl` | anyone (keyless = proposal only, intake cap 200/simulated day/process); buyer key binds identity; agent and owner too |
| Agent channel | `POST /operations`, `POST /approvals/{id}`, `POST /circuit/{cp}/reset` | owner or agent (authority decided in the executor) |
| Clock | `POST /clock/advance` | owner or bank feed |
| Chat side routes | `POST /nl/reset`, `/nl/opener` | owner only (403 otherwise) |
| Chat "New conversation" | `POST /nl/session/reset` | open like the buyer channel of `POST /nl` (route policy class BUYER): the owner ends any session; every other caller only a session of its own principal as `/nl` binds it (agent key, buyer key, or anonymous for an anonymous session), SEC-21; the same `ended: false` for someone else's and for none |
| Owner reads | 50 GET routes (books, mandate, ledger, audit, evidence, Deals/Customers/Activity/Home, strategy, receivables) | owner only, all verified 401 for every other role |
| Owner writes | `/offers/{id}/accept|decline|evaluate`, `/negotiate/{id}`, `/alerts/{id}/act`, `/commitments/{id}/revoke`, `/documents[...]`, `/buyers/{id}/inputs`, `/firm/inputs`, `/pilot/journal`, `/capex/apply`, `/demo/reset|restore|bank-receipt`, read-only computations (`/router/plan`, `/whatif`, `/capex/evaluate`, `/borrower-file`, `/facilities/compile`) | owner only, verified |

Corrections to `docs/SECURITY_ENDPOINT_INVENTORY.json`: `/nl` and `/offers` are not owner-only (they accept anyone);
strategy, exposure and customer-inputs routes are owner-gated via the parent router (verified by request); the
`attack_catalogue_mentions_prefix` column is a prefix match and overstates coverage (only 21 of 76 routes are attacked over HTTP).

## 3. Sensitive data and trust boundaries

- **Protected values:** cash, reserve floor, mandate caps and headroom, facility terms, other buyers' terms, contract clauses,
  the operation log. Readable over HTTP only with the owner token (verified), **except** via `/nl` with the agent key (R-11,
  under review) and whatever the buyer channels echo (R-10, under review).
- **Untrusted input:** buyer text and attachments (`/offers`, `/nl`), uploaded contracts (`/documents`), owner-supplied ids and
  context, model output in live mode, the bank feed.
- **State changers:** the executor (all books), the clock (owner, bank feed), demo reset/restore (owner, demo or memory store
  only: verified), context stores outside the chain (documents, customer inputs, pilot journal, decision facts, security events).
- **Credentials:** owner token, agent key, bank-feed key, buyer keys (env, demo fallbacks while `DEMO_MODE=1`); Ed25519 mandate
  key (public pinned; demo private key committed for the demo).

## 4. Prioritised investigation plan

| # | Item | Why first | Status |
|---|---|---|---|
| 1 | Route authorization by request, both modes | everything else assumes it | **done**: holds on all 76 routes |
| 2 | New owner write routes (accept/decline, demo restore/bank-receipt, inputs, alerts act) | never attacked | **done**: SEC-02..05 |
| 3 | Restore the regression gate (SEC-01) and re-run the full catalogue on the fix commit | current evidence is from 5 Oct | fix in progress |
| 4 | LLM/NL boundary: R-10, R-11, injection, egress, session binding | sensitive-data exposure | reviewer running |
| 5 | Audit integrity and persistence (R-13) | evidence of record | **done on SQLite**: SEC-08, SEC-10, SEC-11 |
| 6 | Deployment posture and web | production gate | **done**: SEC-06, 07, 12, 13, 15 |
| 7 | Capex buy side (pre-merge, not on `dev`) | engine change | reviewer running |
| 8 | New adversarial tests for the 55 unattacked routes (replay, stale binding, object ids, concurrency) | coverage | after fixes |
| 9 | PostgreSQL concurrency + trigger bypass | certification gap | **blocked**: no PostgreSQL |
| 10 | Live-model boundary (231 items) and live injection | certification gap | **blocked**: no test key |
