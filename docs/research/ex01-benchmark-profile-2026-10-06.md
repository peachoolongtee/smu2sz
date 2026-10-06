# EX01 evaluate benchmark: profile and diagnosis (6 Oct 2026)

Test: `services/api/tests/funding/test_benchmark.py::test_ex01_evaluate_under_250ms`. It clears the cross-evaluation
caches (`app.whatif.clear_cache`, `app.verifier.clear_caches`) before every run, times one `evaluate(...)` of
`EX01_PACKAGE` on the golden scenario, and takes the best of three. Nothing in `services/api/app`, the target, the
test or any golden figure was changed to produce this document.

Machine: Apple M4 Pro, 12 cores, Python 3.12.14, `uv sync` at `origin/dev` `38d8047`. Load average was 5 to 7 (other
agent sessions on the same Mac), so absolute numbers carry some noise; the `159 ms` the task board recorded for
`3b139df` reproduces here as 159 ms, so the harness is comparable with the author's.

## 1. Reproduction

`uv run pytest -o addopts= -q tests/funding/test_benchmark.py`, three runs in a row, unchanged tree:

| run | EX01 evaluate (best of 3 cold) | result |
|---|---|---|
| 1 | 257.0 ms | 1 failed, 6 passed |
| 2 | 263.6 ms | 1 failed, 6 passed |
| 3 | 266.5 ms | 1 failed, 6 passed |

(`assert 257.04... < 250`, `263.60... < 250`, `266.49... < 250`.) Only the EX01 test fails; the six others (four
what-if presets, plan, compare) pass.

## 2. Is it a first-call cost? No

The test already takes the best of three, and it times only the `evaluate` call: module imports, fixture loading and
the offer compile are outside the timed region (`compile_offer` is a fixture-cache hit, 0.1 ms in the log).

Eight consecutive cold `evaluate` calls in one fresh process (caches cleared before each, first call first):

    268.1, 276.8, 266.1, 256.0, 277.1, 258.4, 267.3, 264.8 ms

The first call (268 ms) is the same as the rest. Within-process warm-up therefore removes nothing: there is no
lazy import, schema build or `lru_cache` fill that the first call pays and later calls do not. Repeating the call
with the two cross-evaluation caches left in place (the baseline plan and the section 7.4 comparison) gives
198.6 and 200.1 ms. That is the "warm" figure, about 65 ms lower, and it is exactly the cost of the two searches
the test deliberately re-runs (baseline 30 ms, comparison 25 ms, see section 4); it is not a hidden one-off cost,
it is what "cold" means in this test's docstring.

Import cost (`python -X importtime`, outside the timed region): the whole `app.verifier`, `app.compiler`,
`app.whatif`, `app.funding`, `app.mandate` import is about 0.7 s on this Mac (695 ms measured in-process).
Largest items: `app.compiler` 434 ms cumulative (of which `app.compiler.rules` 184 ms self, `lexicon` 94 ms,
`coverage` 51 ms), `app.verifier` 269 ms cumulative, `app.domain.models` 153 ms, pydantic 38 ms. None of it is
paid inside the benchmark's measured window.

## 3. Where the time goes (cProfile, one cold evaluate)

cProfile inflates the run to 0.73 s (profiler overhead, about 2.8x); use the shares, not the absolute figures.
Full output is in section 7. Top by cumulative time:

| share | function | note |
|---|---|---|
| 100% | `evaluate` / `_evaluate` | 1 call |
| 88% | `router._run` / `search.Search.run` / `_search` | 12 searches, 13 `_run` calls |
| 59% | `counters.counters_explained` | 1 call, 0.44 s: the counters (Option A / Option B), each re-checked |
| 42% | `counters.price_adjustment_counter` | 2 `_price_adjustment_at` calls: 60-day then 55-day terms |
| 16% | `evaluate._early_pay_vs_plan` | ADR-0007 tests 2 and 3 |
| 13% | `reserve.baseline` | the status-quo plan |
| 10% | `evaluate._comparison` / `router.compare` | the section 7.4 table |
| 25% | `trajectory.project` (174 calls) | the cash/covenant projection candidates are scored on |
| 29% | `cashpath.run` (2,532 calls) | the cash-only probe inside the search |
| 12% | `fractions.Fraction` `forward` / `_mul` | 51k exact-arithmetic calls; 94k `Fraction.__new__` |

