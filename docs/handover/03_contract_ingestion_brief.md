# Brief: contract ingestion and the deal summary on the home page

Status: proposed, 4 Oct 2026. Not built. Agreed with the owner in principle; the team must agree to lift stability
mode for it (`docs/HANDOVER.md` section 4) before work starts.

Prototype of the target screen: https://claude.ai/artifact/3A2aRvK4XxcpxYW4BaqRNg (low fidelity, synthetic data, the
golden demo on day 34). The clause numbers, quotes and the deliverables list in it are placeholders.

Read `docs/HANDOVER.md` first for the repo's standing rules (branches, delegation format, integration loop, git).
This brief adds a feature; it does not change any of those rules.

---

## 1. What we want

An SME owner runs several deals at once, each at a different stage, and cannot remember the exact terms of each.
The home page should answer, for each deal:

- **What did we sign?** Price, invoicing, payment terms, early-payment terms, and what we must deliver.
- **What changed since?** Offers, our counters, what was accepted.
- **What is in force now?** Terms after the accepted changes.
- **Where does the money stand?** Each invoice: amount, due day, outstanding, late, financed, waiting for approval.
- **What next?** The one action the owner should take on this deal.

The terms must come from the **actual contract and lender agreements**, read by the agent, with every term
pointing at the clause it came from. The live status comes from the books we already keep.

## 2. Why

- **The sell.** "The agent read your contract, and every line here points at the clause" is far stronger than a
  summary stitched together from chat messages and fixtures. It answers the judge's question "where does the AI's
  understanding come from?"
- **Rubric.** Topic E names "business financial analysis" and "operational recommendations"; innovation and
  interaction is 30%. Owner confirmation of what the AI read is also a security story (30%).
- **The home page gap.** Today it shows the day, the opener, cash, approvals and alerts. It never says where each
  deal stands.
- **Bridge to v4.0.** The same reading of a contract is what v4.0 calls the payment-readiness ledger (Surface 3)
  and slips detection (contract vs. what was agreed). We build the reading now and show a first, small contract
  check; full deliverable tracking stays roadmap.

## 3. Decisions already made

| Decision | Detail |
| --- | --- |
| Scope of documents | **The buyer contract and the lender agreements.** One supply agreement with Foshan Home Retail (BUYER-1), plus the credit-line agreement (FAC-LINE) and the invoice-financing agreement (FAC-IF). The lease, guaranteed-loan and equipment-loan term sheets are a stretch goal. |
| Deals shown | **One deal, golden scenario only.** No new multi-deal scenario. The card shows Foshan Home Retail in full and placeholders for future deals. |
| The AI never writes the books | Extraction is a proposal. The owner reviews each field with its quote and confirms. Nothing reaches the financial state or a projection from the extraction alone (the core invariant: the language model never sets the starting state). |
| The golden books are not re-seeded from the contract | `fixtures/scenarios/golden_sme.json` and `fixtures/golden/golden_values.json` are pinned across ~5,400 tests and every document. Do not edit them. Instead, a test proves that the confirmed contract and agreements **reproduce** the golden buyer and facility data to the fen (section 6.7). |
| Inputs | Plain text, `.docx`, and PDF **with a text layer**. No OCR, no scans. |
| Offline demo | The demo documents are run once against the live model and the outputs recorded in `fixtures/compiler_cache/`, exactly like offers today. The default `LLM_MODE=cache` then replays them offline. |
| Honesty | The deck says plainly that the demo contract was written to match the synthetic scenario. Held-out contracts written by someone else are run and reported (section 6.8). |

## 4. What exists today (read before designing)

