# Security integration queue

## Round four, 17 Oct: after the external review of the self-assessment

Built from dev `0fde33fd`, one concern each, no engine module touched. **Combined gate** on `sec/batch-17oct` @ `4fbb2946` (dev `0fde33fd`
plus all six below, merged in this order, no conflicts):

| Suite | Result |
| --- | --- |
| tests/security | 380 passed |
| tests/operations | 412 passed, 1 skipped |
| tests/books | 83 passed (#161 gone) |
| tests/persistence | 161 passed, 1 skipped |
| tests/nl | 1,156 passed |
| tests/api | 1,729 passed, 2 skipped |
| Mock browser suite | 445 passed, 61 skipped |
| typecheck, lint, unit | pass |
| ruff on the changed files | 2 findings, both pre-existing lines in `test_modules_on_books.py` (dev has 63 repo-wide) |

| # | Branch @ head | Finding | Files | Tests | Ready |
|---|---|---|---|---|---|
| 1 | `sec/refusal-budget` @ `089ff973` | SEC-26: one address could hide everyone's refused credentials for an hour | `app/api/auth.py`, `tests/security/test_sec26_refusal_budget.py` | regression 3 (2 fail before) | **yes** |
| 2 | `sec/evidence-verifier` @ `aa050d85` | EV-1: the offline verifier trusted readable fields, ignored the count, had no checkpoint | `scripts/verify_evidence.py`, `tests/security/test_evidence_verifier.py` | regression 5 (5 fail before); all 49 committed evidence files VALID | **yes** |
| 3 | `sec/anonymous-intake-switch` @ `d8d22332` | SEC-19: `ANONYMOUS_INTAKE=0` for a network demo (default on) | `app/config.py`, `app/api/offers.py`, `tests/security/test_anonymous_intake_switch.py` | regression 3 (1 fails before) | **yes** |
| 4 | `sec/harness-assurance` @ `28133edc` | SEC-24, SEC-32, SEC-34: NOT_REACHED, typed expectations for every API case, exact counts (127 API, 133 chat), positive controls, mutation tests, TC-04 | `app/security/attacks.py`, `evals/security/attacks.yaml`, `evals/security/latest_report.*`, `tests/security/` | tests/security 353 on the branch | **yes** |
| 5 | `sec/route-policy` @ `3c4bd9ed` | SEC-25: every method and route classified and called as every caller | `tests/security/test_route_policy.py`, `route_policy_support.py` | 16 passed (about 130 s) | **yes** |
| 6 | `ci/linux-green` commit `e658ba64` (cherry-pick alone) | T-161: the stale router-plan digest | `tests/books/test_modules_on_books.py` (golden only) | tests/books 83 passed | **yes** |
| 7 | `docs/security-assessment-v3` @ (latest) | self-assessment v3, technical document alignment, register, certifications, release gate, figures, builder | docs and `scripts/build_deliverables.py`, `scripts/security_manifest.py` | builds all three documents | **yes** (owner's review of v3) |

The anonymous-intake switch, SEC-26 and the evidence verifier are described in v3 as in the assessed build; if any is not merged, the
Security Lead moves it to open before certifying.

## Round three, 17 Oct

The five round-two branches and the OUT-1 fix are merged (`719c9dcf`, certified 17 Oct for scope S).

| Branch @ head | Finding | Files | Tests | Ready |
|---|---|---|---|---|
| `sec/decide-once-log` @ `2ebb59d0` | SEC-08 executor half (owner-approved 17 Oct) | `app/operations/executor.py` (`_decide` only), `tests/operations/test_sec08_decided_in_log.py` | on `int/security-2`: operations 412, verifier 263, security 289, persistence 161, tests/api 1,729 passed / 2 skipped, mock e2e 444 / 61 skipped, typecheck, lint, unit; after merging `719c9dcf`: operations + guard tests 415 passed | **yes** |

Built 17 Oct on the integration owner's request, each from dev `719c9dcf`, one concern each, no engine change, merging cleanly into
dev `eee7ec70`:

| Branch @ head | Finding | Files | Tests | Ready |
|---|---|---|---|---|
| `sec/out1b-raw-operations` @ `f3392196` | OUT-1b (Low) | `app/api/operations.py` (`run_operation` applies `sent_outside_conflict` under `rt.lock`; `lang` passed through), `tests/security/test_out1b_raw_operations.py` | regression 8 (7 fail before); security 297, operations 406 (1 skipped), tests/api 1,729 passed / 2 skipped; mock e2e 444 / 61 skipped, typecheck, lint, unit | **yes** |
| `sec/offers-422` @ `3158c81c` | RT-2 (Low) | `app/api/offers.py` (`_docs`: 422 `DOCUMENT_INVALID` naming the fields, never the values), `tests/security/test_rt2_malformed_documents.py` | regression 8 (8 fail before); security 297, compiler 1,015 (1 skipped), tests/api 1,729 passed / 2 skipped; mock e2e 444 / 61 skipped, typecheck, lint, unit | **yes** |
| `sec/next-16-3-8` @ `ce7791bd` | RT-1 (Medium) | `apps/web/pnpm-lock.yaml` only: `next` 16.3.7 → 16.3.8 (pinned, not 16.4.2), `source-map-js` 1.2.1 → 1.2.2; `package.json` unchanged | fixes GHSA-cjq9-62q9-8jv4, GHSA-mcj8-r9mp-w47p, GHSA-4jqv-mc3x-m676, GHSA-f87g-xv8r-7p7x, GHSA-3w37-wq28-93x7, GHSA-39w2-rjm5-chcv (next) and GHSA-68fv-2mgg-jv7q (source-map-js); `pnpm audit --prod`: none left; frozen install passes; mock e2e 444 / 61 skipped, typecheck, lint, unit; production build in a browser: 15 pages, sign-in and chat with 0 CSP violations, injections blocked. Remaining in the full audit: `braces` ≤ 3.0.3 (high, no patch) via `eslint-config-next`, lint tooling only | **yes**; the integration owner runs the full mock and live suites before it lands |

## Round two, 16 Oct: five branches for `dev` (merged in `719c9dcf`)

Each branch was cut from `dev`, has the latest `dev` (`fe56b357`, the final UI and the R-10 rounding) merged in, holds one concern,
carries a regression test that fails before and passes after, and passed the full mock browser suite (docs/agents/integration.md rule 4).
None touches an engine module (`app/financial`, `verifier`, `funding`, `alerts`, `operations`, `clock`, `books`, `mandate`). None
depends on another; they touch different files except `app/main.py` (SEC-20 adds one middleware line). Test counts: first on `b07bb6a4`,
then again on `fe56b357` where marked.

| # | Branch @ head | Finding | Files | Tests |
|---|---|---|---|---|
| 1 | `sec/audit-integrity` @ `7a8daf16` | SEC-08 (persistence part) | `app/persistence/guards.py`, `sql_store.py` (reset), migration `0009_audit_guards.py`, `tests/persistence/test_audit_guards.py` | **on `fe56b357`:** persistence 162 incl. the PostgreSQL 17 guard case, concurrency 31 (10 on PostgreSQL 17, none skipped); on `b8c65b24`: operations 406, security 284, mock e2e 444 passed / 61 skipped, typecheck, lint, unit |
| 2 | `sec/rate-limits` @ `19c144f1` | SEC-20 | new `app/api/ratelimit.py`, `app/main.py` (one line), `app/api/runtime.py` (reset per runtime), `tests/security/test_rate_limits.py` | full API suite by directory, **on `b07bb6a4` and again on `fe56b357`**: every shard passes except the known #161 hash pin in `tests/books`; tests/api 1,721 passed, 2 skipped on `b07bb6a4`; 1,729 passed, 2 skipped on `fe56b357`; mock e2e 444 passed / 61 skipped, typecheck, lint, unit |
| 3 | `sec/egress-forms` @ `8f5f6923` | SEC-22 (number forms) | `app/egress/normalise.py`, `tests/egress/test_sec22_number_forms.py` | **on `fe56b357`:** egress + compiler 2,009 (1 skipped); on `b07bb6a4`: tests/api 1,721 passed, 2 skipped, egress + dev's `test_zh_money_units.py` 1,049, mock e2e 444 passed / 61 skipped, typecheck, lint, unit; earlier: egress 994 in 5 of 5 runs, nl 1,122, security 284 |
| 4 | `sec/nl-sessions` @ `8f57116b` | SEC-21 | `app/nl/sessions.py`, `app/nl/service.py` (principal), `tests/nl/test_session_binding.py` | **on `fe56b357`:** nl 1,144; on `b07bb6a4`: nl 1,144, security 284, compiler 966 (1 skipped); mock e2e 444 passed / 61 skipped, typecheck, lint, unit |
| 5 | `sec/csp` @ `26cec6da` | SEC-12 (full CSP) | new `apps/web/proxy.ts`, `apps/web/lib/csp.ts`, `app/layout.tsx` (nonce), `components/customer/overview.tsx` (one prop), `scripts/csp.test.mjs`, `package.json` (test:unit) | **on `fe56b357`: verified in the browser against a production build** (every page, the chat, two injection probes); mock e2e 444 passed / 61 skipped, typecheck, lint, unit (3 new) |

**What each one does, and its limits.**
- **SEC-08:** `approvals` decide once (PENDING to APPROVED or REJECTED, nothing else changes, no delete) and `security_events` is
  append-only, both as database triggers on SQLite and PostgreSQL; the PostgreSQL guard no longer has a session setting that lifts it
  (the reset lifts it with `ALTER TABLE … DISABLE TRIGGER`, which needs table ownership). Limits: whoever owns the tables can still
  drop the triggers; the chain has no external anchor; **the executor half is not built** (below).
- **SEC-20:** a token bucket per caller (owner, agent, bank feed: per credential and address; a buyer's key: per buyer; anyone else: per
  address), 429 `RATE_LIMITED` with `Retry-After`; limits per minute from the environment (`RATE_LIMIT_OWNER` 3000, `_AGENT` 1200,
  `_BANK` 600, `_BUYER` 120, `_ANON` 300; `RATE_LIMITS=0` turns them off). Limits: one process; behind a proxy every caller shares the
  proxy's address, so the proxy's per-client limit is still a condition for S-net; the anonymous intake cap is still one counter per
  simulated day (one sender can use it up for every anonymous buyer).
- **SEC-22:** the egress guard now also reads 30,0000 / ¥3,00,000 / 300.000 / 300'000 / 300_000 / 0.3m / 3e5 / 30w / 400千 / 15‰ /
  千分之十五 / 一点五个点 / 1.5 points / a ratio written as 125%; groupings are removed, every other reading is added beside the text,
  so nothing that matched before stops matching (14 leak cases fail before, 5 ordinary sentences still pass).
  Limit: **derived values** (break-even rate, counter cap, shortfall) are still outside the protected set; that needs the verifier
  to hand them to the guard (engine change, below). Still Low while outbound buyer text is templates only.
- **SEC-21:** a chat session continues only for the principal that opened it (owner, agent, `buyer:<id>` for a keyed buyer, anonymous);
  a different caller presenting the id gets a new session; eviction drops other callers' sessions before an owner's. Ids stay
  client-chosen (the binding makes guessing one useless).
- **SEC-12:** `Content-Security-Policy` per page request with a fresh nonce: `script-src 'self' 'nonce-…' 'strict-dynamic'` (no
  `'unsafe-inline'`/`'unsafe-eval'` in production), `object-src 'none'`, `base-uri 'none'`, `form-action 'self'`, `frame-ancestors
  'none'`, `connect-src` self and the API origin. Browser check: an injected `<img onerror>` and a `javascript:` URL are blocked;
  sign-in, Home, Deals, Cash, Approvals and the chat run with no violation. Limits: `style-src 'unsafe-inline'` (inline style
  attributes); under `'strict-dynamic'` an already trusted script can load others; HSTS belongs to the TLS proxy. Side effect: with a
  nonce per request every page renders on demand (none is prerendered). On `fe56b357` the gate found one consequence: the router's
  prefetch of the Customer page's "Stress-test payment" link (`/cash?stress=…`) was never read to its end, so a request stayed open
  (two responsive tests timed out waiting for the network to settle). That link is now not prefetched, as it already was on
  Receivables and the Deals queue (`components/customer/overview.tsx`, one prop); navigation is unchanged.

**Engine changes waiting for the owner's approval (not built).**
1. SEC-08, executor half (`app/operations/executor.py`, `Executor._decide`): right after the existing
   `if rec.status != ApprovalStatus.PENDING: raise ApprovalAlreadyDecided(...)`, also refuse with `ApprovalAlreadyDecided` when the
   operations log already holds the owner's decision for this `approval_id` (status EXECUTED or REFUSED under the operation's own
   idempotency key, not the `#decide:<actor>` attempts). Test: flip the row back to PENDING with the triggers dropped; approving must
   be 409 with nothing executed. Without it, someone who can drop the triggers can still turn a rejection into an execution.
2. SEC-22, derived values: the verifier passes break-even, counter cap and shortfall to the egress guard's protected set.

**After merging:** tell the Security Lead the merge commit; the Security Lead re-certifies it (OUT-1 still blocks certification of
`dev` until its fix is merged too).

## Open at the deadline (disclosed; owner's decision 16 Oct, not before the deadline)

SEC-11 (more than one process), SETUP-2, SETUP-3, SETUP-6, CAPEX-4b, R-2 (one owner credential and key), R-14 (no emergency write stop),
the capex cancel path, and SEC-06 (built only if the team deploys with Compose). Also open: SEC-19 (design), SEC-14, SEC-15, OUT-2 to
OUT-4, DEMO-L1, PRIV-1 to PRIV-5, and the two engine changes above if not approved. R-10: the owner chose rounding to the nearest
¥10,000 (`fix/counter-base-rounding`, in progress); the Security Lead reassesses R-10 when it lands.

## Round one, 14 Oct (merged; kept for the record)

For the integration owner (Fable). Every branch is cut from `e8e270f8`, holds one concern, carries a regression test that fails before
and passes after (shown below), and has not been merged anywhere. Merge with `--no-ff` in the order given; none depends on another.
After integration the Security Lead re-certifies the integrated commit (see `RELEASE_GATE.md`).

| # | Branch | Findings | Files | Shared financial semantics? | Ready |
|---|---|---|---|---|---|
| 1 | `sec/attack-harness` | SEC-01 | `app/security/attacks.py`, `tests/security/test_harness_payload.py`, `evals/security/latest_report.*` | no | **yes** |
| 2 | `sec/one-agreement-per-request` | SEC-02, SEC-03 | `app/operations/executor.py` (`_check_binding`), `app/api/accept.py`, `tests/operations/test_sec02_one_agreement.py` | **yes: a new executor invariant, needs your sign-off** | after your review |
| 3 | `sec/authority-boundaries` | SEC-04, SEC-05, SEC-09 | `app/api/accept.py` (decline key), `app/operations/executor.py` (circuit gate), `app/api/clock.py`, `tests/operations/test_sec_authority_boundaries.py` | **yes: circuit semantics; SEC-09 amends ADR-0006 §2** | after your review |
| 4 | `sec/intake-hardening` | SEC-16, SEC-17, SEC-18 | `app/api/offers.py`, `tests/security/test_intake_hardening.py` | no (intake only) | **yes: merge first** (anonymous exposure) |
| 6 | `sec/headers` | SEC-12 (partial), SEC-13 | `app/main.py`, `apps/web/next.config.mjs`, `tests/security/test_headers_and_docs.py` | no | yes for the API; **web: config verified to load, `next build` and e2e not run by the Security Lead** |
| 5 | `sec/security-event-growth` | SEC-10 | `app/api/auth.py`, `app/operations/executor.py` (`_add_security` id), id suffix in `alerts.py`, `documents.py`, `nl.py`, `offers.py`; `tests/security/test_security_event_growth.py` | no | **yes** |

Heads: `sec/attack-harness` eaf525b0, `sec/one-agreement-per-request` 8616ee31, `sec/authority-boundaries` 9127aef2,
`sec/intake-hardening` d4aebffe, `sec/security-event-growth` 0b1f6f4a. All five merge cleanly together onto `e8e270f8`
(`sec/candidate` e6863990; see "Gate run"). Suggested order: 4, 1, 5, 2, 3.

## 1. `sec/attack-harness` (SEC-01)

- Change: the harness drops `*_display` and `*_when` presentation keys before validating the server's payload against the strict models;
  any other unknown key still fails.
- Before: `tests/security` 129 errors, 2 failures on `e8e270f8`. After: all pass; `python -m app.security.attacks --report`: 126 API + 133
  NL attacks, 0 with harm (report committed).
- Regression: `tests/security/test_harness_payload.py` (2 of 3 fail before the fix with `extra_forbidden`).
- Merge note: conflicts only if someone else edits `_without_display`. Add `tests/security` to the lead gate; it was not run since 5 Oct.

## 2. `sec/one-agreement-per-request` (SEC-02, SEC-03)

- **Invariant proposed (please confirm or amend in `docs/INVARIANTS.md`):** a buyer request (`offer_id`) carries at most one ACCEPTED/ACTIVE
  commitment. A second one is refused `CONFLICTING_COMMITMENT` in `_check_binding`; the owner revokes the first to replace it.
  Question for you: is there any legitimate flow with two live agreements from one offer id (a revised agreement on the same request, a
  counter accepted after the as-asked terms)? None found in the tests (full-suite result below), but you own the model.
- Accept route: an earlier refused accept's PROPOSED commitment (same verdict, same obligations, unexpired, its accept never queued or ran)
  is reused instead of creating another per click.
- Regression: `tests/operations/test_sec02_one_agreement.py` (both fail before: second agreement EXECUTED; 2 orphan proposals).
- Conflicts: `executor.py` and `accept.py` are touched by the capex buy side and round three; the hunks are small.

## 3. `sec/authority-boundaries` (SEC-04, SEC-05, SEC-09)

- SEC-04: the owner's decline idempotency key gets a server-side random suffix; a second click is still `409 ALREADY_DECLINED` (the
  `_standing` check, unchanged).
