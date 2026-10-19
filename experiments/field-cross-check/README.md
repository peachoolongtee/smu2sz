# Field-classified cross-check experiment

Experimental Build A, independent of the 20 October submission. No deliverable,
submission document, submission evidence file, fixture, dev/main pointer or tag
was edited. This branch is not a release or a security certification.

## Base and scope

Branch: `exp/field-cross-check`. Implementation commit: `4bd24d07`.

The handoff names `submission-2026-10-20` and code `66c31e7e`, with
`03215a2073a49e9bd72603561fcad67c3810c902` as its fallback. The tag and newer
commit were unavailable on the remote when work began; the remote dev pointed
to the explicit fallback. This experiment branches from that exact fallback,
without changing the local dev/main branches. It does not include later security
fixes described in the handoff. Porting to a newer base needs another review and
relevant checks; no merge into dev is authorized here.

The owner explicitly approved field provenance on obligations and owner review
for model-only fields, while retaining financial formulas and settlement-date
semantics. Those semantics, the verifier, executor, mandate, funding and receipt
logic are unchanged. Builds B-F are outside this implementation.

## What the diagnosis actually found

The original checker already permits fields/terms found only by the model. Its
important asymmetry is the reverse: a model omitting a value the rules found is
classified as disagreement. In the stored LF01/LF03/LF04 readings, the model
omitted future-invoice scope and/or the invoice face. These omissions held offers
whose decision-critical labels both readers otherwise met. The remedy is not
to remove the cross-check or lower financial thresholds.

## Field decisions

| Two grounded typed readings | Decision |
| --- | --- |
| Same known value | Retain; provenance `both` |
| Model has a value, rules have none | Retain for proposal/review; provenance `model`; no autonomous acceptance |
| Rules have a value, model has none | Fill only a uniquely paired term, retain both sources' spans; provenance `rules`; no autonomous acceptance |
| Different known values | Hold the offer; do not overwrite either value |
| Rules term missing entirely from model, or ambiguous clause pairing | Hold; do not silently insert a whole obligation |
| Model explicitly leaves scope/end unresolved | Keep the hold, even if the rules have a default base |
| Neither reader has a value | Preserve existing incompleteness; no invented value |
| Rules backend unavailable | Preserve a review-only model proposal; no autonomous acceptance |

Pairing is one-to-one, same-type, exact-values first, with overlapping source
spans required. Repeated clauses without a unique pairing hold. Counterparty,
effective day and duration end are included in material comparison. Money and
rates compare in the existing normalized integer units; no floating-point or new
wording parser was introduced. Provenance says which reader supplied a typed
value, not that its meaning is correct; shared defaults can agree incorrectly.

Conflicts still hold the whole offer atomically. Partial execution or deciding
only selected parts of a disputed package requires a separate design. No
clarification answer becomes consent. Existing coverage notes, model abstentions
and security flags are preserved, and field completion cannot create autonomy.

Empty provenance is omitted from serialized historical objects, preserving their
existing hashes. Checked live objects retain provenance in owner API responses
and memory/SQLite storage. Compiler logs distinguish agreement, review-only and
disagreement using field counts, without logging financial values or credentials.

## Evidence: controlled replay, not a live-model claim

`replay.py` applies the original and experimental checks to the **same recorded
raw model and rules readings**, then invokes the unchanged financial verifier.
The original labels and recordings are read-only; their SHA-256 hashes are in the
report. Seventeen buyer-offer items are replayed; three contracts are excluded.

| Outcome on 17 recorded offers | Original check | Experimental check |
| --- | ---: | ---: |
| Correct reading and non-held verifier result | 3 | 6 |
| Unnecessary holds | 5 | 2 |
| Appropriate holds | 9 | 9 |
| Wrong interpretations under the stored labels | 0 | 0 |

LF01, LF03 and LF04 change from unnecessary holds to correct readings and priced
REJECT decisions. None becomes an autonomous acceptance. LF12 remains held over
a duration conflict; LF15's unresolved scope and LF20's hostile concession claim
remain held. The report asserts that evaluating each item leaves the books unchanged.

Important comparator: the historical rules-only run on these same 17 offers
recorded six correct readings, two unnecessary holds, seven appropriate holds and
two wrong results. This experiment restores completion to that recorded rules
count while retaining the cross-check's holds on unsafe cases. It does **not**
show more completed buyer-offer tasks than rules alone. The historical live runs
were separate provider samples, so their full 20-item totals are not the controlled
replay baseline. This is known-item regression evidence, not independent or blind
validation, a fresh model run, a full workflow evaluation, or production assurance.

The recorded-reader replay makes no provider calls. The separate approved fresh
run below made 23. The handoff's six unseen items were not available
at the fallback base and were not recreated or relabelled. No claim is made about
their outcome. Settlement-date interpretation remains Build B; it was not smuggled
into the reader change.

## Reproduce safely

From the repository root, with the API's installed Python environment:

