# TermsLedger v2: architecture

A **modular monolith**: one FastAPI service (`services/api`), one Next.js app (`apps/web`) and one database. The shared contracts live in `services/api/app/domain/` and belong to the main architect. Modules talk only through those contracts.

Source of truth for the product: `docs/source/TermsLedger_v2_spec.txt` (spec v2) and `docs/source/termsledger_handoff_2026-10-01.md` (handoff). The vocabulary is in `CONTEXT.md`, the laws are in `docs/INVARIANTS.md`, and the decisions are in `docs/adr/`.

## Pipeline

```
buyer text ──► compiler (LLM, untrusted) ──► CompiledOffer (typed obligations + spans, or abstain)
                                                  │
FinancialState + Mandate + funding menu (owner/fixture only) ──────┤
                                                  ▼
             financial engine ──► Trajectory (daily cash, debt, forward concessions, months)
             funding router  ──► FundingPlan + marginal cost of funds
             covenants/mandate ──► Violations
             verifier ──► Verdict (ACCEPT / COUNTER / REJECT / NO_DEAL / NEEDS_OWNER_APPROVAL / NO_VERDICT)
                                                  ▼
             operations executor ──► typed Operation ──► hash-chained log + commitments
```

`/nl` orchestrates: it parses an owner or counterparty request into an intent, then calls the pipeline above. It **never** skips the verifier, and it can only emit typed operations.

## Module map and ownership

Everything lives under `services/api/app/`.

| Module | Owns | Exposes (see `domain/ports.py`) | May import |
| --- | --- | --- | --- |
| `domain/` | contracts, `money.py`, fixture loader, ports | the canonical models | nothing internal |
| `financial/` | daily cash recursion, debt ledger, forward-concession valuation, amortisation schedules | `project()`, `value_concessions()`, `annuity_payment()`, `amortisation_schedule()` | domain |
| `covenants/` | DSCR, leverage, clean-down per facility definition | `evaluate()`, `ratios()` | domain, financial |
| `mandate/` | canonical serialisation, Ed25519 signing, validity, tiers, mandate predicates | `canonical_bytes()`, `sign()`, `verify_signature()`, `check_validity()`, `tier_for()`, `check_predicates()` | domain |
| `compiler/` | LLM adapter (Claude + DeepSeek), prompts, schemas, fixture cache, span validation, injection/data-request detection, term-sheet mode, contract mode (chunking at headings, every term grounded in its clause) | `compile_offer()`, `compile_term_sheet()`, `compile_contract()` | domain **only** (no state, no mandate, no menu) |
| `persistence/` | SQLAlchemy tables, migrations, `LedgerStore` (SQL + in-memory) | `LedgerStore` | domain |
| `commitments/` | commitment lifecycle state machine, terms hash, nonce, expiry | `transition()`, `terms_hash()` | domain, persistence |
| `funding/` | funding menu view, same-basis costing, grid-search router, marginal cost, break-even | `plan()`, `marginal_cost()`, `break_even_discount()` | domain, financial, covenants, mandate |
| `verifier/` | verdict algorithm, reason codes, formulas, counter generation (priced from marginal cost) | `evaluate()`, `counters()` | domain, financial, covenants, mandate, funding |
| `operations/` | the executor: tier check, mandate version/signature/expiry, nonce, idempotency, circuit breaker | `Executor.execute()`, `decide()`, `propose_commitment()` | domain, financial (charge helpers), mandate, commitments, persistence |
| `security/` | attack catalogue, security-event logging helpers, refusal templates | `refuse()`, attack runners | domain, persistence |
| `counterparties/` | deterministic buyer kernel (hidden reservation), template verbaliser | `BuyerKernel` | domain |
| `nl/` | intent parsing, sessions (multi-turn: clarification, correction, fallback), plan → operations | `handle()` | everything above except compiler internals |
| `capex/` (flag) | NPV, payback, structure comparison; evaluation is side-effect free (`POST /capex/apply` is the separate owner step) | `evaluate_capex()` | domain, financial, covenants |
| `borrower_file/` (flag) | 微业贷-style borrower file from verified state (HTML, then PDF/DOCX); read-only, with provenance (generation day, versions, evidence hash); queues nothing | `build()` | domain, financial, covenants, persistence |
| `alerts/` (flag) | cash-flow alerts from the conservative trajectory; receipt reconciliation | `alerts()`, `reconcile()` | domain, financial |
| `ingest/` | text from an uploaded file (Word, PDF with a text layer, plain text); refuses scans, other types and oversize files | `extract_text()` | nothing internal |
| `contracts/` (flag) | contract records: a document read into a record, the suggested facility, the review view, the held-out scorer | `read_document()`, `record_view()`, `score()` | domain, compiler |
| `deals/` (flag) | the deal card: a confirmed contract beside the books, and its chat reply | `deal_summary()`, `deal_reply()` | domain, contracts, alerts (reconciliation), financial (invoice terms), operations (log reading), persistence |
| `api/` | FastAPI routers, dependency wiring | HTTP | everything |

