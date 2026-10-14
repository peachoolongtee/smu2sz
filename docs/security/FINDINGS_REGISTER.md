# Security findings register (FLOW / TermsLedger)

Owner: independent Security Lead. Branch `security/lead-audit` (worktree `.claude/worktrees/sec-lead`).
**Audited code: `e8e270f8`** (`origin/dev`, 14 Oct 2026 18:47 +08) plus the docs-only handoff commit `94b4f79b`.
Opened 14 Oct 2026. Evidence scripts: `docs/security/evidence/2026-10-14/` (run from `services/api` with
`PYTHONUTF8=1 TERMSLEDGER_NO_DOTENV=1 LLM_MODE=cache`; each states its own `DATABASE_URL` / `DEMO_MODE`).

**Status words.** CONFIRMED = reproduced by the Security Lead in this worktree (not only by a reviewer agent).
REVIEWER-CONFIRMED = reproduced by a delegated reviewer, code path re-read by the Security Lead, not re-run.
SUSPECTED = code reading only. Severity is for the stated scope; **S** = hackathon simulation scope (local,
`DEMO_MODE=1`, memory/SQLite, one process, `LLM_MODE=cache`), **P** = a production deployment (none runnable today: SEC-06).

| ID | Title | Sev S / P | Status | Fix |
|---|---|---|---|---|
| SEC-01 | Security attack suite cannot run on `dev` (regression gate silently broken) | High / High | CONFIRMED | open |
| SEC-02 | Two ACTIVE agreements for one buyer request: concession and invoice adjustment booked twice | High / High | CONFIRMED | open |
| SEC-03 | Refused owner accept leaves an orphan PROPOSED commitment (non-atomic accept) | Medium / Medium | CONFIRMED | open |
| SEC-04 | Agent key blocks the owner's decline by pre-claiming its predictable idempotency key | Medium / Medium | CONFIRMED | open |
| SEC-05 | Agent key silently opens any buyer's circuit, blocking owner accept/decline | Medium / Medium | CONFIRMED | open |
| SEC-06 | No runnable production configuration (compose cannot start; web build points at localhost) | n/a / High | CONFIRMED (code) | open |
| SEC-07 | `DEMO_MODE` defaults on; published credentials and committed demo signing key = owner takeover outside compose | Info / High | CONFIRMED (code) | open |
| SEC-08 | Audit trail not tamper-evident (R-13): truncation/rewrite verify; approvals and security events unguarded; approval flip executes a rejected op | Medium / High | CONFIRMED (SQLite) | open |
| SEC-09 | Bank-feed key moves the clock without bound: expires the mandate, posts debt service, logged as SYSTEM | Medium / Medium | CONFIRMED | open |
| SEC-10 | Unauthenticated callers grow `security_events` without bound; each refusal reads the whole table | Medium / Medium | REVIEWER-CONFIRMED | open |
| SEC-11 | Multi-process unsafe: stale clock books backdated ops; route checks rely on a per-process lock | Info / High | CONFIRMED (two runtimes, one SQLite) | open |
| SEC-12 | No security headers (CSP, frame-ancestors, nosniff, HSTS); owner token in `sessionStorage` | Low / Medium | CONFIRMED (code) | open |
| SEC-13 | Public `/docs`, `/redoc`, `/openapi.json`; `/health` discloses `llm_mode` and every feature flag | Low / Low | CONFIRMED | open |
| SEC-14 | Refused operations return HTTP 200 (`/circuit/*/reset`, `/approvals/*` by agent) | Info / Low | CONFIRMED | open |
| SEC-15 | Container and secret hygiene: root containers, unpinned bases, `uv:latest`, no `.dockerignore`, placeholder secrets accepted | Info / Low | REVIEWER-CONFIRMED (code) | open |
| R-2 | One owner credential + one signing key; accept route queues and approves in one call | Info / Medium | open (accepted risk, re-confirmed in code) | design |
| R-3 | Persuaded-but-authorised agent: Tier 1 inside the mandate, no aggregate draw limit | Medium / Medium | open (re-confirmed in code) | design |
| R-10 | Buyer threshold probing; no per-counterparty attempt budget for keyed buyers | pending LLM-boundary review | | |
| R-11 | Agent key reads protected status through `/nl` | pending LLM-boundary review | | |

