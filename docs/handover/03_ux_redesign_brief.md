# Owner's brief 3: UI/UX audit and redesign (verbatim, 5 Oct 2026)

Given with the design reference `docs/handover/03_ux_reference_dashboard.webp` (a clean SaaS dashboard: top
navigation with a few sections, KPI tiles with sparklines and a period comparison, one line chart with a tooltip and
series toggles, a costs-by-category list, a filterable table with search and pagination, one primary button,
green-on-white). The owner's words: "following the design example provided".

```text
You are the PRINCIPAL PRODUCT DESIGNER, UX ARCHITECT, AND FRONTEND LEAD for TermsLedger.

Your task is to perform a ruthless end-to-end UI/UX audit of the actual application, then redesign and improve it.

This is NOT primarily a visual-polish task.

The current problem is INFORMATION ARCHITECTURE.

The product has accumulated many technically useful features, but the interface now exposes too much complexity at once. It feels like:

- a product dashboard;
- an engineering demo;
- an audit console;
- a financial model;
- a security showcase;
- and an owner operating screen

all blended together.

The result is overwhelming.

A normal SME owner or finance manager can open the app and have no idea:

- what matters;
- what is urgent;
- what they should do;
- what will happen next;
- which numbers they actually need to understand.

I want you to fix that.

You have authority to disagree with the current UI, navigation, information hierarchy and feature placement.

Do NOT preserve existing screens merely because they already exist.

Delete, merge, hide, move, simplify or redesign components wherever doing so produces a better product.

==================================================
1. THE CORE USER PROBLEM
==================================================

When the BUSINESS OWNER opens TermsLedger, the interface should answer these questions almost immediately:

1. AM I GOING TO RUN OUT OF MONEY?

In practical terms:

- Is cash projected to fall below my safe reserve?
- When?
- By how much?
- How certain is this?
- What changed?

2. WHAT SHOULD I DO?

Show the best actionable options.

For example:

- collect a receivable earlier;
- draw an existing credit line;
- finance an invoice;
- reject/counter a buyer request;
- wait;
- repay funding;
- approve an exceptional action.

Do not make the user reconstruct this from ten charts.

3. HOW MUCH WILL IT COST ME?

For every meaningful recommendation:

- amount raised / protected;
- cost in currency;
- effective rate where useful;
- duration;
- consequences;
- why this option beats alternatives.

These three questions should define the homepage hierarchy.

If you believe there are other questions a finance owner must answer immediately, identify them and justify them.

Possible examples:

- What changed since yesterday?
- What needs my approval?
- Who has not paid me?
- What commitment is consuming my liquidity?
- What happens if I do nothing?

Do not add questions merely because data exists.

==================================================
2. TWO COMPLETELY DIFFERENT MODES
==================================================

The current interface appears to mix DEMO functionality with the REAL BUSINESS OWNER workflow.

Separate them clearly.

I want at minimum:

BUSINESS
DEMO

as clearly distinct top-level modes/tabs/areas.

They should not feel like the same screen with slightly different controls.

--------------------------------------------------
BUSINESS MODE
--------------------------------------------------

This should behave like a real financial operating product.

It should be calm.

Minimal.

Decision-oriented.

No unnecessary hackathon narration.

No test controls.

No developer-looking information unless intentionally opened.

No artificial walkthrough stepper dominating the experience.

The owner should primarily see:

financial health
urgent decisions
recommended actions
approvals
meaningful changes.

--------------------------------------------------
DEMO MODE
--------------------------------------------------

This exists to help judges understand the full product.

It may include:

guided scenario progression
clock controls
scenario reset
buyer personalities
attack demonstrations
step-by-step explanation
evidence
security demonstrations
advanced feature navigation
before/after states.

Demo controls should NEVER pollute the normal owner experience.

==================================================
3. FIRST: AUDIT THE ACTUAL APPLICATION
==================================================

Do not redesign from this prompt alone.

Inspect:

- actual frontend code;
- route structure;
- navigation;
- components;
- current design system;
- mobile/responsive behaviour;
- live API shape;
- empty states;
- error states;
- loading states;
- approval flow;
- offer flow;
- funding flow;
- alert flow;
- reconciliation;
- capex;
- borrower file;
- evidence/security screens;
- demo flow.

Run the application.

Use the real UI.

Click through it as:

A. SME owner
B. CFO / finance manager
C. first-time user
D. hackathon judge
E. person who did not build the product.

Do not assume a screen makes sense because the code is technically organized.

==================================================
4. AUDIT EVERY SCREEN
==================================================

For every page ask:

WHAT QUESTION IS THIS PAGE ANSWERING?

If the answer is unclear, the page likely needs redesigning.

Also ask:

What is the primary action?

What is the most important number?

What information can be hidden?

What information can be moved into details?

What is duplicated elsewhere?

What terminology requires explanation?

What information is useful only to developers?

What information is useful only to a judge?

What information is useful only after the user asks for it?

Could this page disappear entirely?

Could it become a drawer/modal/detail view?

Could it be combined with another page?

Is the user expected to understand an internal system concept that should
instead be translated into business language?

==================================================
5. USE PROGRESSIVE DISCLOSURE AGGRESSIVELY
==================================================

TermsLedger is financially complex.

The UI should NOT expose that complexity by default.

Use this pattern:

LEVEL 1
What is happening?

LEVEL 2
What should I do?

LEVEL 3
Why?

LEVEL 4
Show me the calculation / evidence.

Example:

BAD:

Reserve floor
Forward concession exposure
DSCR
Leverage
Funding trajectory
Invoice finance APR
Commitment lifecycle
Facility availability

all displayed simultaneously.

BETTER:

"CASH RISK IN 9 DAYS"

You are projected to fall
¥105,000 below your safe cash level.

[Fix this]

Then:

Recommended:
Finance ¥200,000 from Invoice RCV-B

Cost:
¥1,782

Funds available:
Day 37

[See alternatives]

Then only if requested:

Why?
Calculations
Rates
Covenants
Cash trajectory
Evidence.

The engine may be complicated.

The experience should not be.

==================================================
6. REDESIGN THE BUSINESS HOME
==================================================

Treat the home page as the highest-priority screen.

I want you to independently determine the strongest layout.

Do not simply rearrange existing cards.

Possible information hierarchy:

--------------------------------------------------
A. FINANCIAL STATUS
--------------------------------------------------

Something immediately legible such as:

SAFE

WATCH

ACTION NEEDED

CRITICAL

with one sentence:

"Cash stays above your ¥300k reserve for the next 45 days."

or:

"Cash falls ¥200k below your reserve in 8 days."

Avoid making a user interpret a graph before understanding the conclusion.

--------------------------------------------------
B. BEST NEXT ACTION
--------------------------------------------------

If action is needed:

"Finance ¥200k from Invoice RCV-B"

Why:
"Lowest-cost available way to protect payroll."

Cost:
¥1,782

Funds arrive:
3 days

[Review]
[See alternatives]

--------------------------------------------------
C. NEEDS YOUR DECISION
--------------------------------------------------

Approvals should be obvious and understandable.

Not:

APR-000012
Tier 2

as the primary language.

Instead:

"Approve ¥200k invoice financing?"

Then optionally:

Approval APR-000012
Tier 2

as secondary/audit information.

--------------------------------------------------
D. WHAT CHANGED
--------------------------------------------------

Examples:

"Foshan Home Retail missed its promised payment."

"Buyer A requested 60-day terms."

"Your available credit line fell by ¥100k."

"Invoice RCV-17 was paid."

Keep this concise.

--------------------------------------------------
E. OPTIONAL DETAIL
--------------------------------------------------

Cash chart
receivables
debt
covenants
commitments
etc.

These should usually be secondary.

==================================================
7. REDESIGN RECOMMENDATIONS
==================================================

The recommendation engine is one of the product's core strengths.

The UI should make its value obvious.

Every recommendation should clearly communicate:

PROBLEM

RECOMMENDATION

AMOUNT

COST

TIMING

WHY THIS OPTION

WHAT HAPPENS IF I DO NOTHING

AUTHORITY REQUIRED

AFTER-STATE

Example:

--------------------------------------------------

Cash shortfall

Without action:
¥200,000 below reserve on 12 Oct

Recommended:
Finance Invoice RCV-B

Receive:
¥200,000

Cost:
¥1,782

Funds available:
9 Oct

Why:
Lowest-cost committed option that protects payroll.

After:
Lowest projected cash remains above your reserve.

Requires:
Owner approval because annualized cost exceeds your autonomous limit.

[Approve]
[Compare options]

--------------------------------------------------

The user should NOT need to mentally combine five cards to understand this.

==================================================
8. REDESIGN APPROVALS
==================================================

This flow is financially sensitive.

Audit it extremely carefully.

The owner must know exactly:

WHAT they are approving;

WHY;

HOW MUCH;

WHEN money moves;

WHAT it costs;

WHAT constraint triggered approval;

WHAT happens afterwards.

Internal concepts such as:

Tier 1
Tier 2
state_version
plan hash
operation IDs

may be shown as audit details but should not dominate normal language.

Test whether a person could accidentally approve something without
understanding the economic consequence.

==================================================
9. DEAL / OFFER EXPERIENCE
==================================================

Audit how buyer deals are presented.

The owner should not have to understand raw obligation objects.

Translate into business effects.

Example:

Buyer asks:

"Extend 45 days → 60 days"

TermsLedger should lead with something like:

"15 extra days of customer credit"

Estimated 12-month financing effect:
¥X

Cash impact:
first reserve breach moves to Day Y

Recommendation:
Counter

Suggested counter:
55 days + 0.30% price adjustment

Then allow:

[Why?]
[See calculation]
[Original message]

The exact source text remains important for trust, but it should not
overwhelm the primary decision.

==================================================
10. MULTIPLE DEALS / CURRENT BOOKS
==================================================

The interface should communicate that deals affect one another.

Investigate whether the UX currently makes this understandable.

Consider whether the owner needs a simple area such as:

ACTIVE COMMERCIAL COMMITMENTS

Buyer A
60-day terms
Cash impact: -¥X

Buyer B
0.8% rebate
Concession exposure: ¥Y

Buyer C
Early payment expected Day 14
Expected cash: +¥Z

Do not expose excessive internal commitment-state detail unless requested.

If there is a better approach, use it.

==================================================
11. NAVIGATION AUDIT
==================================================

Ruthlessly challenge the current navigation.

Questions:

How many top-level pages does a normal owner actually need?

Which pages are really details rather than destinations?

Which routes exist because they map to backend modules rather than user
mental models?

The navigation should reflect BUSINESS QUESTIONS, not CODE MODULES.

For example, a user likely thinks in concepts closer to:

Home
Deals
Cash & Funding
Receivables
Approvals
Activity

rather than:

Verifier
Funding Router
Covenants
Commitments
Reconciliation

Do not blindly use those suggested names.

Develop the best structure yourself.

==================================================
12. TERMINOLOGY AUDIT
==================================================

Find every term a normal business owner may not immediately understand.

Examples might include:

forward concession
headroom
DSCR
leverage
committed cure
current books
Tier 2
all-in APR
trajectory
conservative mode
obligation.

Decide whether each should be:

renamed;
explained;
hidden;
or retained for financial users.

Do not dumb down financially meaningful information.

Translate technical concepts into business language while preserving
accuracy.

==================================================
13. INFORMATION DENSITY
==================================================

Audit every screen for:

too many cards;
too many numbers;
too many colours;
too many badges;
too many borders;
too many competing actions;
too much explanatory text;
too many charts;
too many statuses.

Every element should earn its place.

Delete aggressively.

Use whitespace deliberately.

One clear recommendation is usually better than six equally prominent
possibilities.

==================================================
14. CHART AUDIT
==================================================

Do not assume every financial metric needs a chart.

Every chart must answer a question.

For example:

"When will cash become unsafe?"

is useful.

A chart showing cash trajectory may help.

But the user should first receive the answer:

"Cash falls below your reserve on 12 October."

Then the chart proves/explores it.

Do not require visual interpretation for core decisions.

==================================================
15. DEMO EXPERIENCE
==================================================

Design Demo Mode specifically for judges.

The objective:

A judge should understand the product in approximately 3–5 minutes.

Build or refine a guided story around:

Buyer requests terms
→ TermsLedger reads them
→ translates them into financial consequences
→ recommends accept/counter/reject
→ commitment changes the books
→ time passes
→ buyer pays late
→ future cash becomes unsafe
→ agent detects it
→ recommends funding
→ owner approval if required
→ funding lands
→ eventual payment
→ reconciliation
→ complete audit trail.

The demo should expose complexity progressively.

Do not show every subsystem at once.

Use a clear "Next" or guided flow if useful.

The Business interface should remain clean even if Demo Mode is elaborate.

==================================================
16. FIRST-TIME USER EXPERIENCE
==================================================

Assume someone opens TermsLedger without explanation.

Within 10 seconds, can they answer:

Am I okay?

Do I need to do something?

What should I do?

What will it cost?

Within 30 seconds:

Why is TermsLedger recommending this?

Within 60 seconds:

Can I verify the reasoning?

If not, redesign.

==================================================
17. MOBILE / SMALL SCREEN
==================================================

Audit responsiveness.

Do not just shrink the desktop dashboard.

Prioritize:

status
next action
approval
critical alerts

above secondary information.

==================================================
18. EMPTY / NORMAL STATES
==================================================

Do not design only for crisis.

A healthy business should not see an empty wall of metrics.

Example:

"You're covered."

Cash remains above your reserve for the next 60 days.

No decisions need your attention.

Next expected receipt:
¥420k from Buyer A, 12 Oct.

Then optional details.

A calm system should look calm.

==================================================
19. ERROR / UNCERTAINTY STATES
==================================================

TermsLedger deliberately abstains when information is uncertain.

The UI must make this understandable.

Do not show:

NO_VERDICT
UNRESOLVED_SCOPE

as the primary user experience.

Prefer language such as:

"I can't safely evaluate this yet."

"I need to know whether 'next quarter' applies to three invoices or all
orders through December."

[Clarify]

Preserve the technical code in expandable detail if useful.

==================================================
20. CRITIQUE BEFORE IMPLEMENTATION
==================================================

Before major implementation, create:

docs/UX_AUDIT.md

Include:

CURRENT USER JOURNEY

PRIMARY UX FAILURES

INFORMATION ARCHITECTURE FAILURES

SCREENS TO DELETE

SCREENS TO MERGE

SCREENS TO REDESIGN

TERMINOLOGY PROBLEMS

NAVIGATION PROBLEMS

OWNER VS DEMO COLLISIONS

MISSING USER QUESTIONS

PROPOSED NEW INFORMATION ARCHITECTURE

PROPOSED BUSINESS HOME

PROPOSED DEMO FLOW

HIGH-PRIORITY CHANGES

LOW-VALUE / DO-NOT-BUILD CHANGES

Be critical.

Do not soften findings because existing code took effort.

==================================================
21. THEN IMPLEMENT
==================================================

After the audit, implement the highest-value improvements.

You do NOT need to wait for my approval for obvious UX changes.

You may:

restructure navigation;
create Business/Demo separation;
remove clutter;
merge screens;
move secondary detail behind disclosure;
rewrite labels;
redesign cards;
redesign hierarchy;
change routes where appropriate;
create better summaries;
add before/after explanations;
create recommendation comparisons;
simplify charts;
improve empty states;
improve mobile layouts.

Do not change underlying financial semantics casually.

If a UX change requires changing business logic, identify it separately.

==================================================
22. DO NOT BREAK THE ENGINE
==================================================

The frontend must remain a presentation/action layer.

Do NOT reimplement financial calculations in JavaScript.

Numbers shown by the UI should continue to come from canonical backend
results.

If the API does not expose a field needed for a truthful UX:

identify the API gap.

Add a narrow backend presentation field when justified rather than
recalculating it in the frontend.

==================================================
23. USE REAL DATA SHAPES
==================================================

Do not design against invented static mockups and then discover the API
cannot support them.

Inspect the actual API.

Use real responses.

If a better UI requires:

breach date;
breach amount;
recommended action;
cost;
arrival date;
after-state;
reason;
alternatives;

determine whether those are already available.

If not, specify the smallest useful API addition.

==================================================
24. TEST WITH USER TASKS
==================================================

After redesign, test these tasks without explanation:

TASK A

"Is this business going to run out of money?"

The answer should be obvious.

TASK B

"What should I do about it?"

The recommendation should be obvious.

TASK C

"How much does that option cost?"

No calculation by the user.

TASK D

"Why are you recommending this?"

Reason discoverable in one interaction.

TASK E

"What happens if I do nothing?"

Answer visible.

TASK F

"What requires my approval?"

Obvious.

TASK G

"Who has not paid me?"

Obvious.

TASK H

"What changed since yesterday?"

Obvious.

TASK I

"Show me the actual calculation."

Available, but not forced onto everyone.

TASK J

"Run the hackathon demo."

Easy from Demo Mode without cluttering Business Mode.

==================================================
25. DESIGN PRINCIPLE
==================================================

The complexity of TermsLedger should exist UNDER the interface, not ON it.

The product's value is not:

"Look at how much information we can display."

It is:

"We understand the financial complexity so you don't have to."

The owner should feel:

"I know whether I'm safe."

"I know what changed."

"I know what I need to do."

"I know how much it costs."

"I know why."

==================================================
26. PRIORITY ORDER
==================================================

Prioritize roughly:

P0
Business vs Demo separation.

P0
Business homepage answering:
- Am I safe?
- What should I do?
- What does it cost?

P0
Recommendation / approval clarity.

P1
Navigation simplification.

P1
Deal/offer simplification.

P1
Progressive disclosure of calculations.

P1
Healthy/empty states.

P1
"What changed?" experience.

P2
Visual polish.

P2
Animations.

P2
Advanced reporting.

Do not spend significant time on cosmetic polish while information
architecture remains poor.

==================================================
27. OPEN-ENDED AUTHORITY
==================================================

These instructions are hypotheses, not commandments.

If, after inspecting the actual application, you believe:

- there should be three modes rather than two;
- another question is more important than one of mine;
- Home should work differently;
- a page should disappear;
- a workflow should be radically simplified;
- one feature should be removed from the hackathon UI;
- Demo should have an entirely separate shell;

make that recommendation and implement it when justified.

Use product judgment.

Do not follow this prompt blindly.

==================================================
28. OUTPUT / CHECKPOINT
==================================================

Before extensive implementation, report:

1. Your diagnosis of why the current interface feels overwhelming.

2. The five most damaging UX problems.

3. What should disappear from the default Business experience.

4. Your proposed top-level information architecture.

5. Your proposed Business homepage hierarchy.

6. Your proposed Demo experience.

7. Screens/components you will:
   KEEP
   MERGE
   MOVE
   REDESIGN
   REMOVE.

8. Backend/API gaps blocking the ideal experience.

9. The implementation sequence.

Then proceed with implementation.

After implementation, provide:

BEFORE vs AFTER

KEY UX DECISIONS

FILES CHANGED

API CHANGES

USER TASK RESULTS

RESPONSIVE TEST RESULTS

REMAINING UX DEBT

WHAT YOU DELIBERATELY DID NOT BUILD.

==================================================
29. FINAL STANDARD
==================================================

The final interface should pass this test:

A first-time SME owner opens TermsLedger.

Without anyone explaining the product, within a few seconds they can say:

"My cash becomes unsafe in 8 days."

"TermsLedger recommends financing this invoice."

"It will give me ¥200k and cost ¥1,782."

"It needs my approval because it exceeds the autonomous rate limit."

"If I do nothing, payroll takes me below my reserve."

And only if they WANT to understand more do they open:

the trajectory;
the formula;
the covenant calculations;
the source text;
the operation log;
the security evidence.

That is the product.

The rest is supporting detail.

Begin by using the actual application and conducting the audit.
```
