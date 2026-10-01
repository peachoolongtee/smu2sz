# Compiler accuracy: what we can honestly claim (1 Oct 2026, commit 389cfd9)

| Set | Independence | Path | Verdict agreement | Material error rate | Silent material errors | **Wrong autonomous accepts** |
| --- | --- | --- | --- | --- | --- | --- |
| Held-out 3, first run (before ADR-0005) | **independent, unseen** | rules grammar | 33/63 (52%) | 4/51 (7.8%) | 7 | **4 of 8** |
| Held-out 3, after round 3 | its failure classes guided round 3 | rules grammar | 46/63 (73%) | 3/51 (5.9%) | 4 | **0** (2 correct) |
| Held-out 3, after round 3 | the prompt was not tuned on it | **live DeepSeek (`deepseek-flash`)** | 42/63 (67%) | 3/51 (5.9%) | 5 | **0** (1 correct) |
| Held-out 2, after round 3 | its classes guided round 2 | rules grammar | 41/47 (87%) | 0/37 | 0 | **0** (4 correct) |
| Form baseline (labels typed in) | — | no compiler | 61/63 (97%) | — | — | — |

**The claim we make:** across every set and both compiler paths, **no misread message was accepted without the owner** after ADR-0005. The architecture lets autonomy happen only on a positive coverage proof plus a stated whole-invoice amount. Free-text understanding is still imperfect: about 1 in 3 messages is not decided the way a human would on first reading. Those cases fall to the owner's queue, a counter, or a request for clarification, never to an unauthorised commitment. Most good early-pay offers also wait for the owner, because they mention a settlement date that the compiler doesn't read into the terms.

**The claim we don't make:** a compiler accuracy figure from a set it was tuned on. The only untuned figure is the first held-out-3 row.

Reproduce:
```bash
uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout3
LLM_PRIMARY=deepseek uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout3 --live
```
