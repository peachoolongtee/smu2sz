# Chinese contract reading

**Status: the result table is not in the repository.** The scoring harness and its fixes are merged (branch `fix/contract-reading-cn`, merged into `dev` as `c93efa17`), but the 30-contract Chinese set and its answer key are not committed, so no per-field table can be reproduced from this repository and none is quoted here. `services/api/evals/contracts_heldout_report.md` still says "pending" for the independent held-out set (`fixtures/contracts_heldout/`).

What is on record, from the merge commit message: reading of the 30-contract set moved from **59% to 66%** field-level agreement with the answer key.

What changed in the reading (same message):

- no wrap space is left inside a CJK word;
- dates in Chinese numerals (二〇二五年十二月十七日) are read;
- a supplier's penalty or a performance bond is not read as late interest or retention;
- a price stated twice (and again inside its own total) is read once;
- performance start and end dates are derived from a period counted from signing;
- stage percentages, stage amounts and the amount in words are cross-checked;
- DeepSeek runs without thinking so long contracts return.

The contract reading is a proposal labelled "AI-generated, for reference"; the owner confirms or rejects it, and it changes no books (ADR-0012).

## Re-scoring it

The harness is `services/api/scripts/eval_contracts.py` (read-only; writes only under `--out` and `--cache-dir`). Offline it uses the cache and the rules grammar, so it needs no key:

```bash
cd services/api
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache \
  uv run python scripts/eval_contracts.py DOC_OR_DIR... --key answer_key.json --out OUT_DIR
```

`OUT_DIR` receives `predictions.json` in the key's shape and the per-field, per-format and per-family tables. `--live` reads with DeepSeek and needs a key; we ran no live scoring for this pack. The mapping from FLOW's terms to the key's fields is in the script's docstring, and the mapping and the scoring are covered by `tests/compiler/test_eval_contracts.py`.

The three demo contracts in `fixtures/contracts/` are not a measurement set: the grammar was written against them.
