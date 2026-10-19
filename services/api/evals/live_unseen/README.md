# Live unseen set

A small, pre-labelled UNSEEN evaluation set for FLOW's model-assisted reading, to show (or fail to show) that the shipped
path completes a useful workflow on new text. Modelled on `../live_frozen`, and scored by the same runner
(`../live_frozen/run.py --items`) with the same rules (see that README's "What is scored").

- `items.yaml`: 6 new synthetic buyer messages from BUYER-1 Foshan Home Retail Co. on the golden demo books (open invoice
  RCV-A ¥420,000, 45-day terms; mandate: ¥5,000 aggregate forward concessions, 1.5% immediate-discount cap; break-even
  discount 0.88%). 3 English, 3 Chinese. No injection items.
- `results_rules_baseline_2026-10-19.*`: the rules grammar in cache mode, not a model.

Each message is one a real buyer might send, whose correct reading is clear to a person but phrased so a grammar may miss
it (colloquial Chinese, indirect English, terms spread across sentences), and whose correct reading leads to a verdict the
owner can act on: a discount below break-even the agent may accept, or a concession over the cap that needs a counter.
LU06 is a hold by design; a hold on any other item scores as "abstained wrongly", so holding is never success by default.

| id | lang | what it tests | blind label |
|---|---|---|---|
| LU01 | en | a rate in words over four sentences ("half of one percent" holds "one percent") | read: IMMEDIATE_DISCOUNT 0.5% on ¥420,000, firm, one-off; an autonomous accept is allowed |
| LU02 | zh | colloquial "让零点六个点" for paying the 42万 early | read: IMMEDIATE_DISCOUNT 0.6% on ¥420,000, firm, one-off; an autonomous accept is allowed |
| LU03 | en | one extension spread over three sentences (45 now, "sixty days", six invoices) | read: TERMS_EXTENSION 60 days, bounded to 6 invoices; owner needed (a counter) |
| LU04 | zh | "返两个点" if H1 purchases pass 一百万, and "照现在的45天走，不变" (no change) | read: CONTINGENT_REBATE 2%, contingent, nothing else; owner needed (a counter) |
| LU05 | zh | "九九五折" on "四十二万", and "以后的票都按六十天走" | read: IMMEDIATE_DISCOUNT 0.5% on ¥420,000 + TERMS_EXTENSION 60 days, perpetual; owner needed (a counter) |
| LU06 | en | two alternatives, one approximate ("in the region of 1%, give or take"), one unquantified | abstain: hold and ask which option and what figure |

## Protocol

1. The six texts were written new for this set; the repository was searched for each distinctive phrase first and held
   none of them.
2. Every label was written blind, before any run of these texts against any backend (no rules grammar, no API, no
   compiler call, no test). `items.yaml` and a draft of this README were committed on their own in **a79cb7a7**, before
   the first run. `items.yaml` sha256: `6daca796530bad1c8b5ff550bc1fa5f545cb23d4e087b02672485ab18acbf9fc` (every result
   records it; a different value means the file was edited).
3. `run.py` gained `--items` in 83b31bce (backward compatible; the scoring is unchanged).
4. The rules baseline was taken next, in cache mode, and committed as it came out in d7680bc2.
5. **Untuned.** No edit to `items.yaml` (texts or labels) after any output has been seen. Results are committed as they
   come out and reported whatever they show. A fix made after seeing output is measured in a separate run
   (`--label live_after_fixes`), reported beside the untuned one, never in place of it.

## The rules baseline (2026-10-19)

Rules grammar, cache mode, not a model. API on 127.0.0.1:8583 with
`TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 LLM_MODE=cache FEATURE_ASK_ROUTER=1 FEATURE_CONTRACT_TERMS=1 FEATURE_CAPEX_CONTRACTS=1`.
Every reading was a cache miss, then `rules-v1`. 31 requests, 6 reading requests.

| id | class | what happened |
|---|---|---|
| LU01 | correct | IMMEDIATE_DISCOUNT 50 bp on ¥420,000, firm, one-off; verdict NEEDS_OWNER_APPROVAL (Tier 2: autonomy not proven, the window "within the week" and other text not read into the terms) |
| LU02 | abstained wrongly | nothing read ("零点六个点"); NO_VERDICT, UNRESOLVED_SCOPE |
| LU03 | abstained wrongly | nothing read ("sixty days" over three sentences); NO_VERDICT, UNRESOLVED_SCOPE |
| LU04 | abstained wrongly | CONTINGENT_REBATE 200 bp read, then a hold on the unread "45天"; NO_VERDICT, clarification asked |
| LU05 | abstained wrongly | nothing read ("九九五折", "六十天"); NO_VERDICT, UNRESOLVED_SCOPE |
| LU06 | abstained correctly | a hold (a concession mentioned without its value); NO_VERDICT, clarification asked |

| class | count |
|---|---|
| correct | 1/6 |
| partially correct | 0/6 |
| wrong | 0/6 |
| abstained correctly | 1/6 |
| abstained wrongly | 4/6 |

Source-span grounded: 2/2 terms read. Nothing was booked on any item. The grammar is safe here (nothing wrong) but does
not complete the workflow: four of the five readable messages end in a hold, and the one it reads goes to the owner rather
than being accepted inside the mandate. Every reading is in `results_rules_baseline_2026-10-19.md`.

## The live runs (2026-10-19)

Run once each on the frozen code `5926ef29`, against DeepSeek (`deepseek-flash`), redaction on, no Anthropic key (so no
fallback), in-memory books and the published demo credentials, untuned and reported as they came out:
`results_live_2026-10-19.*` (the shipped path: model reading plus the rules cross-check) and `results_live_raw_2026-10-19.*`
(the model alone, `LLM_LIVE_RAW=1`). The API logs are `api_live_2026-10-19.log.txt` and `api_live_raw_2026-10-19.log.txt`
(they hold no key). 6 model calls for the shipped run, 27 for the model alone.

| Path | Correct | Wrong | Correctly held | Held although readable |
| --- | --- | --- | --- | --- |
| Rules alone (cache, `rules-v1`) | 1 | 0 | 1 | 4 |
| Shipped (model + cross-check) | 2 | 0 | 1 | 3 |
| Model alone | 2 | 0 | 1 | 3 |

What the model added: LU02, a colloquial Chinese early-payment discount (让零点六个点 on the ¥420,000 invoice), which the rules
could not read (NO_VERDICT), was read correctly, so the owner got a priced decision (NEEDS_OWNER_APPROVAL, Tier 2). What it did
not: neither early-payment item was accepted alone, because the settlement date is not read ("autonomy not proven: a settlement
date or window is stated but not read"); LU03 to LU05 were held by the model itself, not by the checks. Nothing was booked and no
money moved in any run. Six items is a small sample: this shows one kind of gain, not a rate.

## Running it live again

You need your own DeepSeek key. Put it in the shell that starts the API, never in a file. With the key in the shell,
set `TERMSLEDGER_NO_DOTENV=1` so no `.env` feeds the run. (The `../live_frozen` README says not to set it; that applies only
when the key is read from `.env`. Prefer the shell variable.) If `ANTHROPIC_API_KEY` is also set in that shell, Claude
becomes the fallback when DeepSeek errors; leave it unset to measure DeepSeek alone (a DeepSeek failure then falls to the
rules grammar, and the log and the report show it). Use port 8583 (not 8000). Write the API log outside the repository.

### (a) The shipped path (label `live`)

PowerShell, from the repository root:

```
cd services/api
uv sync --frozen
$env:DEEPSEEK_API_KEY = "..."
$env:TERMSLEDGER_NO_DOTENV = "1"; $env:DATABASE_URL = "memory"; $env:DEMO_MODE = "1"; $env:LLM_MODE = "live"; $env:LLM_PRIMARY = "deepseek"
$env:FEATURE_ASK_ROUTER = "1"; $env:FEATURE_CONTRACT_TERMS = "1"; $env:FEATURE_CAPEX_CONTRACTS = "1"
Remove-Item Env:LLM_LIVE_RAW -ErrorAction SilentlyContinue
$api = Start-Process uv -ArgumentList "run","--no-sync","uvicorn","app.main:app","--host","127.0.0.1","--port","8583" -RedirectStandardOutput "$env:TEMP\live_api.log" -RedirectStandardError "$env:TEMP\live_api.err.log" -PassThru -WindowStyle Hidden
# wait until http://127.0.0.1:8583/health answers, then:
uv run --no-sync python evals/live_frozen/run.py http://127.0.0.1:8583 --items evals/live_unseen/items.yaml --log "$env:TEMP\live_api.log" --expect-mode live --label live
# stop the API by PID (the uvicorn process listening on 8583, then uv):
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8583 -State Listen).OwningProcess -Force; Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
```

bash, from the repository root:

```
cd services/api
uv sync --frozen
export DEEPSEEK_API_KEY=...
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 LLM_MODE=live LLM_PRIMARY=deepseek FEATURE_ASK_ROUTER=1 FEATURE_CONTRACT_TERMS=1 FEATURE_CAPEX_CONTRACTS=1 \
  uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8583 > /tmp/live_api.log 2>&1 &
API_PID=$!
# wait until curl -s http://127.0.0.1:8583/health answers, then:
uv run --no-sync python evals/live_frozen/run.py http://127.0.0.1:8583 --items evals/live_unseen/items.yaml --log /tmp/live_api.log --expect-mode live --label live
kill $API_PID
```

`--expect-mode live` refuses to run unless `/health` reports `llm_mode=live`, so a cache-mode API cannot be scored as the
model by mistake. Commit the two `results_live_<date>.*` files as they came out.

### (b) Optionally, the model alone (label `live_raw`)

The same, with `LLM_LIVE_RAW=1` added to the API's environment (PowerShell `$env:LLM_LIVE_RAW = "1"`, bash
`LLM_LIVE_RAW=1` in front of `uv run ... uvicorn`), and `--label live_raw` for the runner. In this mode the API neither
replays recorded readings nor cross-checks the model's reading against the rules grammar. Report both runs.

### What one run sends

From the runner's logic: `GET /health` once, then per item `POST /demo/reset`, `GET /audit`, `POST /offers` (the buyer's
channel key), `POST /offers/{id}/evaluate` (the owner), `GET /audit`. That is **31 requests**, of which **6 are reading
requests** (one `POST /offers` per item; caps 150 / 30). Nothing but the six texts in `items.yaml` is sent.

Model calls (from `app/compiler/service.py` and `backends.py`):

- **(a) live: 6 model calls**, one per `POST /offers` (a buyer message is one call). The API's startup and every
  `POST /demo/reset` also read the three demo documents (one contract, two lender agreements, one chunk each), but in live
  mode those replay from the fixture cache and call no model (the baseline log shows them as `backend=cache outcome=ok`).
  The cross-check against the rules grammar is local.
- **(b) live_raw: 27 model calls**: the 6 messages, plus the three demo documents read by the model at startup (3) and on
  each of the 6 resets (18), since raw mode replays nothing.
- Retries only on failure: DeepSeek makes up to 3 attempts per reading (each with one SDK transport retry), then Claude if
  its key is set, then the rules grammar.
