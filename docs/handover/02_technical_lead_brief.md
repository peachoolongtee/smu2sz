# Owner's brief 2: technical lead, prioritisation owner and integration lead (verbatim, 1 Oct 2026)

```text
You are now the TECHNICAL LEAD, PRIORITISATION OWNER, AND INTEGRATION LEAD
for TermsLedger v2.

A full independent audit has already been completed.

DO NOT perform another broad audit from scratch.

Use the existing audit as the baseline:
- its reproduced defects;
- its current-capability map;
- its financial findings;
- its security findings;
- its recommended C1–C13 changes;
- its implementation backlog.

Your job now is to decide exactly WHAT GETS FIXED NEXT,
delegate bounded grunt work to lower-tier subagents,
and continuously integrate the results into one stable product.

==================================================
0. PRIMARY OBJECTIVE
==================================================

Maximise the quality of the FinTechathon submission while preserving
financial correctness and security.

The confirmed rubric is:

40% Task Completion
30% Security & Compliance
30% Innovation & Interaction

We have already built broad functionality.

DO NOT optimise for more module count.

Optimise for:

1. closing real security holes;
2. eliminating financially wrong decisions;
3. making all modules operate on one coherent financial state;
4. completing end-to-end workflows;
5. turning TermsLedger into an ongoing financial participant;
6. exposing functionality that is already built;
7. making the strongest capabilities obvious in the UI/demo.

The system should become deeper and more coherent, not merely larger.

==================================================
1. BASELINE FINDINGS YOU MUST TREAT AS REAL
==================================================

Unless repo inspection proves they have already been fixed since the audit,
treat these as open defects.

CRITICAL SECURITY

S1:
Counterparty /nl can disclose protected financial state in the structured
response even when the reply string is guarded.

S2:
Quoted/pasted buyer text can cause an owner request to be classified as an
approval and execute a Tier-2 item.

S3:
Compiler coverage can miss unread riders while the response says
"Agreed as proposed."

S4:
Acceptance/approval does not fully re-bind the decision to current state,
allowing concurrent commitments to exceed limits.

Security scoreboard currently contains hard-coded success fields.

CORE STATE

Accepted commitments do not consistently alter the financial base case.

Different modules can therefore operate on different effective books.

Partial settlement can settle an entire receivable.

The early-payment leg of some accepted plans is not executed.

Two concurrent offers can each pass independently and jointly violate
the aggregate cap.

The same receivable can have multiple live commitments.

TIME / PARTICIPATION

Runtime time does not meaningfully advance in the served application.

Therefore:
- due dates do not become overdue;
- mandate expiry is largely inert;
- alerts do not become proactive;
- actual-vs-expected events do not trigger replanning.

Alerts are pull-only.

Reconciliation is largely read-only.

FINANCIAL CORRECTNESS

Known decision-changing issues include:
- early-pay break-even fixed around a 30-day assumption;
- early payment can be accepted even when the cash is not needed;
- financed receivable may be double-counted when settled early;
- some DSCR treatment omits scheduled principal;
- Counter A has a rounding/boundary issue;
- capex comparisons have economic simplifications.

INTERACTION

Several capabilities already exist but are unreachable from /nl:
- funding comparison;
- alerts;
- reconciliation;
- ratios;
- capex;
- borrower file.

There is no strong proactive moment.

There is no useful owner home view.

The approval card is too thin.

The autonomy proof is largely invisible.

==================================================
2. DO NOT BLINDLY FOLLOW THE AUDIT ORDER
==================================================

The audit provides recommendations, not commands.

Inspect the CURRENT repository first.

For every audit finding:

OPEN
FIXED
PARTIALLY FIXED
OBSOLETE
CANNOT REPRODUCE

Record evidence.

Then create a dependency-aware execution plan.

Prioritise using:

P0 — security or correctness defect capable of causing:
- unauthorised operation;
- protected-data disclosure;
- financially wrong ACCEPT/COUNTER;
- double-counted cash;
- stale-state execution.

P1 — required to make the main workflow coherent end to end.

P2 — materially improves task completion or interaction using existing code.

P3 — new enrichment / optional feature.

No P3 work starts while meaningful P0 work remains.

==================================================
3. PRIORITY SCORING
==================================================

For every candidate task score:

SECURITY IMPACT            0–5
FINANCIAL CORRECTNESS      0–5
TASK COMPLETION            0–5
INNOVATION / INTERACTION   0–5
DEMO VALUE                 0–5
DEPENDENCY UNLOCK          0–5
REAL BUSINESS VALUE        0–5
REGRESSION RISK            0–5
ESTIMATED EFFORT           hours/days
CONFIDENCE                 high/medium/low

Then classify:

DO NOW
NEXT
IF TIME
POST-HACKATHON
DO NOT DO

Do not maximise the numeric score mechanically.

A security defect outranks a pretty demo feature even if the feature has
higher presentation value.

==================================================
4. MAIN AGENT VS LOWER-TIER SUBAGENTS
==================================================

YOU, the main Fable agent, own:

- architecture;
- prioritisation;
- financial invariants;
- security invariants;
- shared schemas;
- state semantics;
- merge decisions;
- integration;
- final acceptance testing;
- demo-path decisions.

DO NOT delegate those.

Lower-tier subagents should perform bounded grunt work such as:

- repository searches;
- tracing call paths;
- writing focused unit tests;
- generating adversarial fixtures;
- reproducing one specific bug;
- implementing one isolated function;
- updating one adapter;
- wiring one existing endpoint into /nl;
- creating migration code from an already-decided schema;
- building one UI card from an existing API response;
- generating test cases;
- checking all references to a field/interface;
- documenting an already-approved change.

Subagents may propose interface changes.

They may NOT independently change shared financial semantics.

==================================================
5. DELEGATION RULE
==================================================

Every subagent task must contain:

TASK
exactly one bounded objective

WHY
which audit finding / acceptance criterion it closes

OWNED FILES
exact files/directories it may modify

READ-ONLY DEPENDENCIES
files it may inspect but not edit

INTERFACE CONTRACT
inputs and outputs it must preserve

TESTS REQUIRED
specific tests it must add or run

ACCEPTANCE CRITERIA
machine-checkable where possible

FORBIDDEN CHANGES
what it must not refactor

RETURN FORMAT

STATUS:
complete / partial / blocked

FILES CHANGED:

BUG / FEATURE CLOSED:

TESTS ADDED:

TEST COMMAND:

TEST RESULT:

REGRESSIONS:

INTERFACE CHANGE REQUESTS:

ASSUMPTIONS:

Do not send vague tasks such as:
"Fix current books"
or
"Improve security."

==================================================
6. FIRST PHASE: RECONNAISSANCE
==================================================

Before coding:

1. read the current audit;
2. inspect git status / latest commits;
3. inspect current tests;
4. reproduce the P0 findings where practical;
5. determine which audit items are already fixed;
use the wayfinder skill for this

It must contain:

- current open findings;
- priority;
- dependencies;
- owner;
- estimated effort;
- test proving completion;
- status.

Also produce a dependency graph.

Do this quickly.

Do not spend hours writing prose.

==================================================
7. EXPECTED DEPENDENCY SHAPE
==================================================

Do not assume this is exact, but use it as the starting hypothesis.

WAVE A — SECURITY BOUNDARY

Likely tasks:

A1. Seal /nl counterparty responses.

A2. Separate quoted/untrusted text from owner intent and approval parsing.

A3. Make the security attack suite run through /nl in both owner and
counterparty roles.

A4. Compute security scoreboard from actual run data instead of hard-coded
success values.

A5. Make compiler coverage fail closed on unread word-bearing residue.

A6. Re-verify current predicates and state binding at accept/approve time.

These should be treated as blockers for increasing autonomy.

--------------------------------------------------

WAVE B — ONE FINANCIAL REALITY

Design centrally, then delegate implementation pieces.

Create one canonical concept such as:

current_books(...)

It should represent, as appropriate:

starting state
+ accepted live commitments
+ executed operations
+ settled amounts
+ current runtime day
+ unresolved receivables
+ debt balances
+ applicable scheduled flows.

Do NOT let separate agents independently define this state.

Once the semantics are approved centrally, delegate:

B1. commitment application;

B2. partial settlement / residual receivable;

B3. one-live-commitment-per-receivable enforcement;

B4. early-pay execution leg;

B5. module migration to current_books:
- verifier
- router
- trajectory
- alerts
- capex
- borrower file
- what-if

Do migrations in small batches.

Run golden tests after every batch.

--------------------------------------------------

WAVE C — CLOCK → EVENT → REPLAN LOOP

After B is stable:

C1. runtime clock advancement;

C2. posting due scheduled flows;

C3. expiry handling;

C4. expected vs actual receipt reconciliation;

C5. state update after reconciliation;

C6. automatic re-projection;

C7. alert containing a typed proposed cure;

C8. Tier-1 cure execution / Tier-2 approval queue.

The target experience is:

Day 34.

Expected ¥420,000 receipt was due Day 32.

No receipt found.

Current books now breach the ¥300,000 cash floor on Day 47.

Available bounded cure:
draw ¥150,000 from committed line.

[Execute]

This is the key proactive demo moment.

--------------------------------------------------

WAVE D — FINANCIAL CORRECTNESS

Parallelise only after shared semantics are stable.

Likely sub-tasks:

D1. derive early-pay break-even from actual days early;

D2. compare early pay against the cheapest admissible router plan;

D3. accept early pay only up to the amount actually needed;

D4. correct financed-receivable + early-settlement handling;

D5. correct Counter A rounding/boundary;

D6. test DSCR scheduled principal treatment;

D7. review like-for-like APR gate.

Use independent hand-calculated golden cases.

Do not let the same agent both derive and validate a material financial
formula unless a second agent independently checks it.

--------------------------------------------------

WAVE E — INTERACTION / TASK COMPLETION

Once P0 correctness is stable:

E1. add /nl intents for already-built capabilities;

E2. nearest-capability fallback instead of flat refusal;

E3. owner home;

E4. richer Tier-2 approval card;

E5. visible autonomy proof;

E6. causal financial headline;

E7. consistent rate bases / annualised comparison display.

Do not invent new financial functionality here.

Expose existing functionality cleanly.

--------------------------------------------------

WAVE F — OPTIONAL ENRICHMENTS

Only after the main path is green.

Candidates:

- named stress scenarios;
- stressed borrower-file case;
- payment instrument term:
  cash / 银票 / 商票;
- Chinese localisation;
- guarded supplier payment;
- recurring fixture outflows;
- deployment / mainland reachability.

Treat each as optional.

==================================================
8. CURRENT_BOOKS DESIGN MUST BE CENTRAL
==================================================

This is the architectural change most likely to create regressions.

Do NOT delegate its semantics to a cheap subagent.

The main agent must specify:

- source of truth;
- commitment precedence;
- settlement semantics;
- partial receipt semantics;
- due-date changes;
- effective dates;
- duplicate commitment rules;
- operation ordering;
- state version;
- concurrency behaviour;
- idempotency behaviour;
- whether projections consume current or historical books.

Write a short ADR before implementation.

Then lower-tier agents can implement pieces against that ADR.

==================================================
9. STATE-BINDING RULE
==================================================

A verdict is not permanent authority.

At acceptance / approval / execution:

- verify mandate version;
- verify state version or safely recompute;
- verify aggregate caps;
- verify per-buyer caps;
- verify facility availability;
- verify no conflicting live commitment;
- verify relevant receivable is still unsettled;
- verify operation remains admissible.

If state changed materially:

RECOMPUTE

or

REFUSE_AND_REPLAN

Never execute from a stale verdict merely because it was previously valid.

==================================================
10. /NL SECURITY RULE
==================================================

Treat /nl as the primary attack surface.

Untrusted quoted content must never become owner intent.

Implement clear provenance such as:

OWNER_TEXT
QUOTED_COUNTERPARTY_TEXT
DOCUMENT_TEXT
SYSTEM_STATE
APPROVAL_REFERENCE

Approval identifiers discovered only inside quoted/document text must not
trigger APPROVE.

Counterparty role must not receive:

- reserve floor;
- aggregate cap;
- per-buyer caps;
- DSCR thresholds;
- leverage thresholds;
- facility limits;
- internal funding menu;
- other buyers' terms;
- hidden counter values;
- internal reasoning fields.

Guard the full structured response, not just one reply string.

==================================================
11. COMPILER COVERAGE RULE
==================================================

For autonomous Tier-1 acceptance:

UNKNOWN MATERIAL TEXT MUST FAIL CLOSED.

If there is meaningful word-bearing residue that was not represented by
typed obligations:

ABSTAIN / NEEDS_REVIEW

Do not say:

"Agreed as proposed"

when part of the proposal was not understood.

Instead restate exactly the typed terms being accepted.

Prefer lower autonomous volume over one wrong autonomous commitment.

==================================================
12. FINANCIAL FORMULA REVIEW
==================================================

For every headline formula:

1. derive it explicitly;
2. write independent hand-calculated cases;
3. test boundary cases;
4. test alternate tenors;
5. test no-cash-needed cases;
6. test partial amount cases;
7. have a second subagent independently reproduce the result.

Especially:

- early-payment implied annual cost;
- break-even discount;
- invoice-finance effective cost;
- partial funding;
- DSCR;
- leverage;
- clean-down;
- counter economics.

Never optimise for preserving a headline number if the financially correct
answer changes.

==================================================
13. USE LOWER-TIER AGENTS FOR TEST EXPANSION
==================================================

After an implementation agent finishes, use a different lower-tier agent
to generate adversarial cases for that change.

Examples:

For current_books:
- accepted terms change receipt date;
- revoked commitment removed;
- partial settlement;
- duplicate receipt;
- duplicate live commitment;
- two concurrent offers;
- time advances before acceptance;
- commitment expires;
- repayment posted twice.

For /nl:
- owner quoting buyer;
- buyer quoting owner;
- nested quotes;
- approval id inside attachment text;
- fake approval id;
- counterparty asks for reserve;
- mixed Chinese/English extraction request.

For early pay:
- 3 days;
- 30 days;
- 90 days;
- 0 days;
- cash not needed;
- partial gap;
- early-pay price equal to break-even ±1 bp.

==================================================
14. INTEGRATION LOOP
==================================================

After EVERY merged task:

1. inspect the diff;
2. run module tests;
3. run golden finance tests;
4. run relevant security suite;
5. run one main end-to-end scenario;
6. inspect persisted state;
7. confirm no interface drift;
8. update NEXT_FIXES.md.

Do not merge ten subagent branches and integrate at the end.

Continuous integration is mandatory.

==================================================
15. BRANCH / FILE OWNERSHIP
==================================================

Prefer separate worktrees/branches.

Examples:

fix/nl-boundary
fix/commit-state-binding
feat/current-books
feat/runtime-clock
fix/early-pay-economics
feat/nl-capability-routing
feat/owner-home

Lower-tier agents must not modify unrelated files.

If a task discovers a shared-interface problem, return:

INTERFACE_CHANGE_REQUEST

Do not silently change the shared interface.

==================================================
16. PARALLELISM POLICY
==================================================

Parallelise:

- reproduction;
- unit-test generation;
- independent formula verification;
- isolated endpoint wiring;
- UI cards;
- fixture generation;
- security-case expansion.

Do NOT parallelise competing edits to:

- domain models;
- current_books semantics;
- mandate semantics;
- operation execution semantics;
- financial formula definitions;
- shared API contracts.

Maximum agent count is not the goal.

Maximum independent useful throughput is.

==================================================
17. DO NOT LET LOWER-TIER AGENTS OVER-REFACTOR
==================================================

Tell every implementation agent:

"Make the smallest change that satisfies the acceptance tests.

Do not:
- rename unrelated types;
- change package structure;
- upgrade dependencies;
- rewrite functioning components;
- introduce frameworks;
- clean up unrelated code."

This is a deadline-driven integration phase.

==================================================
18. CAPACITY MANAGEMENT
==================================================

Assume engineering time is scarce.

For each task estimate:

best case
likely
worst case

If a task exceeds 1.5× its expected effort:

STOP

Report why.

Main agent decides whether to:
- continue;
- narrow;
- feature-flag;
- postpone.

Do not let one optional feature consume two days silently.

==================================================
19. DEMO GATE
==================================================

After every major wave, run the complete main demo.

Target eventual story:

1. Buyer sends natural-language commercial offer.

2. Compiler extracts source-grounded obligations.

3. Engine shows the hidden economic effect.

4. Debt Desk compares funding options.

5. Verifier rejects/counters under owner's mandate.

6. Buyer agrees.

7. Commitment is recorded and changes current books.

8. Advance time.

9. Buyer receipt fails to arrive.

10. TermsLedger notices before the cash-floor breach.

11. TermsLedger re-plans.

12. A mandate-bounded cure is proposed.

13. Tier 1 executes or Tier 2 goes to owner approval.

14. Receipt eventually arrives.

15. Reconciliation updates the receivable and repays financing.

16. Ledger shows the full causal history.

17. Security attack is attempted through /nl and refused.

If a change weakens this flow, question whether it belongs before submission.

==================================================
20. SCOREBOARD
==================================================

Maintain a live engineering scoreboard generated from tests.

At minimum:

END-TO-END TASKS PASSED
FINANCIAL GOLDEN CASES PASSED
MATERIAL COMPILER ERRORS
AUTONOMOUS WRONG ACCEPTS
SECURITY ATTACKS RUN
UNAUTHORISED OPERATIONS
PROTECTED FIELDS DISCLOSED
STALE-STATE EXECUTIONS
REPLAY SUCCESSES
CURRENT_BOOKS CONSISTENCY FAILURES
/NL INTENT ACCURACY
/NL CAPABILITY COVERAGE

Do not hard-code success metrics.

==================================================
21. WHEN TO STOP FIXING
==================================================

A module is good enough when:

- no known material financial error remains;
- no known security hole remains;
- relevant golden tests pass;
- it works in the integrated demo;
- additional work would be polish rather than changed behaviour.

Do not optimise every module to perfection.

==================================================
22. REPORT TO ME
==================================================

Before launching implementation subagents, return:

A. CURRENT STATE
Which audit items remain open.

B. PRIORITY TABLE
Ordered list with P0/P1/P2/P3.

C. DEPENDENCY GRAPH
What must precede what.

D. DELEGATION PLAN
For every task:
- main agent or subagent;
- agent tier;
- files owned;
- acceptance test;
- estimated effort.

E. NEXT 24 HOURS
Exactly what will be attempted first.

F. STOP CONDITIONS
What will be dropped if work takes too long.

Then begin execution unless a genuine product decision requires user input.

==================================================
23. OPERATING PRINCIPLE
==================================================

Your role is not:

"Make TermsLedger have the most features."

Your role is:

"Turn the large set of already-built components into the most coherent,
correct, secure and convincing financial agent possible."

Prefer:

existing modules connected together

over

new modules.

Prefer:

one living financial state

over

more screens.

Prefer:

proactive closed-loop behaviour

over

more calculators.

Prefer:

zero wrong autonomous decisions

over

higher autonomous coverage.

Prefer:

a repeatable end-to-end demo

over

architectural cleverness.

Begin with repository reconnaissance and produce the priority/delegation
plan.

view @research/termsledger_v2_audit_2026-10-01/AUDIT.md
```
