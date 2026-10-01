# TermsLedger v2: evaluation report

Run 2026-10-01T00:38:12Z on `agent/final-refresh` @ `7aa9f10`, LLM_MODE=`cache` (offline: fixture cache, then the rules grammar), 248 s. Reproduce: `uv run --project services/api python scripts/evaluate.py`.

## Summary

| Metric | Result | Target |  |
| --- | --- | --- | --- |
| Compiler material error rate (held-out, booked verdicts) | 0/36 (0.0%) | ≤ 5% | PASS |
| E2 silent material errors (incl. booked on must-abstain) | 0 | 0 | PASS |
| Abstention precision (NO_VERDICT when it should) | 14/14 (100%) | informational | info |
| Abstention recall (must-abstain items caught) | 14/14 (100%) | informational | info |
| Wording invariance: same economics → same verdict and terms | 11/11 | informational | info |
| Near-miss pairs → different verdicts | 5/7 | informational | info |
| Verdict agreement with labels (compiler) | 49/50 (98%) | informational | info |
| Verdict agreement with labels (form baseline: labels as input) | 49/50 (98%); gap +0% | informational | info |
| E2 engine ≠ static cap (form inputs) | 18/33 | ≥ 35% (7/20) | PASS |
| Financial exactness (golden values, to the fen) | 55/55 (100.0%) | 100% | PASS |
| E10 covenant + capex golden values | 25/25 | 100% | PASS |
| Router optimality (within ¥1 of brute force) | 26/26 (100%) | ≥ 95% | PASS |
| E9 router cheaper than 'line first' baseline (or baseline infeasible) | 13/26 scenarios with a gap | ≥ 5/20 | PASS |
| Total saving vs 'line first' (where both admissible) | ¥4,136.44 over 22 scenarios (median ¥40.29) | informational | info |
| E9 committed plans relying on an uncommitted facility | 0 | 0 | PASS |
| Router latency p50 / p95 | 39 / 128 ms | informational | info |
| Slowest verifier.evaluate on these states (plans=all) | 0.2 s (reserve_unsafe_1fen) | informational | info |
| Covenant/mandate boundaries (exact, ±1 fen/bp/day) | 20/20 | 100% | PASS |
| DSCR/leverage breaches reported with their month | 2/2 | 100% | PASS |
| Injection success rate | 0.0% of 40 | 0% | PASS |
| Exfiltration success rate | 0.0% of 21 | 0% | PASS |
| Escalation success rate | 0.0% of 20 | 0% | PASS |
| Replay success rate | 0.0% of 21 | 0% | PASS |
| Unauthorised operation count (all attacks) | 0 | 0 | PASS |
| Attacks with any harm (money, facility, disclosure, integrity) | 0/122 | 0 | PASS |
| Attacks detected (SecurityEvent or refusal code) | 97.5% (security-event rate 70.5%) | informational | info |
| Intent accuracy (held-out owner utterances) | 42/47 (89%) | informational | info |
| Slot accuracy (labelled key slots) | 30/30 (100%) | informational | info |
| Clarification rate on deliberately ambiguous requests | 6/6 (over-clarified 1/41 clear requests) | informational | info |
| Task completion rate (scripted /nl tasks) | 37/37 (100%) | ≥ 95% | PASS |
| /nl turn latency p50 / p95 | 5 / 114 ms (69 turns) | informational | info |
| E2E latency, golden Scene 1 (compile → evaluate → negotiate → execute) | p50 202 ms, p95 215 ms over 5 cold runs | completes | PASS |
| E5 hard-line buyer → NO_DEAL, gap still funded | 7/7 checks (3 rounds; ops DRAW_FACILITY, SUBMIT_INVOICE_FOR_FINANCING) | all | PASS |

### Validation gate (spec v2 §14)

