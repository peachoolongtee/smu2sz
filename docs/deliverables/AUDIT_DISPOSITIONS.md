# Audit dispositions: the 19 Oct document audit

An outside reviewer audited the Technical Document (T), the Security Self-Assessment (S) and their evidence on 19 Oct 2026.
The audit was of the documents, not a penetration test, and the reviewer did not re-run the tests. Every finding was treated
as a hypothesis and checked against the code and tests of the submission build before anything changed. This register gives
each finding one disposition:

- **Fixed and verified**: the code or configuration changed, and a test or check that failed before passes now.
- **Corrected wording**: the behaviour was right; a document said something else, and now says what the code does.
- **Accepted limitation**: true, kept, and stated with its scope and the reason.
- **Deferred**: true, with the reason it waits until after the competition.
- **Disproven**: the evidence shows the finding does not hold.

The submission build and its checks are in [`VERIFICATION_MANIFEST.md`](VERIFICATION_MANIFEST.md). Commit ids are on `dev`.

## Authority and consent

| # | Finding | Disposition | What the code does, and the evidence |
| --- | --- | --- | --- |
| 2 | The documents disagree on which words decide an approval | **Corrected wording** and **fixed and verified** (CON-1) | One consent table now appears in both documents (S 1.6, T section 02). A pending plan runs on an explicit "go ahead", "yes", "do it", 执行 or 确认 (its approval-tier legs then wait). An approval is decided only by "approve" or "reject" with what was just shown, or by its id; "yes" and "go ahead" never decide one (`tests/nl/test_authority_audit.py`). The check found one path that broke the rule: after "yes" listed a queue the session had not shown, a bare "1" approved it. Round nine fixes it (CON-1, `tests/security/test_round_nine.py`) ⟦R9⟧ |
| 3 | Pause: may an approval queued before the pause still run? | **Corrected wording**; behaviour kept by design | The owner's own decision runs while the agent is paused (the pause wraps `Executor.execute`; a decision calls the run directly). The pause stops delegated activity: the agent, buyers and non-receipt bank-feed requests. S's "Pending approvals" row said otherwise and is corrected. Pinned by a test in round nine ⟦R9⟧ |
| 4 | T extends the receipt and repayment exceptions to forged mandates | **Corrected wording** (T was wrong) | A bad signature, an edit without re-signing or an unsigned revocation refuses every operation. Expiry, a signed revocation or a wrong version still allows a receipt and the owner's own repayment (`app/operations/executor.py`, `app/mandate/validity.py`). Pinned by tests in round nine ⟦R9⟧ |
| 5 | Can a buyer cause execution? | **Corrected wording** | A keyed buyer message can lead the agent, under the agent's authority (`requested_by: AGENT`) and at Tier 1, to counter, reject, or accept a plain early-payment discount, with no size limit. It never starts a draw or an advance; funding legs follow only paths the owner starts. It is refused while the agent is paused. The buyer supplies no authority of its own (S Table 4, T section 02) |
| 6 | The unit of the ¥100,000 threshold | **Corrected wording** | `tier2_single_commitment_fen` is compared with a commitment's net new future-concession value over the mandate's 365-day horizon; strictly greater needs approval (`tests/operations/test_approval_thresholds.py`). An early-payment discount counts ¥0, so the threshold never limits invoice face. Under the demo mandate the ¥5,000 concession cap binds first, so the threshold cannot bind there; it is stated as such |

## Facts and figures

