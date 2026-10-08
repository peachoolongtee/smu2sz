# Verification of every displayed strategy figure (8 October 2026)

Wave 7 of map #47. A `verifier` agent called the three routes with the flags on, on the golden day-0 books and the day-34 books, and reproduced every figure from the kernel alone (`plan`, `project`, `evaluate`, `value_concessions`, `marginal_cost`, `smallest_step_covering`, the counters' `supplier_cost_fen`) by linear scans, never bisection and never importing `app.strategy`; then compared with the oracle under `fixtures/strategy/`. Result at `feat/strategy-mvp` ae85cbf: **555 figure rows, 0 mismatches**; every oracle difference is an expected one with its reason (the APR-capped collections ceiling on day 34, the counter face the row quotes on day 0, the oracle's shorter horizon). The APR cap was confirmed through the verifier itself: on RI:BUYER-1:2 (11 days early) 0.45% on ¥200,000 passes and 0.50% fails MAX_APR_EXCEEDED (16.67% against 15%). The harness flagged five injected faults. One observation, not a mismatch: on day 34 the terms-with-price lever shows the rule price (80 days, price up 1.05%) while the primary sentence shows the smallest passing price (0.95%); the two agree on day 0 (0.30%). Rows: displayed string | kernel source | direct reproduction | oracle | match.

