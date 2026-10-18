# Owner control, separation of duties, audit checkpoint, privacy trace

Branch `fix/control-audit-privacy` from `origin/int/final3` (2ce5265c), 18 Oct 2026. Paths are relative to `services/api/` unless they
start with `scripts/` or `docs/`. The engine stability set (app/{financial,verifier,funding,alerts,operations,clock,books,mandate,covenants},
app/domain/models.py) was not modified. `app/nl/service.py` and `app/api/decide.py` were not touched.

## 1. Owner control: stopping new financial writes and recovering control

### What existed before this branch

| Control | Where | What it does | Gap |
|---|---|---|---|
| Mandate revocation | `app/mandate/validity.py:47-58` (MANDATE_REVOKED), `app/mandate/signing.py:51-56` (`revoke`), enforced at `app/operations/executor.py:927-944` (`_check_mandate`) | a `revoked` mandate refuses every operation except owner/bank-feed receipts and owner repayments (`executor.py:931-942`) | **no route, script or console action revokes** (R-14). Outside demo mode the API does not hold the owner's private key, so an API revocation would be unsigned, and an unsigned revocation keeps `BAD_SIGNATURE`, which also blocks the bank-feed receipts. Undoing it needs a newly signed mandate, which also has no route. Tests write the store directly (`tests/api/test_accept_as_asked.py:397`). |
| Mandate expiry | `validity.py:35-46`; Home alert `app/alerts/engine.py:524-534` ("Renewal is an offline owner step") | after `expires_day` the agent can no longer act | renewal is offline; no route |
| Mandate renewal | only `POST /setup/open` (`app/api/setup.py:560-620`) on blank books, and the startup seed (`app/api/runtime.py`) | | no renewal route on open books |
| Owner token, agent key, buyer keys | `app/api/auth.py:37-80` (env `OWNER_TOKEN`, `AGENT_KEY`, `COUNTERPARTY_KEYS`) | constant-time checks; a refused credential is a security event (`auth.py:121-152`) | revoking a credential = change the env value and restart. No rotation without a restart, no per-key expiry. Removing a buyer from `COUNTERPARTY_KEYS` revokes that buyer's channel at the next restart. |
| Agreement revocation | `POST /commitments/{id}/revoke` (`app/api/operations.py:412-419`) | owner undoes one agreement's forward concession | per agreement only |
| Circuit breaker | `executor.py:675-684`, owner reset `operations.py:399-404` | 3 refusals in a window stop one counterparty | per counterparty, automatic, not an owner stop |

**Finding:** before this branch there was no way for the owner to stop the agent's new financial writes at once without editing the
database or the environment and restarting.

### What this branch adds: the owner's pause (API only)

`app/api/agent_pause.py` (new), wired at `app/api/runtime.py:71-78` and `app/main.py` (router). No change to the engine or the executor.

- `GET /agent/pause`, `POST /agent/pause`, `POST /agent/resume`: owner token only (`require_owner`, `agent_pause.py:41`). Route policy
  table updated (`tests/security/route_policy_support.py`, OWNER class and two PLAN entries).
- **State on the log, not in memory.** A pause appends one `PAUSE_AGENT` entry, a resume one `RESUME_AGENT` entry, to the hash-chained
  operations log (`agent_pause.py:112-125`). The state is the latest of the two (`pause_state`, `agent_pause.py:58-66`). So it survives a
  restart, needs no migration, every process on the same store sees it, and both switches are on the chain the evidence export verifies.
  A repeat pause or resume writes nothing (`changed: false`).
