# FLOW evaluation review: what each result measures, and how far it can be trusted

Reviewer: evaluation reviewer (AI agent, Claude Code), 18 Oct 2026, branch `docs/sub-evaluation` from
`origin/docs/techdoc-chat-fixes` @ `571ea64f`. Documentation only: no application code was changed.

**Scope.** Every evaluation result in `docs/deliverables/technical_document.md` (Tables 1, 8, 9, 10, 11, 13, 14, Figures
5 to 8 and the inline figures in sections 02 and 03), plus the live-provider stress test of 18 Oct 2026. For each result:
what was measured, how, on which data, with which denominator, its evidence class, its limitation, and the wording the
technical document should use.

**What was re-run here (offline only: `LLM_MODE=cache DEMO_MODE=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory`; no
network, no live model, `.env` never read).** The full offline evaluation (`scripts/evaluate.py`, 707 s), the
held-out-3 and held-out-2 offers suites, the autonomy funnel, the owner-question bank, the everyday-wording set, the judge
pack (`scripts/judge_eval.py`), the router and answer-card tests, and a re-scoring of the recorded contract readings with
the repository's own `score` function. Results: `work/eval/offline_reruns_20261018.json`,
`work/eval/contracts_*_fields.json`. The live stress test was **not** re-run (that would call a provider); its summaries
are copied to `work/eval/live_*.json`, and the router log was joined to the questions offline
(`work/eval/live_router_outcomes.json`). The raw API log was not copied.

---

## 1. Corrections, by impact

1. **"0 wrong autonomous accepts" is a post-tuning figure on 3 accepts, and the untuned figure is 6.** The first runs of
   both held-out sets, before ADR-0005, produced **6 wrong autonomous accepts** (held-out 3: 4 of 8 accepts; held-out 2:
   2, H2A06 and H2X03). Table 9 omits held-out 2's first run and says only the held-out-3 first row is untuned; that is
   not true. Today FLOW accepts **3** of 115 messages on its own, so "0 of 3 wrong" is the safety evidence, not "0 of
   115"; the safety comes from ADR-0005 refusing to act alone, which costs usefulness (3 of 14 good offers). Table 1's
   Safety row must say this.
2. **"303 of 503 owner questions answered directly from the books" counts 75 correct refusals as answers.** 75 of the 303
   are the not-in-books category, where "answered" means the honest "the books do not hold this". Of the 427 turns the
   books can answer, FLOW answers **228 (53%)**, partly 45, declines 154, wrong 0. The bank is also the development
   target (the 30 questions built first, 9 manual scoring overrides): it is a tuned set.
3. **The everyday-wording wrong rate is 2.1% on the held-out part, not 0.9%.** All 3 wrong answers at `b4167053` were in
   the held-out part (3 of 142); 0.9% is over all 345, most of which were tuned on. On `571ea64f` the figure is 326/345
   with 4 wrong: the new "pay everyone" answer (LIQ-10) now takes a tuning item labelled LIQ-01. That is label drift, not
   necessarily a worse answer, but the published 327/345 does not hold on the submitted build.
4. **Contract reading leads with the tuned 98%; the honest figure is 75% of fields on 17 readable unseen contracts, 45% on
   all 30.** 13 of the 30 held-out contracts (scans and photos) are refused before any reading, so field accuracy over the
   whole held-out set is 215/474 (45%). The repository holds none of these figures (`contracts_heldout_report.md` says
   "pending"); the documents, keys and recorded readings live outside the repo; Table 14's command
   (`scripts/eval_contracts.py`) is `services/api/scripts/eval_contracts.py` and is not runnable without that data.
5. **The attack catalogue never put an attack in front of a real model, recorded or live.** In the 18 Oct report the
   compiler read attack text 78 times with the rules grammar and 4 times with a scripted "compromised model"; 0 times from
   recorded model readings. Table 13's "with recorded or scripted model answers" overstates model coverage. The live run's
   8 attack prompts reached the Ask router **0** times, and had no state-based harm oracle.
6. **"Offline evaluation: every target met" (Table 14) holds only because the default offers suite is held-out 1, which was
   relabelled and tuned on.** On held-out 3 the material-error target (3/51, 5.9% > 5%) and the zero-silent-error target
   (4) still fail on `571ea64f`.
7. **Verdict agreement is confounded by policy drift.** 14 of 110 labels (7 per set) disagree with today's verifier given
   the true terms (labels written 1 Oct, before ADR-0007). Reading-only agreement (compiler verdict = today's policy
   applied to the true terms) is **50/63 (79%)** on held-out 3 and **44/47 (94%)** on held-out 2, against 44/63 and 38/47
   against the frozen labels. Both should be shown; neither is untuned.
8. **The router now has a live run, so "no live run is recorded" (Table 10) is out of date**, but the run measured
   availability and latency, not correctness. Of 589 sweep questions, 63 reached the router: 33 answered, 29 "cannot
   answer yet", 1 rejected. One unblinded reviewer (this agent) graded the 33 answers: 22 right, 10 partial, 1 wrong topic.
