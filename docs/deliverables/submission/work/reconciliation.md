# Reconciliation of the technical document's claims

Working file for the submission editor. Reviewer: architecture and security-claims review, 18 Oct 2026, on branch
`docs/sub-claims` from `origin/docs/techdoc-chat-fixes` at `571ea64f`.

**How to read this file.** Each item gives (a) what the document says now, with its location in
`docs/deliverables/technical_document.md` (`TD:line`), (b) what is true, with evidence, and (c) the wording to use. Line numbers
are those of `technical_document.md` at `571ea64f`. Code references are `services/api/...` unless they start with another
top-level folder. Nothing here upgrades an older certification's scope.

**The builds involved** (all offline: `DEMO_MODE=1`, `TERMSLEDGER_NO_DOTENV=1`, `DATABASE_URL=memory`, `LLM_MODE=cache`).

| Name used here | Commit | What it is | Security status |
| --- | --- | --- | --- |
| Engine build | `975e082f` (dev, 17 Oct) | engine, held-out, router and evaluation figures (`docs/deliverables/evidence/EVIDENCE_PACK.md`) | never certified (`EVIDENCE_PACK.md:629`) |
| v3 first assessed build | `29fa0ea2` (dev, 17 Oct) | redaction fix, round four | CERTIFIED for scope S (`docs/security/CERTIFICATIONS.md:107-141`) |
| v3 assessed build on this base | `85309b63` (dev, 17 Oct) | batches 5 and 6 | CERTIFIED for scope S, ASK-1/2 and REG-1..7 disclosed (`CERTIFICATIONS.md:82-105`); the self-assessment on this base names it (`docs/SECURITY_SELF_ASSESSMENT.md:17`) |
| Batches 7 to 10 | `6d2b6941` (dev, 18 Oct) | contract set-up, router, answer cards | CONDITIONAL: scope S only with `FEATURE_CONTRACT_TERMS` off (`CERTIFICATIONS.md:52-80`) |
| Round five | `70f23ac5` (dev head, 18 Oct) | round-five security fixes and the engine half | CERTIFIED for scope S, REG-8 disclosed, in commit `08c8dac0` on `origin/docs/assessment-final`, **not yet merged** into dev or into this base (see item 1) |
| This base | `571ea64f` (`docs/techdoc-chat-fixes`) | `70f23ac5` + terms priced as asked, `--live-llm`, capex dash, Ask full-page card, "can I pay everyone" | **not certified** (no record) |
| Submission build | not yet a commit | this base + tonight's five branches (a) to (e) + possibly `sec/round-six` | **not certified**; features (a) to (e) are "pending merge (assumed)" by the owner's instruction |

---

## 1. Security assessment versions, certified commits, pending fixes and the attack counts

**(a) What the document says.**
- TD:31 and Table 13 (TD:886): "279 stored attack cases ... `int/round-five` at `1294e941`".
- TD:884 (Figure 8 caption): "the Security Self-Assessment certified 260; DOC-05 ... and 18 chat cases ... were added since".
- TD:917-926: "Verdicts (Security Self-Assessment v3) ... It certified 260 cases on its assessed build; 19 were added afterwards,
  giving the 279 above ... Live mode and the question router (ADR-0015) are outside its assessed scope; the router's review by
  the Security Lead is pending."
- TD:373-374: "The ADR is still *proposed* and the Security Lead's review is pending."

**(b) What is true.**
- The attack counts are four different catalogue states, all with 0 harm-oracle violations:
  - **259** = 126 API + 133 chat: `0ba8e4c1` to `0fde33fd` (`CERTIFICATIONS.md:30,44,157,187`).
  - **260** = 127 API + 133 chat: `29fa0ea2` (`CERTIFICATIONS.md:128`; the API case added was TC-04, `FINDINGS_REGISTER.md:42`).
  - **261** = 128 API + 133 chat: `85309b63` (`CERTIFICATIONS.md:94`; DOC-05 added; `SECURITY_SELF_ASSESSMENT.md:33,71,1014`).
  - **279** = 128 API + 151 chat: round five (NL-TQ01..18, Tier-3 requests put as questions), reported on `1294e941`
    (`services/api/evals/security/latest_report.json`, committed `0ff5b0d5`), certified as part of `70f23ac5`
    (`git show 08c8dac0:docs/security/CERTIFICATIONS.md`, row "70f23ac5"), and re-run by this review on `571ea64f`
    (`judge_eval.py`: 279 run, 0 caused harm, detection 97.66% of the 128 API cases, 70.61% of all 279).
- The self-assessment on this base is **v3.0 dated 17 Oct, assessed build `85309b63`, 261 cases** (`SECURITY_SELF_ASSESSMENT.md:11,17,33`).
  The "260" in TD:884 and TD:922 is the `29fa0ea2` figure and is wrong for v3 as it stands on this base.
- `6d2b6941` was CONDITIONAL (`CERTIFICATIONS.md:52-80`): scope S only with `FEATURE_CONTRACT_TERMS` off, because CT-1 and CT-2
  were open; `pnpm demo` turns that flag on (`scripts/demo.mjs:314`).
- **`70f23ac5` has been certified**, but only on an unmerged branch: commit `08c8dac0` on `origin/docs/assessment-final`
  ("certify 70f23ac5 as the final assessed build"). That record says: full suite 10,674 passed, 0 failed, 47 skipped; 279 cases,
  0 harm, 120 of 128 API cases stopped by the named control; sweep 0 violations; language boundary 0 wrong-and-material;
  PostgreSQL 3 of 3; mock browser 479 passed, 77 skipped; CSP 0 violations; verdict **CERTIFIED for scope S, "with contract terms
  and the router on as `pnpm demo` sets them, and live model mode excluded"**; disclosed REG-8 (Low), REG-9 (Info), CT-2b (Low),
  SEC-27 and SEC-28 (deferred by the owner). The same branch moves the self-assessment's manifest to `70f23ac5`
  (`git show 08c8dac0:docs/SECURITY_SELF_ASSESSMENT.md`, line 17) while its document-control line still reads
  "Version 3.0, 17 Oct 2026" (line 11) and its executive summary still says "100 API routes" (line 33).
- The ADR-0015 router **was reviewed**: the review of `6d2b6941` found RT-L1, RT-L2, RT-L3 and ASK-2b
  (`FINDINGS_REGISTER.md:73-76`), fixed on `sec/router-guards` and merged in `70f23ac5` (merge `a622bc75`). The ADR's status
  line still says "Proposed ... the Security Lead's review is pending" (`docs/adr/0015-ask-router.md:3-4`).
- **Pending fixes, not in `70f23ac5` and not in this base:** `sec/round-six` `563de405` (REG-8: a record blocked by
  PARTY_UNCHECKED stays entitled under its counterparty in the egress guard; REG-9: demo lender names apply in demo mode only;
  CT-2b: the borrower file counts set-up invoices before the first is issued). Deferred by the owner and disclosed: SEC-27,
  SEC-28. The register on this base still says round-five fixes are "not yet in dev" (`FINDINGS_REGISTER.md:56-72`), which
  `70f23ac5` made stale; the corrected register is commit `1c736876` (on `origin/docs/assessment-final`).