- **Enforcement at the one entry every typed operation takes.** `Runtime.executor` now returns `PausableExecutor`, a subclass of the
  executor that overrides only `execute` (`agent_pause.py:76-103`). While paused, an operation whose `requested_by` is `AGENT` or
  `COUNTERPARTY` is refused before the executor's gates: nothing is executed, queued for approval or booked, the answer is `REFUSED`,
  `INSUFFICIENT_AUTHORITY`, with the message "Refused: the owner has paused FLOW's agent; …", and a security event of kind `REVOKED`
  (`SEC-PAUSE-…`) records who asked for what. This covers the agent's tool channel (`POST /operations`), the agent's and a keyed buyer's
  chat (`POST /nl`), and the flows FLOW runs under the agent's authority after the owner clicks (acting on an alert, a chat funding plan,
  the capex draw), because they all reach `rt.executor.execute`. A new route cannot bypass it without bypassing the executor.
- **What still runs while paused:** operations the owner requests as `OWNER` (accept, decline, receipts, repayments, draws, deciding an
  approval already queued, revoking an agreement, documents) and bank-feed receipts (`SYSTEM`), which record money that already moved.
- **Refusal instead of queueing.** The coordinator's brief allowed either. Refusal was chosen: queueing would turn every paused agent
  attempt into an approval card the owner must clear, which is the opposite of a stop; and it would need `add_approval` outside the
  executor's own gate order. The owner can still do the thing as owner.
- **Not covered (stated):** `Executor.propose_commitment` (`app/nl/pipeline.py:150`) is not an `execute` call and has no actor; a PROPOSED
  agreement moves no money and binds nothing, and the `AcceptOffer`/`RecordCommitment` that would bind it is refused while paused.
  Refused attempts are not written to the operations log (so a pause cannot trip a buyer's circuit breaker or poison an idempotency key);
  they are security events. A demo reset (`POST /demo/reset`, demo mode only) empties the log and so clears a pause.
- **Web:** not surfaced. A toggle on the limits page is a follow-up (owner-only `POST /agent/pause` / `/agent/resume`, read state from
  `GET /agent/pause`). The web mock suite is unaffected: nothing changes unless the switch is used.

Tests: `tests/api/test_agent_pause.py`
- `:49` an agent draw is refused while paused (books, log and approvals unchanged; one `SEC-PAUSE` event), and runs after resume;
- `:69` the owner's own draw and a bank-feed receipt execute while paused; `GET /activity` still renders;
- `:80` a `COUNTERPARTY` operation is refused too;
- `:88` anonymous, agent and wrong-token callers get 401 on both switches; repeats write nothing; the chain still verifies;
- `:102` a new `Runtime` over the same store (a restart) still refuses.

**Residual risk.** The switch is only as strong as the owner token: whoever holds it can resume. Someone with database write access can
delete the pause entry (the chain then fails verification against a kept checkpoint, area 3). Mandate revoke and renew routes and key
rotation remain open (R-14 is narrowed, not closed).

**Wording for the technical document and the security assessment.**
> The owner can pause FLOW's agent at any time (`POST /agent/pause`, owner token). While paused, every operation requested on the agent's
> or a buyer's authority is refused before it reaches the executor's gates, and each refusal is recorded as a security event; the owner's
> own operations and bank-feed receipts still run. The pause and the resume are entries on the hash-chained operations log, so the
> switch survives a restart. It does not revoke or replace the mandate: mandate revocation and renewal remain offline owner steps
> (R-14, narrowed). The pause is API-only in this build.

Replace in `docs/SECURITY_SELF_ASSESSMENT.md`: line 38 ("The owner has no route to revoke or renew the mandate (R-14)") with "The owner
can pause the agent (`POST /agent/pause`) but has no route to revoke or renew the mandate (R-14, narrowed)"; the Owner row at line 108 gains
"pause and resume the agent"; line 878 next step becomes "owner-only signed-mandate and revoke routes (the write switch is done:
`/agent/pause`)"; line 1011 item 4 likewise.

## 2. Separation of duties: the supported single-operator model

FLOW is a single-operator SME tool. No second approver was added.

