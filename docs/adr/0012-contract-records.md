# ADR-0012: A confirmed contract is a record the deal summary reads, never the books

Status: accepted. Implemented 5 to 10 Oct 2026 on `feat/strategy-mvp-contracts` (brief `docs/handover/03_contract_ingestion_brief.md`), merged into `dev` on 11 Oct 2026 under an explicit, additive exception to the engine stability gate (CONTINUOUS_OPTIMIZATION section 0). Owner: main architect.

## Problem

An owner runs several deals and cannot recall the exact terms of each. The terms live in the signed buyer contract and the lender agreements, which the agent can read. But the language model never sets financial state (INVARIANT 1), the golden books are pinned across about 5,400 tests, and a document sent by a counterparty is untrusted text.

## Decision

1. **A document the agent read becomes a `ContractRecord`, not a change to `FinancialState`.** The record holds the document text, the reading (every term quoting an exact span, parsed by code; the model supplies no number or date of its own), the flags the lexicon raised, the sha256 of the text and the owner's decision. The deal summary reads the confirmed record beside the live books (what changed, what is in force, what is owed). Nothing from a document reaches the books, a projection, a verdict or a plan. A test proves the confirmed demo contract and agreements *reproduce* the golden buyer and facility data to the fen; the books are not re-seeded from them.
2. **The owner's decision is an owner-only operation on the hash chain, bound to the text shown.** `Executor.decide_document` appends CONFIRM_DOCUMENT or REJECT_DOCUMENT (log-only kinds, like RESET_CIRCUIT, not typed operations) with the document's hash; a hash that is not the stored one refuses (the owner decides on the exact text), anyone but the owner refuses with a PRIVILEGE_ESCALATION event, a document carrying text addressed to the agent can be rejected but never confirmed. The decision changes no money state; a lender agreement may be *linked* to an existing facility for reference, and the facility is unchanged.
3. **Storage is its own table, `contract_records` (migration 0007), cleared with the ledger**, with the record's canonical JSON beside the query columns; row-level security as for every table since 0002. It is not a decision fact (ADR-0011) and not part of the state hash.
4. **The feature is flagged (`FEATURE_CONTRACTS`) and on by default**: the Demo starts with its three sample documents confirmed so the deal card is populated; the recorded model outputs replay offline (`LLM_MODE=cache`) like offers.

## Considered and rejected

- Seeding `FinancialState` from the confirmed contract: it would make the model the source of the starting state and break every golden pin. The equality test gives the consistency without the write.
- A typed `Operation` for the decision: it would route an action with no money effect through the operation parser and the circuit breaker; a log-only kind keeps the chain complete and the executor's money paths untouched.
- Writing the decision at the API layer (as ADR-0011's facts are): the decision needs the executor's actor check, security event and atomic log-plus-record write; it is an owner action, not a derived fact.

## Consequences

- The stability set changed additively: new types in `domain/models.py` (and `TermSheetClause.field` gains `advance_rate`), `decide_document` and two log kinds in `operations`. Code older than this ADR cannot parse a stored record that holds an `advance_rate` clause; the term-sheet prompt moved to v3 and its cache entries were re-recorded.
- The reading's accuracy is proven only against documents written for it until the held-out contracts (brief section 6.8) are written by someone who has not seen the schema; no accuracy claim is made before then.
- Pre-merge review fixes (11 Oct): a repeated confirm returns the original decision instead of appending a refusal; the record's hash is validated against its text on load; extraction runs outside the runtime lock with size, page and chunk caps; a contract that does not say what its payment days count from is reported as not comparable, never as a match; `lang` on the deals and documents reads.
