# ADR-0005: Autonomy requires positive proof; the default is the owner

**Context.** The third independent held-out set had never been seen by anyone tuning the compiler. On it, 4 of the 8 buyer offers the system accepted on its own were wrong. In each case the regex grammar kept the discount rate and dropped a clause that contradicted it or added to it:
- an invoice number and amount that don't exist;
- a transfer amount that contradicts the rate;
- a yuan discount that contradicts the percentage;
- an extra delivery request.

No grammar can be made complete. The safe path has to be safe by construction.

**Decision.** Accepting a counterparty's offer without the owner (Tier 1) requires all of:
1. The package is a pure early-pay discount on a named invoice, priced strictly below the exact break-even (ADR-0002 rounding; 0.8832% on the golden fixture).
2. `CompiledOffer.autonomy_eligible` is true. The compiler sets it only after a **coverage proof**:
   - every amount, rate, day count, date and invoice reference in every document is explained by the extracted obligations;
   - no other request or clause is left unread;
   - there are no authority claims or data requests.

   The field defaults to **false**.
3. Each discount's **stated** amount equals the whole face of the open invoice it binds to. Binding by default to "the only open receivable" never qualifies.

Anything else that would have been an ACCEPT becomes NEEDS_OWNER_APPROVAL, and the summary says why autonomy isn't proven. Owner-built typed offers (/nl plans, what-if) carry no free text and are exempt. Counters the buyer accepts are our own template terms, so they are unaffected.

**Consequence.** Unfamiliar wording can only ever cost the owner a click. It can no longer commit the business.
