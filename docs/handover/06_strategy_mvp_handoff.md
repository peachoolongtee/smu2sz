# Handoff: the strategy MVP and the pilot (8 October 2026)

For the next session's lead. Read this, then wayfinder map [#47](https://github.com/peachoolongtee/smu2sz/issues/47) on
GitHub, then `docs/STRATEGY_MVP_REPORT.md` and `docs/STRATEGY_MVP_BRIEF.md` (section 12 last). The earlier handoff,
`docs/handover/05_strategy_and_ux_handoff.md`, still holds the delegation model, the integration loop and the standing
rules; nothing here repeats them.

## 1. Where things are

- **Branch `feat/strategy-mvp`** (from `dev` at `bcc67d4`) holds the read-only MVP: the Safe Deal Envelope, the cash price
  curve and collections worth, behind `FEATURE_ENVELOPE`, `FEATURE_PRICE_CURVE`, `FEATURE_COLLECTIONS_WORTH` (API, default
  off) and `NEXT_PUBLIC_STRATEGY_MVP=1` (web). With the flags off it is byte-for-byte `dev`'s behaviour. It has NOT been
  merged into `dev`: that is the owner's decision in grilling [#56](https://github.com/peachoolongtee/smu2sz/issues/56).
- **Wave 8** ([#57](https://github.com/peachoolongtee/smu2sz/issues/57)), the Impeccable finish over the whole UI, is
  done and merged into `feat/strategy-mvp` (report section 11; `apps/web/DESIGN.md` is the canonical record, `PRODUCT.md`
  the inferred product context with its open questions). If #56 defers the `dev` merge, the finish is cherry-picked onto a
  branch from `dev` without the strategy cards (the finish touched every page, so expect a careful cherry-pick).
- **Running the MVP locally**: API from `services/api` with the three flags, `TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory
  LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8000`; web with `NEXT_PUBLIC_STRATEGY_MVP=1`
  (`NEXT_PUBLIC_API_MODE=live` against the API, or mock mode with the recordings under `apps/web/mocks/strategy/`,
  re-recorded with `node apps/web/scripts/record-mocks.mjs --api http://localhost:<port> --strategy`). E2E with the cards:
  `E2E_STRATEGY=1` (mock and live; the Playwright config passes the flags through). The backtest:
  `uv run --project services/api python services/api/scripts/strategy_backtest.py [--quick] [--json]`, then
  `git checkout -- services/api/evals`.

## 2. What the owner must decide (#56)

1. Merge `feat/strategy-mvp` into `dev` now with the flags off, or keep it on its branch until the pilot ends.
   Recommendation: merge, flags off; the demo path is unchanged by construction and a long-lived branch rots.
2. The shadow pilot: which one or two SMEs, which month; if none, who runs the five interview sets (synthesis section I).
3. `Capacity`: confirm its deferral (the envelope names the wall from the verifier's codes), or ask for the read-only view.
4. The comprehension test of the cash sentence on three owners: who and when. The sentence now leads with yuan ("Cash in
   the next 30 days saves you ¥89.11 of funding cost per ¥10,000 (0.89%); after that, earlier cash saves nothing.") because
   the first cold reader took "worth 0.89% to you" for a rate charged.
5. Controlled action stays off through the 30-day and 90-day windows unless the owner names one action earlier.

## 3. The pilot's instrument

Weekly, enter the pilot SME's books as the demo's are (facilities, invoices, recurring invoices, mandate), run the three
routes, and record against FLOW's answers: the owner's chosen response to each real offer against the envelope's packages
and zone; the order they chased against the worth ranking; receipt dates against due dates (the learning ledger's first
entries). The gates and kill criteria are the synthesis's section I: the envelope is killed if the owner's response was
outside the zone or ignored the packages on more than half of the first ten offers, or fewer than half the buyers have a
recurring invoice; collections if the net order equals the overdue-amount order every week or no pilot has more than two
open receivables; the curve if any owner reads the sentence as a charged rate after one reword. The portfolio's VALIDATE
FIRST gate is read from the pilot's inbox (two or more deals open at once in most weeks).

## 4. What a build session should know

- The contract is the brief; where section 12 and an earlier section differ, section 12 wins. Every displayed figure is
  pinned to the spikes' oracle under `fixtures/strategy/` or, where the engine corrected the research (the APR-capped
  collections ceiling, the day-34 envelope, the curve's definition), to the engine with the reason recorded in the test and
  in `docs/research/strategy/06-backtest-2026-10-08.md`'s expected differences.
- The figures a page shows for one invoice are the same on every page because they share `option_a_face`: change that
  helper and every page moves together.
- The routes read the books under `rt.lock` and compute outside it through one single-flight cache (`app/strategy/cache.py`);
  a cold envelope read is 6–11 s, so a warm-up at deal read is the first performance item if the pilot's owners notice.
- Known limitations and UX debt are in the report's sections 8 and 9; the zh sentences await a native reader.

## 5. Kickoff text for the next session

> Read `docs/handover/06_strategy_mvp_handoff.md` on `feat/strategy-mvp`, then wayfinder map #47 on GitHub. You are the
> lead: you architect, write specs and acceptance criteria, review and merge; implementation goes to lower-tier implementer
> subagents, research to research agents, figures are checked by a verifier agent. Every build wave of the map is done;
> the frontier is the owner's grilling (#56). Record my answers there, append them to the map's "Decisions so far", then
> act on them: merge `feat/strategy-mvp` into `dev` with the flags off if I say so (full gate first), and chart the
> 90-day shadow pilot as a new map from section 3 of this handoff.
