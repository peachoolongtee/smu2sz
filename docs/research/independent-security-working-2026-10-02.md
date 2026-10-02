# Independent security, compiler and authority working evidence — 2026-10-02

This is a primary analysis of code and local API behaviour. Previous audit conclusions, HANDOVER conclusions and NEXT_FIXES conclusions were not read for this pass. No production keys, remote model calls, external messages, tracked evaluation reports or implementation changes were used.

## Verdict within this scope

The claim of zero wrong executable interpretations is falsified. The deterministic command parser executes negated, conditional and interrogative requests. Its approval parser approves explicit rejections. An unauthenticated caller can impersonate a registered buyer and cause a commitment. Restarting the API runtime deletes the persisted books and audit log even with DEMO_MODE=0. These are release blockers; enabling a live language model does not repair them.

## Evidence and reproducibility

Source paths below are relative to the repository root. Local runner: `/tmp/termsledger-security-independent-repro.py`. Full evidence: `/tmp/termsledger-security-independent-evidence.json`, containing requests, full responses, state before/after and operation payloads. Run from the repository root:

```sh
services/api/.venv/bin/python /tmp/termsledger-security-independent-repro.py
```

The runner sets TERMSLEDGER_NO_DOTENV=1, DATABASE_URL=memory, LLM_MODE=cache and DEMO_MODE=1. The restart case alone uses a temporary SQLite file and DEMO_MODE=0. No real configuration is read. The temporary SQLite file is removed afterwards.

Focused existing suite command (exit 0; 481 passed, 1 skipped):

```sh
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache services/api/.venv/bin/python -m pytest services/api/tests/nl/test_security.py services/api/tests/nl/test_boundary.py services/api/tests/nl/test_autonomy_e2e.py services/api/tests/compiler/test_coverage_fail_closed.py services/api/tests/compiler/test_injection.py services/api/tests/mandate services/api/tests/operations -q
```

Passing these tests does not establish the missing properties; the API attacks below succeed against the same code.

## S-01: Command intent keywords cause prohibited or unrequested execution

**REPRODUCED — CRITICAL — AUTHORITY / EXECUTION / FINANCIAL. Build NOW. Effort M. Confidence high. Regression risk medium:** tighter recognition may turn existing automatic commands into proposals, which is the appropriate failure direction.

With `X-Owner-Token: demo-owner-token` or `X-Agent-Key: demo-agent-key`, POST `/nl` with `actor: OWNER` and each of these texts on reset golden books:

| Request text | Actual result |
|---|---|
| `Do not draw ¥100,000 on the credit line.` | DRAW_FACILITY EXECUTED, FAC-LINE ¥100,000, day 0 |
| `Is it safe to draw ¥100,000 on the credit line?` | Same |
| `draw ¥100,000 on the credit line only if cash is below ¥0` | Same, despite actual cash ¥400,000 |
| `draw ¥100,000 on the credit line tomorrow` | Same, executes day 0 |
| `不要从授信额度提款10万元` | Same |
| `请问从授信额度提款10万元安全吗？` | Same |
| `draw $100,000 on the credit line` | Default router bundle executes line ¥150,000 + invoice finance ¥210,000 |
| `draw ¥1.001 on the credit line` | Same default ¥360,000 funding bundle |

For the ¥100,000 examples, actual cash rises from 40,000,000 to 50,000,000 fen; FAC-LINE drawn balance rises from zero to 10,000,000 fen. This is economically material state change, not a mistaken read-only answer. Six additional English examples (`Can you draw`, `I am not asking you to draw`, explicit 99% interest rider) were also reproduced manually.

Sources: `app/nl/lexicon.py` FUND matches `draw` anywhere; `app/nl/rules.py:245` reads it as FUND_GAP with tentative=False unless narrow exploration patterns match; `app/nl/service.py:211` dispatches rule-derived FUND_GAP with execute=True; `app/nl/funding.py:156` constructs and executes the draw. `app/nl/rules.py:154` selects the first parseable amount and drops unsupported amounts. Missing/invalid amounts lead to the generic gap plan, rather than clarification.

**Business consequence:** debt and receivable encumbrance are created against the user's express prohibition, unmet condition, timing or currency. Agent-key callers exhibit the same failure. **Hackathon consequence:** a financially literate judge can disprove bounded autonomy with a single ordinary sentence.