| Piece | Where | Fit |
| --- | --- | --- |
| Offer compiler | `services/api/app/compiler/` (`service.py`, `schema.py`, `grounding.py`, `prompts/`) | Strong base. Every item must quote an exact substring; code finds offsets and parses numbers; ungroundable fields abstain. **But** its schema is for short buyer messages: 7 concession types (`ObligationType`), no parties, contract value, milestones, deliverables or required documents. Long inputs only switch model (`HARD_CHARS = 1_500` in `backends.py`); no chunking. |
| Term-sheet compiler | `compile_term_sheet` in `compiler/service.py`; `build_term_sheet` in `compiler/grounding.py` (line ~1054); `POST /facilities/compile` in `api/offers.py` (owner only, returns a proposal) | Reusable for the lender agreements. Extracts principal, rate, fees (upfront and periodic), tenor, lead time, repayment, covenants (clean-down days parsed), Tier-3 clauses. **Gaps:** no advance rate (FAC-IF needs 80%), proposed facilities get a new `PROPOSED-…` id with `NOT_APPLIED` status and no link to an existing facility, and DSCR/leverage thresholds are not parsed into numbers. |
| Documents | `SourceDocument` in `domain/models.py`: `text` only, `channel` includes `term_sheet` and `attachment`, `filename` optional | No file parsing anywhere in the repo. |
| Recorded outputs | `compiler/cache.py`, `compiler/record_cache.py`, `fixtures/compiler_cache/*.json` keyed by prompt version + canonical documents | Use the same mechanism for the new prompt. |
| Injection and authority detection | `compiler/lexicon.py` | Run it on contracts too: a contract is untrusted input. |
| Books the summary reads | `books/current_books`, `FinancialState` (receivables, recurring invoices, invoice adjustments, lots, facilities), commitments, stored offers and verdicts, approvals queue, `alerts/reconcile.py` | Everything for "what changed", "in force now" and "money owed" already exists. |
| Home page | `apps/web/app/page.tsx`; cards in `apps/web/components/home/` | Add two cards. The web never computes money: every amount is a server display string (INVARIANT 13). |
| Day numbering | Golden `as_of` is `2026-10-01` = day 0; days are absolute integers (ADR-0006) | Contracts use calendar dates; convert with this anchor. RCV-A is issued on day −13 (18 Sep 2026), so the demo contract must be signed before that (the prototype uses 1 Sep 2026). |

## 5. Target behaviour

### 5.1 Owner flow

1. The owner uploads a document (or, in the demo, picks a fixture), says what it is (buyer contract or lender
   agreement) and who the counterparty is.
2. The agent extracts it. The owner sees a review screen: each field, its value, the quoted clause highlighted in
   the document, and the fields the agent left blank and why.
3. The owner confirms or rejects. Confirmation is logged. A confirmed document becomes a **contract record** the
   deal summary reads.
4. The home page shows a Deals card and a "Documents the agent has read" card (see the prototype).

### 5.2 The deal card (per buyer contract)

| Section | Source |
| --- | --- |
| Header: counterparty, contract reference, signed date, term, status pills | Contract record + books |
| Stage strip: contract read → terms negotiated → early payment in → collecting → fulfilled | Derived from the log, commitments and receivables |
| What the contract says, each term with its clause quote; terms the agent left blank | Contract record |
| What changed since signing: buyer asks, agent counters, acceptances, receipts | Stored offers, verdicts, commitments, log |
| Terms in force now, marked same as / different from the contract | Terms in force (template plus accepted adjustments, `docs/FINANCIAL_SEMANTICS.md`) |
| Money owed: each invoice, due day, outstanding, status (late, financed, advance waiting, not due) | Receivables, recurring invoices, lots, approvals, reconciliation |
| What we owe them (deliverables and required documents) | Contract record, **display only** (see open question Q1) |
| Contract check: does what was agreed fit the contract? | Contract record vs. commitments (first, small slips check) |
| Next action with buttons into existing flows | Existing alerts, approvals and reconciliation |

## 6. Build plan

Order matters: 6.1 to 6.3 are backend foundations; 6.4 needs them; 6.5 needs 6.4; 6.6 and 6.7 can start in
parallel with 6.2.

### 6.1 Document text extraction (new, small)

- New module `services/api/app/ingest/` with `extract_text(filename, bytes) -> str` for `.txt`/`.md`, `.docx` and
  text-layer PDF. Keep page and paragraph boundaries in the text so quotes stay readable.
- Libraries: **pypdf** (BSD) and **python-docx** (MIT). **Not PyMuPDF**: it is AGPL and the rules require licence
  compliance (`docs/research/topic-e-rules.md`).
- A PDF with no text layer returns a clear error ("this PDF is a scan; upload a text PDF or Word file"). No OCR.
- Text must be byte-stable: quotes are matched verbatim and cache keys hash the text. Normalise line endings to LF.

### 6.2 Contract extraction schema and prompt (new, the core)

- New schema `ContractExtraction` in `compiler/schema.py`, same design rules as the offer schema: `extra='forbid'`,
  every item carries quotes that must be exact substrings, numbers only as `*_text` inside the quote, no field that
  can express an operation, approval, tier or facility to add.
- Fields for a buyer supply contract: parties, contract reference, signed date, start and end dates, price per
  delivery or per unit, invoicing cadence, payment terms **with their basis** (from invoice, delivery or
  acceptance), early-payment discount and window, payment milestones (percentages and triggers), retention,
  late-payment interest, deliverables, documents required for payment, amendment clause.
- Grounding reuses `locate` and the parsers in `grounding.py`. A field that cannot be grounded abstains with a
  reason. A conflict between two clauses gives `CONFLICTING_SOURCES`.
- Long documents: split by clause or section headings, extract per chunk, merge, and keep each quote tied to its
  chunk's document offsets. Test a contract of ~10 pages.