By self time the leaders are `trajectory.project` (55 ms of 732), `dict.get` (36), `cashpath.run` (32),
`Fraction.__new__` (28), pydantic `validate_python` (22), `Fraction.forward` (22), `Search._search` (18). It is a
flat profile of exact-rational arithmetic and projection in the router search; there is no single dominant call.

A direct instrument of `Search.run` (no profiler) shows where the 12 searches fall. Total evaluate 294 ms, searches
249 ms (85%); every search has distinct inputs (no duplicate that the in-evaluation memo should have caught):

| ms | caller | obligations |
|---|---|---|
| 65.8 | `_price_adjustment_at` (55-day terms, passes re-check) | 2 |
| 41.1 | `_early_pay_vs_plan` | 2 |
| 40.4 | `_price_adjustment_at` (60-day terms, fails re-check) | 2 |
| 29.9 | `baseline` (cleared by the test) | 0 |
| 24.8 | `_comparison` -> `compare` (cleared by the test) | 0 |
| 14.8 | `evaluate` plan, EXPECTED basis | 3 |
| 6.0 to 6.8 | four small ones: COMMITTED plan, cure_plan, `early_pay_counter`, re-check | 1 to 3 |
| 2.0 and 4.2 | `cure_plan` after each price-adjustment attempt | 2 |

The two price-adjustment searches (106 ms, 36% of the evaluate) are the largest block: Option B first tries the
offered 60-day terms, the re-check fails (EX01 Option B is 55 days at 0.30%, `FINANCIAL_SEMANTICS.md`), and it
then tries 55 days, each on a different obligation set so each needs its own search.

## 4. When the cost arrived (bisect on the same harness)

Best-of-7 cold `evaluate` of EX01, same script, each commit's `services/api/app` and `fixtures` extracted
(`git archive`), run in the current venv:

| commit | date | EX01 evaluate | what landed |
|---|---|---|---|
| `b69a6be` | 1 Oct 05:14 | 107 ms | the benchmark is added; target 250 ms is 2.3x |
| `3b139df` | 1 Oct 05:39 | 159 ms | router speed-up (task board: 374 -> 159 ms) |
| `3dea6ca` to `1606bdf` | 1 Oct | 160 ms (flat) | current books, commitments, settlement, reconciliation |
| `0ba5a1c` | 1 Oct 14:30 | 178 ms | Counter A rounding and its floor re-check (+18 ms) |
| `3dc8033` | 1 Oct 15:38 | 270 ms | ADR-0007 early-pay acceptance rule (+93 ms; `_early_pay_vs_plan`) |
| `5d3074b` | 1 Oct 16:24 | 286 ms | |
| `094319e` | 3 Oct 08:24 | 511 ms | the parent of the counter-feasibility merge |
| `3db68b0` | 3 Oct 09:24 | 1,058 ms | counter feasibility: every counter re-checked, Option B walks terms down |
| `919de9f` | 3 Oct 13:41 | 279 ms | evaluation-latency merge (books booked once per search, integer pruning, shared router runs) |
| `db097e0` | 3 Oct 16:13 | 292 ms | the last application change before now |
| `38d8047` (now) | | 255 to 277 ms | |

So the test has been over its target since `3dc8033` on 1 Oct, about eleven hours after it was written: a new
required check (ADR-0007) added about 90 ms of router search, then Option B's term walk added more, and the 3 Oct
latency work brought the figure from 1,058 ms back to about 280 ms but not below 250. `docs/NEXT_FIXES.md` already
recorded one 261 ms miss ("isolated rerun passed"); the 5 Oct 270 ms figure is the same condition. It is not a
regression in the last week: the application code is unchanged since `db097e0` (292 ms on this harness, 255 to 277 ms
today, the difference being load).

## 5. Diagnosis

