# Dry pilot report, 9 October 2026 (map #58, ticket #62)

**This is a rehearsal of the instruments and a robustness fixture. No gate is read from it.** The runbook's own sentence
(section 8): "No gate is read from a dry pilot. The books are not an owner's, the decisions are written or role-played,
and so no figure in a dry pilot counts toward any threshold in section 7." The gates in `docs/STRATEGY_RESEARCH.md`
section I are all stated over real things (for the envelope "on at least five of the first ten real offers the owner's
chosen response is inside the zone or is one of the packages"; for the curve "three of three owners in the comprehension
test"), and nothing below is one of those.

Books: `fixtures/scenarios/public_sme.json` (a ¥105m Guangdong electronics manufacturer, built from one public filing, see
`fixtures/scenarios/public_sme.SOURCES.md`), mandate `public_sme.mandate.json`, branch `feat/pilot-dry-run` on `dev` at 024ae1e
(the curve-ceiling fix is in). Two runs of eight weeks, in process, no server: `dry-a` (`--role-play auto`, exports in
`docs/pilot/dry-a/`) and `dry-b` (`--decisions docs/pilot/dry-a/decisions.yaml`, exports in `docs/pilot/dry-a-decisions/`).
Both exit 0, no route errored, no refusal (a 422) was returned, the operations log holds the 8 clock entries and nothing
else, the hash chain verifies. The two runs exported the same answers to the last field except `computed_in_seconds`.

## 1. What the instrument is, and the one thing that decides how to read the weeks

The runner advances the clock seven days and reads. The clock posts scheduled flows (payroll, tax, suppliers, loan
interest) and issues recurring invoices; **it never lands a receipt and the runner never posts one** (a real owner updates the
books each week, runbook section 4 step 1). So no buyer ever pays: from week 4 cash is below zero and by week 8 it is
-¥9,565,573.64, with 16 open invoices (8 at the start) and none settled. Week 1 is the public-record SME as the filing shows it,
seven days on. Weeks 2 to 8 are the stress case of an owner who does nothing while no customer pays, not a firm's life. The
role-played decisions do not change the books either, which is why the two runs match. Every "wrong" reading below
should be read with that in mind; findings 2 and 3 are real all the same because FLOW should say something sensible there.

## 2. The weeks

Day 0 is 1 January 2026; week N is day 7N. Cash is the books' opening cash for that day. "Plan" is the router's committed
funding plan, which the curve, the ranking and the envelope's cost line all read.

**Week 1 (day 7).** Changed: the clock moved seven days; the invoice RI:BUYER-A:5 was issued; no flow posted; cash ¥7,634,503.82.
The reserve breach is still ahead (day 14); the plan is a ¥4,282,116.74 draw on the credit line from day 7, repaid by the ¥10.5m
receipt due on day 25, cost ¥5,631.28. The curve is the fixture's day-0 reading seven days later (24 days became 17).
- Curve: "Cash in the next 17 days saves you ¥13.15 of funding cost per ¥10,000 (0.13%); after that, earlier cash saves nothing."
- Worth, top row: RCV-F1, Other buyers (aggregate), "Call Other buyers (aggregate) today for the ¥7,500,000.00: it saves you ¥5,631.28 and is the only free action." Then Buyer B ¥3,945.21 (escalate), Buyer D ¥3,352.46 (call); six rows save nothing.
- Envelope primaries: A "up to 100-day terms (the most FLOW checks), or early payment at up to 0.10% on ¥5,397,202.57; a rebate up to 1.50%". B "up to 90-day terms ...; early payment at up to 0.10% on ¥2,401,267.37; a rebate up to 2.00%" (its reason says the ¥3,000,000.00 is 42 days past due, so a deal needs approval). C "up to 100-day terms ...; early payment 0.10% on ¥3,384,660.49; a rebate up to 2.00%". D "Nothing beyond today's terms passes FLOW's checks." E "early payment at up to 0.10% on ¥2,305,982.09". Other buyers "up to 90-day terms ...; early payment 0.05% on ¥10,522,567.67; a rebate up to 0.70%".
- Runtime: curve 1.9 s, worth 11.4 s, envelopes 17.8 / 21.5 / 21.3 / 0.0 / 1.2 / 19.6 s; the week 94.7 s.

**Week 2 (day 14).** Changed: two invoices issued; the day-9 supplier payment posted (-¥2,598,059.96); cash ¥5,036,443.86. The breach is now
today, the credit line takes two days to land, and the router has **no committed plan** (the alert says so): plan cost 0. That one
change turns the curve flat, every worth row to "saves nothing" and the envelope's cost line to ¥0.00 (finding 2).
- Curve: "Earlier cash saves you nothing today." Worth top: "Escalate with Other buyers (aggregate): the ¥7,500,000.00 is 34 days overdue." (no saving).
- Envelopes: early-payment ceilings rise (A 0.15%, C 0.20%, E 0.45%), the rest as week 1.
- Runtime: curve 3.2 s, worth 8.4 s, envelopes 63.5 / 45.8 / 49.7 / 0.0 / 3.6 / 68.4 s; the week 242.6 s (the slowest).

**Week 3 (day 21).** Changed: one invoice issued; payroll, tax and the first loan interest (¥87,337) posted; cash ¥1,960,373.21 (below the ¥3,644,429.99 floor).
- Curve: "Earlier cash saves you nothing today." Worth top: "Escalate with Other buyers (aggregate): the ¥7,500,000.00 is 41 days overdue."
- Envelopes: A 0.10%, B 0.05%, C 0.15%, E 0.40%; Other buyers lose the early-payment offer ("up to 90-day terms; a rebate up to 0.70%").
- Runtime: curve 3.5 s, worth 10.0 s, envelopes 78.5 / 55.4 / 54.8 / 0.0 / 4.9 / 41.2 s; 248.3 s.

**Week 4 (day 28).** Changed: supplier and rent posted (-¥3,253,756.28); cash -¥1,293,383.07. The ¥10.5m aggregate invoice (due day 25) is now 3 days past due and
still counted as unpaid. A reserve alert reads "No committed facility can cure it".
- Curve: "Earlier cash saves you nothing today." Worth top: "Escalate with Buyer B: the ¥3,000,000.00 is 63 days overdue."
- Envelopes: A "a rebate up to 1.50%; not 95 days"; B "a rebate up to 2.00%; not 65 days"; C "up to 100-day terms ...; a rebate up to 2.00%"; D, E "Nothing beyond today's terms passes FLOW's checks."; Other buyers "a rebate up to 0.70%; not 80 days". The terms ceilings fell with the cash.
- Runtime: curve 4.6 s, worth 12.4 s, envelopes 29.2 / 45.8 / 27.4 / 0.0 / 4.1 / 32.9 s; 156.3 s.

**Week 5 (day 35).** Changed: the clock only (nothing posts or is issued); cash unchanged at -¥1,293,383.07; the lateness counters ran on a week.
- Curve: same sentence. Worth top: "Escalate with Buyer B: the ¥3,000,000.00 is 70 days overdue." Envelope C drops its terms offer ("a rebate up to 2.00%; not 95 days"); the others as week 4.
- Runtime: curve 3.7 s, worth 16.0 s, envelopes 30.8 / 57.1 / 26.9 / 0.0 / 4.7 / 37.7 s; 176.9 s.

**Week 6 (day 42).** Changed: two invoices issued; the day-40 supplier payment posted; cash -¥3,891,443.03.
- Same curve sentence; worth top "Escalate with Buyer B: the ¥3,000,000.00 is 77 days overdue."; envelopes as week 5.
- Runtime: curve 3.7 s, worth 16.9 s, envelopes 37.4 / 58.8 / 28.0 / 0.0 / 9.7 / 41.8 s; 196.3 s.

**Week 7 (day 49).** Changed: two invoices issued; payroll and tax posted; cash -¥6,880,176.70.
- Same curve sentence; worth top "... Buyer B ... 84 days overdue."; envelopes as week 5.
- Runtime: curve 3.7 s, worth 20.8 s, envelopes 36.5 / 61.1 / 31.7 / 0.0 / 9.3 / 42.4 s; 205.7 s.

**Week 8 (day 56).** Changed: loan interest and a supplier payment posted; cash -¥9,565,573.64; the reserve gap peaks at ¥18,426,380.32 on day 83 and lasts to day 173.
- Same curve sentence; worth top "Escalate with Buyer B: the ¥3,000,000.00 is 91 days overdue."; envelopes as week 5.
- Runtime: curve 4.0 s, worth 22.4 s, envelopes 40.7 / 67.9 / 34.9 / 0.0 / 10.2 / 42.6 s; 222.8 s.

Breach episodes over the eight weeks: ahead from week 1 (day 14); today from week 2; a real shortfall from week 4 onward and never cured, because no
receipt lands. `dry-b`'s runtimes are within 11% of these (its weeks total 24.1 minutes, `dry-a` 25.7). The machine was shared (load average 2.6 to 4.4 while
`dry-a` ran), so seconds are indicative, not a benchmark.