| # | Finding | Disposition | Evidence |
| --- | --- | --- | --- |
| 1, 12a | "Every check passes" while the live browser suite had failures; "the same three failures in every table" | **Corrected wording** | No document says "every check passes" now; each table gives exact counts per suite. The live suite failed 3 tests on `975e082f` and 6 on the round-seven merge; on the submission build: ⟦FIN-LIVE⟧ |
| 7 | "Its cheapest cure" costs more than the credit-line plan | **Corrected wording** | The verdict's cure may use only sources that can carry a permanent need, which excludes the clean-down credit line, so it is invoice financing at ¥2,406.67 (¥1,731.47 interest and ¥675.20 fees). The ¥1,468.05 plan is the router's plan on the clean-down line. Both rows are relabelled, with a note (T Table F1) |
| 12b | Optimality claims versus the brute-force budget | **Corrected wording** | Over the actions FLOW can run, the brute force completed on 26 of 26 scenarios. It reached its budget in 2 cases (F09, R03), on the pricing reading only, so there the plan is "the best found in a bounded search" |
| 12c | 546 rules answers and 63 router paths against 589 questions | **Corrected wording** | 546 rules + 10 question gate + 12 classifier + 21 fallback = 589; the 63 router paths sit inside the 546 and the 10 |
| 12d | "Cheapest" ignores the authority constraint | **Corrected wording** | A plan FLOW may run alone always ranks before one that needs approval, whatever the cost (`app/funding/search.py`); "cheapest" now says so in five places |
| AI | What the model adds, against rules alone | **Corrected wording**; an unseen live run is prepared for the owner to run ⟦LIVE⟧ | On the frozen 20, per item: LF05 and LF07 go from partly to fully correct; LF15 and LF20 go from wrong to correctly held back; LF01, LF03 and LF04 go from correct to wrongly held back. So the model reads phrasings the rules cannot, and the shipped checks trade 3 needless hold-backs for 0 wrong readings (T section 03) |
| Autonomy | 3 automatic accepts out of 14 acceptable offers | **Corrected wording** | "0 wrong autonomous accepts" now sits beside the 3 of 14 coverage and the note that the sets were tuned after their first runs |
| Sum | ¥257,186 at 0.85% is not ¥2,186.20 | **Fixed** | The face is ¥257,186.08, giving ¥2,186.08; ¥2,186.20 came from the ¥257,200 face of another test (S 1.3) |
| Groups | S misdescribes T Table 5's grouping | **Corrected wording** | T Table 5 counts replay under privilege escalation, and expired commitments and changed offers under induced transfers |
| 57 of 115 | Where the 30 refusals fall | **Corrected wording** | The 57 answered alone are 3 accepts, 20 counters and 34 rejections; all 30 NO_VERDICT refusals go to the owner |
| 98% | 98% on 40 contracts, of which 10 are scans | **Corrected wording** | 98% of key fields on the 30 text-layer contracts; the 10 scans are refused |
| Builds | Builds cited but not listed; 7-character ids | **Corrected wording** | S Table C2 lists every cited build with its date and role; ids normalised to 8 characters |
| Judge report | The committed judge report says 259 attacks | **Fixed** | Regenerated on the submission build ⟦FIN-JUDGE⟧ |
| Routes | Route classes add up to 112, not 113 | **Corrected wording** | 113 = public 3, documentation 4, buyer 3, agent 3, owner side 3, demo and setup 9, owner 88. S Table 6 had omitted `POST /nl/session/reset` and `GET /demo/story` |
| Fig. 13 | The 36-month loan shown as selected | **Fixed** ⟦FIG13⟧ | On the submission build the screening selects the 48-month lease and rejects the loan (reserve breach on day 44); the recorded mock was stale |
| Fig. 10 | Option B reads "About ¥0" but costs ¥3,544.41 | **Corrected wording** (caption); the screen label is **deferred** | The screen shows the net of B's terms alone (−¥162.05), without B's ¥3,706.46 funding plan. The caption says so; rewording the screen's "Cost to you" is a product change after the competition |
| Counts | Route counts disagree across sections; 49 messages but 47 comparisons; Table 4 "first run" header; 85% and 86%; headline test counts | **Corrected wording** | 109 API routes (108 under `app/api` plus `/health`) and 4 documentation routes, 113 in all; 2 held-out items are unlabelled; the header says today's values with first-run values in brackets; 86% is 246/285 key fields and 85% is 198/234 decision fields; test counts are the submission build's |

## Scope of the demonstration