- **Nothing after `70f23ac5` is certified**: the five features already on this base and tonight's (a) to (e) change chat and
  Ask FLOW code (`app/nl/*`, `app/outbound/message.py`, `app/main.py` for (e)). The catalogue still shows 0 harm on this base
  (this review's run), but that is a test result, not a certification.

**(c) Corrected wording.**
- Table 1, Security row: "279 stored attack cases (128 through the API, 151 through chat): 0 violations of the defined harm
  oracles in each specified run, on `70f23ac5` and again on the submission base (`571ea64f`). The Security Lead certified
  `70f23ac5` for the local simulation (internal review, not external accreditation); later chat and Ask FLOW changes are not
  certified."
- Figure 8 caption: "...279 stored cases through the API and chat, by class. The catalogue grew from 259 (16 Oct) to 260
  (TC-04), 261 (DOC-05, the build Security Self-Assessment v3 first assessed, `85309b63`) and 279 (18 chat cases that put a Tier-3
  request as a question, round five)."
- TD:917-926, replace with: "**Verdicts (Security Self-Assessment v3, assessed build `70f23ac5`, certified 18 Oct for the
  local simulation with contract terms and the router switched on as `pnpm demo` sets them).** Local simulation on loopback: GO.
  A demo over a network: NO-GO until a tested deployment profile exists. Production: NO-GO. Live model mode is outside the
  assessed scope. Fixes for three findings of the last review (REG-8, REG-9, CT-2b) are built but not in the assessed build;
  SEC-27 and SEC-28 are deferred by the owner. Changes made after `70f23ac5` (the Ask FLOW fixes in section 03 and the JSON
  error response) were tested with the catalogue but are not certified." **Condition:** use this only once `08c8dac0`
  (`docs/assessment-final`) is merged, so the cited self-assessment matches. Until then: "v3 names `85309b63` (261 cases); the
  Security Lead's certification of `70f23ac5` is recorded on the branch `docs/assessment-final`."
- TD:373-374: "The ADR is *proposed*. The Security Lead reviewed the router on `6d2b6941`; its four findings (RT-L1 to RT-L3,
  ASK-2b) are fixed in `70f23ac5`, which is certified for the local simulation. Live mode, where the router acts, is outside that
  certification." Also update `docs/adr/0015-ask-router.md:3-4`.

---

## 2. Engine results vs recent feature results vs the final build

**(a) What the document says.** Table 1 header (TD:20-22): engine, agent and test figures at `975e082f` (17 Oct); Ask FLOW at
`b4167053`; attacks at `1294e941`. TD:41-42: "every number ... was measured on the build named in Table 1". Table 1 Tests row
(TD:35) and Table 14 (TD:985): "9,085 API tests (9,040 passed, 1 known machine-specific hash failure ...)".

**(b) What is true.**
- The submission build is none of `975e082f`, `b4167053` or `1294e941`. Engine code (`financial/`, `funding/`, `verifier/`,
  `covenants/`) changed after `975e082f` only through the owner-approved round-five engine commit `1c49ce5e` (CT-2, CT-6, CT-7,
  REG-5), whose review found "the golden hashes are identical to `6d2b6941`" (`08c8dac0`, CERTIFICATIONS "Code review of the delta").
  So the engine figures are very likely unchanged, but **no full `scripts/evaluate.py` run on `70f23ac5` or later is recorded**.
- `975e082f`'s figures have clear provenance in `docs/deliverables/evidence/EVIDENCE_PACK.md:26-37` (commands, timings), but the
  `evaluate.py` report itself was written to a scratch folder; the committed `services/api/evals/latest_report.md` is from
  **5 Oct** (`d4b410f`, 126 attacks, router p50 96 ms), not the 17 Oct run the document quotes.
- Issue #161 was a **stale pin, not machine-specific** (`FINDINGS_REGISTER.md:55`), and is **closed** since `29fa0ea2`
  (`SECURITY_SELF_ASSESSMENT.md:25,609-615`). The 9,040 figure is also "accepted as given, not re-run" (`EVIDENCE_PACK.md:27`).
- Later full-suite results with clear provenance: `85309b63` 9,740 passed / 0 failed / 46 skipped; `6d2b6941` 10,375 passed /
  0 failed; `70f23ac5` 10,674 passed / 0 failed / 47 skipped (`08c8dac0`). Mock browser suite on `70f23ac5`: 479 passed, 77
  skipped. No live-browser figure after `975e082f` (139 passed, #157) is recorded.
- Ask FLOW figures re-run by this review on `571ea64f`: the 503-turn bank **303 / 46 / 0 / 154** (unchanged); the 345 everyday
  wordings **326 right (94.5%), 4 wrong topic (1.2%), 15 missed**; held-out **127/142 (89.4%), 3 wrong (2.1%)**. The document's
  327 / 3 (0.9%) is the `b4167053` figure; "can I pay everyone" (`3bc3b1c0`) moved one tuning item ("are we going to be able to
  pay our bills this month") to a wrong-topic answer. Tonight's (b) and (c) change Ask FLOW again, so these must be re-run on
  the submission build.
- `judge_eval.py` on `571ea64f` (this review): 49/49 tasks (88 turns; the document says 87 at TD:713), 279 attacks 0 harm, demo
  walk OK, chain VALID (14 operations, 8 security events), tampered copy rejected, 105 s.

**(c) Corrected wording.**
- Table 1 caption: "Offline. Engine and evaluation figures: dev `975e082f` (17 Oct); the round-five engine change after it left
  every golden value unchanged. Tests and attacks: `70f23ac5` (18 Oct), the certified build. Ask FLOW figures: `571ea64f`
  (18 Oct). Table 14 gives each source."
- Tests row: "10,674 API tests passed, 0 failed, 47 skipped; 479 mock browser tests (on `70f23ac5`, 18 Oct). Web unit 169 and live
  browser 139 (2 known write-conflict retries, #157) on `975e082f`." Delete "machine-specific".
- TD:41-42: "Every number is synthetic and was measured on the build named beside it (Table 14). The submission build adds the
  Ask FLOW changes of section 03 after the last measured build."
- Re-run before submission, on the submission build: `owner_questions_baseline.py`, `owner_questions_general.py --part all`,
  `judge_eval.py`, and ideally `scripts/evaluate.py`; then put the commit in Table 14.

---

## 3. "Every target met" beside tables with missed targets

**(a) What the document says.** Table 14 (TD:993): "Offline evaluation | `scripts/evaluate.py` (7 min 41 s ...) | every target
met; figures in Tables 9 and 6". Table 9 commentary (TD:675): "Targets not met. The material-error target (≤ 5%) and the
zero-silent-error target are not met on held-out 3."

**(b) What is true.** `evaluate.py`'s targets are scored on its default offers set `fixtures/heldout` (45/50 verdict agreement,
material errors 0/36: `EVIDENCE_PACK.md:34`), not on held-out 2 or 3. On held-out 3 (rules path, 17 Oct) material errors are
3/51 = 5.9% (> 5%) and silent material errors 4 (> 0) (TD:665). Held-out 3's verdict agreement (70%) has no target. Also "Tables
9 and 6" is wrong: Table 6 is the funding menu; the evaluate.py figures are in Tables 9 and 10.

**(c) Corrected wording.** "`scripts/evaluate.py` (7 min 41 s, including the funding brute force) | every target in its own
gate met, on its default offers set (`fixtures/heldout`, written before the grammar fixes and since used in tuning). On held-out
3, scored separately (Table 9), the material-error (≤ 5%) and silent-error (0) targets are **not** met. Figures in Tables 9 and
10." Same change wherever the README or deck says "every target met".

---

## 4. "Optimal" funding vs a discrete search

**(a) What the document says.** TD:28 "Funding router | Optimal against an exhaustive brute force on 26/26 scenarios"; TD:84
"finds the cheapest admissible way"; TD:500 "It finds the cheapest admissible combination"; TD:508 "within ¥1 of an exhaustive
brute force"; TD:709 "Within ¥1 of the brute force on 26/26 scenarios".

**(b) What is true.**
- The router searches **at most three actions, amounts on a ¥10,000 grid** (`app/funding/search.py:79`), no action below ¥1,000
  (`:80`), **every source requested on day 0** ("the router searches amounts, not dates", `:16-17`).
- **Approval-free plans rank first whatever the cost difference** (`app/funding/search.py:11-15`): when a plan the agent may run
  alone exists, a cheaper plan with a leg above the rate ceiling is not chosen. "Cheapest" is cheapest within the best class
  (no approval, then needs approval).
- The "exhaustive brute force" is itself discrete and bounded (`services/api/evals/suites/funding.py`): pairs on a ¥5,000 grid,
  triples on a ¥10,000 grid with the last lever filled exactly to the fen (`:7, 380-442, 582`), a 120 s budget per reading, and a
  ¥1 tolerance (`:38, 522`). On `975e082f` the budget ran out on F09 and R03 (priced reading); those are judged "no worse than
  what it found" (`EVIDENCE_PACK.md:34`; `funding.py:503-523`). "Runnable optimality 26/26" is over runnable levers.
- Of the 26 router plans, 19 run today, 6 rely on actions no operation can perform ("cannot run today": buyer early pay, bill
  discount) and 1 (F06) has **no admissible plan** (`EVIDENCE_PACK.md:336-344`). Against a fair, runnable "line first"
  baseline, the router is cheaper in 3 of 18 comparable scenarios (¥169.78 in total) and feasible where the baseline is not in 1
  (`EVIDENCE_PACK.md:346-361`).

**(c) Corrected wording.**
- Table 1: "Funding router | On 26 test scenarios, no more than ¥1 dearer than a bounded grid brute force (two budget-limited
  cases judged against the best plan the brute force found); 19 plans run today, 6 are labelled 'cannot run today', 1 scenario has
  no admissible plan and the router says so."
- TD:84 and TD:500: "finds the cheapest plan it can search (up to three actions on a ¥10,000 grid, all requested today) that
  keeps cash above the reserve and meets the covenants, preferring a plan FLOW may run alone over a cheaper one that needs the
  owner."
- TD:508 and TD:709: "Within ¥1 of a bounded brute-force search on all 26 evaluation scenarios (pairs on a ¥5,000 grid, triples on
  ¥10,000; budget reached in 2 priced cases). This is optimality within the search space, not over every possible amount or date."

