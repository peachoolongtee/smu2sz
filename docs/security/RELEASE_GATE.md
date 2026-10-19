# Release security gate

Issued by the Security Lead (an AI agent in a separate session; an internal release decision, not accreditation), 14 Oct 2026. A gate decision is tied to one commit **and** one deployment configuration;
it lapses when either changes. It is never a claim of absolute security or zero residual risk.

## Configurations

| Id | Configuration |
|---|---|
| **S** (hackathon simulation) | API and web on loopback only (`127.0.0.1`; `pnpm demo` serves the web app on every interface until `sec/demo-loopback` is merged, so until then a trusted machine and network, or a firewall rule for the web port: DEMO-L1), one uvicorn process, `DEMO_MODE=1`, `DATABASE_URL=memory` or a local SQLite file, `LLM_MODE=cache`, simulated buyers, lenders and bank, demo credentials, no real money, no real customer data |
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
| `03215a20` (dev, 19 Oct: round seven merged as `c707ee8c`, code `bee9c50d`; **the submission build**) | **GO** (certified 19 Oct): loopback, one process, cache mode, synthetic data; contract terms and the router as `pnpm demo` sets them; a trusted machine and network (DEMO-L1); not live model mode. Disclosed: SEC-28 with FUND-1 to FUND-4, PAUSE-2, SEC-27, LOG-2, LOG-3 | **NO-GO** until a tested deployment profile exists | **NO-GO** |
| `5941e95a` (dev, 18 Oct: round six, the pause, the consent narrowing) | **NOT CERTIFIED** (PAY-1, Medium: "Can I pay everyone?" showed one plan and saved another); superseded by `03215a20` | NO-GO | **NO-GO** |
| `70f23ac5` (dev, 18 Oct: round five; the last certified build before the submission build) | **GO** (certified 18 Oct): loopback, one process, cache mode, synthetic data; contract terms and the router as `pnpm demo` sets them; not live model mode. Amended 19 Oct: also a trusted machine and network, because `pnpm demo` serves the web app on every interface (DEMO-L1, present in this build) | **NO-GO** until a tested deployment profile exists | **NO-GO** |
| `6d2b6941` (dev, 18 Oct: batches 7 to 10) | **CONDITIONAL**: only with `FEATURE_CONTRACT_TERMS` off | NO-GO | **NO-GO** |
| `85309b63` (dev, 17 Oct: batches 5 and 6) | **GO** (certified 17 Oct): loopback, one process, cache mode, synthetic data; ASK-1, ASK-2 and REG-1 to REG-7 disclosed | **NO-GO** until a tested deployment profile exists | **NO-GO** |
| `29fa0ea2` (dev, 17 Oct: round four, redaction, v3) | **GO** (certified 17 Oct, no test exception): loopback, one process, cache mode, synthetic data | **NO-GO** until one tested deployment profile exists; `ANONYMOUS_INTAKE=0` is now available for it | **NO-GO** |
| `0fde33fd` (dev, 17 Oct: SEC-08 executor check, OUT-1b, RT-2, RT-1) | **GO** (certified 17 Oct, with the #161 test exception) | **NO-GO** until one tested deployment profile exists (below); revised 17 Oct after the 17 Oct review of the self-assessment: the conditions were never exercised on a deployment, and SEC-19 provenance is not shown on the accept card or approvals | **NO-GO** |
| `fe56b357` (dev head, 16 Oct: final UI, R-10 rounding) | not certified: OUT-1 still present (the chat paths do not check the outside mark); R-10 reassessed, residual Low | NO-GO until OUT-1 is fixed | **NO-GO** |

**Conditions for S on `03215a20` (the submission build).** `DEMO_MODE=1`; memory or SQLite; one API process (PAUSE-2,
SEC-11); `LLM_MODE=cache`; synthetic fixtures; simulated counterparties; nobody but the presenter holds the demo credentials;
the demo laptop on a trusted network, or its firewall closed to the web port, because `pnpm demo` serves the web app on every
interface (DEMO-L1; the API stays on 127.0.0.1); results shown are simulation results. The presenter should not rely on the
send result's "the agreement is on your books" or a "gap funded" sentence when an approval is waiting: read the approvals
list (FUND-1, FUND-2). Live model mode (`pnpm demo --live-llm`) is outside this verdict.

**Conditions for S on `e8e270f8`:** loopback only; nobody but the presenter holds the demo credentials; the presenter does not approve
a second agreement for a request already agreed (SEC-02 is fixed only on the branch); results shown are simulation results.

**Additional conditions for S-net:** `sec/intake-hardening` merged; a reverse proxy with a request-rate limit and a body-size limit in
front of the API; `/docs`, `/openapi.json` not exposed; the demo credentials changed from the published values (`OWNER_TOKEN`,
`AGENT_KEY`, `BANK_FEED_KEY`, `COUNTERPARTY_KEYS` set, still `DEMO_MODE=1`); `/demo/reset` accepted as wiping the session's log.

**S-net from 17 Oct: a tested deployment profile.** A network demo is NO-GO until one profile has been deployed and checked, and the
checks recorded against that deployment: credentials changed from the published values; a signing key other than the fixture (a new owner
key pair, `OWNER_PUBLIC_KEY_HEX` set); one worker; synthetic fixtures; `LLM_MODE=cache` or a recorded live decision; documentation
hidden (`DEMO_MODE=0`); a TLS reverse proxy with per-client rate and body-size limits; anonymous intake off or "unverified sender" shown
on every view of the offer (SEC-19); a written stop procedure; the route sweep and the browser injection checks (S3) run against it.
Without such a profile the local configuration S is the one demonstrated.

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
