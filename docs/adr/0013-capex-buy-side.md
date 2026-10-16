# ADR-0013: The buy side: a committed capex contract books its payment schedule

Status: proposed, 14 Oct 2026, on `feat/capex-buy-side` (handover: `docs/capex_handover.md`). An explicit, additive exception
to the engine stability mode (docs/HANDOVER.md section 3), given by the owner on 14 Oct 2026. Owner: main architect.

## Problem

Every deal in TermsLedger has the SME as the supplier: a buyer asks for terms, the verifier prices the concession, the
executor commits it. The owner also buys: capital equipment from a vendor, paid in milestones, financed from cash, the
committed line, the vendor's own terms or a loan. Capex mode (`app/capex`) already screens one purchase price against the
covenants and the reserve, but it does not know the contract, cannot book the purchase, and says nothing about the
company's overall health, its eligibility for larger loans, or how several purchases fit a long-term plan.

ADR-0012 says a confirmed contract is never booked. A purchase the owner commits to must be, or every projection after it
is wrong by the price of the equipment.

## Decision

1. **`DocumentKind.CAPEX_CONTRACT`.** A vendor contract is read by the existing contract reader (the same fields; nothing
   new in `ContractField`), with its own material rule: a price and either milestones or payment terms. Confirmation stays
   a log-only `CONFIRM_DOCUMENT` that changes no money (ADR-0012 unchanged).
2. **The payment schedule is derived by code**, from the confirmed reading and the owner's timeline (signing, delivery,
   acceptance and invoice days, which no contract fixes). A trigger the code cannot classify, shares that do not add up,
   or a price that is not a lump sum make it not derivable (INVARIANT 10). Amounts are rounded once each through
   `app.domain.money.post`, and the last payment carries the remainder so the schedule sums to the price exactly.
3. **`CommitPurchase` is a typed operation, always Tier 2.** It names the confirmed document, its hash, the owner's timeline
   and the hash of the schedule the owner was shown. On approval the executor re-derives the schedule from the stored record,
   refuses if it differs, if the document is not a confirmed capex contract, if the hash is not the stored text's, if a
   payment day is already past, or if the contract was already committed; otherwise it writes one `CashFlow`
   (`FlowKind.CAPEX`, id `CAPEX:<document id>:<n>`) per payment and registers the vendor as a `SUPPLIER`. This is the one
   path from a document to the books, and every step of it is owner-approved and deterministic (INVARIANT 1).
4. **Analysis is read-only and labelled.** Financial health, the 90-day cash coverage ratio, debt capacity, loan eligibility
   against a synthetic catalogue, and long-term plan permutations write nothing. Figures resting on the owner's entries
   carry `OWNER_ESTIMATE`; the long-term model is a monthly estimate and never a hard constraint (INVARIANT 4: catalogue
   products and pending facilities count as zero).
5. **Flag `FEATURE_CAPEX_CONTRACTS`, default off until the gate passes.** With it off, every existing output is unchanged.

## Considered and rejected

- Reusing `Offer`/`Obligation`/`Verdict` for vendor terms: they model promises the supplier makes and feed the concession
  caps; the buy side would need a sign flip through every predicate and pinned figure.
- Booking on confirmation: it would make the owner's "the agent read it correctly" also mean "I am buying it", and it would
  break ADR-0012 for the other two kinds.
- New `ContractField`s (delivery date, acceptance, warranty): every existing reading's `not_found` list would change, and the
  dates a milestone waits for are operational expectations the owner states, not contract terms.
- A daily projection over five years for the long-term plans: too slow per permutation and beyond the mandate's horizon;
  the monthly estimate is labelled as such instead.

## Consequences

- Additive changes to the stability set: `DocumentKind.CAPEX_CONTRACT`, `FlowKind.CAPEX`, the `CommitPurchase` operation and
  its tier, an optional `schedule` on `CapexRequest` omitted from the serialised form while unset.
- Vendor payments past the projection horizon (120 days in the golden mandate) are reported beside the result, never
  silently dropped.
- A committed purchase cannot be cancelled yet (follow-up in the handover).
