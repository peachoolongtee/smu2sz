# Financial semantics

The one place that says what each financial quantity means. Planner, verifier, executor, clock, alerts, capex,
the borrower file and the UI must all follow it. Decided by the technical owner on 3 Oct 2026 after the independent
audit (`docs/research/independent-principal-audit-2026-10-03.md`). "Status" says whether the code follows the rule
yet; the open ones are tracked in `docs/CONTINUOUS_OPTIMIZATION.md`.

Money is integer fen; rates are basis points; days are absolute integers; a year is 365 days; a posting is rounded
half-up to the fen once, where the cash moves (ADR-0002).

## 1. Cash and time

| Rule | Status |
| --- | --- |
| `state.cash_fen` is the bank balance at the start of today. Days before `as_of_day` are closed: nothing may post there. | Done (3 Oct) |
| Cash exists only after the event that creates it. Funding requested on day d on a facility with lead time L becomes cash on day d + L. Until then it is "requested", not cash. | Done (3 Oct) |
| A receipt is recorded only from the bank feed or the owner. The clock never assumes one arrived. | Done |
| An owner-requested facility repayment is a fact like a receipt: the mandate's expiry, revocation and version do not block it. The signature and admission still apply. The same repayment by the agent is refused once the mandate has expired. | Done (3 Oct; `tests/operations/test_redteam_e.py::test_f5_*`) |
| Interest on a draw or advance runs from the day the cash lands. | Done (3 Oct) |
| A projected discretionary repayment (a credit line) is an assumption, labelled as such. It happens only when an operation executes it. Contractual instalments and maturities are posted by the simulated bank as they fall due. | Done (3 Oct) |
| The reserve (`min_cash_fen`) is tested on each day's closing balance of the conservative projection. | Done |

## 2. Receivables

| Rule | Status |
| --- | --- |
| An invoice has one contractual face and one due day, read by every module. Accepted terms or price changes are written onto the invoice once: at acceptance for an issued invoice, at issue for a future one. | Done (3 Oct) |
| A receipt reduces the contractual face. Nothing is ever recomputed on the remaining balance. | Done (3 Oct) |
| The scope of a finite agreement ("this invoice", "the next 3 invoices", "until day D") is fixed at acceptance as a list of invoice ids or an issue-day range. Settling an invoice never moves the scope to another invoice. An unnamed scope never starts before today. A finite agreement ends, and its forward concession is released, when every invoice in its scope is paid. | Done (3 Oct) |
| An invoice can be financed only while it is open, confirmed, not under an early-payment agreement, and only up to the advance rate of its **outstanding** face, with the cash landing before its due day. | Done (3 Oct) |
| An early-payment discount is earned only by a receipt on or before the promised day. A later receipt of the same amount is a plain receipt; the difference stays due. | Done (3 Oct) |
| An early-payment agreement is settled by any portion of its face received on or before the promised day. Each portion earns the agreed rate on that portion (¥100,000 of ¥257,200 at 0.85% is a receipt of ¥99,150.00), and the rest of the face may follow by the same day. A counter that offers early payment states its day ("paid on or before day 2"). The projection and the reconciliation follow the portions; a queued receipt keeps the day it was reported, so one reported on time and approved late still earns the discount. | Done (3 Oct; `tests/operations/test_redteam_e.py::test_f4_*`, `test_f6_*`) |
| An early-pay-only commitment whose promises have all lapsed (the promised day passed unpaid) is closed by the clock: status EXPIRED, with the lapsed obligations listed and shown to the owner. A lapsed agreement no longer blocks financing the invoice; a live one still does. A package with other live terms stays ACTIVE and revocable, and an early receipt fulfils a commitment only when nothing else in it is live. | Done (3 Oct; `tests/operations/test_redteam_d.py::test_f3_*`, `test_f5_*`) |
| Terms in force for a buyer are the template's base terms plus the accepted adjustments (45 days plus an accepted +10 days is 55). A stated target ("40 days") binds against the terms in force for the buyer's next invoice (40 against 55 in force is a gain of 15 days), and the counter texts and the owner's terms constraint read the same terms. | Done (3 Oct; `tests/verifier/test_redteam_e.py::test_f2_*`, `tests/verifier/test_owner_constraints.py`) |

## 3. Admission: what may execute

One function (`app/funding/admission.py`) judges every draw, advance and repayment on today's books with the
planner's engine and predicates, inside the executor's transaction, whoever asks.

| Class | Rule | Effect |
| --- | --- | --- |
| Hard | The engine cannot book it (limit, advance rate, lead time, invoice state) | Refused for everyone |
| Hard | It breaches DSCR or leverage (facility covenant or mandate) | Refused for everyone |
| Hard | It takes projected cash below the reserve where it was not, or deeper | Refused for everyone |
| Hard | `allow_new_borrowing` is false | Refused for everyone |
| Autonomy ceiling | Effective annual cost above `max_apr_bp` | The agent may not do it alone: queued for the owner (Tier 2) |
| Never | Personal guarantee, collateral, equity, mandate change | Tier 3, refused for everyone |

