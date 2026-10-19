# Live unseen set

A small, pre-labelled UNSEEN evaluation set for FLOW's model-assisted reading, to show (or fail to show) that the shipped
path completes a useful workflow on new text. Modelled on `../live_frozen`, scored by the same runner with the same rules.

DRAFT: written with the items, before any run. The protocol, the rules baseline and the owner's commands are filled in
after the labels are committed.

- `items.yaml`: 6 new synthetic buyer messages for BUYER-1 Foshan Home Retail Co. on the golden demo books (3 English,
  3 Chinese), labels written blind on 2026-10-19 before any run of these texts against any backend.

| id | lang | what it tests | blind label |
|---|---|---|---|
| LU01 | en | a rate in words over four sentences ("half of one percent" holds "one percent") | read: IMMEDIATE_DISCOUNT 0.5% on ¥420,000, firm, one-off; the agent may accept (below 0.88% break-even) |
| LU02 | zh | colloquial "让零点六个点" for paying the 42万 early | read: IMMEDIATE_DISCOUNT 0.6% on ¥420,000, firm, one-off; the agent may accept |
| LU03 | en | one extension spread over three sentences (45 now, "sixty days", six invoices) | read: TERMS_EXTENSION 60 days, bounded to 6 invoices; owner needed (a counter) |
| LU04 | zh | "返两个点" if H1 purchases pass 一百万, and "照现在的45天走，不变" | read: CONTINGENT_REBATE 2%, contingent; nothing else; owner needed (a counter) |
| LU05 | zh | "九九五折" on "四十二万" and "以后的票都按六十天走" | read: IMMEDIATE_DISCOUNT 0.5% on ¥420,000 + TERMS_EXTENSION 60 days, perpetual; owner needed (a counter) |
| LU06 | en | two alternatives, one approximate ("in the region of 1%, give or take"), one unquantified | abstain: hold and ask which option and what figure |
