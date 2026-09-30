# TermsLedger v2: Technical Document

2026 FINTECHATHON · International AI Track | Technical Document

| Field | Value |
| --- | --- |
| Team name | [TEAM: team name] |
| Competition track | International AI Track, Topic E: SME Finance Copilot [TEAM: confirm the exact track wording the organisers expect] |
| Submission date | [TEAM: submission date, on or before 20 Oct 2026] |

TermsLedger is an agent owned by a small supplier. It manages both of the supplier's debt books under limits the owner has signed. **Terms Guard** covers the credit the supplier gives buyers through payment terms, discounts and rebates. **Debt Desk** covers the credit it takes from lenders to survive those terms. The language model only interprets text. Deterministic code decides and executes.

**Data notice.** Every company, buyer, lender, rate, amount and message in this document is a **synthetic fixture** (`fixtures/`). Every figure quoted comes from `fixtures/golden/golden_values.json`, an independent oracle (`fixtures/golden/compute_golden.py`), or from the evaluation reports in `services/api/evals/`. No real customer, bank or transaction data is used. The source is at [TEAM: public repository URL and the commit or tag submitted].

## 01 Project Overview

### Problem, target users and selected topic

**Selected topic.** International AI Track, **Topic E: SME Finance Copilot** (financing and cash-flow support for small businesses), under the 2026 theme "AI as a Financial Participant".

**The problem.** Large buyers now negotiate payment terms through software. Pactum's public material, for example, describes payment-term, discount and rebate agents that operate "within parameters you define". Lenders approve small-business loans by model in seconds (MYbank, WeBank). The supplier in the middle usually has neither: just an owner reading a chat message at night, deciding alone whether to accept 60-day terms and, separately, whether to borrow.

The reframe that drives the product: **a payment-term extension is an interest-free loan from the supplier to the buyer, and the supplier funds it by borrowing.** On the synthetic fixture (a ¥420,000 monthly invoice to the largest buyer):