- Run `lexicon.py` over the contract (data requests, authority claims, injected instructions inside a clause).
- New `compile_contract(doc)` in `compiler/service.py` through the same backend chain. The rules backend may
  return an empty extraction (all abstained): that is the correct offline result for an unrecorded contract.
- Version the prompt (`CONTRACT_PROMPT_VERSION`) so cache keys change with it.

### 6.3 Lender agreements: extend the term-sheet path (small)

- Add `advance_rate` to `ClauseField` and the facility build, so FAC-IF's 80% is read.
- Parse DSCR and leverage thresholds from covenant clauses into `threshold_bp` (clean-down is already parsed).
- Let the owner link a compiled agreement to an **existing** facility (FAC-LINE, FAC-IF) instead of proposing a new
  `PROPOSED-…` one. Confirmation records the link; it does not overwrite the facility (section 3).

### 6.4 Contract records, confirmation and the API (backend, needs 6.2 and 6.3)

- New domain contract `ContractRecord`: document id and hash, kind (buyer contract or lender agreement),
  counterparty id, the compiled extraction with spans, abstentions, status (PROPOSED, CONFIRMED, REJECTED),
  confirmed day, linked facility id for lender agreements.
- Storage: add to the `LedgerStore` port and both stores (`persistence/memory_store.py`, `sql_store.py`) with an
  Alembic migration. One agent only touches the store and the domain models (`docs/HANDOVER.md`: never
  parallelise edits to domain models).
- Confirmation must be logged in the hash chain. Recommended: a new owner-only operation `CONFIRM_DOCUMENT` that
  changes no money state, refused for anyone but the owner. This touches executor semantics, so it is the tech
  lead's call and one agent's job (open question Q2).
- Routes (owner token for everything; counterparties never see contract records):
  - `POST /documents` (upload or fixture id, kind, counterparty) → extraction as a proposal
  - `GET /documents`, `GET /documents/{id}` with spans for highlighting
  - `POST /documents/{id}/confirm`, `POST /documents/{id}/reject`
  - `GET /deals` and `GET /deals/{counterparty_id}`: the deal summary of section 5.2, composed read-only from the
    contract record and current books, with server display strings
- Chat: a read-only `SHOW_DEAL` intent ("where are we with Foshan?") answering from `GET /deals` is a cheap win for
  the interaction score. It executes nothing.
- The outbound guard (`egress/`) must treat contract terms as protected for counterparties, like other buyers'
  terms today.

### 6.5 Web (needs 6.4)

- Home: a `DealsCard` and a `DocumentsCard` in `apps/web/components/home/`, inserted after `PositionCard` in
  `apps/web/app/page.tsx`. Follow the prototype.
- A documents page: upload, review screen with each field beside the highlighted clause (reuse
  `components/annotated-text.tsx`, which already highlights offer spans), confirm and reject.
- All data through `lib/api.ts`; mocks recorded with `pnpm mocks:record`, never by hand; English and Chinese
  strings in `lib/dictionary.ts`; Playwright specs for the home cards and the confirm flow.
- Label extracted text "AI-generated, for reference" (a listed known gap; this is the place to close it).

### 6.6 Demo documents (fixtures, can start now)

- `fixtures/contracts/`: the Foshan Home Retail supply agreement (FHR-2026-07, signed 1 Sep 2026), the credit-line
  agreement, the invoice-financing agreement. Write them as realistic contracts (headings, numbered clauses,
  boilerplate), English, with key amounts that match `golden_sme.json` exactly:
  - buyer: ¥420,000 per monthly batch, an invoice every 30 days, 45 days from invoice, early settlement at 1.2%
    within 2 days (FAC-EARLYPAY), RCV-A as the invoice of 18 Sep 2026
  - credit line: ¥150,000 limit, 6.4%, no lead time, DSCR ≥ 1.25×, debt ≤ 2.5× annual EBITDA, clean-down 30
    consecutive days a year
  - invoice financing: ¥350,000 limit, 80% advance rate, 7.8% plus 0.25% per 30-day period, 3-day lead time,
    repaid from the invoice
- Provide each as `.md` and as `.docx`/text PDF to exercise 6.1.
- Record the compiler outputs once in live mode into `fixtures/compiler_cache/` (needs `ANTHROPIC_API_KEY` or
  `DEEPSEEK_API_KEY`).

### 6.7 The golden equality test (proves consistency)

- A test that confirms the three demo documents and asserts that the confirmed terms reproduce, to the fen and the
  day, the golden `recurring_invoices`, RCV-A's face and terms, FAC-EARLYPAY's rate and lead time, and FAC-LINE
  and FAC-IF's limit, rates, fees, lead time, advance rate and covenants.
- This is what lets us say "the books match the contract" without re-seeding the golden books.