A module may not import another module's internals, only its public functions. **Cycles are forbidden.**

## Conventions

- **Money** is integer fen and **rates** are integer bp. Derived rates are exact `Fraction`s, carried as `Ratio` in contracts. Use `app/domain/money.py` for every rounding, and never `float` for money. See ADR-0002.
- **Time** is an integer day offset from `FinancialState.as_of`. Month *m* covers days `30(m-1)+1 .. 30m`. A simulated clock (`current_day`) drives expiry.
- **Contracts** are strict, reject unknown fields and are frozen. To change state, build a new model; nothing mutates in place.
- **Feature flags** live in `app/config.py` (`FEATURE_*`). A disabled feature returns `FEATURE_DISABLED` and never breaks the core.

## Engine semantics (binding for `financial/`)

1. **Order within a day.** Apply inflows first (receipts, early receipts, draws, advances). Then scheduled outflows. Then interest, fees and repayments. `closing_fen` is checked against the floor.
2. **Receivables.** A receivable pays its face on its due day, less any financed advance being repaid (`ON_RECEIPT`). Recurring invoices generate receivables at `next_issue_day + k*every_days`, paid after `terms_days`.
3. **Obligations.**
   - `IMMEDIATE_DISCOUNT` settles the named receivable on `effective_day`: the receipt is the face minus the posted discount.
   - `TERMS_EXTENSION` with `days_delta` changes `terms_days` for invoices issued on or after `effective_day`. With `RECURRING_BOUNDED` it applies to the next N invoices only.
   - `CONTINGENT_REBATE` and other forward concessions affect the **forward-concession ledger**, not cash within the horizon, unless they carry an `effective_day` inside it.
4. **Funding actions.** Funds are requested on the decision day (day 0) and arrive after the facility's lead time. Hard constraints never rely on future draws; see ADR-0003.
   - `DRAW` posts simple interest at repayment.
   - `FINANCE_INVOICE` bills interest and fee in **whole 30-day periods**, repaid from the receivable.
   - `EARLY_PAY` receives the face minus the discount at the lead time. A partial early pay leaves a residual receivable.
5. **Conservative mode.**
   - Unconfirmed inflows are ignored.
   - Only `COMMITTED` facilities can be drawn; PENDING and NOT_APPLIED count as zero.
   - Contingent concessions count at maximum.
6. **Event convention** (clean-down depends on it): line `DRAW` and `REPAYMENT` events carry `ref=facility.id` and principal only; interest and fees are separate `INTEREST` / `FEE` events with the same `ref`.
7. **Expected mode** may include PENDING facilities and unconfirmed inflows. It is shown on screen and **never** used by the verifier for a hard constraint.
7. **Horizon.** The horizon always runs past the last repayment. The default is the mandate's `horizon_days`, extended to the last repayment day plus 1.
9. **Months.**
   - EBITDA is flat at `monthly_ebitda_fen`.
   - Debt service = existing `monthly_debt_service_fen` (the same payments leave cash on their days, `financial/debts.py`) + interest and fees posted in the month on facilities with `counts_in_debt_service` + scheduled amortisation.
   - Total debt = debt principal + month-end facility balances with `counts_in_leverage`.

## Verdict algorithm (binding for `verifier/`)

1. **Offer status.**
   - `CONFLICTING_SOURCES` → `NO_VERDICT` + `CONFLICTING_SOURCES` + a clarification request.
   - `ABSTAINED` → `NO_VERDICT` + `UNRESOLVED_SCOPE`.
