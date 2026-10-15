# ADR-0014: A new owner sets up their own books, typed in and signed, never read in by the model

Status: proposed, 14 Oct 2026, on `feat/setup-books` (awaiting the owner's review). Owner: main architect.

## Problem

Every set of books came from a fixture (`fixtures/scenarios/*.json`). A new owner had no way to enter their cash, credit lines,
loans, customers, the invoices already out under a contract that is part-way through, their bills or their limits. Confirming a
contract writes no books (ADR-0012), the chat refuses to record facts, and the limits could not be signed in the app. The engine
could already represent any starting position (negative issue days, `settled_fen`, `drawn_fen`, recurring invoices, debts); only
the way in was missing.

## Decision

1. **The owner types the starting position in six steps** (business and cash; ways to borrow and loans; customers and the
   invoices already sent and not fully paid, with any repeating contract; bills; limits; review). Amounts travel as the text the
   owner typed and are parsed by code (`app.setup`); dates become day numbers against the start date (day 0). An invoice sent
   before the start keeps its negative issue day; a part payment is `settled_fen`; an invoice-financing balance is the sum of the
   advances recorded on its invoices; a repeating bill is written out as dated flows for three years. A monthly loss is refused,
   not hidden (the engine does not plan for one).
2. **A contract can fill a row, but the owner's figures are what count.** A confirmed contract, or one read during setup, suggests
   the customer's row for the start date: the cadence, the terms, the next invoice and the invoices already sent (invoice n of N).
   The owner edits it; the server builds the books from what the owner submits, never from the reading. A document read during
   setup waits in memory, unconfirmed, and is confirmed into the record (CONFIRM_DOCUMENT) under its new customer or lender when
   the books are opened.
3. **Opening is one owner act on a fresh chain.** `POST /setup/open` re-checks the draft, signs the limits and replaces the books,
   then appends one OPEN_BOOKS entry (log-only kind, with the books' sha256) at the head of the new chain. The owner signs by
   re-typing their sign-in. The limits are signed with the demo owner key, so opening is allowed only in DEMO_MODE: a real
   deployment's owner signs with their own key, which this server never holds. Replacing the books wipes the old record, as the
   demo reset does; the page says so before the owner signs.
4. **A blank scenario is a new business.** `fixtures/scenarios/blank.json` has no books; Business Home offers the setup instead of
   an answer and the other sections wait. `DEMO_SCENARIO=blank` starts an empty demo store on it.

## Considered and rejected

- Filling the books from the confirmed contract: the model would set the starting state (ADR-0012, INVARIANT 1).
- Recording facts through the chat: a casual remark would change the forecast (the reason the chat refuses).
- Keeping the old log across an opening: its commitments, approvals and verdicts name invoices and facilities the new books do
  not have.

## Consequences

- Corrections after opening re-run the setup and replace the books; corrections as new entries on the same chain are later work.
- The spreadsheet template on the welcome screen is not built and says so.
- The forecast still knows only what was entered; bills the owner forgets are not there.
