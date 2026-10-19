# Handoff: `feat/reader-dates` for the Security Lead's evaluation

Written 19 Oct 2026 by the lead session on the owner's Mac, for the Security Lead. The owner asks one question: **can this branch
be included in the final `dev`?** This file is not committed (the owner keeps reviewer notes out of the repository); the branch
is on the remote.

## 1. What to evaluate

| Item | Value |
| --- | --- |
| Branch | `origin/feat/reader-dates`, head **`4604bfc9`** |
| Base | the frozen tag `submission-2026-10-20` (`4e03f0cf`, = `main` = `dev` at the time of writing) |
| Merge state | merges into `dev` with no conflicts while `dev` stays at `4e03f0cf` |
| Contents | Build A (field-classified reader cross-check) + Build B (settlement-date interpreter), replayed from the local branches `exp/field-cross-check` and `feat/settlement-interpreter` (based on `03215a20`), plus three fixes from the lead's review |
| Co-author trailers | none (checked on every commit) |
| Product code changed | 12 files, +464 / −60 (below) |
| Tests changed | 11 files, +632 / −26 |
| Evidence added | `experiments/field-cross-check/`, `experiments/settlement-interpreter/` (78 files, mostly recorded JSON) |

Commits, oldest first:

```
c03fd4c2 feat(compiler): reconcile grounded reader fields for owner review        (Build A)
8a64eccb exp(compiler): record matched-reader evaluation and gate exceptions      (Build A evidence)
de012041 test(settlement): freeze prospective workflow expectations               (Build B)
546b1b4b feat(compiler): prove settlement dates on the books calendar
5cc0e018 fix(compiler): hold unresolved single-discount settlement timing
dbc6b7a1 fix(compiler): distinguish percentage points from settlement times
e2865775 fix(compiler): distinguish date proof from reader agreement
3b9eb209 fix(api): state inclusive discount deadlines clearly in Chinese
39a96d86 fix(compiler): scope unread timing to the payment source sentence
c48991a0 fix(compiler): finalize dates after reader reconciliation
88787c6d test(web): isolate reset checks from unsupported settlement timing
a6793f1d test(api): keep unpriced dated requests visible for clarification
f861e2fe exp(compiler): record settlement workflow results and limitations       (Build B evidence)
2dceb944 fix(compiler): read Chinese day counts whole; bare now is not a day      (lead's review fix)
32959e5b fix(commitments): keep reader evidence out of the terms hash             (lead's review fix)
4604bfc9 test(nl): pin S-06 as stated day binds as stated or not at all           (lead's review fix)
```

Product files (`git diff --stat submission-2026-10-20 origin/feat/reader-dates -- services/api/app apps/web`):

```
services/api/app/compiler/cross_check.py   Build A: per-field reconciliation
services/api/app/compiler/service.py       Build A + B: cross-check outcome, date finalisation after reconciliation
services/api/app/domain/models.py          Obligation.field_provenance, PaymentTiming, Obligation.payment_timing   (domain model)
services/api/app/compiler/settlement.py    Build B: closed settlement-date grammar (new)
services/api/app/compiler/coverage.py      Build B: a code-read timing span may satisfy the coverage proof
services/api/app/compiler/grounding.py     Build B: attach timing; an unread date on a single discount -> settlement_day unresolved
services/api/app/financial/settlement.py   Build B: resolve a typed timing to a books day (new)                        (ENGINE)
services/api/app/verifier/bind.py          Build B: bind the stated day; hold stale / future / not-early / inconsistent    (ENGINE)
services/api/app/api/offers.py             Build B: received_day = the server's books day for non-fixture intake
services/api/app/api/presentation.py       Build B: "discount applies only to payment received by …" (en, zh)
services/api/app/commitments/terms.py      lead's fix: provenance and payment_timing are non-economic for the terms hash
apps/web/e2e/home-reset.spec.ts            Build B: the reset test uses an undated offer (a dated one is now held)
```

**Approvals.** The commits say "approved Build A" (field provenance on obligations) and "approved Build B". Two engine files
(`app/financial/settlement.py`, `app/verifier/bind.py`) and the domain model are touched. **Confirm with the owner that Build B's
engine part was explicitly approved** before certifying; the lead did not witness that approval.

## 2. What the change does

**Build A (reader cross-check, live model mode only).** Before: if the rules grammar read a value the model omitted, the whole
offer was held as a disagreement. Now each field is classified: both readers agree (`both`); only one read it (`model` or
`rules`: kept for a priced proposal, autonomy off); conflicting values, a whole rules term the model lacks, an ambiguous pairing
or the model's own unresolved scope still hold the offer. Pairing is one-to-one, same type, exact values first, overlapping
source spans required. If the rules reader fails, the model's reading stays a proposal with autonomy off. **It can only turn
autonomy off, never on.** In cache mode (scope S) the cross-check does not run.