9. **In live mode the older intent classifier turned 4 of 589 questions into proposed plans** ("What's the cheapest way
   to raise ¥200,000?" and its Chinese twin proposed the ¥405,000 standing plan, ignoring the amount asked; "what do we need
   to do to not go broke"; "最快多久能拿到钱" proposed a Tier-1 early-pay counter). Each waits for "go ahead"; the stress test
   never sent one. "A question is answered, never acted on" is true offline; in live mode it should say "never executed".
10. **The language-boundary "0 wrong-and-material" (231 items, 3 Oct) consulted no model in its cache run** (0 of 140
    model-path items answered by a model, against the harness's own 95% floor); the scripted-model run reached 85.4%,
    also below the floor. It is a rules-path result plus a scripted-model result, on a 3 Oct build.
11. **Latency figures are single-machine, in-process and load-sensitive.** The same command on this machine under
    contention gave Scene 1 p50 4.8 s against the document's 1.08 s. Quote them as an order of magnitude with the
    environment, never as a performance claim.
12. **Committed artefacts disagree with the document.** `services/api/evals/latest_report.md` is from 5 Oct (`d4b410f`);
    `services/api/evals/judge/judge-report.md` reports 259 attacks; `accuracy_summary.md` has 1 Oct figures. A judge who
    opens them sees different numbers. Regenerate or label them as historical.
13. **Test counts are not correctness.** 9,085 / 169 / 445 / 139 (Table 1, 14) were not re-run here (lead's record); the
    router-test count is 452 on `571ea64f`, not 433. Counts move with every branch and measure suite size, not accuracy.

---

## 2. Evidence classes used below

| Class | Meaning | What it can support |
| --- | --- | --- |
| **untouched held-out** | Labels written before the scored code had seen the items; scored once, and that first score is the one quoted | An estimate of accuracy on similar new inputs |
| **after tuning on failures** | The same items re-scored after fixes were chosen by studying their misses (or the set was the development target) | That the fixes work on those items; not generalisation |
| **recorded model replay** | A model's past output replayed from the cache, offline | What that model said once, on that prompt version; not today's model, not variance |
| **live provider calls** | DeepSeek (`deepseek-flash` alias; underlying version not recorded) called live | One sample of a non-deterministic provider on that day |
| **rules-only** | The deterministic grammar, no model | The offline path the demo and CI run |
| **scripted/mocked model** | A fake backend returning designed (often hostile) outputs | That the validators reject what was scripted |
| **unit/invariant tests** | Pytest or hypothesis checks against an oracle or invariant | The cases and properties written; not coverage of unwritten ones |
| **browser tests** | Playwright against mock data or a local live API | That the UI paths written work on one browser setup |
| **deployed-system tests** | Tests against a deployed, networked system | **None exist.** Every result is local, loopback or in-process |

A result can carry two classes (for example "untouched held-out; recorded model replay").

---

## 3. Results table

Wilson 95% intervals are given for the main proportions; they assume independent items and are too narrow where items are
paired or clustered (section 4.3). "TD" = technical document.

### 3.1 Engine, router and agent tasks

| Result (TD) | Measured | Method | Data | Denominator | Class | Limitation | Final wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Financial values exact to the fen, 67/67 (T1, T10) | Each golden value recomputed through the modules' public interfaces equals the oracle's | `evaluate.py --suite financial`; oracle `fixtures/golden/compute_golden.py` (Fraction/Decimal, imports no app code) | The golden books and fixed variants | 67 values | unit/invariant tests | Both implementations come from the same team and the same ADRs, so a shared misreading of a rule passes; mostly one set of books. Re-run 18 Oct: 67/67 | "67 of 67 golden values match an independently written oracle to the fen (same specification, same team)" |
| Covenant and capex values 27/27; boundaries 20/20 (T1, T10) | Golden covenant/capex values; each limit holds at the threshold and breaks one unit past it | `--suite financial`, `--suite covenants` | Golden books, modified per case | 27 values; 20 boundary pairs | unit/invariant tests | Boundaries chosen by the authors; 2 breach-month checks only. Re-run: same | as is, with "on the golden books" |
| Router optimal on 26/26 (T1, T10, §03.2) | Router's runnable plan within ¥1 of an exhaustive brute force over runnable levers | `--suite funding`, 10 designed + 16 seeded random scenarios, 180 s budget per scenario | Golden-book variants (seed 20261001) | 26 scenarios | unit/invariant tests | The brute force is independent search code but uses the same projection engine (`app.financial.project`) to judge admissibility; budget hit on 2 priced cases. Re-run: 26/26 | "Within ¥1 of a brute-force search on 26 of 26 scenarios (the search is independent; the cash projection both use is the engine's own)" |
| Router vs "line first" (T10) | Cost against a like-for-like baseline restricted to runnable actions | `scripts/analysis/stress_and_baseline.py --only baseline` | Same 26 | 18 comparable: cheaper 3 (¥169.78), equal 15; 1 feasible where baseline is not | unit/invariant tests | The gate's own E9 row (9/26, saving ¥−3,491.40) uses unrunnable levers and must not be quoted | as is (TD wording is already fair) |
| 19 of 26 plans runnable today (T10) | Plan category per scenario | as above | 26 | 26 | unit/invariant tests | — | as is |
| Honest no-deal 7/7 (T10, T15) | Hard-line simulated buyer ends in NO DEAL in 3 rounds, gap still funded | `--suite no_deal` | One scenario, simulated buyer | 7 checks on 1 run | unit/invariant tests (simulated counterparty) | One buyer model, one reservation; the buyer kernel is FLOW's own code | "In the one hard-line scenario tested, …" |
| Stress tests (T11) | Effect of late or partial payment, lower EBITDA | `scripts/analysis/stress_and_baseline.py` | Golden books, 3 stresses | 3 | unit/invariant tests | Three hand-picked stresses | as is |
| 49/49 scripted tasks (T1, T10) | Each scripted conversation's turns meet the script's own expectations, chain verifies | `run_scenarios.py --inproc` / `judge_eval.py` | `evals/e2e/scenarios.yaml`, written by the team | 49 tasks, 88 turns on 571ea64f (87 before) | rules-only + recorded model replay; scripted tasks | Pass conditions written by the people who built the handlers; tasks are not a sample of real owner sessions. Re-run: 49/49 | "49 of 49 scripted conversations, written by the team, pass their own checks" |
| Demo walk, chain valid, tampered copy rejected | 17-step walk exits 0; hash chain verifies; an edited copy fails | `judge_eval.py` | Golden story | 1 walk | unit/invariant tests | One tamper (one field of one entry) | as is |

### 3.2 Reading buyer messages (compiler) and autonomy

| Result (TD) | Measured | Method | Data | Denominator | Class | Limitation | Final wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Held-out 3, first run: 33/63 (52%), material 4/51, silent 7, **4 of 8 accepts wrong** (T9) | Verdict = label; booked obligations vs labels | `evaluate.py --suite offers --heldout fixtures/heldout3`, 1 Oct, before ADR-0005 | 66 WeChat/email-style messages (36 en, 30 zh/mixed), 15 must-abstain, 3 unlabelled; labels committed before the run | 63 labelled (verdicts); 51 not must-abstain (material) | **untouched held-out**; rules-only (no item in the cache) | Labels by one AI agent (Claude Opus, separate session) with disclosed deviations and judgement calls (0.88% boundary, H3-I05 convention); 20 pairs. 95% CI 40–64% | "On 63 unseen labelled messages, read by the rules grammar, verdicts matched the label for 33 (52%); 4 of the 8 messages FLOW accepted on its own were misread. This led to ADR-0005." |
| Held-out 2, first run: 28/47 (60%), material 3/37, silent 5, **2 accepts wrong** (missing from TD) | as above | same, `fixtures/heldout2`, `dev e34af1a`, 1 Oct | 49 messages (17 zh/mixed), 12 must-abstain, 2 unlabelled; labelled before the compiler was read | 47; 37 | **untouched held-out**; rules-only | Same labeller type; 13 pairs; CI 45–72% | Add a row: "Held-out 2, first run (1 Oct): 28/47 (60%), 2 wrong autonomous accepts" |
| Held-out 3 today: 44/63 (70%), material 3/51, silent 4, 0 wrong accepts (T9) | as above | same command on 571ea64f, 18 Oct (re-run here: identical) | as above | 63; 51 | after tuning on failures; rules-only | Failure classes guided fixes; labels frozen at 1 Oct policy (7 drift items); reading-only agreement 50/63 (79%). Targets ≤5% and 0 silent **fail** | "After fixes guided by its misses: 44/63 against the 1 Oct labels, 50/63 against today's policy on the true terms; material errors 3/51 and 4 silent errors (targets not met)" |
| Held-out 2 today: 38/47 (81%), material 0/37 (T9) | as above | re-run here: identical | as above | 47; 37 | after tuning on failures; rules-only | 7 drift items; reading-only 44/47 (94%) | as held-out 3 |
| Held-out 3, live DeepSeek: 42/63 (67%), material 3/51, silent 5, 0 wrong accepts (T9) | as above | `evaluate.py --live`, LLM_LIVE_RAW=1, 1 Oct, `389cfd9` | held-out 3 | 63; 51 | live provider calls; shared gates tuned, prompt not | One run, one day, no repeat to measure variance; old build (before 10+ days of changes); model version not recorded; not re-runnable offline | "One live DeepSeek run on 1 Oct (build 389cfd9): 42/63; not repeated on the submitted build" |
| Form baseline 56/63 (T9) | The labels typed into today's verifier | `evals/forms.py` | as above | 63 | unit/invariant tests (policy vs labels) | It is the verifier against the labeller, not a competitor; with drift it is ≤100% by construction | "Today's verifier agrees with the 1 Oct labels on 56/63; the other 7 are policy changes since (ADR-0007)" |
| "0 wrong autonomous accepts on two held-out sets (115 messages)" (T1, T8) | Accepts at Tier 1 whose label is not accept or that carry a material error | `autonomy_funnel.py` (re-run here: identical) | held-out 3 + 2 | **3 autonomous accepts** (of 115 messages) | after tuning on failures; rules-only | The relevant denominator is 3 accepts (CI 0–56%); the untuned first runs had 6 wrong accepts | See section 6 wording |
| Usefulness: 57/115 answered with no owner; 3 of 14 good offers accepted alone (T1, T8) | Funnel per message | as above | as above | 115 messages; 14 eligible | after tuning on failures; rules-only | "Eligible" uses today's policy, so it moves with policy; 54 autonomous counters/rejects agree with today's policy on every labelled item, which checks reading, not the policy | as is, plus "unnecessary escalation: 11 of 14 good offers (79%); 11 of 58 escalations" |
| Abstention precision/recall (not in TD) | NO_VERDICT when it should / must-abstain caught | offers suite | held-out 3; held-out 2 | 16 and 15; 14 and 12 | after tuning on failures | Over-abstention is safe but costs the owner a review | Add: "abstentions: 14 of 16 needed on held-out 3 (first run: 12 of 38)" |
| "Why a model": rules 0/17 party names, DeepSeek 14/17 (§02) | Party names matching the key | Re-scoring of batch-2 predictions | 17 text-layer unseen contracts | 17 contracts (×2 names) | untouched held-out; recorded model replay vs rules-only | The rules grammar has no Chinese party pattern at all, so it is a straw baseline; the 3 DeepSeek misses are swaps | "On 17 unseen Chinese contracts the rules grammar, which has no Chinese party pattern, found no party names; recorded DeepSeek readings found both for 14 and swapped buyer and seller in 3" |

### 3.3 Contracts

| Result (TD) | Measured | Method | Data | Denominator | Class | Limitation | Final wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 75% field accuracy, batch 2 (T14, §03, Fig 6) | Key items matched (13 scored fields) | `eval_contracts.py score` over recorded readings (re-scored here) | 30 synthetic contracts (6 new types), 17 with a text layer; answer key generated with the documents (seed 202) | 285 key items on 17 docs (474 on all 30) | **untouched held-out; recorded model replay** (DeepSeek, `contract-v1`) | 17 documents, clustered fields (CI 70–80% understated); one generator family with batch 1; unscored fields FLOW cannot express (instrument, pay-when-paid, LPR multiples, delivery); data outside the repo | Section 5 wording |
| 86% after fixes (T14, Fig 6) | as above | 6 fix steps chosen from batch-2 misses | as above | 285 | after tuning on failures; recorded model replay | No longer held out | "86% after five fixes chosen by studying those failures (no longer held out)" |
| 98% batch 1 (T14, Fig 6) | as above | as above | 40 contracts, 30 text-layer | 514 (668 on all 40) | after tuning on failures; recorded model replay | The reader was written against it | Do not lead with it; "98% on the 30 contracts the reader was built on" |
| Scans and photos refused | SCANNED_PDF before any model call | log | 13 of 30 (batch 2), 10 of 40 (batch 1) | — | rules-only | No OCR: a real owner's phone photo gets nothing | as is |

### 3.4 Owner questions (Ask FLOW)

| Result (TD) | Measured | Method | Data | Denominator | Class | Limitation | Final wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 303 answered, 46 partly, 0 wrong, 154 declined of 503 (T1, T10, T14) | Rule-based score per reply (expected figure or yes/no present; refusal intents CANT), hand-checked once on the first baseline | `owner_questions_baseline.py` (re-run here: identical) | 122 questions × en/zh × 1–2 paraphrases | 503 turns = 427 in books + 76 not in books | **after tuning on failures** (the bank was the build target); rules-only | 75 of 303 "answered" are correct refusals; 9 manual overrides; wordings of one question are related (62 of 122 answered in every wording); scorer written by the team | "Of 427 bank turns the books can answer, 228 are answered (53%), 45 partly, 154 declined, 0 wrong by the bank's own scorer; 75 of the 76 questions the books cannot answer are declined honestly. The answer module was built against this bank." |
| 327/345 right, held-out 127/142 (89.4%), wrong topic 3 (0.9%) (T1, T10) | Answer topic id = label (or also-id, page read, honest not-held) | `owner_questions_general.py --part all` | 345 phrasings (219 en, 126 zh) mapped to ~33 answer ids; labels written before the matcher; split 60/40 by text hash | 142 held-out; 203 tuning | held-out part: untouched held-out *but observed* (first measured 130/142, then three precision changes cost three items); tuning part: after tuning; rules-only | Scores the topic, not the figures; all wrong answers fall in the held-out part (3/142 = 2.1%, CI 0.7–6.0%); on 571ea64f: 326/345, 4 wrong (label drift on LIQ-10) | "On the 142 held-out wordings it reaches the right answer for 127 (89.4%) and a wrong topic for 3 (2.1%); on the 203 it was tuned on, 199 and 1 (build b4167053; one more tuning item changes topic on the submitted build)" |
| No question executes or queues anything (T1, T10) | Store fingerprint before/after each turn; EXECUTED/PENDING_APPROVAL ops | both harnesses | as above | 503 + 345 turns | rules-only | Offline only. 3 turns propose a plan awaiting "go ahead", 4 log a Tier-3 security event. Live: 4 of 589 proposals (section 7) | "Offline, no question executed, queued or changed the books; three proposed a plan that waits for 'go ahead'" |
| Router contract: 433 passed, 1 skipped (T10) | Malformed outputs rejected, canary, timeouts, injection, prompt holds no books, 231-item boundary set with a hostile router | pytest | scripted router outputs | 452 passed, 1 skipped on 571ea64f | scripted/mocked model; unit/invariant tests | Count is suite size; scripted outputs are the authors' imagination of failure | "The router's validator rejects every scripted malformed or hostile output we wrote (24 kinds)" |
| Router answer quality (T10: "not measured") | See section 7 | live stress test, one reviewer | 63 sweep questions reaching the router | 33 answered | live provider calls | Single unblinded grader; questions mostly from the tuned bank | Section 7 wording |

### 3.5 Security

| Result (TD) | Measured | Method | Data | Denominator | Class | Limitation | Final wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 harm-oracle violations of 279 (T1, T13, Fig 8) | Store diff after each case: money moved, ops executed, facilities added, concessions booked, commitments activated, protected values in outbound text or readable without the token, canaries, integrity | `python -m app.security.attacks --report`, fresh in-memory runtime per case (re-run via judge pack: 279, 0 harm) | `attacks.yaml` (128 API) + chat catalogue (151) written by the implementation team | 279 cases | rules-only (78 compilations) + scripted/mocked model (4); 0 recorded or live model | Catalogue is the team's own; egress guard never reached by a catalogue case (SEC-32: tested by `tests/egress` instead); no live model; one process; in-memory store | "None of 279 stored attack cases violated the defined harm oracles on build 1294e941 (rules path and a scripted hostile model; no real model read an attack)" |
| 279 of 279 reached their path (T13) | Every declared step ran (NOT_REACHED never counts) | harness, SEC-24 | as above | 279 | unit/invariant tests | "Reached" = the steps ran, not that a model path was exercised | as is |
| 120 of 128 API cases stopped by the named control; 8 known gaps SEC-34 (T13) | Evidence named in each case's expected controls observed | harness | 128 API | 128 | rules-only | 8 cases held by a different control | as is |
| Detection 97.7% / security events 74.2% (T13) | Signal raised / SecurityEvent logged | harness | 128 API | 125/128; 95/128 | rules-only | Over all 279 detection is 70.6%: 79 chat cases are HELD with no signal by design (consent cases) | Add "over all 279, 70.6%; the chat consent cases are judged on nothing running" |
| Positive controls (not in TD) | Six legitimate actions execute through the same runtime and oracle | `tests/security/test_positive_controls.py` | PC-01..06 | 6 | unit/invariant tests | Shows the clean result is not a system that refuses everything; 6 actions only | Add one sentence |
| Mutation tests (not in TD) | One control off at a time; the harness must see harm | `tests/security/test_mutations.py` | 7 controls | 7 | unit/invariant tests | 2 of 7 first found blind spots (terms hash, egress); TC-04 added for one | Add one sentence |
| Tier-3 as a question 18/18 (T13) | Refused, logged, security event | chat catalogue | NL-TQ01..18 = 9 questions × 2 callers | 18 | rules-only | 9 distinct wordings | "9 wordings, each as the owner and as the agent key" |
| Live attack prompts (new) | Reply text and security events | `stress.py hard`, 18 Oct | 8 prompts | 8 | live provider calls | **0 of 8 reached the router**; no store-diff oracle (harm judged from replies); 2 of 8 raised a security event ("transfer ¥500,000 to account …" raised none) | "8 live prompts: none executed anything visible in the replies; they never reached the model router, so they do not test it" |
| External red-team (16 Oct, 100 live calls) | its own | not in the repo | — | — | live provider calls | Not re-run, report not in the repo | as is ("its results are its own") |

### 3.6 Performance and load

| Result (TD) | Measured | Method | Data | Denominator | Class | Limitation | Final wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Router p50 81 / p95 238 ms; chat turn p50 9 / p95 567 ms; Scene 1 p50 1.08 s (T10) | Wall time in process | `evaluate.py` timers, TestClient, cache mode | 26 router scenarios; 87 scripted turns; 5 cold Scene-1 runs | 26; 87; 5 | rules-only + recorded replay | One machine (not named), no network, no browser, no provider; my contended re-run gave Scene 1 p50 4.8 s and chat p95 3.0 s on the same code | "In process on one development machine, cache mode, no network or model: … (n = 26, 87 and 5); these vary severalfold with machine load" |
| "Before they ask" envelope ~17 s first read (§03.9) | Wall time | stated in TD | demo books | not stated | rules-only | Source and n not recorded | "about 17 s on the development machine (single observation)" or drop |
| Live sweep: 589/589 HTTP 200, p50 0.13 s, p95 1.17 s, max 5.79 s (new) | Client wall time per POST /nl, sequential | `stress.py sweep` against a local API on loopback | bank main wordings (244) + everyday wordings (345), demo books | 589 turns | live provider calls | Includes provider latency only for the turns that called it (at least 75: 63 router, 12 classifier, plus any live offer readings); one run, one machine; HTTP 200 is availability, not correctness | Section 7 wording |
| Router call latency (new) | `latency_ms` on `ask.router` log lines | API log | all phases | 69 calls: p50 0.91 s, p95 1.08 s, max 6.18 s | live provider calls | One day, one region, one provider | as stated |
| Bursts of 5/10/20 (new) | Concurrent POST /nl, plus page reads | `stress.py burst`, one trial per size | HARD questions repeated | 5, 10, 20 turns; 3 page reads per burst | live provider calls | Turn max 3.0 / 4.1 / 8.4 s grows with N, consistent with serialised processing; page reads n=3 per burst (max 7.8 s at 20); "one global lock" is the team's diagnosis, not measured here; one trial; p95 of 5 values is the 4th value | "All 35 concurrent questions were answered; with 20 at once the slowest took 8.4 s and a page read waited 7.8 s (3 reads sampled), consistent with requests being processed one at a time" |

### 3.7 Language boundary, tests, deployment

| Result (TD) | Measured | Method | Data | Denominator | Class | Limitation | Final wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 231 adversarial inputs, 0 wrong-and-material (T10) | Class per item (correct, safe clarification/abstention, wrong harmless, wrong material) | `certify_language_boundary.py --backend cache` and `--backend fake`, 3 Oct, `979defb` | `fixtures/certification/language_boundary.yaml` | 231 | rules-only (cache run: 0 of 140 model-path items answered by a model) + scripted/mocked model (fake run: 85.4%) | Below the harness's own 95% model-path floor; build is 15 days old; 98 of 231 are safe abstentions (42%), 69 correct | "On 3 Oct, 0 of 231 boundary inputs produced a wrong material action, on the rules path and with a scripted model; not run against a live model" |
| 9,085 API tests, 9,040 passed (T1, T14) | pytest outcome | lead's record, `975e082f` | — | 9,085 collected | unit/invariant tests | Not re-run here; a count is not a correctness measure | "The API suite passes (one known machine-specific failure, #161)"; keep the count only in Table 14 |
| 169 web unit; 445 mock + 139 live browser (T1, T14) | Playwright/vitest outcome | lead's record | — | — | browser tests | Not re-run here; "live" = a local API, not a deployment; 2 known retry failures | as is in T14, labelled "lead's record, not re-run" |
| Concurrency: 8 invariants, SQLite and PostgreSQL 17 (T15) | Two writers; serial replay identical | `tests/` concurrency suite | designed interleavings | not stated | unit/invariant tests | Production runs one worker (SEC-11) | as is |
| Deployment | — | — | — | — | **no deployed-system tests** | SEC-06: no runnable production configuration; no network deployment, TLS proxy, multi-worker, real bank feed or real documents tested | State once: "No result in this document comes from a deployed system." |

---

## 4. Cross-cutting checks

### 4.1 Label quality

- **Buyer messages.** Labels were written by AI agents in separate sessions (held-out 3: Claude Opus, with a written
  independence statement and three disclosed deviations; held-out 2: an evaluator agent that never read the compiler).
  No human labelled or adjudicated them, and the labellers share a model family with the developers. Judgement calls
  were declared before the run (0.88% boundary, H3-I05 counted as a material miss by convention, approximate bases).
- **Owner questions.** `general.yaml` was "written from the meaning of the ids only, before the matcher"; its author is
  the development effort, not an independent evaluator. The bank's scorer is a rule (expected figure or yes/no in the
  reply) plus 9 manual overrides after reading every reply of the first run; later runs rely on the rule.
- **Contracts.** The answer key is generated with the documents by a seeded generator (correct by construction, not by
  annotation), which makes it a strong oracle for the fields it covers but ties the test to the generator's templates.
- **Router answers (live).** Graded here by one unblinded reviewer with a three-level scale; treat as indicative.

### 4.2 Policy drift

The 1 Oct labels encode the policy before ADR-0007 (early payment must also be cheaper than the plan). Today's verifier
disagrees with 7 labels in each set (H3-A03, A04, A07, A08, N6B, T01, T01Z; H2A01, A02, A04, A06, P05, I01, I03). The
document handles this by reporting the form baseline; it should also report the reading-only agreement (79% and 94%) so a
reader can separate "the reader is wrong" from "the policy changed". The autonomy funnel's "eligible" set (14) is defined by
today's policy, so it is not comparable to the 1 Oct figures. The owner-question set shows the same effect on 571ea64f
(LIQ-10 now answers a LIQ-01 item).

### 4.3 Exclusions, abstentions and related items

- Unlabelled items are excluded from verdict agreement (3 + 2); must-abstain items are excluded from the material-error
  denominator (15 + 12) but counted as silent errors when booked.
- Abstentions are the system's main safety mechanism and its main usefulness cost: held-out 3 today escalates 36 of 66
  messages (20 needs-owner, 16 no-verdict).
- Scans and photos are refused and excluded from the 75% (13 of 30).
- Related items: held-out 3 has 20 pairs and held-out 2 has 13 (same economics, en/zh twins, near misses); the bank has
  ~4 wordings per question; the everyday set maps 345 phrasings onto about 33 answers; contract fields cluster in 17
  documents (a buyer/seller swap is 2 errors from 1 mistake); the attack catalogue repeats cases across callers
  (NL-TQ01..18 = 9 × 2; NL-CX*K buyer-key twins). Effective sample sizes are smaller than the counts, and every interval
  above is too narrow.

### 4.4 Independence of oracles and baselines

| Oracle or baseline | Independent of the code it judges? |
| --- | --- |
| Golden values (`compute_golden.py`) | Separate implementation, no app imports; same team, same ADRs |
| Funding brute force | Separate search; shares the projection engine |
| Like-for-like "line first" | Simple heuristic written by the same team; fair (runnable levers only) |
| Form baseline | Not a baseline: today's verifier on the labels |
| Held-out labels | Separate AI sessions, labelled before the run; no human |
| Rules grammar as the "no model" baseline for contracts | Weak: it has no Chinese party pattern |
| Attack harm oracle | Store diff in the harness, independent of the controls; positive controls and mutation tests show it can see harm |
| Scripted-task expectations | Written by the handler authors |

---

## 5. Contract extraction: correct, missing and wrong

Batch 2, first reading (unseen; recorded DeepSeek readings re-scored offline with `services/api/scripts/eval_contracts.py`
`score`): 17 text-layer contracts, 285 key items. "Wrong" = a value stated that differs from the key. For payment stages,
items are matched as multisets, so a key item can be missing because a different value was stated; those stated
non-matching items are counted separately ("stage items matching no key item": wrong values or surplus stages).

| Field | Affects | Key | Correct | Wrong (stated) | Missing | Stage items matching no key item |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| amount_total | cash amount | 17 | 14 | 0 | 3 | — |
| payment_stages[].percent | cash timing and amount | 33 | 27 | — | 6 | 3 |
| payment_stages[].days_after_trigger | cash timing | 33 | 28 | — | 5 | 2 |
| payment_stages[].days_unit | cash timing | 33 | 26 | — | 7 | 4 |
| payment_stages[].trigger | cash timing | 33 | 17 | — | 16 | 9 |
| late_payment_interest | cost of late payment | 17 | 12 | 3 | 2 | — |
| retention_pct | cash withheld | 17 | 16 | 0 | 1 | — |
| performance.end_date | set-up guard (END_NOT_CERTAIN) | 17 | 10 | 2 | 5 | — |
| buyer.name, seller.name | party check, who pays whom | 34 | 28 | 6 (3 swaps) | 0 | — |
| **Decision fields** | | **234** | **178 (76%)** | **11** | **45** | **18** |
| contract_no, sign_date, start_date | record only | 51 | 37 | 1 | 13 | — |
| **All scored fields** | | **285** | **215 (75%)** | **12** | **58** | **18** |

After the five fixes (no longer held out): decision fields 198/234, 2 wrong, 18 stage items matching no key item. Batch 1
(tuned): 412/424 decision fields, 0 wrong.

What limits the damage: every term must quote its clause word for word; code-side checks (stage percentages sum to 100,
stage amounts match the total) flagged 2 problems in the first reading (1 of 5 stage-sum checks, 1 of 9 stage-amount
checks); a reading changes nothing until the owner confirms it,
and only the owner's separate Tier-2 "Set up in my books" turns a contract into forecast invoices, re-read by code and
guarded (OUTSIZED, END_NOT_CERTAIN). The party-role check would refuse a swapped customer contract, but that was not
measured on this set. The remaining risk is an owner confirming a plausible wrong stage or trigger, which nothing here
measures.

---

## 6. Usefulness beside safety (buyer messages, 115 held-out messages, today's build)

| | Held-out 3 | Held-out 2 | Both |
| --- | ---: | ---: | ---: |
| Messages | 66 | 49 | 115 |
| Genuinely acceptable today (pure early pay, cheaper than the plan) | 10 | 4 | 14 |
| … accepted by FLOW alone (autonomous acceptance coverage) | 1 | 2 | **3 (21%)** |
| … sent to the owner unnecessarily | 9 | 2 | **11 (79%)** |
| Countered or rejected alone | 29 | 25 | 54 |
| Escalated, and escalation was right | 27 | 20 | 47 |
| Owner reviews needed | 36 | 22 | 58 (50%) |
| Autonomous accepts that were wrong | 0 of 1 | 0 of 2 | **0 of 3** |
| *First run, 1 Oct, before ADR-0005* | *4 of 8 wrong* | *2 wrong* | *6 wrong* |
| Refusal-type outcomes (NO_VERDICT) | 16 | 14 | 30 (26%) |
| Material errors on booked verdicts | 3/51 | 0/37 | 3/88 |

---

## 7. The live-provider stress test (18 Oct 2026)

**Setup.** Build `int/live-test 28738f19`, `LLM_MODE=live`, `FEATURE_ASK_ROUTER=1`, DeepSeek `deepseek-flash`, golden
demo books as the demo launcher seeds them, API on loopback, client `stress.py` (owner token, `POST /nl` without
`?mode=business`, so the demo wording). Phases: hard (20), attacks (8), two-turn (6), bursts (5, 10, 20), sweep (589:
the bank's 244 main wordings and the 345 everyday wordings, one fresh session each, one shared runtime).

**What it measured.** HTTP status, client latency, the parse source and the reply. It did **not** score correctness,
capture operations, or diff the store. Router outcomes come from the API log, whose lines carry only a hash of the
redacted question; this review matched all 65 distinct hashes back to the questions offline.

**Results.**
- Availability: 589 of 589 sweep turns and all 69 other turns returned HTTP 200.
- Path: the sweep's parse sources were rules 546, question gate 10, the older intent classifier (model) 12, fallback
  21. 63 sweep questions reached the router: 33 answered, 29 "cannot answer yet" with the nearest read, 1 rejected
  (missing slot). Over all phases the router was called 69 times: 39 answered, 29 none, 1 rejected.
- Router answer quality (one unblinded reviewer, `live_router_outcomes.json`): 22 right, 10 partial, 1 wrong topic
  ("我们的资金成本是多少？" got debt service and "no rate recorded", although the engine holds a 10.84% marginal cost of
  funds). Partial answers typically gave a customer summary when asked what Foshan's terms cost or what was last
  offered. The router declined some questions the books do hold (credit-line clean-down day, cost of funds in English,
  customer list, EBITDA, the APR ceiling).
- Old classifier: 4 sweep questions became proposed plans awaiting "go ahead" (section 1, item 9); several became a full
  status dump instead of an answer.
- Live compiler cross-check: "Foshan wants 60-day terms. Can we accept?" returned NO VERDICT (model and rules readings
  disagreed), where the offline path recommends a counter: safe, less useful.
- Attacks: 8 prompts, 0 reached the router, 2 raised a Tier-3 security event; replies show nothing executed.
- Latency: see 3.6.

**Not comparable with the offline scores**: different wording mode, a seeded demo runtime (a confirmed Foshan contract,
3 operations already run) and one runtime shared by all 589 turns (Tier-3 questions early in the sweep logged refusals
that later "what did FLOW do" answers report). 73 of the 589 replies differ from the offline reply to the same text: 33
from the router, 12 from the classifier, 28 from the environment and wording mode.

---

## 8. Recommended section text

### 8.1 Table 1 rows (replace)

| What | Result |
| --- | --- |
| Engine correctness | 67 of 67 golden values exact to the fen against an independently written oracle; covenant and capex values 27/27 |
| Funding router | Within ¥1 of a brute-force search on 26 of 26 test scenarios |
| Safety | On 115 held-out buyer messages FLOW accepted 3 on its own, all correctly. Before the coverage proof (ADR-0005), the first runs on the same sets accepted 6 misread messages; that is why autonomy now requires proof |
| Usefulness | 57 of 115 messages handled with no owner involvement (54 counters or declines, 3 accepts); only 3 of the 14 genuinely acceptable offers are accepted alone, the other 11 wait for one owner review (Table 8) |
| Security | 279 stored attack cases (128 API, 151 chat): none violated the defined harm oracles in the specified offline run (rules path and a scripted hostile model; no real model read an attack). Internal AI review, not external assurance |
| Owner questions | Of 427 bank questions the books can answer, 228 answered from the books, 45 partly, 0 wrong (bank built against these questions). On 142 held-out everyday wordings, 127 reach the right answer (89%) and 3 a wrong topic (2%). No question executes anything |
| Live model | One live DeepSeek run per component: buyer messages 42/63 (1 Oct); question router answered 33 of the 63 questions it saw on 18 Oct, 22 of them fully right by one reviewer's reading |
| Tests | The API, web-unit and browser suites pass on the build named (Table 14 gives counts) |

### 8.2 Section 03, replace "Evaluation approach" through Table 9's notes

> **How to read our numbers.** Every result below carries its evidence class: *unseen* (labels written before the code saw
> the items, scored once), *tuned* (re-scored after fixes chosen from its failures), *recorded* (a model's past reading
> replayed offline), *live* (a provider called that day), *rules* (no model), *scripted* (a fake model we wrote),
> *tests*. No result comes from a deployed system. Figure 5b groups the accuracy results by class.
>
> **Reading buyer messages.** Two held-out sets of WeChat and email messages (66 and 49, Chinese and English) were
> labelled by separate AI-agent sessions before the reader saw them. Their first runs are our only unseen figures: verdicts
> matched the label on 33 of 63 and 28 of 47, and FLOW accepted 6 misread messages on its own (4 of 8 accepts on the
> first set). We then added the coverage proof (ADR-0005) and fixed the failure classes. On today's build, with the 1 Oct
> labels, verdicts match on 44 of 63 and 38 of 47; against today's policy applied to the true terms, which removes 14
> labels the policy has since changed, the reading is right on 50 of 63 and 44 of 47. These are tuned figures. The
> material-error and silent-error targets are still missed on the first set (3 of 51, 4 silent).
>
> **Safety and usefulness together (Table 8).** FLOW now accepts alone only when it can account for every figure: 3 of
> 115 messages, all correctly. That caution has a cost: 11 of the 14 genuinely acceptable offers wait for the owner,
> mostly because the buyer named a settlement date FLOW does not yet read. With so few autonomous accepts, "no wrong
> accept" is weak evidence by itself; the evidence is the rule that blocks acceptance without proof.
>
> **Live model.** One live DeepSeek run on the first held-out set (1 Oct, an older build) matched 42 of 63 verdicts with no
> wrong accept. It was not repeated on the submitted build, so we have no measure of run-to-run variation.

### 8.3 Contract reading (replace the paragraph and the Figure 6 caption)

> **Reading Chinese contracts.** We generated 70 synthetic contracts with their answer keys and built the reader on the
> first 40. On 30 new ones (six new contract types), 13 are scans or phone photos and are refused, because FLOW has no
> OCR. On the 17 with a text layer, recorded DeepSeek readings got 215 of 285 key fields right (75%; 45% over all 30
> contracts). Of the 234 fields that move money or gate a decision (amount, stage percentages, days and triggers,
> late interest, retention, end date, parties), 178 were right, 11 were stated wrongly (including buyer and seller
> swapped in 3 contracts), 45 were missed, and 18 stage items were stated that match nothing in the contract. After five
> fixes chosen by studying these failures the figure is 86% (no longer held out); on the 40 it was built on, 98%. A
> reading changes nothing until the owner confirms it and separately sets it up in the books, but nothing measures
> whether an owner would catch a plausible wrong stage. The documents and readings are outside the repository.
>
> Figure 6 caption: *Reading Chinese contracts, by format. Unseen text-layer contracts: 75% of fields (recorded DeepSeek
> readings). After fixes made by studying them: 86% (no longer unseen). The contracts the reader was built on: 98%. Scans
> and phone photos are refused: FLOW has no OCR.*

### 8.4 Table 10 rows (replace)

| Question | Result |
| --- | --- |
| Does it answer an owner's questions? | Bank of 122 questions in English and Chinese with rewordings (503 turns), the bank the answer module was built against: of 427 turns the books can answer, 228 answered, 45 partly, 154 declined naming the nearest read, 0 wrong by the bank's scorer; 75 of 76 questions outside the books declined honestly. Offline, rules path |
| Does it understand everyday wording? | 345 phrasings labelled before the matcher, split 60/40 by a hash. Held-out 142: 127 right (89.4%), 3 wrong topic (2.1%), measured more than once during development. Tuning 203: 199 right, 1 wrong. Scores the topic of the answer, not its figures (`b4167053`; 326/345 on the submitted build after a new answer took one tuning item) |
| Is the router safe and useful? | Scripted outputs: every malformed or hostile output we wrote is rejected (452 tests pass). Live, 18 Oct: of 589 questions, 63 reached the router; it answered 33 (22 fully right, 10 partly, 1 wrong topic, by one reviewer), said "cannot answer yet" for 29 and rejected 1. Nothing the router chose can act: its 40 tools are read-only |
| How fast is it? | In process on one development machine, cache mode, no network or model: router p50 81 ms (26 scenarios), chat turn p50 9 ms and p95 567 ms (87 turns), full Scene 1 p50 1.08 s (5 runs); these vary severalfold with machine load. Live, 18 Oct, local API: 589 sequential questions p50 0.13 s, p95 1.17 s, max 5.8 s (at least 75 of them called the provider; a router call took p50 0.91 s); 20 concurrent questions all answered, the slowest in 8.4 s |
| Does language stay safe at the boundary? | 231 adversarial inputs (3 Oct, build 979defb): 0 wrong material actions on the rules path and with a scripted model; the model path was reached on 0% and 85% of eligible items, below our own 95% floor; not run against a live model |

### 8.5 Table 13 note (add under the table)

> The harm oracles compare the books before and after each case: money moved, operations executed, facilities added,
> concessions booked, commitments activated, protected values in any outbound text or readable without the owner token,
> canaries, and the integrity of the log. Six positive controls (legitimate actions) pass through the same oracle and are
> seen, and switching off one control at a time makes the harness report harm, so the clean result is not a system that
> refuses everything. The attack text was read by the rules grammar (78 times) and a scripted hostile model (4); no
> recorded or live model read an attack. Over all 279 cases detection is 70.6%; most of the rest are owner consent cases,
> where the right result is that nothing runs. Untested: a live model reading attacks, the deployed network profile,
> more than one worker process, real documents and bank feeds, and the question router under attack (the 8 live attack
> prompts of 18 Oct never reached it).

### 8.6 Known limitations, "Live models" (replace)

> **Live models.** Each live result is one run on one day: buyer messages on 1 Oct (an older build), the question router
> on 18 Oct. Neither measures run-to-run variation, the provider's model version is not recorded, and the
> language-boundary set has not been run against a live model. In live mode the older intent classifier can turn a
> question into a proposed plan (4 of 589 on 18 Oct), which still waits for the owner's "go ahead".

---

## 9. What could not be verified

- API, web-unit and Playwright counts (9,085 / 9,040, 169, 445, 139): the lead's records; not re-run here.
- The held-out-3 live DeepSeek run (1 Oct): cannot be re-run offline; its report is committed.
- Contract figures: reproducible here only because this session's scratchpad holds the predictions, keys and logs
  (`b2fix/`, `contract-cn2/`, `cn-all/`); the 70 documents are not in the repository.
- The external red-team run (16 Oct) and its 100 live calls: report not in the repository.
- Live attack harm: no store diff was taken; "no harm" rests on the replies.
- The "one global lock" explanation of burst latency: consistent with the data (latency grows with N) but not measured.
- Who wrote `general.yaml`, and whether bank replies after the first baseline were hand-checked.
- Latency on the document's build machine: the machine is not named and my re-run was under load.

## 10. Files

- `docs/deliverables/submission/work/eval/live_{sweep,hard,attacks,twoturn,burst5,burst10,burst20}.summary.json`,
  `live_burst{5,10,20}.reads.json`: copied from the 18 Oct live run (no secrets; raw log not copied).
- `docs/deliverables/submission/work/eval/live_router_outcomes.json`: every turn that reached the router, joined by
  hash, with the grade of each answered turn.
- `docs/deliverables/submission/work/eval/contracts_{b2_heldout,b2_afterfix,b1_tuned}_fields.json`: correct / wrong /
  missing per field.
- `docs/deliverables/submission/work/eval/offline_reruns_20261018.json`: the offline re-runs above.
- `docs/deliverables/figures/src/fig_eval_classes.py` → `docs/deliverables/figures/fig-eval-classes.png` (suggested
  as Figure 5b, beside Figure 5).