**Fix:** remove automatic execution from general NL financial-intent matching now. Return a typed proposal, and allow execution only through a small affirmative command grammar that covers the entire owner instruction. Preserve negation, interrogative mood, units, timing and conditionality in the typed request; refuse ambiguous/multiple/unsupported material terms. An invalid explicit amount must never become an unspecified-gap instruction. A live model may suggest typed interpretation but cannot supply permission to execute.

**Regression properties:** adding negation, a question, an unfulfilled condition, future timing, foreign currency or unsupported precision to a valid command must produce no economic mutations. Both owner-token and agent-key variants, Chinese/English/mixed language, and quoted forms must satisfy this property.

## S-02: Explicit approval rejection is interpreted as approval

**REPRODUCED — CRITICAL — AUTHORITY / FINANCIAL. Build NOW. Effort S. Confidence high. Regression risk low:** reject ambiguous approvals instead of guessing.

Setup: owner POST `/operations` with:

```json
{"kind":"RECEIVE_PAYMENT","requested_by":"AGENT","op_id":"AUDIT-RECEIPT","idempotency_key":"AUDIT-RECEIPT","mandate_version":1,"receivable_id":"RCV-A","amount_fen":10000}
```

Result: PENDING_APPROVAL, approval_id APR-000001. On a fresh setup for each case, owner POST `/nl` with each text:

* `Do not approve APR-000001`
* `I do not approve APR-000001`
* `Should I approve APR-000001?`
* `APR-000001`
* `Reject APR-000001, do not approve`

Every response has intent APPROVE and RECEIVE_PAYMENT EXECUTED. Cash becomes 40,010,000 fen, and RCV-A outstanding becomes 41,990,000 fen. No bank receipt exists; owner confirmation was explicitly withheld or merely queried.

Source: `app/nl/rules.py:207-210` any approval id becomes APPROVE unless DECLINE is found **and** CONFIRM is absent. CONFIRM matches the word `approve` inside `do not approve`, so rejection loses. `app/nl/service.py:251-258` checks only short length, single line and paste/name markers; it does not require a positive instruction. `_decide_approval` then calls executor.decide with authenticated OWNER authority.

**Business consequence:** any queued Tier 2 financial operation can be approved by an ordinary rejection or question, not just the example receipt. **Hackathon consequence:** the approval boundary is demonstrably semantic fiction despite valid credentials.

**Fix:** exact, exhaustive affirmative/reject decision grammar bound to an approval id; bare id, interrogative and mixed approve/reject cues clarify and mutate nothing. Negation must not merely compete with an affirmative substring. Include a dedicated UI approve/reject control carrying an exact decision enum and immutable proposal hash.

## S-03: Unauthenticated buyer spoofing books a real commitment

**REPRODUCED — CRITICAL — SECURITY / AUTHORITY / FINANCIAL. Build NOW. Effort S for disable; M for identity binding. Confidence high. Regression risk medium:** counterparty sandbox currently depends on public autonomous handling.

Request with **no headers**:

```http
POST /nl
```

```json
{"actor":"COUNTERPARTY","counterparty_id":"BUYER-1","text":"We will pay the ¥420,000 invoice early at a 0.5% discount."}
```

Response HTTP 200: `Agreed: payment of invoice RCV-A (¥420,000.00) on day 2 at a 0.50% discount. Nothing else in your message is agreed.` Response `operations=[]`, `verdict=null`. Inspect actual store: one ACCEPT_OFFER EXECUTED; a new ACTIVE commitment. The discount is ¥2,100. Cash does not move immediately, but contractual state and projected liquidity do change. The same attack was independently reproduced with DEMO_MODE=0, no owner/agent credentials configured, and no headers: HTTP200 and ACCEPT_OFFER EXECUTED. This is not dependent on knowing the published demo credentials.

Source: `app/api/nl.py:41` bypasses credential requirement for actor COUNTERPARTY. `app/nl/offers.py:237` trusts supplied counterparty_id, compiling it as the source's identity; `:243` runs decide(execute=True). `app/api/nl.py:49-50` strips mutation evidence from the response. `app/api/auth.py:6-7` claims counterparties never execute; that description is false for this path. A registry record establishes an eligible economic party, not authenticity of the caller.