---

## 5. Autonomous Tier-1 authority vs "nothing happens without the owner"

**(a) What the document says.**
- Figure 1 caption (TD:107): "(3) Nothing is sent or agreed without the owner."
- TD:11-14: FLOW "answers within limits the owner has signed. It counters, declines or accepts, arranges the funding ..."
- TD:208-209: "Through the simulated buyer. The owner reviews the exact counter, then sends it ..."
- TD:754-758: Tier 1 "autonomous inside the mandate".
- Figure 9 caption (TD:1020): "The owner stays in control."

**(b) What is true.**
- Tier 1 runs with no owner step, inside the mandate (`app/mandate/tiers.py:85-120`; executor `app/operations/executor.py:641-712`):
  counter and reject (only the owner's decline closes a request); accept a pure early-pay discount on a named invoice that
  passes break-even, need, "cheaper than the plan" and the coverage proof (ADR-0005, ADR-0007); draw on, or finance from, a
  committed owner-approved facility **at any size within its limit** (`tiers.py:73-77`), if admission passes and, for the agent,
  the cost is within the rate ceiling; repay; a receipt from the bank feed or the owner.
- **A keyed buyer's chat message executes at Tier 1 with no owner step.** For a counterparty turn authenticated by its channel
  key, `app/nl/offers.py:359-367` calls `decide(..., execute=authenticated)`, which sends counters (`:324-332`), executes a Tier-1
  acceptance or queues a Tier-2 one (`:333-346`), or rejects (`:348-352`); the reply goes back to the buyer in the same HTTP
  response. An anonymous sender's message is "proposal only", nothing executed (`:372-375`). Before the owner has marked a
  counter as sent outside FLOW, this path is open (`:319-323` stops it after).
- The agent key (`X-Agent-Key`) can run the same Tier-1 operations through `POST /operations` (`app/api/operations.py:78-129`);
  there is no aggregate or daily draw limit (R-3, `FINDINGS_REGISTER.md:90`, Moderate in production).
- In the shipped UI, Tier-1 funding runs on an owner click ("Run the plan", "go ahead", an alert's *act*), but the legs are
  submitted as the agent (`app/alerts/act.py:25`; `app/nl/context.py:144-148`), so a leg above the ceiling is queued.
- What does need the owner: everything in Tier 2 (item 9), and every Tier-3 kind is refused for everyone.

**(c) Corrected wording.**
- Figure 1 caption, point (3): "In Business mode FLOW sends nothing itself: the owner sends the reply. Anything beyond FLOW's
  signed limits waits for the owner."
- TD:11-14, add after "answers within limits the owner has signed": "Inside those limits it may counter, decline, accept a
  plain early-payment discount and draw on committed funding on its own (Tier 1); everything else waits for the owner."
- TD:205-213 ("How agreement happens"): add a third bullet: "**A registered buyer writing through its channel key.** FLOW
  answers at once within Tier 1: it counters, declines, or accepts a plain early-payment discount that passes every test;
  anything else is queued for the owner. An unsigned message is a proposal only."
- Keep "The owner stays in control" only with "of everything outside the signed limits".

## 6. Manual external sending and owner-reported buyer acceptance

**(a) What the document says.**
- TD:211-213: "Outside FLOW. The owner sends the counter themselves ... and marks it as sent. FLOW then waits for the owner to
  record the buyer's answer, bound to the exact message hash. FLOW transmits nothing itself, and after a counter is marked as sent
  outside, no other path can answer that request."
- TD:467-469, TD:1191-1192: "In Business mode the owner copies FLOW's exact message, sends it, marks it as sent and records the
  buyer's answer."
- Table 3 Deals row (TD:145): "records the buyer's answer".

**(b) What is true.**
- Marking sent is bound to the verdict id, the books' state version, the mandate in force and the **message hash**
  (`app/api/outbound.py:348-396`; checks at `:357-375`), and records only an OFFERED fact.
- **"The buyer accepted" is the owner's report, not the buyer's.** `POST /offers/{id}/counters/{cid}/buyer-accepted` needs the
  owner token (`outbound.py:74`), is bound to the OFFERED fact and its message hash, expiry, the counter's terms hash, lapse,
  state version and mandate (`:455-478`), and executes `AcceptOffer` with `requested_by=OWNER` (`:486-489`). A Tier-2 result
  stays queued (`:511`). The buyer is **not authenticated**; any `evidence_text` is stored as an unverified document
  (`:493-497`).
- "Buyer declined" and "withdraw" are bound to the message hash (`outbound.py:554-601`). **A pasted buyer reply is not**: `POST
  /offers/{id}/buyer-reply` passes `message_hash=None` (`:618, 628`) and compiles the text as a new request (`:619-630`); a reply
  with no terms is refused (`:624-626`).
- Once a counter is marked as sent outside, chat paths and raw operations are refused (OUT-1, OUT-1b;
  `app/api/decisions.py:101-115`, applied at `accept.py:309`, `decide.py:464`, `operations.py:122`, `nl/pipeline.py:125`,
  `nl/offers.py:319`).
- What FLOW books on a reported acceptance is an agreement in its own books. It is not an authenticated communication, not a
  signature, and has no legal effect; FLOW cannot know whether the buyer actually agreed.
- Recording note (18 Oct, `docs/deliverables/video/README.md:72-73`): in Business mode, recording the buyer's acceptance books
  the agreement but **not the planned funding** (the Demo shell's simulated send runs it). Not re-checked on this base.

**(c) Corrected wording.**
- TD:211-213: "**Outside FLOW.** The owner sends the counter themselves, for example by WeChat, and marks it as sent; the mark is
  bound to the exact message. FLOW transmits nothing itself. When the buyer answers, the owner records it: 'accepted' and
  'declined' are bound to that message, and a pasted reply is read as a new request. FLOW does not authenticate the buyer's
  answer: an agreement recorded this way is the owner's report, checked against the terms and today's books, not proof that the
  buyer agreed. After a counter is marked as sent outside, no other path can answer that request."
- TD:1191-1192: "...marks it as sent and records the buyer's answer as the owner heard it. Recording an acceptance books the
  agreement; the funding plan is run separately from Cash & funding."

## 7. Redaction claims vs merge status, bypasses and the assessed scope

**(a) What the document says.** TD:252-255 "Identifying data is redacted first, by every provider backend (PRIV-1 to 3)";
TD:869 "The model receives redacted text only"; TD:953 (`--live-llm`): "text is redacted before it leaves"; TD:321-322.

**(b) What is true.**
- Merge status: the PRIV-1..3 fix (`sec/redaction-mandatory` `817bcaad`) is merged since `975e082f`/`29fa0ea2` and certified there
  for scope S (`CERTIFICATIONS.md:110`); it is in this base. It was tested with scripted backends
  (`tests/compiler/test_redaction_mandatory.py`), never against a live provider.
- What is redacted: six identifier kinds only (accounts, phones, emails, unified credit codes, national IDs, addresses after a
  label) (`app/compiler/redaction.py:4-12, 42, 73-80`). Names, amounts, dates, rates, clauses, chat ids, IBANs, full-width digits,
  unlabelled addresses and 12-15-digit accounts reach the provider (PRIV-4, PRIV-5, open; `SECURITY_SELF_ASSESSMENT.md:724-733`).
- Who redacts: compiler backends redact by default (`app/compiler/backends.py:64-82`; `app/compiler/service.py:61-71`), as do
  the classifier (`app/nl/classifier.py:126-137`) and the router (`app/nl/router/route.py:428-434`).
- Bypasses:
  - `LLM_REDACT=0` (`app/config.py:97-99`, default on) turns redaction off for **all three** model uses.
  - `LLM_LIVE_RAW=1` (`app/config.py:94-96`, default off) does **not** turn redaction off; in live mode it drops the
    recorded-reading step and the rules cross-check (`service.py:69, 83`), so a model's reading is no longer checked against
    the rules grammar. `scripts/evaluate.py:35-38` and `scripts/evaluate_contracts.py:20` set it for live measurement runs.
  - `pnpm demo --live-llm` passes the shell's environment through (`scripts/demo.mjs:179`) and never sets `LLM_REDACT`, so a
    shell `LLM_REDACT=0` reaches the API while the launcher prints "text is redacted first" (`:289`).
- Scope: live mode is an explicit exclusion of the assessed build (`SECURITY_SELF_ASSESSMENT.md:24`) and of the `70f23ac5`
  certification ("live model mode excluded", `08c8dac0`). PRIV-4/PRIV-5 are rated Moderate (`:824`).

**(c) Corrected wording.**
- TD:252-255: "**Identifying numbers are redacted first, in live mode, by every model call** (compiler, intent classifier and
  question router): bank and card numbers, phone numbers, email addresses, unified social credit codes, ID and passport numbers,
  and addresses after a label become placeholders. Redaction is on by default; `LLM_REDACT=0` turns it off. It is pattern-based:
  names, amounts, clauses, chat ids, IBANs and unlabelled addresses still reach the provider (PRIV-4, PRIV-5). It has been tested
  with scripted models only; live mode is outside every security certification."
- TD:869: "In live mode the model receives text with identifying numbers redacted (section 02 lists what is not)."
- TD:953: "...text is redacted before it leaves (unless `LLM_REDACT=0` is set in the shell)." Better: make `demo.mjs` force
  `LLM_REDACT=1` (code change, not in this review's scope).

## 8. Model-assisted uses vs diagrams that show only the compiler as model-backed

**(a) What the document says.** TD:14 "A language model reads text and nothing more"; Figure 2 caption (TD:174) "the compiler
is the only model-backed step"; Table 4 (TD:180) "Compiler (the only model-backed role, untrusted)";
`docs/deliverables/figures/fig1-architecture.png` labels the Compiler box "the only model step". TD:227-234 lists three uses
correctly. TD:240, 267-268, 935, 1026: the cache holds "recorded outputs" / "the model's past readings replayed".

**(b) What is true.**
- Model-backed in live mode (`LLM_MODE=live`):
  1. **The compiler** (`app/compiler/service.py:61-71`): buyer offers and messages (`POST /offers`, keyed and anonymous buyers;
     buyer chat; the owner's quoted text; **a pasted buyer reply**, `app/api/outbound.py:623`); contracts and lender agreements
     (`app/contracts/records.py:40-65`, `POST /documents`, owner only); `POST /facilities/compile`; and **setup's "Fill from an
     agreement"** (`app/api/setup.py:194-307`), whose read limit, rate and fees prefill a facility row that enters the books once
     the owner reviews and signs (`setup.py:502-525, 568-572`): the one place model-read numbers can become facility state.
  2. **The chat intent classifier** (`app/nl/classifier.py:33-34`, a closed list of 10 intents with no APPROVE, REJECT or
     COUNTERPARTY_MESSAGE): owner and agent turns the rules do not read (`app/nl/service.py:268-277`), never buyer turns
     (`:173-174`); its output never executes (`:300, 346-347, 376, 380-382`).
  3. **The question router** (ADR-0015): owner only, `FEATURE_ASK_ROUTER`; tries recorded routes first, then the provider in
     live mode (`app/nl/router/route.py:234-245, 425-434`).
  4. **Pending merge (assumed), (a):** classifier-labelled plain read intents (SHOW_STATUS etc.) go to the answers and the router
     in live mode (`origin/feat/ask-router-reads` `89e57719`, `app/nl/service.py`).
- Not model-backed: the simulated buyer (`app/counterparties/verbaliser.py:147-173` has an optional hook that is never
  connected; `app/api/decide.py:502`).
- **No model output ships in the repository.** The 19 files in `fixtures/compiler_cache/` all carry `"source_model":
  "rules-v1"` (the deterministic grammar); there is no `intent_cache` or `route_cache`. So offline (cache mode, the demo, the tests,
  the evaluation), every reading comes from the rules grammar. The contract figures (75%/86%/98%) and the 17-contract party
  comparison used DeepSeek readings recorded outside the repository.

**(c) Corrected wording.**
- TD:14: "A language model only reads text, and in live mode picks an intent or a read-only question from closed lists; it
  never decides, prices or executes."
- Figure 2 caption and the figure: "Untrusted text enters on the left, where a model may read it (the compiler). In live mode a
  model may also label an owner's chat request or route a question to read-only tools; its output is a closed-list choice that code
  validates." Redraw `fig1-architecture.png`: replace "the only model step" with "model or rules", and add a small "classifier /
  router (live, closed lists)" box on the chat edge.
- Table 4, Compiler row: "the main model-backed role (untrusted)".
- TD:240 (Table 5, Cache row): "Recorded readings keyed by a hash of the documents and the prompt version. The 19 shipped
  recordings were made by the rules grammar; no model output ships. A message not in the cache goes to the rules grammar."
- TD:267-268: "2. **Real engine, offline.** The full API with the rules grammar (and its recorded readings). This is the demo,
  the tests and every evaluation figure unless stated otherwise." Same fix at TD:935 ("replays recorded model readings" →
  "reads with the rules grammar") and TD:1026-1027.

## 9. Hard rules, owner approval thresholds and the APR ceiling

**(a) What the document says.** TD:295-296 lists "APR at most 15%" beside the covenants; TD:535 lists "the APR ceiling" among
the verifier's rules; TD:757 Tier 1 "below the rate ceiling"; TD:765 Tier 2 "a draw above the rate ceiling"; TD:787 "The owner
cannot waive a hard rule by approving."

**(b) What is true.**
- **Unwaivable on a buyer's request (REJECT, and "accept as asked" refused):** the aggregate and per-buyer concession caps,
  an uncurable reserve breach, DSCR, leverage and clean-down breaches, an invalid mandate and an unknown counterparty
  (`app/verifier/evaluate.py:190-193, 447, 463-464, 562-573, 726-758`). The owner's accept route answers 409 OVER_MANDATE for a
  cap code and 409 NOT_ACCEPTABLE for any outcome other than ACCEPT or NEEDS_OWNER_APPROVAL (`app/api/accept.py:97-107,
  372-379`); the executor backs this (`executor.py:626-631, 995-1004`) and re-checks the caps at commit (`:1117-1134`).
- **Price rules** (implied early-pay APR above the ceiling, the discount cap, above break-even, not needed, dearer than the
  plan; `evaluate.py:91-93, 299-308, 369-374`) give COUNTER or REJECT; the asked terms cannot be accepted as asked either. Only a
  re-checked counter can be accepted (`evaluate.py:712-720`).
- **Exception:** a *curable* reserve breach is not hard; the owner may accept as asked and the receipt says the gap stays open
  (`accept.py:129-137`).
- **Unwaivable on funding (admission, for everyone, also when an approval re-runs):** what the engine cannot book, a live
  early-pay hold, covenant breaches and the reserve test (`app/funding/admission.py:6-13, 119-152`).
- **Owner approval thresholds (Tier 2):** terms lengthening; rebates, price, volume or other non-early-pay terms; a
  commitment's future value above ¥100,000 (strictly greater; `tiers.py:108, 117`; `fixtures/scenarios/golden_sme.json:360`);
  a draw on an uncommitted facility; applying for or adding a facility; a capex commit; a contract set-up or undo; a receipt not
  from the bank feed or owner; and **an agent-requested funding leg above the rate ceiling** (rate strictly above `max_apr_bp`,
  `app/funding/rates.py:161-168`).
- **The APR ceiling therefore plays three roles:** (1) a price rule on a buyer's early-pay discount; (2) a verdict rule on a
  lender term sheet, but the owner's `AddFacility` path does not check it (`executor.py:1499-1511`), so it is advisory there;
  (3) for funding, an **approval threshold for the agent only**: `executor.py:852-854` raises to Tier 2 only when the requester
  is not the owner, so **the owner's own draw above the ceiling through `POST /operations` runs at Tier 1**, and an owner may
  approve the agent's leg above it, as the demo does at 32.5% (`docs/deliverables/evidence/demo_walk/operations_log.md:17`;
  this review's `demo_run.py`).
- **Tier 3 (never, for every caller including the owner):** SignPersonalGuarantee, PledgeCollateral, IssueEquity, ChangeMandate
  (`tiers.py:46`), AddFacility by a non-owner (`:94-95`), any unknown operation type (`:98-99`); an approved Tier-3 operation
  stays refused (`SECURITY_SELF_ASSESSMENT.md:250`).

**(c) Corrected wording.**
- TD:295-296: "...DSCR must be at least 1.25× and leverage at most 2.5×. Funding that costs more than 15% a year needs the
  owner's approval."
- TD:787, replace with: "**What approval can and cannot do.** The owner's approval releases a Tier-2 operation; it never
  waives a hard rule. Hard rules are refused for everyone, the owner included: the concession caps, the covenants, a reserve
  breach no committed funding can cure, an invalid mandate, and Tier 3. The rate ceiling is not a hard rule: it decides who may
  borrow. Above it the agent must ask; the owner may approve, or borrow directly."
- TD:757 and 765: keep, adding "when the agent requests it" to TD:765.

## 10. Multi-process concurrency vs the single-API-process restriction

**(a) What the document says.** Table 15 (TD:1014): "Two writers at once | Two processes act on the same books | Eight invariants
hold; a serial replay gives identical books | Concurrency tests, SQLite and PostgreSQL 17". TD:1056: "One worker process only
until PostgreSQL is proven in CI (SEC-11)".

**(b) What is true.**
- `tests/concurrency` spawns two worker **processes that call the executor directly** against one database
  (`tests/concurrency/harness.py:1-15`); it proves the **store's** compare-and-swap and unit of work hold (8 invariants; 3 of 3
  clean PostgreSQL 17 runs on `85309b63` and `70f23ac5`). It does not run two API processes.
- Route-level checks rely on a **per-process lock** (`rt.lock`, e.g. `app/api/accept.py:372`) and each process keeps its own
  clock: with two runtimes on one SQLite file, the second executed a draw dated to an old day after the first advanced the clock
  (SEC-11, CONFIRMED, `FINDINGS_REGISTER.md:220-227`), and two runtimes each passed the accept binding (REVIEWER-CONFIRMED).
  SEC-11 is open by the owner's decision (`FINDINGS_REGISTER.md:84`).
- The restriction is not "until PostgreSQL is proven in CI": it is a code change (read the day from stored state inside the
  unit of work, move route invariants into the executor; `SECURITY_SELF_ASSESSMENT.md:850`). The production image runs one
  uvicorn process by default (`infra/api.Dockerfile:9`, no `--workers`); nothing refuses a second process.

**(c) Corrected wording.**
- Table 15 row: "Two writers on one database | Two worker processes call the executor on the same books at once | Eight store
  invariants hold and a serial replay gives identical books (SQLite; PostgreSQL 17, 3 of 3 runs). This covers the store, not
  two API processes: route checks and the clock are per process, so FLOW must run as one API process (SEC-11)."
- TD:1056: "**One API process only (SEC-11).** A second process keeps its own clock and lock, and route checks such as one
  agreement per request can then be bypassed. Fixing it means reading the day from the store inside each unit of work and moving
  route checks into the executor."

---

## 11. "Only the executor writes"

**(a) What the document says.** TD:14-15 "only one component, the executor, can change the books"; Figure 2 caption (TD:174)
"Only the executor writes"; Appendix B (TD:1090) "The executor (the only writer)"; `SECURITY_SELF_ASSESSMENT.md:87`.

**(b) What is true.** The invariant holds for **typed operations**: every accept, counter, reject, commitment, draw, invoice
financing, repayment, receipt, approval decision, circuit reset, commitment revocation, document confirm or reject, capex
application or commit, facility addition and contract set-up or undo goes through `Executor.execute`, `decide` or a sibling
method, with the tier, the gates and a hash-chained log entry (`app/api/operations.py:78-129, 370-419`; `accept.py:366-415`;
`decide.py:358-375, 522-555`; `outbound.py:489`; `alerts.py:151+`; `capex.py:82-234`; `contract_terms.py:374, 413-468`;
`documents.py:250-283`). The approvals table is written only by the executor (`executor.py:388, 689, 709`). Writes **outside**
the executor:

| Path | What it writes | Changes the books? | Logged in the chain? |
| --- | --- | --- | --- |
| `POST /clock/advance` → `Runtime.advance_to` → `clock._advance_once` (`app/api/clock.py:31-49`; `app/clock/__init__.py:269-344`) | posts scheduled flows, debt service and landing funding; issues recurring invoices; expires or fulfils commitments; state with a version check | **yes** (owner only) | yes, ADVANCE_CLOCK (`clock/__init__.py:341`) |
| `POST /setup/open` (`app/api/setup.py:560-629`) | replaces the books and the mandate, which it signs with the demo key (`:579`) | **yes** (owner, demo mode, blank books only) | starts a new chain with OPEN_BOOKS (`:606`) |
| `POST /demo/reset`, `/demo/restore`, startup seeding (`app/api/runtime.py:175-188, 254-263, 307-341`) | wipes and reseeds books and mandate | **yes** (demo mode or the in-memory store) | no entry for the reset itself; the log is erased |
| `POST /customers` (`app/api/customers.py:187-229`) | the counterparty registry in the state | **yes**: the registry gates documents, invoice financing and the unknown-sender screen | yes, ADD_CUSTOMER, same transaction (`:227-228`) |
| `Executor.propose_commitment` (`executor.py:603-637`; called from `accept.py:382`, `decide.py:522`, `outbound.py:481`) | a PROPOSED commitment | no (proposed only) | no log entry, no mandate or tier check |
| Document intake and refile (`app/api/documents.py:150-230, 286-346`) | contract records | no | refile yes (REFILE_DOCUMENT); intake no |
| Offer intake, evaluation, chat verify (`app/api/offers.py:165-214`; `decide.py:201-231`; `app/nl/context.py:110-111`) | stored offers and verdicts (a verdict later backs a commitment) | no | no |
| Deal facts: mark sent, buyer declined, withdraw, buyer reply (`app/api/decisions.py:82-98`; `outbound.py:348-646`) | decision facts that gate later actions (an OFFERED fact blocks accept, decline, negotiate and `/operations`) | no | no (facts table) |
| Customer inputs, pilot journal (`app/api/customer_inputs.py:118`; `app/api/pilot.py:40`) | advisory inputs, read by strategy views only | no | no |
| Security events, evidence export (`app/api/auth.py:120-145`; `app/api/read.py:278-283`) | append-only security events; an export row on GET | no | security events are append-only but not chained |
| Process memory (`runtime.py:54-60, 103-132`; `app/nl/sessions.py:76-175`; `app/api/ratelimit.py`) | chat sessions with pending plans, budgets, caches | no | no |

**(c) Corrected wording.** TD:14-15: "Deterministic code decides, and every operation that commits the business or moves money
goes through one component, the executor, which checks it and records it in a tamper-evident log." Appendix B row: "The
executor (the only path for typed operations) and the commitment lifecycle". Add to section 04, after "The record": "Outside the
executor, three owner or demo actions also change the books, each logged: moving the simulated clock (ADVANCE_CLOCK), opening
books from setup (OPEN_BOOKS, demo mode) and adding a customer (ADD_CUSTOMER). A demo reset erases the books and the log (demo
mode only). Stored offers, verdicts, contract readings, deal facts and chat sessions are records, not books."

## 12. Placeholders, video timestamps, screenshots, names, references and reproduction commands

**Template placeholders.** The technical document has none. `docs/SECURITY_SELF_ASSESSMENT.md` still has `[TEAM: ...]` at
lines 7 (team name), 9 (submission date), 556 (who did the principal audit), 559 and 581 (who ran the external red team; attach
its report), 625 ("Accepted by [TEAM]"), 698 (live-mode indicator), 768 (licence) and 1022 (E9 report location). The same lines
are in the `08c8dac0` version. Fill: team ISMOGGER (TD:6), 20 October 2026 (TD:9); the rest need the owner.

**Video timestamps (TD:1137-1149).** They match `docs/deliverables/video/README.md:17-35, 43-59` (build `ed5e0932`, 18 Oct, 4:22
and 17:31). But: (1) `ed5e0932` predates round five, batch 10's recording fixes (`94e36d49` pasted approval, `893df906` Home
truthful after reset), the Ask full-page card, "can I pay everyone" and tonight's changes, so the video shows an older build;
(2) neither video file is in the repository (the full tour is git-ignored at 129 MB, `video/README.md:43`); (3) in the 5-minute
cut the buyer's request is sent in the buyer's role with no channel key (`video/README.md:74-75`), i.e. as an anonymous proposal.
Wording: "Two recordings of build `ed5e0932` (18 Oct), before the last Ask FLOW and security fixes; the screens may differ
slightly from the submission build."

**Screenshots.** All figures referenced exist. Screenshots date from 17 Oct (`shot1`, `shot2`, `shot9` at `29332814`; `shot3` at
`170eb858`; `shot6` at `3824f954`) and 18 Oct (`shot10` at `dc6f0bad`, before the Ask full-page card `28738f19`). Not compared
visually with the submission build by this review; re-shoot `shot10` at least. `figures/fig1-architecture.png` says "the only
model step" (item 8) and "every outcome, refusals too" for the log (only executor outcomes are chained; refusals before the
executor are security events).