- SEC-05: the owner's **AcceptOffer and RejectOffer** pass an open circuit (answering a buyer's request is the owner looking, which is
  what the circuit waits for); the owner's other circuit operations (AddFacility from a lender that tripped it) stay blocked until a
  reset, as `test_approvals_and_circuit.py` requires; the owner's own refused operations never count toward a circuit. Agent and
  counterparty operations are still stopped. (A first version exempted every owner operation; the full-suite run caught it: 9127aef2.)
- SEC-09: `POST /clock/advance` is owner-only. The bank-feed key keeps receipts (`/operations` as SYSTEM). No web or e2e caller uses the
  bank key for the clock (grep of `apps/web`, `services/api/tests`). **This amends ADR-0006 §2**; if you want the feed to keep a clock
  role, the alternative is one day per call plus an actor field in the log, which bounds the speed but not the total.
- Regression: `tests/operations/test_sec_authority_boundaries.py` (all 4 fail before).

## 4. `sec/intake-hardening` (SEC-16, SEC-17, SEC-18): **escalated; merge first**

- SEC-16: an anonymous caller could replace the stored text of any offer the owner reads; a different document under a taken `doc_id` is
  now 409 `DOCUMENT_ID_TAKEN` (identical resubmission still 200). SEC-17: at most 5 documents of 4,000 characters (413) before compiling.
  SEC-18: channel key bound on `/offers` (403 on mismatch); only the owner may use the `owner`/`term_sheet` channels (422).