### 6.8 Held-out contracts (credibility)

- Two or three contracts written by a teammate who has not seen the schema, with their expected fields labelled
  **before** the first run. Include at least one with payment "from acceptance", one with retention, and one with
  a clause the schema cannot carry.
- Report agreement, abstentions and any wrong field in a short report next to
  `services/api/evals/accuracy_summary.md`. Never quote a figure from a set the prompt was tuned on.

## 7. Rules that must hold

- The language model never sets financial state. Extraction → owner confirmation → record. Nothing from an
  extraction is projected, verified or executed.
- Every displayed contract term has a span that matches the document verbatim. No span, no term (it shows as
  "not found").
- Do not edit `golden_sme.json`, `golden_sme.mandate.signed.json` or `golden_values.json`. Do not change the
  engine, verifier, router or executor semantics beyond the one logged confirmation operation (if Q2 says yes).
- Web never formats money or rates itself.
- Default runs stay offline (`LLM_MODE=cache`) and the existing gate stays green: backend suite, 49/49 scenarios,
  255 attacks with 0 harm, `demo_run.py` exit 0.
- New attacks for the security catalogue: an injected instruction inside a contract clause, a contract from an
  unregistered sender, a counterparty asking for another buyer's contract terms, and a non-owner confirming a
  document. All must end with nothing confirmed and nothing leaked.
- Wording: "the agent read it, you confirmed it". Never "the AI signs" or "legally verified".

## 8. Suggested agent split

| Agent | Task | Owns | Depends on |
| --- | --- | --- | --- |
| A | 6.1 text extraction | `app/ingest/`, its tests, `pyproject.toml` deps | none |
| B | 6.2 contract schema, prompt, grounding, chunking | `compiler/schema.py` (new classes only), new `compiler/contract.py`, prompt, tests | none |
| C | 6.3 term-sheet extensions | `compiler/grounding.py` term-sheet part, term-sheet tests | none; coordinate with B on `grounding.py` (C edits only `build_term_sheet` and `_covenants`) |
| D | 6.4 records, store, migration, confirmation, routes, `SHOW_DEAL` | `domain/models.py` (new classes), `persistence/`, `api/documents.py`, `api/deals.py`, `nl/` intent | A, B, C merged |
| E | 6.6 documents and recording, 6.7 equality test | `fixtures/contracts/`, cache entries, the test | B and C for recording |
| F | 6.5 web | `apps/web` | D's API contract (can start on mocks of the agreed JSON shape) |
| G | 6.8 held-out set and report, security attacks | `fixtures/contracts_heldout/`, `services/api/evals/`, `security/attacks.py` additions | B, D |

Each brief to an agent follows the format in `docs/HANDOVER.md` section 3 (TASK, WHY, OWNED FILES, …, the return
format). Merge into `dev` one branch at a time with the integration loop after each merge.

## 9. Done when

- The three demo documents upload, extract, show on the review screen with highlighted clauses, and confirm.
- The home page shows the deal card and documents card as in the prototype, in live and mock mode, English and
  Chinese.
- The golden equality test passes.
- The held-out report exists, with its numbers stated honestly.
- New attacks pass with 0 harm; the existing gate is green.
- `docs/SYSTEM_WALKTHROUGH.md`, the technical document and the security self-assessment describe the feature and
  its limits.

## 10. Open questions (decide before or early in the build)

| Id | Question | Recommendation |
| --- | --- | --- |
| Q1 | Deliverables and required documents: show them only, or track their status? | Show only (extracted list with quotes). Tracking needs new state and an evidence workflow; that is v4.0's Surface 3 and a post-deadline item. The prototype's ticks are placeholders. |
| Q2 | Log confirmation as a new executor operation `CONFIRM_DOCUMENT`? | Yes, owner-only, no money effect, one agent. The alternative (a separate table outside the chain) is weaker for the audit story. |
| Q3 | Should a confirmed contract ever change the books (for a new buyer, outside the golden demo)? | Not before the deadline. Post-deadline it would create receivables and recurring invoices through an owner operation. |
| Q4 | Contract language: English only, or Chinese too? | English for the demo (submission language is English); add one Chinese held-out contract if time allows, since the compiler already handles Chinese offers. |

## 11. Time and the cut line

Rough effort with agents in parallel: 6.1 to 6.3 about two days, 6.4 two to three days, 6.5 two to three days,
6.6 to 6.8 alongside. Call it a week and a half of elapsed time. The submission deadline is 20 Oct, 23:59 UTC+8.

If time runs short, cut in this order: the stretch term sheets, Chinese, the `SHOW_DEAL` chat intent, the upload
of `.docx`/PDF (keep text fixtures), held-out set size. Never cut owner confirmation or the equality test. This
work must not delay the deck or the video recording.