**Obsolete names.** The technical document says FLOW throughout. "TermsLedger" remains in `SECURITY_SELF_ASSESSMENT.md:31`
("TermsLedger v2 (FLOW)"), the findings register's title (`FINDINGS_REGISTER.md:1`)
and the code (`termsledger-api`, `TERMSLEDGER_*` variables, `termsledger.db`; `README.md:27-28` explains this). Add to TD section
05: "The code and its variables still use the working name TermsLedger (`TERMSLEDGER_NO_DOTENV` etc.); it is the same system."

**Inaccurate references.**
| TD line | Says | Correct |
| --- | --- | --- |
| 35, 985 | "#161, a hash that differs by machine" | a stale pin, closed since `29fa0ea2` (item 2) |
| 373-374, 926 | router review "pending" | reviewed on `6d2b6941`; fixes in `70f23ac5` (item 1) |
| 884, 922 | v3 "certified 260" | v3 on this base: 261 on `85309b63`; 279 on `70f23ac5` once `08c8dac0` is merged (item 1) |
| 993 | "figures in Tables 9 and 6" | Tables 9 and 10 |
| 995 | `scripts/eval_contracts.py` | `scripts/evaluate_contracts.py`; data outside the repository |
| 996 | "105 routes on `b4167053` (100 on `975e082f`)" | 105 under `app/api` + `/health` = 106 now; 99 + 1 = 100 then (claim register C3) |
| 1056 | "One worker process only until PostgreSQL is proven in CI" | code change needed (item 10) |
| 240, 267-268, 935, 1026 | "recorded model readings" | the shipped recordings are rules-grammar output (item 8) |
| 713 | 87 turns | 88 turns on `571ea64f` |
| 33, 715, 991 | 327/345, 3 wrong (0.9%) | 326/345, 4 wrong (1.2%) on `571ea64f` |

