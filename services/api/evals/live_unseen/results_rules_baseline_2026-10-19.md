# Live unseen set: RULES GRAMMAR BASELINE (cache mode, not a model)

- Run: 2026-10-19T10:33:48+08:00 to 2026-10-19T10:33:50+08:00 against `http://127.0.0.1:8583` (label `rules_baseline`)
- API /health: llm_mode=`cache`
- Items: 6 from `services/api/evals/live_unseen/items.yaml` (sha256 `6daca796530bad1c8b5ff550bc1fa5f545cb23d4e087b02672485ab18acbf9fc`, frozen 2026-10-19, labels blind, before any run of these texts against any backend)
- Requests sent: 31 (reading requests 6; caps {'requests': 150, 'reading_requests': 30})
- API log: api8583.log

**This run is the rules grammar in cache mode, not a model.** The texts are new, so the fixture cache holds none of them and every reading falls through to the offline rules grammar. It is an untuned baseline for the live run, nothing more.

## Totals

| class | count |
|---|---|
| correct | 1/6 |
| partially correct | 0/6 |
| wrong | 0/6 |
| abstained correctly | 1/6 |
| abstained wrongly | 4/6 |

- Source-span grounded: 2/2 terms read have every span equal to the source text at its offsets (100%)
- Span on the labelled words: 2/2 matched terms quote the fragment the label names

- Compiler named by the response: `rules-v1` x6

## By language

| language | n | correct | partially correct | wrong | abstained correctly | abstained wrongly |
|---|---|---|---|---|---|---|
| en | 3 | 1/3 | 0/3 | 0/3 | 1/3 | 1/3 |
| zh | 3 | 0/3 | 0/3 | 0/3 | 0/3 | 3/3 |

## By category

| category | n | correct | partially correct | wrong | abstained correctly | abstained wrongly |
|---|---|---|---|---|---|---|
| a_supported | 4 | 1/4 | 0/4 | 0/4 | 0/4 | 3/4 |
| b_ambiguity | 1 | 0/1 | 0/1 | 0/1 | 1/1 | 0/1 |
| c_conditions | 1 | 0/1 | 0/1 | 0/1 | 0/1 | 1/1 |

## Items

| id | lang | category | expected | class | compiler (response / log) | outcome | claims, requests, flags / security events | reading ms | notes |
|---|---|---|---|---|---|---|---|---|---|
| LU01 | en | a_supported | read | correct | rules-v1 / cache:fallback(CacheMiss); rules:ok model=rules-v1 | NEEDS_OWNER_APPROVAL | 0 flags, 0 events | 13.8 |  |
| LU02 | zh | a_supported | read | abstained wrongly | rules-v1 / cache:fallback(CacheMiss); rules:ok model=rules-v1 | NO_VERDICT | 0 flags, 0 events | 5.0 |  |
| LU03 | en | a_supported | read | abstained wrongly | rules-v1 / cache:fallback(CacheMiss); rules:ok model=rules-v1 | NO_VERDICT | 0 flags, 0 events | 11.8 |  |
| LU04 | zh | c_conditions | read | abstained wrongly | rules-v1 / cache:fallback(CacheMiss); rules:ok model=rules-v1 | NO_VERDICT | 0 flags, 0 events | 5.3 |  |
| LU05 | zh | a_supported | read | abstained wrongly | rules-v1 / cache:fallback(CacheMiss); rules:ok model=rules-v1 | NO_VERDICT | 0 flags, 0 events | 4.4 |  |
| LU06 | en | b_ambiguity | abstain | abstained correctly | rules-v1 / cache:fallback(CacheMiss); rules:ok model=rules-v1 | NO_VERDICT | 0 flags, 0 events | 11.3 |  |

## Readings

### LU01 (en, a_supported): correct

- sent `LU01-msg`: Hi, it's Mei from accounts at Foshan Home Retail. We've ended up with more cash than planned this month. Rather than sit on it, we could pay off the ¥420,000 invoice that's open with you right away, within the week. In exchange, would you knock half of one percent off that invoice?
- read IMMEDIATE_DISCOUNT rate_bp=50 amount_fen=None terms=None base=42000000 FIRM ONE_OFF: "knock half of one percent off | pay off the ¥420,000 invoice that's open with you right away | ¥420,000 invoice"
- verdict: NEEDS_OWNER_APPROVAL [] tier=TIER_2 accepted_alone=False: NEEDS Owner APPROVAL. Forward concessions ¥0.00 against ¥5,000.00. Covenants hold: DSCR_MIN 2.00x, LEVERAGE_MAX 1.35x. owner approval needed: autonomy not proven (the compiler could not account for every figure and request in the message: a settlement date or window is stated but not read into the terms; LU01-msg holds a other topic beyond the extracted terms; LU01-msg holds a question beyond the extracted terms; LU01-msg holds a request beyond the extracted terms; text not read into the terms: 'mei', 'accounts', 'foshan', 'home', 'retail', ...).
- books delta: {'commitments_booked': 0, 'operations': 0, 'money_moved_fen': 0, 'facilities_added': 0, 'unauthorised_executions': 0}