- moving that buyer from 45 to 60 days going forward ties up **¥207,123.29** of extra receivables, permanently;
- funding that on the cheapest committed source that can carry a permanent need (invoice financing at **10.8417%** all-in, since the credit line's clean-down rules it out) costs **¥1,871.30 per invoice**, or **¥22,455.62 a year**;
- the extension moves ¥0 today, so it passes every spend cap. Wallet-style controls (spend caps, allowlists, signer policies) guard transfers; none of them can see a promise.

**Target users.** Supplier SMEs with roughly 20–100 staff, 10–40 buyers, one bank credit line and at least one term loan, a bookkeeper and no finance team: light-manufacturing subcontractors, packaging, logistics, MRO and facility-services suppliers. This profile is a composite (spec v2 §3.1) and is labelled **INFERENCE**. Two informal SME conversations contradicted one of our assumed pain points (that the owner phones the bank when cash looks low), so we do not claim it. [TEAM: add any validated user interviews, or leave this as stated.]

### Core value and innovation

**Two features, one engine.**

- **Terms Guard (the credit the SME gives).** It compiles a buyer's free-text offer (Chinese or English, message plus attachments) into typed obligations with source spans. It projects them onto a dated daily cash, debt and forward-concession trajectory, prices every concession at the firm's own marginal cost of funds, and returns ACCEPT, REJECT, COUNTER, NO DEAL, NEEDS_OWNER_APPROVAL or NO_VERDICT. A formula and its inputs back every reason.
- **Debt Desk (the credit the SME takes).** It sizes the gap from the same trajectory, compares the owner's own facilities on all-in cost, time to cash and covenant effect (DSCR, leverage, clean-down), and picks the cheapest admissible plan. It also evaluates capex financing structures and prepares a borrower file for the owner.

Each feature sharpens the other. Concessions are priced at the SME's real marginal cost of debt. A known funding alternative lets the agent walk away (NO DEAL) and still cover the gap.

**What the agent actually does.** Inside three permission tiers, it accepts, counters, records commitments, draws and repays committed facilities, and submits invoices for financing. It refuses under injection. Every action is a typed operation in an append-only, hash-chained log.

**Innovation, stated honestly.** Nothing here is a new algorithm. Negotiation agents, cash-flow forecasting, loan marketplaces, covenant monitoring and rebate accrual all exist.

- **New application of known mechanisms.** The supplier's side of buyer-side negotiation automation, joined to the borrower's side of SME lending: control what the agent can *promise*, and the borrowing those promises cause.
- **One partial mechanism-level contribution.** A contingent concession is counted as a bounded maximum-exposure liability, and an unapproved facility as zero, on a dated liquidity trajectory that is used as a *hard acceptance boundary* together with the aggregate concession cap and the bank's covenants.
- **Integration.** Compiler, trajectory engine, funding router, covenant model, signed mandate, commitment lifecycle and an injection-resistant typed interface, all in one deterministic pipeline.

**Prior art we checked** (vendor claims unless stated; absence from our search is a search result, not a fact):

| System | What it does | Difference from TermsLedger |
| --- | --- | --- |
| Pactum | Buyer-side procurement agents negotiating payment days, discounts and rebates within buyer-set parameters | The other side of the table |
| MYbank 百灵2.0 | An agent that tailors financing plans for about 42 million micro merchants, using MYbank's own credit and bill products only | Lender-owned, single-provider; no link to the trade terms that created the need |
| MYbank AI票据管家 | Bill-discount price and timing advice | A lender tool for one funding source |
| Xero JAX Cash Flow Actions (beta, Jul–Aug 2026) | Spots cash-flow gaps and suggests plans (protect payroll, delay bills, bridge gaps) | Ledger-side forecasting; no offer intake, no mandate, no covenant-bounded acceptance |
| Cerebro Capital | US mid-market debt capacity, covenant compliance tracking and a lender marketplace | Mid-market, lender-network model; no offer intake |
| Capitalise | UK lender marketplace with credit data | Multi-provider comparison, but no forecast or acceptance boundary |
| Codat Working Capital Insights | Flags working-capital and refinancing needs to bank relationship managers | Tells the bank, not the SME |
| Lendio; Cardo AI; Fence | Loan matching; lender-side covenant monitoring; covenant-checked drawdowns for lenders | Start after the owner wants a loan, or serve the lender |

Our positioning line is therefore narrow: **none we found is owned by the supplier and bounded by its own mandate across both debt books.** [TEAM: re-check the Chinese-language prior art (supply-chain finance platforms, ERP vendors) before using this line on stage; spec v2 §9 marks it UNVERIFIED.]

**Claims we make** (spec v2 §13):

1. No model output alone can create a commitment, borrow or move money in this system. Every operation is built by code from a verifier verdict and gated by the executor. One live-mode weakness, where the model's contingency label can change a verdict, is disclosed as finding F-04 in section 04.
2. Every accepted, countered and refused offer carries a typed record with the failing predicate and its source spans.
3. The verifier never reads free text.
4. Contingent concessions count at maximum exposure, and uncommitted facilities at zero, by default.
5. Every funding choice shows its all-in rate, time to cash and covenant effect.

We do not claim "first", "best loan", "proof", "atomic", "financial advice", "bank-grade" or "cannot be fooled". TermsLedger is decision support under the owner's own limits; the owner decides and signs, and the agent never applies for, signs or guarantees a loan.

## 02 System Architecture

### Architecture diagram and component responsibilities

TermsLedger is a **modular monolith** (ADR-0001): one FastAPI service (`services/api`), one Next.js web app (`apps/web`) and one database. Shared contracts live in `app/domain/`. Modules talk only through those contracts, and import cycles are forbidden. The diagram's source is `docs/deliverables/architecture.mmd`.

<!-- figure: architecture.png | Figure 1. TermsLedger v2 architecture (rendered from architecture.mmd) -->
<!-- ascii-fallback -->
```
 UNTRUSTED TEXT                      OWNER AUTHORITY (signed / token)
 buyer msg, PO, term sheet           Mandate v1 (Ed25519)   Funding menu   Tier-2 approvals
 owner /nl request                         |                     |               |
        |                                  |                     |               |
        v                                  v                     v               |
 +---------------+  CompiledOffer   +-------------------------------------+      |
 | compiler/     |----------------->| verifier/ (reads no free text)      |      |
 | LLM or cache  | typed + spans    |  screen -> mandate -> predicates    |      |
 | + rules grammar| or abstain      |  -> Verdict + formulas + counters   |      |
 +---------------+                  +-------------------------------------+      |
        ^                              ^           ^            ^                |
        |                              |           |            |                |
 +---------------+           +--------------+ +-----------+ +------------+       |
 | nl/ intent,   |---------->| financial/   | | funding/  | | covenants/ |       |
 | sessions,     |           | daily cash,  | | grid      | | DSCR, lev, |       |
 | clarify/fix   |           | debt, fwd    | | router,   | | clean-down |       |
 +---------------+           | concessions  | | marginal  | +------------+       |
                             +--------------+ | cost      |                      |
                                              +-----------+                      |
        Verdict --> typed operations (built by code, never by the model)         |
                                   |                                             |
                                   v                                             v
 +----------------------------------------------------------------------------------+
 | operations/ executor: idempotency, dating, mandate signature/version/expiry,       |
 | Tier 3 refuse, circuit breaker, nonce + terms hash, Tier 2 queue, preconditions   |
 +----------------------------------------------------------------------------------+
                                   |
                                   v
      append-only hash-chained log + commitments + security events --> GET /evidence
                                   |
  counterparties/ buyer kernel --> egress/ guard --> template-filled outbound text
  apps/web (Next.js) displays server-formatted money; it never computes money
```

**Component responsibilities** (all under `services/api/app/` unless noted):

| Component | Responsibility | Trust |
| --- | --- | --- |
| `compiler/` | Turns buyer offers and lender term sheets into typed obligations or facility terms. Every obligation carries a span that must match the document exactly; otherwise the field is abstained. A zh + en rules grammar flags authority claims, data requests and unknown lenders. | Untrusted output; schema-validated |
| `financial/` | The daily cash recursion, debt ledger and forward-concession valuation, in integer fen, in conservative and expected modes | Trusted, deterministic |
| `covenants/` | DSCR, leverage and clean-down per facility definition, evaluated monthly on the projected state | Trusted, deterministic |
| `funding/` | The Debt Desk router: grid search for the cheapest admissible mix; marginal cost of funds; break-even early-pay discount; the terms extension priced as a loan | Trusted, deterministic |
| `mandate/` | Canonical serialisation, Ed25519 signing and verification with a pinned owner key, validity (expiry, revocation, version), tier computation, mandate predicates | Trusted; signed by the owner |
| `verifier/` | The verdict algorithm, reason codes, formulas and counters priced from the marginal cost of funds. It imports no text-bearing field (enforced by an AST test). | Trusted, deterministic |
| `operations/` | The executor: the **only** writer of commitments and operations. It computes the tier itself. | Trusted |
| `commitments/` | Commitment lifecycle (PROPOSED → ACCEPTED → ACTIVE → FULFILLED, or EXPIRED / REVOKED), terms hash, nonce, expiry | Trusted |
| `persistence/` | SQLAlchemy tables, Alembic migrations and `LedgerStore` (SQL and in-memory). The operations log is append-only and hash-chained. | Trusted |
| `counterparties/` | A deterministic buyer kernel with a hidden reservation, mock lenders, and a template verbaliser | Separate fixtures; can refuse |
| `egress/` | Scans every outbound text for protected values and planted canaries, and blocks the whole message on a hit | Trusted, last step |
| `nl/` | `/nl` harness: natural-language request → intent and typed slots → verifier → typed operations; multi-turn sessions with clarification, correction and fallback | Trusted orchestration; never skips the verifier |
| `security/` | Attack catalogue runner, security-event helpers, refusal templates | Test and audit |
| `capex/`, `borrower_file/`, `alerts/`, `whatif/` | Capex NPV and financing structures; a lender-ready borrower file built from verified state (HTML/DOCX, neutral styling); cash alerts and receipt reconciliation; a read-only what-if sandbox. All are feature-flagged. | Trusted, deterministic |
| `api/` | FastAPI routers, dependency wiring and authentication (owner token, agent key) | Trust boundary |
| `apps/web` | Next.js screens: Mandate, Inbox, Trajectory, Funding, Verdict, Capex, Ledger, plus Approvals, Security, Evidence, Alerts, Reconciliation and What-if; English and Chinese labels; a demo stepper | Displays server-formatted values only |

**One offer, end to end.**

1. A buyer message arrives. The compiler proposes obligations with spans, or abstains. A conflict between the body and an attachment gives `NO_VERDICT` with `CONFLICTING_SOURCES`.
2. The verifier's security screen logs and neutralises unknown senders, funding claims, unevidenced "we agreed last month" concessions and data requests. None of them can book anything.
3. The engine projects the conservative trajectory under the offer's bookable obligations.
4. The router prices any gap from committed facilities and emits the marginal cost of funds; forward concessions are valued at that rate.
5. The verifier tests every day and month against the mandate and covenants and returns a verdict with formulas. On REJECT it attaches counters priced from the marginal cost.
6. The buyer kernel answers within bounded rounds; NO DEAL is a first-class outcome.
7. Code, not the model, turns the verdict into typed operations. The executor gates them, runs Tier 1, queues Tier 2 for the owner, refuses Tier 3, and appends every outcome to the hash-chained log.

**Binding design decisions.** Money is integer fen and rates are integer basis points, with exact fractions in between and one half-up rounding per posting (ADR-0002). Funding is requested on the decision day and lands after its lead time, so hard constraints never rely on future availability (ADR-0003). The evidence export's hash covers `prev_hash + payload_json + result_json` only, so a cache-mode replay reproduces the same head hash (ADR-0004).

### Models, tools, data sources and external services

**Models.** The model is used only to (a) compile offers and term sheets into a strict JSON schema and (b) optionally classify an `/nl` request into one intent from a closed list when the rules parser finds nothing. It never decides, prices, negotiates or executes.

| Backend | Model | When |
| --- | --- | --- |
| `cache` (default) | Recorded outputs keyed by sha256(documents + prompt version) in `fixtures/compiler_cache/` | Tests, CI, the demo and the scenario runner. No network. |
| `claude` | `claude-sonnet-5-5` by default, `claude-opus-5-5` for hard compilations (Anthropic SDK) | `LLM_MODE=live`, opt-in |
| `deepseek` | `deepseek-flash` (OpenAI-compatible SDK) | `LLM_MODE=live`; a China-reachable backend |
| rules grammar | Deterministic regex and lexicon, Chinese and English | Always runs beside the model; the fallback when a backend errors, times out or returns invalid JSON |

The model sees only the documents and the output schema. Mandate values, facility limits, reservation values and other buyers' terms never enter a prompt; a test checks the compiler package's imports to keep it that way. Only a document hash and timing are logged per call, never the text.

**Tools (the agent's typed interface).** Every tool is an HTTP route with a strict Pydantic schema (`extra="forbid"`):

| Tool | Route |
| --- | --- |
| Natural-language harness | `POST /nl` |
| Offer intake and evaluation | `POST /offers`, `POST /offers/{id}/evaluate`, `POST /negotiate/{offer_id}` |
| Debt Desk | `POST /router/plan`, `POST /facilities/compile` (owner), `POST /capex/evaluate`, `POST /borrower-file` |
| Execution | `POST /operations`, `GET /approvals/queue`, `POST /approvals/{id}`, `POST /circuit/{id}/reset` |
| Read views and evidence | `GET /state`, `/mandate`, `/trajectory`, `/ledger`, `/audit`, `/evidence`; `POST /demo/reset` |

The typed operation kinds (`app/domain/models.py`) are:

- ACCEPT_OFFER, COUNTER_OFFER, REJECT_OFFER and RECORD_COMMITMENT;
- DRAW_FACILITY, REPAY_FACILITY, SUBMIT_INVOICE_FOR_FINANCING and RECEIVE_PAYMENT;
- APPLY_FOR_FACILITY, ADD_FACILITY, GENERATE_BORROWER_FILE and REQUEST_OWNER_APPROVAL;
- the Tier-3 kinds SIGN_PERSONAL_GUARANTEE, PLEDGE_COLLATERAL, ISSUE_EQUITY and CHANGE_MANDATE, which exist only to be refused.

No operation has a payee or account field. A request for a transfer to a third party (`TRANSFER_FUNDS`) is rejected as an unknown kind.

**Data sources (all synthetic).**

- `fixtures/scenarios/golden_sme.json`: the supplier's state. Cash ¥400,000; payroll ¥340,000 on day 12; supplier payment ¥120,000 on day 20; Receivable A ¥420,000 due on day 32; the funding menu below.
- `fixtures/scenarios/golden_sme.mandate.signed.json`: mandate v1, signed with a **published demo key** labelled DEMO ONLY. Floor ¥300,000; aggregate forward-concession cap ¥5,000; DSCR at least 1.25×; leverage at most 2.5×.
- `fixtures/offers/offers.yaml`: the 12 worked examples of spec v2 §8, a reworded EX01, and the FastCapital security message.
- `fixtures/counterparties/`: buyer profiles with hidden reservations, and mock lenders.
- `fixtures/golden/`: the independent oracle and its golden values.
- `services/api/evals/security/attacks.yaml`: 122 attacks.
- `services/api/evals/e2e/scenarios.yaml`: 37 scripted `/nl` tasks.

The synthetic funding menu (owner-approved; only the owner can add to it):

| Facility | Status | Price | Lead time |
| --- | --- | --- | --- |
| Bank credit line, ¥150,000 limit, 30-day clean-down | COMMITTED | 6.4% simple | same day |
| Invoice financing, onboarded platform, ¥350,000 limit | COMMITTED | 7.8% + 0.25% per 30-day period, 10.8417% all-in | 3 days |
| Buyer early-payment offer | COMMITTED | 1.2% discount | 2 days |
| Bank acceptance bill discounting (银票) | COMMITTED (no bill held in the base fixture) | 0.58% a year | 1 day |
| Government-guaranteed working-capital loan | NOT_APPLIED | 5.0% all-in | 21 days |
| Equipment term loan, 36 months | NOT_APPLIED | 5.6% | 14 days |
| Equipment lease, 48 months | NOT_APPLIED | 7.2% | 10 days |
| Equity | REFERENCE_ONLY (Tier 3) | n/a | n/a |

**External services.** No bank, lender, payment or blockchain API is used; lenders and the buyer are simulated. In live mode only, the Anthropic API or the DeepSeek API receives the inbound documents and the extraction schema. The deployment database is PostgreSQL on a Supabase Singapore pooler, with row-level security enabled on every table and no Supabase Auth or Storage.

**Libraries.** Python 3.12, FastAPI, Pydantic v2 (strict), SQLAlchemy 2 + Alembic, PyNaCl (Ed25519), structlog, python-docx, pypdf, openpyxl; Next.js 16, React 19, Tailwind 4, Recharts; pytest, hypothesis and Playwright for tests.

## 03 Agent Design

### Intent understanding, planning, tool use and state management

**Roles.** The pipeline has four roles: Compiler (the model, untrusted), Risk/Verifier (engine, covenants, verifier), Negotiator (counters and the bounded buyer rounds) and Treasurer (router and executor). Each role is a module with its own boundary, not a free-running LLM agent.

**Intent understanding (`nl/`).**

- A deterministic rules parser (zh + en lexicon) maps each request to one of 13 intents: EVALUATE_OFFER, NEGOTIATE, ACCELERATE_RECEIPT, FUND_GAP, REPAY_FACILITY, SHOW_STATUS, EXPLAIN, WHAT_IF, APPROVE, REJECT, COUNTERPARTY_MESSAGE, OUT_OF_SCOPE and AMBIGUOUS. It fills typed slots; every id is checked against the registry.
- Only when the rules find nothing is an optional LLM classifier consulted (cache mode by default). It may only *choose* an intent from a closed list and fill a strict slot schema. APPROVE, REJECT and COUNTERPARTY_MESSAGE are not in its vocabulary, and a canary in its output discards the answer.
- The actor comes from authentication, never from text. A request from a COUNTERPARTY is never parsed for intents: it is compiled and verified as an inbound message, and it can never execute anything.

**Planning.** A plan is a list of typed steps built by code from a verdict or a router plan:

- *Goal to plan* (worked example 12): "Get paid early on the Foshan invoice without giving anything away next quarter" becomes an early-pay counter at 0.85% with zero forward concession, and a fallback to invoice financing if the buyer refuses.
- *Multi-step funding*: draw the line, finance an invoice, repay on receipt.
- *Clarification*: "fund it" with two open gaps asks which one; an offer with no sender asks which buyer.
- *Correction*: "make it 0.8%" amends the pending plan; "1%" is refused because it is above the 0.88% break-even; "switch to invoice financing" swaps the source.
- *Out of scope*: a polite refusal plus the list of what the agent can do.

**Tool use.** Handlers call module functions (compile, evaluate, plan, negotiate), then send typed operations to the executor. Every operation carries an idempotency key derived from the session, turn and step. No handler can skip the verifier or build an operation from model output (Invariant 1).

**State management.**

- *Session state* (`nl/sessions.py`) holds only typed references: the last offer and verdict ids, a pending plan awaiting confirmation or correction, a pending clarification, and the operations each `request_id` produced. A retried request is replayed, not re-planned. Sessions expire after 30 minutes.
- *Financial state* is a frozen `FinancialState` plus the operations log. Contracts are immutable; a state change builds a new model.
- *Time* is an integer simulated day. A simulated clock drives expiry, and the executor refuses backdated or future-dated operations.
- *Commitments* follow a lifecycle state machine with a nonce, an expiry and a terms hash.

### Core algorithms and evaluation approach

**1. Trajectory recursion (`financial/`).** For each day *t* of the horizon:

`closing(t) = opening(t) + Σ inflows(t) − Σ scheduled outflows(t) − Σ interest, fees and repayments(t)`

- Within a day, inflows come first (receipts, early receipts, draws, advances), then scheduled outflows, then interest, fees and repayments. `closing(t)` is tested against the floor.
- **Conservative mode decides:** unconfirmed inflows are ignored, only COMMITTED facilities can be drawn (PENDING and NOT_APPLIED count as zero), and contingent concessions count at their maximum. Expected mode is shown beside it and never used for a hard constraint.
- Forward concessions go to a separate forward-concession ledger, valued over the concession horizon at the marginal cost of funds.
- Month *m* covers days 30(m−1)+1 to 30m and carries EBITDA, debt service and total debt for the covenants. The horizon always runs past the last repayment.
- Everything is integer fen. Interest is Actual/365 simple; invoice financing bills whole 30-day periods; each posting is rounded once, half-up (ADR-0002).

*Golden check.* With the full EX01 package accepted and no new funding, cash is **¥354,960** after day 20 and **¥254,960** on day 47: a **¥45,040** shortfall against the ¥300,000 floor. The committed marginal source cures it for **¥802.70**.

**2. Router grid search (`funding/`).** Each candidate is a list of funding actions run through the same engine. Its cost is whatever that trajectory posts (interest, fees and discounts, net of what the offer alone posts), so the router never computes cash itself.

- A candidate is admissible only if closing cash stays at or above the floor every day, no covenant is violated, every source's all-in rate is within the mandate's maximum APR, and new borrowing is allowed.
- Every source is requested on day 0 and lands after its lead time (ADR-0003). The search is over amounts, on a ¥10,000 grid.
- The search runs single-source fills; then pairs (a grid over the first source, the second filling the residual); then triples (the first source at capacity, a grid over the second, the third filling). Candidates whose probed lower-bound cost already exceeds the best plan found are pruned.
- On the golden gap of **¥360,000** before day 32, it selects the credit line (¥150,000, interest **¥841.64**) plus invoice financing (¥210,000, **¥1,871.30**): **¥2,712.94** in total. Taking the buyer's 1.2% discount would cost **¥5,040.00**, and the v1 optimum (line plus partial early pay) **¥3,392.25**. The guaranteed loan is inadmissible because it is not committed and lands on day 21, after payroll on day 12.
- **Marginal cost of funds:** the all-in annual rate of the cheapest COMMITTED, owner-approved source able to carry a *permanent* need. Clean-down excludes the line, so it is invoice financing at **10.8417%**.
- **Break-even early-pay discount:** a discount *d* is cheaper than the marginal source only if d/(1−d) < c, where c is that source's cost share for 30 days. So d = c/(1+c) = **0.88%**.

**3. Covenant tests (`covenants/`).** Evaluated exactly, per facility definition, every projected month:

- `DSCR = monthly EBITDA / monthly debt service`. Debt service is existing service plus interest and fees on facilities that count, plus scheduled amortisation.
- `Leverage = total debt / (12 × monthly EBITDA)`.
- **Clean-down:** the longest run of consecutive zero-balance days on a credit line must reach the facility's clean-down length.
- Golden values: DSCR **2.00×** at base and **1.92×** after funding the extension; leverage **1.53×** and **1.72×**. For capex, the 18-month loan fails DSCR in months 1–3 (**1.13×**) and the 36-month loan passes (**1.43×**, then **1.77×**).

**4. Verdict algorithm (`verifier/`).**

1. Offer status: conflicting sources or abstention give NO_VERDICT.
2. Security screen, never booked and logged as SecurityEvents: an unknown sender or funding claim gives `UNKNOWN_COUNTERPARTY`; an unevidenced prior concession gives `UNEVIDENCED_PRIOR_CONCESSION`; a data request gives `DATA_EXTRACTION_REFUSED` with a fixed reply.
3. Mandate validity: signature, version, expiry and revocation.
4. Conservative projection, the router plan and the marginal cost.
5. Predicates: minimum cash on every day, the aggregate and per-buyer forward-concession caps (including existing commitments), the immediate-discount cap, maximum APR, covenants every month, and Tier-3 clauses. A reserve breach that the committed plan can cure is reported as curable with its cure cost. Only FIRM gains may offset concessions.
6. Outcome: Tier 3 or an unknown counterparty gives REJECT; any hard violation gives REJECT with counters; a Tier-2 need gives NEEDS_OWNER_APPROVAL; otherwise ACCEPT.

Every violation carries a code, the day or month, the observed value, the limit, a `formula` and its `inputs`. The UI shows them verbatim.

*Golden check (Scene 1).* The EX01 package compiles to three spans: an immediate discount of ¥5,040.00, a recurring terms extension (¥207,123.29 of extra receivables) and a contingent rebate of up to ¥4,000. The forward-concession ledger is **¥26,455.62** against the **¥5,000** cap, so the verdict is **REJECT: AGG_CONCESSION_EXCEEDED; RESERVE_BREACH@47 (curable)**.

**5. Counters from the marginal cost (`verifier/counters.py`).**

- **Option A (early pay):** keep 45-day terms and no rebate; accept early settlement on up to **¥211,800** of face at the largest whole-5 bp rate below break-even, **0.85%**. The supplier's cost is the discount of **¥1,800.30** plus line interest of **¥841.64**: **¥2,641.94**.
- **Option B (price adjustment):** accept the 60-day terms with the smallest whole-5 bp price adjustment whose per-invoice amount covers the per-invoice funding cost: **0.45%**, **¥1,890** per invoice against ¥1,871.30.
- Bounded-extension and rebate-within-headroom counters are generated the same way.
- Outbound text is template-filled from an allow-list and passes the egress guard. It never contains the floor, a cap, a limit, the marginal rate or a reservation.

**6. Buyer kernel (`counterparties/`).** A deterministic kernel with a hidden reservation. Its surplus from a package is:

`surplus = discount received + declared benefits + rebate received + value of extra payment days − its own cost of paying early − price adjustments it pays`

It ACCEPTs when every reservation gate holds and the surplus reaches its reservation. Otherwise it COUNTERs one step toward, but never onto, its reservation. In its last round, or when rounds run out, it REJECTs. The kernel reads only a counter's public terms, never the supplier's cost or rationale. In Scene 1 it accepts Option A. In Scene 2 a different reservation refuses every counter within **3** rounds, giving NO DEAL; the router then funds the gap with the line plus invoice financing for ¥2,712.94.

**7. Capex mode (`capex/`).** For the synthetic ¥600,000 machine: NPV **¥380,885.77**, payback in month **31**. The 18-month loan (**¥34,830.60** a month) fails DSCR. The **36-month loan (¥18,144.62 a month, interest ¥53,206.14) is selected**. The 48-month lease costs **¥39,121.18** more in interest. Leverage is **2.08×**, or **2.28×** with the extension also funded. The loan is Tier 2, so the application and borrower file are queued for the owner.

**Evaluation approach.**

| What is tested | How | Current result |
| --- | --- | --- |
| Engine, router, covenants and capex exactness | An independent oracle (`fixtures/golden/compute_golden.py`, written separately from the engine) produces `golden_values.json`; the engine, router, verifier and capex tests assert every value to the fen | All golden values reproduced (see 05 for the test run) |
| Worked examples | The 12 examples of spec v2 §8, plus EX01B, as verdict tests | Every `offers.yaml` verdict reproduces |
| Wording invariance | EX01B, the same economics in other words, must give the same verdict; paraphrase tests in `tests/compiler` | Same verdict (scripted task S03) |
| Router versus a naive baseline | 6 designed cases against "draw the line first, then the cheapest next source" (`tests/funding/test_designed.py`) | The router is cheaper in 3 and admissible where the baseline is not in 3 |
| Task completion | 37 scripted `/nl` tasks (`scripts/run_scenarios.py`), each from a fresh reset, checking intent, verdict, codes and operation kinds and statuses | **37/37 passed** (see the Execution Evidence document) |
| Security | 122 attacks run end to end through the real API, plus two hypothesis fuzzers | 0 harm on the 118 catalogue attacks; 4 documented findings (see 04) |
| Boundaries and money invariants | Boundary tests at every cap and floor, and at cap ± 1 fen; hypothesis property tests on money, the trajectory, operations, commitments and the egress guard | Included in the test run in 05 |

The full validation gate of spec v2 §14 has **not** been run yet in its held-out form. That covers E2 (20 held-out offers by non-builders against a form and a bare LLM), E9 (20 held-out router scenarios against the line-first baseline), E5 and E8. We do not claim results for them. [TEAM: run E2 and E9 and record the results here before submission, or leave this sentence as it is.]

## 04 Security Design

### Tiered permissions and confirmation for sensitive actions

**Who can act.**

- The **owner** is recognised only by the `X-Owner-Token` header, compared in constant time.
- The agent's own tool channel is recognised by the `X-Agent-Key` header.
- A body field such as `requested_by: OWNER` confers nothing: it is downgraded before parsing.
- Counterparties can only submit documents or talk on `/nl` as COUNTERPARTY, which compiles and verifies but never executes.
- Outside demo mode (`DEMO_MODE=0`), the owner and agent routes fail closed (HTTP 503) until real credentials are set, and every refused credential is logged as a `PRIVILEGE_ESCALATION` security event.

**Three tiers, computed by the executor** (`app/mandate/tiers.py`). A caller-supplied tier is rejected as an unknown field, and extra facts can only raise the tier.

| Tier | Operations | Outcome |
| --- | --- | --- |
| **Tier 1: autonomous inside the mandate** | Accept, counter or reject a verified offer; record a commitment; draw on or repay a COMMITTED, owner-approved facility within its limit; submit an eligible invoice to the onboarded financing facility; receive a payment | EXECUTED if every gate passes |
| **Tier 2: owner approval** | Apply for a facility; generate the borrower file; accept a commitment that changes payment terms; any single commitment above ¥100,000; draw on any facility that is not COMMITTED and owner-approved; an owner-originated AddFacility | PENDING_APPROVAL, queued with a reason |
| **Tier 3: never** | Personal guarantee, pledging collateral, issuing equity, changing the mandate, adding a facility by anyone but the owner, any unknown operation type | REFUSED for every caller, the owner included |

**Confirmation.** A Tier-2 operation is stored as its exact canonical JSON. When the owner approves, the executor re-runs every gate against the mandate then in force. An approval given after a revocation is therefore refused, and an approved Tier-3 operation stays refused.

**Verification.** Every operation passes the same gates, in order:

1. idempotency key (`DUPLICATE`);
2. dating (`STALE_OPERATION`, `REPLAY`);
3. mandate signature, pinned key, expiry, revocation and version;
4. Tier 3;
5. counterparty circuit breaker (three refusals in seven days; only the owner can reset it);
6. for acceptances, the commitment must exist and be unrevoked, the nonce must be single-use and match, the commitment must not be expired, the terms hash and mandate version must match, and a verifier verdict must back the terms;
7. Tier 2 queue;
8. per-kind preconditions.

**Record.** Every outcome, refusals and duplicates included, is appended to a hash-chained log: `entry_hash = sha256(prev_hash + payload_json + result_json)`. `scripts/verify_evidence.py` recomputes the chain with the standard library alone.

**Rollback.** The log is append-only, so a mistake is corrected by a logged compensating operation: repay a draw, settle an advance on receipt, revoke a commitment through its lifecycle, decline a queued request, or revoke the mandate. A refused or pending operation leaves state unchanged; the attack suite checks this. A typed owner-only `RevokeCommitment` operation is not built yet (R-6).

### Protection against prompt injection, privilege escalation and privacy leakage

**Prompt injection: architecture first, detection second.**

- Counterparty text only ever becomes a `CompiledOffer`: typed obligations whose spans must match the source exactly. The schema has no field for an operation, an approval, a tier, a reply or a new facility.
- The verifier reads typed rows only; no text field reaches `verifier/`, `funding/`, `covenants/`, `mandate/` or `financial/` (AST-enforced test).
- A claimed prior concession with no matching ledger commitment is never booked. A lender named in a message becomes an `UnsolicitedFundingClaim` and a security event, never a facility.
- The rules grammar flags override attempts, fake SYSTEM lines, role-play, encoded text and authority claims in both languages. Detection is logged, but refusal does not depend on it.
- If a model backend fails, times out or returns invalid JSON, the deterministic rules grammar takes over.

**Privilege escalation.** Tiers are enforced by code, never by prompts. The executor trusts no caller-supplied tier, actor or approval. Self-approval, circuit resets by the agent, forged or edited mandates, reused or guessed nonces and backdated operations are all refused and logged.

**Privacy leakage.**

- The compiler never sees the mandate, state, funding menu or reservations.
- Outbound text is template-filled from an allow-list. Data requests get one fixed reply that discloses nothing.
- The deterministic egress guard scans every outbound text for protected values in their usual forms (¥, k, 万, Chinese numerals, percentages, ratios, company names and role aliases) and for four planted canaries. It blocks the whole message on a hit.
- Read routes (`/state`, `/mandate`, `/trajectory`, `/ledger`, `/audit`, `/evidence`) require the owner token.
- Cache mode sends nothing off the machine. In live mode only the inbound documents and the schema leave it.

**Measured results** (`services/api/evals/security/latest_report.md`; 122 attacks, `LLM_MODE=cache`):

| Metric | Catalogue (118 attacks) | Documented findings (4 attacks) |
| --- | --- | --- |
| Unauthorised operations executed | **0** | 4 |
| Facilities added by non-owners | **0** | 0 |
| Concessions booked from unevidenced claims | **0** | 0 |
| Money moved by attacks | **¥0.00** | ¥460,000.00 of ledger movement |
| Protected values disclosed in outbound text | **0** | 0 |
| Protected values readable without the owner token | **0** | 0 |
| Canaries tripped in outbound text | **0** | 0 |

- **Attack success rate on the catalogue:** 0.0% for injection (39 attempts), exfiltration (21), privilege escalation (20) and replay (20).
- **Detection rate:** 94.3% of all 122 attacks produced a SecurityEvent or a refusal code. **SecurityEvent rate:** 53.3%.
- The four documented findings are disclosed, not hidden. The suite runs each as a strict expected failure:
  - F-01: an operation's effects and its log entry are not one transaction (FR-06);
  - F-02: RECEIVE_PAYMENT is Tier 1 for any requester (SE-07);
  - F-04: in live mode, a gain's contingency relies on the model's label (FR-05);
  - F-07: commitments are bound to the stored offer, not to the verdict's obligations (TC-02).

  Each has a planned fix, listed in the Security Self-Assessment.

## 05 Deployment and Testing

### Environment, deployment instructions, test cases and known limitations

**Environment.**

- API: Python 3.12 with `uv`; SQLite for local development and tests; PostgreSQL 16 in Docker Compose or on Supabase (Singapore).
- Web: Node with `pnpm`.
- The default `LLM_MODE=cache` needs no network or API key.
- Target deployment: one Docker Compose stack (web, api and postgres) on one VM in Hong Kong or Singapore. [TEAM: confirm the VM, its URL and a reachability test from mainland China.]

**Run locally** (from the repository root):

```
cd services/api && uv sync && uv run uvicorn app.main:app --reload     # API on :8000 (cache mode, demo credentials)
cd apps/web && pnpm install && NEXT_PUBLIC_API_MODE=live pnpm dev       # UI on :3000; omit the variable for offline mock mode
cd services/api && uv run pytest                                        # API tests, offline
python3 scripts/run_scenarios.py --inproc                               # the 37 scripted /nl tasks and evidence
```

**Deploy.**

1. Copy `infra/.env.example` to `infra/.env` and set `POSTGRES_PASSWORD`, `OWNER_TOKEN` and `AGENT_KEY` (random values). Optionally set `LLM_MODE=live` with `ANTHROPIC_API_KEY` or `DEEPSEEK_API_KEY`.
2. Run `docker compose -f infra/docker-compose.yml up --build`.
3. The compose file sets `DEMO_MODE=0`, so the published demo credentials are rejected. It binds the API to `127.0.0.1:8000`, to sit behind a TLS reverse proxy.

**Test cases.** `uv run pytest --co` collects **2,200** API tests:

| Area | Tests | Area | Tests |
| --- | --- | --- | --- |
| egress guard | 925 | covenants | 32 |
| compiler | 199 | capex | 22 |
| operations (executor) | 166 | api | 21 |
| security (attacks + fuzzers) | 128 | borrower file | 19 |
| verifier | 113 | alerts | 18 |
| nl harness | 96 | money | 7 |
| commitments | 90 | fixtures | 4 |
| counterparties | 89 | persistence | 62 |
| mandate | 69 | financial engine | 52 |
| whatif | 44 | funding router | 44 |

**Latest full run** (`uv run pytest`, `dev` at 3ac4c39, 1 Oct 2026): **2,175 passed, 4 expected failures, 21 failed**, in 194 s.

- The 4 expected failures are the four documented security findings (F-01, F-02, F-04, F-07). Each runs as a strict xfail, so a silent fix or regression is caught.
- The 21 failures are API tests (alerts, borrower file, capex, `/nl` approvals and three security tests) written before commit 3ac4c39 put these routes behind the owner token and agent key. They now receive HTTP 401 where they expected a result.

[TEAM: update those tests, re-run, and replace this paragraph with the green result before submission.]

The web app adds 19 Playwright test declarations (demo walk in mock and live modes, API contract, alerts, what-if, responsive layout) and a unit test that checks the mock data against `golden_values.json`.

**Known limitations.**

- **Open security findings:** F-01, F-02, F-04 and F-07 (see 04). The Security Self-Assessment also lists F-08 to F-12 (HTTP 500 on a replayed approval, compiler flags not yet logged as events, rules-grammar coverage gaps, a textual-SQL gap in the append-only guard, audit view fragility) and R-1 to R-6 (egress coverage for spelled-out numbers, single-operator key custody, Tier-1 blast radius, no channel authentication, trust in the in-process actor, no typed commitment revocation).
- **Semantic risk remains.** A schema-valid obligation can still carry the wrong contingency. Conservative defaults bound the damage but do not remove it.
- **Everything is simulated.** Lenders and the buyer are mocks, facilities and rates are synthetic, and there are no real bank integrations or loan applications.
- **Covenant definitions differ by lender.** We test the defined covenants "under this definition", not bank-grade compliance.
- **Not yet available:** capex is not an `/nl` intent, and the after-signing extension (statutory due dates, late interest, receivable confirmation) is feature-flagged off.
- **Held-out validation (E2, E9) is not yet run** (see 03).
- **Live-mode calibration:** DeepSeek tends to mark a whole package CONTINGENT. The demo and the evidence use cache mode.