Stale committed evidence a judge may open: `services/api/evals/judge/judge-report.md` (16 Oct, 259 attacks); `services/api/evals/
latest_report.md` (5 Oct); `services/api/evals/contracts_heldout_report.md` ("pending"); `docs/deliverables/evidence/
demo_run_output.txt` (16 Oct, says ¥162,800 unpaid; today ¥160,000); `FINDINGS_REGISTER.md:56-72` ("not yet in dev");
`SECURITY_SELF_ASSESSMENT.md:33` ("100 API routes"); `docs/adr/0015-ask-router.md:3-4`. Regenerate or label each.

**Incomplete reproduction commands (Table 14, TD:981-996).**
- `scripts/run_scenarios.py --inproc` and `scripts/analysis/autonomy_funnel.py ...` lack the interpreter: use
  `uv run --project services/api python scripts/run_scenarios.py --inproc` (and `PYTHONUTF8=1` on Windows).
- The attack command needs `TERMSLEDGER_NO_DOTENV=1` too, and **overwrites the committed** `services/api/evals/security/
  latest_report.*`; `judge_eval.py` without `--out` overwrites `services/api/evals/judge/judge-report.*`. Say so, or add `--out`.
- `uv run pytest` (services/api): tests opt in to demo mode through `tests/conftest.py`; on Windows add `SKIP_PERF_BENCH=1`.
- The contract evaluation cannot be reproduced: its 70 contracts are outside the repository.
- PostgreSQL concurrency needs `TERMSLEDGER_TEST_DATABASE_URL` for an empty local database.
- TD:940-941 "Run it": add the prerequisites (uv with Python 3.12, Node 22+, pnpm) on the same line.

