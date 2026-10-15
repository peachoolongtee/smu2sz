# Negotiation communication: handoff for an independent evaluation session

Written 15 Oct 2026 by the technical lead (integration owner), for a fresh session that will **evaluate and design** an
end-to-end buyer communication capability. Your first task is evaluation and architecture, not implementation.

**How this was made.** I read origin/dev at **833d3050** (`833d3050ad59dd02c3c7a8b5e428efec776de8b1`), with two read-only inventories
of the code and spot checks of the key claims. I ran no tests to write it. Paths are relative to the repository root. File:line
references are to 833d3050 and will drift. **UNKNOWN** means not verified in the time-box; the investigation path follows it.

Read this with:
- `docs/SYSTEM_WALKTHROUGH.md` (actors, the buyer channel key at `:70`, egress at `:202`);
- `docs/ARCHITECTURE.md` (outbound template text, `:119`);
- `docs/INVARIANTS.md` (invariant 7: privacy between counterparties);
- `docs/FINANCIAL_SEMANTICS.md`, `CONTEXT.md` (glossary);
- `docs/adr/0005`, `0006`, `0009`, `0011` (see section 11);
- `docs/research/deals-flow-audit-2026-10-15.md` (the latest Deals UX audit).

---

## 1. Repository state (15 Oct 2026, evening)

| Branch | Head | State | Touches negotiation or communication? |
|---|---|---|---|
| `dev` | 833d3050 | integrated; Deals redesign (round three) and security fixes SEC-01..05, 09 merged | the baseline described here |
| `int/dylan-ui` (local, being gated) | 5ecd4334 | dev + Dylan's redesign of Home, Cash, Receivables, Activity, the trust pages and the shell; re-recorded mocks. **Mock e2e: 373 passed, 53 failed (being triaged).** Next to land on dev. | web only. Deals components kept as dev's, except `components/deals/commitments.tsx`, `deal-list.tsx`, `ui/worklist-rows.tsx`, `home/v2/*` |
| `feat/dylan-ui` | 6242929c | source of the above | as above |
| `int/busy-five` | 689bfafb | dev + five more busy customers (BUYER-4..8, offers EX13..EX17, 5 supply contracts). **Held:** busy load takes 80 to 100 s | `fixtures/offers/offers.yaml`, `fixtures/scenarios/busy*.json`, `app/api/documents.py`, `app/api/runtime.py`, `app/domain/fixtures.py` |
| `fix/busy-load` (local, in progress) | 689bfafb+ | agent caching the seeded busy books in `app/api/runtime.py` | `runtime.py`, `demo_seed.py` |
| `perf/busy-tests` | 988129a8 | test-only snapshot fixture for busy tests (in progress) | `services/api/tests/api/*busy*`, `conftest.py` |
| `feat/capex-buy-side` | 90d3520c | buy side (purchase contracts) + setup-books; **held out of dev** until the Security Lead re-certifies | `app/operations/executor.py` (`_commit_purchase`), `app/api/capex.py`, `approval_review.py`, Deals page (a Buying card) |
| `fix/capex-1-3` | e48f8696 | CAPEX-1..4 security fixes for the buy side (final checks) | `executor.py` (`_tier2_reason`, `_commit_purchase`), `app/api/operations.py`, `components/approval-card.tsx` |
| `fix/setup-guard` | 7d9afdf4 | setup-books open guard | `app/api/setup.py`, `runtime.py` |
| `security/lead-audit` (**local only, not pushed**) | d274d0ad | the Security Lead's `docs/security/FINDINGS_REGISTER.md`. Read it with `git show security/lead-audit:docs/security/FINDINGS_REGISTER.md` | findings SEC-18..22, R-10, R-11 are about the buyer channel (section 8) |
| `docs/security-lead-handoff` | 94b4f79b | `docs/SECURITY_LEAD_HANDOFF.md`, `docs/SECURITY_ENDPOINT_INVENTORY.json` (not on dev) | reference |

- There are no open pull requests; integration is by `--no-ff` merges into dev by the lead.
- Open issues touching this area:
  - #158: accept-as-asked executor debt (one click logs two operations; decline reason not stored; a refused accept leaves a PROPOSED commitment);
  - #159: verifier observations;
  - #66: owner decisions, including "selectable counter";
  - #88 / #98: negotiation intelligence and the envelope.

**Present on dev:** everything in sections 3 to 7 unless marked otherwise.
**Only on another branch:** Dylan's UI, the busy five, the buy side, setup-books, the CAPEX fixes.
**In progress:** the busy load cache, the busy test snapshot, the Dylan UI e2e triage.
**Planned, not implemented:** any real buyer channel (section 9).

**Feature flags** (`services/api/app/config.py:53-68`, `1|true|yes|on`):
- on by default:
  - `FEATURE_TERMS_GUARD`
  - `FEATURE_DEBT_DESK`
  - `FEATURE_CAPEX`
  - `FEATURE_BORROWER_FILE`
  - `FEATURE_BUYER_NEGOTIATION`
  - `FEATURE_SECURITY_SCENES`
  - `FEATURE_ALERTS`
  - `FEATURE_EXPECTED_PLANS`
  - `FEATURE_CONTRACTS`
- off by default:
  - `FEATURE_ENVELOPE`
  - `FEATURE_PRICE_CURVE`
  - `FEATURE_COLLECTIONS_WORTH`
  - `FEATURE_EXPOSURE` (the e2e live API turns it on)
  - `FEATURE_CUSTOMER_ECONOMICS`
  - `FEATURE_PILOT_JOURNAL`
- also:
  - `LLM_MODE` (cache | live)
  - `LLM_PRIMARY` (claude | deepseek)
  - `CLAUDE_MODEL`
  - `CLAUDE_HARD_MODEL`
  - `DEEPSEEK_MODEL`
  - `DATABASE_URL` (`memory` for all development)
  - `DEMO_MODE`
  - `COUNTERPARTY_KEYS` (`app/api/auth.py:56`)