Unverified areas and blockers are listed at the end; they are not passes.

---

## SEC-01 Security attack suite cannot run on `dev`

- **Affected:** `services/api/app/security/attacks.py:707`, `tests/security/test_attacks.py`, `tests/security/test_scoreboard.py`.
- **Evidence (CONFIRMED, 14 Oct, `e8e270f8`):** `pytest tests/security tests/concurrency` → 126 `test_attack_causes_zero_harm` ERROR,
  3 more ERROR, 2 FAILED. Cause: `CompiledOffer.model_validate_json(...)` on the `/offers` response rejects the new field
  `abstentions[].reason_when` (`extra_forbidden`), added to `app/api/offers.py:75-79` after the catalogue's last change (5 Oct).
  `_without_display` strips only display keys, not `*_when`.
- **Consequence:** the "0 of 259 attacks caused harm" claim has no current evidence; any security regression since the field
  landed would not have been caught. Lead gates ran `tests/api` only.
- **Exploitability:** none directly; it removes the control that would detect the others.
- **Fix:** strip the presentation fields in the harness (or validate with `extra="ignore"` on a harness-side copy), then re-run the
  full catalogue and record a new report on the fixed commit. Add `tests/security` to the lead gate.

## SEC-02 Two ACTIVE agreements for one buyer request

- **Affected:** `app/operations/executor.py:1032-1054` (exclusivity only for obligations naming an existing receivable;
  `RI:` future invoices are skipped), `app/api/accept.py:233-249` (`_answered` ignores PROPOSED commitments without a pending approval).
- **Reproduction (CONFIRMED, `evidence/.../repro3.py`, busy scenario, memory store):** agent opens the circuit (SEC-05) → owner
  accept refused (orphan PROPOSED commitment, SEC-03) → owner resets circuit and accepts (200, ACTIVE) → an ACCEPT_OFFER naming the
  orphan's nonce is queued (`PENDING_APPROVAL`, reason "lengthens payment terms", no mention of the agreement in force) → owner
  approves in `/approvals` → EXECUTED. Observed: `commitments [CMT-0569… ACTIVE, CMT-ec95… ACTIVE]`, forward concessions
  `[(CMT-ec95…, 66832), (CMT-0569…, 66832)]`, two invoice adjustments for the same obligation `OFF-96e7…-O1`.
- **Preconditions:** owner approval of the second item (so not an authority bypass); the nonce comes from owner-only `/ledger`
  or from the deterministic NL nonce. A second path (two workers, reviewer `repro5.py`) needs more than one process (SEC-11).
- **Consequence:** the books carry the concession twice (forward concession value and invoice terms), misstating cash, cost and
  the buyer's terms; downstream readers (Deals, Activity, alerts) show two agreements.
- **Fix (needs Fable: shared financial semantics):** in the executor's binding check, refuse an AcceptOffer when any
  ACCEPTED/ACTIVE commitment already exists for the same `offer_id`, regardless of receivable; plus SEC-03.

## SEC-03 Refused owner accept leaves an orphan PROPOSED commitment

- **Affected:** `app/api/accept.py:362-376`: `propose_commitment`, `execute` and `decide` are three units of work.
- **Reproduction (CONFIRMED, `repro1.py` A):** two refused owner accepts and one refused decline: commitments `[] → 2 PROPOSED`,
  log 4 → 7, `state_version` unchanged, picture still says `available: True`. Reviewer `repro2.py` D: orphan later raises a
  misleading expiry alert suggesting ACCEPT_OFFER for an already-agreed request.
- **Consequence:** raw material for SEC-02; misleading alerts. If `decide`'s re-run refuses, an approval may stay APPROVED with
  nothing executed (SUSPECTED, not reproduced).