- Client impact: none found. Fixtures are at most 247 characters and 2 documents; the web sends fixtures or chat-length text. If a client
  needs longer buyer documents, raise `MAX_DOCUMENT_CHARS` only together with a compile time budget.
- Regression: `tests/security/test_intake_hardening.py` (5 of 6 fail before; the oversized case takes about a minute before the fix).

## 5. `sec/security-event-growth` (SEC-10)

- Random ids at every security-event site (prefixes unchanged: Activity keys off `SEC-AUTH-`); no site reads the event table to make an
  id. A runtime records at most 300 refused credentials per wall-clock hour, then one event saying the rest are counted, not recorded.
- Regression: `tests/security/test_security_event_growth.py` (budget, no table read on refusal, 12 concurrent refusals → 12 ids).

## 6. `sec/headers` (SEC-12 partial, SEC-13)

- API: every response sends `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`,
  `Referrer-Policy: no-referrer`; `/docs`, `/redoc`, `/openapi.json` only with `DEMO_MODE` on. `/health` unchanged (the web reads its
  feature flags there).
- Web: the same frame, sniff and referrer headers plus `object-src 'none'; base-uri 'none'` via `headers()` in `next.config.mjs`.
  Not yet a full CSP: `script-src` needs the pre-hydration script's hash (`app/layout.tsx:22`) and `connect-src` the API origin, and that
  must be checked in a browser before it ships. Please run the web e2e on this branch before merging.