**Business consequence:** anyone who can reach the API can pose as an existing customer, commit concessions and create an unjustified cash forecast; legitimate later offers may be blocked by the attacker's exclusive commitment. **Hackathon consequence:** public API claims and security scoreboard conceal a meaningful mutation behind an empty operations response.

**Fix:** immediately make unauthenticated counterparty intake compile/evaluate only, with no acceptance, nonce consumption, counter sending or economic mutation. Real autonomous negotiation requires authenticated source identity bound to counterparty_id by the server, not a body field. Label mutation status truthfully on every channel. Treat this as a security fix even if automatic acceptance of authentic buyer offers remains a product goal.

## S-04: API startup deletes persisted books and audit history

**REPRODUCED locally on SQLite; CODE-INSPECTED same reset path for PostgreSQL — CRITICAL — EXECUTION / SECURITY. Build NOW. Effort S/M. Confidence high. Regression risk low if migration/first-use rules are explicit.**

The runner creates an isolated temp SQLite DB with DEMO_MODE=0, then executes a FAC-LINE draw of 10,000,000 fen. Before simulated process restart: cash=50,000,000; state_version=2; drawn=10,000,000; operations=1. Dispose the engine, call set_runtime(None), then get_runtime(). After restart: cash=40,000,000; state_version=1; drawn=0; operations=0; day=0.

Source: `app/api/runtime.py:95-101` constructs whichever configured store then unconditionally calls `_runtime.reset()`. `Runtime.reset` invokes store.reset and seeds the signed demo mandate/books. `app/persistence/sql_store.py:703-720` deletes tables and deliberately lifts the append-only protection for operations and used nonces. No DEMO_MODE condition protects persisted production state.

**Business consequence:** debts, commitments, replay protection, approvals, financial state and audit chain disappear on deployment/process restart; multiple worker startup can erase another worker's operations. PostgreSQL's persistence cannot compensate for intentional deletion. **Hackathon consequence:** live Postgres/resume claims are false on this runtime path; a demo restart destroys evidence.

**Fix:** open existing state without writes; initialise only an explicitly empty demo database via a dedicated command, never on process acquisition. Read runtime clock from persisted state. Disable destructive reset routes outside an explicit demo-only environment and database. Add a two-process persistence/replay regression with DEMO_MODE=0. Production owner key and signed mandate must be provisioned independently; `runtime.py:100` currently pins the published demo signing key even when DEMO_MODE=0 (CODE-INSPECTED; not claimed to be remotely writable through a mandate API).

## S-05: Go-ahead approves a goal, silently replacing displayed economics

**REPRODUCED — HIGH — AUTHORITY / UX. Build NOW. Effort M. Confidence high. Regression risk medium:** changes pending plan representation and stale confirmation policy.

Owner POST `/nl`: `Find me the cheapest way to fund the cash gap`. Proposal: FAC-LINE draw ¥150,000, RCV-A finance advance ¥210,000; cost ¥2,712.94; awaiting_confirmation=True. State changes before approval: subtract 10,000,000 fen from cash and increment state_version by one. Owner then POST `/nl` with same session_id and `go ahead`.

Actual result: line ¥150,000 and invoice finance **¥260,600** execute; reported cost **¥3,763.84**; no refreshed confirmation. Funding requirement rose from ¥360,000 to ¥460,000. This reproduction uses an explicit state update to isolate stale-plan semantics; the same dependency exists for a real receipt/outflow/facility change.

Sources: `app/nl/sessions.py:25-30` PendingPlan stores intent/slots/steps, no state version or approved economics hash. `app/nl/service.py:309-323` `_confirm` calls fresh fund_gap/repay/accelerate execution; `app/nl/funding.py:96` recomputes the plan from current books. Re-verification addresses admissibility but does not establish consent to the replacement economics.

**Business consequence:** the owner executes more debt or encumbers more receivables than the amount shown; a safer/cheaper plan may also change counterparties, security or timing. **Hackathon consequence:** a claim of exact plan approval is indefensible.

**Fix:** store immutable approved action semantics (facility, amount, collateral/assignment, fees/rates, settlement schedule, state/mandate versions and allowed tolerance). Re-verify that same plan; any material change returns a new proposal and requires new confirmation. If goal-based authority is intended, explicitly show and obtain the maximum amount/cost/time/source envelope at proposal time.