- **Fix:** run the three steps in one `rt.store.transaction()` so a refusal rolls back the proposal, or move the commitment to
  EXPIRED/REVOKED on any non-EXECUTED result.

## SEC-04 Agent key blocks the owner's decline

- **Affected:** `app/api/accept.py:389` (`op_id = idempotency_key = f"decline-{offer_id}-{verdict.id}"`, verdict ids deterministic),
  `executor._duplicate`.
- **Reproduction (CONFIRMED, `repro1.py` B):** agent posts REJECT_OFFER under that key (EXECUTED; an agent rejection does not close
  the request) → owner `POST /offers/{id}/decline` 409 NOT_RECORDED "Idempotency key … already used"; a REPLAY security event is
  logged against the owner; decision stays RESPONSE_READY until the books change.
- **Consequence:** an agent (or anyone holding its key) can deny the owner a control action; evidence log blames the owner.
- **Fix:** server-side random component in route-made keys, or reserve the `accept-`/`decline-` prefixes for owner routes.

## SEC-05 Agent key silently opens any buyer's circuit

- **Affected:** `executor.py` circuit gate (applies to owner-requested Accept/Reject), `_recent_refusals` counts refusals by anyone;
  a refused op does not burn its key.
- **Reproduction (CONFIRMED, `repro1.py` A):** three agent COUNTER_OFFERs with a bogus `counter_id` and the same key → all REFUSED,
  circuit open, **no security event** (`sec 0`); owner accept and decline both 409 "Circuit open".
- **Consequence:** denial of the owner's decisions per buyer, repeatable after each owner reset; feeds SEC-03.
- **Fix:** do not gate `requested_by == OWNER` on the circuit; count only refusals attributable to the counterparty's channel or
  carrying a security kind; log a security event when an agent op trips a circuit.

## SEC-06 No runnable production configuration

- **Evidence (CONFIRMED, code):** `infra/docker-compose.yml` sets `DEMO_MODE: "0"` but passes no `OWNER_PUBLIC_KEY_HEX` or
  `COUNTERPARTY_KEYS` → `runtime.py:235-237` StartupError; an empty PostgreSQL store with `DEMO_MODE=0` → `runtime.py:259-263`
  StartupError; no provisioning script exists (`scripts/`, `services/api/scripts/`). `infra/web.Dockerfile:6-8` bakes
  `NEXT_PUBLIC_API_URL=http://localhost:8000` (compose passes no build args); web published on `0.0.0.0:3000` over HTTP.
- **Consequence:** production cannot be certified; the likeliest operator workaround (set `DEMO_MODE=1`) lands in SEC-07.
- **Fix:** add the key to compose and `.env.example`; a provisioning command (books + owner-signed mandate); web build args;
  bind web to loopback behind the TLS proxy.

## SEC-07 `DEMO_MODE` defaults on

- **Evidence (CONFIRMED, code):** `app/api/auth.py:28` default `"1"`; `_expected()` falls back to published values;
  `runtime.py:232-234` pins the demo key whose private half is committed (`fixtures/keys/owner_demo_ed25519.json`);
  `infra/api.Dockerfile` sets no `DEMO_MODE`.
- **Verified safe direction:** with `DEMO_MODE=0` every demo credential is refused on all 76 routes (`authz_sweep_demo_off.json`);
  the demo key is never pinned; `/demo/reset` and `/demo/restore` return 403 `RESET_REFUSED` on a persistent store
  (`reset_prod_sqlite.py`, ledger unchanged). **This corrects the handoff/self-assessment F-05**, which says reset erases the log in
  any mode: it does so only with `DEMO_MODE=1` or the memory store.
- **Fix:** default `DEMO_MODE` to off (dev scripts opt in), `ENV DEMO_MODE=0` in the API image, refuse `DEMO_MODE=1` with a
  PostgreSQL URL.

## SEC-08 Audit trail not tamper-evident (R-13, extended)