The excess is a steady-state cost, not a one-off. The engine now does what the spec requires per EX01 evaluation:
12 distinct exact router searches (status quo, committed, expected, early-pay-versus-plan, comparison, two Option B
terms, the cures and the counters' re-checks), 25 to 29% of it each in `project` and `cashpath.run` (nested), about 12% in
`Fraction` arithmetic. A warm-up cannot remove it and the test's own best-of-three already discards any one-off. At
the time of writing the Mac reads 255 to 277 ms, i.e. 2 to 11% over target, and Windows reads at or just over 250
ms: the target has about 0 headroom against the real work, so it fails on machine and load noise alone.

## 6. Recommendation

Raise the EX01 target to 350 ms (the what-if preset target is 400 ms; the figure keeps about 25% headroom over the
280 ms steady state and still catches the 3 Oct kind of regression, 500 to 1,000 ms), updating the docstring to say
that the budget is set by a measured cold figure of 255 to 290 ms made of 12 router searches (the two Option B term
attempts 106 ms, the early-pay-versus-plan search 41 ms, the cold baseline and comparison 55 ms). If the lead would
rather hold 250 ms, the only hot-path change that moves it by itself is in `price_adjustment_counter`: the 60-day
attempt (40 ms search plus a failing re-check) is run before the 55-day one, and the failure of the offered terms
is decided by the same reserve shortfall that `reserve.cure_plan` finds, so a cheap pre-test (does the plan for these
terms keep the reserve with a curable shortfall) could skip the full search at terms already known to fail; saving
at most 40 ms, and only if it provably gives the same verdict and notes text, which needs the lead's review since it
is on the counter path. Rewriting `project`/`cashpath.run` (or `Fraction` -> integer arithmetic) would also work but
touches the financial core and is not worth the risk for a 2 to 11% miss. I recommend raising the target and not
touching `app`. I made no change to the test: there is no one-off first-call cost to warm up.

## 7. Raw output

Scripts are in the scratchpad of this session (cProfile of one cold `evaluate`; instrumented `Search.run`; per-commit
bench). The cProfile output, trimmed to 45 rows by cumulative time and 25 by self time:

```
import ms 695.3262500173878
per-run ms (first first): [268.1, 276.8, 266.1, 256.0, 277.1, 258.4, 267.3, 264.8]
no-clear warm ms 198.5980840108823
no-clear warm ms 200.1371670048684
         3509953 function calls (3489561 primitive calls) in 0.732 seconds

   Ordered by: cumulative time
   List reduced from 578 to 45 due to restriction <45>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.750    0.750 evaluate.py:989(evaluate)
      4/1    0.000    0.000    0.746    0.746 evaluate.py:520(_evaluate)
       13    0.000    0.000    0.656    0.050 router.py:192(_run)
       12    0.000    0.000    0.643    0.054 search.py:820(run)
       12    0.018    0.002    0.643    0.054 search.py:830(_search)
       11    0.000    0.000    0.620    0.056 router.py:287(plan)
       11    0.000    0.000    0.506    0.046 evaluate.py:144(plan)
        1    0.000    0.000    0.438    0.438 counters.py:656(counters_explained)
        1    0.000    0.000    0.438    0.438 counters.py:737(_counters)
     7956    0.010    0.000    0.416    0.000 search.py:776(fill)
        1    0.000    0.000    0.310    0.310 counters.py:464(price_adjustment_counter)
        2    0.000    0.000    0.310    0.155 counters.py:498(_price_adjustment_at)
     9215    0.013    0.000    0.269    0.000 search.py:702(probe)
        2    0.000    0.000    0.257    0.129 evaluate.py:970(plan)
     2532    0.032    0.000    0.210    0.000 cashpath.py:224(run)
      121    0.001    0.000    0.198    0.002 search.py:570(evaluate)
      174    0.055    0.000    0.186    0.001 trajectory.py:984(project)
     9215    0.002    0.000    0.167    0.000 search.py:748(consider)
        3    0.000    0.000    0.153    0.051 counters.py:161(why_not)
        3    0.000    0.000    0.153    0.051 evaluate.py:974(__call__)
     2714    0.007    0.000    0.148    0.000 trajectory.py:625(_apply_actions)
    71698    0.017    0.000    0.127    0.000 search.py:912(_beaten)
        4    0.000    0.000    0.119    0.030 evaluate.py:326(_early_pay_vs_plan)
        1    0.000    0.000    0.103    0.103 counters.py:695(_passes)
    19408    0.007    0.000    0.099    0.000 search.py:896(_cls)
        5    0.000    0.000    0.095    0.019 reserve.py:57(baseline)
        1    0.000    0.000    0.094    0.094 reserve.py:48(_baseline)
    51179    0.022    0.000    0.088    0.000 fractions.py:613(forward)
    39754    0.010    0.000    0.086    0.000 search.py:873(_over)
     3742    0.003    0.000    0.077    0.000 search.py:527(action_pricing)
        4    0.000    0.000    0.076    0.019 evaluate.py:502(_comparison)
        2    0.000    0.000    0.076    0.038 evaluate.py:162(_compare_cached)
      183    0.000    0.000    0.076    0.000 search.py:641(executed)
        2    0.000    0.000    0.076    0.038 router.py:310(compare)
       74    0.000    0.000    0.076    0.001 search.py:666(executable_order)
       78    0.000    0.000    0.076    0.001 search.py:657(refused)
     2631    0.001    0.000    0.072    0.000 rates.py:110(action_rate)
     2188    0.000    0.000    0.061    0.000 search.py:540(action_rate)
       12    0.000    0.000    0.060    0.005 search.py:808(_probe_units)
        3    0.000    0.000    0.056    0.019 reserve.py:158(cure_plan)
     1096    0.007    0.000    0.054    0.000 trajectory.py:544(_finance_invoice)
      174    0.002    0.000    0.053    0.000 evaluate.py:107(evaluate)
     5845    0.009    0.000    0.051    0.000 fmt.py:17(pct)
     1508    0.004    0.000    0.047    0.000 trajectory.py:467(_draw)
    20389    0.013    0.000    0.047    0.000 money.py:25(round_half_up)



         3509953 function calls (3489561 primitive calls) in 0.732 seconds

   Ordered by: internal time
   List reduced from 578 to 25 due to restriction <25>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      174    0.055    0.000    0.186    0.001 trajectory.py:984(project)
   588590    0.036    0.000    0.036    0.000 {method 'get' of 'dict' objects}
     2532    0.032    0.000    0.210    0.000 cashpath.py:224(run)
    94154    0.028    0.000    0.037    0.000 fractions.py:186(__new__)
    34897    0.022    0.000    0.022    0.000 {method 'validate_python' of 'pydantic_core._pydantic_core.SchemaValidator
    51179    0.022    0.000    0.088    0.000 fractions.py:613(forward)
    23853    0.019    0.000    0.019    0.000 trajectory.py:1036(<genexpr>)
       12    0.018    0.002    0.643    0.054 search.py:830(_search)
   232937    0.018    0.000    0.034    0.000 {built-in method builtins.isinstance}
    42565    0.017    0.000    0.031    0.000 fractions.py:742(_mul)
    71698    0.017    0.000    0.127    0.000 search.py:912(_beaten)
      169    0.013    0.000    0.021    0.000 clean_down.py:52(line_balances)
    20389    0.013    0.000    0.047    0.000 money.py:25(round_half_up)
     9215    0.013    0.000    0.269    0.000 search.py:702(probe)
    73091    0.012    0.000    0.016    0.000 fractions.py:317(_from_coprime_ints)
   193540    0.011    0.000    0.011    0.000 {built-in method __new__ of type object at 0x10106e258}
     7956    0.010    0.000    0.416    0.000 search.py:776(fill)
    39754    0.010    0.000    0.086    0.000 search.py:873(_over)
    21627    0.009    0.000    0.013    0.000 search.py:865(_lb)
   139237    0.009    0.000    0.009    0.000 {built-in method math.gcd}
    20303    0.009    0.000    0.011    0.000 fmt.py:10(y)
     5845    0.009    0.000    0.051    0.000 fmt.py:17(pct)
    80296    0.009    0.000    0.016    0.000 <frozen abc>:117(__instancecheck__)
    26934    0.009    0.000    0.020    0.000 fractions.py:933(_richcmp)
    65118    0.009    0.000    0.031    0.000 {built-in method builtins.sum}



```
