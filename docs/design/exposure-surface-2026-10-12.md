# How buyer exposure, customer economics, the comparator and the envelope surface, and how they interact (design note, 12 Oct 2026)

Written by the lead for map #88's web phases, after the Deals walkthrough of ticket #105 (the moments picture, the path columns, the raised reply bar). It fixes where each new answer lives, what state they share, and what each reads from the server. The brief's section I is superseded by this note where they differ.

## 1. One selection, two toggles, nothing computed in the browser

The Deals page has exactly one piece of selection state, **the picked path** (as asked, Option A, Option B). It already drives the reply bar, the emphasised line and the column. Every new answer follows it:

- the exposure strip's capacity figure is the picked path's;
- the decision record shows the decided path's figures, with no selection;
- the comparator's rows are the paths; a path is a column, not a new page.

Two **view toggles** sit above the picture and never change the selection: **"If Foshan pays 30 days late"** (the stress) and, from Phase 3, **"If Foshan walks away"** (the customer-loss hypothetical). A toggle adds one dashed grey line for the picked path to the picture and one row of tiles under the moments; the moments list gains the stressed path's lowest point as a moment. Each toggle's sentence is the server's assumption ("a test, not a forecast"; "assumes Foshan stops buying from you").

The browser computes nothing: every figure, every "when", every tone and every sentence is a field of the exposure read. A surface with the flag off renders nothing, not a placeholder.

## 2. Where each answer lives (the remediation's order holds: conclusion → reply → cost → timing → consequence → authorisation → result → remaining task → evidence)

| Surface | What appears | Phase |
| --- | --- | --- |
| **Deals, the consequence band** (between the path columns and the folds) | "Your exposure to Foshan": three tiles. Concentration: "100% of what you are owed today (¥420,000) · no receipts due in 30 days". Late payment: "Paid 30 days late: cash −¥250,000 on 30 Nov, 65 days below your minimum; no committed facility covers the ¥550,000" (with the typical-delay figure beside it only above the history minimums, else "no completed payments yet"). Capacity after the picked path: "Option A leaves ¥0 of room for another payment until 1 Nov; today ¥81,000". A fold "Capacity in detail": the five headrooms before and after with "recovers on", and the stress rows (contractual, +30, typical). | 1 |
| **Deals, the picture** | The stress toggle above the chart; the dashed grey stressed line for the picked path; its lowest point as a moment ("Lowest, if paid late"). | 1 |
| **Deals, the "As they asked" column** | Under the authority pill, the economics context sentence: "Context: about 2.6% of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit (Demo assumption). It does not change what FLOW may do." An "Edit" text link opens the inputs sheet. | 2 |
| **Deals, the inputs sheet** (owner only) | Annual sales, margin with its basis (gross default), classification; each with a provenance label ("you entered", "estimated", "from your invoices"); writes `POST /buyers/{id}/inputs`; the page re-reads exposure. | 2 |
| **Deals, the walk-away toggle** | A dashed line and a tile row for the customer-loss copy: revenue and receipts removed once; the sentence states the assumption; no cash figure "net of avoided costs". | 3 |
| **Deals, "The most you can give"** | Becomes "What you can offer instead": the compensating-price answer for the asked terms ("55 days works if the price rises at least 0.25%"; "No price rise makes 60 days work: … ¥240,200 paid now and 0.40%"), read on demand (P4), the packages that pass their re-check, each with its authority class. | 4 |
| **The decision record** (`/decisions/[id]`) | The same exposure band after the consequence block, for the decided path; the economics sentence under the authorisation block; both read-only. | 1, 2 |
| **Receivables** | The buyer's payment-behaviour sentence under "Who pays when" (median days late with the count, or "no completed payments yet; the stress uses +30 days"); the concentration share as a pill on the table header. | 1 |
| **Home** | No new block. The open-offer row on "Your deals" gains one word of context only when the server says it is material ("Foshan is 100% of what you are owed"). | 1 |
| **Ask FLOW** | The page context carries the exposure read; three prompts appear on Deals ("What if Foshan pays late?", "How much room is left after Option A?", "How concentrated am I on Foshan?"), each answered from the stored read, never from model arithmetic. | 1 |

## 3. What each surface reads

- `GET /offers/{offer_id}/exposure?lang=` returns, for the offer's buyer, **all paths at once** (asked and each counter): `concentration`, `payments`, `stress` (rows per delay with the picked-path series for the picture), `capacity` (per path: the five windows before and after, `spare` = the X* search with its shape sentence and binding reason), `economics` (Phase 2: null until inputs exist, then the context sentence with provenance), `loss` (Phase 3). One read per offer, cached by books, mandate, day, buyer and commitments; switching the picked column is instant and needs no request. `response=` selects which path's figures the sentences name, and is what the decision record uses through `GET /decisions/{id}/exposure`.
- Receivables reads `payments` and `concentration` per buyer from the same module through the receivables read (additive fields), so the figures are the same object on both pages.
- The inputs sheet writes through `POST /buyers/{id}/inputs` and the firm row through `POST /firm/inputs`; both are owner-only, append-only, and never touch the books.
- The flag `FEATURE_EXPOSURE` gates the routes (403 FEATURE_DISABLED) and the web block (absent when the read is refused).

## 4. Rules the implementers hold

- Mandate and economics are two sentences, never one: the authority pill states what FLOW may do; the context sentence beneath says what the deal is worth; concentration and stress change wording and attention, never a verdict (property test P8: the verdict, tier, counters and plan are byte-identical with the flag on and off).
- Three authority classes everywhere a package or path is shown: FLOW can send it; needs your approval; over a limit you signed, only a new mandate changes that.
- The picture draws only what differs: the stressed line is the picked path only, dashed grey, labelled by its lowest moment; no event labels.
- Business mode: no codes, ids, day numbers, formulas; every sentence in en and zh; estimates worded as estimates ("we estimate", "Demo assumption", "you entered").
- Phone: the exposure band is three stacked tiles after the columns; the fold stays closed; the priced decision stays in the first viewport.
- Nothing here adds execution authority; the inputs sheet is the only write, and it writes context.

## 5. Build order

1. #105 lands in `dev` (the picture, the columns, the reply bar).
2. Phase 1 web: the exposure band, the stress toggle and moment, the record's band, the Receivables sentence and pill, the Home word, the Ask FLOW prompts, `e2e/exposure.spec.ts`.
3. Phase 2: the economics sentence and the inputs sheet.
4. Phase 3: the walk-away toggle (the comparator is the columns plus the two toggles; no new page).
5. Phase 4: "What you can offer instead" from the envelope's P4 to P6.
