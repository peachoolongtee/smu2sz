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
| `state.cash_fen` is the bank balance at the start of today. Days before `as_of_day` are closed: nothing may post there. | Open for carried debt (A08) |
| Cash exists only after the event that creates it. Funding requested on day d on a facility with lead time L becomes cash on day d + L. Until then it is "requested", not cash. | Projection: yes. Executor: open (A08) |
| A receipt is recorded only from the bank feed or the owner. The clock never assumes one arrived. | Done |
| Interest on a draw or advance runs from the day the cash lands. | Projection: yes. Executor: open (A08) |
| A projected discretionary repayment (a credit line) is an assumption, labelled as such. It happens only when an operation executes it. Contractual instalments and maturities are posted by the simulated bank as they fall due. | Open (A08) |
| The reserve (`min_cash_fen`) is tested on each day's closing balance of the conservative projection. | Done |

## 2. Receivables

| Rule | Status |
| --- | --- |
| An invoice has one contractual face and one due day, read by every module. Accepted terms or price changes are written onto the invoice once: at acceptance for an issued invoice, at issue for a future one. | Open (A06) |
| A receipt reduces the contractual face. Nothing is ever recomputed on the remaining balance. | Open (A06) |
| The scope of a finite agreement ("this invoice", "the next 3 invoices", "until day D") is fixed at acceptance as a list of invoice ids or an issue-day range. Settling an invoice never moves the scope to another invoice. A finite agreement ends when its last invoice is issued. | Open (A07) |
| An invoice can be financed only while it is open, confirmed, not under an early-payment agreement, and only up to the advance rate of its **outstanding** face, with the cash landing before its due day. | Done (3 Oct) |
| An early-payment discount is earned only by a receipt on or before the promised day. A later receipt of the same amount is a plain receipt; the difference stays due. | Done (3 Oct) |

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

## 4. Rates

| Name | Formula | Used for |
| --- | --- | --- |
| Tariff (menu rate) | Line or loan: rate + upfront fee × 12 / term months. Invoice financing: rate + period fee × 365 / period. | Comparing sources on the menu; choosing the marginal source |
| Effective annual cost of an advance | (interest + period fees + upfront fee) / advance × 365 / days from cash landing to the due day | The `max_apr_bp` ceiling; what the owner is shown before approving |
| Early-payment rate | d / (1 − d) × 365 / days early | Comparing a discount with borrowing |
| Break-even discount | d* = c / (1 + c), c = all charges of borrowing the same net cash for the same days / principal; the upfront fee counts once | ADR-0007 test 1 (upfront-fee repetition: open, F-FIN-09) |

`max_apr_bp` is a ceiling on what the agent may borrow alone, tested on the effective annual cost. It is not a
prohibition. Whole-period billing makes a short advance expensive: ¥200,000 for 10 days costs ¥1,782.19, 32.5% a
year, so the owner must approve it.

## 5. Debt and ratios

| Rule | Status |
| --- | --- |
| Debt = `state.debts` principal + every facility's drawn balance that counts in leverage. The two never describe the same loan. | Done (fixture convention) |
| DSCR = monthly EBITDA / monthly debt service. Service = fixed service on existing debt + interest and fees as posted + amortising principal + bullet term loans on a level basis (ADR-0008). The level basis is an owner's reserve-coverage reading, not a lender's contractual definition (U-004). | Done; label open |
| Leverage = month-end debt / (12 × monthly EBITDA). Undefined when EBITDA ≤ 0: with debt it is a breach, never an exception. | Capex path open (F-FIN-12) |
| Every drawn balance has a dated lot (request day, landing day, principal, maturity). The projection never invents day 0. | Open (A08) |

## 6. Forward concessions

| Rule | Status |
| --- | --- |
| Valuation window W = [today, today + H), H = `forward_concession_horizon_days`. A cost counts when the invoice's issue day is in W and inside the frozen scope. | Open (A11) |
| A gain is dated like a cost: by the invoice's issue day in W. Only a FIRM gain offsets a cost. Window-edge convention: a gain on an invoice issued inside W counts even if its cash arrives just after W, exactly as that invoice's extension cost counts. (A stricter cash-date rule for gains was tried on 3 Oct and withdrawn: it counted 13 cost invoices against 11 gain invoices of the same agreement.) | Open (A11) |
| The same invoices give the same value whatever the wording (bounded or perpetual). | Open (A11) |
| Terms extension of Δ days on face F: F × Δ × r / 365 per invoice, r = the marginal tariff. Price change p: p × F per invoice. Summed over the dated invoices, posted once. | Open (A11) |
| Pro forma of an extension: extra debt = F × Δ / invoice interval; monthly service = that × r / 12. | Open (F-FIN-07) |

Counting dated invoices means a 365-day window holds 12 or 13 monthly invoices depending on the issue dates. The
golden books (first issue on day 2) hold 13, so the 12-month extension cost moves from ¥22,455.62 to ¥24,326.92.
Derivation: `docs/research/concession-valuation-handcalc-2026-10-03.md`.

## 7. Consent

| Rule | Status |
| --- | --- |
| Free text executes a financial operation only when the whole message matches a closed affirmative command. Negation, a question, a condition, a future time, a foreign currency or an unreadable amount never execute. | In progress (A01) |
| An approval id is approved or rejected only by an exact decision. Anything else that mentions it changes nothing. | In progress (A02) |
| "Go ahead" authorises the exact operations shown (kind, facility, invoice, amount) with the quoted cost as a ceiling. If they are no longer admissible at that cost, a new proposal is shown and nothing runs. | Open (A10) |
| A counterparty is who its channel key says it is. An unauthenticated message can be read and evaluated, never agreed. | In progress (A03) |

## 8. Capex and the borrower file

Capex is a screen, not an investment recommendation: project NPV and payback on the owner's own estimates, and
for each real facility at its real tenor, total financing charges (interest + fees, not discounted), liquidity on
the daily projection and covenants. No financing winner when the project is not worth doing. The borrower file
states the use of proceeds and deducts the purchase. (In progress, A12/A13.)