| Who | Approves / does | Can never |
|---|---|---|
| Owner (one person, `X-Owner-Token`; the mandate is signed offline with the owner's Ed25519 key, public key pinned at start-up, `runtime.py _owner_key_hex`) | signs the mandate (offline); decides every Tier-2 item; adds facilities; accepts and declines buyer requests; records receipts; revokes agreements; resets circuits; pauses and resumes the agent; moves the simulated clock | execute a Tier-3 operation (`app/mandate/tiers.py:_ALWAYS_TIER3`: personal guarantee, collateral pledge, equity issue, mandate change) through FLOW; it is refused for everyone |
| Agent (`X-Agent-Key`) | Tier 1 inside the signed mandate: counter, accept or record within caps, draw or repay a committed, owner-approved facility, submit an invoice for financing | Tier 2 without the owner (queued: new facility applications, purchases, contract set-up, commitments above `tier2_single_commitment_fen`, terms extensions, receipts it reports); Tier 3 ever; decide an approval (`executor.py:360-372`); edit or renew the mandate; act while the mandate is expired, revoked or replaced, or while the owner has paused it |
| Buyer (keyed channel) | send offers and messages; its identity comes from the key, never the body | read the owner's verdicts, plans or limits (`app/api/nl.py _counterparty_view`); execute anything outside Tier 1 |
| Bank feed (`X-Bank-Feed-Key`) | record receipts as SYSTEM (facts) | anything else |

Tiers are computed from the typed operation by code (`app/mandate/tiers.py`), never from a caller-supplied field.

**Residual risk of one owner credential.** Whoever holds the owner token is the owner for every API purpose: they can approve every Tier-2
item, accept any buyer request, resume a paused agent and revoke agreements. The token is a static secret in the environment, with no
expiry, no rotation without a restart and no second factor. The mandate signing key is separate and offline (outside demo mode), so a stolen
token cannot widen the mandate's limits, and Tier 3 stays refused. In `POST /offers/{id}/accept` the owner queues and approves in one
request (`app/api/accept.py`, register R-2): there is no second pair of eyes by design.

**Where a second approver would add value (future work, not built).** Tier-2 items above a threshold (for example a new facility or a
purchase above a set share of cash, or a commitment above the per-buyer cap); resuming the agent after a pause triggered by a security
event; any mandate change. Either a second person's token with a two-step approve, or the owner's hardware key signing the approval.

**Wording.**
> FLOW supports one operator. The owner signs the mandate offline and decides every Tier-2 item; the agent acts only inside that mandate
> at Tier 1 and can never decide an approval, change the mandate or run a Tier-3 operation. One owner credential is a single point of
> compromise for everything inside the signed limits; it cannot widen them. A second approver above a threshold is future work.

## 3. Audit integrity: a manual checkpoint kept outside the database

### What existed

`scripts/verify_evidence.py` recomputed every link, checked the readable fields and the chain line's count, and had `--checkpoint-out`
(prints `COUNT:HEAD`) and `--checkpoint COUNT:HEAD` (the file must hold at least COUNT entries and entry COUNT must have that hash), with
tests for a consistent cut and a consistent rewrite (`tests/security/test_evidence_verifier.py:96`). EV-1, fixed 17 Oct.

### What this branch adds

- `--checkpoint-save FILE` (`scripts/verify_evidence.py:160-182, 210-214`): on a valid export, writes a JSON checkpoint: `count`, `head`,
  `last_entry_day` (simulated day of the last entry), `export_simulated_day` and `export_recorded_at` (from the export's run header),
  `export_sha256`, `saved_at` (UTC), and a note to keep it elsewhere.
- `--checkpoint` accepts that file as well as `COUNT:HEAD` (`parse_checkpoint`, `:136-150`); a malformed value or a file of another format
  exits 2; a passing check prints how many entries were appended since.
- Owner procedure: `GET /evidence` (owner token) → `python scripts/verify_evidence.py export.jsonl --checkpoint-save cp.json` → copy
  `cp.json` somewhere the database administrator cannot write (another machine, a USB key, an email to oneself). Later:
  `python scripts/verify_evidence.py later.jsonl --checkpoint cp.json`.

Tests (`tests/security/test_evidence_verifier.py`): `:120` saved file holds count, head and day; one entry appended after it is accepted
("1 entries appended since"); a rewrite before it with every link recomputed verifies on its own but is refused against the checkpoint
("history rewritten"); an older consistent export one entry short is refused ("fewer than the … checkpointed"). `:161` a checkpoint with
the right count and the wrong head is refused; malformed checkpoints exit 2.

**What a database or checkpoint administrator can still do.** Anyone with database write access can rewrite or cut the log consistently;
it is caught only against a checkpoint taken before the change and kept where they cannot write. Changes after the latest checkpoint are
not caught until the next checkpoint is compared (the window is the checkpoint interval). Whoever can edit both the database and the kept
checkpoint can make a rewrite verify. The checkpoint file is not signed. The security events and the approvals table are not in the chain
(they are append-only by database guard since SEC-08, but a database owner can lift that). Checkpoints are manual: nothing publishes them.

**Wording.**
> The operations log is hash-chained. The owner can save a manual checkpoint of the chain head (entry count, head hash, day) with
> `scripts/verify_evidence.py --checkpoint-save` and keep it outside the database; a later export verified against it shows any
> truncation, rollback or rewrite of entries up to that point, and accepts entries appended after it. This is tamper evidence, not
> tamper-proofing: an administrator who can also change the kept checkpoint, or who changes the log after the latest checkpoint, is not
> detected by it. Checkpoints are manual; there is no external anchoring service.

## 4. Privacy trace: what leaves the process in live mode

Default `LLM_MODE=cache`: no model provider is called; recorded readings, then the rules grammar. Everything below is `LLM_MODE=live`.

| Path | Entry (who reaches it) | What is sent | Redaction | Logged |
|---|---|---|---|---|
| Offer / buyer message | `compile_offer` (`app/compiler/service.py:154`), from `POST /offers` (`app/api/offers.py:173`), a buyer's `POST /nl` turn (`app/nl/offers.py:109`), outbound replies (`app/api/outbound.py:623`) | fixed system prompt + output schema; the documents rendered as `<documents>` with `doc_id`, `channel`, `filename`, `attachment_of` attributes and the text (`app/compiler/prompts/__init__.py:159-194`) | provider backends redact their own input by default (`app/compiler/backends.py:64-82`, `call_redacted` `redaction.py:278-287`); text only, not the attributes | `compiler.call` (backend, model, outcome, error **type name**, prompt version, `doc_hash`, latency) `service.py:97-104`; `model.redaction` counts per kind `redaction.py:269-272`; `compiler.cross_check` agree/disagree |
| Contract | `compile_contract` (`service.py:135-149`), from `app/contracts/records.py:45` (POST /documents, setup) | same, one chunk per call | same | same |
| Term sheet / lender agreement | `compile_term_sheet`, from `offers.py:249`, `records.py:53` | same | same | same |
| Intent classifier | `classifier.classify` (`app/nl/classifier.py:196-215`), from `app/nl/service.py:294` for an owner or agent chat turn that no rule parsed | fixed system prompt + schema; the message | `CallableBackend.classify` `classifier.py:136-150` | counts; rejections carry `"<backend> call failed: <ErrorType>"` only |
| Question router | `route_outcome` (`app/nl/router/route.py:405-476`), from `app/nl/ask.py:413`; owner turns only (`route.py:427-430`) | fixed system prompt + tool catalogue; the question between markers with the reply language; no books, no figures (`build_prompt` takes no context) | `route.py:434` | `ask.router`: question **hash**, backend, model, tool names, outcome, latency; a rejection as a fixed code; a backend error as `"<name> call failed: <ErrorType>"` truncated |

**Redacted (pattern-based, `app/compiler/redaction.py:41-97`).** Bank account and card numbers (labelled, or 16-19 bare digits), phone
numbers (labelled, Chinese mobiles, 0755-style landlines, +country), email addresses, the 18-character unified social credit code,
national ID and passport numbers (labelled, or an 18-character 身份证 number with a valid birth date), and a street address only where a
label says so (住所/地址/Address:, "registered address at"). Each distinct value becomes a stable placeholder per call; quotes are mapped
back to the original before grounding, so stored spans refer to the original.

**Not redacted, by design (FLOW reads them):** company and party names, amounts, dates, percentages, rates, contract and invoice numbers,
the clauses. **Not redacted, not by design (found while tracing):** personal names (a contact or legal representative), WeChat and other
handles, an unlabelled address, the document `filename` attribute (`prompts/__init__.py:164-165`), and the trailing short group of an
unlabelled card number written as "6222 0212 3456 7890 123" (the last "123" stays; a labelled 卡号/Account No. is redacted whole). It is
pattern matching: an identifier in a shape the patterns do not cover goes as written.

**Exceptional paths.** Provider SDK errors become `BackendError`/`ClassifierError`/`RouterError` carrying only the exception type
(`backends.py:109-140, 202-258`, `classifier.py:142-145`, `route.py:196-259`); nothing logs the request text on failure. Retries resend the
same redacted text (Claude SDK `max_retries=2`; DeepSeek up to 3 attempts, one with a larger budget). Fallback from one provider to the next
re-redacts from the original (each backend redacts its own input); the rules grammar and the cache read the original **inside the process**.
The cross-check reads the original inside the process. Nothing is sent to a provider in cache mode.

**Switches.**
- `LLM_REDACT=0` (env or `.env`) sends the original text on every path (`app/config.py:99`; `backends.py:73-79`; `classifier.py:128-130`;
  `route.py:434`). It is the only switch that does. Tested: `tests/security/test_model_privacy_paths.py:134`,
  `tests/compiler/test_redaction_mandatory.py:72`, `tests/compiler/test_redaction.py:411`.
- `LLM_LIVE_RAW=1` turns off the recorded-reading lookup and the rules cross-check in live mode; it does **not** turn off redaction
  (`service.py:69, 83`). `scripts/evaluate.py --live` sets it by default.
- **There is no `--live-llm` flag in this repository.** The live flags that exist (`scripts/evaluate.py --live`,
  `scripts/certify_language_boundary.py --backend live`, `services/api/scripts/eval_contracts.py --live`,
  `services/api/scripts/record_router_cache.py --live`) honour `LLM_REDACT` (on by default) and do **not** force it: with `LLM_REDACT=0`
  in the environment or `.env` they send original text. Not changed here (P2, recorded in the decision log): forcing it would change
  what the evaluation harnesses measure.

**Tests.** New: `tests/security/test_model_privacy_paths.py` runs all five paths in `LLM_MODE=live` with the product's default chains and
both SDK constructors (`anthropic.Anthropic`, `openai.OpenAI`) replaced by a recorder; every request and retry holds none of the six
identifiers and still holds the party name, amount, invoice number and rate; no structlog or stdlib log line holds an identifier, including
when the provider error itself quotes the original text. Existing: `tests/compiler/test_redaction.py` (patterns, mapping, counts-only log
`:385`, classifier `:398, :411`), `tests/compiler/test_redaction_mandatory.py` (PRIV-1..3), `tests/nl/test_ask_router.py:319` (router).

**Wording.**
> In live mode FLOW sends a model provider only the document text, chat message or question being read, with a fixed prompt. Before it
> leaves the process, pattern-based redaction replaces bank account and card numbers, phone numbers, email addresses, unified social
> credit codes, ID and passport numbers, and labelled street addresses with placeholders. Company names, amounts, dates, rates and invoice
> numbers are sent, because FLOW reads them; personal names, unlabelled addresses and document filenames are not redacted. Logs hold
> hashes, counts and error types, never the text. Redaction is pattern matching, not anonymisation, and is not a claim of compliance with
> any data-protection law. It is on by default; `LLM_REDACT=0` turns it off. The demo and CI run in cache mode and call no provider.

## Tests run

See the decision log and the final report for the exact suites and counts.
