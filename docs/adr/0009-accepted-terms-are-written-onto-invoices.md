# ADR-0009: Accepted terms are written onto invoices, with a fixed scope

Status: accepted, 3 Oct 2026. Owner: technical owner. Closes audit A06 and A07.

## Problem

An accepted terms extension or price adjustment lives only as an obligation that every projection re-applies to
whatever invoices are still open. The clock issues invoices at their unadjusted face and due day, the executor
receives against the unadjusted face, and reconciliation reads the unadjusted due day. So:

- the agreed amount cannot be paid (a receipt of ¥421,890 on an invoice issued at ¥420,000 is refused);
- after a partial receipt the price change is recomputed on the remaining balance and ¥450 disappears;
- reconciliation calls an invoice overdue on day 47 while the alerts use day 62;
- "the next 3 invoices" moves to invoices 4, 5 and 6 once the first three are settled.

## Decision

1. **One contractual invoice.** `Receivable.face_fen` and `terms_days` are the contractual face and terms that
   every module reads. `base_face_fen`, `base_terms_days` and `applied` (adjustment ids) keep the original values
   and the provenance.
2. **Scope is fixed at acceptance.** When a commitment becomes ACTIVE, each bookable TERMS_EXTENSION and
   PRICE_ADJUSTMENT obligation becomes an `InvoiceAdjustment` in `FinancialState.invoice_adjustments`:
   - a named invoice, ONE_OFF or count-bounded scope becomes an explicit list of invoice ids, chosen once with
     today's selection rule (the buyer's unsettled invoices with issue day ≥ the effective day, in issue order;
     future recurring invoices are named by their generated id `RI:<buyer>:<issue day>`);
   - a perpetual or date-bounded scope becomes an issue-day range (`from_issue_day`, `until_issue_day`).
   Membership never depends on which invoices are open later.
3. **Written once.** At acceptance the adjustment is applied to the invoices in scope that are already issued
   (terms extended; face raised by `post(rate × contractual face)`). At issue, the clock applies the adjustments in
   scope to the new invoice with the same function. Nothing is applied twice; a receipt reduces the contractual
   face and nothing is recomputed on the balance.
4. **One function.** `app/financial/invoices.py` holds `resolve_scope` (obligation → scope) and `materialise`
   (base face, base terms, adjustments → contractual face, terms, applied ids). The projection uses them for
   invoices not yet issued and for obligations under evaluation; the clock and the executor use them when writing.
5. **Live commitments no longer re-apply.** `current_books` stops passing a live commitment's terms and price
   obligations to the engine: their effect is in the state. Obligations under evaluation (an offer, a what-if, a
   re-verification) are still passed and are applied on top with the same functions.
6. **Contingent gains.** An adjustment that is a gain and CONTINGENT is recorded with `contingent_gain = true`. The
   clock does not write it onto an invoice and the conservative projection ignores it (INVARIANT 5 unchanged);
   the expected projection applies it.
7. **Completion** (amended 3 Oct 2026 after the second red team, finding F7). A finite adjustment is consumed when
   its last invoice is issued and is then removed from `state.invoice_adjustments`; its scope stays readable on
   the invoices themselves (each carries the adjustment id `<commitment>:<obligation>` in `applied`), so no other
   record is kept. A commitment with no adjustment left and no other live obligation becomes FULFILLED, and its
   forward concession leaves `state.forward_concessions`, only when every invoice carrying its terms is SETTLED
   (or when it is revoked, §8): until the buyer has paid, the concession is still ahead and still counts against
   the aggregate and per-buyer caps. Releasing it at issue let an agreement split into one-invoice agreements over
   time bypass the cap. The clock applies this rule when it closes a day. A commitment that wrote nothing (only
   contingent gains) is fulfilled when its adjustments are consumed.
8. **Revocation** removes the commitment's remaining adjustments and its forward concession. Invoices already
   issued keep their contractual terms; changing those needs a credit or debit note, which is out of scope.

## Consequences

- Real Option B (60-day terms, +0.45%): `RI:BUYER-1:2` is issued at ¥421,890 due day 62; the bank receipt of
  ¥421,890 settles it; after a ¥100,000 partial receipt ¥321,890 is outstanding everywhere.
- "Next 3 invoices" stays on the three invoices chosen at acceptance.
- Day-0 evaluations of an offer do not change: the selection rule is the same, only when it is evaluated changes.
- Stored states gain fields with defaults; no migration is needed for JSON state rows.