- web:
  - `NEXT_PUBLIC_API_MODE` (mock | live)
  - `NEXT_PUBLIC_API_URL`
  - `NEXT_PUBLIC_DEMO` (prefills the demo owner token and buyer keys)
  - `NEXT_PUBLIC_REQUEST_TIMEOUT_MS`

**Environments.**
- Development is local only:
  - the API runs on uvicorn with `TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1`;
  - the web runs in mock mode (recorded API answers in `apps/web/mocks`, produced only by `apps/web/scripts/record-mocks.mjs`) or in live mode.
- Supabase/Postgres exists for deployment but is not used in development; its schema is at migration 0002 of 0008.
- **Ports 3000 and 8000 belong to the owner.** Never use or stop them.

## 2. FLOW in one page

FLOW (流) is an AI working-capital agent for a Chinese SME supplier. A buyer asks for different terms (pay early for a discount, pay later, a rebate, a package). FLOW reads the request, proves on the current books whether the business can afford it, and proposes a priced reply. It then funds any gap (invoice financing, a credit-line draw) and executes only what the owner's signed mandate allows. Everything else goes to the owner for approval.

The lifecycle, with the code that owns each step:

| Step | What happens | Where |
|---|---|---|
| Buyer request | a message or document arrives on a buyer channel | `POST /offers` (`app/api/offers.py:73`), `POST /nl` as COUNTERPARTY (`app/api/nl.py:120`) |
| Semantic compilation | the model extracts grounded terms; code checks every quote and number | `app/compiler` (`service.py`, `grounding.py`) |
| Financial evaluation | projected on current books (ADR-0006); counters priced | `app/verifier/evaluate.py`, `counters.py`, `app/funding` |
| Mandate verification | owner-signed limits and tiers | `app/mandate/tiers.py:79-117`, signature checks |
| Decision | ACCEPT / COUNTER / REJECT / NEEDS_OWNER_APPROVAL / NO_VERDICT | `app/verifier/evaluate.py:723-758` |
| Negotiation | today: a simulated buyer inside the server | `POST /negotiate/{offer_id}` (`app/api/decide.py:382`), `app/counterparties` |
| Authorization | tiers; the owner's approval queue | `app/operations/executor.py`, `POST /approvals/{id}` |
| Execution | typed operations, one lock, one transaction, re-verified (ADR-0006 §5) | `executor.py` `_handle` / `_commit` / `_check_binding` (around `:1003-1122`) |
| Monitoring | alerts, clock, decision record, deal tracker | `app/alerts`, `app/clock`, `app/decisions`, `app/api/deal_tracker.py` |
| Reconciliation | bank receipts (SYSTEM key) settle invoices | `ReceivePayment`, `app/api/receivables.py`, reconciliation reads |

**The distinctions the new feature must keep:**
- **Commercial terms:** what the buyer and FLOW say they want. Obligations come from `CompiledOffer` (`app/domain/models.py:188`); counters are `CounterProposal` (`models.py:873`).
- **Financial commitments:** `Commitment` (`models.py` around `:927`), PROPOSED → ACCEPTED/ACTIVE → FULFILLED/EXPIRED/REVOKED. They are written onto invoices (ADR-0009).
- **Financing operations:** `DrawFacility` and `SubmitInvoiceForFinancing` are executor operations, separate from the deal.
- **Buyer-facing messages:** today these are deterministic server templates (section 7). No model prose reaches a buyer.
- **Owner approvals:** Tier-2+ operations queue for `POST /approvals/{id}`. Only the owner approves; the executor refuses an AGENT.
- **Settlement events:** only the bank feed (`ReceivePayment`, SYSTEM) records money arriving. Time moves only by the owner (`POST /clock/advance`, SEC-09).
- **Hypothetical scenarios:** what-if, `/offers/{id}/picture` and `/scenarios`, and the stress reads change nothing.

**The rule this feature must preserve:** model output never authorizes or executes a financial operation.
- The compiler's prompt grants no authority and has no action fields (`app/compiler/prompts/__init__.py`, `_COMMON`).
- Every operation is built by code from a stored verdict.
- The executor screens acceptances against the verdict's bound obligations and counters (`executor.py:933-974`).
- The NL classifier cannot emit APPROVE, REJECT or COUNTERPARTY_MESSAGE (`app/nl/classifier.py:1-11`).
- Chat can never approve from inferred text (`app/nl/service.py:274-283`).

## 3. Existing negotiation capability (the important section)

### 3.1 Incoming buyer requests

- **`POST /offers`** (`app/api/offers.py:73` `post_offer`)
  - Body: `OfferIn{fixture_id?, counterparty_id?, documents?}` (`:35`).
  - Callers:
    - the owner token;
    - the agent key;
    - a buyer's `X-Counterparty-Key`, which binds the sender: a different body id gets 403 `COUNTERPARTY_MISMATCH` (`:79-87`, SEC-18);
    - anonymous, capped by `enforce_intake_cap` → 429 `INTAKE_CAPPED` (`:53-70`; `INTAKE_CAP_PER_DAY`, default 200, `config.py:87`).
  - Limits: at most 5 documents of 4,000 characters each (`:30-31`).
  - Non-owner documents must use a channel in `BUYER_CHANNELS` = chat | email | portal | attachment (`:32`, `:103`). `SourceDocument.channel` is a Literal (`models.py:69`). **"email" is a label only; there is no mail ingestion.**
- **`POST /nl`** with a buyer key: the message is compiled as an offer (`app/nl/offers.py:346` `counterparty_message`).
- **`POST /documents`** is the owner's contract intake (`app/api/documents.py:72`), not buyer offers.
- **Identity.** The actors are OWNER, AGENT, SYSTEM (bank feed) and COUNTERPARTY (`app/api/auth.py:1-56`). Demo keys exist for BUYER-1 and BUYER-2; real keys come from `COUNTERPARTY_KEYS`. There is no `require_buyer` dependency: the check is inline in `offers.py` and `nl.py`.
- **Linking.**
  - `offer_id = "OFF-" + sha256(canonical documents)[:12]` (`app/compiler/grounding.py:90`); `deal_id = "deal:" + offer_id` (`app/decisions/identity.py:37`).
  - A buyer is linked by `counterparty_id` only. **There is no conversation or thread id.** A follow-up is a new offer. `parent_doc_id` exists on the model but no flow sets it.