- Regression: `tests/security/test_headers_and_docs.py`.

## Residual after these branches

- SEC-03 covers refusals at execute time (circuit, screen). A Tier-2 accept refused later, at `decide`, still leaves its proposal: the
  accept key already holds a PENDING entry, so it cannot be reused. Harmless after SEC-02 (it can never become a second agreement) but it
  can raise a stale expiry alert. A proper fix is an executor "withdraw proposal" operation (logged). Fable's call.
- SEC-04: route-made accept keys (`accept-{commitment id}`) are not guessable (random nonce in the id), so not changed.

## Gate run

Sharded by test directory (31 shards; this repo's pytest config prints no totals, so exit codes are the evidence):
- **Baseline** `sec/attack-harness` (`e8e270f8` + harness): all shards exit 0 except `tests/books` (router-plan digest pin,
  `test_modules_on_books.py:207`) and `tests/deals` (`test_lang.py:77`, `/deals` and `/deals/BUYER-1`). Both pre-exist on `e8e270f8`
  (the handoff lists `test_lang`; the capex reviewer saw the digest pin on the base). Not security; not caused by these branches.
- **Candidate v1** (first SEC-05): same two plus `tests/operations` (`test_approvals_and_circuit.py:170` owner AddFacility, and the
  SEC-03 test relying on the circuit). Both corrected (9127aef2, 8616ee31).
- **Candidate v2** `sec/candidate` e6863990 (branches 1-5; `sec/headers` not included): all 31 shards exit 0 except the same two
  pre-existing failures (`test_modules_on_books.py:207`, `test_lang.py:77` ×2), identical to baseline. Attack catalogue on the same
  tree: 126 API + 133 NL attacks, 0 with harm, detection 98.4%. `sec/headers` was tested on its own (`tests/security`, startup).

## Not yet queued (fix design needs a decision, or is in progress)

| Finding | Proposed change | Decision needed from |
|---|---|---|
| SEC-07 `DEMO_MODE` default on | default off; dev scripts and tests opt in | Fable (touches every local script and test fixture) |
| SEC-06 compose cannot start | `OWNER_PUBLIC_KEY_HEX`, provisioning command, web build args | Fable / owner (deployment target) |
| SEC-08 audit integrity | approval decision bound to the log; DB triggers on approvals and security events; non-owner DB role; external head anchor | Fable (persistence) |
| R-11 agent key reads protected values via `/nl` | owner token for pure reads; no `verdict`/`plan` JSON to non-owner callers | Fable (what the agent channel is for) |
| R-10 threshold and funding-gap oracle for keyed buyers | coarse rate grid; counter face not sized to the gap; per-buyer attempt budget | Fable (pricing) |
| SEC-19 anonymous offers filed as a named buyer | `authenticated` flag on offers; label or exclude on Deals | Fable (Deals model) |
| SEC-20/21 throttling, NL session binding | token buckets; server-issued session ids bound to a credential | Security Lead can implement on request |
| SEC-10 remainder | 401 rate limit at the proxy; paginated `/audit` | Fable / deployment |
| SEC-11 multi-process | day from stored state inside the unit of work | Fable (only if more than one process is planned) |
| SEC-12/13 headers, public docs | `headers()` in next.config, docs off outside demo, terse `/health` | in progress (Security Lead) |
| Capex buy side (not on `dev`) | see register CAPEX-1..4: **do not merge** until CAPEX-1..3 are fixed and tested | branch owner |
