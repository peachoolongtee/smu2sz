# Home V2 state recipes (verified against dev d8598f8d, flags on, demo credentials) — input to slice 3
1 No pending decisions: POST /demo/reset; POST /alerts/{id}/act with next_action from /home → alert null, Needs you 0, one Waiting row. Fully empty: reset, negotiate cooperative, advance to day 2, POST /demo/bank-receipt.
2 One deal: POST /offers + /offers/{id}/evaluate with EX01_PACKAGE → one DECISION row, CAUTION.
3 Five deals sorted: EX01..EX05 → CRITICAL (deadline 12), CAUTION, CAUTION, NORMAL, NORMAL.
4 Three deals one customer: EX01, EX02, EX03 → Foshan "3 open negotiations · 3 need you".
5 Buyer reply pending: EX07_CONFLICT → WAITING BUYER_REPLY, "Nothing to resend."
6 Approval required: (a) POST /operations with X-Agent-Key, APPLY_FOR_FACILITY on FAC-GGL → APPROVAL row (customer_id null); (b) POST /demo/reset?scenario=short_facilities, run the plan twice → alert "waits for your approval", control APPROVE_PLAN.
7 Funding proposed: day 0, nothing run → kpis.funding.state PROPOSED ¥405,000.
8 Funding submitted not cash: run the plan → ARRANGED, "¥255,000 pending", SETTLEMENT row.
9 Payment overdue: EX01, negotiate cooperative, advance day 2, bank receipt, advance day 34 → COLLECTION row CRITICAL "¥291k overdue"; without receipt "Promised payment missed".
10 Cash critical: POST /clock/advance to day 13+, no plan → cash ¥60k, tone bad, CRITICAL.
11 Customer selected in crisis: /worklist ignores customer (alert persists); /buyers/BUYER-1/exposure and /customers/BUYER-1/overview; selection is URL state. Browser-side only.
12 Scenario still calculating: no server field; exposure cold read 0.7–1.3 s → the browser's fetch-pending state is the state (no computation, a quiet "Working out…" from the dictionary). Test with a delayed mock route.
Shapes: alert present {"key":"company-cash","eyebrow":"Company cash","text":"Reserve unsafe in 12 days. A funding plan is ready.","tone":"bad","primary":{"label":"Run or compare","href":"/"}}; no alert after plan: counts {needs_you 0, waiting 1, customers 2}; empty tab: [] with count 0.
Known server items (not on the critical path): busy 7-customer list needs scenario=public_sme (6 customers); stress delay fixed at 30 days (?stress=BUYER-1:60 ignored); /mandate read-only over HTTP; zh APPROVAL subject keeps the English facility name (server words); /offers/{id}/exposure wants response=counter:<k> not counter.