| Gate | Question | Criterion | Evidence |  |
| --- | --- | --- | --- | --- |
| E2 | Compiler beats a form; engine differs from a cap | 0 silent material errors; engine ≠ cap on ≥ 7/20 (handling time not measured) | E2 silent material errors (incl. booked on must-abstain): 0; E2 engine ≠ static cap (form inputs): 18/33 | PASS |
| E3 | Engine correctness | every golden case exact | Financial exactness (golden values, to the fen): 55/55 (100.0%) | PASS |
| E4 | Language cannot create an unauthorised promise | 0 booked; every refusal has a reason | Injection success rate: 0.0% of 40; Unauthorised operation count (all attacks): 0 (attack catalogue only; see EV-01/EV-02: benign held-out wording executes ACCEPT_OFFER on booked terms that differ from the buyer's text) | PASS |
| E5 | Honest no-deal | bounded rounds; explicit NO DEAL; gap still funded | E5 hard-line buyer → NO_DEAL, gap still funded: 7/7 checks | PASS |
| E7 | Harness compatibility | /nl → plan → verdict → operation log; injected requests refused | Task completion rate (scripted /nl tasks): 37/37 (100%); Attacks with any harm (money, facility, disclosure, integrity): 0/122 | PASS |
| E9 | The router matters and stays honest | router ≠ baseline with lower cost on ≥ 5/20; 0 plans on uncommitted facilities | E9 router cheaper than 'line first' baseline (or baseline infeasible): 13/26 scenarios with a gap; E9 committed plans relying on an uncommitted facility: 0 (the separate ≥ 95% optimality target is in the summary) | PASS |
| E10 | Covenant and capex engine | all exact; every breach reported with its month | E10 covenant + capex golden values: 25/25; Covenant/mandate boundaries (exact, ±1 fen/bp/day): 20/20; DSCR/leverage breaches reported with their month: 2/2 | PASS |

## Findings

Weaknesses found by this run, with severity and a suggested owner module (`services/api/evals/findings.yaml`).

| Id | Severity | Owner | Finding |
| --- | --- | --- | --- |
| EV-01 | high | `services/api/app/compiler (rules grammar) + services/api/app/nl (counterparty acceptance reply)` | “X% off the invoice, we pay today” compiles to a next-quarter rebate; a buyer message then executes ACCEPT_OFFER on terms the buyer never offered |
| EV-02 | high | `services/api/app/compiler (abstention) + services/api/app/verifier/bind.py (rebate base)` | Unbounded or unscoped rebates are booked as a one-off next-quarter rebate instead of abstaining (INVARIANT 10) |
| EV-03 | high | `services/api/app/compiler (rules grammar)` | Compiler material error rate 22% on held-out offers (target ≤ 5%); 11 silent material errors (E2 needs 0) |
| EV-04 | medium | `services/api/app/compiler (rules grammar, zh and number words)` | 13 of 36 clear held-out offers abstain (safe, but the owner must re-key them) |
| EV-05 | medium | `services/api/app/compiler/grounding.py` | Conflicting message/attachment pairs are reported as UNRESOLVED_SCOPE, not CONFLICTING_SOURCES |
| EV-06 | medium | `services/api/app/funding/search.py (Search._slots, recovery_days)` | Router optimality 85% (22/26) against brute force: it only repays the line on baseline recovery days |
| EV-07 | medium | `services/api/app/verifier/evaluate.py (expected plan) + services/api/app/funding/search.py (EXPECTED basis)` | POST /offers/{id}/evaluate can take 14 s: the display-only EXPECTED plan search blows up near the floor |
| EV-08 | medium | `services/api/app/nl/lexicon.py (FIXTURE_RE, APPROVAL_ID_RE)` | Ids glued to Chinese text are not recognised: “批准APR-000003。” approves nothing specific |
| EV-09 | medium | `services/api/app/nl/lexicon.py + services/api/app/nl/intent_cache` | Offline intent accuracy 57%: most misses fall back to OUT_OF_SCOPE; 4 of 6 vague requests get no clarifying question |
| EV-10 | medium | `product / evaluation design (spec §14 E2)` | E2 engine ≠ cap on only 27% of held-out offers (criterion ≥ 35%, i.e. 7/20) |
| EV-11 | low | `services/api/app/funding/search.py` | The router proposes a 1-fen early payment (cost ¥0.00) to cure a 1-fen shortfall |
| EV-12 | low | `services/api/app/covenants (display) + services/api/app/verifier (summary)` | A one-fen DSCR breach reads “1.25x < 1.25x”, repeated eight times in the summary |

### EV-01: “X% off the invoice, we pay today” compiles to a next-quarter rebate; a buyer message then executes ACCEPT_OFFER on terms the buyer never offered

Severity **high**, owner `services/api/app/compiler (rules grammar) + services/api/app/nl (counterparty acceptance reply)`, suite `offers`.

"We'll pay the ¥420,000 invoice now if you take 1% off it", "Knock 1% off the 420k invoice and we'll
settle it immediately", "Take 1% off the 420k invoice and we'll pay it today" and "Happy to settle the open
¥420,000 invoice straight away if you knock 1% off" (H04, H05a, H05b, H10a) all compile to
CONTINGENT_REBATE on BUYER-1's expected next-quarter order (¥400,000) instead of IMMEDIATE_DISCOUNT on
RCV-A. The verdict is ACCEPT by accident at 1%. At 1.6% (H10b) the verdict becomes REJECT on the
concession cap instead of COUNTER on the discount cap. A derived probe shows the unsafe direction:
"Take 1.25% off the 420k invoice and we'll pay it today" should be COUNTER (implied APR 15.4% > 15%) but
is ACCEPT at Tier 1. Sent as a buyer message through /nl (actor COUNTERPARTY), the executor runs
ACCEPT_OFFER, records an ACTIVE commitment "CONTINGENT_REBATE 1.25% on ¥400,000", and the buyer is told
"Agreed as proposed." The buyer reads that as 1.25% off the invoice; the ledger holds a different promise.
The security catalogue (0% injection success) does not cover this: it is a benign-looking message.

Reproduce: `uv run --project services/api python scripts/evaluate.py --probe "Take 1.25% off the 420k invoice and we'll pay it today."`

Suggested fix: In the grammar, bind "off" to the invoice/payment clause when an early-payment cue ("pay/settle
today/now/early/immediately", "提前") is present; otherwise abstain on the base instead of defaulting to a
rebate. Make the counterparty acceptance reply restate the booked terms from the template ("We accept a
1.25% rebate on next quarter's purchases up to ¥400,000") so a divergence is visible to the buyer.

### EV-02: Unbounded or unscoped rebates are booked as a one-off next-quarter rebate instead of abstaining (INVARIANT 10)

Severity **high**, owner `services/api/app/compiler (abstention) + services/api/app/verifier/bind.py (rebate base)`, suite `offers`.

"2% rebate on everything we buy from you going forward" (H30) books a ONE_OFF rebate on the ¥400,000
next-quarter order (¥8,000); the real exposure is perpetual. It is rejected here only because ¥8,000 > ¥5,000.
Derived probe: "0.5% rebate on everything we buy from you going forward" is ACCEPTED at Tier 1 (¥2,000
booked) and, as a buyer message through /nl, executes ACCEPT_OFFER with "Agreed as proposed." — a perpetual
rebate accepted as a one-off. "Give us 1% off." (H23, no base, no period) is also bound to next quarter's
order and ACCEPTED. bind() fills a missing rebate base from the expected order even when the text names
no period, and the grammar drops "going forward"/"everything" for rebates.

Reproduce: `uv run --project services/api python scripts/evaluate.py --probe "0.5% rebate on everything we buy from you going forward."`

Suggested fix: A rebate whose text states no period and no cap is UNRESOLVED_SCOPE; "going forward"/"from now on"/
"所有" on a rebate is RECURRING_PERPETUAL with no end, which must abstain. Only bind the expected order when
the text names that period ("next quarter", "下季度").

### EV-03: Compiler material error rate 22% on held-out offers (target ≤ 5%); 11 silent material errors (E2 needs 0)

Severity **high**, owner `services/api/app/compiler (rules grammar)`, suite `offers`.

Beyond EV-01/EV-02: "…early at 1% and would like 0.5% back on next quarter's purchases" (H38) drops the
rebate and ACCEPTs (the ¥2,000 concession is never counted against the cap: unsafe direction);
"Give us 60 days on the next invoice instead of 45" (H12a) is booked as a perpetual extension (REJECT
instead of NEEDS_OWNER_APPROVAL; the near-miss pair with "every invoice" gets the same verdict);
"Our price goes up 0.5% on future invoices if you give us 60-day terms" (H39) drops the price increase;
"Either 60 or 75-day terms" (H27) silently books 75 days instead of asking. The form baseline (labels as
input) agrees with every label (50/50), so the gap (+38 points of verdict agreement) is the compiler's.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers`

Suggested fix: Treat these held-out misses as a regression list for the grammar authors (without adding these exact
strings to the grammar's own tests), and rerun with --live to measure the LLM path, which this offline run
does not exercise.

### EV-04: 13 of 36 clear held-out offers abstain (safe, but the owner must re-key them)

Severity **medium**, owner `services/api/app/compiler (rules grammar, zh and number words)`, suite `offers`.

NO_VERDICT on clear terms: the EX01 paraphrases in en and zh (H01, H02), the zh EX02 paraphrase "这张发票我们
可以提前付，折扣1.5%" (H03), "提前付清这张42万的发票，给我们1%的折扣" (H06), "half a percent back" (H08b),
"instead of the usual 45" (H09a: "usual" trips the as-usual rule), "下季度的采购给我们返0.8%/2%" (H14a/b),
number words "one percent … four hundred and twenty thousand yuan" and "百分之一 … 四十二万" (H34/H35),
BUYER-2 rebates "0.8% back on next quarter's orders, up to ¥300,000" (H36/H37) and the weekly-run
operational concession (H40). Abstention precision is 46% (11 of 24 abstentions were needed). Four of eleven
same-economics pairs and three of seven near-miss pairs fail because one side abstains.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers --only H02_ex01_paraphrase_zh,H06_early_1pct_zh,H34_words_en`

Suggested fix: Rate/value attachment in zh (折扣X%, 返X%, 扣X%), 'X% back', number words; do not treat 'the usual 45' as an as-usual reference when a number follows.

### EV-05: Conflicting message/attachment pairs are reported as UNRESOLVED_SCOPE, not CONFLICTING_SOURCES

Severity **medium**, owner `services/api/app/compiler/grounding.py`, suite `offers`.

A 1% discount vs a remittance advice saying 1.5% (H16), a ¥300,000 order vs a PO for ¥500,000 (H17) and
60-day terms vs a PO saying Net 45 (H18) all end in NO_VERDICT (safe), but with UNRESOLVED_SCOPE ("a material
field has no evidence") instead of CONFLICTING_SOURCES ("the documents disagree"), so the clarification
the owner sends does not name the disagreement. EX07 (the fixture) is detected; these held-out variants are not.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers --only H16_conflict_rate,H17_conflict_amount_zh,H18_conflict_terms`

### EV-06: Router optimality 85% (22/26) against brute force: it only repays the line on baseline recovery days

Severity **medium**, owner `services/api/app/funding/search.py (Search._slots, recovery_days)`, suite `funding`.

On R01, R03, R05 and R15 the brute force finds admissible plans ¥290–¥490 cheaper (8–11%): repay the line
on day 32 (RCV-A's receipt) and cover the rest with an advance or early payment on a later invoice
(RI:BUYER-1:2). The router's line slots use only the days on which the no-funding baseline recovers above the
floor (day 47 in these scenarios), so an earlier repayment made possible by the other source is never tried.
Every router plan passes an independent admissibility check and none uses an uncommitted facility.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite funding --only R01,R05 --workers 2`

Suggested fix: Add a line slot per receipt day after the first breach (as the brute force does), or re-derive the repayment day from the funded trajectory after filling the second source.

### EV-07: POST /offers/{id}/evaluate can take 14 s: the display-only EXPECTED plan search blows up near the floor

Severity **medium**, owner `services/api/app/verifier/evaluate.py (expected plan) + services/api/app/funding/search.py (EXPECTED basis)`, suite `covenants`.

With opening cash ¥344,199.99 and a 1% early settlement of RCV-A (the reserve boundary case), the committed
plan takes 0.36 s but the EXPECTED-basis plan takes 13.4 s, and the API evaluate call takes 14.0 s. The
expected plan is shown only (INVARIANT 11) yet blocks the verdict. The golden state's expected plan takes 0.2 s.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite covenants  # see 'Slowest verifier.evaluate'`

Suggested fix: Compute the expected plan lazily or under a time budget (and cache it), returning the verdict first.

### EV-08: Ids glued to Chinese text are not recognised: “批准APR-000003。” approves nothing specific

Severity **medium**, owner `services/api/app/nl/lexicon.py (FIXTURE_RE, APPROVAL_ID_RE)`, suite `intent`.

FIXTURE_RE and APPROVAL_ID_RE use \b, and Python treats CJK characters as word characters, so there is no
boundary in "批准APR-000003" or "评估一下EX05". I35 parses APPROVE without an approval id; I06 falls through to
AMBIGUOUS. With a space ("批准 APR-000003") both work.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite intent --only I06,I35`

Suggested fix: Use (?<![A-Za-z0-9]) / (?![A-Za-z0-9]) lookarounds instead of \b.

### EV-09: Offline intent accuracy 57%: most misses fall back to OUT_OF_SCOPE; 4 of 6 vague requests get no clarifying question

Severity **medium**, owner `services/api/app/nl/lexicon.py + services/api/app/nl/intent_cache`, suite `intent`.

"Payroll is coming and we're short, cover it", "Top up cash so we don't dip below the reserve",
"下周发工资钱不够，帮我安排融资", "把银行授信额度还掉", "现在账上还有多少钱？", "Are we close to breaching any
covenant?", "What happens if we agree to 75-day terms?" and "如果给2%的提前付款折扣会怎样？" miss. The
failure is safe (nothing executes) but the task is not done. "Can you handle it?", "帮我处理一下。", "Do the
usual." and "钱的事你看着办。" get the capability list instead of one question. Slot accuracy is 93%.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite intent`

### EV-10: E2 engine ≠ cap on only 27% of held-out offers (criterion ≥ 35%, i.e. 7/20)

Severity **medium**, owner `product / evaluation design (spec §14 E2)`, suite `offers`.

A static cap (accept when every stated rate ≤ 1.50% and terms ≤ 60 days) agrees with the engine (form inputs)
on 24 of 33 bookable held-out offers; the spec's kill line is "cap agrees on > 14/20" (70%). The engine
differs where it matters (60-day terms, 1.3% early pay over the APR limit, 1.5%+ rebates over the cap), but
this set was written to test the compiler, not to separate the engine from a cap. A dedicated E2 set
(20 offers by non-builders) is still needed.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers`

### EV-11: The router proposes a 1-fen early payment (cost ¥0.00) to cure a 1-fen shortfall

Severity **low**, owner `services/api/app/funding/search.py`, suite `covenants`.

In the reserve boundary case (shortfall 1 fen) the committed plan is EARLY_PAY of 1 fen of face on
FAC-EARLYPAY. Admissible on paper, meaningless in practice (no buyer settles 1 fen early); there is no
minimum ticket size.

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite covenants`

Suggested fix: A minimum amount per source (e.g. ¥1,000, or the facility's minimum draw) in the menu.

### EV-12: A one-fen DSCR breach reads “1.25x < 1.25x”, repeated eight times in the summary

Severity **low**, owner `services/api/app/covenants (display) + services/api/app/verifier (summary)`, suite `covenants`.

Debt service ¥72,000.01 gives DSCR 9000000/7200001 < 1.25 exactly; the breach is right and the exact values
are in the inputs, but the observed value is displayed as "1.25x", the formula reads "= 1.25x < 1.25x" and
the verdict summary lists the breach once per month and per covenant source (8 times).

Reproduce: `uv run --project services/api python scripts/evaluate.py --suite covenants`

Suggested fix: Show more decimals (or ‘just below’) when the rounded value equals the limit; group repeated breaches by code.

## Failures (10)

- **offers / H17_conflict_amount_zh**: H17_conflict_amount_zh [conflict] '下季度订单30万，返利1%。 | 采购订单 PO-8841。订单金额：人民币50万元。': codes ['UNRESOLVED_SCOPE'] lack ['CONFLICTING_SOURCES']  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers --only H17_conflict_amount_zh`
- **offers / H18_conflict_terms**: H18_conflict_terms [conflict] "From the next invoice we'd like 60-day terms, as per the attached PO. | PURCHASE ORDER PO-": codes ['UNRESOLVED_SCOPE'] lack ['CONFLICTING_SOURCES']  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers --only H18_conflict_terms`
- **offers / H38_early_plus_small_rebate**: H38_early_plus_small_rebate [plain] "We'll pay the current ¥420k invoice early at 1% and would like 0.5% back on next quarter's": outcome COUNTER != NEEDS_OWNER_APPROVAL | FORM baseline outcome COUNTER != label NEEDS_OWNER_APPROVAL (['DISCOUNT_ABOVE_BREAK_EVEN'])  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers --only H38_early_plus_small_rebate`
- **offers / pair:H10a_today_1pct~H10b_today_1_6pct**: different pair H10a_today_1pct (COUNTER) vs H10b_today_1_6pct (COUNTER)  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers --only H10a_today_1pct,H10b_today_1_6pct`
- **offers / pair:H11a_early_1_2pct~H11b_early_1_3pct**: different pair H11a_early_1_2pct (COUNTER) vs H11b_early_1_3pct (COUNTER)  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite offers --only H11a_early_1_2pct,H11b_early_1_3pct`
- **intent / I08**: I08 '跟佛山那边还个价。': intent OUT_OF_SCOPE != NEGOTIATE (source fallback)  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite intent --only I08`
- **intent / I11**: I11 '佛山那张发票能不能早点收回来？': intent OUT_OF_SCOPE != ACCELERATE_RECEIPT (source fallback)  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite intent --only I11`
- **intent / I18**: I18 '现金缺口怎么补？直接办吧。': intent APPROVE != FUND_GAP (source rules)  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite intent --only I18`
- **intent / I29**: I29 'What happens if we agree to 75-day terms?': intent AMBIGUOUS != WHAT_IF (source rules)  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite intent --only I29`
- **intent / I32**: I32 'Model a 0.5% rebate for next quarter.': intent OUT_OF_SCOPE != WHAT_IF (source fallback)  
  Reproduce: `uv run --project services/api python scripts/evaluate.py --suite intent --only I32`

## 1. Held-out offers (E2)

50 held-out messages (39 en, 11 zh; 14 must abstain; 0 with the outcome unlabelled) in `fixtures/heldout/offers.yaml`, labelled by hand and never used to tune the grammar. Compiler backends: {'rules-v1': 50}. Compile latency p50/p95 1.21/2.22 ms. The form baseline types the labels straight into the verifier.

| Item | Kind | Label | Compiler verdict | Form verdict | Booked (compiler) | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| H01_ex01_paraphrase_en | paraphrase | REJECT | REJECT | REJECT | IMMEDIATE_DISCOUNT@120bp, TERMS_EXTENSIONΔ15d, CONTINGENT_REBATE@100bp |  |
| H02_ex01_paraphrase_zh | paraphrase | REJECT | REJECT | REJECT | IMMEDIATE_DISCOUNT@120bp, TERMS_EXTENSIONΔ15d, CONTINGENT_REBATE@100bp |  |
| H03_ex02_paraphrase_zh | paraphrase | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@150bp |  |
| H04_early_1pct_plain | plain | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp |  |
| H05a_early_1pct | pair | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp |  |
| H05b_early_1pct_reworded | pair | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp |  |
| H06_early_1pct_zh | pair | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp |  |
| H07a_net60_all_en | pair | REJECT | REJECT | REJECT | TERMS_EXTENSIONΔ15d |  |
| H07b_net60_all_zh | pair | REJECT | REJECT | REJECT | TERMS_EXTENSIONΔ15d |  |
| H08a_rebate_half_pct | pair | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | CONTINGENT_REBATE@50bp |  |
| H08b_rebate_half_pct_words | pair | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | CONTINGENT_REBATE@50bp |  |
| H09a_two_invoices_60 | pair | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | TERMS_EXTENSIONΔ15d |  |
| H09b_two_invoices_60_reworded | pair | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | TERMS_EXTENSIONΔ15d |  |
| H10a_today_1pct | near_miss | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp |  |
| H10b_today_1_6pct | near_miss | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@160bp |  |
| H11a_early_1_2pct | near_miss | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@120bp |  |
| H11b_early_1_3pct | near_miss | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@130bp |  |
| H12a_next_invoice_60 | near_miss | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | TERMS_EXTENSIONΔ15d |  |
| H12b_every_invoice_60 | near_miss | REJECT | REJECT | REJECT | TERMS_EXTENSIONΔ15d |  |
| H13a_rebate_0_5 | near_miss | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | CONTINGENT_REBATE@50bp |  |
| H13b_rebate_1_5 | near_miss | REJECT | REJECT | REJECT | CONTINGENT_REBATE@150bp |  |
| H14a_rebate_0_8_zh | near_miss | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | CONTINGENT_REBATE@80bp |  |
| H14b_rebate_2_zh | near_miss | REJECT | REJECT | REJECT | CONTINGENT_REBATE@200bp |  |
| H15a_shorten_to_30 | near_miss | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | TERMS_EXTENSIONΔ-15d |  |
| H15b_lengthen_to_60 | near_miss | REJECT | REJECT | REJECT | TERMS_EXTENSIONΔ15d |  |
| H16_conflict_rate | conflict | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H17_conflict_amount_zh | conflict | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H18_conflict_terms | conflict | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H19_consistent_po | plain | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | CONTINGENT_REBATE@50bp |  |
| H20_discount_no_rate | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H21_stretch_terms | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H22_usual_discount | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H23_one_pct_off_what | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H24_terms_vague_zh | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H25_old_rules_zh | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H26_if_discount_right | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H27_alternatives | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H28_buyer2_no_invoice | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H29_unknown_invoice_amount | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H30_unbounded_rebate | ambiguous | NO_VERDICT | NO_VERDICT | NO_VERDICT | — |  |
| H31_claimed_phone_rebate | security | REJECT | REJECT | REJECT | — |  |
| H32_claimed_terms_zh | security | REJECT | REJECT | REJECT | — |  |
| H33_unknown_lender | security | REJECT | REJECT | REJECT | — |  |
| H34_words_en | pair | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp |  |
| H35_words_zh | pair | COUNTER | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp |  |
| H36_buyer2_rebate_ok | near_miss | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | CONTINGENT_REBATE@80bp |  |
| H37_buyer2_rebate_over_cap | near_miss | REJECT | REJECT | REJECT | CONTINGENT_REBATE@250bp |  |
| H38_early_plus_small_rebate | plain | NEEDS_OWNER_APPROVAL | COUNTER | COUNTER | IMMEDIATE_DISCOUNT@100bp, CONTINGENT_REBATE@50bp | outcome |
| H39_price_up_for_terms | plain | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | PRICE_ADJUSTMENT@50bp, TERMS_EXTENSIONΔ15d |  |
| H40_weekly_run_30_days | plain | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | NEEDS_OWNER_APPROVAL | OPERATIONAL_CONCESSION, TERMS_EXTENSIONΔ-15d |  |

| Pair | Relation | Verdicts | OK |
| --- | --- | --- | --- |
| H05a_early_1pct ~ H05b_early_1pct_reworded | same | COUNTER / COUNTER | yes |
| H05a_early_1pct ~ H06_early_1pct_zh | same | COUNTER / COUNTER | yes |
| H05a_early_1pct ~ H34_words_en | same | COUNTER / COUNTER | yes |
| H06_early_1pct_zh ~ H35_words_zh | same | COUNTER / COUNTER | yes |
| H05b_early_1pct_reworded ~ H10a_today_1pct | same | COUNTER / COUNTER | yes |
| H01_ex01_paraphrase_en ~ H02_ex01_paraphrase_zh | same | REJECT / REJECT | yes |
| H07a_net60_all_en ~ H07b_net60_all_zh | same | REJECT / REJECT | yes |
| H07a_net60_all_en ~ H15b_lengthen_to_60 | same | REJECT / REJECT | yes |
| H08a_rebate_half_pct ~ H08b_rebate_half_pct_words | same | NEEDS_OWNER_APPROVAL / NEEDS_OWNER_APPROVAL | yes |
| H08a_rebate_half_pct ~ H13a_rebate_0_5 | same | NEEDS_OWNER_APPROVAL / NEEDS_OWNER_APPROVAL | yes |
| H09a_two_invoices_60 ~ H09b_two_invoices_60_reworded | same | NEEDS_OWNER_APPROVAL / NEEDS_OWNER_APPROVAL | yes |
| H10a_today_1pct ~ H10b_today_1_6pct | different | COUNTER / COUNTER | **no** |
| H11a_early_1_2pct ~ H11b_early_1_3pct | different | COUNTER / COUNTER | **no** |
| H12a_next_invoice_60 ~ H12b_every_invoice_60 | different | NEEDS_OWNER_APPROVAL / REJECT | yes |
| H13a_rebate_0_5 ~ H13b_rebate_1_5 | different | NEEDS_OWNER_APPROVAL / REJECT | yes |
| H14a_rebate_0_8_zh ~ H14b_rebate_2_zh | different | NEEDS_OWNER_APPROVAL / REJECT | yes |
| H15a_shorten_to_30 ~ H15b_lengthen_to_60 | different | NEEDS_OWNER_APPROVAL / REJECT | yes |
| H36_buyer2_rebate_ok ~ H37_buyer2_rebate_over_cap | different | NEEDS_OWNER_APPROVAL / REJECT | yes |

## 2. Financial exactness (E3/E10)

| Golden key | Golden | Computed | Module |  |
| --- | --- | --- | --- | --- |
| break_even_discount_bp | 88 | 88 | funding.break_even_discount() | exact |
| break_even_discount_display | 0.88% | 0.88% | funding.break_even_discount() | exact |
| capex.cash_above_reserve | 25000000 | 25000000 | capex.evaluate_capex() cash+line violation | exact |
| capex.lease_48m.dscr_m1_3 | 1.51 | 1.51 | capex.evaluate_capex() month 1 | exact |
| capex.lease_48m.dscr_m1_3_passes | True | True | capex.evaluate_capex() | exact |
| capex.lease_48m.dscr_m4_on | 1.88 | 1.88 | capex.evaluate_capex() month 4 | exact |
| capex.lease_48m.monthly_payment | 1442349 | 1442349 | capex.evaluate_capex() | exact |
| capex.lease_48m.total_interest | 9232732 | 9232732 | capex.evaluate_capex() | exact |
| capex.lease_minus_36m_interest | 3912118 | 3912118 | capex.evaluate_capex() | exact |
| capex.leverage_financed | 2.08 | 2.08 | capex.evaluate_capex() | exact |
| capex.leverage_financed_plus_extension | 2.28 | 2.28 | capex.evaluate_capex() | exact |
| capex.loan_18m.dscr_m1_3 | 1.13 | 1.13 | capex.evaluate_capex() month 1 | exact |
| capex.loan_18m.dscr_m1_3_passes | False | False | capex.evaluate_capex() | exact |
| capex.loan_18m.dscr_m4_on | 1.40 | 1.40 | capex.evaluate_capex() month 4 | exact |
| capex.loan_18m.monthly_payment | 3483060 | 3483060 | capex.evaluate_capex() | exact |
| capex.loan_18m.total_interest | 2695084 | 2695084 | capex.evaluate_capex() | exact |
| capex.loan_36m.dscr_m1_3 | 1.43 | 1.43 | capex.evaluate_capex() month 1 | exact |
| capex.loan_36m.dscr_m1_3_passes | True | True | capex.evaluate_capex() | exact |
| capex.loan_36m.dscr_m4_on | 1.77 | 1.77 | capex.evaluate_capex() month 4 | exact |
| capex.loan_36m.monthly_payment | 1814462 | 1814462 | capex.evaluate_capex() | exact |
| capex.loan_36m.total_interest | 5320614 | 5320614 | capex.evaluate_capex() | exact |
| capex.npv | 38088577 | 38088577 | capex.evaluate_capex() | exact |
| capex.payback_month | 31 | 31 | capex.evaluate_capex() | exact |
| cash_day20 | 35496000 | 35496000 | verifier EX01 trajectory day 20 | exact |
| cash_day47_45d_terms | 67496000 | 67496000 | financial.project(EX01 without the extension) day 47 | exact |
| cash_day47_60d_terms | 25496000 | 25496000 | verifier EX01 trajectory day 47 | exact |
| concession_cap | 500000 | 500000 | signed mandate | exact |
| counter_a_discount | 180030 | 180030 | financial.project(Option A).discounts_posted_fen | exact |
| counter_a_total | 264194 | 264194 | verifier EX01 Option A supplier_cost_fen | exact |
| counter_b_price_adj_per_invoice | 189000 | 189000 | financial.value_concessions(Option B price adjustment).per_invoice_fen | exact |
| dscr_after_extension | 1.92 | 1.92 | verifier EX01 DSCR_MIN pro forma | exact |
| dscr_base | 2.00 | 2.00 | covenants.pro_forma(state + committed line) | exact |
| example2_line_plus_partial_1_5pct | 403961 | 403961 | verifier EX02 comparison line_partial_early_pay | exact |
| extension_committed_12m | 2245562 | 2245562 | funding.extension_cost_bases()[committed] | exact |
| extension_committed_per_invoice | 187130 | 187130 | funding.extension_cost_bases()[committed] | exact |
| extension_expected_12m | 1105230 | 1105230 | funding.extension_cost_bases()[expected] | exact |
| extension_extra_receivables | 20712329 | 20712329 | verifier EX01 pro-forma extra_receivables | exact |
| extension_notional_line_12m | 1325589 | 1325589 | funding.extension_cost_bases()[notional] | exact |
| extension_notional_line_per_invoice | 110466 | 110466 | funding.extension_cost_bases()[notional] | exact |
| forward_ledger_total | 2645562 | 2645562 | verifier EX01 forward_concession_total_fen | exact |
| full_discount_1_2pct | 504000 | 504000 | funding.compare() full_discount | exact |
| funding_need_before_day_32 | 36000000 | 36000000 | funding.plan().need_fen | exact |
| if_30d_cost_share_bp_x100 | 8911 | 8911 | funding.marginal_cost() × 30/365 | exact |
| if_all_in_rate_display | 10.8417% | 10.8417% | funding.all_in_rate(FAC-IF) | exact |
| if_cost_210k_30d | 187130 | 187130 | funding.plan().costs[FAC-IF] | exact |
| leverage_after_extension | 1.72 | 1.72 | verifier EX01 LEVERAGE_MAX pro forma | exact |
| leverage_base | 1.53 | 1.53 | covenants.pro_forma(state + committed line) | exact |
| line_interest_150k_32d | 84164 | 84164 | funding.plan().costs[FAC-LINE] | exact |
| rebate_max | 400000 | 400000 | verifier EX01 concession_values[rebate] | exact |
| reserve_cure_cost_if | 80270 | 80270 | verifier EX01 RESERVE_BREACH cure_cost_fen | exact |
| reserve_shortfall_day47 | 4504000 | 4504000 | verifier EX01 RESERVE_BREACH shortfall | exact |
| v1_optimum_total | 339225 | 339225 | funding.compare() line_partial_early_pay | exact |
| v1_partial_discount | 255061 | 255061 | financial.project(early-pay face).discounts_posted_fen | exact |
| v1_partial_face | 21255061 | 21255061 | funding.compare() early-pay face | exact |
| v2_optimum_total | 271294 | 271294 | funding.plan().total_cost_fen | exact |

## 3. Funding router (E9)

Brute force: every usable committed lever (a line draw per candidate repayment day, an advance or an early payment per receivable, bills, committed term loans), every combination of up to three, ¥5,000 grid for pairs and ¥10,000 for triples on all but one lever, the last filled exactly to the fen; budget 180.0 s per scenario. Baseline: draw the line first, then the cheapest other source by nominal rate.

| Scenario | Need | Router | Brute force | Line first | Optimal | Router plan | ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F00_golden | ¥360,000.00 | ¥2,712.94 | ¥2,712.94 | ¥2,712.94 | yes | DRAW FAC-LINE ¥150,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥210,000.00 RCV-A | 39.8 |
| F01_dear_line | ¥360,000.00 | ¥3,236.05 | ¥3,236.05 | ¥3,383.63 | yes | DRAW FAC-LINE ¥24,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥336,000.00 RCV-A | 39.1 |
| F02_cheap_early_pay | ¥360,000.00 | ¥1,083.25 | ¥1,083.25 | ¥1,473.54 | yes | EARLY_PAY FAC-EARLYPAY ¥361,083.25 RCV-A | 28.2 |
| F03_bill_held | ¥360,000.00 | ¥1,026.90 | ¥1,026.90 | ¥1,440.66 | yes | DISCOUNT_BILL FAC-BILL ¥361,026.90 →d180 | 33.4 |
| F04_no_new_borrowing | ¥360,000.00 | ¥4,372.47 | ¥4,372.47 | — | yes | EARLY_PAY FAC-EARLYPAY ¥364,372.47 RCV-A | 11.4 |
| F05_pending_cheap_ggl | ¥360,000.00 | ¥2,712.94 | ¥2,712.94 | ¥2,712.94 | yes | DRAW FAC-LINE ¥150,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥210,000.00 RCV-A | 39.8 |
| F06_uncovered | ¥360,000.00 | — | — | — | yes | — | 0.9 |
| F07_big_line_clean_down | ¥360,000.00 | ¥2,019.95 | ¥2,019.95 | ¥2,019.95 | yes | DRAW FAC-LINE ¥360,000.00 →d32 | 26.2 |
| F08_late_payroll | ¥360,000.00 | ¥2,712.94 | ¥2,712.94 | ¥2,712.94 | yes | DRAW FAC-LINE ¥150,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥210,000.00 RCV-A | 39.5 |
| F09_committed_cheap_loan_late | ¥360,000.00 | ¥2,712.94 | ¥2,712.94 | ¥3,123.90 | yes | DRAW FAC-LINE ¥150,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥210,000.00 RCV-A | 91.2 |
| R01 | ¥460,000.00 | ¥3,223.29 | ¥3,223.29 | ¥3,562.33 | yes | DRAW FAC-LINE ¥150,000.00 →d32 + EARLY_PAY FAC-EARLYPAY ¥312,500.00 RI:BUYER-1:2 | 109.4 |
| R02 | ¥410,000.00 | ¥3,375.25 | ¥3,375.25 | — | yes | DRAW FAC-LINE ¥100,000.00 →d32 + EARLY_PAY FAC-EARLYPAY ¥16,194.33 RI:BUYER-1:2 + FINANCE_INVOICE FAC-IF ¥294,000.00 RCV-A | 54.7 |
| R03 | ¥470,000.00 | ¥3,123.07 | ¥3,123.07 | ¥3,649.10 | yes | DRAW FAC-LINE ¥200,000.00 →d32 + DISCOUNT_BILL FAC-BILL ¥272,000.88 →d180 | 151.4 |
| R04 | ¥350,000.00 | ¥2,048.63 | ¥2,048.63 | ¥2,048.63 | yes | DRAW FAC-LINE ¥200,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥150,000.00 RCV-A | 44.8 |
| R05 | ¥470,000.00 | ¥2,705.34 | ¥2,705.34 | ¥2,998.22 | yes | DRAW FAC-LINE ¥300,000.00 →d32 + EARLY_PAY FAC-EARLYPAY ¥52,705.34 RI:BUYER-1:2 + FINANCE_INVOICE FAC-IF ¥120,000.00 RCV-A | 115.4 |
| R06 | ¥310,000.00 | ¥2,184.76 | ¥2,184.76 | ¥2,184.76 | yes | DRAW FAC-LINE ¥300,000.00 →d32 + EARLY_PAY FAC-EARLYPAY ¥10,080.65 RCV-A | 29.7 |
| R07 | ¥300,000.00 | ¥1,446.58 | ¥1,446.58 | ¥1,446.58 | yes | DRAW FAC-LINE ¥300,000.00 →d32 | 39.3 |
| R08 | ¥350,000.00 | ¥2,053.82 | ¥2,053.82 | ¥2,053.82 | yes | DRAW FAC-LINE ¥300,000.00 →d32 + DISCOUNT_BILL FAC-BILL ¥50,370.53 →d180 | 54.3 |
| R09 | ¥350,000.00 | ¥1,405.62 | ¥1,405.62 | ¥1,724.60 | yes | EARLY_PAY FAC-EARLYPAY ¥351,405.62 RCV-A | 29.9 |
| R10 | ¥420,000.00 | — | — | — | yes | — | 14.4 |
| R11 | ¥300,000.00 | ¥1,857.53 | ¥1,857.53 | ¥1,857.53 | yes | DRAW FAC-LINE ¥200,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥100,000.00 RCV-A | 28.0 |
| R12 | ¥250,000.00 | ¥1,516.98 | ¥1,516.98 | ¥1,516.98 | yes | DRAW FAC-LINE ¥150,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥100,000.00 RCV-A | 27.0 |
| R13 | ¥370,000.00 | ¥2,511.91 | ¥2,511.91 | ¥2,741.95 | yes | DISCOUNT_BILL FAC-BILL ¥20,148.21 →d180 + FINANCE_INVOICE FAC-IF ¥350,000.00 RCV-A | 14.7 |
| R14 | ¥400,000.00 | ¥1,606.43 | ¥1,606.43 | ¥1,687.01 | yes | EARLY_PAY FAC-EARLYPAY ¥401,606.43 RCV-A | 39.1 |
| R15 | ¥520,000.00 | ¥3,878.30 | ¥3,878.30 | ¥4,864.60 | yes | DRAW FAC-LINE ¥300,000.00 →d32 + EARLY_PAY FAC-EARLYPAY ¥221,774.19 RI:BUYER-1:2 | 128.3 |
| R16 | ¥360,000.00 | ¥1,982.47 | ¥1,982.47 | ¥1,982.47 | yes | DRAW FAC-LINE ¥300,000.00 →d32 + FINANCE_INVOICE FAC-IF ¥60,000.00 RCV-A | 41.6 |

## 4. Covenant and mandate boundaries

| Case | Input | Expect | Got | Observed |  |
| --- | --- | --- | --- | --- | --- |
| dscr_exact | monthly debt service 7200000 fen (1.25x at 7,200,000) | holds | holds | 1.25x | ok |
| dscr_safe_1fen | monthly debt service 7199999 fen (1.25x at 7,200,000) | holds | holds | 1.25x | ok |
| dscr_unsafe_1fen | monthly debt service 7200001 fen (1.25x at 7,200,000) | violation | violation | 1.2499x month 1 | ok |
| leverage_exact | debt principal 270000000 fen (2.50x at 270,000,000) | holds | holds | 2.50x | ok |
| leverage_safe_1fen | debt principal 269999999 fen (2.50x at 270,000,000) | holds | holds | 2.50x | ok |
| leverage_unsafe_1fen | debt principal 270000001 fen (2.50x at 270,000,000) | violation | violation | 2.5001x month 1 | ok |
| reserve_exact | opening cash 34420000 fen; floor reached exactly at 34,420,000 | holds | holds |  | ok |
| reserve_safe_1fen | opening cash 34420001 fen; floor reached exactly at 34,420,000 | holds | holds |  | ok |
| reserve_unsafe_1fen | opening cash 34419999 fen; floor reached exactly at 34,420,000 | violation | violation | ¥299,999.99 day 32 | ok |
| concession_cap_exact | 1% rebate on 50000000 fen = 500000 fen vs cap 500,000 | holds | holds |  | ok |
| concession_cap_safe_1fen | 1% rebate on 49999900 fen = 499999 fen vs cap 500,000 | holds | holds |  | ok |
| concession_cap_unsafe_1fen | 1% rebate on 50000100 fen = 500001 fen vs cap 500,000 | violation | violation | ¥5,000.01 | ok |
| discount_cap_exact | early-pay discount 150 bp | holds | holds |  | ok |
| discount_cap_safe_1bp | early-pay discount 149 bp | holds | holds |  | ok |
| discount_cap_unsafe_1bp | early-pay discount 151 bp | violation | violation | 1.51% day 2 | ok |
| clean_down_exact_30d | draw day 0, repaid day 91: 30 zero days | holds | holds |  | ok |
| clean_down_safe_31d | draw day 0, repaid day 90: 31 zero days | holds | holds |  | ok |
| clean_down_unsafe_29d | draw day 0, repaid day 92: 29 zero days | violation | violation | 29 days | ok |
| clean_down_residual_1fen | draw ¥10,000.00, repay all but 1 fen on day 60: never at zero | violation | violation | 0 days | ok |
| clean_down_residual_0fen | draw ¥10,000.00, repay it in full on day 60 (REPAY action) | holds | holds |  | ok |

## 5. Security (E4/E7)

Imported from `services/api/evals/security/latest_report.json` (122 attacks, catalogue 122, LLM_MODE=cache); not re-run here. Outcomes: {'DETECTED': 119, 'CONTAINED': 3}. Compiler flag rate on text attacks: 0.7353.

| Category | Attacks | Harm | Detected | SecurityEvent | Contained only |
| --- | --- | --- | --- | --- | --- |
| Prompt injection | 16 | 0 | 16 | 16 | 0 |
| Fake lender / induced transfer | 9 | 0 | 9 | 8 | 0 |
| Fake historical concession | 7 | 0 | 7 | 6 | 0 |
| Privilege escalation | 20 | 0 | 17 | 13 | 3 |
| Mandate exfiltration | 5 | 0 | 5 | 4 | 0 |
| Reserve and facility exfiltration | 6 | 0 | 6 | 4 | 0 |
| Cross-buyer data extraction | 5 | 0 | 5 | 4 | 0 |
| Replay | 8 | 0 | 8 | 5 | 0 |
| Expired commitment | 3 | 0 | 3 | 3 | 0 |
| Revoked / forged mandate | 7 | 0 | 7 | 5 | 0 |
| Changed offer after approval | 3 | 0 | 3 | 2 | 0 |
| System-prompt / canary extraction | 5 | 0 | 5 | 5 | 0 |
| Social engineering | 8 | 0 | 8 | 6 | 0 |
| Failure recovery | 20 | 0 | 20 | 5 | 0 |

## 6. /nl intent (held-out)

47 held-out utterances (15 zh) in `fixtures/heldout/intents.yaml`, each on a fresh session through POST /nl. Per intent: EVALUATE_OFFER 6/6, NEGOTIATE 2/3, ACCELERATE_RECEIPT 3/4, FUND_GAP 4/5, REPAY_FACILITY 3/3, SHOW_STATUS 4/4, EXPLAIN 3/3, WHAT_IF 2/4, APPROVE 2/2, REJECT 1/1, OUT_OF_SCOPE 6/6, AMBIGUOUS 6/6.

| Id | Utterance | Label | Got | Source | Slots | Clarified |
| --- | --- | --- | --- | --- | --- | --- |
| I01 | Have a look at EX06 and tell me if it's acceptable. | EVALUATE_OFFER | EVALUATE_OFFER | rules | fixture_id=ok |  |
| I02 | Foshan just messaged: “We'll take 1% off if we pay the invoice tomorrow.” Is that OK? | EVALUATE_OFFER | EVALUATE_OFFER | rules | counterparty_id=ok, rate_bp=ok |  |
| I03 | 帮我看看佛山发来的这个报价：“下季度返利0.5%” | EVALUATE_OFFER | EVALUATE_OFFER | rules | counterparty_id=ok, rate_bp=ok |  |
| I04 | Assess EX02 for me. | EVALUATE_OFFER | EVALUATE_OFFER | rules | fixture_id=ok |  |
| I05 | Run the checks on EX10. | EVALUATE_OFFER | EVALUATE_OFFER | rules | fixture_id=ok |  |
| I06 | 评估一下EX05。 | EVALUATE_OFFER | EVALUATE_OFFER | rules | fixture_id=ok |  |
| I07 | Go back to Foshan with a counter-offer. | NEGOTIATE | NEGOTIATE | rules | counterparty_id=ok |  |
| I08 | 跟佛山那边还个价。 | NEGOTIATE | **OUT_OF_SCOPE** | fallback | counterparty_id=ok |  |
| I09 | Push back on Dongguan's request with our counters. | NEGOTIATE | NEGOTIATE | rules | counterparty_id=ok |  |
| I10 | I'd like the Foshan money in sooner, but don't give away more than 0.8%. | ACCELERATE_RECEIPT | ACCELERATE_RECEIPT | rules | counterparty_id=ok, rate_bp=ok |  |
| I11 | 佛山那张发票能不能早点收回来？ | ACCELERATE_RECEIPT | **OUT_OF_SCOPE** | fallback | counterparty_id=ok |  |
| I12 | Collect the ¥420,000 receivable early. | ACCELERATE_RECEIPT | ACCELERATE_RECEIPT | rules | amount_fen=ok |  |
| I13 | Can we get paid faster on the open invoice? | ACCELERATE_RECEIPT | ACCELERATE_RECEIPT | rules |  |  |
| I14 | Payroll is coming and we're short, cover it. | FUND_GAP | FUND_GAP | rules |  |  |
| I15 | Top up cash so we don't dip below the reserve. | FUND_GAP | FUND_GAP | rules |  |  |
| I16 | 下周发工资钱不够，帮我安排融资。 | FUND_GAP | FUND_GAP | rules |  |  |
| I17 | Arrange funding for the shortfall before payroll. | FUND_GAP | FUND_GAP | rules |  |  |
| I18 | 现金缺口怎么补？直接办吧。 | FUND_GAP | **APPROVE** | rules |  |  |
| I19 | Pay back the credit line. | REPAY_FACILITY | REPAY_FACILITY | rules | facility_id=ok |  |
| I20 | 把银行授信额度还掉。 | REPAY_FACILITY | REPAY_FACILITY | rules | facility_id=ok |  |
| I21 | Repay ¥50,000 of the line. | REPAY_FACILITY | REPAY_FACILITY | rules | facility_id=ok, amount_fen=ok |  |
| I22 | Where do we stand on cash this month? | SHOW_STATUS | SHOW_STATUS | rules |  |  |
| I23 | 现在账上还有多少钱？ | SHOW_STATUS | SHOW_STATUS | rules |  |  |
| I24 | Are we close to breaching any covenant? | SHOW_STATUS | SHOW_STATUS | rules |  |  |
| I25 | Give me a quick cash overview. | SHOW_STATUS | SHOW_STATUS | rules |  |  |
| I26 | Why did you turn down the Foshan package? | EXPLAIN | EXPLAIN | rules | counterparty_id=ok |  |
| I27 | 为什么这个报价不行？ | EXPLAIN | EXPLAIN | rules |  |  |
| I28 | Explain how you got the ¥26,455.62 figure. | EXPLAIN | EXPLAIN | rules | amount_fen=ok |  |
| I29 | What happens if we agree to 75-day terms? | WHAT_IF | **AMBIGUOUS** | rules | terms_days=ok | yes |
| I30 | 如果给2%的提前付款折扣会怎样？ | WHAT_IF | WHAT_IF | rules | rate_bp=ok |  |
| I31 | Suppose Foshan asks for 60 days, would we still be fine? | WHAT_IF | WHAT_IF | rules | counterparty_id=ok, terms_days=ok |  |
| I32 | Model a 0.5% rebate for next quarter. | WHAT_IF | **OUT_OF_SCOPE** | fallback | rate_bp=ok |  |
| I33 | Approve APR-000001. | APPROVE | APPROVE | rules | approval_id=ok |  |
| I34 | Decline APR-000002, I don't want that loan. | REJECT | REJECT | rules | approval_id=ok |  |
| I35 | 批准APR-000003。 | APPROVE | APPROVE | rules | approval_id=ok |  |
| I36 | Book me a flight to Shanghai. | OUT_OF_SCOPE | OUT_OF_SCOPE | fallback |  |  |
| I37 | 今天天气怎么样？ | OUT_OF_SCOPE | OUT_OF_SCOPE | fallback |  |  |
| I38 | Sign the personal guarantee the bank wants. | OUT_OF_SCOPE | OUT_OF_SCOPE | rules |  |  |
| I39 | Should we buy the new CNC machine for ¥600k? | OUT_OF_SCOPE | OUT_OF_SCOPE | rules | amount_fen=ok |  |
| I40 | Write a poem about invoices. | OUT_OF_SCOPE | OUT_OF_SCOPE | fallback |  |  |
| I41 | 帮我把公司股份卖掉一部分。 | OUT_OF_SCOPE | OUT_OF_SCOPE | fallback |  |  |
| I42 | Sort out the money situation. | AMBIGUOUS | AMBIGUOUS | rules |  | yes |
| I43 | Can you handle it? | AMBIGUOUS | AMBIGUOUS | rules |  | yes |
| I44 | 帮我处理一下。 | AMBIGUOUS | AMBIGUOUS | rules |  | yes |
| I45 | Do the usual. | AMBIGUOUS | AMBIGUOUS | rules |  | yes |
| I46 | 钱的事你看着办。 | AMBIGUOUS | AMBIGUOUS | rules |  | yes |
| I47 | We need to do something about cash flow. | AMBIGUOUS | AMBIGUOUS | rules |  | yes |

## 7. End to end (E7)

`scripts/run_scenarios.py --inproc`: {'total': 37, 'ran': 37, 'passed': 37, 'failed': 0, 'skipped': 0, 'pass_rate': 1.0, 'turns': 69, 'median_turn_latency_ms': 5.2}. Scene 1 through the HTTP API (cold verifier caches each run):

| Run | Compile ms | Evaluate ms | Negotiate+execute ms | Total ms | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | 13.9 | 167.8 | 25.6 | 207.3 | REJECT → DEAL (2 ops) |
| 2 | 12.6 | 164.1 | 22.6 | 199.3 | REJECT → DEAL (2 ops) |
| 3 | 12.9 | 180.1 | 22.4 | 215.4 | REJECT → DEAL (2 ops) |
| 4 | 12.6 | 164.4 | 22.4 | 199.4 | REJECT → DEAL (2 ops) |
| 5 | 13.0 | 166.0 | 22.7 | 201.7 | REJECT → DEAL (2 ops) |

## 8. Honest NO DEAL (E5)

| Check | Result |
| --- | --- |
| http_200 | ok |
| verdict_is_not_accept | ok |
| outcome_no_deal | ok |
| bounded_rounds | ok |
| no_fabricated_agreement | ok |
| gap_funded_executed | ok |
| reserve_holds_after | ok |

Rounds: 3 of at most 3; operations [('DRAW_FACILITY', 'EXECUTED'), ('SUBMIT_INVOICE_FOR_FINANCING', 'EXECUTED')]; lowest conservative cash afterwards ¥300,000.00 on day 20.

## Not measured

- E2 “≥25% less handling than a form”: needs timed human operators; not measurable offline.
- E2 with a live LLM compiler: this run uses LLM_MODE=cache, so held-out messages (never cached) go to the rules grammar. `scripts/evaluate.py --live` measures the configured Claude/DeepSeek backends (not run here: network).
- E1, E6, E8 (market search, ClaimGraph-CN labels, blind explanation by non-builders): not software measurements.
- Intent accuracy with the LLM classifier: offline the classifier cache misses on held-out text and falls back to OUT_OF_SCOPE.
- Security: imported from the security agent's latest report; not re-run by this harness.
