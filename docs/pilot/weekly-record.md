# Pilot weekly record: template

Copy to `docs/pilot/<label>/week-NN/weekly-record.md` and fill every section. Figures are copied **as FLOW displayed them**
(the route's `*_display` strings and sentences), decisions **as the owner made them**, in the owner's words. Do not
recompute anything. Use only anonymous labels ("Buyer A"). Nothing is committed before section 8 is signed
(`docs/pilot/RUNBOOK.md` section 5). Leave a cell `none` rather than blank.

## 1. Session

| | |
| --- | --- |
| SME label | |
| Week number (1 = the first session) | |
| Session date (`as_of`) | |
| Who was in the session (roles only: owner, finance manager) | |
| Repository commit the runtime ran from (`git rev-parse --short HEAD`) | |
| Flags on | envelope, price curve, collections worth, pilot journal |
| Books changed since last week (cash, invoices added or paid, facilities, mandate number changed?) | |
| Operations log empty at the end (`/ledger` `chain_length` 0, no agreements) | yes / no |
| Notes on the runtime (a refusal sentence FLOW gave, a slow read) | |

Week 1 only: the date the owner confirmed the mandate's numbers on their own paper: ______

## 2. The three answers as FLOW displayed them

Files in this folder, with the hash of each file as committed (`sha256`; this is the journal's `snapshot_hash`).

| File | sha256 |
| --- | --- |
| `price-curve.json` | |
| `worth.json` | |
| `envelope-<buyer>.json` (one row per buyer) | |
| `cash.png`, `receivables.png`, `deals-<buyer>.png` | (screenshots: no hash needed) |

**Cash price (`sentence`):** "…"

**Collections (`top_action`):** "…"

| Rank (FLOW's net order) | Invoice label | Due | Outstanding | FLOW said it is worth | Action |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |

FLOW's amount order for the same invoices (largest outstanding first): ______
FLOW's gross-saving order (`gross_order`): ______
Net order differs from the amount order this week: yes / no

**Envelope (`primary`) per buyer:**

| Buyer | "You can live with: …" (exact) | Reason (exact) |
| --- | --- | --- |
| Buyer A | | |

## 3. Offers received since the last session

One row per real offer a buyer made (a request for longer terms, a discount, a rebate or an earlier payment). Number the
pilot's first ten offers; they are the envelope gate's sample. Fill "what the owner did" **in the owner's words**, then the
classification afterwards.

| No. | Date received | Buyer | What was asked (days, price, early payment, rebate) | What the owner replied or did (verbatim) | Days to reply | Against FLOW's envelope: inside the zone / one of the packages / outside / ignored the packages | Reason, one line, from the packages and zone table FLOW displayed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

Offers so far in the pilot: ____ (of the first ten: ____ inside the zone or a package, ____ outside or ignored)

## 4. The chase

In the order the owner did it, since the last session.

| Order done | Buyer | Invoice label | How (call, message, visit) | Why (the owner's words) |
| --- | --- | --- | --- | --- |
| 1 | | | | |

Shown FLOW's ranking after the above was written down.

- Did the owner's order follow FLOW's net order? yes / partly / no
- Does the owner say FLOW's order is the one they should have followed? yes / no / not sure
- If no or not sure, the owner's reason in their words: ______

## 5. Receipts since the last session

| Invoice label | Buyer | Due date | Date the money arrived | Days after due (negative = early) | Anything the owner did to bring it forward |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## 6. Counts for the gates

| Count | This week |
| --- | --- |
| Buyers on the books | |
| Of them, buyers with a recurring invoice | |
| Open receivables at once (rows in `worth.json` whose id does not start with `RI:`, which are invoices not yet issued) | |
| Buyer deals open at the same time (an offer being weighed or negotiated, not yet answered or closed) | |
| Did the owner ask for a conditional deal unprompted? (quote them if yes) | |
| Did the owner say the Alerts page already answers something these answers claim to? (quote them if yes) | |

## 7. Journal entries recorded (`journal.json`)

| Entry id | Answer (envelope / worth / curve) | Choice (followed / partly / ignored / not_applicable) |
| --- | --- | --- |
| | | |

## 8. Approval to commit

The owner has read this record, the three answers files, the screenshots and `journal.json`, and agrees they may be committed.
Counterparty, company, person and place names are anonymised; no bank identifier, tax number, phone, email or chat id appears
anywhere in the folder; the private state and mandate files and the name key are not in it.

| | |
| --- | --- |
| Owner's yes (initials) | |
| Date | |
| Anything the owner asked to leave out (and where it was removed) | |
| Checked for real names with the name key by | |

## 9. What confused the owner this week

Anything FLOW said that the owner did not understand, read differently from what it means, or did not believe, in their words.

______
