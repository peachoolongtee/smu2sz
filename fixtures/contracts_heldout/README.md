# Held-out contracts (brief 03 §6.8)

**Status: pending.** No independent contract has been supplied yet, so the report says so and quotes no figure.

This set measures how well the agent reads contracts it was not written against. The demo documents in
`fixtures/contracts/` do not count: the contract grammar was written against them, so they say nothing about accuracy.

## Protocol

1. **Who writes them.** A teammate who has **not** seen the contract schema, the grammar or the demo documents writes
   two or three realistic supply contracts (English; one Chinese contract if time allows), each as a `.md` or `.txt`
   file in this folder. The person who wrote the reading code may not write or edit them.
2. **What they must include.** Across the set: at least one contract whose payment terms count **from acceptance**,
   at least one with a **retention**, and at least one clause the schema **cannot carry** (for example a price review
   formula, a volume rebate ladder or a currency clause). Normal boilerplate, numbered clauses and a signature block.
3. **Label before the first run.** In `labels.yaml`, before anyone runs the reading on the file, write what a careful
   human reads for every field in the schema below, and `null` for a field the contract does not state. Commit the
   labels in their own commit, before the first run, so the order can be checked in `git log`.
4. **Run and report.**

   ```bash
   PYTHONUTF8=1 uv run --project services/api python scripts/evaluate_contracts.py
   ```

   writes `services/api/evals/contracts_heldout_report.md` (and `.json`). Report the numbers as they come out. Do not
   change the grammar, the prompt or the labels after the first run and then report the second run as held-out.

## Label schema

```yaml
contracts:
  - id: HO-C01                      # stable id
    file: ho-c01-supply.md          # in this folder
    kind: BUYER_CONTRACT
    counterparty_id: BUYER-2        # who it is with (a buyer on the registry)
    written_by: "<name>"            # never the implementer of the reading
    labelled_on: "2026-10-06"       # before the first run
    expected:                       # one entry per field; null when the contract does not state it
      PRICE: {amount_fen: 12000000, unit: PER_DELIVERY}     # unit: PER_DELIVERY | PER_UNIT | PER_MONTH | LUMP_SUM
      INVOICING: {days: 30}         # or {months: 1}
      PAYMENT_TERMS: {days: 60, basis: ACCEPTANCE}          # basis: INVOICE | DELIVERY | ACCEPTANCE | MONTH_END
      EARLY_PAYMENT: null
      MILESTONE: [{rate_bp: 3000}]  # a list for the fields a contract may state several times
      RETENTION: {rate_bp: 500, months: 12}
      LATE_INTEREST: {rate_bp: 600}
      SIGNED_DATE: {date: "2026-08-15"}
      START_DATE: {date: "2026-09-01"}
      END_DATE: {date: "2027-08-31"}
      DURATION: {months: 12}
      CONTRACT_REFERENCE: {text: "DG-2026-031"}
      SCHEDULED_INVOICE: []
      REQUIRED_DOCUMENT: 3          # how many documents payment depends on
      DELIVERABLE: 2                # how many deliverables the supplier owes
    unsupported:                    # clauses the schema cannot carry, in words
      - "price review every quarter by the copper index"
```

Each labelled value is compared with the agent's reading of the same field. Only the keys a label gives are compared.

| Outcome | Meaning |
| --- | --- |
| AGREE | The reading states the labelled value, or both leave the field blank |
| ABSTAINED | The label has a value; the reading left the field blank (safe: the owner sees "not found") |
| WRONG | The reading states a value the label does not have, or a value where the label is null |

A WRONG field is the number that matters: a confirmed contract with a wrong term misleads the deal card, even though it
never reaches the books.