Clean-down is a plan-level test (it is breached by not repaying, not by one draw); the router and the alerts test it.
The owner cannot waive a hard rule by approving; the owner changes the mandate instead. No code ever approves on the
owner's behalf.

| Rule | Status |
| --- | --- |
| Legs are judged in order, each on the books the legs before it leave (`app/funding/legs.py`, shared by the router and admission): a draw today on an open line becomes the lot it is, repaid by the engine on the first affordable receipt; every other leg stays an action. The router orders a plan's legs so that every prefix is admissible. | Done (3 Oct) |
| A plan that is admissible only as a whole, in no order, cannot run today: it is flagged `executable_now` false ("cannot run today"), not "needs the owner", because the owner cannot approve past a hard rule. | Done (3 Oct) |

## 4. Rates

| Name | Formula | Used for |
| --- | --- | --- |
| Tariff (menu rate) | Line or loan: rate + upfront fee × 12 / term months. Invoice financing: rate + period fee × 365 / period. | Comparing sources on the menu; choosing the marginal source |
| Effective annual cost of an advance | (interest + period fees + upfront fee) / advance × 365 / days from cash landing to the due day | The `max_apr_bp` ceiling; what the owner is shown before approving |
| Early-payment rate | d / (1 − d) × 365 / days early | Comparing a discount with borrowing |
| Break-even discount | d* = c / (1 + c), c = all charges of borrowing the same net cash for the same days / principal; the upfront fee counts once | ADR-0007 test 1  |
| Fixed-sum discount rate | the sum / the face of the portion it is given on, kept as an exact fraction (¥8,000 on ¥420,000 is 2/105, 1.9048%) | The same checks as a stated rate: the mandate's discount cap (¥6,300.00 on ¥420,000 is exactly the 1.50% cap, one fen more is above it), the break-even, the rate ceiling and the comparison with the plan |

`max_apr_bp` is a ceiling on what the agent may borrow alone, tested on the effective annual cost. It is not a
prohibition. Whole-period billing makes a short advance expensive: ¥200,000 for 10 days costs ¥1,782.19, 32.5% a
year, so the owner must approve it.

## 5. Debt and ratios