```
curve | day0 | amount_display (arrival amount) | ¥10,000.00 | GRID_STEP_FEN | ¥10,000.00 | ¥10,000.00 | yes | 
curve | day0 | number of bands | 3 | funding.plan x 2 per arrival day | 3 | no oracle | yes | 
curve | day0 | band days 0..0 days | 0..0 | plan().total_cost_fen | 0..0 | no oracle | yes | 
curve | day0 | band days 0..0 value_display (cost(d+30)-cost(d) per ¥10,000) | ¥0.00 | plan().total_cost_fen(d+30) - plan().total_cost_fen(d) with a ¥10,000 inflow | ¥0.00 | ¥0.00 | yes | 
curve | day0 | band days 0..0 value_fen | 0 | same | 0 | 0 | yes | 
curve | day0 | band days 0..0 value_bp | 0 | round(value_fen*10000/1,000,000) | 0 | no oracle | yes | 
curve | day0 | band days 0..0 value_pct | 0.00% | fmt_pct(value_bp) | 0.00% | no oracle | yes | 
curve | day0 | band days 1..30 days | 1..30 | plan().total_cost_fen | 1..30 | no oracle | yes | 
curve | day0 | band days 1..30 value_display (cost(d+30)-cost(d) per ¥10,000) | ¥89.11 | plan().total_cost_fen(d+30) - plan().total_cost_fen(d) with a ¥10,000 inflow | ¥89.11 | ¥89.11 | yes | 
curve | day0 | band days 1..30 value_fen | 8911 | same | 8911 | 8911 | yes | 
curve | day0 | band days 1..30 value_bp | 89 | round(value_fen*10000/1,000,000) | 89 | no oracle | yes | 
curve | day0 | band days 1..30 value_pct | 0.89% | fmt_pct(value_bp) | 0.89% | no oracle | yes | 
curve | day0 | band days 31..120 days | 31..120 | plan().total_cost_fen | 31..120 | no oracle | yes | 
curve | day0 | band days 31..120 value_display (cost(d+30)-cost(d) per ¥10,000) | ¥0.00 | plan().total_cost_fen(d+30) - plan().total_cost_fen(d) with a ¥10,000 inflow | ¥0.00 | expected difference: the spike read only to day 90, the band runs to 120 (oracle ¥0.00 on 31..90) | yes | 
curve | day0 | band days 31..120 value_fen | 0 | same | 0 | 0 | yes | 
curve | day0 | band days 31..120 value_bp | 0 | round(value_fen*10000/1,000,000) | 0 | no oracle | yes | 
curve | day0 | band days 31..120 value_pct | 0.00% | fmt_pct(value_bp) | 0.00% | no oracle | yes | 
curve | day0 | every arrival day 0..120 (121 days): direct vs bands (mismatching days) | 0 | per-day plan cost difference | 0 | 0 | yes | 
curve | day0 | sentence (whole string rebuilt from the direct bands) | Cash in the next 30 days saves you ¥89.11 of funding cost per ¥10,000 (0.89%); after that, earlier cash saves nothing. | bands above | Cash in the next 30 days saves you ¥89.11 of funding cost per ¥10,000 (0.89%); after that, earlier cash saves nothing. | no oracle | yes | 
curve | day0 | sentence figures (in order) | ['30', '¥89.11', '0.89%'] | bands above | ['30', '¥89.11', '0.89%'] | no oracle | yes | 
curve | day34 | amount_display (arrival amount) | ¥10,000.00 | GRID_STEP_FEN | ¥10,000.00 | ¥10,000.00 | yes | 
curve | day34 | number of bands | 3 | funding.plan x 2 per arrival day | 3 | no oracle | yes | 
curve | day34 | band days 34..42 days | 34..42 | plan().total_cost_fen | 34..42 | no oracle | yes | 
curve | day34 | band days 34..42 value_display (cost(d+30)-cost(d) per ¥10,000) | ¥178.22 | plan().total_cost_fen(d+30) - plan().total_cost_fen(d) with a ¥10,000 inflow | ¥178.22 | ¥178.22 | yes | 
curve | day34 | band days 34..42 value_fen | 17822 | same | 17822 | 17822 | yes | 
curve | day34 | band days 34..42 value_bp | 178 | round(value_fen*10000/1,000,000) | 178 | no oracle | yes | 
curve | day34 | band days 34..42 value_pct | 1.78% | fmt_pct(value_bp) | 1.78% | no oracle | yes | 
curve | day34 | band days 43..60 days | 43..60 | plan().total_cost_fen | 43..60 | no oracle | yes | 
curve | day34 | band days 43..60 value_display (cost(d+30)-cost(d) per ¥10,000) | ¥89.12 | plan().total_cost_fen(d+30) - plan().total_cost_fen(d) with a ¥10,000 inflow | ¥89.12 | ¥89.12 | yes | 
curve | day34 | band days 43..60 value_fen | 8912 | same | 8912 | 8912 | yes | 
curve | day34 | band days 43..60 value_bp | 89 | round(value_fen*10000/1,000,000) | 89 | no oracle | yes | 
curve | day34 | band days 43..60 value_pct | 0.89% | fmt_pct(value_bp) | 0.89% | no oracle | yes | 
curve | day34 | band days 61..154 days | 61..154 | plan().total_cost_fen | 61..154 | no oracle | yes | 
curve | day34 | band days 61..154 value_display (cost(d+30)-cost(d) per ¥10,000) | ¥0.00 | plan().total_cost_fen(d+30) - plan().total_cost_fen(d) with a ¥10,000 inflow | ¥0.00 | expected difference: the spike read only to day 124, the band runs to 154 (oracle ¥0.00 on 61..124) | yes | 
curve | day34 | band days 61..154 value_fen | 0 | same | 0 | 0 | yes | 
curve | day34 | band days 61..154 value_bp | 0 | round(value_fen*10000/1,000,000) | 0 | no oracle | yes | 
curve | day34 | band days 61..154 value_pct | 0.00% | fmt_pct(value_bp) | 0.00% | no oracle | yes | 
curve | day34 | every arrival day 34..154 (121 days): direct vs bands (mismatching days) | 0 | per-day plan cost difference | 0 | 0 | yes | 
curve | day34 | sentence (whole string rebuilt from the direct bands) | Cash in the next 8 days saves you ¥178.22 of funding cost per ¥10,000 (1.78%), then ¥89.12 (0.89%) for the 18 days after; later, nothing. | bands above | Cash in the next 8 days saves you ¥178.22 of funding cost per ¥10,000 (1.78%), then ¥89.12 (0.89%) for the 18 days after; later, nothing. | no oracle | yes | 
curve | day34 | sentence figures (in order) | ['8', '¥178.22', '1.78%', '¥89.12', '0.89%', '18'] | bands above | ['8', '¥178.22', '1.78%', '¥89.12', '0.89%', '18'] | no oracle | yes | 
worth | day0 | ranked order of rows | ['RCV-A'] | net, gross, due day | ['RCV-A'] | no oracle (the oracle ranks by its own net) | yes | 
worth | day0 | gross_order | ['RCV-A'] | gross saving, due day | ['RCV-A'] | no oracle | yes | 
worth | day0 | first_breach_day | 12 | financial.project first closing < floor | 12 | 12 | yes | 
worth | day0 | RCV-A outstanding_display | ¥420,000.00 | state receivable.outstanding_fen | ¥420,000.00 | ¥420,000.00 | yes | 
worth | day0 | RCV-A action | offer_early_pay | rules of 5.3 on the direct figures | offer_early_pay | expected difference: oracle action is a different vocabulary (offer early pay up to 0.75%) | yes | 
worth | day0 | RCV-A effect today (day 0) saving_text | ¥3,113.93 | plan().total_cost_fen: base - received | ¥3,113.93 | ¥3,113.93 | yes | 
worth | day0 | RCV-A effect today (day 0) saving_display | ¥3,113.93 | same | ¥3,113.93 | ¥3,113.93 | yes | 
worth | day0 | RCV-A effect today (day 0) need_left_display | ¥0.00 | plan().need_fen of the received copy | ¥0.00 | ¥0.00 | yes | 
worth | day0 | RCV-A effect today (day 0) breach_days_removed | 20 | project() days below the floor, before - after | 20 | 20 | yes | 
worth | day0 | RCV-A effect before_due (day 27) saving_text | ¥532.49 | plan().total_cost_fen: base - received | ¥532.49 | ¥532.49 | yes | 
worth | day0 | RCV-A effect before_due (day 27) saving_display | ¥532.49 | same | ¥532.49 | ¥532.49 | yes | 
worth | day0 | RCV-A effect before_due (day 27) need_left_display | ¥360,000.00 | plan().need_fen of the received copy | ¥360,000.00 | ¥360,000.00 | yes | 
worth | day0 | RCV-A effect before_due (day 27) breach_days_removed | 5 | project() days below the floor, before - after | 5 | 5 | yes | 
worth | day0 | RCV-A effect first_breach (day 12) saving_text | ¥3,113.93 | plan().total_cost_fen: base - received | ¥3,113.93 | ¥3,113.93 | yes | 
worth | day0 | RCV-A effect first_breach (day 12) saving_display | ¥3,113.93 | same | ¥3,113.93 | ¥3,113.93 | yes | 
worth | day0 | RCV-A effect first_breach (day 12) need_left_display | ¥0.00 | plan().need_fen of the received copy | ¥0.00 | ¥0.00 | yes | 
worth | day0 | RCV-A effect first_breach (day 12) breach_days_removed | 20 | project() days below the floor, before - after | 20 | 20 | yes | 
worth | day0 | RCV-A gross_saving_display | ¥3,113.93 | = today effect saving | ¥3,113.93 | ¥3,113.93 | yes | 
worth | day0 | RCV-A ceiling[whole] face_display | ¥420,000.00 | Option A counter face / outstanding / ceil100(plan.need_fen) | ¥420,000.00 | ¥420,000.00 | yes | 
worth | day0 | RCV-A ceiling[whole] largest_rate_display | 0.70% | C1-C0 sweep + verifier APR cap | 0.70% | 0.70% | yes | 
worth | day0 | RCV-A ceiling[whole] cost_without_display (C0) | ¥3,113.93 | posted cost of the books | ¥3,113.93 | ¥3,113.93 | yes | 
worth | day0 | RCV-A ceiling[whole] cost_with_display (C1 at the ceiling) | ¥2,940.00 | C0 + (C1-C0) at ceiling | ¥2,940.00 | ¥2,940.00 | yes | 
worth | day0 | RCV-A ceiling[whole] beats_by_display (C0-C1 at ceiling) | ¥173.93 | -(C1-C0) at ceiling | ¥173.93 | ¥173.93 | yes | oracle read from its sweep at 70bp
worth | day0 | RCV-A ceiling[whole] mid_rate_display (ceiling/2 on the 5bp grid) | 0.35% | spike rule max(5, best//2//5*5) | 0.35% | no oracle (the spike has no mid rate; oracle sweep used below) | yes | 
worth | day0 | RCV-A ceiling[whole] mid_saving_display | ¥1,643.93 | -(C1-C0) at the mid rate | ¥1,643.93 | ¥1,643.93 | yes | oracle read from its sweep at 35bp
worth | day0 | RCV-A ceiling[whole] next_rate_display | 0.75% | largest + 5bp within the cap | 0.75% | 0.75% | yes | 
worth | day0 | RCV-A ceiling[whole] next_rate_dearer_by_display | ¥36.07 | C1-C0 at largest+5bp | ¥36.07 | ¥36.07 | yes | 
worth | day0 | RCV-A ceiling[need] face_display | ¥405,000.00 | Option A counter face / outstanding / ceil100(plan.need_fen) | ¥405,000.00 | ¥405,000.00 | yes | 
worth | day0 | RCV-A ceiling[need] largest_rate_display | 0.75% | C1-C0 sweep + verifier APR cap | 0.75% | 0.75% | yes | 
worth | day0 | RCV-A ceiling[need] cost_without_display (C0) | ¥3,113.93 | posted cost of the books | ¥3,113.93 | ¥3,113.93 | yes | 
worth | day0 | RCV-A ceiling[need] cost_with_display (C1 at the ceiling) | ¥3,054.54 | C0 + (C1-C0) at ceiling | ¥3,054.54 | ¥3,054.54 | yes | 
worth | day0 | RCV-A ceiling[need] beats_by_display (C0-C1 at ceiling) | ¥59.39 | -(C1-C0) at ceiling | ¥59.39 | ¥59.39 | yes | oracle read from its sweep at 75bp
worth | day0 | RCV-A ceiling[need] mid_rate_display (ceiling/2 on the 5bp grid) | 0.35% | spike rule max(5, best//2//5*5) | 0.35% | no oracle (the spike has no mid rate; oracle sweep used below) | yes | 
worth | day0 | RCV-A ceiling[need] mid_saving_display | ¥1,688.48 | -(C1-C0) at the mid rate | ¥1,688.48 | ¥1,688.48 | yes | oracle read from its sweep at 35bp
worth | day0 | RCV-A ceiling[need] next_rate_display | 0.80% | largest + 5bp within the cap | 0.80% | 0.80% | yes | 
worth | day0 | RCV-A ceiling[need] next_rate_dearer_by_display | ¥144.25 | C1-C0 at largest+5bp | ¥144.25 | ¥144.25 | yes | 
worth | day0 | RCV-A ceiling[counter] face_display | ¥257,200.00 | Option A counter face / outstanding / ceil100(plan.need_fen) | ¥257,200.00 | no oracle (Option A counter face: pinned only from the app's own run) | yes | 
worth | day0 | RCV-A ceiling[counter] largest_rate_display | 0.85% | C1-C0 sweep + verifier APR cap | 0.85% | no oracle (counter face) | yes | 
worth | day0 | RCV-A ceiling[counter] cost_without_display (C0) | ¥3,113.93 | posted cost of the books | ¥3,113.93 | no oracle (counter face) | yes | 
worth | day0 | RCV-A ceiling[counter] cost_with_display (C1 at the ceiling) | ¥3,027.77 | C0 + (C1-C0) at ceiling | ¥3,027.77 | no oracle (counter face) | yes | 
worth | day0 | RCV-A ceiling[counter] beats_by_display (C0-C1 at ceiling) | ¥86.16 | -(C1-C0) at ceiling | ¥86.16 | no oracle (counter face) | yes | 
worth | day0 | RCV-A ceiling[counter] mid_rate_display (ceiling/2 on the 5bp grid) | 0.40% | spike rule max(5, best//2//5*5) | 0.40% | no oracle (the spike has no mid rate; oracle sweep used below) | yes | 
worth | day0 | RCV-A ceiling[counter] mid_saving_display | ¥1,250.06 | -(C1-C0) at the mid rate | ¥1,250.06 | no oracle (counter face) | yes | 
worth | day0 | RCV-A ceiling[counter] next_rate_display | 0.90% | largest + 5bp within the cap | 0.90% | no oracle (counter face) | yes | 
worth | day0 | RCV-A ceiling[counter] next_rate_dearer_by_display | ¥54.51 | C1-C0 at largest+5bp | ¥54.51 | no oracle (counter face) | yes | 
worth | day0 | RCV-A quoted face | counter | counter face if it has a rate, else the plan's need | counter | no oracle | yes | 
worth | day0 | RCV-A mid_rate_display (row) | 0.40% | quoted ceiling mid rate | 0.40% | no oracle | yes | 
worth | day0 | RCV-A mid_saving_display (row) | ¥1,250.06 | quoted ceiling mid saving | ¥1,250.06 | no oracle | yes | 
worth | day0 | RCV-A net_saving_display | ¥86.16 | call now: gross; else beats_by of the quoted ceiling | ¥86.16 | expected difference: the row quotes the Option A counter face (README of the fixtures); oracle is on the whole face | yes | oracle net_value_at_ceiling ¥173.93
worth | day0 | RCV-A net_saving_text | ¥86.16 | same | ¥86.16 | expected difference: the row quotes the Option A counter face (README of the fixtures); oracle is on the whole face | yes | 
worth | day0 | RCV-A worth_text | Saves ¥86.16 at the 0.85% limit; ¥1,250.06 if they take 0.40% | built from the direct figures | Saves ¥86.16 at the 0.85% limit; ¥1,250.06 if they take 0.40% | expected difference: the row quotes the Option A counter face (README of the fixtures); oracle is on the whole face | yes | 
worth | day0 | RCV-A action_sentence figures (incl. the due distance in days) | ['¥420,000.00', '32', '0.85%', '¥257,200.00'] | direct figures; state due_day - as_of_day | ['¥420,000.00', '32', '0.85%', '¥257,200.00'] | no oracle | yes | On the ¥420,000.00 due in 32 days, offer early payment at up to 0.85% on ¥257,200.00, or fund it instead.
worth | day0 | RCV-A reason_sentence figures | ['0.85%', '¥86.16', '0.40%', '¥1,250.06', '0.90%', '¥54.51', '¥3,113.93'] | direct figures | ['0.85%', '¥86.16', '0.40%', '¥1,250.06', '0.90%', '¥54.51', '¥3,113.93'] | no oracle | yes | At the 0.85% limit it saves you ¥86.16 against the cheapest funding plan; at 0.40% ¥1,250.06. 0.90% would cost ¥54.51 more than the plan. If it arrived today it would save you ¥3,113.93 and clear the shortfall.
worth | day0 | top_action figures | ['¥420,000.00', '32', '0.85%', '¥257,200.00'] | first ranked row's action sentence | ['¥420,000.00', '32', '0.85%', '¥257,200.00'] | no oracle | yes | On the ¥420,000.00 due in 32 days, offer early payment at up to 0.85% on ¥257,200.00, or fund it instead.
worth | day34 | ranked order of rows | ['RCV-A', 'RI:BUYER-1:2', 'RI:BUYER-1:32'] | net, gross, due day | ['RCV-A', 'RI:BUYER-1:2', 'RI:BUYER-1:32'] | no oracle (the oracle ranks by its own net) | yes | 
worth | day34 | gross_order | ['RI:BUYER-1:2', 'RI:BUYER-1:32', 'RCV-A'] | gross saving, due day | ['RI:BUYER-1:2', 'RI:BUYER-1:32', 'RCV-A'] | no oracle | yes | 
worth | day34 | first_breach_day | 42 | financial.project first closing < floor | 42 | 42 | yes | 
worth | day34 | RCV-A outstanding_display | ¥162,800.00 | state receivable.outstanding_fen | ¥162,800.00 | ¥162,800.00 | yes | 
worth | day34 | RCV-A action | call_now | rules of 5.3 on the direct figures | call_now | expected difference: oracle action is a different vocabulary (call now) | yes | 
worth | day34 | RCV-A effect today (day 34) saving_text | ¥1,374.61 | plan().total_cost_fen: base - received | ¥1,374.61 | ¥1,374.61 | yes | 
worth | day34 | RCV-A effect today (day 34) saving_display | ¥1,374.61 | same | ¥1,374.61 | ¥1,374.61 | yes | 
worth | day34 | RCV-A effect today (day 34) need_left_display | ¥37,200.00 | plan().need_fen of the received copy | ¥37,200.00 | ¥37,200.00 | yes | 
worth | day34 | RCV-A effect today (day 34) breach_days_removed | 0 | project() days below the floor, before - after | 0 | 0 | yes | 
worth | day34 | RCV-A gross_saving_display | ¥1,374.61 | = today effect saving | ¥1,374.61 | ¥1,374.61 | yes | 
worth | day34 | RCV-A quoted face | None | counter face if it has a rate, else the plan's need | None | no oracle | yes | 
worth | day34 | RCV-A mid_rate_display (row) | none | quoted ceiling mid rate | none | no oracle | yes | 
worth | day34 | RCV-A mid_saving_display (row) | ¥0.00 | quoted ceiling mid saving | ¥0.00 | no oracle | yes | 
worth | day34 | RCV-A net_saving_display | ¥1,374.61 | call now: gross; else beats_by of the quoted ceiling | ¥1,374.61 | ¥1,374.61 | yes | oracle net_value_at_ceiling ¥1,374.61
worth | day34 | RCV-A net_saving_text | ¥1,374.61 | same | ¥1,374.61 | ¥1,374.61 | yes | 
worth | day34 | RCV-A worth_text | Saves ¥1,374.61 | built from the direct figures | Saves ¥1,374.61 | no oracle (the oracle has no such string) | yes | 
worth | day34 | RCV-A action_sentence figures (incl. the due distance in days) | ['¥162,800.00', '¥1,374.61'] | direct figures; state due_day - as_of_day | ['¥162,800.00', '¥1,374.61'] | no oracle | yes | Call Foshan Home Retail Co. today for the ¥162,800.00: it saves you ¥1,374.61 and is the only free action.
worth | day34 | RCV-A reason_sentence figures | ['¥162,800.00', '2', '¥1,374.61', '¥37,200.00'] | direct figures | ['¥162,800.00', '2', '¥1,374.61', '¥37,200.00'] | no oracle | yes | The ¥162,800.00 was due 2 days ago. If it arrived today it would save you ¥1,374.61 and leave ¥37,200.00 still to cover. No early-payment discount applies to an invoice already due.
worth | day34 | RI:BUYER-1:2 outstanding_display | ¥420,000.00 | state receivable.outstanding_fen | ¥420,000.00 | ¥420,000.00 | yes | 
worth | day34 | RI:BUYER-1:2 action | offer_early_pay | rules of 5.3 on the direct figures | offer_early_pay | expected difference: oracle action is a different vocabulary (offer early pay up to 0.80%) | yes | 
worth | day34 | RI:BUYER-1:2 effect today (day 34) saving_text | ¥1,706.10 | plan().total_cost_fen: base - received | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:2 effect today (day 34) saving_display | ¥1,706.10 | same | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:2 effect today (day 34) need_left_display | ¥0.00 | plan().need_fen of the received copy | ¥0.00 | ¥0.00 | yes | 
worth | day34 | RI:BUYER-1:2 effect today (day 34) breach_days_removed | 5 | project() days below the floor, before - after | 5 | 5 | yes | 
worth | day34 | RI:BUYER-1:2 effect before_due (day 42) saving_text | ¥1,706.10 | plan().total_cost_fen: base - received | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:2 effect before_due (day 42) saving_display | ¥1,706.10 | same | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:2 effect before_due (day 42) need_left_display | ¥0.00 | plan().need_fen of the received copy | ¥0.00 | ¥0.00 | yes | 
worth | day34 | RI:BUYER-1:2 effect before_due (day 42) breach_days_removed | 5 | project() days below the floor, before - after | 5 | 5 | yes | 
worth | day34 | RI:BUYER-1:2 gross_saving_display | ¥1,706.10 | = today effect saving | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[whole] face_display | ¥420,000.00 | Option A counter face / outstanding / ceil100(plan.need_fen) | ¥420,000.00 | ¥420,000.00 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[whole] largest_rate_display | 0.40% | C1-C0 sweep + verifier APR cap | 0.40% | 0.40% | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[whole] cost_without_display (C0) | ¥3,731.12 | posted cost of the books | ¥3,731.12 | ¥3,731.12 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[whole] cost_with_display (C1 at the ceiling) | ¥3,705.02 | C0 + (C1-C0) at ceiling | ¥3,705.02 | ¥3,705.02 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[whole] beats_by_display (C0-C1 at ceiling) | ¥26.10 | -(C1-C0) at ceiling | ¥26.10 | ¥26.10 | yes | oracle read from its sweep at 40bp
worth | day34 | RI:BUYER-1:2 ceiling[whole] mid_rate_display (ceiling/2 on the 5bp grid) | 0.20% | spike rule max(5, best//2//5*5) | 0.20% | no oracle (the spike has no mid rate; oracle sweep used below) | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[whole] mid_saving_display | ¥866.10 | -(C1-C0) at the mid rate | ¥866.10 | ¥866.10 | yes | oracle read from its sweep at 20bp
worth | day34 | RI:BUYER-1:2 ceiling[whole] next_rate_display | 0.45% | largest + 5bp within the cap | 0.45% | 0.45% | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[whole] next_rate_dearer_by_display | ¥183.90 | C1-C0 at largest+5bp | ¥183.90 | ¥183.90 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[need] face_display | ¥200,000.00 | Option A counter face / outstanding / ceil100(plan.need_fen) | ¥200,000.00 | ¥200,000.00 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[need] largest_rate_display | 0.45% | C1-C0 sweep + verifier APR cap | 0.45% | expected difference: the oracle has no APR cap; the verifier refuses 50bp on this tenor (MAX_APR_EXCEEDED), so the ceiling is 45bp | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[need] cost_without_display (C0) | ¥3,731.12 | posted cost of the books | ¥3,731.12 | ¥3,731.12 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[need] cost_with_display (C1 at the ceiling) | ¥2,942.84 | C0 + (C1-C0) at ceiling | ¥2,942.84 | ¥2,942.84 | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[need] beats_by_display (C0-C1 at ceiling) | ¥788.28 | -(C1-C0) at ceiling | ¥788.28 | ¥788.28 | yes | oracle read from its sweep at 45bp
worth | day34 | RI:BUYER-1:2 ceiling[need] mid_rate_display (ceiling/2 on the 5bp grid) | 0.20% | spike rule max(5, best//2//5*5) | 0.20% | no oracle (the spike has no mid rate; oracle sweep used below) | yes | 
worth | day34 | RI:BUYER-1:2 ceiling[need] mid_saving_display | ¥1,288.28 | -(C1-C0) at the mid rate | ¥1,288.28 | ¥1,288.28 | yes | oracle read from its sweep at 20bp
worth | day34 | RI:BUYER-1:2 ceiling[need] next_rate_display | none | largest + 5bp within the cap | none | expected difference: the oracle has no APR cap; the verifier refuses 50bp on this tenor (MAX_APR_EXCEEDED), so the ceiling is 45bp | yes | 
worth | day34 | RI:BUYER-1:2 quoted face | need | counter face if it has a rate, else the plan's need | need | no oracle | yes | 
worth | day34 | RI:BUYER-1:2 mid_rate_display (row) | 0.20% | quoted ceiling mid rate | 0.20% | no oracle | yes | 
worth | day34 | RI:BUYER-1:2 mid_saving_display (row) | ¥1,288.28 | quoted ceiling mid saving | ¥1,288.28 | no oracle | yes | 
worth | day34 | RI:BUYER-1:2 net_saving_display | ¥788.28 | call now: gross; else beats_by of the quoted ceiling | ¥788.28 | expected difference: APR cap of the mandate (oracle has none): ceiling 45bp vs oracle 80bp | yes | oracle net_value_at_ceiling ¥77.58
worth | day34 | RI:BUYER-1:2 net_saving_text | ¥788.28 | same | ¥788.28 | expected difference: APR cap of the mandate (oracle has none): ceiling 45bp vs oracle 80bp | yes | 
worth | day34 | RI:BUYER-1:2 worth_text | Saves ¥788.28 at the 0.45% limit; ¥1,288.28 if they take 0.20% | built from the direct figures | Saves ¥788.28 at the 0.45% limit; ¥1,288.28 if they take 0.20% | expected difference: APR cap of the mandate (oracle has none): ceiling 45bp vs oracle 80bp | yes | 
worth | day34 | RI:BUYER-1:2 action_sentence figures (incl. the due distance in days) | ['¥420,000.00', '13', '0.45%', '¥200,000.00'] | direct figures; state due_day - as_of_day | ['¥420,000.00', '13', '0.45%', '¥200,000.00'] | no oracle | yes | On the ¥420,000.00 due in 13 days, offer early payment at up to 0.45% on ¥200,000.00, or fund it instead.
worth | day34 | RI:BUYER-1:2 reason_sentence figures | ['0.45%', '¥788.28', '0.20%', '¥1,288.28', '¥1,706.10'] | direct figures | ['0.45%', '¥788.28', '0.20%', '¥1,288.28', '¥1,706.10'] | no oracle | yes | At the 0.45% limit it saves you ¥788.28 against the cheapest funding plan; at 0.20% ¥1,288.28. If it arrived today it would save you ¥1,706.10 and clear the shortfall.
worth | day34 | RI:BUYER-1:32 outstanding_display | ¥420,000.00 | state receivable.outstanding_fen | ¥420,000.00 | ¥420,000.00 | yes | 
worth | day34 | RI:BUYER-1:32 action | wait | rules of 5.3 on the direct figures | wait | expected difference: oracle action is a different vocabulary (offer early pay up to 1.20%) | yes | 
worth | day34 | RI:BUYER-1:32 effect today (day 34) saving_text | ¥1,706.10 | plan().total_cost_fen: base - received | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:32 effect today (day 34) saving_display | ¥1,706.10 | same | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:32 effect today (day 34) need_left_display | ¥0.00 | plan().need_fen of the received copy | ¥0.00 | ¥0.00 | yes | 
worth | day34 | RI:BUYER-1:32 effect today (day 34) breach_days_removed | 5 | project() days below the floor, before - after | 5 | 5 | yes | 
worth | day34 | RI:BUYER-1:32 effect before_due (day 72) saving_text | no saving | plan().total_cost_fen: base - received | no saving | no saving | yes | 
worth | day34 | RI:BUYER-1:32 effect before_due (day 72) saving_display | no saving | same | no saving | no saving | yes | 
worth | day34 | RI:BUYER-1:32 effect before_due (day 72) need_left_display | ¥200,000.00 | plan().need_fen of the received copy | ¥200,000.00 | ¥200,000.00 | yes | 
worth | day34 | RI:BUYER-1:32 effect before_due (day 72) breach_days_removed | 0 | project() days below the floor, before - after | 0 | 0 | yes | 
worth | day34 | RI:BUYER-1:32 effect first_breach (day 42) saving_text | ¥1,706.10 | plan().total_cost_fen: base - received | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:32 effect first_breach (day 42) saving_display | ¥1,706.10 | same | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:32 effect first_breach (day 42) need_left_display | ¥0.00 | plan().need_fen of the received copy | ¥0.00 | ¥0.00 | yes | 
worth | day34 | RI:BUYER-1:32 effect first_breach (day 42) breach_days_removed | 5 | project() days below the floor, before - after | 5 | 5 | yes | 
worth | day34 | RI:BUYER-1:32 gross_saving_display | ¥1,706.10 | = today effect saving | ¥1,706.10 | ¥1,706.10 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[whole] face_display | ¥420,000.00 | Option A counter face / outstanding / ceil100(plan.need_fen) | ¥420,000.00 | ¥420,000.00 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[whole] largest_rate_display | 0.65% | C1-C0 sweep + verifier APR cap | 0.65% | 0.65% | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[whole] cost_without_display (C0) | ¥3,731.12 | posted cost of the books | ¥3,731.12 | ¥3,731.12 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[whole] cost_with_display (C1 at the ceiling) | ¥3,676.76 | C0 + (C1-C0) at ceiling | ¥3,676.76 | ¥3,676.76 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[whole] beats_by_display (C0-C1 at ceiling) | ¥54.36 | -(C1-C0) at ceiling | ¥54.36 | ¥54.36 | yes | oracle read from its sweep at 65bp
worth | day34 | RI:BUYER-1:32 ceiling[whole] mid_rate_display (ceiling/2 on the 5bp grid) | 0.30% | spike rule max(5, best//2//5*5) | 0.30% | no oracle (the spike has no mid rate; oracle sweep used below) | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[whole] mid_saving_display | ¥1,524.36 | -(C1-C0) at the mid rate | ¥1,524.36 | ¥1,524.36 | yes | oracle read from its sweep at 30bp
worth | day34 | RI:BUYER-1:32 ceiling[whole] next_rate_display | 0.70% | largest + 5bp within the cap | 0.70% | 0.70% | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[whole] next_rate_dearer_by_display | ¥155.64 | C1-C0 at largest+5bp | ¥155.64 | ¥155.64 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[need] face_display | ¥200,000.00 | Option A counter face / outstanding / ceil100(plan.need_fen) | ¥200,000.00 | ¥200,000.00 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[need] largest_rate_display | 1.20% | C1-C0 sweep + verifier APR cap | 1.20% | 1.20% | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[need] cost_without_display (C0) | ¥3,731.12 | posted cost of the books | ¥3,731.12 | ¥3,731.12 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[need] cost_with_display (C1 at the ceiling) | ¥3,657.44 | C0 + (C1-C0) at ceiling | ¥3,657.44 | ¥3,657.44 | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[need] beats_by_display (C0-C1 at ceiling) | ¥73.68 | -(C1-C0) at ceiling | ¥73.68 | ¥73.68 | yes | oracle read from its sweep at 120bp
worth | day34 | RI:BUYER-1:32 ceiling[need] mid_rate_display (ceiling/2 on the 5bp grid) | 0.60% | spike rule max(5, best//2//5*5) | 0.60% | no oracle (the spike has no mid rate; oracle sweep used below) | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[need] mid_saving_display | ¥1,284.38 | -(C1-C0) at the mid rate | ¥1,284.38 | ¥1,284.38 | yes | oracle read from its sweep at 60bp
worth | day34 | RI:BUYER-1:32 ceiling[need] next_rate_display | 1.25% | largest + 5bp within the cap | 1.25% | 1.25% | yes | 
worth | day34 | RI:BUYER-1:32 ceiling[need] next_rate_dearer_by_display | ¥27.21 | C1-C0 at largest+5bp | ¥27.21 | ¥27.21 | yes | 
worth | day34 | RI:BUYER-1:32 quoted face | need | counter face if it has a rate, else the plan's need | need | no oracle | yes | 
worth | day34 | RI:BUYER-1:32 mid_rate_display (row) | 0.60% | quoted ceiling mid rate | 0.60% | no oracle | yes | 
worth | day34 | RI:BUYER-1:32 mid_saving_display (row) | ¥1,284.38 | quoted ceiling mid saving | ¥1,284.38 | no oracle | yes | 
worth | day34 | RI:BUYER-1:32 net_saving_display | ¥73.68 | call now: gross; else beats_by of the quoted ceiling | ¥73.68 | ¥73.68 | yes | oracle net_value_at_ceiling ¥73.68
worth | day34 | RI:BUYER-1:32 net_saving_text | ¥73.68 | same | ¥73.68 | ¥73.68 | yes | 
worth | day34 | RI:BUYER-1:32 worth_text | Saves nothing extra now | built from the direct figures | Saves nothing extra now | no oracle (the oracle has no such string) | yes | 
worth | day34 | RI:BUYER-1:32 action_sentence figures (incl. the due distance in days) | ['¥420,000.00', '43'] | direct figures; state due_day - as_of_day | ['¥420,000.00', '43'] | no oracle | yes | Wait: the ¥420,000.00 due in 43 days is beyond the shortfall; chasing it now saves nothing extra.
worth | day34 | RI:BUYER-1:32 reason_sentence figures | ['¥1,706.10'] | direct figures | ['¥1,706.10'] | no oracle | yes | Collected today it would save you ¥1,706.10 and clear the shortfall, but the invoices due before it already cover what you need, so chasing it adds nothing.
worth | day34 | top_action figures | ['¥162,800.00', '¥1,374.61'] | first ranked row's action sentence | ['¥162,800.00', '¥1,374.61'] | no oracle | yes | Call Foshan Home Retail Co. today for the ¥162,800.00: it saves you ¥1,374.61 and is the only free action.
envelope | day0 | primary figures | ['55', '0.30%', '0.85%', '¥257,200.00', '1.25%', '60'] | verifier.evaluate scans (terms x price, early pay, rebate) + counter re-check | ['55', '0.30%', '0.85%', '¥257,200.00', '1.25%', '60'] | no oracle for the sentence; levers below carry the oracle | yes | You can live with: up to 55-day terms if the price rises 0.30%, or early payment at up to 0.85% on ¥257,200.00; a rebate up to 1.25%; not 60 days without an early payment.
envelope | day0 | reason figures | ['60', '47', '¥5,000.00'] | RESERVE_BREACH violation day; mandate.max_aggregate_forward_concession_fen; past-due receivable outstanding and days | ['60', '47', '¥5,000.00'] | no oracle for the sentence (day-0 breach day 47 and cap in oracle: yes) | yes | 60 days without an early payment leaves a shortfall in 47 days that no fix covers; the ¥5,000.00 budget buys no terms without a price rise.
envelope | day0 | money figures | ['¥0.00', '¥3,027.77', '¥3,113.93'] | supplier_cost_fen of the verifier's own counters; status-quo verdict plan.total_cost_fen | ['¥0.00', '¥3,027.77', '¥3,113.93'] | no oracle | yes | Cost to you ¥0.00 with the price rise, or ¥3,027.77 with the early payment; without a deal your current funding plan costs ¥3,113.93.
envelope | day0 | lever keys | ['terms_alone', 'terms_budget_ignored', 'terms_with_price', 'early_pay_whole', 'early_pay_counter', 'rebate'] | — | ['terms_alone', 'terms_budget_ignored', 'terms_with_price', 'early_pay_whole', 'early_pay_counter', 'rebate'] | no oracle (labels differ; see each lever) | yes | 
envelope | day0 | lever terms_alone maximum | 45 | verifier.evaluate full scan (no bisection) | 45 | 45 | yes | 
envelope | day0 | lever terms_alone maximum_display | 45 days | scan + Option B rule price (value_concessions, smallest_step_covering) | 45 days | 45 days | yes | oracle lever string: 45 days
envelope | day0 | lever terms_alone next_step_sentence | 50 days: over your limits; its funding cannot run today | scan beyond the maximum + approved + flags | 50 days: over your limits; its funding cannot run today | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | oracle next step: REJECT / fails fwd ¥8,108.97
envelope | day0 | lever terms_alone at_maximum forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | ¥0.00 | yes | 
envelope | day0 | lever terms_alone at_maximum plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | lever terms_alone at_maximum outcome | ACCEPT | verdict.outcome | ACCEPT | ACCEPT | yes | 
envelope | day0 | lever terms_alone at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day0 | lever terms_alone next_step forward_budget_used_display | ¥8,108.97 | verdict.forward_concession_total_fen | ¥8,108.97 | ¥8,108.97 | yes | 
envelope | day0 | lever terms_alone next_step plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | lever terms_alone next_step outcome | REJECT | verdict.outcome | REJECT | REJECT | yes | 
envelope | day0 | lever terms_alone next_step reserve breach (day, cure cost) | (47, '¥1,570.36') | RESERVE_BREACH violation day, cure_cost_fen | (47, '¥1,570.36') | (47, '¥1,570.36') | yes | 
envelope | day0 | lever terms_budget_ignored maximum | 55 | verifier.evaluate full scan (no bisection) | 55 | 55 | yes | 
envelope | day0 | lever terms_budget_ignored maximum_display | 55 days | scan + Option B rule price (value_concessions, smallest_step_covering) | 55 days | 55 days | yes | oracle lever string: 55 days
envelope | day0 | lever terms_budget_ignored next_step_sentence | 60 days: over your limits | scan beyond the maximum + approved + flags | 60 days: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | oracle next step: REJECT / fails fwd ¥24,326.92
envelope | day0 | lever terms_budget_ignored at_maximum forward_budget_used_display | ¥16,217.95 | verdict.forward_concession_total_fen | ¥16,217.95 | ¥16,217.95 | yes | 
envelope | day0 | lever terms_budget_ignored at_maximum plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | lever terms_budget_ignored at_maximum outcome | REJECT | verdict.outcome | REJECT | REJECT | yes | 
envelope | day0 | lever terms_budget_ignored at_maximum reserve breach (day, cure cost) | (47, '¥1,570.36') | RESERVE_BREACH violation day, cure_cost_fen | (47, '¥1,570.36') | (47, '¥1,570.36') | yes | 
envelope | day0 | lever terms_budget_ignored next_step forward_budget_used_display | ¥24,326.92 | verdict.forward_concession_total_fen | ¥24,326.92 | ¥24,326.92 | yes | 
envelope | day0 | lever terms_budget_ignored next_step plan_cost_display | ¥3,873.58 | verdict.plan.total_cost_fen | ¥3,873.58 | no oracle (not recorded) | yes | 
envelope | day0 | lever terms_budget_ignored next_step outcome | REJECT | verdict.outcome | REJECT | REJECT | yes | 
envelope | day0 | lever terms_budget_ignored next_step reserve breach (day, cure cost) | (47, None) | RESERVE_BREACH violation day, cure_cost_fen | (47, None) | (47, None) | yes | 
envelope | day0 | lever terms_with_price maximum | 55 | verifier.evaluate full scan (no bisection) | 55 | 55 | yes | 
envelope | day0 | lever terms_with_price maximum_display | 55 days, price up 0.30% | scan + Option B rule price (value_concessions, smallest_step_covering) | 55 days, price up 0.30% | 55 days, price up 0.30% | yes | oracle lever string: 55 days at +0.25%
envelope | day0 | lever terms_with_price rule_price_display | 0.30% | marginal_cost + value_concessions + smallest_step_covering | 0.30% | 0.30% | yes | 
envelope | day0 | lever terms_with_price next_step_sentence | 60 days, price up 1.00%: over your limits | scan beyond the maximum + approved + flags | 60 days, price up 1.00%: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | oracle next step: REJECT / fails fwd ¥0.00
envelope | day0 | lever terms_with_price at_maximum forward_budget_used_display | ¥2,567.95 | verdict.forward_concession_total_fen | ¥2,567.95 | ¥2,567.95 | yes | 
envelope | day0 | lever terms_with_price at_maximum plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | lever terms_with_price at_maximum outcome | NEEDS_OWNER_APPROVAL | verdict.outcome | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | yes | 
envelope | day0 | lever terms_with_price at_maximum reserve breach (day, cure cost) | (47, '¥1,570.36') | RESERVE_BREACH violation day, cure_cost_fen | (47, '¥1,570.36') | (47, '¥1,570.36') | yes | 
envelope | day0 | lever terms_with_price next_step forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | ¥0.00 | yes | 
envelope | day0 | lever terms_with_price next_step plan_cost_display | ¥3,873.58 | verdict.plan.total_cost_fen | ¥3,873.58 | no oracle (not recorded) | yes | 
envelope | day0 | lever terms_with_price next_step outcome | REJECT | verdict.outcome | REJECT | REJECT | yes | 
envelope | day0 | lever terms_with_price next_step reserve breach (day, cure cost) | (47, None) | RESERVE_BREACH violation day, cure_cost_fen | (47, None) | (47, None) | yes | 
envelope | day0 | lever early_pay_whole maximum | 70 | verifier.evaluate full scan (no bisection) | 70 | 70 | yes | 
envelope | day0 | lever early_pay_whole maximum_display | 0.70% on ¥420,000.00 | scan + Option B rule price (value_concessions, smallest_step_covering) | 0.70% on ¥420,000.00 | 0.70% on ¥420,000.00 | yes | oracle lever string: 0.70%
envelope | day0 | lever early_pay_whole face_display | ¥420,000.00 | context receivable / Option A counter face | ¥420,000.00 | ¥420,000.00 | yes | 
envelope | day0 | lever early_pay_whole next_step_sentence | 0.75% on ¥420,000.00: over your limits | scan beyond the maximum + approved + flags | 0.75% on ¥420,000.00: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | oracle next step: COUNTER / fails fwd ¥0.00
envelope | day0 | lever early_pay_whole at_maximum forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | ¥0.00 | yes | 
envelope | day0 | lever early_pay_whole at_maximum plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day0 | lever early_pay_whole at_maximum outcome | ACCEPT | verdict.outcome | ACCEPT | ACCEPT | yes | 
envelope | day0 | lever early_pay_whole at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day0 | lever early_pay_whole next_step forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | ¥0.00 | yes | 
envelope | day0 | lever early_pay_whole next_step plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day0 | lever early_pay_whole next_step outcome | COUNTER | verdict.outcome | COUNTER | COUNTER | yes | 
envelope | day0 | lever early_pay_whole next_step reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day0 | lever early_pay_counter maximum | 85 | verifier.evaluate full scan (no bisection) | 85 | 85 | yes | 
envelope | day0 | lever early_pay_counter maximum_display | 0.85% on ¥257,200.00 | scan + Option B rule price (value_concessions, smallest_step_covering) | 0.85% on ¥257,200.00 | 0.85% on ¥257,200.00 | yes | oracle lever string: 0.85%
envelope | day0 | lever early_pay_counter face_display | ¥257,200.00 | context receivable / Option A counter face | ¥257,200.00 | ¥257,200.00 | yes | 
envelope | day0 | lever early_pay_counter next_step_sentence | 0.90% on ¥257,200.00: over your limits | scan beyond the maximum + approved + flags | 0.90% on ¥257,200.00: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | oracle next step: COUNTER / fails fwd ¥0.00
envelope | day0 | lever early_pay_counter at_maximum forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | ¥0.00 | yes | 
envelope | day0 | lever early_pay_counter at_maximum plan_cost_display | ¥841.57 | verdict.plan.total_cost_fen | ¥841.57 | no oracle (not recorded) | yes | 
envelope | day0 | lever early_pay_counter at_maximum outcome | ACCEPT | verdict.outcome | ACCEPT | ACCEPT | yes | 
envelope | day0 | lever early_pay_counter at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day0 | lever early_pay_counter next_step forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | ¥0.00 | yes | 
envelope | day0 | lever early_pay_counter next_step plan_cost_display | ¥853.64 | verdict.plan.total_cost_fen | ¥853.64 | no oracle (not recorded) | yes | 
envelope | day0 | lever early_pay_counter next_step outcome | COUNTER | verdict.outcome | COUNTER | COUNTER | yes | 
envelope | day0 | lever early_pay_counter next_step reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day0 | lever rebate maximum | 125 | verifier.evaluate full scan (no bisection) | 125 | 125 | yes | 
envelope | day0 | lever rebate maximum_display | 1.25% | scan + Option B rule price (value_concessions, smallest_step_covering) | 1.25% | 1.25% | yes | oracle lever string: 1.25%
envelope | day0 | lever rebate next_step_sentence | 1.30%: over your limits | scan beyond the maximum + approved + flags | 1.30%: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | oracle next step: REJECT / fails fwd ¥5,200.00
envelope | day0 | lever rebate at_maximum forward_budget_used_display | ¥5,000.00 | verdict.forward_concession_total_fen | ¥5,000.00 | ¥5,000.00 | yes | 
envelope | day0 | lever rebate at_maximum plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | lever rebate at_maximum outcome | NEEDS_OWNER_APPROVAL | verdict.outcome | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | yes | 
envelope | day0 | lever rebate at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day0 | lever rebate next_step forward_budget_used_display | ¥5,200.00 | verdict.forward_concession_total_fen | ¥5,200.00 | ¥5,200.00 | yes | 
envelope | day0 | lever rebate next_step plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | lever rebate next_step outcome | REJECT | verdict.outcome | REJECT | REJECT | yes | 
envelope | day0 | lever rebate next_step reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day0 | zone 30d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | 0.00% | yes | 
envelope | day0 | zone 30d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | None | yes | 
envelope | day0 | zone 30d cost per invoice | None | value_concessions per_invoice_fen | None | None | yes | 
envelope | day0 | zone 30d at-that-price forward_budget_used / outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | yes | 
envelope | day0 | zone 30d at-that-price plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | zone 35d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | 0.00% | yes | 
envelope | day0 | zone 35d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | None | yes | 
envelope | day0 | zone 35d cost per invoice | None | value_concessions per_invoice_fen | None | None | yes | 
envelope | day0 | zone 35d at-that-price forward_budget_used / outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | yes | 
envelope | day0 | zone 35d at-that-price plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | zone 40d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | 0.00% | yes | 
envelope | day0 | zone 40d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | None | yes | 
envelope | day0 | zone 40d cost per invoice | None | value_concessions per_invoice_fen | None | None | yes | 
envelope | day0 | zone 40d at-that-price forward_budget_used / outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | yes | 
envelope | day0 | zone 40d at-that-price plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | zone 45d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | 0.00% | yes | 
envelope | day0 | zone 45d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | None | yes | 
envelope | day0 | zone 45d cost per invoice | None | value_concessions per_invoice_fen | None | None | yes | 
envelope | day0 | zone 45d at-that-price forward_budget_used / outcome | ('¥0.00', 'ACCEPT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'ACCEPT') | ('¥0.00', 'ACCEPT') | yes | 
envelope | day0 | zone 45d at-that-price plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | zone 50d smallest price (min_price_display / lowest_price_words) | 0.10% | first price in 0..100 that the verifier passes | 0.10% | 0.10% | yes | 
envelope | day0 | zone 50d rule price | 0.15% | marginal_cost+value_concessions+smallest_step_covering | 0.15% | 0.15% | yes | 
envelope | day0 | zone 50d cost per invoice | ¥623.77 | value_concessions per_invoice_fen | ¥623.77 | ¥623.77 | yes | 
envelope | day0 | zone 50d at-that-price forward_budget_used / outcome | ('¥2,648.97', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥2,648.97', 'NEEDS_OWNER_APPROVAL') | ('¥2,648.97', 'NEEDS_OWNER_APPROVAL') | yes | 
envelope | day0 | zone 50d at-that-price plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | zone 55d smallest price (min_price_display / lowest_price_words) | 0.25% | first price in 0..100 that the verifier passes | 0.25% | 0.25% | yes | 
envelope | day0 | zone 55d rule price | 0.30% | marginal_cost+value_concessions+smallest_step_covering | 0.30% | 0.30% | yes | 
envelope | day0 | zone 55d cost per invoice | ¥1,247.53 | value_concessions per_invoice_fen | ¥1,247.53 | ¥1,247.53 | yes | 
envelope | day0 | zone 55d at-that-price forward_budget_used / outcome | ('¥2,567.95', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥2,567.95', 'NEEDS_OWNER_APPROVAL') | ('¥2,567.95', 'NEEDS_OWNER_APPROVAL') | yes | 
envelope | day0 | zone 55d at-that-price plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | zone 60d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | none works | yes | 
envelope | day0 | zone 60d rule price | 0.45% | marginal_cost+value_concessions+smallest_step_covering | 0.45% | 0.45% | yes | 
envelope | day0 | zone 60d cost per invoice | ¥1,871.30 | value_concessions per_invoice_fen | ¥1,871.30 | ¥1,871.30 | yes | 
envelope | day0 | zone 60d at-that-price forward_budget_used / outcome | ('¥0.00', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'REJECT') | ('¥0.00', 'REJECT') | yes | 
envelope | day0 | zone 60d at-that-price plan_cost_display | ¥3,873.58 | verdict.plan.total_cost_fen | ¥3,873.58 | no oracle (not recorded) | yes | 
envelope | day0 | zone 65d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | none works | yes | 
envelope | day0 | zone 65d rule price | 0.60% | marginal_cost+value_concessions+smallest_step_covering | 0.60% | 0.60% | yes | 
envelope | day0 | zone 65d cost per invoice | ¥2,495.07 | value_concessions per_invoice_fen | ¥2,495.07 | ¥2,495.07 | yes | 
envelope | day0 | zone 65d at-that-price forward_budget_used / outcome | ('¥0.00', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'REJECT') | ('¥0.00', 'REJECT') | yes | 
envelope | day0 | zone 65d at-that-price plan_cost_display | ¥3,991.93 | verdict.plan.total_cost_fen | ¥3,991.93 | no oracle (not recorded) | yes | 
envelope | day0 | zone 70d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | none works | yes | 
envelope | day0 | zone 70d rule price | 0.75% | marginal_cost+value_concessions+smallest_step_covering | 0.75% | 0.75% | yes | 
envelope | day0 | zone 70d cost per invoice | ¥3,118.84 | value_concessions per_invoice_fen | ¥3,118.84 | ¥3,118.84 | yes | 
envelope | day0 | zone 70d at-that-price forward_budget_used / outcome | ('¥0.00', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'REJECT') | ('¥0.00', 'REJECT') | yes | 
envelope | day0 | zone 70d at-that-price plan_cost_display | ¥4,110.29 | verdict.plan.total_cost_fen | ¥4,110.29 | no oracle (not recorded) | yes | 
envelope | day0 | zone 75d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | none works | yes | 
envelope | day0 | zone 75d rule price | 0.90% | marginal_cost+value_concessions+smallest_step_covering | 0.90% | 0.90% | yes | 
envelope | day0 | zone 75d cost per invoice | ¥3,742.60 | value_concessions per_invoice_fen | ¥3,742.60 | ¥3,742.60 | yes | 
envelope | day0 | zone 75d at-that-price forward_budget_used / outcome | ('¥0.00', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'REJECT') | ('¥0.00', 'REJECT') | yes | 
envelope | day0 | zone 75d at-that-price plan_cost_display | ¥4,228.64 | verdict.plan.total_cost_fen | ¥4,228.64 | no oracle (not recorded) | yes | 
envelope | day0 | zone 80d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | none works | yes | 
envelope | day0 | zone 80d rule price | 1.05% | marginal_cost+value_concessions+smallest_step_covering | 1.05% | 1.05% | yes | 
envelope | day0 | zone 80d cost per invoice | ¥4,366.37 | value_concessions per_invoice_fen | ¥4,366.37 | ¥4,366.37 | yes | 
envelope | day0 | zone 80d at-that-price forward_budget_used / outcome | ('¥2,162.81', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥2,162.81', 'REJECT') | ('¥2,162.81', 'REJECT') | yes | 
envelope | day0 | zone 80d at-that-price plan_cost_display | ¥4,347.00 | verdict.plan.total_cost_fen | ¥4,347.00 | no oracle (not recorded) | yes | 
envelope | day0 | zone 85d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | none works | yes | 
envelope | day0 | zone 85d rule price | 1.20% | marginal_cost+value_concessions+smallest_step_covering | 1.20% | 1.20% | yes | 
envelope | day0 | zone 85d cost per invoice | ¥4,990.14 | value_concessions per_invoice_fen | ¥4,990.14 | ¥4,990.14 | yes | 
envelope | day0 | zone 85d at-that-price forward_budget_used / outcome | ('¥10,271.78', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥10,271.78', 'REJECT') | ('¥10,271.78', 'REJECT') | yes | 
envelope | day0 | zone 85d at-that-price plan_cost_display | ¥4,465.36 | verdict.plan.total_cost_fen | ¥4,465.36 | no oracle (not recorded) | yes | 
envelope | day0 | zone 90d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | none works | yes | 
envelope | day0 | zone 90d rule price | 1.35% | marginal_cost+value_concessions+smallest_step_covering | 1.35% | 1.35% | yes | 
envelope | day0 | zone 90d cost per invoice | ¥5,613.90 | value_concessions per_invoice_fen | ¥5,613.90 | ¥5,613.90 | yes | 
envelope | day0 | zone 90d at-that-price forward_budget_used / outcome | ('¥18,380.75', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥18,380.75', 'REJECT') | ('¥18,380.75', 'REJECT') | yes | 
envelope | day0 | zone 90d at-that-price plan_cost_display | ¥3,689.21 | verdict.plan.total_cost_fen | ¥3,689.21 | no oracle (not recorded) | yes | 
envelope | day0 | package settings set (route vs regenerated grid) | ['45-day terms · early payment 0.70% · rebate 1.25%', '45-day terms · early payment 0.85% on ¥257,200.00', '45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%', '45-day terms · rebate 1.25%', '50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%', '50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%', '50-day terms · price up 0.10% · rebate 0.55%', '55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%', '55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%', '55-day terms · price up 0.25% · rebate 0.60%', '55-day terms · price up 0.30%'] | grid: terms in force, +5, +10 x {none, Option A, whole}; smallest price then largest rebate | ['45-day terms · early payment 0.70% · rebate 1.25%', '45-day terms · early payment 0.85% on ¥257,200.00', '45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%', '45-day terms · rebate 1.25%', '50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%', '50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%', '50-day terms · price up 0.10% · rebate 0.55%', '55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%', '55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%', '55-day terms · price up 0.25% · rebate 0.60%', '55-day terms · price up 0.30%'] | no oracle | yes | 
envelope | day0 | package [45-day terms · rebate 1.25%] forward_budget_used_display | ¥5,000.00 | verdict.forward_concession_total_fen | ¥5,000.00 | ¥5,000.00 | yes | 
envelope | day0 | package [45-day terms · rebate 1.25%] plan_cost_display | ¥3,113.93 | verdict.plan.total_cost_fen | ¥3,113.93 | no oracle (not recorded) | yes | 
envelope | day0 | package [45-day terms · rebate 1.25%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | None | yes | 
envelope | day0 | package [45-day terms · rebate 1.25%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [45-day terms · rebate 1.25%] rate/price/rebate/face displays | ('0.00%', '0.00%', '1.25%', None) | the setting itself | ('0.00%', '0.00%', '1.25%', None) | no oracle (the setting itself) | yes | 
envelope | day0 | package [45-day terms · rebate 1.25%] counter_match | True | settings among the verifier's counters to the asks | True | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%] forward_budget_used_display | ¥5,000.00 | verdict.forward_concession_total_fen | ¥5,000.00 | ¥5,000.00 | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%] plan_cost_display | ¥841.57 | verdict.plan.total_cost_fen | ¥841.57 | no oracle (not recorded) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | None | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%] rate/price/rebate/face displays | ('0.00%', '0.85%', '1.25%', '¥257,200.00') | the setting itself | ('0.00%', '0.85%', '1.25%', '¥257,200.00') | no oracle (the setting itself) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00 · rebate 1.25%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [45-day terms · early payment 0.70% · rebate 1.25%] forward_budget_used_display | ¥5,000.00 | verdict.forward_concession_total_fen | ¥5,000.00 | ¥5,000.00 | yes | 
envelope | day0 | package [45-day terms · early payment 0.70% · rebate 1.25%] plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day0 | package [45-day terms · early payment 0.70% · rebate 1.25%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | None | yes | 
envelope | day0 | package [45-day terms · early payment 0.70% · rebate 1.25%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [45-day terms · early payment 0.70% · rebate 1.25%] rate/price/rebate/face displays | ('0.00%', '0.70%', '1.25%', None) | the setting itself | ('0.00%', '0.70%', '1.25%', None) | no oracle (the setting itself) | yes | 
envelope | day0 | package [45-day terms · early payment 0.70% · rebate 1.25%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [50-day terms · price up 0.10% · rebate 0.55%] forward_budget_used_display | ¥4,848.97 | verdict.forward_concession_total_fen | ¥4,848.97 | ¥4,848.97 | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · rebate 0.55%] plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · rebate 0.55%] reserve breach day / cure cost | (47, '¥1,570.36') | RESERVE_BREACH violation | (47, '¥1,570.36') | (47, '¥1,570.36') | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · rebate 0.55%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · rebate 0.55%] rate/price/rebate/face displays | ('0.10%', '0.00%', '0.55%', None) | the setting itself | ('0.10%', '0.00%', '0.55%', None) | no oracle (the setting itself) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · rebate 0.55%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%] forward_budget_used_display | ¥4,848.97 | verdict.forward_concession_total_fen | ¥4,848.97 | ¥4,848.97 | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%] plan_cost_display | ¥2,673.04 | verdict.plan.total_cost_fen | ¥2,673.04 | no oracle (not recorded) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%] reserve breach day / cure cost | (47, '¥2,673.04') | RESERVE_BREACH violation | (47, '¥2,673.04') | (47, '¥2,673.04') | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%] rate/price/rebate/face displays | ('0.10%', '0.85%', '0.55%', '¥257,200.00') | the setting itself | ('0.10%', '0.85%', '0.55%', '¥257,200.00') | no oracle (the setting itself) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.85% on ¥257,200.00 · rebate 0.55%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%] forward_budget_used_display | ¥4,848.97 | verdict.forward_concession_total_fen | ¥4,848.97 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%] plan_cost_display | ¥1,563.51 | verdict.plan.total_cost_fen | ¥1,563.51 | no oracle (not recorded) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%] reserve breach day / cure cost | (47, '¥1,563.51') | RESERVE_BREACH violation | (47, '¥1,563.51') | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%] rate/price/rebate/face displays | ('0.10%', '0.65%', '0.55%', None) | the setting itself | ('0.10%', '0.65%', '0.55%', None) | no oracle (the setting itself) | yes | 
envelope | day0 | package [50-day terms · price up 0.10% · early payment 0.65% · rebate 0.55%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [55-day terms · price up 0.25% · rebate 0.60%] forward_budget_used_display | ¥4,967.95 | verdict.forward_concession_total_fen | ¥4,967.95 | ¥4,967.95 | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · rebate 0.60%] plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · rebate 0.60%] reserve breach day / cure cost | (47, '¥1,570.36') | RESERVE_BREACH violation | (47, '¥1,570.36') | (47, '¥1,570.36') | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · rebate 0.60%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · rebate 0.60%] rate/price/rebate/face displays | ('0.25%', '0.00%', '0.60%', None) | the setting itself | ('0.25%', '0.00%', '0.60%', None) | no oracle (the setting itself) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · rebate 0.60%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%] forward_budget_used_display | ¥4,967.95 | verdict.forward_concession_total_fen | ¥4,967.95 | ¥4,967.95 | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%] plan_cost_display | ¥2,673.04 | verdict.plan.total_cost_fen | ¥2,673.04 | no oracle (not recorded) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%] reserve breach day / cure cost | (47, '¥2,673.04') | RESERVE_BREACH violation | (47, '¥2,673.04') | (47, '¥2,673.04') | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%] rate/price/rebate/face displays | ('0.25%', '0.85%', '0.60%', '¥257,200.00') | the setting itself | ('0.25%', '0.85%', '0.60%', '¥257,200.00') | no oracle (the setting itself) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.85% on ¥257,200.00 · rebate 0.60%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%] forward_budget_used_display | ¥4,967.95 | verdict.forward_concession_total_fen | ¥4,967.95 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%] plan_cost_display | ¥1,563.51 | verdict.plan.total_cost_fen | ¥1,563.51 | no oracle (not recorded) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%] reserve breach day / cure cost | (47, '¥1,563.51') | RESERVE_BREACH violation | (47, '¥1,563.51') | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%] rate/price/rebate/face displays | ('0.25%', '0.65%', '0.60%', None) | the setting itself | ('0.25%', '0.65%', '0.60%', None) | no oracle (the setting itself) | yes | 
envelope | day0 | package [55-day terms · price up 0.25% · early payment 0.65% · rebate 0.60%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00] forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00] plan_cost_display | ¥841.57 | verdict.plan.total_cost_fen | ¥841.57 | no oracle (not recorded) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00] outcome / tier / approved | ('ACCEPT', 'TIER_1', True) | verdict + counters.infeasibility | ('ACCEPT', 'TIER_1', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00] rate/price/rebate/face displays | ('0.00%', '0.85%', '0.00%', '¥257,200.00') | the setting itself | ('0.00%', '0.85%', '0.00%', '¥257,200.00') | no oracle (the setting itself) | yes | 
envelope | day0 | package [45-day terms · early payment 0.85% on ¥257,200.00] counter_match | True | settings among the verifier's counters to the asks | True | no oracle | yes | counter (the verifier's own counter, taken verbatim); cheaper price passes []; larger rebate passes 25 values
envelope | day0 | package [55-day terms · price up 0.30%] forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | ¥0.00 | yes | 
envelope | day0 | package [55-day terms · price up 0.30%] plan_cost_display | ¥1,570.36 | verdict.plan.total_cost_fen | ¥1,570.36 | no oracle (not recorded) | yes | 
envelope | day0 | package [55-day terms · price up 0.30%] reserve breach day / cure cost | (47, '¥1,570.36') | RESERVE_BREACH violation | (47, '¥1,570.36') | (47, '¥1,570.36') | yes | 
envelope | day0 | package [55-day terms · price up 0.30%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | yes | 
envelope | day0 | package [55-day terms · price up 0.30%] rate/price/rebate/face displays | ('0.30%', '0.00%', '0.00%', None) | the setting itself | ('0.30%', '0.00%', '0.00%', None) | no oracle (the setting itself) | yes | 
envelope | day0 | package [55-day terms · price up 0.30%] counter_match | True | settings among the verifier's counters to the asks | True | no oracle | yes | counter (the verifier's own counter, taken verbatim); cheaper price passes [25]; larger rebate passes 25 values
envelope | day34 | primary figures | ['80', '0.95%', '0.40%', '¥420,000.00', '1.25%', '85'] | verifier.evaluate scans (terms x price, early pay, rebate) + counter re-check | ['80', '0.95%', '0.40%', '¥420,000.00', '1.25%', '85'] | no oracle for the sentence; levers below carry the oracle | yes | You can live with: up to 80-day terms if the price rises 0.95%, or early payment at up to 0.40% on ¥420,000.00; a rebate up to 1.25%; not 85 days.
envelope | day34 | reason figures | ['¥162,800.00', '2', '¥5,000.00'] | RESERVE_BREACH violation day; mandate.max_aggregate_forward_concession_fen; past-due receivable outstanding and days | ['¥162,800.00', '2', '¥5,000.00'] | no oracle | yes | The ¥162,800.00 still owed by Foshan Home Retail Co. is 2 days past due, so any deal with Foshan Home Retail Co. needs your approval; the ¥5,000.00 budget buys no terms without a price rise.
envelope | day34 | money figures | ['¥1,706.10'] | supplier_cost_fen of the verifier's own counters; status-quo verdict plan.total_cost_fen | ['¥1,706.10'] | no oracle | yes | Without a deal your current funding plan costs ¥1,706.10.
envelope | day34 | lever keys | ['terms_alone', 'terms_budget_ignored', 'terms_with_price', 'early_pay_whole', 'rebate'] | — | ['terms_alone', 'terms_budget_ignored', 'terms_with_price', 'early_pay_whole', 'rebate'] | no oracle (labels differ; see each lever) | yes | 
envelope | day34 | lever terms_alone maximum | 45 | verifier.evaluate full scan (no bisection) | 45 | no oracle | yes | 
envelope | day34 | lever terms_alone maximum_display | 45 days | scan + Option B rule price (value_concessions, smallest_step_covering) | 45 days | no oracle | yes | 
envelope | day34 | lever terms_alone next_step_sentence | 50 days: over your limits | scan beyond the maximum + approved + flags | 50 days: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | 
envelope | day34 | lever terms_alone at_maximum forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | no oracle | yes | 
envelope | day34 | lever terms_alone at_maximum plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | lever terms_alone at_maximum outcome | NEEDS_OWNER_APPROVAL | verdict.outcome | NEEDS_OWNER_APPROVAL | no oracle | yes | 
envelope | day34 | lever terms_alone at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever terms_alone next_step forward_budget_used_display | ¥7,485.21 | verdict.forward_concession_total_fen | ¥7,485.21 | no oracle | yes | 
envelope | day34 | lever terms_alone next_step plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | lever terms_alone next_step outcome | REJECT | verdict.outcome | REJECT | no oracle | yes | 
envelope | day34 | lever terms_alone next_step reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever terms_budget_ignored maximum | 90 | verifier.evaluate full scan (no bisection) | 90 | no oracle | yes | 
envelope | day34 | lever terms_budget_ignored maximum_display | 90 days | scan + Option B rule price (value_concessions, smallest_step_covering) | 90 days | no oracle | yes | 
envelope | day34 | lever terms_budget_ignored next_step_sentence | no further step | scan beyond the maximum + approved + flags | no further step | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | 
envelope | day34 | lever terms_budget_ignored at_maximum forward_budget_used_display | ¥67,366.85 | verdict.forward_concession_total_fen | ¥67,366.85 | no oracle | yes | 
envelope | day34 | lever terms_budget_ignored at_maximum plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | lever terms_budget_ignored at_maximum outcome | REJECT | verdict.outcome | REJECT | no oracle | yes | 
envelope | day34 | lever terms_budget_ignored at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever terms_budget_ignored next_step | None | — | None | no oracle | yes | 
envelope | day34 | lever terms_with_price maximum | 80 | verifier.evaluate full scan (no bisection) | 80 | no oracle | yes | 
envelope | day34 | lever terms_with_price maximum_display | 80 days, price up 1.05% | scan + Option B rule price (value_concessions, smallest_step_covering) | 80 days, price up 1.05% | no oracle | yes | 
envelope | day34 | lever terms_with_price rule_price_display | 1.05% | marginal_cost + value_concessions + smallest_step_covering | 1.05% | no oracle | yes | 
envelope | day34 | lever terms_with_price next_step_sentence | 85 days, price up 1.00%: over your limits | scan beyond the maximum + approved + flags | 85 days, price up 1.00%: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | 
envelope | day34 | lever terms_with_price at_maximum forward_budget_used_display | ¥4,516.44 | verdict.forward_concession_total_fen | ¥4,516.44 | no oracle | yes | 
envelope | day34 | lever terms_with_price at_maximum plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | lever terms_with_price at_maximum outcome | NEEDS_OWNER_APPROVAL | verdict.outcome | NEEDS_OWNER_APPROVAL | no oracle | yes | 
envelope | day34 | lever terms_with_price at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever terms_with_price next_step forward_budget_used_display | ¥9,481.64 | verdict.forward_concession_total_fen | ¥9,481.64 | no oracle | yes | 
envelope | day34 | lever terms_with_price next_step plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | lever terms_with_price next_step outcome | REJECT | verdict.outcome | REJECT | no oracle | yes | 
envelope | day34 | lever terms_with_price next_step reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever early_pay_whole maximum | 40 | verifier.evaluate full scan (no bisection) | 40 | no oracle | yes | 
envelope | day34 | lever early_pay_whole maximum_display | 0.40% on ¥420,000.00 | scan + Option B rule price (value_concessions, smallest_step_covering) | 0.40% on ¥420,000.00 | no oracle | yes | 
envelope | day34 | lever early_pay_whole face_display | ¥420,000.00 | context receivable / Option A counter face | ¥420,000.00 | no oracle | yes | 
envelope | day34 | lever early_pay_whole next_step_sentence | 0.45% on ¥420,000.00: over your limits | scan beyond the maximum + approved + flags | 0.45% on ¥420,000.00: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | 
envelope | day34 | lever early_pay_whole at_maximum forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | no oracle | yes | 
envelope | day34 | lever early_pay_whole at_maximum plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day34 | lever early_pay_whole at_maximum outcome | NEEDS_OWNER_APPROVAL | verdict.outcome | NEEDS_OWNER_APPROVAL | no oracle | yes | 
envelope | day34 | lever early_pay_whole at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever early_pay_whole next_step forward_budget_used_display | ¥0.00 | verdict.forward_concession_total_fen | ¥0.00 | no oracle | yes | 
envelope | day34 | lever early_pay_whole next_step plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day34 | lever early_pay_whole next_step outcome | COUNTER | verdict.outcome | COUNTER | no oracle | yes | 
envelope | day34 | lever early_pay_whole next_step reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever rebate maximum | 125 | verifier.evaluate full scan (no bisection) | 125 | no oracle | yes | 
envelope | day34 | lever rebate maximum_display | 1.25% | scan + Option B rule price (value_concessions, smallest_step_covering) | 1.25% | no oracle | yes | 
envelope | day34 | lever rebate next_step_sentence | 1.30%: over your limits | scan beyond the maximum + approved + flags | 1.30%: over your limits | no oracle for the sentence (oracle next-step outcome/budget are the rows below) | yes | 
envelope | day34 | lever rebate at_maximum forward_budget_used_display | ¥5,000.00 | verdict.forward_concession_total_fen | ¥5,000.00 | no oracle | yes | 
envelope | day34 | lever rebate at_maximum plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | lever rebate at_maximum outcome | NEEDS_OWNER_APPROVAL | verdict.outcome | NEEDS_OWNER_APPROVAL | no oracle | yes | 
envelope | day34 | lever rebate at_maximum reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | lever rebate next_step forward_budget_used_display | ¥5,200.00 | verdict.forward_concession_total_fen | ¥5,200.00 | no oracle | yes | 
envelope | day34 | lever rebate next_step plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | lever rebate next_step outcome | REJECT | verdict.outcome | REJECT | no oracle | yes | 
envelope | day34 | lever rebate next_step reserve breach (day, cure cost) | None | RESERVE_BREACH violation day, cure_cost_fen | None | None | yes | 
envelope | day34 | zone 30d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | no oracle | yes | 
envelope | day34 | zone 30d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | no oracle | yes | 
envelope | day34 | zone 30d cost per invoice | None | value_concessions per_invoice_fen | None | no oracle | yes | 
envelope | day34 | zone 30d at-that-price forward_budget_used / outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 30d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 35d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | no oracle | yes | 
envelope | day34 | zone 35d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | no oracle | yes | 
envelope | day34 | zone 35d cost per invoice | None | value_concessions per_invoice_fen | None | no oracle | yes | 
envelope | day34 | zone 35d at-that-price forward_budget_used / outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 35d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 40d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | no oracle | yes | 
envelope | day34 | zone 40d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | no oracle | yes | 
envelope | day34 | zone 40d cost per invoice | None | value_concessions per_invoice_fen | None | no oracle | yes | 
envelope | day34 | zone 40d at-that-price forward_budget_used / outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 40d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 45d smallest price (min_price_display / lowest_price_words) | 0.00% | first price in 0..100 that the verifier passes | 0.00% | no oracle | yes | 
envelope | day34 | zone 45d rule price | None | marginal_cost+value_concessions+smallest_step_covering | None | no oracle | yes | 
envelope | day34 | zone 45d cost per invoice | None | value_concessions per_invoice_fen | None | no oracle | yes | 
envelope | day34 | zone 45d at-that-price forward_budget_used / outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥0.00', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 45d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 50d smallest price (min_price_display / lowest_price_words) | 0.05% | first price in 0..100 that the verifier passes | 0.05% | no oracle | yes | 
envelope | day34 | zone 50d rule price | 0.15% | marginal_cost+value_concessions+smallest_step_covering | 0.15% | no oracle | yes | 
envelope | day34 | zone 50d cost per invoice | ¥623.77 | value_concessions per_invoice_fen | ¥623.77 | no oracle | yes | 
envelope | day34 | zone 50d at-that-price forward_budget_used / outcome | ('¥4,965.21', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥4,965.21', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 50d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 55d smallest price (min_price_display / lowest_price_words) | 0.20% | first price in 0..100 that the verifier passes | 0.20% | no oracle | yes | 
envelope | day34 | zone 55d rule price | 0.30% | marginal_cost+value_concessions+smallest_step_covering | 0.30% | no oracle | yes | 
envelope | day34 | zone 55d cost per invoice | ¥1,247.53 | value_concessions per_invoice_fen | ¥1,247.53 | no oracle | yes | 
envelope | day34 | zone 55d at-that-price forward_budget_used / outcome | ('¥4,890.41', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥4,890.41', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 55d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 60d smallest price (min_price_display / lowest_price_words) | 0.35% | first price in 0..100 that the verifier passes | 0.35% | no oracle | yes | 
envelope | day34 | zone 60d rule price | 0.45% | marginal_cost+value_concessions+smallest_step_covering | 0.45% | no oracle | yes | 
envelope | day34 | zone 60d cost per invoice | ¥1,871.30 | value_concessions per_invoice_fen | ¥1,871.30 | no oracle | yes | 
envelope | day34 | zone 60d at-that-price forward_budget_used / outcome | ('¥4,815.62', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥4,815.62', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 60d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 65d smallest price (min_price_display / lowest_price_words) | 0.50% | first price in 0..100 that the verifier passes | 0.50% | no oracle | yes | 
envelope | day34 | zone 65d rule price | 0.60% | marginal_cost+value_concessions+smallest_step_covering | 0.60% | no oracle | yes | 
envelope | day34 | zone 65d cost per invoice | ¥2,495.07 | value_concessions per_invoice_fen | ¥2,495.07 | no oracle | yes | 
envelope | day34 | zone 65d at-that-price forward_budget_used / outcome | ('¥4,740.82', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥4,740.82', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 65d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 70d smallest price (min_price_display / lowest_price_words) | 0.65% | first price in 0..100 that the verifier passes | 0.65% | no oracle | yes | 
envelope | day34 | zone 70d rule price | 0.75% | marginal_cost+value_concessions+smallest_step_covering | 0.75% | no oracle | yes | 
envelope | day34 | zone 70d cost per invoice | ¥3,118.84 | value_concessions per_invoice_fen | ¥3,118.84 | no oracle | yes | 
envelope | day34 | zone 70d at-that-price forward_budget_used / outcome | ('¥4,666.03', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥4,666.03', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 70d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 75d smallest price (min_price_display / lowest_price_words) | 0.80% | first price in 0..100 that the verifier passes | 0.80% | no oracle | yes | 
envelope | day34 | zone 75d rule price | 0.90% | marginal_cost+value_concessions+smallest_step_covering | 0.90% | no oracle | yes | 
envelope | day34 | zone 75d cost per invoice | ¥3,742.60 | value_concessions per_invoice_fen | ¥3,742.60 | no oracle | yes | 
envelope | day34 | zone 75d at-that-price forward_budget_used / outcome | ('¥4,591.23', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥4,591.23', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 75d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 80d smallest price (min_price_display / lowest_price_words) | 0.95% | first price in 0..100 that the verifier passes | 0.95% | no oracle | yes | 
envelope | day34 | zone 80d rule price | 1.05% | marginal_cost+value_concessions+smallest_step_covering | 1.05% | no oracle | yes | 
envelope | day34 | zone 80d cost per invoice | ¥4,366.37 | value_concessions per_invoice_fen | ¥4,366.37 | no oracle | yes | 
envelope | day34 | zone 80d at-that-price forward_budget_used / outcome | ('¥4,516.44', 'NEEDS_OWNER_APPROVAL') | verdict.forward_concession_total_fen, verdict.outcome | ('¥4,516.44', 'NEEDS_OWNER_APPROVAL') | no oracle | yes | 
envelope | day34 | zone 80d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 85d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | no oracle | yes | 
envelope | day34 | zone 85d rule price | 1.20% | marginal_cost+value_concessions+smallest_step_covering | 1.20% | no oracle | yes | 
envelope | day34 | zone 85d cost per invoice | ¥4,990.14 | value_concessions per_invoice_fen | ¥4,990.14 | no oracle | yes | 
envelope | day34 | zone 85d at-that-price forward_budget_used / outcome | ('¥9,481.64', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥9,481.64', 'REJECT') | no oracle | yes | 
envelope | day34 | zone 85d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | zone 90d smallest price (min_price_display / lowest_price_words) | none works | first price in 0..100 that the verifier passes | none works | no oracle | yes | 
envelope | day34 | zone 90d rule price | 1.35% | marginal_cost+value_concessions+smallest_step_covering | 1.35% | no oracle | yes | 
envelope | day34 | zone 90d cost per invoice | ¥5,613.90 | value_concessions per_invoice_fen | ¥5,613.90 | no oracle | yes | 
envelope | day34 | zone 90d at-that-price forward_budget_used / outcome | ('¥16,966.85', 'REJECT') | verdict.forward_concession_total_fen, verdict.outcome | ('¥16,966.85', 'REJECT') | no oracle | yes | 
envelope | day34 | zone 90d at-that-price plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | package settings set (route vs regenerated grid) | ['45-day terms · early payment 0.40% · rebate 1.25%', '45-day terms · rebate 1.25%', '50-day terms · price up 0.05%', '50-day terms · price up 0.05% · early payment 0.40%', '55-day terms · price up 0.20%', '55-day terms · price up 0.20% · early payment 0.40%'] | grid: terms in force, +5, +10 x {none, Option A, whole}; smallest price then largest rebate | ['45-day terms · early payment 0.40% · rebate 1.25%', '45-day terms · rebate 1.25%', '50-day terms · price up 0.05%', '50-day terms · price up 0.05% · early payment 0.40%', '55-day terms · price up 0.20%', '55-day terms · price up 0.20% · early payment 0.40%'] | no oracle | yes | 
envelope | day34 | package [45-day terms · rebate 1.25%] forward_budget_used_display | ¥5,000.00 | verdict.forward_concession_total_fen | ¥5,000.00 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [45-day terms · rebate 1.25%] plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | package [45-day terms · rebate 1.25%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [45-day terms · rebate 1.25%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [45-day terms · rebate 1.25%] rate/price/rebate/face displays | ('0.00%', '0.00%', '1.25%', None) | the setting itself | ('0.00%', '0.00%', '1.25%', None) | no oracle (the setting itself) | yes | 
envelope | day34 | package [45-day terms · rebate 1.25%] counter_match | True | settings among the verifier's counters to the asks | True | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day34 | package [45-day terms · early payment 0.40% · rebate 1.25%] forward_budget_used_display | ¥5,000.00 | verdict.forward_concession_total_fen | ¥5,000.00 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [45-day terms · early payment 0.40% · rebate 1.25%] plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day34 | package [45-day terms · early payment 0.40% · rebate 1.25%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [45-day terms · early payment 0.40% · rebate 1.25%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [45-day terms · early payment 0.40% · rebate 1.25%] rate/price/rebate/face displays | ('0.00%', '0.40%', '1.25%', None) | the setting itself | ('0.00%', '0.40%', '1.25%', None) | no oracle (the setting itself) | yes | 
envelope | day34 | package [45-day terms · early payment 0.40% · rebate 1.25%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day34 | package [50-day terms · price up 0.05%] forward_budget_used_display | ¥4,965.21 | verdict.forward_concession_total_fen | ¥4,965.21 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [50-day terms · price up 0.05%] plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | package [50-day terms · price up 0.05%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [50-day terms · price up 0.05%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [50-day terms · price up 0.05%] rate/price/rebate/face displays | ('0.05%', '0.00%', '0.00%', None) | the setting itself | ('0.05%', '0.00%', '0.00%', None) | no oracle (the setting itself) | yes | 
envelope | day34 | package [50-day terms · price up 0.05%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day34 | package [50-day terms · price up 0.05% · early payment 0.40%] forward_budget_used_display | ¥4,965.21 | verdict.forward_concession_total_fen | ¥4,965.21 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [50-day terms · price up 0.05% · early payment 0.40%] plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day34 | package [50-day terms · price up 0.05% · early payment 0.40%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [50-day terms · price up 0.05% · early payment 0.40%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [50-day terms · price up 0.05% · early payment 0.40%] rate/price/rebate/face displays | ('0.05%', '0.40%', '0.00%', None) | the setting itself | ('0.05%', '0.40%', '0.00%', None) | no oracle (the setting itself) | yes | 
envelope | day34 | package [50-day terms · price up 0.05% · early payment 0.40%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day34 | package [55-day terms · price up 0.20%] forward_budget_used_display | ¥4,890.41 | verdict.forward_concession_total_fen | ¥4,890.41 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [55-day terms · price up 0.20%] plan_cost_display | ¥1,706.10 | verdict.plan.total_cost_fen | ¥1,706.10 | no oracle (not recorded) | yes | 
envelope | day34 | package [55-day terms · price up 0.20%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [55-day terms · price up 0.20%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [55-day terms · price up 0.20%] rate/price/rebate/face displays | ('0.20%', '0.00%', '0.00%', None) | the setting itself | ('0.20%', '0.00%', '0.00%', None) | no oracle (the setting itself) | yes | 
envelope | day34 | package [55-day terms · price up 0.20%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
envelope | day34 | package [55-day terms · price up 0.20% · early payment 0.40%] forward_budget_used_display | ¥4,890.41 | verdict.forward_concession_total_fen | ¥4,890.41 | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [55-day terms · price up 0.20% · early payment 0.40%] plan_cost_display | ¥0.00 | verdict.plan.total_cost_fen | ¥0.00 | no oracle (not recorded) | yes | 
envelope | day34 | package [55-day terms · price up 0.20% · early payment 0.40%] reserve breach day / cure cost | None | RESERVE_BREACH violation | None | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [55-day terms · price up 0.20% · early payment 0.40%] outcome / tier / approved | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | verdict + counters.infeasibility | ('NEEDS_OWNER_APPROVAL', 'TIER_2', True) | no oracle (this setting is not in the oracle's packages) | yes | 
envelope | day34 | package [55-day terms · price up 0.20% · early payment 0.40%] rate/price/rebate/face displays | ('0.20%', '0.40%', '0.00%', None) | the setting itself | ('0.20%', '0.40%', '0.00%', None) | no oracle (the setting itself) | yes | 
envelope | day34 | package [55-day terms · price up 0.20% · early payment 0.40%] counter_match | False | settings among the verifier's counters to the asks | False | no oracle | yes | grid cell; cheaper price passes []; larger rebate passes 0 values
```
