# FLOW (流) / TermsLedger v2: Technical Document

2026 FINTECHATHON · International AI Track | Technical Document

| Field | Value |
| --- | --- |
| Team name | [TEAM: team name] |
| Competition track | International AI Track, Topic E: SME Finance Copilot [TEAM: confirm the exact track wording the organisers expect] |
| Submission date | [TEAM: submission date, on or before 20 Oct 2026] |

**FLOW (流)** is an AI working-capital agent owned by a small Chinese supplier; **TermsLedger** is the name of its engine and repository. It manages both of the supplier's debt books under limits the owner has signed. **Terms Guard** covers the credit the supplier gives buyers through payment terms, discounts and rebates. **Debt Desk** covers the credit it takes from lenders to survive those terms. The language model only reads text. Deterministic code decides and executes. This is a simulation: lenders, the buyer and the bank feed are simulated, no real payment is made, and the system makes no claim of bank-covenant compliance.

**What this document describes.** The code on `dev` at commit `0f92d433` (16 Oct 2026). Paths are relative to `services/api/app/` unless they start with `apps/`, `docs/`, `fixtures/`, `scripts/` or `services/`. Work that is built but not yet merged into `dev` is listed separately as "in integration" (section 01) and is not described as shipped anywhere else.

**Data notice.** Every company, buyer, lender, rate, amount and message is a **synthetic fixture** (`fixtures/`). Figures come from `fixtures/golden/golden_values.json` (an independent oracle, `fixtures/golden/compute_golden.py`), from the reports committed under `services/api/evals/` (each names its run date and commit), from commands run on `0f92d433` on 16 Oct 2026 for this document (the test collection and the attack catalogue, section 05), from the gate recorded in the `0f92d433` merge message, or from the contract-reading harness output named in section 03. Each figure names its source. No real customer, bank or transaction data is used. The source is at [TEAM: public repository URL and the commit or tag submitted].

## 01 Project Overview

### Problem, target users and selected topic

**Selected topic.** International AI Track, **Topic E: SME Finance Copilot** (financing and cash-flow support for small businesses), under the 2026 theme "AI as a Financial Participant".

**The problem.** Large buyers now negotiate payment terms through software. Pactum's public material, for example, describes payment-term, discount and rebate agents that operate "within parameters you define". Lenders approve small-business loans by model in seconds (MYbank, WeBank). The supplier in the middle usually has neither: an owner reads a chat message at night and decides alone whether to accept 60-day terms and, separately, whether to borrow.

The reframe that drives the product: **a payment-term extension is an interest-free loan from the supplier to the buyer, and the supplier funds it by borrowing.** On the synthetic fixture (a ¥420,000 monthly invoice to the largest buyer):