| Rule | Status |
| --- | --- |
| Debt = `state.debts` principal + every facility's drawn balance that counts in leverage. The two never describe the same loan. | Done (fixture convention) |
| DSCR = monthly EBITDA / monthly debt service. Service = fixed service on existing debt + interest and fees as posted + amortising principal + bullet term loans on a level basis (ADR-0008). The level basis is an owner's reserve-coverage reading, not a lender's contractual definition (U-004). | Done; label open |
| Leverage = month-end debt / (12 × monthly EBITDA), on drawn balances only (a draw counts from its request day; a committed line's undrawn room is not debt). One function, `covenants.ratios_for`, on a projection's month points: the verifier reads the projection with the offer and its committed plan, capex each structure's own projection, the borrower file and the chat the same month points. A figure needed before a plan exists is a labelled estimate. Undefined when EBITDA ≤ 0: with debt it is a breach, never an exception. Golden figures on this definition: EX01 after the extension 1.47× (was 1.72× with the line limit counted), base 1.35× (was 1.53×); capex 1.90×, and 2.10× with the extension (was 2.08× and 2.28×). | DONE (3 Oct; gate G2; `tests/covenants/test_one_leverage_property.py`) |
| Every drawn balance has a dated lot (request day, landing day, principal, maturity). The projection never invents day 0. | Done (3 Oct) |
| Existing debt (`state.debts`) is cash. One schedule (`app/financial/debts.py`): from `next_payment_day`, every `payment_every_days`, on each payment day on or after today while principal is left, interest = principal × `rate_bp` × days since the last payment / 365 and principal = min(principal, service − interest); the last payment clears the principal. The projection and the clock post the same payments (cash down, debt and leverage debt down by the principal); nothing is posted before today. The ratio keeps the fixed monthly service for the months the schedule covers, zero once the principal is cleared. The golden D-EQUIP's 0% rate is a fixture assumption. | Done (3 Oct) |

## 6. Forward concessions

| Rule | Status |
| --- | --- |
| Valuation window W = [today, today + H), H = `forward_concession_horizon_days`. A cost counts when the invoice's issue day is in W and inside the frozen scope. | Done (3 Oct) |
| A gain is dated like a cost: by the invoice's issue day in W. Only a FIRM gain offsets a cost. Window-edge convention: a gain on an invoice issued inside W counts even if its cash arrives just after W, exactly as that invoice's extension cost counts. (A stricter cash-date rule for gains was tried on 3 Oct and withdrawn: it counted 13 cost invoices against 11 gain invoices of the same agreement.) | Done (3 Oct) |
| The same invoices give the same value whatever the wording (bounded or perpetual). | Done (3 Oct) |
| Terms extension of Δ days on face F: F × Δ × r / 365 per invoice, r = the marginal tariff. Price change p: p × F per invoice. Summed over the dated invoices, posted once. | Done (3 Oct) |
| Pro forma of an extension: extra debt = F × Δ / invoice interval; monthly service = that × r / 12. | Done (3 Oct) |

Counting dated invoices means a 365-day window holds 12 or 13 monthly invoices depending on the issue dates. The
golden books (first issue on day 2) hold 13, so the 12-month extension cost moves from ¥22,455.62 to ¥24,326.92.
Derivation: `docs/research/concession-valuation-handcalc-2026-10-03.md`.

## 7. Consent

| Rule | Status |
| --- | --- |
| Free text executes a financial operation only when the whole message matches a closed affirmative command. Negation, a question, a condition, a future time, a foreign currency or an unreadable amount never execute. | Done (3 Oct) |
| An approval id is approved or rejected only by an exact decision. Anything else that mentions it changes nothing. | Done (3 Oct) |
| "Go ahead" authorises the exact operations shown (kind, facility, invoice, amount) with the quoted cost as a ceiling. If they are no longer admissible at that cost, a new proposal is shown and nothing runs. | Done (3 Oct) |
| A counterparty is who its channel key says it is. An unauthenticated message can be read and evaluated, never agreed. | Done (3 Oct) |
| A past-tense statement is not a repayment, and a tag question never confirms a plan. | Done (3 Oct; `tests/nl/test_consent.py`) |
| The closed grammar abstains rather than guess. An offer abstains, with a reason the buyer is asked about, when it carries an unusual number form (a decimal comma such as 0,5%, mixed separators), a per-day rate, a discount code (2/10 net 30), a currency other than yuan, a partial amount, another party's invoice, a hedge ("maybe", "perhaps", 可能), a payment after the due date, or a rider (a price freeze). Nothing is countered, committed or queued from it. | Done (3 Oct; `tests/compiler/test_boundary_abstentions.py`, `tests/nl/test_boundary_abstentions.py`) |
| "Pay early, 0.3% off" with one open invoice binds to that invoice (the only reading), and the acceptance is queued for the owner; it is never run at Tier 1. | Done (3 Oct; certification items MM-026 and MM-027) |

## 7a. Counters

| Rule | Status |
| --- | --- |
| Every counter a verdict offers passes its own re-check: evaluated as an offer on the same books it was built from (as the commit hook re-evaluates a commitment), it gives ACCEPT or NEEDS_OWNER_APPROVAL, never REJECT, with no covenant or rate-ceiling breach. This is the curable reading: a reserve shortfall the counter causes is allowed when an admissible committed plan cures it, and a cure marked "cannot run today" may finance only invoices issued by the first day of the shortfall. A counter that fails is dropped and the summary says in one sentence why. EX01's Option B is therefore 55-day terms at 0.30% (60 days fails). | Done (3 Oct) |
| A buyer with an open invoice past its due day on current books cannot be accepted without the owner; the verdict names the invoice and the days. | Done (3 Oct) |

## 8. Capex and the borrower file

Capex is a screen, not an investment recommendation: project NPV and payback on the owner's own estimates, and
for each real facility at its real tenor, total financing charges (interest + fees, not discounted), liquidity on
the daily projection and covenants. No financing winner when the project is not worth doing. The borrower file
states the use of proceeds and deducts the purchase. Evaluating capex writes nothing; applying is a separate owner
step (`POST /capex/apply`, bound to the evaluation's state version). The borrower file is a read-only owner action
with provenance (generation day, versions, evidence hash). (Done 3 Oct.)

## 9. Concurrency

One organisation's books are one serialisation boundary, and the database enforces it, not a process lock
(`docs/research/concurrency-certification-2026-10-03.md`).

| Rule | Status |
| --- | --- |
| One operation is one unit of work: every executor entry point that decides something (`execute`, `decide`, `revoke_commitment`, `reset_circuit`, `propose_commitment`) and the clock's advance runs in one store transaction and appends exactly one log entry. | Done (3 Oct) |
| Compare-and-swap on the log head: a unit that began before another writer committed cannot append, and keeps nothing. | Done (3 Oct) |
| Compare-and-swap on the state: `put_state(state, expected_version=v)` refuses unless the stored state is version `v`; the executor and the clock write every state this way. | Done (3 Oct) |
| A unit that lost a race runs again on the books as they now are, at most 8 times (the executor and the clock), so the second of two draws on the last room is refused for room and the second of two identical bank events is a DUPLICATE. No financial rule, admission check or tier changed. | Done (3 Oct) |
| A write conflict that survives the retries answers HTTP 409 with a retry hint in every writing route, never a 500. | Done (3 Oct; `tests/api/test_write_conflict_409.py`, `tests/clock/test_clock_conflict.py`) |
| File SQLite takes the write lock when a unit begins (`BEGIN IMMEDIATE`); the compare-and-swap is the backstop and the only guard on PostgreSQL. | Done on SQLite; PostgreSQL not run (needs a URL) |
| Proof: eight invariants with two spawned processes on three engines, then the committed actions replayed serially must give byte-identical books. | SQLite proven (`tests/concurrency/test_invariants.py`); PostgreSQL UNVERIFIED |