**Build B (settlement dates, both modes).** A stated payment time in a single whole-invoice discount clause ("tomorrow",
"within 5 days", "this Friday", "2026-10-25", 本周内, 明天, 三天内) is parsed by fixed code (no model) into `PaymentTiming`, resolved
on the books' calendar from the message's day, and bound as the obligation's `effective_day`. The binder holds a date that is
stale, in the future, not before the invoice's due day, or inconsistent with a stated effective day. A promise is never a
receipt: cash and receivables move only on the bank feed. Unsupported timing (business days, holidays, time zones, "next week",
"before …", a bare "now") stays unread and holds the offer for clarification.

**This widens autonomy.** Until now every stated settlement time failed the coverage proof and went to the owner (S-06's interim
rule, from `docs/research/independent-security-working-2026-10-02.md` §S-06). With Build B, a provable stated day can satisfy
the proof, so **a buyer holding a valid counterparty key can have an early-payment discount at a stated day accepted at Tier 1
without the owner.** S-06's prescribed fix was exactly this ("ground requested/promised settlement timing into a typed field …
until this exists, any explicit timing including today/tomorrow must fail autonomous coverage"), and its required test 6
("change today to tomorrow to in 2 days; executable timing must change correspondingly or safely abstain") is what the branch
now pins. It is still a change to a certified control: the Security Lead decides.

## 3. The lead's review (19 Oct) and what was fixed

Verified read-only first, then fixed on this branch:

1. **Seven pinned S-06 tests failed on Build B's own branch** (`tests/nl/test_counterparty_channel.py`: stated day not accepted
   autonomously, en and zh). Build B's reported "3,432 passed" did not include them. **Fixed (`4604bfc9`)** by rewriting them to
   the new rule, not deleting them: today / tomorrow / tonight / right away / 今天 / 明天 bind that exact day; "now", 现在 and
   "after the holiday" bind nothing even with the buyer key.
2. **Chinese compound day counts were misread** (十五天内 → 5 days, 十一天内 → 1, 二十天内 → 10). The coverage proof caught them
   (owner review, not Tier 1), but the owner's proposal carried the wrong deadline. **Fixed (`2dceb944`)**: counts are read whole
   up to 九十九; a count preceded by a digit or numeral is refused.
3. **A bare "now" was read as "pay today" and accepted at Tier 1** ("We can now pay … early" bound a discount valid only for
   payment received today; without "now" the same message binds the facility's two-day lead). **Fixed (`2dceb944`)**: "now" and
   现在 leave the grammar; the coverage proof still lists them, so such a message is held.
4. **Reader evidence entered the commitment's terms hash** (`field_provenance`, and Build B's `payment_timing` with its source
   offsets; counters inherit both). Every comparison reads the same objects on both sides, so nothing mismatched, but the hash is
   meant to cover economics only. **Fixed (`32959e5b`)**: both are in `NON_ECONOMIC_FIELDS`; the bound `effective_day` still
   carries the promise; objects without them hash as before.
5. **Missing tests the next-builds handoff asked for**, added: the terms hash ignores the evidence fields and changes with a rate;
   a one-reader field is not accepted alone on the buyer's chat channel; the numeral and "now" cases.

The 5.3 review checklist (`HANDOFF_FLOW_full.md`), as the lead found it:

| Question | Answer |
| --- | --- |
| Can a model-only or rules-only value enable Tier 1? | No. Build A sets `autonomy_eligible` false whenever a field is not `both`; the verifier's `_autonomy_gaps` is the only Tier-1 acceptance gate; every accept path (chat, `/offers/{id}/accept`, buyer yes, negotiate) needs a verdict the executor re-checks. Tested through the verifier and the chat channel. |
| Bindings and hashes unchanged for existing objects? | Yes. Empty provenance and absent timing are omitted when serialised; both are excluded from the terms hash. |
| Consent rules kept? | Not touched by this branch (no `app/nl/consent.py`, sessions or pipeline change). |
| Executor the only place money moves; pause and mandate checks? | Not touched. Build B adds no operation; a promised day changes the verdict's valuation and the commitment's effective day only. |
| Does any reply now claim something the state does not support? | The new sentence "discount applies only to payment received by …" states the bound day; checked in en and zh on the presentation path, not re-audited across every surface. |
| New log lines free of values and credentials? | Build A logs field counts only; Build B adds none. |

## 4. Verification so far (not a gate)