- **Evidence:** the chain (`app/persistence/chain.py:19-36`) is an unkeyed hash from a zero genesis, verified only internally; DB
  triggers guard only `operations` and `used_nonces` (`guards.py`); `approvals`, `security_events`, `commitments`, states are
  unguarded and outside the chain; result JSON carries no state hash.
- **Reproduction:** CONFIRMED (`approval_flip.py`, SQLite): owner REJECT → raw `UPDATE approvals SET status='PENDING'` → owner
  APPROVE → EXECUTED; log shows PENDING_APPROVAL, REFUSED, EXECUTED for one approval id; `chain_valid: True`.
  REVIEWER-CONFIRMED (`r13.py`): tail truncation (after dropping the trigger) and a consistent full rewrite both verify; deleting
  `security_events`/`evidence_exports` needs no trigger change. In `DEMO_MODE=1` an owner `POST /demo/reset` empties the log and the
  empty chain verifies (by design for the demo; only trace is in-memory `demo_history`).
  SUSPECTED (PostgreSQL unavailable): the trigger function honours `current_setting('termsledger.allow_reset')`, a custom GUC any
  session can `SET LOCAL`, so any role with DELETE can bypass it without DDL (`guards.py:210,264`).
- **Preconditions:** database write access (insider, leaked DB credential, SQL injection) or the owner token in demo mode.
- **Fix:** refuse a decision when the log already holds a decision entry for that approval id (log as source of truth); triggers
  allowing only `PENDING → APPROVED|REJECTED`; run the API as a non-owner role without UPDATE/DELETE/TRUNCATE on log tables; reset
  via a SECURITY DEFINER function, not a settable flag; sign and externally publish `(seq, head_hash)` periodically; include
  `state_version` and a state hash in result JSON.

## SEC-09 Bank-feed key moves the clock without bound

- **Affected:** `app/api/clock.py:31-43` (`MAX_STEP_DAYS=366` per call, unlimited calls), `runtime.advance_to` logs `SYSTEM`.
- **Reproduction (CONFIRMED, `repro2.py` E):** bank key: `/operations` 401, but three `{"days":366}` advances move day 0 → 1098;
  mandate (expires day 90) now `MANDATE_EXPIRED`; one step posted `debt_service_fen: 42000000`; later agent ops REFUSED.
  Time cannot be moved back.
- **Consequence:** a holder of the bank-feed key (an external integration) can irreversibly expire the mandate, close days,
  post debt service, expire commitments and lapse offers; the log does not say who did it.
- **Fix:** remove clock authority from the bank-feed key (owner only), or cap it to one day per call and never past the real
  calendar; record the real actor.

## SEC-10 Unbounded security-event growth from anonymous requests

- **Affected:** `app/api/auth.py:69-90` (`log_refusal` on every refused credential; id uses `len(rt.store.security_events())`, a full
  read), `app/operations/executor.py:771` (same pattern), `app/api/offers.py:51-61` (one event per over-cap intake).
- **Evidence (REVIEWER-CONFIRMED, `refusal_dos.py`):** 2,000 anonymous `GET /ledger` on SQLite: per-refusal cost 5.4 → 17.9 ms,
  linear in stored events (≈0.7 s/refusal at 100k events); `/audit` already 844 KiB; 16 concurrent refusals produced 2 distinct
  ids (no unique constraint). Code path re-read by the Security Lead.
- **Consequence:** storage and latency DoS by an unauthenticated caller; evidence log diluted; on SQLite the executor's own
  security writes hold the write lock while reading the whole table.
- **Fix:** uuid/sequence ids; aggregate refusals per (route, reason, day) as a counter; rate-limit 401s; paginate `/audit`.

## SEC-11 Multi-process unsafe

- **Reproduction (CONFIRMED, `stale_day.py`):** two runtimes on one SQLite file; A advances to day 20; B (still day 0) executes
  DrawFacility dated day 0 → EXECUTED `effective_day=0`; log `(4, ADVANCE_CLOCK, 20), (5, DRAW_FACILITY, 0)`, chain valid.
  The concurrency certification (§5) claims a lagging process refuses as STALE_OPERATION: it is the reverse.
  REVIEWER-CONFIRMED (`repro5.py`): two runtimes each pass the accept binding and both record an agreement (SEC-02).