```sh
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache \
  python experiments/field-cross-check/replay.py --out /tmp/field-check-replay.json
```

The runner sets the safe environment before importing app modules and calls no
provider, HTTP endpoint or database. It requires the fallback commit locally to
load the original checker. Test commands and final results are in `checks.json`;
the controlled reader replay is in `replay.json`.

Full-app lint on the fallback has 65 findings in 29 files unchanged by this
experiment. Changed application/test files and the runner pass lint. These
inherited findings are not silently fixed or waived. The full mock browser run
has 477 passes, 77 skips and two reproducible layout failures in unchanged web
code (home-v2.spec.ts:501 and :1000). Both fail again with one worker: phone-width
overflow after resizing, and a 375px cash card against a 360px maximum. This is
not a green integration gate. UI code and assertions were left unchanged.


## Fresh DeepSeek run: 19 October 2026

After explicit owner approval for credential use, external transmission of these
synthetic documents and a maximum of 30 paid requests, the API-only loader ran the
new path on the original 20 known items. It used 23 provider requests (76,012 prompt
and 6,337 completion tokens, 82,349 total reported tokens). No monetary cost was
estimated. SDK retries were disabled and a request hook enforced the cap. The
provider returned the alias `deepseek-flash`, not an immutable model version.
Redaction was on; the database was memory only; the server listened on loopback
8585 and was stopped by its recorded PID after the run. Credentials were neither
printed nor copied into evidence. The API loader was the only process to load the
credential file. The archived driver is evidence text, not a product launcher or
permission for another paid run.

**Actual 20-item API outcome:** 7 correct, 1 partly correct, 0 wrong, 10 appropriate
holds, 2 unnecessary holds; 36/36 returned term spans match their sources. This
remains a known-item, post-fix sample, not blind validation. The whole API run
recorded 4 operations, but zero new commitments, money movement, facility additions
or unauthorized executions. Do not confuse zero financial harm with zero logged
operations or proof of safety on unseen inputs.

The API instrumentation captured identical grounded model/rules readings for
both the original and experimental checks. `score_live_shadow.py` independently
recomputes both checks from those inputs, evaluates with the unchanged verifier,
and asserts that new-path grades match the observed API grades.

| On 17 matched fresh buyer-offer readings | Rules only | Original check | Experimental check |
| --- | ---: | ---: | ---: |
| Correct reading and non-held verifier result | 6 | 2 | 5 |
| Unnecessary holds | 2 | 5 | 2 |
| Appropriate holds | 7 | 10 | 10 |
| Wrong under the stored labels | 2 | 0 | 0 |

LF01/LF03/LF04 again become correct priced REJECT proposals instead of unnecessary
holds, without becoming autonomous acceptances. LF13 is now an appropriate model
hold under its read-or-abstain label; that is why the fresh paired result differs
from the historical replay. This change recovers three useful proposals compared
with the old check on identical fresh responses. It **does not** prove superior
completion to rules alone: the fresh hybrid reads five correctly against rules'
six, while avoiding their two labelled wrong results. Unseen usefulness and full
workflow generalization still need separate evaluation.

Re-score the fresh evidence without any provider call:

```sh
python experiments/field-cross-check/score_live_shadow.py \
  --input experiments/field-cross-check/evidence/fresh-live \
  --out /tmp/field-check-fresh-comparison.json
```

The stored API result includes three contracts, which are outside the reader
cross-check change. The matched comparison excludes them rather than silently
combining changed and unchanged functionality.

## Browser and static-check exceptions

The API-backed browser run used recorded/cache LLM mode, one worker, web 3423 and
API 8584. It returned 175 passed, 51 skipped and two failures (ask.spec.ts:83 and
:191), both waiting for the Ask FLOW dialog to become visible. UI source is
unchanged by this branch; these failures are reported, not waived or hidden. An
untouched-base control browser run was not performed. Together with the two mock
layout failures and inherited lint findings, they mean no green integration or
release gate is claimed. Web typecheck and lint pass; web unit tests: 187 passed.
No full 11k API release suite, PostgreSQL release gate or new deployment audit was
run. Nothing was merged into dev, main or the submission tag.


## Final regression snapshot

On implementation commit `4bd24d07`, the compiler/security/consent plus new API and
persistence regressions finished with **2,131 passed, 1 skipped**. The two warnings
concern Hypothesis falling back to in-memory example storage. The earlier 95-test
focused result overlaps this set and is not added to its count. The standalone
attack and language-boundary reports were produced during implementation before
the last compiler logging change; the final security regressions were rerun on
the committed code. The unchanged rules-path autonomy funnel still accepts only
3 of 14 labelled good offers autonomously across 115 messages, with zero wrong
autonomous accepts. This build does not claim Build B's date-related coverage gain.

`checks.json` lists every gate and its exceptions. `SHA256SUMS` covers this report,
scorers, replay data, check manifest and stored evidence. No merge or publication
of a release is implied by the local experiment commits.
