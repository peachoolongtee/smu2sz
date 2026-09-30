# ADR-0003: Canonical fixture timeline and when funding lands

Spec v2 states a reserve breach on day 47 under 60-day terms but gives no dated events for it. The fixture keeps spec v2 §6.1 and adopts v1 example B's dated failure:
- The next monthly ¥420,000 invoice to Buyer 1 is issued on **day 2**. Under 45-day terms it's due on day 47; under 60-day terms, on day 62.
- An operating bill of **¥100,000** falls due on **day 47**.
- Receivable A (¥420,000) was issued on day −13 on 45-day terms, so it's due on day 32.
- Existing debt service (¥45,000 a month) feeds the covenants only. The dated flows are all-in.

With the full package accepted and no new funding, cash is ¥354,960 after day 20 and ¥254,960 on day 47. That's a **¥45,040 shortfall** against the ¥300,000 floor; it recovers on day 62.

## Funding timing
Hard constraints never rely on future availability: a line open today may be frozen tomorrow. So every source in a plan is **requested on the decision day (day 0)** and arrives after its lead time:
- the line on day 0;
- invoice financing on day 3;
- buyer early payment on day 2.

An invoice-financing advance against an invoice not yet issued is requested on the invoice's issue day. Invoice financing bills interest and its 0.25% fee in **whole 30-day periods**, the platform's convention. That's why the ¥210,000 advance (day 3 to day 32) costs one period, ¥1,871.30.

**Consequence:** the router searches amounts, not draw dates. A just-in-time draw scheduler could be cheaper, but it would rely on availability it can't guarantee.

## Cure cost
The day-47 shortfall is carried on the committed marginal source for a *permanent* need: invoice financing, because clean-down rules out the line. Requested on day 0 against the day-2 invoice, the advance lands on day 5 and is repaid on day 62: 57 days, billed as two 30-day periods, for **¥802.70** (¥577.50 interest + ¥225.20 fee). The extension's structural cost is ¥1,871.30 per invoice, and the screen shows both.
