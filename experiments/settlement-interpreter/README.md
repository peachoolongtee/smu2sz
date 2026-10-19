# Build B: settlement dates and workflow evidence

19 October 2026. **Bounded experimental implementation; not a release certification.**
Branch: `feat/settlement-interpreter`. Final application/test checkpoint: `f9fab6749a04d54db3dcc2f0e468d784418b6a3d`. Built on isolated Build A, which uses the handoff's frozen fallback `03215a20`.

## Outcome

This improves date-aware proposals and assisted completion. **The live AI path still completes very few workflows autonomously.** Its missing invoice-basis fields remain a major bottleneck.

The same 36 newly authored English/Chinese messages were labelled and committed before baseline runs and implementation. Labels were available to the implementer, so this is **not blind or independently authored validation**.

| Matched fresh-provider readings, 36 cases | Build A before B | Build B final-stage replay |
| --- | ---: | ---: |
| Autonomous agreement + correct bank receipt | 0 | 2 |
| Explicitly quoted, correctly resolved settlement days | 0 | 16 |
| Wrong autonomous accepts observed | 0 | 0 |
| Financial state changed during intake/evaluation | 0 | 0 |

A separate **post-hoc owner-inclusive protocol** completed 3 workflows before B and 15 after B: **2 autonomous + 13 explicitly reviewed/approved by the simulated owner**. That runner uses expected-date/safe-case labels to select owner approvals; it is a controlled conformance check, not a human usability study or evidence of unaided task completion.

The new **rules/cache path completed 15 autonomously** on this set. Do not describe the 15 as live-AI autonomous completions. Do not turn appropriate holds plus completions into a headline task-completion percentage.

The 16 dates include one correctly priced counteroffer. The original permissive labels allow rather than require acceptance. SB18 (`2026年10月6日前`) was left held because deadline inclusivity is unclear; its original label was not rewritten. The late-date offer remains subject to the existing pricing checks.

## What changed

- Added optional quoted payment-timing evidence, an immutable received-day reference, a closed date grammar and a versioned `calendar_grammar_v1` proof marker. This is deterministic evidence, **not two independent readers agreeing on a date**.
- New offer intake stamps receipt on the server's books clock. Caller-supplied days cannot shift “tomorrow”. Fixture inputs remain untouched.
- Clear today/tomorrow, relative calendar-day, explicit year-bearing calendar-date and this-week weekday expressions bind to a day on the books. Week-end windows use a **Monday–Sunday calendar convention**. Business-week/holiday calendars and timezone conversion are not implemented.
- Existing verifier and early-pay pricing use that bound day. Stale, invalid, inconsistent or non-early days are held. Unsupported single-discount timing is not priced on an assumed facility day.
- A date in a separate price-probing question does not become the offer's settlement date. This restores MX-04's existing refusal/counter egress paths.
- Timing is finalized after field reconciliation so a rules-filled amount can support a correctly dated **owner-reviewed** proposal. Genuine model uncertainty, all abstentions and every one-reader review restriction remain. This step never upgrades a prior lack of autonomy proof.
- A payment promise remains a forecast/conditional agreement, never a receipt. Only a bank-feed receipt changes cash. Timely and late receipt behavior is tested on memory and SQLite stores.
- Model prompt/schema versions, recorded model fixtures and existing financial formulas are unchanged. Empty timing/provenance fields retain historical serialization.

## Evaluation provenance and limits

**First fresh run:** 36/36 cases were answered by `deepseek-flash`, at `ed0626b78adc407d62d39c10ac66c40dbbe301b2`. It produced 2 autonomous completions and 31 NO_VERDICT outcomes. This exposed a sequencing defect: grounded model obligations often lacked an invoice amount; rules reconciliation filled it, but a previously derived unresolved-date marker stranded the offer.

**Final-stage comparison:** captured checked readings are replayed through the new finalization seam at `0857012a`, then through real intake/evaluation, stored commitments, owner-visible decision reads, clock and bank-feed operations. The new stage takes exactly that captured checked offer as its input. No additional provider calls were used for the 36-case replay. The original snapshots/results remain archived. This is not a fresh full-provider rerun of the final code.

**Post-fix smoke:** four original cases were requested again on the final code, with raw typed extraction retained. They are targeted diagnostic repeats, not four new blind cases. Overall provider attempts: **36 + 4 = 40 / 40 approved**; SDK retries disabled; memory storage; redaction enabled. Recorded tokens: 137,834 prompt + 8,396 completion = 146,230. No currency cost is estimated. Returned alias is recorded; an immutable provider model version is unavailable.

The initial 36-case records retain grounded/checked offers, not the complete raw extraction schema. Therefore missing invoice amounts at that boundary alone do not prove whether the model omitted a quantity or grounding failed to associate it. The four diagnostic rechecks expose the relevant raw fields:

| Diagnostic case | Immediate-discount base_amount_text | invoice_amount quantity text |
| --- | --- | --- |
| SB01 | `["¥420,000"]` | `["¥420,000"]` |
| SB03 | `[null]` | `["¥420,000"]` |
| SB12 | `[null]` | `["42万"]` |
| SB17 | `[null]` | `["42万"]` |

The targeted rechecks resolved all four dates; one workflow completed autonomously and three remained review-only. In those three, the raw typed extraction contains an invoice-amount quantity while the obligation's base_amount_text is null. This identifies an extraction-to-obligation association gap for these repeats. Outputs also vary between calls, so the one smoke completion is neither added to the 36 unique cases nor attributed as an autonomy gain from the fix.

