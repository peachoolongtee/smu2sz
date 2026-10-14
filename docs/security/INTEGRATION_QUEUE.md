# Security integration queue

For the integration owner (Fable). Every branch is cut from `e8e270f8`, holds one concern, carries a regression test that fails before
and passes after (shown below), and has not been merged anywhere. Merge with `--no-ff` in the order given; none depends on another.
After integration the Security Lead re-certifies the integrated commit (see `RELEASE_GATE.md`).

| # | Branch | Findings | Files | Shared financial semantics? | Ready |
|---|---|---|---|---|---|
| 1 | `sec/attack-harness` | SEC-01 | `app/security/attacks.py`, `tests/security/test_harness_payload.py`, `evals/security/latest_report.*` | no | **yes** |
| 2 | `sec/one-agreement-per-request` | SEC-02, SEC-03 | `app/operations/executor.py` (`_check_binding`), `app/api/accept.py`, `tests/operations/test_sec02_one_agreement.py` | **yes: a new executor invariant, needs your sign-off** | after your review |
| 3 | `sec/authority-boundaries` | SEC-04, SEC-05, SEC-09 | `app/api/accept.py` (decline key), `app/operations/executor.py` (circuit gate), `app/api/clock.py`, `tests/operations/test_sec_authority_boundaries.py` | **yes: circuit semantics; SEC-09 amends ADR-0006 §2** | after your review |
| 4 | `sec/intake-hardening` | SEC-16, SEC-17, SEC-18 | `app/api/offers.py`, `tests/security/test_intake_hardening.py` | no (intake only) | **yes: merge first** (anonymous exposure) |

Commits: `sec/attack-harness` eaf525b0, `sec/one-agreement-per-request` b2768fd8, `sec/authority-boundaries` cd000f26,
`sec/intake-hardening` d4aebffe. All four merge cleanly together onto `e8e270f8` (`sec/candidate`, see the gate run below).

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
- SEC-05: the circuit no longer gates operations `requested_by == OWNER`, and the owner's own refused operations no longer count toward
  it. Agent and counterparty operations are still stopped (test asserts `CIRCUIT_OPEN` for the agent).
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
| SEC-10 security-event growth | uuid ids, aggregated refusal counters, 401 rate limit, paginated `/audit` | in progress (Security Lead) |
| SEC-11 multi-process | day from stored state inside the unit of work | Fable (only if more than one process is planned) |
| SEC-12/13 headers, public docs | `headers()` in next.config, docs off outside demo, terse `/health` | in progress (Security Lead) |
| Capex buy side (not on `dev`) | see register CAPEX-1..4: **do not merge** until CAPEX-1..3 are fixed and tested | branch owner |