## 3. Findings

Nothing errored. Business-language check: no displayed sentence (primary, reason, cost line, curve sentence, worth text,
action sentence) holds a code, a tier, a day number or an engine word at level 1; the only capitalised word is the brand.
What did go wrong:

**1. Envelope and worth answers are far over 10 seconds (every week; routes `/buyers/{id}/envelope` and `/receivables/worth`).** Each of the
four buyers with a terms lever (A, B, C and the aggregate) took 17.8 to 78.5 s (median 41 s over the 32 reads) in all 8 weeks, the worst
in weeks 2 and 3; the week's six envelopes, with worth and curve, need 94 to 248 s. Worth took 11.4 s in week 1 and rose to 22.4 s by week 8 as open
invoices went from 9 to 16; it was over 10 s in 6 of 8 weeks. The curve stayed under 5 s. The runbook already warns of "about 44 seconds" per envelope,
and ticket #62's golden books read 16.4 s, so the public-record books are worse than both. An owner would not wait for the Deals page.
Needs a ticket: "Envelope and worth answers take 17 to 78 s and 8 to 22 s on the public-record SME (over the 10 s mark every week)".

**2. When no committed plan exists, three routes say "saves nothing" and "costs ¥0.00" (weeks 2 to 8; curve, worth, envelope).** From week 2 the
router has no admissible plan (the breach starts today and the credit line lands two days later), so the plan's cost is read as zero. The curve
then says "Earlier cash saves you nothing today." when cash is -¥9.6m by week 8; every worth row reads "Saves nothing extra now", including "Escalate with Buyer B: the
¥3,000,000.00 is 91 days overdue"; every envelope's cost line reads "Without a deal your current funding plan costs ¥0.00." The alerts on the same books
read CRITICAL, "No committed facility can cure it". Week 1 agrees across the routes at ¥5,631.28; from week 2 the routes contradict the alert, and a
careful owner reading "saves nothing" would conclude the opposite of the truth: that cash does not matter. Needs a ticket: "When no committed plan restores the
reserve, the curve, the worth ranking and the envelope's cost line say so instead of reading as 'saves nothing' / '¥0.00'".

