# ADR-0014: A confirmed customer contract can set up that customer's repeating invoices, by an owner operation

Status: accepted by the owner, 17 Oct 2026, and merged for the submission switched on in `pnpm demo`
(FEATURE_CONTRACT_TERMS); the Security Lead's review of the engine changes is pending. Owner: main architect. Amends ADR-0012 §1 for one narrow, explicit path; keeps
ADR-0012 §2 (confirming changes nothing).

## Problem

Confirming a customer contract on Attach deals files its reading (ADR-0012) and changes nothing in the books. For a customer
the books already hold (the demo's Foshan Home Retail) that is right: the reading is checked against the books and shown. For
a new customer, or a customer whose contract was signed after the books were opened, it leaves the forecast blind: the owner
has a signed agreement for an invoice every 30 days and the forecast expects none of that money. The owner asked (1b, "make it
do something") for confirming a contract to be able to set up that customer's agreed payment terms and expected repeating
invoices in the books, so the forecast reflects them.

The danger is the same one ADR-0012 and ADR-0013 (set up your books) refused: text written by a counterparty, read by a model,
becoming the books. The conservative forecast counts every invoice a repeating contract generates as money that arrives on its
due day (`trajectory._receivables`, `confirmed=True`), so a wrong repeating invoice overstates cash, and overstated cash makes
every later decision (a concession, a counter, a draw) look safer than it is.

## Decision

### 1. What a confirmed contract may set, and what it never sets

It may set exactly one thing: **one `RecurringInvoice` for the contract's customer** (`FinancialState.recurring_invoices`):

| Field | From the reading | Required to be |
| --- | --- | --- |
| `face_fen` | the PRICE term | one PRICE term, `unit = PER_DELIVERY` (a price per batch or delivery), amount > 0 |
| `every_days` | the INVOICING term | one INVOICING term stating a day interval (1..366); "monthly" is not a day count and blocks |
| `next_issue_day` | the INVOICING term's first invoice date | stated; the first issue on the contract's cadence on or after today (`BuyerContractTerms.next_issue_day`) |
| `terms_days` | the PAYMENT_TERMS term | one PAYMENT_TERMS term counted from the **invoice date** (the books count from it), in calendar days (0..365) |

These are the four figures `app.contracts.derive.buyer_terms(...).recurring(today)` already derives for the deal card's check.

It **never** sets, whatever the contract says: cash, receivables already issued (the contract's scheduled or opening
invoices; whether they were paid is a bank fact, not a contract fact), receipts, facilities or anything on the funding menu,
the mandate or its caps, forward concessions, debts, counterparties or the registry, invoice adjustments, commitments, and
anything Tier 3 (guarantees, collateral, equity). A lender agreement, a capex contract (ADR-0013 capex: its own
`CommitPurchase`), and a rejected, proposed, superseded or blocked document set nothing.

Clauses that are read but not set, and why:

- **Early payment** (the buyer may settle early at a discount): an option, not a schedule. The conservative forecast never
  assumes an early receipt (ADR-0007); taking one is an offer evaluated on its own. Shown beside the step as "not set up".
- **Rebates, volume or price concessions:** the contract reader has no field for them (ContractField), so nothing is read and
  nothing is booked. A rebate the supplier signed is a forward concession; booking it from text would be the model setting a
  cap's consumption. Out of scope; open question for the owner (§9).
- **Milestones, retention, late interest:** not a repeating invoice; shown, not set.
- **The contract's end date:** the engine's `RecurringInvoice` has no end. If the contract states an end date that falls
  inside today's forecast window (today + the mandate's `horizon_days`), the step is **blocked** rather than forecasting
  invoices the contract does not promise. A later end date is set up with a warning that FLOW will keep expecting invoices
  after it until the owner undoes the set-up (§9 asks for an end day on `RecurringInvoice`).

### 2. A separate, explicit, typed owner operation, never a side effect of confirming

Confirming stays what ADR-0012 says (CONFIRM_DOCUMENT, no money state). Setting up the terms is a second act, after
confirmation, on its own control: **`SetUpContractTerms`** (kind `SET_UP_CONTRACT_TERMS`), a typed `Operation` in
`domain/models.py` run by the executor, the only writer of the books.

- **Tier 2, always** (`mandate/tiers.py` `_ALWAYS_TIER2`, beside `ApplyForFacility` and `CommitPurchase`), and **owner-only**:
  a request by anyone but the owner (AGENT, COUNTERPARTY, SYSTEM) is refused before it is queued, with a
  PRIVILEGE_ESCALATION security event, exactly as CAPEX-2 does for `CommitPurchase`. Nothing a caller supplies lowers it.
- **Approval.** The owner's press of "Set up in my books", after the before/after forecast is shown and confirmed in a
  dialog, is the Tier-2 approval: the route queues the operation as the owner (PENDING_APPROVAL, logged) and then decides that
  approval as the owner (`Executor.decide`, which re-runs every gate except the queue against today's mandate and books, logged
  under the approval id). The approvals row is APPROVED, so the security summary's "Tier 2 executed without an owner approval"
  count stays 0. If the decision cannot run (a refusal at decision time), the approval stays as the executor left it and the
  page says why. (The Security Lead may prefer the CommitPurchase shape, where the press only queues and the owner approves on
  the Approvals page; §9.)
- **Idempotency key** `contract-terms:<document id>:<terms hash[:16]>`: the same terms set up twice are one operation (a
  repeat is answered DUPLICATE, nothing re-run); other terms for the same document are another key and are refused by the
  conflict rule (§3), never silently added.
- **Bound to the document and the exact terms shown.** The operation carries the document's `doc_hash` and a `terms_hash`
  (sha256 of the canonical JSON of the document id, its text hash, the customer, the four figures and the span of each source
  term). The preview (`GET /documents/{id}/terms`) shows the figures and that hash; the operation carries both. On execution the
  executor re-derives the terms **by code from the stored record against today's books** (`app.contracts.terms_setup`) and
  refuses with TERMS_CHANGED unless the derived hash and figures are the ones carried: a reading edited in the database, a
  clock that moved the next invoice, or a different document cannot slip through under the owner's approval.
- **Re-verified on today's books**, inside the executor's unit of work: the document is still CONFIRMED and not superseded;
  the customer is still a known BUYER on the registry; the customer still has no repeating invoice (§3); no receivable already
  holds an id the new schedule would generate; and the books with the new invoice still project (an `EngineError` refuses).
- **Logged** in the hash-chained log like every operation: the queued row, the approved run (or its refusal), refusals by
  other actors with their security event.
- **Reversible by a logged compensating operation**, **`UndoContractTerms`** (kind `UNDO_CONTRACT_TERMS`, same tier,
  owner-only, same approval shape), naming the set-up's `op_id`. It removes the repeating invoice the set-up wrote, if it is
  still the one in the books (same customer, face, cadence and terms; next issue day on the same cadence, not earlier). Invoices
  the clock has already issued from it stay: they are real receivables now (as ADR-0009 §8 keeps issued invoices on revoke).
  A set-up can be undone once; an undone set-up can be set up again, which is a new operation.

### 3. Existing repeating invoices for that customer

The engine and many readers hold **one** repeating invoice per customer (`next(... for r in state.recurring_invoices if
r.counterparty_id == cp)`, `terms_in_force` requires exactly one). So:

- **None:** the set-up adds one. This is the case the owner asked for (a new customer contract).
- **One, identical** to what the contract gives (the demo's Foshan Home Retail): "Already in your books", nothing to do; no
  operation is offered, and one sent anyway is refused.
- **One, different:** **refused on conflict** in this version, showing both. Replacing a repeating invoice interacts with
  accepted terms written onto future invoices by id (ADR-0009 `receivable_ids` of `RI:<buyer>:<day>`), with live commitments
  on that customer and with the decision records; the owner corrects it through the setup (ADR-0013 set up your books) or waits
  for a replace path (§9).

### 4. Who the contract is with

The contract must name the chosen customer as its **buyer**: one PARTY_BUYER term whose name is the customer's registry name
(or its short form inside it), compared after NFKC, case folding and punctuation; and the customer must not be the contract's
PARTY_SUPPLIER. No PARTY_BUYER term, or a mismatch, blocks. The party check (`app/contracts/parties.py`, merged into dev in
batch 5 and brought into this branch) already prevents confirming a document that names neither party as the chosen counterparty
(PARTY_NOT_NAMED, blocking); its PARTY_UNCHECKED warning blocks this step; and this step compares with the same rule
(`parties.party_matches` over `parties.registry_names`), restricted to the PARTY_BUYER term.

### 5. Reading errors: only quoted, code-parsed figures; anything unchecked blocks

The four figures come only from terms that, re-checked by code at the moment of the preview and again in the executor:

- quote the document verbatim (`span.text == document.text[start:end]`, the value fragment inside the quote);
- re-parse to the same figure with the reader's own parsers (`parse_money`, `parse_days`, the date among the dates in the
  quote, `basis_of`, `unit_of`, `business_days`), so a number the model wrote that the text does not say is refused;
- are the only term of their field (two PRICE terms, or a term the reader dropped as conflicting, block);
- carry no abstention that is not a note (`term dropped`, conflicting sources) and no failed cross-check (`check failed`).

The reading's status must be COMPILED, the document must carry no blocking flag, and none of its flags may be a party flag.
Anything missing or unchecked blocks the step with the reason in words; nothing is assumed (INVARIANT 10).

### 6. Words and money

The server writes every figure and sentence of the step in English and Chinese (INVARIANT 13): the four terms with their
clause and quote, what is not set up and why, the before/after forecast (lowest forecast headroom and its day, the first day
below the reserve, cash at the end of the window, and the invoices and money from this customer inside the window), the
conflict and block reasons, and the result. The forecast effect is the conservative projection of current books
(`app.books.current_books`) with and without the new repeating invoice, the same projection Home uses. The browser computes no
money or date and writes no sentence about them; its own words are labels.

### 7. Security review points

- **Injection.** Contract text becomes at most four typed integers and one customer id, each from a verbatim quote and
  re-parsed by code; no text from the document reaches the books, a label or a prompt. A document with text addressed to the
  agent cannot be confirmed (ADR-0012), so it never reaches this step. A reading edited after confirmation (the hash binds the
  text, not the reading) is caught by the re-parse and the terms hash. Tests send contracts that instruct the agent, state the
  price twice, name another buyer, swap the parties, and write a figure the text does not say.
- **Privilege.** Owner-only routes (`require_owner`); the executor refuses the operation from AGENT, COUNTERPARTY and SYSTEM
  before queueing (PRIVILEGE_ESCALATION), so `POST /operations` with the agent key and an approval decided by the agent both
  fail; the chat has no path that builds it. It is never Tier 1.
- **Privacy.** The preview holds the reserve, headroom and forecast: owner-only, never on a counterparty route, never in
  outbound text. A repeating invoice in the books is protected from other buyers by the existing egress rules
  (`app/egress/protected.py` reads `state.recurring_invoices`).
- **Feature flag** `FEATURE_CONTRACT_TERMS`, **default off**: off, the routes answer 403 FEATURE_DISABLED, the executor refuses
  the operation (whichever route queued it) and the web hides the step.

### 8. The engine stability set, minimised

| File | Change | Why |
| --- | --- | --- |
| `app/domain/models.py` | two operation types (`SetUpContractTerms`, `UndoContractTerms`) added to the `Operation` union | an executor operation must be typed to be logged, parsed back and replay-checked |
| `app/mandate/tiers.py` | both added to `_ALWAYS_TIER2` | an unknown operation is Tier 3; these are always the owner's decision |
| `app/operations/executor.py` | two handlers, the owner-only gate (before queueing and at run), the approval reasons | the executor is the only writer of the books |

Nothing changes in `financial`, `verifier`, `funding`, `alerts`, `clock` (it already issues repeating invoices), `books`,
`covenants` or `mandate` beyond the one line. The derivation and the words live outside the set
(`app/contracts/terms_setup.py`, `app/api/contract_terms.py`). No migration: `recurring_invoices` is part of the stored state.

### 9. Open questions

For the owner:

1. Replace a different repeating invoice from a newer contract (with the before/after shown), or keep refusing and send the
   owner to the setup?
2. Should a rebate or price clause in a contract be read and booked as a forward concession (it uses the cap)?
3. Contracts invoiced monthly ("on the last day of each month") or with milestone payments: set up as dated invoices?
4. The opening or scheduled invoices a contract lists (RCV-A): offer to add those not yet issued?

For the Security Lead:

1. One press (queue and approve in the owner's request, as built) or two (queue on Attach deals, approve on Approvals, as
   `CommitPurchase`)?
2. The contract end date: add `until_issue_day` to `RecurringInvoice` (an engine change: the trajectory, the clock and
   `invoices._future`) so a set-up stops at the contract's end, instead of the block-inside-the-window rule.
3. Should the set-up also bind `state_version` (refuse when anything in the books moved since the preview), or is the
   re-derivation on today's books (as built) enough?

## Implementation note, 17 Oct 2026 (`feat/contract-sets-terms`)

- Derivation: `services/api/app/contracts/terms_setup.py` (`derive`, `terms_hash`); routes: `services/api/app/api/contract_terms.py`;
  executor: `Executor._set_up_terms`, `_undo_terms`, `_owner_only_terms`; flag `FEATURE_CONTRACT_TERMS` (`app/config.py`).
- Web: `apps/web/components/contract-terms-step.tsx` on the review of a confirmed buyer contract (`document-review.tsx`); mock
  `apps/web/mocks/contract_terms.json` from `record-mocks.mjs --contract-terms` (the demo agreement only: ALREADY, and BLOCKED once
  superseded); the full flow is `apps/web/e2e/contract-terms.spec.ts` on the live project, whose API starts with the flag on.
- Test contract: `fixtures/contract_terms/dgos-2026-09-supply-agreement.md` (Dongguan Office Supplies, BUYER-2, not a demo starting
  document). On the demo books it adds ¥180,000 every 30 days from day 14, payable in 45 days: three receipts inside the 120-day
  forecast (¥540,000); the lowest forecast headroom (day 30) does not move, cash at the end of the window rises by ¥540,000.
- Tests: `tests/contracts/test_terms_setup.py`, `tests/operations/test_contract_terms.py` (both stores),
  `tests/api/test_contract_terms.py`, `tests/mandate/test_tiers.py`.

## Considered and rejected

- **Setting the terms on confirmation.** Confirming is a statement about the reading; setting up is a change to the forecast.
  One press doing both would make a document upload one click from changing what every decision relies on.
- **Writing the reading's figures as sent by the browser.** The browser shows; the executor re-derives from the stored record.
- **Rewriting the terms of open invoices** to the contract's terms: changing an issued invoice needs a credit or debit note
  (ADR-0009 §8).
- **A log-only kind** (like CONFIRM_DOCUMENT): this one changes money state, so it goes through the typed pipeline with its
  tier, mandate check and idempotency.

## Consequences

- The forecast can now rely on money a contract promises. That is the point and the risk; it is why the step is the owner's,
  Tier 2, bound and reversible.
- After an undo, the receivables the clock issued from the set-up stay in the books.
- The demo's starting books are unchanged (the flag is off by default, and the demo customer's contract already matches).