- moving that buyer from 45 to 60 days going forward ties up **¥210,000.00** of extra receivables, permanently;
- funding that on the cheapest committed source that can carry a permanent need (invoice financing at **10.8417%** all-in, since the credit line's clean-down rules it out) costs **¥1,871.30 per invoice**, or **¥24,326.92** over the 13 invoices dated inside a 365-day window (a monthly service of ¥1,897.29);
- the extension moves ¥0 today, so it passes every spend cap. Wallet-style controls (spend caps, allowlists, signer policies) guard transfers; none of them can see a promise.

**Target users.** Supplier SMEs with roughly 20–100 staff, 10–40 buyers, one bank credit line and at least one term loan, a bookkeeper and no finance team: light-manufacturing subcontractors, packaging, logistics, MRO and facility-services suppliers. This profile is a composite (spec v2 §3.1) and is labelled **INFERENCE**. Two real SME interviews contradicted one of our assumed pain points (that the owner phones the bank when cash looks low), so we do not claim it. [TEAM: add any validated user interviews, or leave this as stated.]

### Core value and innovation

**Two features, one engine, and a buy side.**

- **Terms Guard (the credit the SME gives).** It compiles a buyer's free-text offer (Chinese or English, message plus attachments) into typed obligations with source spans, projects them onto a dated daily cash, debt and forward-concession trajectory, prices every concession at the firm's own marginal cost of funds, and returns ACCEPT, REJECT, COUNTER, NO DEAL, NEEDS_OWNER_APPROVAL or NO_VERDICT. A formula and its inputs back every reason.
- **Debt Desk (the credit the SME takes).** It sizes the gap from the same trajectory, compares the owner's own facilities on all-in cost, time to cash and covenant effect (DSCR, leverage, clean-down), and picks the cheapest admissible plan. It also screens capex financing structures and prepares a borrower file for the owner.
- **The buy side (ADR-0013, behind `FEATURE_CAPEX_CONTRACTS`, off by default).** When the SME is the *buyer* of equipment, a vendor contract is read like any other contract, code derives its payment schedule from the confirmed reading and the owner's timeline, and only an owner-approved `CommitPurchase` books those payments (section 03, algorithm 9).

Each feature sharpens the other. Concessions are priced at the SME's real marginal cost of debt, and a known funding alternative lets the agent walk away (NO DEAL) and still cover the gap.

**What the agent does.** Inside three permission tiers it counters and rejects offers, accepts the one kind of offer it can prove it has read completely, records commitments, draws and repays committed facilities, and submits invoices for financing. Everything else waits for the owner. Every action is a typed operation in an append-only, hash-chained log.

**The agent stays on duty after the decision.** The books are current: every accepted commitment changes every later projection, and a simulated clock moved only by the owner (`POST /clock/advance`, ADR-0006 as amended for SEC-09) closes days one by one. Receipts come only from the bank feed or the owner, so a promised payment that was not made is visible; a partial payment leaves the residual open; reconciliation reports each promised early payment as AWAITED, RECEIVED, LAPSED or SETTLED_OTHERWISE. In chat the agent speaks first (`POST /nl/opener`): it names what needs the owner, proposes a cure inside the mandate with its cost, effective annual rate and landing day, and runs it only on a direct "go ahead", as exactly the operations shown. A cure above the mandate's rate ceiling is queued and runs only when the owner approves it as a second step. On the golden books the path is: Counter A agreed, the early payment of ¥255,013.80 on day 2, the clock to day 34 with ¥162,800.00 unpaid, the opener (a ¥200,000.00 advance on invoice RI:BUYER-1:2, cost ¥1,782.19, 32.5% a year for 10 days, above the 15% ceiling), "go ahead" (queued as APR-000001), "approve APR-000001" (cash lands on day 37), the late residual on day 36, the financed invoice paid on day 47 and its advance repaid from the receipt, the proposal to repay the ¥149,986.20 line draw, reconciliation, and a 14-entry hash chain (`scripts/demo_run.py`, recorded 3 Oct 2026; it now needs `DEMO_MODE=1`, commit `dfefea11`).

**What the owner sees (dev on 16 Oct 2026).** The browser computes no money and no date words: every amount and every "when" is a display string the server writes in English and Chinese (INVARIANT 13; `api/presentation.py`, `api/engine_zh.py`).

- **A landing page** at `/welcome` ("Access FLOW" for a returning owner, the setup for a new one; merge `8e80b8bc`, `apps/web/components/landing/`). It asks nothing of the server.
- **The shell** has eight rail entries: Home, Deals, Documents, Cash, Sandbox (what-if), Loans (capex), Receivables and Activity; the account menu adds Set up your books, Limits and Trust (`apps/web/components/app-shell.tsx`). A slide-over chat panel is on every page.
- **Home** shows the cash card with a funding ring, one recommendation that opens the plan on Cash, the worklist (each deal row opens Deals), upcoming movements and what each customer owes (merge `a6de32a2`; `docs/handover/19_reconciliation_2026-10-16.md` section 1).
- **Deals, redesigned on 15 Oct (#160, merge `31058785`; `apps/web/DESIGN.md`, "Deals ... the redesign of 15 October").** The list groups deals into tabs (Needs you, Waiting, Agreed) and files agreements by money owed: **Payment late**, **Awaiting payment**, **Closed**, with one row per agreed deal; a row moves only because money moves. A deal opens as its own page with "All deals" and a previous/next walk. Before agreement the page leads with **"FLOW recommends"** (the reply, the cash against the minimum, what it costs, who decides, why not accept as asked), then **"Your choices"**, one table with the buyer's request ("Accept their request") and each reply as columns and terms, lowest cash, cost, funding needed and who decides as rows, then why a reply is withheld. **Cash impact** draws one thin bar per choice to its lowest cash against the dashed minimum, and exactly two day-by-day lines (the request and the chosen reply). The send review states what sending does, its cost and **what happens if the buyer refuses** (the no-deal plan, read and not run). An agreed deal shows its tracker and lifecycle strip.
- **Cash** puts the plan first, then the chart and the funding options; **Receivables** lists customers first; **Activity** adds a reconciliation tab.

**Set up your books (`docs/adr/0013-set-up-your-books.md`).** A new owner types the starting position in six steps (business and cash; ways to borrow and loans; customers and invoices already out; bills; limits; review). Code parses every amount from the typed text and builds the `FinancialState` and the mandate (`setup/__init__.py`); a contract can suggest a customer's row but the owner's figures are what count. Opening is one owner act (`POST /setup/open`): the owner re-types the sign-in token, the limits are signed, and one `OPEN_BOOKS` entry starts a fresh chain. It is allowed only on untouched blank books and only in demo mode (section 04).

**Decisions have a lifecycle, kept in a record (ADR-0011).** The record derives each deal's and each funding decision's state from the stores the engine already fills, plus three append-only facts that cannot be re-derived (when a verdict was made, which counter was sent, what the owner was shown when an action was queued). A send is bound to the verdict, the counter and the books version the owner saw; a mismatch is refused and creates nothing (section 03, algorithm 8).

**Contracts the owner confirms (ADR-0012).** The owner uploads a signed buyer contract, a lender agreement or (with the flag) a vendor contract; the agent reads it with every term beside its quoted clause, labelled "AI-generated, for reference", and the owner confirms or rejects it. The decision is an owner-only entry on the hash chain, bound to the hash of the text shown, and it changes no books. **Chinese contracts are now read and measured**: on a fictional, answer-keyed set of 30 readable Chinese contracts, overall field accuracy rose from 59% to 66% (section 03, evaluation).

**Strategy answers, behind flags and read-only.** What the owner can offer a named buyer (the Safe Deal Envelope), what earlier cash is worth (the cash price curve) and whom to chase first are computed on labelled copies of the books and change nothing. Each flag defaults to off (`FEATURE_ENVELOPE`, `FEATURE_PRICE_CURVE`, `FEATURE_COLLECTIONS_WORTH` in `config.py`); off, the routes answer 403 `FEATURE_DISABLED` (`docs/STRATEGY_MVP_REPORT.md` section 1).

**Innovation, stated honestly.** Nothing here is a new algorithm. Negotiation agents, cash-flow forecasting, loan marketplaces, covenant monitoring and rebate accrual all exist.

- **New application of known mechanisms.** The supplier's side of buyer-side negotiation automation, joined to the borrower's side of SME lending: control what the agent can *promise*, and the borrowing those promises cause.
- **One partial mechanism-level contribution.** A contingent concession is counted as a bounded maximum-exposure liability, and an unapproved facility as zero, on a dated liquidity trajectory used as a *hard acceptance boundary* together with the aggregate concession cap and the covenants.
- **Autonomy requires proof (ADR-0005).** The agent may accept a counterparty's offer alone only when the compiler can show it read every figure and request in the message. The default is the owner.
- **Integration.** Compiler, trajectory engine, funding router, covenant model, signed mandate, commitment lifecycle, decision record and an injection-resistant typed interface in one deterministic pipeline.

**Prior art we checked** (vendor claims unless stated; absence from our search is a search result, not a fact):

| System | What it does | Difference from FLOW |
| --- | --- | --- |
| Pactum | Buyer-side procurement agents negotiating payment days, discounts and rebates within buyer-set parameters | The other side of the table |
| MYbank 百灵2.0 | An agent that tailors financing plans for about 42 million micro merchants, using MYbank's own credit and bill products only | Lender-owned, single-provider; no link to the trade terms that created the need |
| MYbank AI票据管家 | Bill-discount price and timing advice | A lender tool for one funding source |
| Xero JAX Cash Flow Actions (beta, Jul–Aug 2026) | Spots cash-flow gaps and suggests plans | Ledger-side forecasting; no offer intake, no mandate, no covenant-bounded acceptance |
| Cerebro Capital | US mid-market debt capacity, covenant tracking and a lender marketplace | Mid-market, lender-network model; no offer intake |
| Capitalise | UK lender marketplace with credit data | Multi-provider comparison, but no forecast or acceptance boundary |
| Codat Working Capital Insights | Flags working-capital needs to bank relationship managers | Tells the bank, not the SME |
| Lendio; Cardo AI; Fence | Loan matching; lender-side covenant monitoring; covenant-checked drawdowns | Start after the owner wants a loan, or serve the lender |

Our positioning line is therefore narrow: **none we found is owned by the supplier and bounded by its own mandate across both debt books.** [TEAM: re-check the Chinese-language prior art (supply-chain finance platforms, ERP vendors) before using this line on stage; spec v2 §9 marks it UNVERIFIED.]

**Claims we make** (spec v2 §13):

1. No model output alone can create a commitment, borrow or move money. Every operation is built by code from a verifier verdict, an owner's typed entry or an owner-confirmed record, and gated by the executor.
2. After ADR-0005, no misread message was accepted without the owner, across our three held-out sets and both compiler paths (section 03). Free-text understanding itself is still imperfect, and we say by how much.
3. Every accepted, countered and refused offer carries a typed record with the failing predicate and its source spans.
4. The verifier never reads free text.
5. Contingent concessions count at maximum exposure, and uncommitted facilities at zero, by default.
6. Every funding choice shows its all-in rate, time to cash and covenant effect.
7. Confirming a document never changes the books. The one path from a document to the books is a vendor contract's payment schedule, derived by code and booked only by an owner-approved `CommitPurchase` (ADR-0012, ADR-0013).
8. The strategy answers are read-only and flagged off by default.

We do not claim "first", "best loan", "proof", "atomic", "financial advice", "bank-grade", "safe by construction", "cannot be fooled" or compliance with any bank's covenants. The contract-reading figure is on a fictional set, not on real contracts. The checks screen the obligations that were entered, not the whole business; a plan is the cheapest within the bounded search; the bullet-loan DSCR is a reserve-coverage reading; the hash chain is internally checkable only. FLOW is decision support under the owner's own limits; the owner decides and signs, and the agent never applies for, signs or guarantees a loan.

**In integration, not on `dev`** (checked with `git log origin/dev` on 16 Oct 2026; none is described as shipped elsewhere in this document):

- **Buyer messages** (branch `int/buyer-message`): the owner drafts and copies a verified counter to the buyer and records the buyer's answer; it carries an ADR-0011 addendum on that branch. The design question is open in `docs/NEGOTIATION_COMMUNICATION_HANDOFF.md` section 9.
- **Early-pay base rounding** (branch `fix/counter-base-rounding`): rounding the early-pay counter's face so it no longer states the owner's funding gap (the remaining part of R-10, section 04).
- **Live readers with a model-versus-rules cross-check** (branch `int/live-readers`): live mode replays recorded readings first, and a model's reading of a buyer message that disagrees with the rules grammar's abstains.

## 02 System Architecture

### Architecture diagram and component responsibilities

FLOW is a **modular monolith** (ADR-0001): one FastAPI service (`services/api`), one Next.js web app (`apps/web`) and one database. Shared contracts live in `domain/`; modules talk only through them, and import cycles are forbidden. The diagram's source is `docs/deliverables/architecture.mmd`.

<!-- figure: architecture.png | Figure 1. FLOW / TermsLedger architecture on dev 0f92d433 (rendered from architecture.mmd) -->
<!-- ascii-fallback -->
```
 UNTRUSTED INPUT                       EDGE (api/)                              OWNER AUTHORITY
 buyer msg / PO / term sheet    -->  auth: owner token | agent key |        Mandate (Ed25519, 3 tiers)
 uploaded contract (buyer,           bank-feed key | buyer key;             Funding menu (owner adds)
   lender, vendor)                   DEMO_MODE off unless set               Approvals queue (owner)
 chat (/nl)                          intake: 5 docs x 4,000 chars;          Setup: /setup/open (demo mode)
                                     buyer budget 5/day (R-10)
                                     agent view for the agent key (R-11)
        |                                       |                                  |
        v                                       v                                  v
 +-------------+ CompiledOffer  +----------------------------------------------------------+
 | compiler/   |--------------->| verifier/ (reads no free text): screen -> mandate ->       |
 | cache | LLM | typed + spans, |  predicates -> early-pay tests -> autonomy -> verdict     |
 | + rules     | coverage proof |  + counters (each re-checked)                             |
 +-------------+ or abstain     +----------------------------------------------------------+
        ^                          ^ books/ current books   ^ funding/ router,  ^ covenants/
        |                          | financial/ trajectory   | admission, rates  | DSCR, leverage
 nl/ intents, consent grammar      | clock/ (owner only)     |                   | clean-down
        |                          |                         |                   |
        +---- Verdict -> typed operations (built by code) ---+-------------------+
                                   |
                                   v
 +------------------------------------------------------------------------------------------+
 | operations/ executor: idempotency, dating, mandate, Tier 3, circuit, accept binding and    |
 | re-verification, Tier 2 queue, admission; one unit of work, compare-and-swap, 8 retries    |
 +------------------------------------------------------------------------------------------+
        |                                                         |
        v                                                         v
 append-only hash-chained log --> GET /evidence           counterparties/ kernel --> egress/ guard
                                                           --> template-filled outbound text
 BESIDE THE ENGINE (the engine imports none of them):
  ingest/ + contracts/ + deals/: document -> record -> owner confirms (log only, no books)
  capex/schedule + CommitPurchase (flag): confirmed vendor contract -> payments, owner-approved
  decisions/ (ADR-0011) | strategy/ (flags off) | health/, lending/ (read-only) | setup/ (pure builder)
  api read caches: exposure answers, offer picture, no-deal plan (per books, cleared on reset)
 apps/web (Next.js): landing, Home, Deals, Documents, Cash, Sandbox, Loans, Receivables,
  Activity, chat panel, owner sign-in; displays server-written sentences and money only
```

**Four roles.** Each is a module with its own boundary, not a free-running LLM agent:

| Role | Modules | May do | May not do |
| --- | --- | --- | --- |
| **Compiler** (the only model-backed role, untrusted) | `compiler/` | Turn text into typed obligations, facility terms or contract terms with exact spans; flag authority claims, data requests and unknown lenders; say whether it can prove coverage | See the state, mandate, funding menu or reservations; emit an operation, a tier or a reply |
| **Risk / Verifier** | `books/`, `financial/`, `covenants/`, `verifier/` | Project the trajectory on current books, test the mandate and covenants, return a verdict with formulas | Read free text |
| **Negotiator** | `verifier/counters.py`, `counterparties/`, `egress/` | Price counters from the marginal cost of funds, run bounded rounds with the buyer kernel, fill outbound templates | Reveal the floor, caps, menu or reservation values |
| **Treasurer** | `funding/`, `operations/` | Find the cheapest admissible funding plan, and execute typed operations through the tier gates | Use an uncommitted facility for a hard constraint; execute Tier 3 |

**Component responsibilities:**

| Component | Responsibility | Trust |
| --- | --- | --- |
| `compiler/` | Buyer offers, term sheets and contracts become typed obligations, facility terms or contract terms. Every value must sit inside a quote found verbatim in the document, and code parses it; otherwise the field is abstained. The zh + en lexicon flags authority claims, data requests and unknown lenders on every backend. The coverage proof (`coverage.py`) sets `autonomy_eligible`. Contract mode (`contract.py`, `contract_parsing.py`, `contract_checks.py`) chunks at headings, derives dates and cross-checks figures | Untrusted output; schema-validated |
| `books/`, `clock/` | `books.current_books` is the one set of current books (ADR-0006). `Runtime.advance_to` is the only way time moves: it posts the day's flows, lands funding lots, posts instalments and the existing loan's payments, writes accepted terms onto new invoices (ADR-0009), expires lapsed commitments and logs one `ADVANCE_CLOCK` entry. It never records a receipt | Trusted, deterministic |
| `financial/` | The daily cash recursion, debt ledger, funding lots (`lots.py`), existing-debt schedule (`debts.py`), invoice terms (`invoices.py`) and forward-concession valuation, in integer fen, conservative and expected modes; `cashpath.py` is the fast cash-only projector | Trusted, deterministic |
| `covenants/` | DSCR, leverage and clean-down per facility definition, on the projected months | Trusted, deterministic |
| `funding/` | The router (`search.py`, `router.py`), marginal cost and break-even, rates (`rates.py`), leg ordering (`legs.py`) and admission (`admission.py`: the router's engine and predicates on today's books, used by the executor) | Trusted, deterministic |
| `mandate/` | Canonical serialisation, Ed25519 signing and verification with a pinned owner key, validity, tier computation (`tiers.py`) | Trusted; signed by the owner |
| `verifier/` | The verdict algorithm, binding (`bind.py`), the security screen, reason codes, formulas and counters. It imports no text-bearing field (AST test) | Trusted, deterministic |
| `operations/`, `commitments/` | The executor, the **only** writer of commitments and operations, and with the clock the only writer of the books outside set-up and the demo reset; the commitment lifecycle with nonce, expiry and terms hash | Trusted |
| `persistence/` | SQL and in-memory `LedgerStore`; migrations `0001`–`0008` (RLS in `0002`, append-only triggers in `0003`, decision facts `0006`, contract records `0007`, customer inputs `0008`); the hash chain (`chain.py`) | Trusted |
| `counterparties/`, `egress/` | A deterministic buyer kernel with a hidden reservation and a template verbaliser; the outbound guard that blocks any message stating a protected value or a canary | Trusted, last step |
| `nl/` | `POST /nl`: 22 intents, typed slots, multi-turn sessions, the consent grammar (`consent.py`), plans proposed and confirmed | Trusted orchestration; never skips the verifier |
| `ingest/`, `contracts/`, `deals/` | Text from Word or a PDF with a text layer (scans refused; a line wrap inside Chinese text is joined without a space, `ingest/text.py`); a contract record per document (PROPOSED until the owner decides); the deal summary and the purchases read | Trusted; the reading inside is untrusted model output |
| `capex/`, `health/`, `lending/` | The capex screen (NPV, payback, structures); the buy side: schedule derivation (`capex/schedule.py`), long-term plan permutations on a labelled monthly estimate (`capex/plans.py`); financial health and the 90-day cash coverage ratio; indicative eligibility against a synthetic lender catalogue (`fixtures/lending/catalogue.json`). All read-only except the owner's `CommitPurchase` | Trusted; buy side flagged off by default |
| `setup/` | Builds books and an unsigned mandate from the owner's typed draft. Pure: no store, no clock, no signing (`api/setup.py` signs and opens) | Trusted |
| `decisions/` | The decision record (ADR-0011): fact models, deterministic ids, the pure `derive()` and `waiting_for()`. No engine module imports it (`tests/decisions/test_isolation.py`) | Trusted, deterministic |
| `strategy/`, `pilot/` | Flagged, read-only answers on labelled copies of the books; the shadow-pilot journal | Trusted; flags default off |
| `api/` | 93 routes (`scripts/security_route_inventory.py` on `0f92d433`), authentication, intake limits, the agent's allow-list view (`agent_view.py`), every sentence the pages show in both languages, and the read caches for the Deals exposure answer, the offer picture and the no-deal plan (`strategy_exposure.py`, `offer_picture.py`, `refusal.py`, keyed by the books and cleared on reset) | Trust boundary |
| `apps/web` | Next.js pages listed in section 01; the owner sign-in keeps the token in `sessionStorage` only; English and Chinese; plain SVG cash pictures drawn from the server's series | Displays server-formatted values only |

**One offer, end to end.**

1. A buyer message arrives. Intake refuses more than 5 documents or more than 4,000 characters per document (413), files the offer as the buyer the channel key names, and counts it against that buyer's daily budget, or an unauthenticated offer against the daily intake cap (`api/offers.py`).
2. The compiler proposes obligations with spans, or abstains; a conflict between sources gives `NO_VERDICT` with `CONFLICTING_SOURCES`. It then runs the coverage proof.
3. The verifier's security screen logs and neutralises unknown senders, funding claims, unevidenced prior concessions and data requests. None of them can book anything.
4. The engine projects the conservative trajectory on current books under the offer's bookable obligations; the router prices any gap and returns the marginal cost of funds.
5. The verifier tests every day and month against the mandate and covenants, applies the early-payment tests and the autonomy rule, and returns a verdict with formulas and re-checked counters.
6. The buyer kernel answers within bounded rounds; NO DEAL is a first-class outcome.
7. Code turns the verdict into typed operations. The executor gates them, runs Tier 1, queues Tier 2 for the owner, refuses Tier 3 and appends every outcome to the hash-chained log. The decision record follows the deal to settlement.

**Binding design decisions.** Money is integer fen and rates integer basis points, exact fractions in between, one half-up rounding per posting (ADR-0002). Funding is requested on the decision day and lands after its lead time (ADR-0003, ADR-0010). The evidence hash covers `prev_hash + payload_json + result_json` only (ADR-0004). Autonomy requires proof (ADR-0005). One set of current books, an owner-moved clock and re-verification at commitment (ADR-0006). The early-payment rule (ADR-0007). Bullet term loans serviced on a level basis for DSCR (ADR-0008). Accepted terms written onto invoices with a fixed scope (ADR-0009). A decision's lifecycle derived from stored reality (ADR-0011). A confirmed contract is a record, never the books (ADR-0012). The buy side books a vendor contract only through `CommitPurchase` (ADR-0013, capex). Books are opened from typed entries, never read in by the model (ADR-0013, set up your books). **The engine stability set** (`financial`, `verifier`, `funding`, `alerts`, `operations`, `clock`, `books`, `mandate`, `domain/models.py`) changes only when a reproduction proves cause or the owner grants an explicit exception (ADR-0012 and ADR-0013 were additive exceptions); between 12 and 16 Oct no file under `financial/`, `verifier/` or `funding/` changed (`git diff 86123a3c..0f92d433`), so every engine figure in this document stands.

### Models, tools, data sources and external services

**Models.** The model is used only to (a) compile offers, term sheets and contracts into a strict JSON schema and (b) optionally classify an `/nl` request into one intent from a closed list when the rules parser finds nothing. It never decides, prices, negotiates or executes.

| Backend | Model | When |
| --- | --- | --- |
| `cache` (default) | Recorded outputs keyed by sha256 of the documents and the prompt version (`fixtures/compiler_cache/`) | Tests, CI, the demo and the offline evaluation. No network. A miss goes to the rules grammar |
| `claude` | `claude-sonnet-5-5`; `claude-opus-5-5` for inputs over 1,500 characters, multi-document offers and term sheets (`compiler/backends.py`) | `LLM_MODE=live`, opt-in; the default primary |
| `deepseek` | `deepseek-flash` (OpenAI-compatible SDK), with thinking switched off so a long contract's answer is not consumed by reasoning tokens; a cut answer is retried once with 16,000 tokens and a compact instruction (`compiler/backends.py`, commit `dc1504ab`) | `LLM_MODE=live`, `LLM_PRIMARY=deepseek`; China-reachable |
| rules grammar | Deterministic regex and lexicon, Chinese and English | Always runs beside the model; the fallback on any error, timeout or invalid JSON |

The model sees only the documents and the output schema. Mandate values, facility limits, reservation values and other buyers' terms never enter a prompt; a test checks the compiler package's imports. Only a document hash and timing are logged per call.

**Tools (the agent's typed interface).** Every tool is an HTTP route with a strict Pydantic schema (`extra="forbid"`):

| Tool | Route |
| --- | --- |
| Chat | `POST /nl` (a buyer sends `X-Counterparty-Key`); `POST /nl/opener` (owner) |
| Offers and deals | `POST /offers`, `GET /offers/{id}`, `POST /offers/{id}/evaluate`, `POST /negotiate/{offer_id}`, `POST /offers/{id}/accept` and `/decline` (owner, bound to the verdict and books shown), `GET /offers/{id}/picture`, `GET /offers/{id}/scenarios`, `GET /worklist`, `GET /decisions/{id}/tracker` |
| Clock, alerts, reconciliation | `POST /clock/advance` (owner only); `GET /alerts`; `POST /alerts/{id}/act`; `GET /reconciliation` |
| Debt Desk | `POST /router/plan`, `POST /facilities/compile` (owner), `POST /capex/evaluate`, `POST /capex/apply`, `POST /borrower-file` |
| Buy side (flag) | `POST /capex/contracts/{id}/evaluate`, `POST /capex/contracts/{id}/commit`, `GET/POST /finance/health`, `GET/POST /lending/eligibility`, `POST /lending/products/{id}/add-to-menu`, `POST /capex/plans`, `GET /purchases[/{id}]` |
| Set up your books | `GET /setup/status`, `GET/POST /setup/documents`, `POST /setup/preview`, `POST /setup/open` |
| Execution | `POST /operations`, `GET /approvals/queue`, `POST /approvals/{id}`, `POST /circuit/{id}/reset`, `POST /commitments/{id}/revoke` |
| Contracts | `POST /documents`, `GET /documents[/{id}]`, `POST /documents/{id}/confirm`, `POST /documents/{id}/reject`, `GET /deals[/{buyer}]` |
| Reads and evidence | `GET /home`, `/state`, `/mandate`, `/trajectory`, `/ledger`, `/audit`, `/evidence`, `/decisions[/{id}]` (owner token); every Business read takes `?lang=en\|zh` with the same figures |

The typed operation kinds (`domain/models.py`): ACCEPT_OFFER, COUNTER_OFFER, REJECT_OFFER, RECORD_COMMITMENT; DRAW_FACILITY, REPAY_FACILITY, SUBMIT_INVOICE_FOR_FINANCING, RECEIVE_PAYMENT; REQUEST_OWNER_APPROVAL, APPLY_FOR_FACILITY, ADD_FACILITY; COMMIT_PURCHASE (ADR-0013); and the Tier-3 kinds SIGN_PERSONAL_GUARANTEE, PLEDGE_COLLATERAL, ISSUE_EQUITY and CHANGE_MANDATE, which exist only to be refused. Log-only kinds on the same chain: ADVANCE_CLOCK, RESET_CIRCUIT, REVOKE_COMMITMENT, CONFIRM_DOCUMENT, REJECT_DOCUMENT and OPEN_BOOKS. No operation has a payee or account field; `TRANSFER_FUNDS` is rejected as an unknown kind.

**Data sources (all synthetic).**

- `fixtures/scenarios/golden_sme.json` (cash ¥400,000; payroll ¥340,000 on day 12; supplier ¥120,000 on day 20; the existing loan's ¥45,000 payment every 30 days from day 30; Receivable A ¥420,000 due day 32) and `golden_sme.mandate.signed.json` (signed with a **published demo key** labelled DEMO ONLY: floor ¥300,000; aggregate forward-concession cap ¥5,000; DSCR ≥ 1.25×; leverage ≤ 2.5×; Tier-2 threshold ¥100,000 per commitment; rate ceiling 15%).
- `fixtures/scenarios/blank.json`: a new business with no books, the start of set-up.
- `fixtures/offers/offers.yaml` (the worked examples), `fixtures/heldout*/` (three held-out evaluation sets), `fixtures/counterparties/`, `fixtures/golden/`.
- `fixtures/contracts/`: three demo documents written to match the golden books; `fixtures/capex/`: one vendor contract (¥600,000 die-cutting line: 30% on signing, 60% within 45 days of delivery, 10% retention for 12 months, 2% for paying within 5 days of delivery); `fixtures/lending/catalogue.json`: illustrative lender products.
- The Chinese contract test set (40 fictional documents with an answer key) is **not in the repository**; only its harness is (`services/api/scripts/eval_contracts.py`).
- `services/api/evals/security/attacks.yaml` (126 API attacks; the 133 chat attacks are generated by the same runner) and `services/api/evals/e2e/scenarios.yaml` (49 scripted tasks).

The synthetic funding menu (owner-approved; only the owner can add to it):

| Facility | Status | Price | Lead time |
| --- | --- | --- | --- |
| Bank credit line, ¥150,000, 30-day clean-down | COMMITTED | 6.4% simple | same day |
| Invoice financing, ¥350,000 | COMMITTED | 7.8% + 0.25% per 30-day period, 10.8417% all-in | 3 days |
| Buyer early-payment programme | COMMITTED | 1.2% discount | 2 days |
| Bank acceptance bill discounting (银票) | COMMITTED (no bill held) | 0.58% a year | 1 day |
| Government-guaranteed working-capital loan | NOT_APPLIED | 5.0% all-in | 21 days |
| Equipment term loan, 36 months | NOT_APPLIED | 5.6% | 14 days |
| Equipment lease, 48 months | NOT_APPLIED | 7.2% | 10 days |
| Equity | REFERENCE_ONLY (Tier 3) | n/a | n/a |

**External services.** No bank, lender, payment or blockchain API is used. In live mode only, the Anthropic or DeepSeek API receives the inbound documents and the extraction schema. The deployment database is PostgreSQL (the Compose container, or Supabase through `DATABASE_URL`) with row-level security on every table and no policies.

**Libraries.** Python 3.12, FastAPI, Pydantic v2 (strict), SQLAlchemy 2 + Alembic, PyNaCl (Ed25519), structlog, python-docx, pypdf, openpyxl, the Anthropic and OpenAI SDKs; Next.js 16, React 19, Tailwind 4, Recharts (demo and what-if charts only); pytest, hypothesis and Playwright.

## 03 Agent Design

### Intent understanding, planning, tool use and state management

**Intent understanding (`nl/`).**

- A deterministic rules parser (zh + en lexicon) maps each request to one of **22 intents** (`nl/models.py`): EVALUATE_OFFER, NEGOTIATE, ACCELERATE_RECEIPT, FUND_GAP, REPAY_FACILITY, SHOW_STATUS, SHOW_ALERTS, COMPARE_FINANCING, RECONCILE, SHOW_RATIOS, CAPEX, BORROWER_FILE, SHOW_DEAL, EXPLAIN, WHAT_IF, RECORD_FACT, CHANGES, APPROVE, REJECT, COUNTERPARTY_MESSAGE, OUT_OF_SCOPE and AMBIGUOUS. It fills typed slots, and every id is checked against the registry. RECORD_FACT and CHANGES are read-only: a stated bill or figure is answered "cannot record it, forecast unchanged". A request that matches nothing gets the nearest capability.
- Only when the rules find nothing is the optional LLM classifier consulted. It may only *choose* an intent from a closed list; APPROVE, REJECT and COUNTERPARTY_MESSAGE are not in its vocabulary, and a canary in its output discards the answer.
- **Consent grammar** (`nl/consent.py`). A financial instruction executes only when the whole message is one closed affirmative command with exactly one RMB amount; negation, a question, a condition, a future time, a foreign currency, an unreadable amount, a rider and quoted or pasted text execute nothing. An approval id is decided only by an exact decision sentence.
- **The actor comes from authentication, never from text.** A COUNTERPARTY's message is compiled and verified as an inbound offer and never executes; its response carries the reply and the session id only. The **agent key** (no owner token) gets an allow-list view of its turn (R-11, `api/agent_view.py`): the intent, the operation steps, the outcome word, what ran or was queued, and refusals in words, with no cash figure, limit, floor, cap, break-even or verdict JSON; the only amounts are those of the operations it is acting on, and the view passes the egress guard.

**Planning.** A plan is a list of typed steps built by code from a verdict or a router plan: goal to plan ("get paid early without giving anything away next quarter" becomes an early-pay counter at 0.85% with a fallback to invoice financing); multi-step funding (draw, finance, repay on receipt); clarification ("fund it" with two gaps asks which); correction ("make it 0.8%" amends, "1%" is refused above the 0.88% break-even); and **proactive re-plan**: after the clock or the bank feed moves the books, the opener names what needs the owner and proposes a cure priced as the executor will charge it. A plan is stored with its exact operations, quoted cost and books; "go ahead" runs those operations or shows a new proposal if the books moved.

**Tool use.** Handlers call module functions (compile, evaluate, plan, negotiate) and send typed operations to the executor. Every operation carries an idempotency key derived from the session (with a random part), the turn and the step. No handler can skip the verifier or build an operation from model output (INVARIANT 1).

**State management.**

- *Session state* (`nl/sessions.py`) holds typed references only (last offer and verdict, a pending plan, a pending clarification, the operations each request produced); a retried request is replayed, not re-planned; sessions expire after 30 minutes.
- *Financial state* is a frozen `FinancialState` plus the operations log; a change builds a new model and bumps `state_version`.
- *Current books and time* (ADR-0006, algorithm 2): integer simulated days; the books are closed before `as_of_day`; only the owner moves the clock.
- *Commitments* follow PROPOSED → ACCEPTED → ACTIVE → FULFILLED, or EXPIRED / REVOKED, each with a nonce, an expiry and a terms hash.
- *Records beside the books*: decision facts (migration `0006`), contract records (`0007`) and the owner's customer inputs (`0008`) are not part of the state hash; setup documents read before opening are held in memory (at most 10).
- *Read caches*: the Deals exposure answer, the offer picture and the no-deal refusal plan are cached by a key built from the state, the mandate, the day, the commitments and (for the exposure answer) the verdict, the log's change marker, the inputs and the language; the router's work is shared across languages, and `Runtime.reset` clears every cache (merge `545b4efc`; `tests/api/test_exposure_cache.py` pins that a cached read equals an uncached one in both languages).

### Core algorithms and evaluation approach

Each algorithm below says what it decides, why it is safe, then how.

#### 1. Grounded semantic compilation (`compiler/`)

**Decides:** what a buyer's message, a term sheet or a contract says, as typed data. **Why it is safe:** the model supplies no number, date or decision of its own; every value is a substring of the document parsed by code, and anything that cannot be grounded is abstained, so a misreading can only cost the owner a click (ADR-0005).

1. **Backend chain.** Cache, then the live model if enabled, then the rules grammar. A failing backend falls to the next.
2. **Grounding** (`grounding.py`). An obligation is kept only if its quote is found verbatim in its document (exact, then whitespace-insensitive), and each value fragment lies inside that quote. Code parses the value (digits, ¥/k/万, English number words, Chinese and 大写 numerals). Otherwise the obligation is dropped with a material abstention and the offer is `ABSTAINED`. Two sources that disagree on a material value, or a stated discount sum ≠ `post(rate × face)`, give `CONFLICTING_SOURCES`. A concession stated twice is booked once.
3. **Flags** (`lexicon.py`, on NFKC-folded text with zero-width characters removed and look-alikes mapped): data requests, authority claims, unsolicited funding claims. Flagged text never becomes an obligation.
4. **Boundary abstentions** (`boundary.py`): a decimal comma, a per-day rate, "2/10 net 30", a foreign currency, a partial amount, another party's invoice, a hedge, a payment after the due date or a rider abstains, with a question for the buyer.
5. **Coverage proof** (`coverage.py`). `autonomy_eligible = true` only if: status COMPILED; no abstention or flag; every amount, rate, day count, date and invoice reference is explained by an obligation; no request, condition or question cue (en + zh); no word outside a short filler list (a word inside an obligation's own span is not exempt). It defaults to false.
6. **Contracts** (`contract.py`). A contract is split at headings into chunks of at most 6,000 characters (more than 40 chunks is refused before any model call). Each term quotes its clause verbatim and code parses its value. Since 16 Oct, for Chinese contracts: a PDF line wrap inside CJK text is joined without a space so quotes match (`ingest/text.py`); dates in Chinese numerals (二〇二五年十二月十七日) are read (`contract_parsing.py`); a supplier's late-delivery penalty is not read as the buyer's late-payment interest, and a performance bond is not read as retention (`contract.py`); a price stated again inside its own total is read once, and a one-valued field stated with different values is dropped as `CONFLICTING_SOURCES`; a performance period counted from signing ("自合同签订之日起45日内") derives start and end dates, labelled "derived"; and stage percentages, stage amounts and the amount in words (大写) are cross-checked against the total, a disagreement adding a note and changing no term (`contract_checks.py`). A sentence addressed to the agent is a blocking flag: the document can be rejected, never confirmed.

#### 2. Current books and projection (`books/`, `financial/`; ADR-0006, 0009, 0010)

**Decides:** the cash, debt and forward-concession path every other decision is tested on. **Why it is safe:** there is one set of books for every module, conservative mode alone decides, and nothing is assumed to arrive that has not been recorded.

- **Current books** = `(state, live obligations)` from `books.current_books(store, day)`: the stored position today plus the cash-relevant obligations of ACCEPTED/ACTIVE commitments that still bind. An early payment not made by its day drops out and is reported LAPSED. Accepted terms and prices are already written onto invoices (ADR-0009), so they are not re-applied.
- **Daily recursion.** For each day *t*: `closing(t) = opening(t) + Σ inflows(t) − Σ scheduled outflows(t) − Σ interest, fees and repayments(t)`; inflows first, then outflows, then charges. `closing(t)` is tested against the floor.
- **Conservative mode:** unconfirmed inflows ignored; only COMMITTED facilities drawn (PENDING and NOT_APPLIED count as zero); contingent concessions at their maximum; contingent gains at zero. Expected mode is shown, never used for a hard constraint.
- **Time.** Days are absolute; flows and receipts dated before `as_of_day` are dropped (posted or not happened); an overdue receipt is never assumed. Funding is a dated lot: requested on day *d*, cash on *d* + lead time net of the upfront fee, interest from landing (ADR-0010). Existing debt is paid on its own schedule and leaves cash.
- **Money.** Integer fen; Actual/365 simple interest; invoice financing billed in whole 30-day periods; one half-up rounding per posting (ADR-0002). Month *m* covers days 30(m−1)+1 to 30m.
- **Covenants** (`covenants/`): `DSCR = monthly EBITDA / monthly debt service` (bullet term loans on a level basis, a labelled reserve-coverage reading, ADR-0008); `Leverage = month-end drawn debt / (12 × monthly EBITDA)`; clean-down = the longest run of zero-balance days on a line.
- **Forward concessions:** a terms extension of Δ days on face F costs `F × Δ × r / 365` per invoice issued in the window, at the marginal tariff r; a price change p is `p × F`; only FIRM gains offset.

*Golden check.* With the full EX01 package accepted and no new funding, cash is **¥354,960** after day 20 and **¥209,960** on day 47: a **¥90,040** shortfall against the ¥300,000 floor; the committed marginal source cures it for **¥2,406.67**. Golden values: DSCR 2.00× at base and 1.92× after funding the extension; leverage 1.35× and 1.47× (`fixtures/golden/golden_values.json`).

#### 3. The verifier (`verifier/`)

**Decides:** accept, counter, reject, needs the owner, or no verdict. **Why it is safe:** it reads typed rows only (an AST test forbids text fields), every hard rule is a predicate on the conservative books, and the agent's own authority is the narrowest case that can be proved.

1. **Offer status.** `CONFLICTING_SOURCES` or `ABSTAINED` → NO_VERDICT.
2. **Security screen** (never booked, each a SecurityEvent): unknown sender or funding claim → `UNKNOWN_COUNTERPARTY`; a claimed prior concession with no ledger commitment → `UNEVIDENCED_PRIOR_CONCESSION`; a data request → `DATA_EXTRACTION_REFUSED` with a fixed reply.
3. **Mandate validity:** signature against the pinned key, version, expiry, revocation; any failure → REJECT with no evaluation.
4. **Projection** on current books with the offer, the router's committed plan and the marginal cost of funds.
5. **Hard rules** (each a `Violation` with code, day or month, observed value, limit, `formula` and `inputs`): closing cash ≥ floor on every day (a breach the committed plan can cure is reported `curable` with its cost); aggregate and per-buyer forward-concession caps including existing commitments; the immediate-discount cap; the rate ceiling; DSCR and leverage every month; Tier-3 clauses. A buyer with a past-due invoice on current books needs the owner.
6. **Early-payment tests** (ADR-0007, algorithm 4): a discount at or above break-even, not needed, or dearer than the plan is a pricing fault → COUNTER.
7. **Outcome:** Tier 3 or unknown counterparty → REJECT; a hard violation → REJECT with counters; a pricing fault → COUNTER; Tier 2 or a past-due buyer → NEEDS_OWNER_APPROVAL; otherwise ACCEPT.
8. **Autonomy (ADR-0005).** An ACCEPT stays Tier 1 only if the package is a pure early-pay discount on a named invoice that passes all three early-payment tests, `autonomy_eligible` is true, and the stated amount equals the whole face of the open invoice it binds to. Otherwise it becomes NEEDS_OWNER_APPROVAL and the summary names the missing proof. Owner-built typed offers carry no free text and are exempt.

**Mandate tiers** (`mandate/tiers.py`; computed by the executor, never taken from the caller):

| Tier | Operations | Outcome |
| --- | --- | --- |
| 1: autonomous | The proved early-pay acceptance above; counter or reject within the mandate; draw on or repay a COMMITTED, owner-approved facility, or finance an eligible invoice, when admission passes and the effective annual cost ≤ `max_apr_bp`; a receipt from the bank feed or the owner | EXECUTED |
| 2: owner approval | Every other acceptance; any commitment above ¥100,000; a draw or advance above the rate ceiling; any non-committed facility; apply for a facility; `CommitPurchase` (always); a receipt reported by the agent or a buyer; an owner's AddFacility | PENDING_APPROVAL |
| 3: never | Personal guarantee, collateral, equity, mandate change, a facility added by a non-owner, any unknown kind | REFUSED for every caller |

*Golden check (Scene 1).* EX01 compiles to a ¥5,040.00 (1.2%) discount, a recurring terms extension and a contingent rebate of up to ¥4,000. The forward-concession ledger is **¥28,326.92** against the **¥5,000** cap, so the verdict is **REJECT: AGG_CONCESSION_EXCEEDED; RESERVE_BREACH@47 (curable at ¥2,406.67); DISCOUNT_ABOVE_BREAK_EVEN; EARLY_PAY_DEARER_THAN_PLAN** (¥6,508.05 against ¥3,550.64), with covenants holding at DSCR 1.92× and leverage 1.47×.

#### 4. Counter pricing and negotiation (`verifier/counters.py`, `counterparties/`; ADR-0007)

**Decides:** what FLOW offers back. **Why it is safe:** every counter is priced from the firm's own marginal cost, and every counter is itself re-evaluated as an offer on the same books before it is shown; one that fails is dropped with a one-sentence reason.

- **Marginal cost of funds** `r`: the all-in annual rate of the cheapest COMMITTED, owner-approved source able to carry a *permanent* need (clean-down excludes the line): invoice financing, 10.8417%.
- **Test 1, break-even for the actual tenor.** For an early payment *n* days before the due day, `c(n)` is the marginal source's cost share: invoice financing `rate × 30 × k / 365 + fee × k` with `k = ⌈n/30⌉`; any other source `rate × n / 365`. Break-even `d* = c / (1 + c)`; fail when `d ≥ d*`. For *n* = 30 on the golden books `d* = 0.8832%`.
- **Test 2, the cash is needed; test 3, cheaper than the plan.** `C0` = total posted cost (interest + fees + discounts) of the cheapest plan the agent can run without the early-pay leg; `C1` = the same with it, discount included. No funding needed and `C1 > C0` → `EARLY_PAY_NOT_NEEDED`; `C1 ≥ C0` → `EARLY_PAY_DEARER_THAN_PLAN`. The buyer's early-pay programme and a bill are never legs of `C0` (no operation can make the buyer pay).
- **Hand-calculated (ADR-0007; `tests/verifier/test_early_pay_handcalc.py`).** `C0 = ¥3,113.93`. A whole-invoice discount 30 days early at 0.74% costs ¥3,108.00 and is accepted; at 0.75% (¥3,150.00) it is countered.
- **Option A (early pay).** Keep 45-day terms, no rebate; accept early settlement on up to face `F = gap_net / (1 − d)`, where `gap_net` is the part of the gap the line does not cover (¥255,000), rounded up to a whole ¥100 (¥257,186.08 → **¥257,200**), at the largest whole-5 bp rate strictly below `d*(n)` (**0.85%**), "paid on or before day 2". Cost: discount ¥2,186.20 + line ¥149,986.20 × 6.4% × 32/365 = ¥841.57, total **¥3,027.77** < `C0`, so it is offered.
- **Option B (price adjustment).** Accept longer terms with the smallest whole-5 bp adjustment `p` such that `p × F ≥ F × Δ × r / 365` per invoice. On EX01: **55-day terms at 0.30%** (¥1,260.00 against ¥1,247.53 per invoice; 12-month net −¥162.05), needing the owner. 60 days fails its re-check (no committed cure for the day-60 loan payment), so it is not offered.
- **Buyer kernel.** `surplus = discount received + declared benefits + rebate received + value of extra payment days − its own cost of paying early − price adjustments it pays`. It accepts when every reservation gate holds and surplus ≥ reservation, else counters one step toward (never onto) its reservation, and rejects in its last round. Scene 2: a hard-line reservation refuses every counter within **3** rounds → NO DEAL, and the router funds the gap for ¥3,113.93.
- Outbound text is template-filled and passes the egress guard (algorithm 7).

#### 5. The funding router and search (`funding/`; ADR-0003, 0010)

**Decides:** the cheapest admissible way to fund a gap from the owner's own facilities. **Why it is safe:** it never computes cash itself (each candidate is run through the engine), uncommitted facilities are not candidates, and the executor runs every draw through the same admission check whoever asks.

- **Candidates.** Lists of funding actions on a **¥10,000 grid** (`GRID_STEP_FEN`): single-source fills, then pairs (a grid over the first, the second filling the residual), then triples. No action below **¥1,000** (`MIN_ACTION_FEN`). Every source is requested on day 0 and lands after its lead time; a bullet line may be repaid on any receipt day after the gap opens on which cash stays at or above the floor.
- **Admissible** iff closing cash ≥ floor every day, no covenant violation and new borrowing allowed. **Cost** = what the trajectory posts, net of what the offer alone posts.
- **Rate ceiling.** The effective annual cost of a leg, `(interest + period fees + upfront fee) / advance × 365 / days from landing to due day` (`funding/rates.py`, shared with the executor), above `max_apr_bp` makes the plan `needs_owner_approval`, not inadmissible. Ranking: plans needing no one first, then cheapest. A plan admissible only as a whole is flagged "cannot run today"; legs are ordered so every prefix is admissible (`legs.py`).
- **Speed.** The search steers on `financial.project_cash` (same postings, no display trajectory); any probe that could win is re-run through the full projection and covenants before it is accepted. The display-only expected search is capped at 2,000 candidates; the committed search is never capped.
- **Admission** (`funding/admission.py`): inside the executor's transaction, a draw, advance or repayment is refused if the engine cannot book it, it breaches DSCR or leverage, it takes cash below the reserve (or deeper), or borrowing is switched off. The owner cannot waive these by approving.
- **Golden result.** Gap **¥405,000** before day 32; plan: the line ¥150,000 (interest ¥841.64) + invoice financing ¥255,000 (¥2,272.29) = **¥3,113.93**, against ¥5,040.00 for the buyer's 1.2% discount. The guaranteed loan is not committed and lands on day 21, after payroll on day 12.
- **Optimality.** Against an exhaustive brute force over the usable committed levers on 26 scenarios (10 designed, 16 seeded random), the router's best runnable plan is within ¥1 on **26/26** (`services/api/evals/latest_report.md`, 5 Oct 2026). The brute force is grid-bounded, so a plan both missed is invisible.

#### 6. The executor (`operations/executor.py`; ADR-0006)

**Decides:** whether a typed operation runs, waits or is refused. **Why it is safe:** it is the only writer, it computes the tier itself, it re-verifies a verdict at the moment of commitment, and every outcome is on a hash chain.

Gates, in order: (1) idempotency key (`DUPLICATE`; a key reused for another operation is `REPLAY`; a refusal does not use the key up); (2) dating (the operation's day must equal the clock); (3) mandate signature, pinned key, expiry, revocation, version; (4) Tier 3; (5) counterparty circuit breaker (3 refused offer operations in 7 days; only the owner resets it; the owner's answer to a buyer's request passes it, and the owner's own refusals do not count, SEC-05); (6) for acceptances: commitment exists and is unrevoked, single-use nonce matches (constant-time), not expired, terms hash and mandate version match, a verdict backs the terms, and **re-verification now**: named receivables still open, **one live commitment per invoice and per buyer request** (SEC-02), caps still hold, and if `state_version` moved, the obligations still verify on current books (`STALE_VERDICT`, `CONFLICTING_COMMITMENT`); (7) Tier 2 queue; (8) per-kind preconditions and admission. For `CommitPurchase`, the owner-only check runs when it is queued and again when it runs.

**Units of work.** Each entry point runs as one store transaction: state, commitment, nonce, approval, security event and log entry commit together or not at all. The store enforces compare-and-swap on the state version and on the log head; a unit that lost a race reruns on the new books, at most **8** times (`_CAS_ATTEMPTS`), then HTTP 409. Proven with two processes on SQLite; the deployment runs one process (SEC-11).

**Hash chain** (`persistence/chain.py`): `entry_hash = sha256(prev_hash + payload_json + result_json)`, genesis `"0" × 64`, contiguous `seq`. Refusals and duplicates are logged too. `scripts/verify_evidence.py` recomputes it with the standard library.

#### 7. The egress guard (`egress/`)

**Decides:** whether an outbound text may leave. **Why it is safe:** outbound text is already template-filled from typed fields; the guard is the last, deterministic check behind that, and it blocks the whole message rather than redacting.

`ProtectedSet` lists every protected value in its surface forms (¥, k, 万, Chinese and 大写 numerals, English number words, percentages, ratios, names and role aliases): mandate limits, facility terms, covenants, balances, debts, flows, other buyers' invoices and terms, booked concessions, each confirmed or proposed contract's terms (owned by that counterparty), and **4 planted canaries** (`fixtures/security/canaries.yaml`) that nobody is entitled to. `guard(text, recipient)` scans the folded text; on any value the recipient is not entitled to, it replaces the message with a fixed safe sentence and logs a `DATA_EXTRACTION` event with labels only, never values. It runs on chat replies, counter texts, negotiation replies and, since 16 Oct, on every text the agent key receives (R-11). Known gaps: some number forms and derived values are not in the set (SEC-22, open; low while outbound buyer text is template-only).

#### 8. The decision record state machine (`decisions/`; ADR-0011)

**Decides:** nothing about money. It says where each deal or funding decision stands and what it is waiting for. **Why it is safe:** it is a pure read model over the canonical stores plus three append-only facts; it computes no money, prices no past moment, and no engine module imports it.

- **Facts** (table `decision_facts`, insert-if-absent, strict models with integers and ids only): EVALUATED (the verdict's day), SENT (which counter was sent and what it cost), QUOTED (the economics the owner was shown when a funding action was queued or run). A failed fact write never fails the route; the read says "not recorded".
- **Identity:** `deal:{offer_id}`; `alert:{id}:v{state_version}` (and `:plan`); `nl:{session}:{scope}`; `approval:{id}`.
- **DEAL states,** first matching rule wins (`state.py`): REVOKED; FULFILLED; MISSED (expired with lapsed obligations, or active with a lapsed promise); AGREED (ACTIVE); EXPIRED; **DECLINED when the owner declined the request** (an owner-requested REJECT_OFFER through `POST /offers/{id}/decline`); AUTHORIZATION_REQUIRED; DECLINED (approval rejected); FAILED (refused, or approved then refused on re-run); NO_DEAL; NEEDS_CLARIFICATION; RESPONSE_READY; RECEIVED. LAPSED is set by the API read when an offer can no longer be drawn on today's books. An agreement made by the owner accepting the request as asked is marked `accepted_as_asked`.
- **FUNDING states:** AUTHORIZATION_REQUIRED; DECLINED; FAILED; PARTIALLY_EXECUTED; SETTLEMENT_PENDING (a lot not yet landed); SETTLED; EXECUTED. Residual risk is a field read now and labelled as today's position.
- **Waiting for** (`waiting_for`): the owner's response or approval, the buyer's clarification or receipt (with the promised or due day), an invoice issue, the lender's settlement, or nothing.
- **Bound send.** `POST /negotiate` with `verdict_id`, `counter_id`, `state_version` refuses a mismatch with 409 `COUNTER_CHANGED` and a repeat with 409 `ALREADY_SENT`; nothing is proposed, accepted or funded.

#### 9. The buy side: schedule derivation and commitment (`capex/schedule.py`, `operations/executor.py`; ADR-0013)

**Decides:** the dated payments of a confirmed vendor contract, and whether the owner's purchase is booked. **Why it is safe:** code derives every amount from spans it parsed, abstains on anything ambiguous, and only an owner-authored, owner-approved operation bound to the hashes the owner saw can write the payments.

- **Derivation.** Inputs: the confirmed reading and the owner's timeline (signing, delivery, acceptance, invoice days). The price must be one lump sum; each milestone's trigger is classified into one event with the offset its own words state (delivery + 45); milestones + retention must reconcile to 100%; a month is 30 days and business days count as calendar days (the earlier reading of an outflow). Each payment is `post(price × share)` and the last carries the remainder, so the schedule sums to the price exactly. `schedule_hash = sha256(price, [day, amount, kind, share] per payment)`.
- **Guards (CAPEX-1 to 4, certified on `b6d1e519`).** No schedule from a milestone share outside (0%, 100%], a retention above 100% or an early-pay discount of 100% or more; every payment must be > 0 (in derivation and again in the executor). `CommitPurchase` is refused unless the requester is the owner (CAPEX-2), the document is a confirmed capex contract whose hash matches, the schedule re-derived from the stored record hashes to what the owner was shown, no payment day is past, and the same contract (same text, or same reference and vendor) is not already committed (CAPEX-3); a vendor that is the SME itself, compared by company key, is refused (CAPEX-4).
- **Effect.** One `CashFlow` of kind CAPEX per payment (`CAPEX:<document id>:<n>`) and the vendor registered as a supplier; the clock then pays them like any bill. The vendor's early-pay discount is priced with the sell side's own rate `d / (1 − d) × 365 / days earlier`. Health, eligibility and long-term plans are read-only and labelled `OWNER_ESTIMATE` or estimate; catalogue products count as zero for hard constraints.

#### 10. Capex screen and strategy answers (brief)

The capex screen (`capex/evaluate.py`) is a screen, not an appraisal: for the synthetic ¥600,000 machine NPV **¥380,885.77**, payback month **31**; the **48-month lease** is selected (¥14,423.49 a month) because the 36-month loan's first instalment takes cash to ¥296,855.38, below the reserve. The strategy answers sweep labelled copies of the books through the kernel's own functions; their backtest passed with 0 failures (`docs/research/strategy/06-backtest-2026-10-08.md`).

#### Evaluation program

We evaluate the compiler on data its tuners had not seen, the engines against an independent oracle and a brute force, contract reading against an answer key, and the whole agent through scripted tasks and attacks.

**Three held-out sets of buyer messages.** Each was written by a separate evaluation agent from the spec, the glossary and the golden state, with labels committed before the first run. Held-out 1 (50 offers) was tuned on and is not an accuracy claim; held-out 2 (49) was unseen at its first run; held-out 3 (66 offers, labels in `1d6d8fd`) is the only independent, untuned figure.

**Compiler accuracy: the only claims we make** (`services/api/evals/accuracy_summary.md`):

| Set | Independence | Path | Verdict agreement | Material error rate | Silent material errors | **Wrong autonomous accepts** |
| --- | --- | --- | --- | --- | --- | --- |
| Held-out 3, first run (before ADR-0005) | **independent, unseen** | rules grammar | 33/63 (52%) | 4/51 (7.8%) | 7 | **4 of 8** |
| Held-out 3, after round 3 | guided round 3 | rules grammar | 46/63 (73%) | 3/51 (5.9%) | 4 | **0** (2 correct) |
| Held-out 3, after round 3 | prompt not tuned on it | live DeepSeek (`deepseek-flash`) | 42/63 (67%) | 3/51 (5.9%) | 5 | **0** (1 correct) |
| Held-out 2, after round 3 | guided round 2 | rules grammar | 41/47 (87%) | 0/37 | 0 | **0** (4 correct) |
| Form baseline (labels typed in) | — | no compiler | 61/63 (97%) | — | — | — |

- **The guarantee:** across every held-out set and both paths, **0 wrong autonomous accepts** after ADR-0005. Text the compiler cannot account for goes to the owner, a counter or a clarification.
- **The misses, unchanged:** about 1 message in 3 is not decided as a human would on first reading. The material-error target (≤ 5%) and the zero-silent-error target are **not met** on held-out 3.
- **How ADR-0005 was found:** all four wrong autonomous accepts on the first held-out-3 run were early-pay offers where the grammar kept the rate and dropped a contradicting clause (`services/api/evals/heldout3_report.md`).

**Chinese contract reading (new, 16 Oct).** `services/api/scripts/eval_contracts.py` reads each document with the production path (`ingest.extract_text`, then `compiler.service.compile_contract`), maps FLOW's terms onto the answer key's fields and scores them field by field; fields FLOW cannot express (payment instrument, per-stage day counts, LPR multiples, and others the script lists) are reported, not scored. The test set is **fictional and answer-keyed**: 40 generated Chinese contracts (government goods and services, B2B goods and technology; 18 text PDFs and 12 Word drafts are readable). The **10 scanned PDFs are refused before any model call, because there is no OCR**. Every model reading came from DeepSeek (`deepseek-flash`, live), recorded once and replayed from a local cache, so the before and after runs differ only in code. Results on the 30 readable contracts (harness output of 16 Oct, before and after the `fix/contract-reading-cn` changes; the set and the output are kept outside the repository):

| Field | Before | After |
| --- | --- | --- |
| contract number, buyer, seller, total amount | 30/30 each | 30/30 each |
| signing date | 26/30 (87%) | 30/30 (100%) |
| performance start date | 13/30 (43%) | 30/30 (100%) |
| performance end date | 13/30 (43%) | 30/30 (100%) |
| retention % | 28/30 (93%) | 28/30 (93%) |
| late-payment interest | 22/30 (73%) | 22/30 (73%) |
| payment stage percentages | 50/61 (82%) | 50/61 (82%) |
| stage days after trigger | 12/61 (20%) | 12/61 (20%) |
| stage day unit | 12/61 (20%) | 12/61 (20%) |
| stage trigger | 7/61 (11%) | 7/61 (11%) |
| **All fields** | **303/514 (59%)** | **341/514 (66%)** |

The code-side checks on the after run: stages summing to 100% confirmed on 16 contracts, stage amounts on 38 stages, the amount in words on 14, 30 derived dates. Per-stage day counts and triggers stay weak because `PAYMENT_TERMS` is one value per contract and `PaymentBasis` has four triggers. The separate held-out contract set (written by someone who has not seen the schema) is still pending and quotes no figure (`services/api/evals/contracts_heldout_report.md`).

**Full offline evaluation** (`services/api/evals/latest_report.md`, run 5 Oct 2026 on `d4b410f`, `LLM_MODE=cache`, 609 s; spec v2 §14 gates):

| Gate | Question | Result | Status |
| --- | --- | --- | --- |
| E3 | Engine correctness | Golden values exact to the fen: **67/67** | PASS |
| E5 | Honest no-deal | Hard-line buyer → NO_DEAL within 3 rounds, gap still funded: **7/7** | PASS |
| E7 | Harness compatibility | Scripted `/nl` tasks **49/49**; API attacks with harm **0/126** | PASS |
| E9 | The router matters and stays honest | Cheaper than "line first" (or baseline infeasible) on **9/26**; plans on uncommitted facilities **0**; runnable optimality **26/26** | PASS |
| E10 | Covenant and capex engine | Golden **27/27**; boundaries at ±1 fen/bp/day **20/20**; breaches with their month **2/2** | PASS |
| E2 (held-out 1) | Compiler beats a form | 0/36 material errors on a **tuned** set; engine ≠ static cap 22/33 | PASS on a tuned set |

**Latency** (same report, one laptop, offline): router plan p50 **96 ms**, p95 **302 ms**; slowest `verifier.evaluate` **0.7 s**; `/nl` turn p50 **14 ms**, p95 **843 ms** over 87 turns; golden Scene 1 end to end p50 **757 ms**, p95 **816 ms** over 5 cold runs. A live model call adds its own latency (the live DeepSeek held-out-3 run took 682 s for 66 offers).

**Language-boundary certification.** A 231-item adversarial set scored from stored state through the real `/nl` route (`scripts/certify_language_boundary.py`): **WRONG_MATERIAL 0** in the cache run and the scripted-model run (3 Oct 2026). **No real model has been run through it**: the live run is pending an API key.

**Not measured.** Contract reading on real contracts or on the pending held-out set; the strategy answers against a real owner; handling time against a form; a live Claude accuracy run; the live language-boundary run; PostgreSQL concurrency; blind explanation tests by non-builders.

## 04 Security Design

### Tiered permissions and confirmation for sensitive actions

> **For Security Lead review.** This section summarises the security design as it stands on `dev` at `0f92d433`. The Security Lead will verify it. The full report, with every test, finding and risk, is `docs/SECURITY_SELF_ASSESSMENT.md`; the register, certifications and release gate are in `docs/security/`.

**Actors and keys** (`api/auth.py`; constant-time comparisons; a refused credential logs a `PRIVILEGE_ESCALATION` event, at most 300 recorded per hour, SEC-10):

| Credential | Header / variable | Confers |
| --- | --- | --- |
| Owner token | `X-Owner-Token` / `OWNER_TOKEN` | Owner authority: reads, approvals, revocation, circuit reset, AddFacility, the clock, documents, setup, the buy side, demo reset |
| Agent key | `X-Agent-Key` / `AGENT_KEY` | The agent's tool channel: Tier 1 inside the mandate; Tier 2 queued; chat through the allow-list view (R-11) |
| Bank-feed key | `X-Bank-Feed-Key` / `BANK_FEED_KEY` | Recording a receipt as SYSTEM (Tier 1). Since SEC-09 it no longer moves the clock |
| Buyer channel key | `X-Counterparty-Key` / `COUNTERPARTY_KEYS` | That the sender is that registered buyer, on `/nl` and `/offers` (SEC-18); never authority to execute |
| Mandate key | Ed25519, public key pinned | Signs the mandate offline; the demo key is pinned only in demo mode |
| None | — | Submit an offer or chat as an unauthenticated counterparty: compiled and verified, never agreed, nothing live stored |

A body field such as `requested_by: OWNER` confers nothing; it is rewritten to AGENT before parsing.

**`DEMO_MODE` is off unless set** (since 16 Oct, SEC-07; `config.py`, `api/auth.py`). Off, the published demo credentials match nothing, an unset owner or agent credential makes those routes fail closed (503), `/docs` and `/openapi.json` are not served (SEC-13), the demo key is never pinned, `/demo/reset` on a persistent store is refused, and setup cannot open books. Local runs, tests and CI opt in with `DEMO_MODE=1`.

**Owner-only routes.** Every read view (`/state`, `/mandate`, `/trajectory`, `/ledger`, `/audit`, `/evidence`, `/home`, `/decisions`), documents and deals, setup, the buy side, the clock, the opener, approvals, revocation and circuit reset require the owner token. The Security Lead's authorization sweep called every route as anonymous, a wrong token, the agent, the bank feed, a buyer and the owner, with `DEMO_MODE` on and off: no non-owner role passed an owner route (94 API routes on `b6d1e519`, `docs/security/CERTIFICATIONS.md`).

**Three tiers, computed by the executor** (the table in section 03, algorithm 3). A caller-supplied tier is rejected as an unknown field; extra facts can only raise the tier. An early-pay discount that fails an early-payment test is a COUNTER, never an acceptance.

**Signed mandate.** The mandate is Ed25519-signed over its canonical bytes; the executor verifies it on every operation against the pinned key. A re-signed or edited mandate gives `BAD_SIGNATURE`; an expired or revoked one refuses agent operations (a bank or owner receipt is still booked: it records a fact).

**Approvals.** A Tier-2 operation is stored as its exact canonical JSON with a reason that is the operation's own description. The agent cannot edit or approve it. On approval the executor re-runs every gate except the queue against the mandate then in force, so an approval after revocation is refused and an approved Tier-3 operation stays refused. The owner's accept-as-asked (`POST /offers/{id}/accept`) queues and approves in one owner call (R-2, accepted for the simulation).

**Sensitive owner acts with their own binding.**

- *Confirming a document* (CONFIRM_DOCUMENT / REJECT_DOCUMENT): owner only, bound to the SHA-256 of the text reviewed (409 `TERMS_CHANGED` otherwise), once; a document carrying text addressed to the agent cannot be confirmed; it writes no books.
- *Committing a purchase* (COMMIT_PURCHASE): owner-authored and always Tier 2, bound to the document hash and the schedule hash (algorithm 9).
- *Opening books* (`POST /setup/open`): owner token re-typed as a signature, only on untouched blank books (no log entry, no security event, day 0; otherwise 409 `BOOKS_ALREADY_OPEN`, SETUP-1), only in demo mode (403 `SETUP_REFUSED` otherwise, SETUP-7), bounded inputs (SETUP-4, SETUP-5); `OPEN_BOOKS` records what it replaced.
- *Acting on an alert*: `POST /alerts/{id}/act` carries the state version and the suggestions shown (409 `ALERT_CHANGED` if either moved).

**Record.** Every outcome, refusals and duplicates included, is appended to the hash chain (algorithm 6). Database triggers refuse UPDATE and DELETE on the log tables (migration `0003`). The chain is internally checkable only: its head is not anchored outside the system, and approvals and security events are not on it (SEC-08, open).

**Rollback.** The log is append-only, so a mistake is corrected by a logged compensating operation: repay a draw, settle an advance on receipt, revoke a commitment (owner, `REVOKE_COMMITMENT`), decline a queued request, or revoke the mandate. A refused or pending operation leaves state unchanged; the attack suite checks this. A committed purchase cannot yet be cancelled (ADR-0013, consequences).

### Protection against prompt injection, privilege escalation and privacy leakage

**Prompt injection: architecture first, detection second.**

- Counterparty text only ever becomes a `CompiledOffer`, a term-sheet proposal or a contract reading; the schemas have no field for an operation, an approval, a tier, a reply or a new facility. The verifier, router, covenants, mandate and engine read typed rows only (AST-enforced).
- A claimed prior concession with no ledger commitment is never booked; a lender named in a message becomes an `UnsolicitedFundingClaim` and a security event, never a facility.
- Contingency is decided by code after the model answers; a gain is never relabelled FIRM.
- The lexicon flags override attempts, fake SYSTEM lines, role-play, encoded, full-width, zero-width and homoglyph text and authority claims in both languages. Detection is logged; refusal does not depend on it.
- A misread message cannot be accepted without the owner (ADR-0005); the coverage proof fails closed on unread words.
- A contract sentence addressed to the agent blocks confirmation; documents are read only for counterparties on the owner's registry with the matching role (a vendor is accepted for a capex contract only, through an owner-only route).
- Intake is bounded (SEC-16, SEC-17, SEC-18): a different document under a taken id is 409; at most 5 documents of 4,000 characters (413); a channel key files only as its own buyer (403), and non-owners cannot use the owner's channels (422). Unauthenticated intake is capped per simulated day.

**Privilege escalation.** Tiers are enforced by code, never by prompts. The executor trusts no caller-supplied tier, actor or approval. Self-approval, circuit resets by the agent, forged mandates, reused nonces, backdated operations, an agent-authored `CommitPurchase` and a non-owner document decision are refused and logged. The agent key can no longer pre-claim the owner's decline key (a random part, SEC-04) or trip a buyer's circuit to block the owner (SEC-05); one buyer request can hold only one live agreement (SEC-02, SEC-03).

**Privacy leakage.**

- The compiler never sees the mandate, state, menu or reservations. Outbound text is template-filled; data requests get one fixed reply; the egress guard blocks any protected value or canary (algorithm 7). A contract's terms are protected values owned by that counterparty.
- **R-11 (16 Oct, owner's decision).** The agent key's chat no longer reads cash, the floor, limits, caps, the break-even or verdict JSON; it gets the allow-list view behind the egress guard.
- **R-10 (16 Oct).** A keyed buyer may send **5** offers or messages per simulated day (`BUYER_ATTEMPTS_PER_DAY`); past that, 429 `BUYER_BUDGET_EXHAUSTED` in neutral words and one `SEC-BUDGET-` security event per buyer and day. This limits probing of the accept/counter threshold; the counter's face still reveals the funding gap until the base-rounding work in integration lands.
- Read routes require the owner token. Cache mode sends nothing off the machine; in live mode only the inbound documents and the schema leave it.

**Compliance, in brief.** In live mode a buyer's documents go to the configured model provider for extraction only; sending a real document containing personal information to a provider outside mainland China would be a cross-border transfer under PIPL, an obligation on a deployer, not legal advice. The demo, tests and evaluations use synthetic data only. The UI labels model readings "AI-generated, for reference" until the owner confirms them. FLOW executes no real payment. Licence: [TEAM: licence to be chosen by the owner].

**Measured results.** The attack catalogue was run for this document on `0f92d433` (16 Oct 2026; `uv run python -m app.security.attacks`, `DEMO_MODE=1`, `LLM_MODE=cache`, no report written): **259 attacks, 0 with harm**: 126 through the API and 133 through chat (43 as the owner, 64 as a buyer, 26 with the agent key). Each attack runs on a fresh runtime through the real routes.

| Metric (the 126 API attacks) | Result |
| --- | --- |
| Unauthorised operations executed | **0** |
| Facilities added or changed by non-owners | **0** |
| Concessions booked from unevidenced claims; commitments activated by attacks | **0**; **0** |
| Money moved by attacks | **¥0.00** |
| Protected values disclosed outbound, or readable without the owner token | **0**, **0** |
| Canaries tripped outbound or in internal artifacts | **0**, **0** |
| Integrity failures | **0** |
| Detection rate (a SecurityEvent or a refusal code) | **98.41%** (124 of 126) |
| SecurityEvent rate | **73.02%** (92 of 126) |

Across all 259: 210 detected, 2 contained (Tier-2 requests by the agent, queued as designed) and 47 changed nothing without raising an event, 39 of them consent attacks whose correct result is that nothing runs. Scope: the catalogue attacks a subset of the 93 routes; the other routes are covered by targeted tests and the authorization sweep, not by the catalogue (`docs/security/CERTIFICATIONS.md`).

**Independent review and certifications.** An independent audit and five red-team rounds (1 to 3 Oct; 13 and 26 findings, all fixed with regression tests), then an independent Security Lead audit of 14 to 16 Oct, which reproduced every finding before recording it and certified exact commits (`docs/security/CERTIFICATIONS.md`):

| Commit | What | Verdict |
| --- | --- | --- |
| `0ba8e4c1` | SEC-01..05, 09, 10, 16..18 (intake hardening, one agreement per request, authority boundaries, the attack harness, event growth) | CERTIFIED |
| `081541d1` via `a6de32a2` | SEC-12/13 headers (no-frame, no-sniff, no-referrer; docs only in demo mode), with the Deals redesign and the UI redesign | CERTIFIED |
| `b6d1e519` | The capex buy side with CAPEX-1..4, set up your books with SETUP-1, 4, 5, 7 | CERTIFIED for scope S |

**Merged after the last certification, pending the Security Lead's verification:** R-11, R-10 and SEC-07 (merge `6408f7cb`, inside `0f92d433`); the read caches and the Chinese contract reading also merged after it. `0f92d433` itself is not yet certified. Release gate (`docs/security/RELEASE_GATE.md`): the local simulation (S) is GO on the certified commits; a networked demo (S-net) is CONDITIONAL; production (P) is NO-GO.

**Open, and listed in the self-assessment (section 04):** no runnable production configuration (SEC-06); audit trail not tamper-evident (SEC-08); unsafe with more than one process (SEC-11); full CSP and HSTS (SEC-12, partly fixed); anonymous offers can name any buyer (SEC-19); intake caps per process, not per key (SEC-20); session ids chosen by the client (SEC-21); egress number forms and derived values (SEC-22); CAPEX-4b; SETUP-2, 3, 6; one owner credential approves everything (R-2); the Tier-1 blast radius of a persuaded agent (R-3); PostgreSQL and the live model not certified.

## 05 Deployment and Testing

### Environment, deployment instructions, test cases and known limitations

**Environment.** API: Python 3.12 with `uv`; SQLite for local development and tests, PostgreSQL 16 in Docker Compose or Supabase with RLS. Web: Node with `pnpm`. The default `LLM_MODE=cache` needs no network or key. Target deployment: one Compose stack (web, api, postgres) on one VM in Hong Kong or Singapore, one API process. [TEAM: confirm the VM, its URL and a reachability test from mainland China.]

**Run locally** (from the repository root; `DEMO_MODE=1` is now required for the demo credentials):

```
scripts/dev.sh live                                                     # API :8000 + UI :3000 (in-memory books, cache mode, DEMO_MODE=1)
scripts/dev.sh mock                                                     # UI alone on the recorded mocks
cd services/api && uv sync && DEMO_MODE=1 uv run uvicorn app.main:app --reload
cd apps/web && pnpm install && NEXT_PUBLIC_API_MODE=live pnpm dev
DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py
python3 scripts/verify_evidence.py services/api/evals/e2e/latest/evidence/S01_scene1_counter_accept.jsonl
```

`scripts/dev-api.sh` also switches on `FEATURE_EXPOSURE` and the strategy flags that the web pages expect; `FEATURE_CAPEX_CONTRACTS=1` enables the buy side.

**Deploy.** Copy `infra/.env.example` to `infra/.env`, set `POSTGRES_PASSWORD`, `OWNER_TOKEN` and `AGENT_KEY`, then `docker compose -f infra/docker-compose.yml up --build`. Compose sets `DEMO_MODE=0` and binds the API to `127.0.0.1:8000` behind a TLS proxy. **Known gap (SEC-06):** the Compose file passes no `OWNER_PUBLIC_KEY_HEX` and nothing provisions books into an empty database, so with `DEMO_MODE=0` the API refuses to start until both are supplied; the web image is built against `localhost`. The submission is therefore demonstrated in configuration S (loopback, demo mode, simulated data).

**Test cases.** On `0f92d433`, `uv run pytest --co` collects **8,598** API tests (run for this document, 16 Oct 2026). The gate recorded in the `0f92d433` merge message: **API 8,556 passed** with 1 known failure (a books digest pin, issue #161), the mock browser suite **435/435**, the live browser suite **141/141**, web unit **163**, typecheck and lint clean. Tests by directory (collected):

| Area | Tests | Area | Tests |
| --- | --- | --- | --- |
| api (routes, presentation, Deals, setup, buy side) | 1,660 | capex | 111 |
| funding router | 1,151 | commitments | 90 |
| nl harness | 1,122 | books | 83 |
| egress guard | 975 | counterparties | 76 |
| compiler (incl. contract reading and the eval harness) | 731 | alerts | 76 |
| strategy | 489 | mandate | 74 |
| operations (executor) | 407 | what-if | 51 |
| security (attacks, fuzzers, metrics) | 279 | deals | 44 |
| verifier | 262 | certification | 41 |
| financial engine | 195 | covenants | 38 |
| pilot journal | 167 | ingest | 35 |
| persistence | 158 | concurrency | 30 |
| decisions | 144 | borrower file | 29 |
| evaluation harness | 24 | health; lending | 16; 10 |
| contracts; clock | 9; 9 | money and fixtures | 12 |

**Scripted tasks and evidence.** `scripts/run_scenarios.py --inproc` passed **49/49** tasks (87 `/nl` turns) on 3 Oct 2026 (`services/api/evals/e2e/latest/summary.md`); all 49 evidence chains verify with `scripts/verify_evidence.py`. The browser suites (`apps/web/e2e/`) cover the demo walk with the golden numbers, Home, the Deals list and deal page, accept-as-asked, documents and contracts, the buy side and capex, Cash, Receivables, Activity, chat, approvals, phone and touch layouts, axe checks and the adapter contract. Set-up has API tests (`tests/api/test_setup_books.py`); neither set-up nor the landing page has a browser spec yet. No screen-reader, zoom or real-device pass was run and no WCAG conformance is claimed.

**Known limitations.**

- **Free-text understanding is imperfect.** On the only untuned run, 52% verdict agreement and 4 wrong autonomous accepts out of 8. ADR-0005 now sends anything the compiler cannot account for to the owner, but the material-error and silent-error targets are not met on held-out 3.
- **Contract reading** is measured on a fictional set only (66% of fields), weakest on per-stage day counts and triggers, which FLOW's contract fields cannot express; scanned PDFs are refused (no OCR); the held-out set is pending; a confirmed sell-side contract or lender agreement never creates receivables or facilities.
- **Simulation.** Lenders, buyers, the bank feed and every receipt are simulated; facilities and rates are synthetic; there are no real bank integrations or loan applications.
- **Time-bound offers** cannot be accepted autonomously (settlement dates are not read into terms); extra requests are detected by cues.
- **Covenants** are tested "under this definition"; the bullet-loan DSCR is a reserve-coverage reading (the ¥500,000 12-month loan shows 1.014× and fails 1.25×). The projection screens only the obligations entered.
- **The rate ceiling sends an expensive cure to the owner** (whole-period billing: ¥200,000 for 10 days is 32.5% a year); the effective annual cost uses simple annualisation (U-009).
- **The buy side** is flagged off by default; a committed purchase cannot be cancelled; long-term plans are a labelled monthly estimate; vendor payments past the 120-day horizon are reported beside the result.
- **Set-up** opens books only in demo mode; corrections after opening re-run set-up and replace the books.
- **Security** (section 04): production configuration, tamper-evidence beyond the internal chain, multi-process safety and the counter's face revealing the funding gap are open; PostgreSQL concurrency and the live-model language boundary are not certified; one API process only.
- **Live mode is opt-in and less tested.** The demo, evidence and evaluation tables use cache mode; the only live accuracy runs are DeepSeek's held-out-3 row and the contract readings.
- **Performance.** EX01 evaluates in 22 s on the eight-customer busy books, which are parked (#162; `docs/handover/19_reconciliation_2026-10-16.md` section 4); the EX01 benchmark (`tests/funding/test_benchmark.py`, 350 ms) ran at about 400 ms on the Windows machine on 12 Oct and is hidden by `SKIP_PERF_BENCH=1`.