**3. The envelope keeps offering concessions to an owner already below the floor (weeks 2 to 8, route envelope; a consequence of 2).** In weeks 2 and 3 buyers
A and C are told "You can live with: up to 100-day terms" with the credit line unable to cover day 14; from week 4 "a rebate up to 1.50%" and "2.00%" are offered while cash
is negative. The reasons are right (they call out the past-due invoice and the terms steps that fail), but the headline sentence is what is read. A
sentence that would mislead this owner. Covered by the ticket of finding 2 (the envelope tests against a plan that cannot be built); not a separate ticket.

**4. The ranking's order among rows that save nothing (weeks 2 to 8, route worth).** With every saving at zero the order is a tie-break. In weeks 2 and 3 rows
"Wait: ... beyond the shortfall" (a ¥10.5m invoice due in 11 days) rank above Buyer B's invoice, 49 days late, and Buyer D's, 24 days late;
from week 4 the oldest debts head the list. The top action flips from the 34-day-late aggregate invoice to Buyer B in week 4 with no figure to say why. Falls under
the ticket of finding 2, which should say what orders the list when nothing is saved; no separate ticket.

**5. The same answer hashes differently on every read (all weeks, all routes).** The exported JSON carries `computed_in_seconds`, so the 64 files of `dry-a` and the 64 of
`dry-b` are identical except that field and have 64 different sha256 values. The journal's `snapshot_hash` therefore proves which file was shown, but two reads of
unchanged books cannot be shown to be the same answer. Needs a (low) ticket: "Exports carry `computed_in_seconds`, which makes snapshot_hash differ between
identical answers (hash the answer without timings, or export them beside it)".

**6. The instrument itself (not FLOW).** The runner lands no receipts and records no decision into the books (section 1), so a role-played eight weeks cannot
test whether FLOW's advice would have cured anything. Needs a ticket: "Dry-pilot runner: an optional weekly receipts file that lands payments (settles invoices, moves cash) so the books follow the
role-played decisions". Minor: `tests/pilot/test_journal_file.py` asserts `docs/pilot/dry-a/journal.jsonl` does not exist, so the committed journal copies are named `journal-entries.jsonl`.