- **Duplicates.**
  - The same documents give the same offer id; `put_offer` raises `OfferVersionConflict` → 409 (`offers.py:127-130`).
  - A different document under a taken id → 409 `DOCUMENT_ID_TAKEN` (SEC-16, `:137-144`).
  - There is no request idempotency key on intake.
- **Storage.**
  - `CompiledOffer` is stored with `doc_ids`, `compiler` and `prompt_version`.
  - **The raw documents live only in `rt.documents`, in memory, deliberately not persisted** (`app/api/runtime.py:10,56`). Each obligation's quoted `SourceSpan.text` survives (`models.py:50`).
  - The full original message is lost on restart.

### 3.2 Semantic interpretation

- **Chain** (`app/compiler/service.py:49-65`):
  - `LLM_MODE=cache` (the default): CacheBackend, then RulesBackend.
  - `live`: Claude, then DeepSeek, then Rules; `LLM_PRIMARY=deepseek` swaps the first two.
  - Rules is always appended.
  - Each call logs backend, prompt version, doc hash and latency.
- **Output.** `OfferExtraction`, `TermSheetExtraction` and `ContractExtraction` (`app/compiler/schema.py`), turned into `CompiledOffer`: obligations, abstentions, data_requests, authority_claims, funding_claims, autonomy_eligible.
- **Grounding** (`grounding.py:1-9`, `:135-404`). Every quote must appear verbatim; code computes offsets and parses numbers from quoted fragments. Anything unproven becomes an `Abstention`.
- **Ambiguity.** `Outcome.NO_VERDICT` (`models.py:870`); `clarification_request` (`app/nl/offers.py:168`). The Deals queue shows these as BUYER_REPLY rows reading "Nothing to resend" (`app/api/worklist.py:298-305`). **These are not replies to a counter.**
- **Can model output reach execution?** No (section 2).

### 3.3 Financial evaluation and counters

- **`POST /offers/{id}/evaluate`** (`app/api/decide.py:173-262`):
  - calls `app.verifier.evaluate`;
  - stores the verdict and an EvaluatedFact;
  - logs security events;
  - guards the counters' text;
  - returns the comparison, the cure plan, and `send_plans` / `decline_plan`.
- **Outcome rules** (`app/verifier/evaluate.py:723-758`):
  - REJECT: a hard violation or a security code.
  - COUNTER: price codes or a breached goal (REJECT if no counter survives).
  - NEEDS_OWNER_APPROVAL:
    - lengthened terms;
    - forward value above `tier2_single_commitment_fen`;
    - anything beyond early pay;
    - unproven autonomy;
    - a buyer who is past due.
  - ACCEPT: otherwise.
- **Counters** (`app/verifier/counters.py`: `counters()` `:633`, `counters_explained()` `:656`, `_proposal` `:310-325`):
  - They are deterministic. Their text is assembled from template clauses, and each span is recorded.
  - Each counter is re-checked as an offer (`evaluate.py:713-719`).
  - `counters_explained` says why an option is withheld; the picture shows it as `withheld[]`.
- **Alternatives:**
  - `GET /offers/{id}/picture` (`app/api/offer_picture.py:1139`);
  - `GET /offers/{id}/scenarios` (`:1157`);
  - `GET /offers/{id}/compare` (`strategy_compare.py:82`, behind the exposure flag);
  - `POST /router/plan` (`decide.py:618`, using `app/funding`).

### 3.4 Negotiation state and the "send"

- **`POST /negotiate/{offer_id}`** (`decide.py:382`, `_negotiate_locked` `:425-574`)
  - Owner only; behind the `terms_guard` and `buyer_negotiation` flags.
  - Body: `NegotiateIn{buyer_profile="cooperative", max_rounds (ignored), verdict_id?, counter_id?, state_version?}` (`:319-327`).
  - **Binding:**
    - 409 `COUNTER_CHANGED` with reasons VERDICT_CHANGED, COUNTER_NOT_IN_VERDICT or BOOKS_CHANGED (`:353-363`, `:436-453`);
    - 409 `ALREADY_SENT` when an open agreement has the same `terms_hash` (`:397-414`);
    - the lapsed-offer refusal.
  - **Where it goes:**
    - only to the in-process deterministic `BuyerKernel` (`app/counterparties/buyer.py`, with a hidden reservation), through `negotiate()` (`app/counterparties/negotiation.py:72-140`): at most 3 rounds, with a `transcript_hash`;
    - **nothing leaves the process**;
    - the web says so: "The buyer's reply is simulated in this environment. Nothing is sent outside FLOW." (`apps/web/lib/dictionary.ts:17`).
  - **Profiles:** `PROFILES = {"cooperative": "BUYER-1", "hard_line": "BUYER-1-HARDLINE"}` (`decide.py:102`). **Every Deals send negotiates against BUYER-1's hidden profile, whatever the offer's real buyer.** The chat path uses `offer.counterparty_id`.
  - **On a deal:**
    - `propose_commitment(expires_day=day+7)`;
    - `AcceptOffer(requested_by=AGENT, idempotency_key="accept-{commitment}")` (`:488-493`);
    - the funding gap's operations (`_ops_for_plan` `:330-347`);
    - a `SentFact` on the decision record (`:530-552`).
  - **On no deal:** the refusal plan funds the gap (`app/api/refusal.py`). The UI discloses this beforehand as `if_refused_text`.
  - **The buyer's counter-counter is discarded.** `supplier_next(_resp)` ignores the response and sends the next untried counter (`decide.py:461-466`). `BuyerResponse.source_document` ("for the compiler or the inbox", `buyer.py:99`) is never called in `app/`.
  - **Buyer reply text:** `rounds[].buyer_text`, guarded toward OWNER (`:471-483`). It is shown only on the demo `/verdict` page (`apps/web/app/verdict/page.tsx:300-305`), **not on Deals**.
