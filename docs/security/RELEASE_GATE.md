# Release security gate

Issued by the independent Security Lead, 14 Oct 2026. A gate decision is tied to one commit **and** one deployment configuration;
it lapses when either changes. It is never a claim of absolute security or zero residual risk.

## Configurations

| Id | Configuration |
|---|---|
| **S** (hackathon simulation) | API and web on loopback only (`127.0.0.1`), one uvicorn process, `DEMO_MODE=1`, `DATABASE_URL=memory` or a local SQLite file, `LLM_MODE=cache`, simulated buyers, lenders and bank, demo credentials, no real money, no real customer data |
| **S-net** | as S, but reachable from a network (a shared demo URL, a judging booth on Wi-Fi) |
| **P** (production) | compose (`DEMO_MODE=0`, PostgreSQL 16) behind TLS, real credentials, real customer data, possibly `LLM_MODE=live` |

## Verdicts

| Commit | S | S-net | P |
|---|---|---|---|
| `e8e270f8` (`dev`, audited) | **CONDITIONAL GO**: see conditions | **NO-GO** (SEC-16, SEC-17: an anonymous caller can forge what the owner reads and stall the API) | **NO-GO** |
| `sec/candidate` (`e8e270f8` + the four queued branches; not an integration commit) | **GO**, pending certification of the integrated commit | **CONDITIONAL GO**: also needs SEC-19/20 and the S-net conditions | **NO-GO** |
| `0ba8e4c1` / `081541d1` (dev, security fixes merged) | **GO** (certified 16 Oct, `CERTIFICATIONS.md`) | **CONDITIONAL GO**: needs SEC-19/20 and the S-net conditions | **NO-GO** |
| `a6de32a2` (dev head, 16 Oct) | **GO** (certified 16 Oct) | CONDITIONAL GO, as above | **NO-GO** |
| `b6d1e519` (`int/capex-fixes`, capex buy side + dev) | **GO** (certified 16 Oct) | CONDITIONAL GO, as above | **NO-GO** |
| `0f92d433` (dev, owner's decisions) | **GO** (certified 16 Oct) | CONDITIONAL GO, as above | **NO-GO** |
| `b8c65b24` (dev, buyer messages, demo launcher) | **NOT CERTIFIED** (OUT-1): usable for S only if the presenter never marks a counter sent outside FLOW and then negotiates in the chat | NO-GO until OUT-1 is fixed | **NO-GO** |
| `719c9dcf` (dev, 17 Oct: round-two fixes, OUT-1 fixed, ui-final) | **GO** (certified 17 Oct; not live mode with real customer documents: PRIV-1 to PRIV-3) | **CONDITIONAL GO**: the S-net conditions below; in-app rate limits now exist (SEC-20) but behind a proxy every caller shares its address, so the proxy's per-client limit stays a condition; SEC-19 accepted or anonymous intake off | **NO-GO** |
| `fe56b357` (dev head, 16 Oct: final UI, R-10 rounding) | not certified: OUT-1 still present (the chat paths do not check the outside mark); R-10 reassessed, residual Low | NO-GO until OUT-1 is fixed | **NO-GO** |

**Conditions for S on `e8e270f8`:** loopback only; nobody but the presenter holds the demo credentials; the presenter does not approve
a second agreement for a request already agreed (SEC-02 is fixed only on the branch); results shown are simulation results.

**Additional conditions for S-net:** `sec/intake-hardening` merged; a reverse proxy with a request-rate limit and a body-size limit in
front of the API; `/docs`, `/openapi.json` not exposed; the demo credentials changed from the published values (`OWNER_TOKEN`,
`AGENT_KEY`, `BANK_FEED_KEY`, `COUNTERPARTY_KEYS` set, still `DEMO_MODE=1`); `/demo/reset` accepted as wiping the session's log.

## P blockers (all must close; none is closed today)

1. SEC-06: no runnable production configuration (compose cannot start; no provisioning; web built against localhost).
2. SEC-07: `DEMO_MODE` defaults on.
3. SEC-08: audit trail not tamper-evident (approvals and security events unguarded, unanchored chain, trigger bypass via a settable GUC
   on PostgreSQL, unverified).
4. R-2: one owner credential and one signing key approve everything; no second approver for Tier 2.
5. R-11 and R-10: protected values to the agent key; threshold and funding-gap oracle for keyed buyers.
6. SEC-11: unsafe with more than one process (stale clock, per-process route locks).
7. SEC-12: no CSP or frame protection while the owner token sits in `sessionStorage`.
8. SEC-10, SEC-20: no rate limiting; unbounded security-event growth.
9. Unverified: PostgreSQL concurrency and triggers; live-model language boundary (231 items) and live prompt injection; backup and
   restore; an emergency write stop (no mandate revocation route, R-14).

## Evidence for this gate

| Check | Commit | Result |
|---|---|---|
| Route authorization by request, 76 routes × 6-7 roles, `DEMO_MODE` on and off | `e8e270f8` | holds; demo credentials refused with `DEMO_MODE=0` (`evidence/2026-10-14/authz_sweep_*.json`) |
| Demo reset/restore on a persistent store, `DEMO_MODE=0` | `e8e270f8` | refused 403, ledger unchanged |
| `tests/security` + attack catalogue (126 API + 133 NL) | `sec/attack-harness` (e8e270f8 + harness fix) | all pass; 0 attacks with harm |
| Regression tests for SEC-01..05, 09, 16..18 | each fix branch | fail before, pass after |
| Full API suite, sharded by directory | baseline `sec/attack-harness` vs `sec/candidate` | see INTEGRATION_QUEUE.md "Gate run" |
| Capex buy side (not on `dev`) | `78cc1d5e`, `db95a2d5` | **do not merge**: CAPEX-1 (inflow booked from a vendor contract), CAPEX-3 (double commit) |

## Not covered by this gate (explicitly unverified)

PostgreSQL (no database available to the Security Lead); live Claude/DeepSeek behaviour (no test key); the web app in a browser
(reviewed as code only); a deployed TLS proxy; the 55 routes the catalogue does not attack beyond this audit's targeted tests;
round-three and other branches not on `dev`.