What worked: the curve fix (ticket #63) holds, with no refusal in 16 curve reads and week 1 reproducing the fixture's sentence moved seven days; the router, the worth ranking and the envelopes' cost line in week 1 agree
on one figure (¥5,631.28); `--journal-file`, the validation, and the operations count behaved as designed.

## 4. What the answers would have told this owner

**Envelope.** In week 1 it is an owner-friendly reading: longer terms are not the lever (the biggest buyers can be given up to 100 days without breaking a limit, but the owner would not),
early payment is worth at most 0.05% to 0.10% because the credit line costs 3%, and the one-sentence reasons name the two buyers who are past due. Over the following weeks the early-payment
ceiling moves from 0.10% to 0.45% (Buyer E) and back to nothing, and the terms offers disappear (A, B and the aggregate from week 4, C from week 5) as the cash runs out. A real owner would find the
week-1 answer useful and the later ones confusing, for the reasons in findings 2 and 3, and each answer took long enough to be abandoned.

**Worth ranking.** Week 1 is the strongest answer of the pilot: chase the ¥7.5m group first (¥5,631.28, the whole cost of the plan), then Buyer B and Buyer D. It names the free action and
the money. After that the list is a chase order by lateness with no money attached, and its top moves from the aggregate buyers to Buyer B in week 4. For this owner the
week-1 order equals the overdue-amount order (so there is nothing here for the collections gate); in weeks 2 to 8 the two differ, but only by the tie-break among rows that save nothing, which is not evidence of anything.

**Curve.** One useful sentence in eight weeks (week 1: cash within 17 days is worth ¥13.15 per ¥10,000, i.e. nearly nothing at a 3% line) and seven weeks of "Earlier cash saves you nothing today."
which is false in spirit while the owner is overdrawn (finding 2). Honest reading: on cheap bank money the curve is small and short-lived, which these books show by design; the owner's cash question on these books is about the breach, which the curve cannot see.

## 5. The journal and the decisions

`dry-a` (`--role-play auto`): 64 entries, all `followed` (8 curve, 8 worth, 48 envelope; owner_did "role-play: followed FLOW's answer"). This exercises the pipeline only and says nothing about any owner.
`dry-b` (the finance director's written decisions): 25 entries (5 curve, 8 worth, 12 envelope): 7 followed, 8 partly, 6 ignored, 4 not applicable. Worth: 5 followed, 2 partly, 1 ignored (weeks 3, 5 and 7
departed from FLOW's order for relationship and size reasons). Envelope: 5 partly (early payment taken at a lower rate than the ceiling, never the terms), 3 ignored (all the longer-terms offers),
2 followed, 2 not applicable. Curve: never followed (2 not applicable, 2 ignored, 1 partly). The role-played director follows the chase list and refuses what FLOW calls acceptable on terms. These are
written decisions, not behaviour; against FLOW's all-followed baseline, the useful signal is only that the pipeline records `partly` and `ignored` with the owner's words and the hash of the file shown.

## 6. Limitations the fixture carries (restated)

1. **Bills as cash.** The filing's suppliers are paid largely with endorsed bank acceptance bills; the books treat every supplier payment as cash (¥2,598,059.96 per payment), so outflows are higher than the company's real cash outflows.
2. **Calibrated terms.** The filing states no credit terms, loan maturities, payment days or facility terms; the terms (60/90/76 days), issue days, the invoice-financing and guaranteed-loan options, the floor and the caps are calibrated (SOURCES.md section 10).
Add the runner's own: no receipt ever lands (section 1).

## 7. What a real pilot would do differently

- The owner updates the books every week (cash, receipts, new invoices), so breaches are cured or not by what the owner did; nothing drifts into a case no owner would reach.
- The owner states what they did before FLOW's order is shown; a dry run reads decisions the day after FLOW spoke.
- The first read is day 0, not day 7; the envelope is read per buyer with an offer on the table, not for all six buyers weekly.
- The envelope and worth reads must come inside 10 s (finding 1) before an owner is asked to wait for them; otherwise screenshots and the comprehension test will be taken on pages that are still loading.
- A comprehension test of the curve's sentence with three owners, which a dry pilot cannot supply; and a cold-user walk of the alerts page against the "saves nothing" sentences (finding 2).
- Read the weeks against the gates only after the report names which gate each figure feeds; this rehearsal feeds none.