- **Scope:** the shipped image runs one uvicorn process, so this is latent; it blocks any multi-worker or multi-replica deployment.
- **Fix:** take `now` from the stored state inside the unit of work and refuse ops dated before `state.as_of_day`; move route
  invariants (one agreement per offer) into the executor.

## SEC-12 No security headers

- **Evidence (CONFIRMED, code):** no `headers()` in `apps/web/next.config.mjs`, no middleware, none on the API (which serves
  `/borrower-file/*.html`). Token in `sessionStorage` (`apps/web/lib/auth.ts`). No XSS sink found (reviewer: only a static
  `dangerouslySetInnerHTML` in `app/layout.tsx:22`; server hrefs built with `quote(..., safe="")`).
- **Fix:** CSP (`default-src 'self'`, `connect-src` API origin, `frame-ancestors 'none'`, hash for the pre-hydration script),
  `nosniff`, `Referrer-Policy: no-referrer`, HSTS at the proxy; same frame/nosniff headers on the API.

## SEC-13 Public API documentation and flag disclosure

- **Evidence (CONFIRMED, sweep):** `/docs`, `/redoc`, `/openapi.json`, `/health`, `/clock`, `/fixtures/offers` answer anonymous callers
  in both modes. **Fix:** disable docs outside `DEMO_MODE`; `/health` → `{"ok": true}`.

## SEC-14 Refused operations return HTTP 200

- **Evidence (CONFIRMED, sweep + code):** agent `POST /circuit/{id}/reset` → 200 with body `REFUSED INSUFFICIENT_AUTHORITY`
  (`executor.py:403-424`); owner can "reset" a non-existent counterparty id (log entry written). Not a bypass.
- **Fix:** 403 for authority refusals; 404 for unknown counterparty.

## SEC-15 Container and secret hygiene

- Root containers, unpinned `python:3.12-slim`/`node:22-alpine`, `ghcr.io/astral-sh/uv:latest`, no `.dockerignore` (repo-root
  `.env` sent as build context), no length/placeholder check on `OWNER_TOKEN` etc. (reviewer, re-read by the Security Lead).

## Prior risks re-checked

- **R-2** (CONFIRMED in code): no second approver; `accept.py:362-370` queues and approves in one request. Accepted design risk for
  the simulation; production needs a second approver or hardware key for Tier 2.
- **R-3** (code): Tier-2 threshold is a strict "greater than" per operation (`tiers.py:104`); no aggregate or daily draw limit, so
  an authorised agent can draw the whole line in Tier 1 steps. Not re-run.
- **R-10, R-11:** pending the LLM-boundary reviewer; to be reproduced by the Security Lead before being marked.
- **R-14** partly stale: `OWNER_PUBLIC_KEY_HEX` is required outside demo; there is still no mandate replace/revoke route and no
  emergency write switch.

## Unverified areas and blockers (not passes)

| Area | Why unverified | Needed |
|---|---|---|
| PostgreSQL concurrency, triggers, GUC bypass (SEC-08) | no Docker, no PostgreSQL; WSL install needs sudo | a throwaway local PostgreSQL 16 and `TERMSLEDGER_TEST_DATABASE_URL` |
| Live-model language boundary (231 items) and live prompt injection | no model API key available to this session | a test-only key, budget approval |
| Full attack catalogue on current code | SEC-01 | fix SEC-01, re-run |
| 55 of 76 routes never attacked by the catalogue | catalogue last changed 5 Oct | new attacks for new routes (in progress) |
| Backup/restore, emergency write stop | no procedure or route exists | design work (Fable) |
| TLS proxy, real deployment | no proxy config committed (SEC-06) | a deployment to certify |
| Capex buy side (not on `dev`) | pre-merge review in progress | — |