2. **Security screen.** These never book anything and are logged as `SecurityEvent`s.
   - Sender not on the registry → `UNKNOWN_COUNTERPARTY`.
   - Each `funding_claims` entry → `UNKNOWN_COUNTERPARTY`; no facility is added.
   - Each `CLAIMED_PRIOR_CONCESSION` with no matching ledger commitment → `UNEVIDENCED_PRIOR_CONCESSION`; not booked.
   - Each `data_requests` entry → `DATA_EXTRACTION_REFUSED`; the reply is a fixed template that discloses nothing.
3. **Mandate validity:** signature, version, expiry and revocation. Any failure → `REJECT`, with no evaluation.
4. **Projection.** Project the conservative trajectory under the offer's bookable obligations. Then:
   - Get the router's committed plan for any gap.
   - Get the **marginal cost of funds**: the cheapest committed source able to carry a *permanent* need. Clean-down excludes the credit line.
   - Value the forward concessions at that rate over `forward_concession_horizon_days`.
5. **Predicates.** Check:
   - min cash every day (see below for `RESERVE_BREACH`);
   - aggregate and per-buyer forward-concession caps, including already-committed concessions;
   - the immediate-discount cap;
   - max APR;
   - covenants every month, plus the pro-forma covenant effect of permanently funding any terms extension;
   - Tier 3 clauses.

   A `RESERVE_BREACH` that the committed plan can cure is reported with `curable=true`, `cure_cost_fen` and a note, and does not by itself force a `REJECT`. **Netting:** only FIRM gains (a shorter term, a price adjustment) may offset forward concessions. Contingent gains count as zero.
6. **Outcome.**
   - A Tier-3 clause or an unknown counterparty → `REJECT`.
   - Any hard violation → `REJECT` with `counters()` attached, so the outward message is a `COUNTER` when a counter exists.
   - An early-pay discount at or above the break-even is a pricing fault (`DISCOUNT_ABOVE_BREAK_EVEN`) → `COUNTER`, like `MAX_APR_EXCEEDED` (spec §5.3, §8 example 2).
   - Otherwise, if the resulting operations need Tier 2 → `NEEDS_OWNER_APPROVAL`.
   - Otherwise → `ACCEPT`.
   - The buyer refusing every counter within the bounded rounds → `NO_DEAL`, and the router's plan covers the gap.
7. **Counters.**
   - An early-pay counter is priced below the break-even discount: `d/(1−d) < c`, where `c` is the invoice-financing cost share for 30 days, giving 0.88%. Option A uses 0.85%, up to the face that closes the gap net of the line.
   - A terms counter uses a `PRICE_ADJUSTMENT` that covers the per-invoice funding cost (Option B, 0.30% at 55 days on EX01).
   - The outbound text is template-filled and never reveals the floor, caps, menu or reservation values.

Every violation carries a `formula` and `inputs` the UI can show verbatim.

## Operations and tiers (binding for `operations/`)