---

# Task 3. Security-control facts for the editor

All from `571ea64f` unless marked. Paths under `services/api/` unless they start with another folder.

| Control | Fact | Evidence |
| --- | --- | --- |
| **Authentication** | Five credentials by header: `X-Owner-Token`, `X-Agent-Key`, `X-Bank-Feed-Key`, `X-Counterparty-Key` (mapped to a buyer id), none. Constant-time compare (`hmac.compare_digest`). Published demo values work only with `DEMO_MODE=1`; `DEMO_MODE` is off by default. Unset owner token outside demo mode: 503 on owner routes. A body `requested_by: OWNER/SYSTEM` without the matching credential becomes AGENT; approvals and circuit resets take the actor from the token. Unverified observation: a non-ASCII owner, agent or bank header may raise in the rate limiter and give a plain 500 (not exercised) | `app/api/auth.py:25-80, 155-175`; `app/config.py:52-56`; `app/api/operations.py:82-85, 366-377, 402`; `app/api/ratelimit.py:73-77` |
| **Signed mandate and key custody** | Ed25519 (PyNaCl) over sorted-key JSON; the executor pins one public key (`OWNER_PUBLIC_KEY_HEX`, or the demo key in demo mode) and refuses to start without one. The demo private key is committed (`fixtures/keys/owner_demo_ed25519.json`, labelled DEMO ONLY). Setup signs the new mandate on the server with the demo key, demo mode only; its "signature" step re-types the owner token. No route revokes, renews or re-signs the mandate (R-14); `ChangeMandate` is Tier 3. One person holds the token and the key (R-2) | `app/mandate/signing.py:13-56`; `app/mandate/validity.py:9-70`; `app/api/runtime.py:284-293`; `app/operations/executor.py:320-321, 930`; `app/api/setup.py:568, 579, 88-93`; `app/mandate/tiers.py:46` |
| **Exact-offer binding** | A commitment binds offer id and version, the verdict, a random 128-bit nonce, the terms hash (SHA-256 of canonical obligations) and an expiry day. The executor finds it by constant-time nonce match and requires the terms hash and value to equal the verdict's bound terms or one of its counters | `app/commitments/lifecycle.py:90-157`; `app/commitments/terms.py:21-30`; `executor.py:861-870, 963-1004` |
| **Nonce** | Single use (stored in `used_nonces`, append-only); reuse or mismatch → REPLAY. Exception: the chat path uses a deterministic nonce derived from the session key and verdict | `lifecycle.py:149-152`; `executor.py:698-702`; `app/nl/pipeline.py:129-146` |
| **Expiry** | `day > expires_day` → COMMITMENT_EXPIRED; mandate expiry refuses every operation except a bank or owner receipt and an owner repayment | `lifecycle.py:153`; `SECURITY_SELF_ASSESSMENT.md:271-275` |
| **Stale-state checks** | Operation day must equal the executor's day (STALE_OPERATION). At commit: named invoices still owed, one live agreement per request, caps re-checked, and a verdict on older books re-verified (STALE_VERDICT unless still ACCEPT/NEEDS_OWNER). Owner routes bind the verdict id and state version (409 VERDICT_CHANGED, BOOKS_CHANGED); the state is written with compare-and-swap | `executor.py:669-670, 703-717, 1077-1146`; `app/api/runtime.py:83-101`; `app/api/accept.py:296-318` |
| **Approval semantics** | A Tier-2 operation is stored as canonical JSON; only the owner may decide (others refused and logged as PRIVILEGE_ESCALATION); decided once (executor and database triggers; a decision the log already holds is refused, SEC-08); approval re-runs every gate except the queue, dated today, against the current mandate and admission. "Accept as asked" approves its own queued item in the same click. Open: a refused re-run leaves the row APPROVED (SEC-27, deferred) | `executor.py:360-416, 689`; `app/persistence/guards.py:55-136`; `migrations/versions/0009_audit_guards.py`; `accept.py:390-393` |
| **Idempotency** | Each operation carries a key; EXECUTED or PENDING entries make a resend DUPLICATE; a refused key may run again; the same key for a different operation is REPLAY with a security event | `executor.py:757-796` |
| **Negotiation transitions** | Simulated buyer: `/negotiate` under the process lock, optionally bound to verdict, counter and books version (409 COUNTER_CHANGED, BOOKS_CHANGED); sent outside: an OFFERED fact bound to the message hash blocks every other answer (OUT-1, OUT-1b); withdraw appends a fact, never deletes. Keyed buyer chat executes at Tier 1 (item 5) | `app/api/decide.py:350-391, 410-486`; `app/api/decisions.py:101-115`; `app/api/outbound.py:348-396, 554-601`; `app/nl/offers.py:319-367` |
| **Owner-reported acceptance** | The owner reports the buyer's yes; bound to the sent message, terms hash, expiry, state version and mandate; executes AcceptOffer as the owner; the buyer is not authenticated and evidence text is stored unverified. A pasted reply is not bound to the message hash | `outbound.py:455-513, 610-646` (item 6) |
| **Prompt injection** | Extraction schemas have no operation, approval, tier or facility field (`extra="forbid"`); every term must quote the source (exact find, whitespace-tolerant fallback); values parsed from the quote; coverage proof defaults to false and is forced false on reader disagreement; an AST test keeps the verifier from reading free text; owner chat executes only a whole-message closed command (≤ 160 characters, one RMB amount); the classifier's list excludes APPROVE/REJECT and its output never executes; buyer turns never reach the classifier. Detection is logged but refusal does not depend on it | `app/compiler/schema.py:9, 29-30`; `app/compiler/grounding.py:97-162, 342-352`; `app/domain/models.py:204-207`; `app/compiler/cross_check.py:81`; `tests/verifier/test_invariants.py:20-62`; `app/nl/consent.py:1-40, 159`; `app/nl/classifier.py:33-34`; `app/nl/service.py:173-174, 346-347` |
| **Data sent to providers** | Live mode only. Compiler: system prompt + schema + the full documents (redacted). Classifier: the redacted message. Router: a fixed system prompt with the tool catalogue + the redacted question (≤ 500 chars) fenced as data; `build_prompt` takes no books. Providers: Anthropic (SDK default endpoint) or DeepSeek (`api.deepseek.com`, `deepseek-flash` alias); no zero-retention header; region and retention not set. With DeepSeek primary, text goes to a provider in mainland China; with Claude, outside it (PIPL assessment not done) | `app/compiler/prompts/__init__.py:173-178`; `app/nl/classifier.py:133-137`; `app/nl/router/route.py:61-123, 425-434`; `SECURITY_SELF_ASSESSMENT.md:685-700, 765`; ADR-0015 §8 |
| **Redaction limits** | Six identifier kinds; names, amounts, clauses, chat ids, IBANs, full-width digits, unlabelled addresses pass (PRIV-4/5 open, Moderate); `LLM_REDACT=0` disables it everywhere; `pnpm demo --live-llm` lets a shell `LLM_REDACT=0` through | item 7 |
| **Logging** | Per model call: backend, model, outcome, prompt version, document hash, latency; redaction counts per kind; router: a 16-hex unsalted hash of the redacted question, tools and outcome (not secret against a dictionary). No document or question text is logged (code search). Stored text: the intent cache would keep original text when recorded (none ships); the route cache keeps the redacted question. Access log keeps method, path with query string, status and client address | `app/compiler/service.py:98-105, 127`; `app/compiler/redaction.py:269-272`; `app/nl/router/route.py:346-347, 418-445`; `app/nl/classifier.py:108-115`; `SECURITY_SELF_ASSESSMENT.md:672` |
| **Audit integrity** | **Tamper-evident, not tamper-proof.** `entry_hash = sha256(prev_hash + payload_json + result_json)` from a zero genesis, in the same unit of work as the effect; append-only triggers on the log, nonces and security events, decide-once on approvals, no session bypass (0009); `scripts/verify_evidence.py` re-checks an export offline and against a `COUNT:HEAD` checkpoint. Limits: the API connects as the table owner, so a database administrator can drop triggers and rewrite the chain consistently (R-13); there is **no external anchor** (the export's head hash is stored in the same database); security events are not chained; demo reset and setup start a new chain | `app/persistence/chain.py:4-36`; `app/persistence/guards.py:19-23, 55-188`; `app/persistence/sql_store.py:137-147, 194-222`; `scripts/verify_evidence.py:15-22, 113-142`; `infra/docker-compose.yml:7, 17`; `app/api/read.py:277-283` |
| **Partial execution and recovery** | Each operation is atomic; a plan is not (SEC-28, Medium, deferred). Chat "go ahead" stops at the first leg not executed and says "stopped after step N of M"; `/alerts/{id}/act` continues past a queued leg; `/negotiate` runs every leg and says the gap is funded before the results exist. Nothing reverses or resumes legs; recovery is manual (read Activity, compensate, ask again) | `app/nl/plans.py:211-254`; `app/api/alerts.py:236-241`; `app/api/decide.py:358-375, 534-555`; `SECURITY_SELF_ASSESSMENT.md:346-383` |
| **Deployment configuration** | `pnpm demo`: API on 127.0.0.1, in-memory books, `TERMSLEDGER_NO_DOTENV=1`, `DEMO_MODE=1`, cache mode unless `--live-llm`, every feature flag on; the web dev server listens on all interfaces (no `-H`, DEMO-L1) and bakes the demo owner token. Compose: `DEMO_MODE=0`, but no `OWNER_PUBLIC_KEY_HEX` (startup fails), no provisioning, no `COUNTERPARTY_KEYS`, anonymous intake on by default, web on all interfaces over HTTP, web build baked to `localhost:8000`, containers as root, one uvicorn process. No global exception handler on this base (a non-409 error is a plain 500 without CORS headers; (e) is pending merge) | `scripts/demo.mjs:179, 283-333`; `apps/web/lib/config.ts:18`; `infra/docker-compose.yml:23-36`; `infra/web.Dockerfile:7-8`; `infra/api.Dockerfile:9`; `app/config.py:107-112`; `app/api/errors.py:45-47`; `app/main.py:53, 71-77` |
| **Open blockers** | SEC-06 (no runnable production configuration), SEC-11 (one API process only), R-2 (single key holder), R-13 (no external anchor; DB owner can rewrite), R-14 (no mandate revoke or renew route), SEC-19 (anonymous offer can name a buyer; switch `ANONYMOUS_INTAKE=0` exists, default on), SEC-28 (partial plans), R-3 (agent Tier-1 reach, no aggregate draw limit), PRIV-4/5, OPS (no backup, restore, write switch, PostgreSQL in CI), S3 (browser injection not penetration-tested), LIVE (live mode never certified). Pending fixes not in `70f23ac5`: REG-8, REG-9, CT-2b (`sec/round-six` `563de405`) | `SECURITY_SELF_ASSESSMENT.md:813-852`; `FINDINGS_REGISTER.md`; `08c8dac0` register rows 79-81 |

**Readiness.**

| Deployment | Verdict | Basis |
| --- | --- | --- |
| Local demo on loopback (`pnpm demo`, cache mode, one process, synthetic data, presenter holds the credentials) | **GO** for `70f23ac5` (certified for scope S with contract terms and the router on; record on `docs/assessment-final`). The submission build adds uncertified chat and Ask FLOW changes; this review's offline catalogue run on `571ea64f` shows 0 harm in 279 cases | `08c8dac0`; this review |
| `pnpm demo --live-llm` | **Not assessed.** Live mode is excluded from every certification; the language boundary has never run against a live model; redaction is pattern-based | `SECURITY_SELF_ASSESSMENT.md:24, 852` |
| Demo reachable over a network | **NO-GO** until a tested profile exists (changed credentials and signing key, TLS proxy with per-client limits, anonymous intake off, docs hidden, one worker, a stop procedure, sweep and browser checks against it). Note DEMO-L1: even the local launcher's web server listens on all interfaces | `SECURITY_SELF_ASSESSMENT.md:988`; `scripts/demo.mjs:330` |
| Production with real customers, documents or money | **NO-GO.** No runnable configuration (SEC-06), single-process (SEC-11), no mandate revoke (R-14), single key holder (R-2), no external anchor (R-13), partial plans (SEC-28), anonymous provenance (SEC-19), redaction gaps and no PIPL assessment, no backups, no penetration test; every counterparty, lender and bank feed is simulated | `SECURITY_SELF_ASSESSMENT.md:989`; `docs/security/RELEASE_GATE.md:45-57` |

---

# Top corrections by impact

1. **The 15% APR ceiling is not a hard rule for funding** (item 9): the agent must ask above it, but the owner may approve
   (the demo does, at 32.5%) or draw directly at Tier 1. TD:787 "the owner cannot waive a hard rule" sits beside "APR at most
   15%" listed with the covenants. Reword it as an approval threshold.
2. **A keyed buyer's message executes at Tier 1 with no owner step** (item 5): Figure 1's "Nothing is sent or agreed without
   the owner" is false for that path.
3. **No model output ships** (item 8): "recorded model readings" in Table 5, the "three ways to run" and the demo text describe
   rules-grammar output; the diagrams' "only model step" is wrong in live mode.
4. **Assessment status** (item 1): v3 on this base says `85309b63` / 261 cases; the `70f23ac5` certification (279) exists only
   on `docs/assessment-final`; nothing after `70f23ac5`, including tonight's features, is certified. "260" is wrong everywhere.
5. **"Optimal" funding** (item 4) and **"every target met"** (item 3) need their scope.
6. **Owner-reported acceptance is not authenticated** (item 6); the pasted reply is not bound to the message hash.
7. **"Only the executor writes"** (item 11): true for typed operations only; the clock, setup, customers and demo resets write
   the books outside it.
8. **Redaction** (item 7): `LLM_REDACT=0` bypasses all three model uses, and `--live-llm` lets it through from the shell.

# Could not verify

- Tonight's (b) customer loss, customer stopping orders and DSO answers, and (e) the JSON 500 handler: no commit found on
  `origin` at the time of this review; described from the owner's instruction only.
- Whether screenshots match the submission build (not compared visually); whether the Business-mode acceptance still skips the
  planned funding; the non-ASCII header 500 (code reading only).
- The contract-reading figures, the two SME interviews, the external red-team report and the competitor descriptions: the
  sources are not in the repository.
- No full `scripts/evaluate.py` run after `975e082f` (8 minutes; not re-run here); no live-browser run after `975e082f`.
- No live-model run of any kind (forbidden for this review).