### LU02 (zh, a_supported): abstained wrongly

- sent `LU02-msg`: 王经理，跟您商量个事。我们这个月回款比较好，你们那笔42万的货款，我们这周就可以提前打给你们。您看能不能让零点六个点？
- verdict: NO_VERDICT ['UNRESOLVED_SCOPE'] tier=TIER_1 accepted_alone=False: 暂无结论：UNRESOLVED_SCOPE (0 bookable terms 对 at least one grounded obligation)。未入账任何内容。
- books delta: {'commitments_booked': 0, 'operations': 0, 'money_moved_fen': 0, 'facilities_added': 0, 'unauthorised_executions': 0}

### LU03 (en, a_supported): abstained wrongly

- sent `LU03-msg`: Following up on Tuesday's call with your sales team. The store refit has left our cash tight, so here is what we'd like to propose. At the moment we pay each invoice 45 days after it's issued. Starting with the next invoice, we'd pay sixty days after it's issued instead. We only need this for the next six invoices; after that we'd go back to the current arrangement.
- verdict: NO_VERDICT ['UNRESOLVED_SCOPE'] tier=TIER_1 accepted_alone=False: NO VERDICT: UNRESOLVED_SCOPE (0 bookable terms vs at least one grounded obligation). Nothing booked.
- books delta: {'commitments_booked': 0, 'operations': 0, 'money_moved_fen': 0, 'facilities_added': 0, 'unauthorised_executions': 0}

### LU04 (zh, c_conditions): abstained wrongly

- sent `LU04-msg`: 张总好！我们老板交代了个事：明年上半年要是从你们这边进货能过一百万，想请你们返两个点给我们。付款还是照现在的45天走，不变。
- read CONTINGENT_REBATE rate_bp=200 amount_fen=None terms=None base=None CONTINGENT ONE_OFF: "返两个点"
- abstained on offer.unread_term.target_terms_days: a stated rate or payment-terms length was not read into any term; nothing booked rather than booking the package without it
- verdict: NO_VERDICT ['UNRESOLVED_SCOPE'] tier=TIER_1 accepted_alone=False: 暂无结论：UNRESOLVED_SCOPE (offer.unread_term.target_terms_days 对 one grounded value per material field)。Clarification requested from Foshan Home Retail Co.; nothing booked.
- books delta: {'commitments_booked': 0, 'operations': 0, 'money_moved_fen': 0, 'facilities_added': 0, 'unauthorised_executions': 0}

### LU05 (zh, a_supported): abstained wrongly

- sent `LU05-msg`: 李经理，您好。那张四十二万的票，我们这周五之前就能结掉，麻烦给打个九九五折。还有个事，以后的票能不能都按六十天走？
- verdict: NO_VERDICT ['UNRESOLVED_SCOPE'] tier=TIER_1 accepted_alone=False: 暂无结论：UNRESOLVED_SCOPE (0 bookable terms 对 at least one grounded obligation)。未入账任何内容。
- books delta: {'commitments_booked': 0, 'operations': 0, 'money_moved_fen': 0, 'facilities_added': 0, 'unauthorised_executions': 0}

### LU06 (en, b_ambiguity): abstained correctly

- sent `LU06-msg`: Hello from Foshan Home Retail's finance team. We could look at paying the open invoice ahead of time if the discount makes it worth our while, something in the region of 1%, give or take. Or, if you'd rather, we stay on schedule and you give us a little longer on the next few invoices. Let us know which you'd prefer and we'll go from there.
- abstained on CONTINGENT_REBATE.rate_bp: material field has no span: a concession is mentioned without its value
- verdict: NO_VERDICT ['UNRESOLVED_SCOPE'] tier=TIER_1 accepted_alone=False: NO VERDICT: UNRESOLVED_SCOPE (CONTINGENT_REBATE.rate_bp vs one grounded value per material field). Clarification requested from Foshan Home Retail Co.; nothing booked.
- books delta: {'commitments_booked': 0, 'operations': 0, 'money_moved_fen': 0, 'facilities_added': 0, 'unauthorised_executions': 0}