- **Tier 1:** accept an early-pay discount on a named invoice with nothing else changed; any other accepted package is Tier 2 (spec §5.3's example; EV-01/EV-02). Counter and reject within the mandate (acceptance also below `tier2_single_commitment_fen` in forward value); draw on or submit invoices to a COMMITTED, owner-approved facility at any size within its limit (spec §5.3); record a commitment of that same early-pay kind; draw and repay a COMMITTED facility; submit an eligible invoice to the onboarded financing facility; receive payment.
- **Tier 2:**
  - apply for a facility;
  - accept or record any package other than an early-pay discount on a named invoice (rebates, terms changes in either direction, price adjustments, volume or operational concessions);
  - the capex application (`POST /capex/apply`, the owner's explicit step: evaluating capex queues nothing);
  - any single commitment above `tier2_single_commitment_fen`.

  Preparing the borrower file is not an operation: it is a read-only owner action (prepared, not sent) and queues nothing.

  The executor returns `PENDING_APPROVAL` and queues a `RequestOwnerApproval`.
- **Tier 3:** personal guarantee, pledging collateral, equity, mandate change, and adding a facility by anyone but the owner. Always `REFUSED`.
- The executor computes the tier itself; it never trusts a tier supplied by the caller. It also checks the mandate version, signature, expiry and revocation, then the nonce, the idempotency key, the commitment expiry and the terms hash, in that order.
- Every result is appended to the hash-chained log, **including refusals**.
- **Documents** (brief 03): the owner's decision on an uploaded contract's reading, `Executor.decide_document`, is logged as `CONFIRM_DOCUMENT` or `REJECT_DOCUMENT` (Tier 2, owner only, bound to the SHA-256 of the text, once). It writes the decision on the contract record and nothing else: a document never changes the books.

## LLM adapter (binding for `compiler/`)

- The backends are `claude` (Anthropic SDK: `claude-sonnet-5-5` by default, `claude-opus-5-5` for hard compilations) and `deepseek` (OpenAI-compatible SDK, `deepseek-flash`). A third backend, `cache`, replays recorded outputs keyed by the sha256 of the documents plus the prompt version.
- `LLM_MODE=cache` is the default for tests and the demo, and CI never calls a network.
- The model sees **only** the documents and the output schema. Mandate values, facility limits, reservation values and other buyers' terms never enter a prompt.
- Output is validated with Pydantic. A span must exactly match the document substring; otherwise the obligation is dropped and the field is abstained.
- A deterministic rule layer (regex/lexicon, zh + en) runs alongside the model to detect authority claims, data requests and unknown lenders. Detection is logged; the **architecture** is what refuses, not the prompt.

## API (owned by main; routers in `app/api/`)

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/nl` | multi-turn session: `{session_id?, actor, text}` → `{reply, intent, plan, verdict?, operations[], clarification?}` |
| `POST` | `/offers` | submit documents → `CompiledOffer` |
| `POST` | `/offers/{id}/evaluate` | → `Verdict` |
| `POST` | `/negotiate/{offer_id}` | bounded rounds with the buyer kernel |
| `POST` | `/router/plan` | → `FundingPlan` (committed + expected) |
| `POST` | `/facilities/compile` | term sheet → `CompiledTermSheet` (owner must approve) |
| `POST` | `/capex/evaluate` | flag `capex`; writes nothing |
| `POST` | `/capex/apply` | flag `capex`; owner only, bound to the evaluation's state version; queues the Tier-2 application |
| `POST` | `/borrower-file` | flag `borrower_file`; read-only owner action |
| `POST` | `/operations` | typed operation → `OperationResult` |
| `GET`/`POST` | `/approvals`, `/approvals/{id}` | the Tier-2 queue |
| `GET` | `/state`, `/trajectory`, `/ledger`, `/audit`, `/mandate` | read views; money pre-formatted on the server |
| `POST` | `/demo/reset` | reload fixtures, clear the ledger |
| `GET` | `/evidence` | JSONL execution evidence with hashes |
| `POST` | `/documents` | flag `contracts`; owner only; a demo document, an upload (base64) or pasted text → a contract record with the agent's reading |
| `GET` | `/documents`, `/documents/{id}` | flag `contracts`; owner only; the records, and one record's review view |
| `POST` | `/documents/{id}/confirm`, `/documents/{id}/reject` | flag `contracts`; owner only; `{doc_hash, link_facility_id?}` → `CONFIRM_DOCUMENT` / `REJECT_DOCUMENT` |
| `GET` | `/deals`, `/deals/{buyer}` | flag `contracts`; owner only; the deal card |
| `GET` | `/fixtures/contracts` | flag `contracts`; owner only; the demo documents |

## Storage

SQLAlchemy 2. Tests and local dev use SQLite (`DATABASE_URL=sqlite:///...`); deploy uses Postgres via Docker Compose (ADR-0001). The same `LedgerStore` interface has an in-memory implementation for unit tests. Contract records live in `contract_records` (migration `0005_contract_records`, with row-level security on Postgres); a decision is a compare-and-swap on a PROPOSED record.

## Frontend

`apps/web` is Next.js + TypeScript + Tailwind, with Recharts for charts. **It never computes money**; it displays server-formatted strings. Two shells since 5 Oct: Business (the owner's product, fed by the presentation read `GET /home` in `app/api/home.py` and the `presentation` fields on `GET /approvals/queue`) and Demo (the story and the engine views); see `docs/UX_AUDIT.md`. API types are generated from FastAPI's OpenAPI schema with `openapi-typescript`. Labels are in English and Chinese.

## Git workflow

- `main` is stable. `dev` is integration.
- Each agent works on `agent/<module>` in its own worktree, branched from `dev`, and commits only its owned paths.
- The main agent reviews, merges into `dev`, runs the whole suite, and fast-forwards `main` at checkpoints.
- Commit messages are one plain, concise sentence, with no co-author trailers.
