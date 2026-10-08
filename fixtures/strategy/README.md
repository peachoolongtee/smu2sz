# Strategy oracle fixtures

Recorded output of the research spikes in `services/api/scripts/research/` (wayfinder map #47, ticket #48). They are the
differential oracle for the read-only strategy MVP: the production code that replaces a spike must reproduce these figures.
Every amount is `{"fen", "display"}` and every rate `{"bp", "display"}`; the `_meta` object at the top of each file holds
the command, branch, base commit and date of the recording.

| File | What it is | Command (from the repository root) |
| --- | --- | --- |
| `envelope_day0.json` | Safe Deal Envelope for BUYER-1 on the day-0 golden books: lever maxima, the terms x price zone, the package grid | `envelope_spike.py --json` |
| `collections_both.json` | Collections worth on the day-0 and day-34 books: ranking, early-pay ceilings, cash price curve | `collections_spike.py --day both --json` |
| `portfolio_default.json` | Portfolio enumeration of EX01, EX08A, EX08B and the greedy `evaluate_many` order | `portfolio_spike.py --json` |
| `envelope_packages.json` | The deep dive's nine interaction packages (ten evaluations: package 8 at price 95 and 100) as whole verifier evaluations; the document holds `_meta`, the buyer and `requested` | `envelope_spike.py --json --package K=V,...` (one flag per package; the exact list is in `_meta.command`) |

Nothing in the app reads these files. Only `services/api/tests/strategy` does.

## Re-record

Never edit a file by hand. Run each script with the environment below, send stdout to the file, then add the `_meta` object
as the first key (load, insert, dump with `ensure_ascii=False, indent=2`) and update the pins in
`services/api/tests/strategy/test_oracle_fixture.py` if a figure moved on purpose.

```
FLOW_RESEARCH_SPIKES=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \
  uv run --project services/api python services/api/scripts/research/<script>.py <flags> > fixtures/strategy/<file>.json
```

The `seconds` fields are wall-clock timings and differ on every run; the tests do not read them.