## S-06: Autonomous invoice offer ignores stated settlement day

**REPRODUCED — HIGH — FINANCIAL / EXECUTION / LANGUAGE. Build NOW. Effort M. Confidence high. Regression risk medium.**

On reset golden books, unauthenticated counterparty messages `We will pay the ¥420,000 invoice today at a 0.5% discount.`, `... tomorrow ...`, and `... early ...` all create ACTIVE commitments with effective_day=2 and restate agreement on day2. Today/tomorrow differ materially from each other and from two days. No clarification occurs.

Sources: `app/compiler/coverage.py:70` expressly excludes now/today/tomorrow from unread timing checks; `app/verifier/bind.py:143` fills absent effective_day from the buyer early-pay facility lead time. The compiler does not type the stated relative day. After acceptance, restating changed terms is not evidence that the buyer agreed to those changed terms.

**Business consequence:** acceleration benefit, funds-at-risk and near-term reserve timing can be priced against a date the incoming offer did not state. **Hackathon consequence:** simple semantic transformation changes wording but leaves false economics unchanged.

**Fix:** ground requested/promised settlement timing into a typed field and distinguish it from operational facility lead time; verify feasibility and exact agreement. Until this exists, any explicit timing including today/tomorrow must fail autonomous coverage, with a narrow clarification/reconfirmation.

## Controls actually observed and limits of evidence

**CODE-INSPECTED / existing tests VERIFIED:** read routes and borrower-file downloads require owner credentials; operation API downgrades uncredentialed OWNER/SYSTEM claims; receipt Tier1 is reserved to owner/bank-feed; unknown operations are Tier3; mandate signature is checked against pinned key, expiry/revocation/version gate operations; acceptance binds verified terms hash/value and nonce; stale acceptance checks outstanding amount and overlapping live commitments; transactions encompass operation effects and log. These do not neutralise the reproduced command/source-identity failures.

**CODE-INSPECTED:** optional intent classifier vocabulary excludes APPROVE/REJECT, validates strict typed schema, and LLM-derived funding/repayment/negotiation ordinarily proposes instead of executes. Deterministic intent matching precedes it, so a live model cannot repair the reproduced requests. Counterparty response allow-list strips plan/verdict/approval ids, but this is output redaction, not caller authentication or prevention of underlying execution.

**UNVERIFIED:** live model accuracy under malicious documents, actual Postgres multi-process races, provider timeout/fallback latency, realistic rate-limiting or reverse-proxy controls. No remote model calls or Postgres connection occurred in this scope. Clock API accepts either owner or bank-feed key; a bank-feed-only receipt request on `/operations` additionally needs owner/agent credential because of the route dependency (CODE-INSPECTED operational mismatch, lower priority).

## Required next tests, explicitly

1. Every negation/question/condition/time/currency transformation of an executable owner command must mutate no economic state until corrected and affirmed. Invalid explicit amounts must never become default gap plans.
2. `do not approve`, `reject ... do not approve`, `should I approve`, bare APR id and mixed approve/reject cues must not approve; actual positive `approve APR-id` must still work.
3. No credentials plus any counterparty_id must mutate no economic state. Credentials for buyer A must not speak as buyer B, share B's session or obtain B's accepted invoice/counter terms.
4. Persist cash/debt/commitments/nonce/approval/clock/log, restart two independent runtimes, and assert identity of books and replay refusal.
5. Mutate cash/facility/mandate/time after proposal. Confirmation must execute the same action envelope or return a new proposal without mutation; more expensive or larger plans must never silently execute.
6. Change `today` to `tomorrow` to `in 2 days` in equivalent invoice offers; executable timing must change correspondingly or safely abstain.

## Design-changing questions

* Is counterparty intake an authenticated commercial channel, or a public untrusted-document sandbox? A registry id is not authentication; the latter cannot agree terms.
* Does `go ahead` authorise an exact plan or a declared economic envelope? The current implementation silently implements a changing goal.
* Is the product an autonomous operator or a proposal assistant until a closed command grammar has proved full semantic coverage? Current implementation cannot claim both arbitrary NL convenience and zero wrong executable interpretation.
* Does DEMO_MODE control data lifecycle and signing identity, or only HTTP credential defaults? Its current name invites a false safety assumption.