- **Accept as asked** (`app/api/accept.py:360`) and **decline** (`:393`): the owner's own acceptance or refusal of the buyer's request, bound to the verdict and state version (`_bound` `:295-315`).
  - Accept reuses the open proposal (SEC-03).
  - Decline uses a random key (SEC-04); the decline reason is not stored (#158).
- **Expiry.**
  - `Commitment.expires_day`: +7 on /negotiate, `PROPOSAL_DAYS=7` in accept.py, `COMMITMENT_DAYS=14` (capped at the mandate's expiry) in /nl (`app/nl/pipeline.py:39,113`).
  - The clock sets EXPIRED (`app/clock/__init__.py:238,299`).
  - Acceptance screening checks REPLAY, COMMITMENT_EXPIRED and TERMS_CHANGED (`executor.py:933-953`, `app/commitments/lifecycle.py:134-154`).
- **Multiple conversations for one buyer.** Each offer is its own deal; there is no per-buyer conversation. Supersession is handled by `tests/deals/test_supersession.py` and the open-offer logic.
- **Accepted terms → commitment → execution.** Executor `_commit` → `_check_binding` (ADR-0006 §5) checks:
  - the named receivables are still owed;
  - one live agreement per offer (SEC-02);
  - the aggregate and per-buyer caps;
  - re-verification if the state version changed.
  Tier 2 goes to approvals.
- **Audit.**
  - The operations log is hash-chained: `entry_hash = sha256(prev + payload + result)` (`app/persistence/chain.py`).
  - Decision facts are in `app/decisions` (ADR-0011).
  - Reads: `GET /activity` (`app/api/activity.py:282`), `GET /audit` (`app/api/read.py:224`), `GET /decisions/{id}` and `/tracker`.

### 3.5 The authenticated buyer path already executes (read this before designing inbound)

`counterparty_message` calls `decide(..., execute=authenticated)` (`app/nl/offers.py:354-355`). **A buyer turn on `POST /nl` with a valid `X-Counterparty-Key` runs CounterOffer, AcceptOffer or RejectOffer with no owner step** (`app/nl/pipeline.py:108-156`).
- The actor is AGENT.
- Only early pay on a named invoice is Tier 1, so it executes; Tier 2+ queues for the owner (`app/mandate/tiers.py:106-115`).
- Without a key, the turn is a proposal only, with `UNCONFIRMED_NOTE` (`offers.py:59`, `:359-363`).
- The reply goes through the egress guard, and only allow-listed keys are returned (`app/api/nl.py:41-51`).
- `evals/findings.yaml` EV-01 records a past incident where a buyer message executed ACCEPT on misread terms. The fix limited Tier 1 to pure early pay.

**An inbound email channel that maps onto this path would let an external message execute.** Decide deliberately whether it should.

### 3.6 Capability inventory

| Capability | Implemented? | Code | Evidence | Gap |
|---|---|---|---|---|
| Buyer request intake (API) | Yes | `offers.py:73`, `nl.py:120` | `tests/compiler/test_offers.py`, `tests/security/test_intake_hardening.py`, `test_intake_cap.py` | no real channel; raw text not persisted |
| Buyer authentication | Partial | `auth.py`, inline in `offers.py:79-87` | `tests/nl/test_counterparty_channel.py` | static keys; anonymous intake can name any buyer (SEC-19) |
| Grounded extraction (Claude, DeepSeek, rules, cache) | Yes | `app/compiler` | `tests/compiler/*` | live-mode certification evidence not found |
| Priced, deterministic counters | Yes | `app/verifier/counters.py` | `tests/verifier/test_counter_*.py` | — |
| Buyer-facing counter text | Yes, as a template | `counters.py:310-325`; `reply_text` in `offer_picture.py:729` | shown as the recommendation headline on Deals | not labelled as the message; not in the send review; no copy |
| Prepared outbound message stored | **No** | — | ADR-0011 stores no sentence or buyer text (`docs/adr/0011-durable-decision-record.md` around `:291`) | — |
| Send to the simulator | Yes | `decide.py:382`, `app/counterparties` | `tests/api/test_negotiate_binding.py`, `tests/counterparties/*` | wrong profile for buyers other than BUYER-1; counter-counters discarded |
| Simulated buyer response | Yes, synchronous | `negotiation.py:72-140` | `tests/counterparties/test_negotiation.py` | no asynchronous waiting state |
| Direct external sending | **No** | — | no email, SMTP, IMAP or HTTP client to buyers (section 9) | — |
| Transmission status | **No** | — | — | — |
| Buyer acceptance → commitment | Yes (simulator, buyer chat) | `decide.py:488-493`; `pipeline.py:108-156` | `tests/operations/test_sec02_one_agreement.py` | bound to the kernel's ACCEPT, not to an external message |
| Duplicate-send prevention | Yes | `ALREADY_SENT` (`decide.py:397-414`); SentFact key `nodeal:{verdict}:{profile}[:counter]` | `test_negotiate_binding.py` | for simulator sends only |
| Stale-state protection on send | Yes | `COUNTER_CHANGED` (`decide.py:353-363`); executor `_check_binding` | `tests/operations/test_state_binding.py` | — |
| Negotiation audit trail | Partial | hash-chained ops; SentFact; activity categories (`activity.py:37-43`) | `tests/api/test_activity_read.py` | no message record; whether a no-deal send appears in Activity is **UNKNOWN** (see `activity.py:114-160`) |
| Copy a buyer-facing request | Yes, for collections only | `components/business/chase-payment.tsx:93` (`GET /receivables/{id}/chase`) | receivables e2e | **the pattern to reuse** |
| Confidentiality guard on outbound text | Yes | `app/egress/guard.py:69-108` | `tests/egress/*` | misses number forms (SEC-22); derived values not protected |

## 4. API and module inventory

`O` = `require_owner`; `O|A` = `require_owner_or_agent`.

| Method and path | Handler | Actor | In → out | Side effects | Tests | Limitations |
|---|---|---|---|---|---|---|
| POST /offers | `post_offer` `offers.py:73` | O, A, buyer key, anonymous (capped) | `OfferIn` → offer, documents | `put_offer`; documents in memory | `tests/compiler/test_offers.py`, `tests/security/test_intake_*.py` | no thread; raw text not persisted |
| GET /offers/{id} | `get_offer` `offers.py:147` | O | → offer, documents, latest verdict id | — | many in `tests/api` | — |
| POST /offers/{id}/evaluate | `evaluate_offer` `decide.py:173` | O (+terms_guard) | `EvaluateIn` → verdict view | verdict, EvaluatedFact, security events | `tests/api/test_decide.py` | — |
| POST /negotiate/{id} | `negotiate_offer` `decide.py:382` | O (+terms_guard, buyer_negotiation) | `NegotiateIn` → outcome, rounds, commitment, operations | commitment, AcceptOffer, funding ops, SentFact | `tests/api/test_negotiate_binding.py` | simulator only; BUYER-1 profile |
| POST /offers/{id}/accept | `accept_as_asked` `accept.py:360` | O | `AcceptIn{verdict_id, state_version}` → decision, receipt | commitment, AcceptOffer (OWNER) | `tests/api/test_accept_as_asked.py`, `tests/operations/test_sec02_one_agreement.py` | #158 |
| POST /offers/{id}/decline | `decline_request` `accept.py:393` | O | `DeclineIn` → decision, receipt | RejectOffer | same, plus `test_sec_authority_boundaries.py` | reason not stored |
| GET /offers/{id}/picture, /scenarios | `offer_picture.py:1139`, `:1157` | O | → picture, scenarios | none (cached) | `tests/api/test_offer_picture*.py` | whether `reply_text` (`:729`) passes the egress guard is **UNKNOWN** (evaluate guards counter text at `decide.py:123`) |
| GET /decisions, /decisions/{id}, /decisions/{id}/tracker | `decisions.py:723,752`, `deal_tracker.py:802` | O | → record, tracker | — | `tests/api/test_decisions_flow.py`, `test_deal_tracker.py` | — |
| POST /operations | `operations.py:67` | O\|A (SYSTEM only with the feed key) | typed Operation → result | executor | `tests/operations/*` | — |
| GET /approvals/queue, POST /approvals/{id} | `operations.py:188`, `:328` | O (the executor refuses an AGENT approval) | → queue; `{decision}` → result | `executor.decide` | `tests/operations/test_approvals_and_circuit.py`, `tests/api/test_approval_*.py` | — |
| POST /commitments/{id}/revoke | `operations.py:370` | O | → result | revoke, log | `tests/api/test_slice_b_round_three.py` | thin coverage |
| POST /nl, /nl/opener, /nl/reset | `nl.py:120`, `:186`, `:170` | O, A, buyer (key or none) | `NlRequest` → turn | may execute (section 3.5) | `tests/nl/*`, `tests/api/test_chat_scope.py`, `tests/security/test_nl_attacks.py` | SEC-21 sessions; R-10, R-11 |
| GET /activity, /audit | `activity.py:282`, `read.py:224` | O | → rows | — | `tests/api/test_activity_read.py` | chain not anchored (R-13) |
| GET /deals, /worklist, /customers | `deals.py:39`, `worklist.py:886`, `:894` | O | → queue | — | `tests/api/test_deals_queue.py`, `test_worklist.py` | — |
| GET /receivables/{id}/chase | `app/api/collections.py` (**route line UNKNOWN**; grep `chase`) | O | → a copyable payment request | — | receivables tests | the copy pattern |

## 5. Frontend flows (dev)

- **Deals** (`apps/web/app/deals/page.tsx` → `components/deals/flow/deals-page.tsx:39`)
  - The queue comes from `GET /deals`, with tiers needs_you / waiting / agreements / customers. Selection lives in the URL.
  - `DecisionPane` (`decision-pane.tsx:199`) loads `GET /offers/{id}`, `/decisions/{id}`, `/offers/{id}/picture` and `/exposure` through `use-negotiation.ts:36`.
  - `Recommendation` (`deal-overview.tsx:21`) shows `reply_text` as a headline. `ChoicesTable` (`:196`) compares the buyer's request ("Accept their request") with each reply.
  - "Review and send the counter" opens `SendBlock` (`components/deals/flow/send-block.tsx:37`):
    - who may send it;
    - cost;
    - the receipt statements;
    - terms;
    - `if_refused_text`;
    - the commitment receipt.
  - Send → `negotiate()` → `POST /negotiate/{id}` (`send-block.tsx:103-125`). `SendResult` (`decision-pane.tsx:86-104`) shows "accepted" or "refused every counter".
  - Accept as asked: `AcceptBlock` (`accept-block.tsx:167-170`).
  - The buyer-profile selector shows only in demo mode (`send-block.tsx:217-238`).
- **Customer overview** (`app/customers/[id]/page.tsx`, `components/customer/overview.tsx:108-170`): reads `GET /customers/{id}/overview`, and its action links back to `/deals?...`.
- **Approvals** (`app/approvals/page.tsx`, `components/approval-card.tsx:106`): `GET /approvals/queue`, `POST /approvals/{id}`. Approve stays disabled until the terms are shown (`lib/approval-terms.ts:16-26`).
- **Activity** (`components/activity/activity-read.tsx:150`): `GET /activity`. The deal categories are ACCEPT_OFFER, RECORD_COMMITMENT, COUNTER_OFFER, REJECT_OFFER and REVOKE_COMMITMENT.
- **Demo** (`app/demo/page.tsx`, `lib/demo.ts:150` `DEMO_STEPS`):
  - The steps are ask → decide → agree (`negotiate`, cooperative) → cash → bank → time → queue → approve → settle → outcome → proof. `runWalkAway` uses hard_line.
  - Scenarios: golden_sme, busy, short_facilities, public_sme (server, `read.py:264`). The web has cards for three of them.
- **Ask FLOW** (`components/chat/*`, `POST /nl`)
  - Owner chat: NEGOTIATE is a proposal, then "go ahead". **Chat cannot draft, preview or send a buyer message.**
  - "Act as buyer": `chat-view.tsx:230` sends a demo `X-Counterparty-Key`, and that path executes (section 3.5).
- **Inbox:** buyer messages are fixed copies labelled "not connected" (`apps/web/lib/inbox.ts:4-8`). Opening one calls `POST /offers`.

**Today's journey and where it breaks:** request (simulated inbox or buyer chat) → Deals queue → evaluate → choose a reply → review → send → (synchronous simulated reply) → agreement → approval if Tier 2 → record → tracker. The breaks:
1. **Verified counter → buyer-facing message.** There is no message preview, edit or copy in the review; the only words are the `reply_text` headline.
2. **Message → channel.** The message goes to the in-process kernel only; nothing leaves FLOW.
3. **Buyer reply.** There is no asynchronous waiting state, and `buyer_text` is not shown on Deals.
4. **Re-evaluation.** A buyer's counter-counter is discarded.

## 6. Model infrastructure and DeepSeek

- **Files:** `app/compiler/{backends,service,cache,record_cache}.py`, `app/nl/classifier.py`.
- **Models** (names only):
  - `CLAUDE_MODEL` (default `claude-sonnet-5-5`);
  - `CLAUDE_HARD_MODEL` (`claude-opus-5-5`, used for long, multi-document, term-sheet and contract inputs, `backends.py:37-41`);
  - `DEEPSEEK_MODEL` (`deepseek-flash`; the key is read from the environment).
- **Calls:**
  - Claude: JSON-schema output, 2 SDK retries, 60 s timeout, a server-side fallback beta.
  - DeepSeek: `json_object` plus Pydantic validation, 3 attempts, temperature 0 (`backends.py:74-203`).
  - The classifier times out after 30 s.
  - Latency is logged per call; there is no SLA.
- **Prompt versions:** `offer-v4`, `termsheet-v3`, `contract-v1`, with a prompt canary (`prompts/__init__.py:17-23`).
- **Cache:** `fixtures/compiler_cache/` (keyed by sha256 of prompt version and documents). It is what tests and the demo run on.
- **DeepSeek status:** implemented and live only with `LLM_MODE=live` and its key. Evidence of its quality for buyer-facing prose: **none**. It is used only for extraction.
- **Who controls what today:**

| Responsibility | Component | Model involved? |
|---|---|---|
| Understanding commercial language | compiler (grounded extraction) | yes, constrained by grounding and abstention |
| Determining financial terms | verifier, counters, funding router | no |
| Authorizing operations | mandate tiers, executor, owner approval | no |
| Generating buyer-facing prose | templates: `counters.py:310-325`; `counterparties/verbaliser.py` (en/zh); `nl/offers.py:168-340` | no. The verbaliser's optional LLM `VerbaliserHook` (`verbaliser.py:141-147`) is **not wired anywhere** |
| Sending external communications | nothing | — |

## 7. Financial and security invariants for communication

| Requirement | Existing enforcement | Missing or unverified |
|---|---|---|
| Commercial-term integrity | counters are deterministic templates with recorded spans; `terms_hash` (`app/commitments`); `COUNTER_CHANGED` binding; the executor screens terms (`executor.py:933-974`) | a rendered message is not bound to `terms_hash`; no stored outbound artefact |
| Confidentiality | `app/egress/guard.py:69-108` swaps the whole text for a safe template and logs DATA_EXTRACTION; canaries; INVARIANTS 7 | SEC-22: number forms (30,0000; 0.3m; 3e5; 30w; 千分之十五; 15‰) and derived values (break-even, counter cap, shortfall) are not protected. The register says this is "required before any generated outbound text". R-1: numbers in words, 大写 numerals. R-10: a counter's face can reveal the funding gap; there is no per-buyer attempt budget |
| Recipient integrity | the buyer key binds `counterparty_id` (SEC-18) | no destination addresses exist; anonymous offers can name any buyer (SEC-19, open) |
| Authority: negotiate vs transmit | the tiers decide what executes | no separate "may transmit" permission exists; today "send" equals "negotiate with the simulator" |
| Stale state | `COUNTER_CHANGED` (VERDICT, COUNTER, BOOKS), lapsed offers; ADR-0006 §5 re-verification | a send to a real buyer would need the same check at transmit time and at the reply |
| Replay and idempotency | `ALREADY_SENT`; SentFact keys; executor idempotency keys; SEC-04 random decline key | no outbound message id or provider idempotency |
| Lifecycle integrity | ADR-0011 does not model a sent-but-unanswered counter (around `:291`); the kernel's ACCEPT creates the commitment | a real send must not create a commitment. New states are needed (drafted, sent, delivered, replied, accepted, effective) |
| Inbound trust | buyer keys; the intake cap; the injection flags (`app/security`, compiler canary); grounding | email has no authentication model; the authenticated buyer path executes (section 3.5); SEC-20: the intake cap is global; SEC-21: NL session ids are client-chosen |
| Agreement confirmation | executor `_commit` → `_check_binding`; one live agreement per offer (SEC-02); the approval queue | a buyer's "yes" by email must re-enter through compile → verify → bind, never straight to `AcceptOffer` |
| Auditability | hash-chained operations; decision facts | outbound content is not stored (ADR-0011 stores no sentence); the chain is not anchored (R-13) |

The security register is `docs/security/FINDINGS_REGISTER.md`, **on the local branch `security/lead-audit` only** (read it with `git show`). Also:
- `docs/SECURITY_SELF_ASSESSMENT.md` §04 on dev (F-01..F-12, R-1..R-16);
- `evals/findings.yaml`.

## 8. Channels and integrations

| Channel | State |
|---|---|
| Simulated buyer (`app/counterparties`, kernel and verbaliser en/zh) | Implemented (in-process, synchronous) |
| Buyer chat with a key (`POST /nl`) | Implemented (it executes; section 3.5) |
| Simulated inbox (`apps/web/lib/inbox.ts`) | Implemented as fixed copies, labelled "not connected" |
| Copy-to-clipboard request (collections) | Implemented (`chase-payment.tsx`) |
| Email sending (SMTP, SendGrid, Resend, Mailgun) | Absent |
| Gmail, OAuth | Absent |
| Inbound email, IMAP, webhooks | Absent |
| WeChat or other messaging | Absent (the word appears only in lexicon regexes) |
| Message threading | Absent (no thread id; `parent_doc_id` unused) |
| Delivery status | Absent |
| Background jobs, outbox worker | Absent (no scheduler, BackgroundTasks or create_task in `app/`) |

A provider accepting a send would not mean the buyer received it, and receipt would not mean acceptance. None of these states exist today.

## 9. The proposed feature: a hypothesis to test, not an approved design

End-to-end buyer communication:
1. evaluate the request;
2. pick a verified reply;
3. render a buyer-facing message with the exact verified terms;
4. the owner sends it (or FLOW does, where separately authorized);
5. record it against the negotiation;
6. the buyer replies;
7. match and compile the reply;
8. re-verify on current books;
9. propose or execute the next permitted step;
10. agreements become effective only through the existing binding and authorization.

Approaches to weigh:
- deterministic templates (exists);
- the existing model gateway;
- DeepSeek prose;
- the simulated channel;
- draft-and-copy (the Chase payment pattern);
- connected email sending;
- inbound email;
- bounded autonomous sending.

Find the smallest safe implementation that genuinely improves the product.

**The lead's prior, which you are free to reject:** the smallest safe step is draft-and-copy. That means:
- show the exact template message for the chosen reply in the send review, rendered deterministically from the counter and bound to its `terms_hash`;
- egress-guard it;
- copy it to the clipboard;
- record a "sent by the owner outside FLOW" fact;
- the owner pastes the buyer's answer back into the existing intake, so it is compiled and verified as a new offer.

No transport, no model prose. Fix SEC-22 first if any prose is ever generated.

## 10. Risks and integration concerns

- **The files you would touch:**
  - `app/api/decide.py` (`negotiate_offer`);
  - `app/api/offer_picture.py` (`reply_text`);
  - `app/verifier/counters.py` (template text: an engine module, **stability set, read-only without lead sign-off**);
  - `app/egress/*`;
  - `app/decisions` (facts; ADR-0011 says it stores no sentence, so storing outbound text is an ADR change);
  - `app/counterparties/*`;
  - `app/nl/offers.py`;
  - on the web: `components/deals/flow/send-block.tsx`, `decision-pane.tsx`, `deal-overview.tsx`, `lib/dictionary.ts`, `lib/live/*`, the mocks (recorder only).
- **The engine stability set is read-only:** `app/{financial,verifier,funding,alerts,operations,clock,books,mandate,covenants}` and `app/domain/models.py`. A new operation or model field there needs an ADR and the lead.
- **Reuse, do not duplicate:**
  - the egress guard;
  - `terms_hash` and the commitment lifecycle;
  - the `COUNTER_CHANGED` binding;
  - SentFact and the decision facts;
  - the verbaliser templates;
  - the Chase-payment copy pattern;
  - `t(lang, en, zh)` server words (INVARIANT 13: the browser builds no sentence and computes no money word).
- **Known debt:**
  - the BUYER-1 profile hard-wired on Deals sends;
  - counter-counters discarded;
  - `max_rounds` ignored;
  - #158;
  - raw documents not persisted;
  - `slice-b-round-three.spec.ts` committed empty (0 bytes);
  - `outbound_blocked` (`decide.py:126`) and `biz.deals.send.blocked` (dictionary) unused on the web.
- **Security findings that bear on this:** SEC-18, 19, 20, 21, 22, R-1, R-10, R-11, R-13, EV-01.
- **Testing limits:**
  - mock e2e needs recorded answers (re-record with the recorder, never by hand);
  - busy-books tests are slow (60 to 140 s each until `perf/busy-tests` lands);
  - live e2e is serial;
  - this machine runs one heavy suite at a time, and the lead's checks have priority.
- **Demo limits:** the demo resets shared in-memory books; the busy books currently load in 80 to 100 s on `int/busy-five`.
- **Database:** storing messages or threads needs a migration (`services/api/migrations/versions`, now at 0008) and both stores (in-memory and SQL).
- **Areas other agents are changing now (avoid):**
  - `app/api/runtime.py`, `demo_seed.py` (busy load);
  - `app/operations/executor.py`, `app/api/operations.py`, `components/approval-card.tsx` (CAPEX fixes);
  - `app/api/setup.py`;
  - `services/api/tests/api/*busy*`, `conftest.py`;
  - every web page outside Deals (Dylan's UI, about to land);
  - `components/deals/commitments.tsx`;
  - `lib/dictionary.ts` (shared; union on merge).
- **Why outbound or inbound cannot be done safely as the code stands:**
  1. "send" and "negotiate" are one act;
  2. there is no permission to transmit;
  3. there is no message record or state between "sent" and "accepted";
  4. the authenticated buyer path executes on receipt;
  5. the outbound guard has known holes.
  Any real channel needs these first.

## 11. What to inspect first

1. `services/api/app/api/decide.py` `:319-574`: the send, its binding and what an ACCEPT does.
2. `services/api/app/counterparties/` (`negotiation.py`, `buyer.py`, `verbaliser.py`): the simulated reply cycle; how much is reusable.
3. `services/api/app/nl/offers.py` `:168-560` and `app/nl/pipeline.py:108-156`: buyer-channel execution and clarification text.
4. `services/api/app/egress/guard.py` and `normalise.py`, plus SEC-22 in the register: whether a message can be guarded.
5. `services/api/app/verifier/counters.py` `:310-325`, and `offer_picture.py:729`: where the message text comes from; whether `reply_text` is guarded.
6. `docs/adr/0011-durable-decision-record.md` (facts, and what it excludes), plus `app/decisions`.
7. `services/api/app/commitments/` and `executor.py` `_commit` / `_check_binding`: how a reply would become effective.
8. `apps/web/components/deals/flow/send-block.tsx` and `decision-pane.tsx`: where a message preview and copy would sit.
9. `apps/web/components/business/chase-payment.tsx`: the copy pattern already shipped.
10. `services/api/app/compiler/backends.py`: whether any drafting model is needed at all.

## 12. Collaboration rules

- Work in your own git worktree (`git worktree add .claude/worktrees/<name> -b <branch> origin/dev`). Never edit the lead's worktrees (`.claude/worktrees/int-*`, `fix-*`, `perf-*`, `dylan-ui`, `capex-fix`, `setup-guard`, `busy-load`).
- Never merge into dev. Push focused branches; the lead integrates with `--no-ff`.
- Evaluation first. Build nothing until the owner authorizes it.
- Never reset shared demo data on a server you did not start. Use your own ports (pick 85xx/35xx; never 3000 or 8000) with `DATABASE_URL=memory`.
- Never use real customer addresses or contacts. Never read or print `.env`. Never connect to Supabase or Postgres.
- Do not change financial semantics or the engine stability set without the lead.
- Security-sensitive changes (anything that sends, receives or executes) need an independent verifier and the Security Lead.
- Run focused tests only. Never run full suites while the lead's check is running; ask first.
- Before any release, rebase on the latest dev.
- Never `git stash`. Never kill processes by image name. If a command is refused by the permission system, report it and do not route around it.
- Commits: plain one-line messages, no co-author line.
- Likely conflict files: `lib/dictionary.ts`, `lib/types.ts`, `send-block.tsx`, `decision-pane.tsx`, `decide.py`, `offer_picture.py`, `apps/web/mocks/*`, `scripts/record-mocks.mjs`.

## 13. Priorities right now (15 Oct)

1. Dylan's UI to dev (e2e triage under way).
2. The busy load fix, then the busy five to dev.
3. The CAPEX and setup fixes → Security Lead re-certification → the buy side to dev.

The deadline is the hackathon demo (date: ask the owner). Frozen: the engine stability set; Slice C is not started.

This feature does not conflict with the critical path if it stays in evaluation until items 1 and 2 land. Building it now would collide with `decision-pane`, `dictionary.ts` and the mocks while they are changing.

## 14. Focused tests

From `services/api`:

```bash
SKIP_PERF_BENCH=1 PYTHONUTF8=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory uv run --project "$PWD" --directory "$PWD" pytest -o addopts= -p no:cacheprovider tests/api/test_negotiate_binding.py tests/api/test_decide.py tests/api/test_decisions_flow.py tests/api/test_accept_as_asked.py tests/api/test_lapsed_offers.py tests/counterparties tests/verifier/test_counter_a_floor.py tests/verifier/test_counter_property.py tests/compiler/test_offers.py tests/mandate tests/operations/test_mandate_gate.py tests/operations/test_approvals_and_circuit.py tests/commitments tests/nl/test_consent.py tests/nl/test_plan_binding.py tests/nl/test_counterparty_channel.py tests/egress -q
```

From `apps/web` (choose free ports):

```bash
E2E_TARGET=mock E2E_PORT=3517 pnpm exec playwright test e2e/deals.spec.ts e2e/deals-queue.spec.ts e2e/accept-as-asked.spec.ts e2e/slice-b.spec.ts e2e/slice-b-round-two.spec.ts e2e/demo.spec.ts e2e/chat.spec.ts e2e/approvals.spec.ts
```

```bash
E2E_TARGET=live E2E_LIVE_PORT=3518 E2E_API_PORT=8518 pnpm exec playwright test e2e/accept-as-asked.spec.ts e2e/slice-b.spec.ts e2e/demo.spec.ts e2e/chat.spec.ts
```

**Recent evidence (not proof of your tree):**
- On dev 833d3050, the round-three gate was: API full green after ec21ada0, mock e2e green after da3df86d, live with 2 known failures (#157).
- On `int/dylan-ui` 5ecd4334 today: mock e2e 373 passed, 53 failed (being triaged), unit 163/163, tsc and eslint clean.
- On `int/busy-five` 689bfafb: the 145 busy-related API tests pass.

Re-run what you rely on.

## 15. Questions to answer independently

1. Is outbound buyer communication genuinely FLOW's highest-value missing capability?
2. What communication and negotiation infrastructure already exists?
3. What is the smallest safe end-to-end implementation?
4. Should the MVP stop at a draft, support real email sending, or process inbound replies?
5. Should DeepSeek be used, or should the existing model gateway be reused?
6. Which commercial clauses must be rendered deterministically?
7. How should recipient identity and communication authority be verified?
8. How can FLOW receive and match replies without confusing negotiations?
9. How can a buyer's apparent acceptance become an effective agreement without bypassing existing safeguards?
10. How should the draft, sent, delivered, accepted and effective states be represented?
11. How can the communication workflow fit naturally into the existing Deals UI?
12. What is the smallest convincing hackathon demonstration?
13. What additional security risks would external communication introduce?
14. What can be implemented independently without disrupting ongoing work?
15. Should the team build now, build a narrow MVP, or defer?

You are free to disagree with every recommendation here. Report your findings to the owner and the lead before building.