See the extraction records before attributing this universally to model capability. A future fix must prove a quantity belongs to the correct invoice/obligation; it must not waive single-reader review or use confidence as authority.

This corpus is narrow: one synthetic invoice face/rate, clear positive payments plus selected unsafe/ambiguous variants. It does not establish contract completeness, general multilingual accuracy, real collections, provider fallback certification or production security.

## What counts as a completed workflow

A completion requires the correct stored commitment (invoice, full face, rate and day), the correct owner-visible agreement outcome, no cash/receivable change from the promise itself, then an authenticated simulated bank receipt of **¥417,900** settling the **¥420,000** invoice at **0.5%**. Cash changes intentionally occur at that receipt. **Do not claim zero operations or zero money moved across the workflow experiment.** No real money/database was used.

The primary protocol executes Tier-1 accepts only. The separate owner-inclusive protocol adds the actual owner acceptance endpoint for otherwise correctly dated, affordable review proposals, then checks the same receipt/state results. It never approves the labelled unsafe cases.

## Verification

- **Final clean checkpoint:** `3432 passed, 3 skipped, 35 warnings in 352.74s (0:05:52)`. Compiler, verifier, operations, financial, clock/books, security, persistence, API timing/provenance and selected authority/consent tests; memory and temporary SQLite only. Source was clean before and after the run.
- **Attack catalogue:** 128 API + 151 chat = 279 attacks; zero observed harm; 120/128 named API controls defended; no not-reached/control-not-seen cases. These are finite observed tests, not a proof of absence of vulnerabilities.
- **Language boundary:** 231 cases each, cache and fake, WRONG_MATERIAL = 0. **Important:** the unmodified harness aborts because its “early next week” setup can no longer price an approval. An experiment-only adapter queues the same 30bp invoice proposal as explicitly review-only. Scored texts/labels stay unchanged; adapted reports and affected setup IDs are archived. These are not unmodified certification runs.
- Frontend typecheck, lint and **187 unit tests** passed.
- Full mock browser: **478 passed, 77 skipped, 1 failed**. Cash-card height is 375px against a 360px limit at 1280px (`home-v2.spec.ts:1045`). The same failure is recorded in Build A evidence; UI production source is unchanged.
- Full API-backed browser (`LLM_MODE=cache`, one worker): **176 passed, 51 skipped, 1 failed**. The reset test's “10 days early” seed is now deliberately unpriceable. Only that seed was changed to an undated 1% offer; reset/cache assertions remain. The amended case **passed in isolation**. The full API-backed suite was not rerun after this test-only amendment. Earlier Ask FLOW failures did not recur in this run.
- A direct check and API regression confirm unsupported timing stays visible as a BUYER_REPLY waiting task, with no agreement or financial-state change. Its current clarification is generic; structured, resumable field-specific clarification remains outstanding.
- Full application/test Ruff still has **60 findings in 26 unchanged files**; changed files are clean. This is an inherited integration blocker, not a green lint gate.

Earlier development-run logs are retained, including the MX-04 failure before its fix. Code was iterating during those runs; they are not the final clean-checkpoint result and their overlapping test counts must not be added together.

## Outstanding

1. **Invoice-basis extraction/association:** the live path's base amount is still often rules-supplied, requiring owner review. Diagnose raw extraction versus grounding; validate any future quantity association with conflicting/two-invoice/partial/missing-source cases. Do not silently loosen the authority policy.
2. **Broader date context:** separate invoice issue/due dates from payment promises; handle contractual reference dates, relative-to-due expressions and business calendars deliberately. Legacy H3-A05 still holds on invoice-date context. Yearless/ambiguous weekdays, holidays and explicit intraday/timezone deadlines remain restricted. The current grammar is a bounded first Build B, not a general date interpreter.
3. **Build D:** persist verified fields, unresolved fields and source/books versions; ask a targeted payment-date question and resume safely. A clarification answer must never become consent.
4. **Stronger evaluation:** independently authored, prelabelled complete workflows with exact terminal/state expectations, realistic varied amounts, invoice contexts and owner actions. This study's permissive labels and post-hoc assisted protocol are insufficient for a competition-wide completion claim.
5. **Integration:** fix the cash-card assertion and inherited lint; update the maintained certification bootstrap legitimately after the freeze, then rerun the required gates. Review/port onto the newer security-fixed base before considering integration. Full API release suite, PostgreSQL/release/deployment gates were not run. Nothing is merged or release-certified.

The older 115-message funnel moves only from **3 to 4 autonomous accepts**, with no wrong autonomous accepts observed. Its nominal 23 “eligible” labels include obsolete price thresholds, partial payments and hostile cases, so do not use 23 (or the previously discussed derived 14) as a clean eligibility denominator. Labels were left unchanged. It is evidence that broad natural-language usefulness remains limited, not a success-rate headline.

## Preserved and reproducible

No submission documents, `fixtures/`, frozen evaluation files or recorded mocks changed. The only web change is the explicitly documented reset-test seed. `dev` remains `3bd440a004214d669b5428d7d80391e682070c77` and `main` remains `beb8c66bd483fe99e0a630ef4309a479f2927da4`. Nothing was pushed or merged.

`checks.json` records stages and limitations; `evidence/` holds original/final results, logs and diagnostics. `run_workflows.py` defaults to cached/offline, memory-only runs and supports recorded-reading replay. Standalone live invocation is rejected; archived provider wrappers are audit material, not authorization for another paid run. `language_boundary_adapter.py` records its setup override and unchanged fixture/harness hashes. `SHA256SUMS` provides artifact integrity hashes, not independent security certification.