| Check | Result |
| --- | --- |
| Port onto the tag | 16 commits applied cleanly; lint (`ruff check app tests`, CI's rule) clean |
| Wide API run on the branch before the last amendment: compiler, security, persistence, nl, verifier, decisions, domain, operations, financial, commitments, the two new API files | 5,812 passed, 4 skipped, 2 failed: Build B's own coverage cases expecting "now" to be proven; amended in `2dceb944` |
| The affected files after the amendment | 185 passed |
| Build A replay and fresh-run re-score (no provider calls), on the tag | identical to the committed results key for key |
| Build A evidence checksums | 26 of 26 verify; no key-like strings |

Measured by the build sessions (their evidence, not re-run by the lead):

| Measure | Before | After |
| --- | --- | --- |
| Build A, 17 recorded offers: correct and priced / held for no reason / rightly held / wrong | 3 / 5 / 9 / 0 | 6 / 2 / 9 / 0 |
| Build B, 36 new workflow items, rules (cache): completed workflows, wrong Tier-1 accepts | 0, 0 | 15, 0 |
| Build B, same items, live DeepSeek (40 approved calls): completed alone / with owner review / wrong Tier-1 | 0 / 3 / 0 | 2 / 13 / 0 |
| Attack catalogue (Build B session) | | 279 attacks, 0 harm, 120/128 named controls |

The live path is weak: the model often leaves the invoice amount off the obligation, so the date cannot be finalised and the
offer goes to the owner. Build B's evidence says so.

## 5. Open before any merge

1. **The full release gate on `4604bfc9`** (`HANDOFF_FLOW_full.md` §5.4): the whole API suite (the lead ran a wide subset, not all
   ~11,400), attack catalogue, sweep, reproductions and approval flip, PostgreSQL concurrency and guards, audits, secret scan,
   mock browser (desktop and phone) and live browser (one worker) on a quiet machine, CSP, judge pack, sandbox both transports.
   Build A's and B's sessions reported browser failures on their base (`home-v2.spec.ts:501/:1000` cash card height,
   `ask.spec.ts:83/:191`): **run a control on the untouched tag** to show whether they are pre-existing; on `66c31e7e` the gate's
   browser suites were green.
2. **The language-boundary certification** (`scripts/certify_language_boundary.py`) passes only with Build B's experiment
   adapter (`experiments/settlement-interpreter/language_boundary_adapter.py`): the frozen harness creates a pending approval with
   "next week", which is now held. Decide: update the harness setup, or record the exception.
3. **S-06 disposition**: the Security Lead's decision that a provable stated day may bind at Tier 1 (section 2), and the
   findings register / self-assessment wording that follows if it ships.
4. **Engine approval** for `app/financial/settlement.py` and `app/verifier/bind.py` (section 1).
5. **Evidence hygiene**: several logs under `experiments/` carry this Mac's absolute paths (`/Users/…`); the public-release
   cleanup removed such paths from the tree. Strip or relocate before `dev` if the repository goes public.
6. **The six unseen items** (`services/api/evals/live_unseen/`) were not re-scored against Build A or B (the experiments' base
   lacked them).
7. **Judging**: `dev`, `main` and the tag are one commit. The submitted documents link to the tag, so moving `dev` breaks no
   link, but the standing advice was to keep `dev` frozen until judging ends. The owner decides when.

## 6. Residual risks to weigh

- **Autonomy widened (by design):** a keyed buyer's dated early-payment offer may now be accepted alone. The guards hold stale,
  future, not-early and inconsistent days; the grammar refuses holidays, business days, time zones, "before", "next week", bare
  "now" and anything with "due", "until" or "not" in the message. A wrong-but-plausible date (for example a buyer who writes
  "tomorrow" meaning a business day) binds the stricter day: the discount applies only to payment received by then.
- **"by" and "on" bind the same day.** "Pay tomorrow" and "pay by tomorrow" both bind day +1 as the last day for the discount.
- **Week end** (本周内, "by the end of this week") resolves to Sunday of the message's week.
- **The live reader's gain is small**; most dated live offers still reach the owner.
- **R-3 (open, unchanged):** a persuaded-but-authorised agent can act at Tier 1 inside the mandate; Build B adds dated discounts
  to what Tier 1 covers.

## 7. How to fold it in, if certified

```bash
git fetch origin
git switch dev && git pull --ff-only
git merge --no-ff origin/feat/reader-dates   # a merge(...) message in the owner's format, no co-author trailer
```

Never move `main` or the tag `submission-2026-10-20`. If `dev` has moved since `4e03f0cf`, merge `dev` into the branch first and
re-run the gate on the merge commit. Record the certification as for `66c31e7e` (`CERTIFICATIONS.md` entry, `RELEASE_GATE.md`
row, evidence folder with `security_manifest.py`).

The original local branches (`exp/field-cross-check` 3a61acea, `feat/settlement-interpreter` d82af8d0) exist only on the owner's
Mac; everything in them is on `feat/reader-dates`.