| # | Finding | Disposition | Evidence |
| --- | --- | --- | --- |
| 10 | The launcher's web server listened on all interfaces | **Fixed and verified** | `pnpm demo` serves the web app on 127.0.0.1 (`da86b702`); with the demo running, `netstat` shows 127.0.0.1 only and the LAN address is refused. One API process, cache mode by default, synthetic data: as the launcher prints |
| 8 | The egress guard is called the last step, but text changes after it | **Fixed and verified** (LOG-2) ⟦R9⟧ | The buyer's whole reply is scanned before it is sent. A leftover rewrite after the per-counter scan, fixed wording that also duplicated a noun, is removed, so the text scanned is the text sent and logged |
| 9 | Recovery confuses settlement with reversal | **Corrected wording** | An invoice advance is repaid only by a real customer receipt; a line draw by `RepayFacility`; revoking a commitment changes FLOW's record only and does not rescind an agreement the buyer accepted. The stop procedure never records a receipt that did not happen (S Table 10, 1.12, 4.6) |
| 11 | "Whatever the model does" | **Corrected wording** | Replaced by the authority invariants and their assumptions. A model can misread payer, contingency, dates, scope or units inside typed fields. The checks reduce that but do not remove it. A misreading can influence an owner's approval. Text sent to a provider has left the machine (S 2.11, 3.3) |
| SEC-19 | Anonymous provenance missing on accept and approval views | **Fixed and verified** ⟦R9⟧ | An offer that came without a buyer's key is labelled "unverified sender" wherever the owner can accept it or approve its operations. Anonymous intake stays on in the demo, because the FastCapital injection example uses it |
| CSP | CSP checked on a production build while the demo uses `next dev` | **Corrected wording**, and the development server checked ⟦FIN-CSPDEV⟧ | The development server sends the same nonce policy plus `'unsafe-eval'` for hot reload. Both are now checked and stated |

## Accepted limitations and deferred work

| Finding | Disposition | Scope and reason |
| --- | --- | --- |
| The disclosure oracle uses the product's own scanner | **Accepted limitation** | Stated (S 2.5). The oracle also checks state and money, which do not depend on the scanner; an independent scanner is post-competition work |
| Disabling egress produced no catalogue leak | **Accepted limitation** | Stated as a coverage gap (SEC-32); the guard is covered by its own tests, not end to end by the catalogue |
| Partial plans differ across chat, alerts and negotiation | **Accepted limitation** (SEC-28, deferred by the owner) | Each leg is now reported as it ran (FUND-1 to FUND-5 fixed); stopping at the first failed leg and resuming after an approval change product behaviour and wait |
| Cross-route races in one process untested | **Accepted limitation** | One API process is a condition of the demo (SEC-11); race tests are post-competition |
| Parser timeouts and decompression limits | **Accepted limitation** (SEC-31, Low) | The routes are owner-only; size limits exist; a parse timeout is post-competition |
| Receipts without references can repeat | **Accepted limitation** (SEC-29) | A simulation assumption; over-payment is refused; a real bank feed must carry a reference |
| No aggregate draw limit | **Accepted limitation** (R-3) | Each draw is inside the mandate; an aggregate limit is a production prerequisite |
| Recurring invoices count after their first issue | **Accepted limitation** (CT-2b, ADR-0014) | The borrower file is fixed; the other readers are disclosed |
| Production deployment, credential lifecycle, database roles, anchored audit records, real bank events | **Deferred** | Production is NO-GO; listed in S section 04 |

## Presentation

| Finding | Disposition |
| --- | --- |
| Too long; history in the main reading path | **Corrected** in part: the main narratives lead with the current build; certification history sits in appendices ⟦PRES⟧ |
| Charts and screenshots too small | **Fixed**: the cash trajectories, the evaluation charts, the authority matrix and the decision screenshots now print at 5 to 6 inches wide (they were about 3) |
| Dense 8-point tables | **Fixed**: tables print at 9 points (8.5 for seven columns or more), code at 8 to 8.5 |
| The security PDF has one link | **Fixed**: its evidence paths are links pinned to the submitted commit |
| Reproduction commands that fail when pasted; a rerun overwrites the submitted report | **Fixed**: commands give the POSIX and PowerShell forms and write into `out/` ([`REPRODUCE.md`](REPRODUCE.md)) |
| Covers underemphasise FLOW | **Accepted limitation**: the organiser's template fields stay as required |

## Confirmed by the audit, no change

The capex NPV of ¥380,885.77 recomputes. The NBS receivables figures match the publication. The `braces` exception is a real
advisory with no patched version. The documents disclose internal AI-assisted review, uncertified live mode, tuned
evaluations, simulated money and production NO-GO.
