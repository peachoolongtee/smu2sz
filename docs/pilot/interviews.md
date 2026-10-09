# The five interview sets, ready to use

For wayfinder map [#58](https://github.com/peachoolongtee/smu2sz/issues/58). The sets are `docs/STRATEGY_RESEARCH.md` section I,
"Interview question sets (from 02, actual behaviour, not "would you use")", **verbatim**. They run when no pilot SME is
reachable ("If no SME is reachable, the five interview sets below run first with the same thresholds read from the interviews'
'what did you do' answers"; section L: "run in the first fortnight"), or alongside the pilot to widen it.

## How to run them

- **Who.** One person per set (five sets, so at least five interviewees; two or more per set is better). Reach people who do
  the job today, not people who would like the tool. Not the pilot owners for the same set.
- **Actual behaviour, not opinion.** Ask for the last time. When an answer begins "usually" or "we would", ask "when was the
  last time that happened?" and write down that instance. Never ask "would you use this?". Never describe FLOW before the
  last question.
- **Order.** Ask in the order printed. Skip a question only if the interviewee already answered it; note which.
- **Recording.** Notes by hand, in the interviewee's words. No audio without their written agreement. Name, company, buyers and
  places are never written down: the record carries a label (`CFO-1`, `Sales-2`), a role, a company size band and a sector.
- **Length.** Forty minutes. Stop at the end of the list, not at the end of the hour.
- **Offers and receivables as numbers.** Wherever an answer is a count (deals open, receivables open, buyers with a regular
  invoice), write the number, not "several".

## The sets (verbatim)

### Set 1: SME owner

1. The last time a buyer asked for longer terms: who asked, how did you decide, how long did it take?
2. What did you check before saying yes, and where was it?
3. Have you discovered after signing that a deal made cash tight; what then?
4. When did you last call your bank RM, and what did you ask?
5. How much of your receivables sits with your largest buyer; do you know without looking?
6. Who may give a discount without asking you; is it written down?
7. When cash was tightest last year, what did you do first, second, third?
8. How many hours a week do you spend on getting paid?
9. Which buyers have you kept despite poor payment, and why?
10. What would have to be true for software to send a counter-offer in your name?

### Set 2: CFO (mid-market)

1. Your deal-approval process: thresholds, signers, turnaround.
2. Last quarter, how many deals did finance push back on, how many were overridden?
3. How do you cost payment terms in a deal today?
4. How often is the cash forecast refreshed, by whom, in what, and when did it last miss badly?
5. Facility utilisation now, and when did it last exceed your comfort?
6. Which covenants do you watch; how would you know a month early?
7. Who decides draw versus chase harder, on what evidence?
8. Credit policy on new buyers; last updated?
9. The one number you wish sales saw before quoting?
10. What has stopped you buying AR or treasury software?

### Set 3: Finance manager

1. The cash spreadsheet: tabs, refresh, editors.
2. When sales agrees terms, how and how late do you find out?
3. How do you compute the cost of an early-payment discount?
4. What does month-end reveal you wish you knew on day 5?
5. The last unplanned draw: cause, notice, cost.
6. Which supplier do you pay late when short, and how do you decide?
7. Which reports does the owner ask for, which by hand?
8. Which buyer's behaviour changed recently, how did you learn?
9. How do you track rebates and contingent concessions owed?
10. What breaks when you are on leave?

### Set 4: Credit controller / AR

1. Yesterday morning: which list, what order, why?
2. How many accounts touched, by which channel?
3. Which accounts are you told not to chase, by whom?
4. How do you know a buyer's risk changed?
5. A disputed invoice: how long to resolve, who?
6. How do you record a promise to pay; does the forecast use it?
7. Asked to chase harder because a facility was about to be drawn; how did you know?
8. What do you do with the aged-debtor report the system cannot?
9. What would make you trust a ranked list you did not build?
10. When did a chase damage a relationship?

### Set 5: Sales manager

1. A deal finance rejected or slowed in the last three months: what happened, what did the buyer do?
2. What discount or terms can you grant alone; how do you know?
3. When a buyer asks for 90 days, what do you say in the room and check afterwards?
4. How do you learn a customer pays late; does it change how you sell?
5. Who told you about the last credit-limit cut, and when?
6. Have you offered price instead of terms, or the reverse; how did you pick?
7. How are you paid: bookings, revenue, cash, margin?
8. How long do you wait for approval; what do you tell the buyer?
9. What would you want on your phone before a negotiation?
10. When did finance's "no" turn out right?

## The probes the gates need (added; not from section I)

The sets do not ask for three counts the gates read. Ask them at the end of the matching set, after its ten questions, so they
do not change the answers to the ten. They are additions made by this ticket and are marked so in the record.

| Asked of | Probe | Read by |
| --- | --- | --- |
| SME owner, Finance manager | "Of the buyers you invoice today, how many are invoiced on a regular rhythm, the same amount every month or so, and how many are one-off?" | Envelope gate (buyers with a recurring invoice) |
| SME owner, Credit controller | "Right now, how many invoices are open and unpaid, at the same time?" | Collections gate (open receivables at once) |
| SME owner, Sales manager | "At this moment, how many buyers are in the middle of asking you for different terms, a discount or a rebate?" | Portfolio gate (deals open at once) |

## What each gate reads from the interviews

The thresholds are section I's, quoted in `docs/pilot/RUNBOOK.md` section 7. With no pilot, each is read from the interviewees'
**actual** past behaviour, as below. A reading is a count over interviewees or over described instances; write both the count
and the instances. The interviews can **kill** a capability on their own; they can only **support** a pass, and the pilot or the
comprehension test is still needed to confirm it.

| Gate | Passes when (section I) | Killed when (section I) | Read from | How the interviews read it |
| --- | --- | --- | --- | --- |
| Envelope | on at least five of the first ten real offers the owner's chosen response is inside the zone or is one of the packages; at least half the pilot's buyers have a recurring invoice | chosen response outside the zone or packages ignored on more than half of the first ten offers; fewer than half the buyers have a recurring invoice | Set 1 Q1, Q2, Q3, Q6, Q10; Set 5 Q1, Q3, Q6, Q8; Set 3 Q2; Set 2 Q1-Q3; the recurring-invoice probe | Take the first ten **described** offers (a buyer asked for terms, a discount or a rebate) across all sets. For each, the response the person actually gave: was it package-shaped (a number of days, or a price, early-payment or rebate, in a combination), and did it stay inside what they themselves say they could afford (Set 1 Q3: a deal that later made cash tight is outside)? Pass reading: at least five of ten package-shaped and inside their own limit. Kill reading: more than half answered with a flat yes or no, a handshake, or a response they say afterwards was outside their limits. The recurring-invoice probe: count buyers, at least half regular. |
| Collections | the net-value order differs from the overdue-amount order and the chase order followed it (or they say it should have); at least one pilot has more than two open receivables at once | the orders coincide every week; no pilot has more than two open receivables | Set 4 Q1, Q7, Q8, Q9; Set 1 Q7, Q8; Set 3 Q6; the open-receivables probe | Q1 gives the order they really chase in. If every interviewee orders by amount or by age only, and none says a facility or a cash date has changed whom they call first, the orders coincide (kill reading). If at least one chases by something else (a drawdown date, a covenant date, a cash gap) and others say that is what they should do, the orders differ (pass reading). The probe: more than two open at once for at least one interviewee. |
| Cash price curve | three of three owners explain "0.89%" as what earlier cash is worth to them, not a rate charged | any owner reads it as a charged rate | The comprehension test, `docs/pilot/comprehension-test.md` | **Not read from the interviews.** Set 2 Q3 and Set 3 Q3 (how they cost terms and early-payment discounts today) are context: note whether they think in a rate or in a yuan saving. |
| Portfolio (VALIDATE FIRST) | two or more deals open at the same time in most pilot weeks | fewer than two simultaneous deals in most weeks | Set 5 Q1, Q3, Q8; Set 1 Q1; Set 2 Q2; the deals-open probe | Count interviewees who report two or more buyers asking at once in a normal week. "Most" is more than half the interviewees. The greedy-versus-enumeration clause needs no interview. |
| Stress-to-action, tripwires | the cold-user walk shows the alerts page does not already answer the question | it does | Set 2 Q4-Q6; Set 3 Q4, Q5; Set 4 Q7 | Listen for whether they already have an early warning that names the action (a covenant date, a draw notice). The decision itself is the cold-user walk's. |
| Conditional deals | a pilot owner asks for one unprompted | nobody does | Set 5 Q3, Q6; Set 1 Q1; Set 2 Q9 | Count interviewees who describe, **before FLOW is mentioned**, an agreement whose terms depend on a later condition (a rebate if volume is met, terms if the invoice is paid early). |
| Controlled action (post-pilot) | the pilot's gates | not asked | Set 1 Q10 | Not a gate. Record the answer: it says what would have to be true before FLOW sends anything in the owner's name. |

## The record, one block per interview

Copy this block once per interview into `docs/pilot/interviews/<label>.md` (anonymised, no names).

```
Label: ______   Set (1-5): ____   Date: ______   Interviewer: ______
Role, company size band (staff), sector, region (province only): ______
Agreed that the notes may be kept: yes / no

Answers, verbatim where short, one line each (Q1 to Q10):
 1. 
 ...
Probe(s) asked (added by ticket #60):  ______ -> count: ____

Described offers (for the envelope reading), each as: what was asked / what they did / inside their own limits?
 - 
Chase order they described (Set 4 Q1) and what decides it: ______
Open at once (receivables / deals / buyers invoiced regularly of total): ____ / ____ / ____ of ____
Unprompted mention of a conditional deal (their words): ______
Anything that surprised the interviewer: ______
```

## The roll-up, after all five sets

| Gate | Count read | Instances (labels) | Reading (pass / kill / not read) |
| --- | --- | --- | --- |
| Envelope: described offers package-shaped and inside the interviewee's limits | ____ of ____ (first ten) | | |
| Envelope: buyers with a regular invoice | ____ of ____ | | |
| Collections: interviewees whose real order differs from amount or age order | ____ of ____ | | |
| Collections: most open receivables at once | ____ | | |
| Portfolio: interviewees with two or more deals open at once | ____ of ____ | | |
| Conditional deals: unprompted mentions | ____ | | |
| Alerts already answer the stress question | ____ of ____ | | |
