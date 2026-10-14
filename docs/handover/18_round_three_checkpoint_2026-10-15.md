# Handoff 18: Slice B round three, paused at a checkpoint (15 Oct 2026)

Second machine. Round three (brief `docs/design/flow-mockup-2026-10-13/05_slice_b_round_three.md`, handoff 17) is built and
verified twice, and is **not merged**. It was paused on the owner's request after the last verifier fixes landed.

## STOP: the owner's review on 15 Oct (#160)
The owner reviewed the preview and found it still buggy and not intuitive:
- the minimised queue with "Show queue" is inelegant;
- the charts ("As they asked", the headroom plot) make no sense;
- the breadcrumb is redundant;
- no Option B appears for any deal on the busy books.

All work is paused. **Do not run the gate or merge.** The next step is a full audit of the Deals flow and mock-ups of alternatives (#160 lists them), not the "To finish" list below.

## Where it stands
| | Branch | Head | State |
|---|---|---|---|
| Server | `feat/slice-b-r3-api` | `051ec9f6` | Tasks 1 to 5, the owner's Agreements groups, both verifiers' fixes, scenarios on their own route. Focused files green (round-three, deals_queue, tracker: 90). Full `tests/api` last green at `88a6016c` (1428 passed); **not re-run since**. |
| Web | `feat/slice-b-r3-web` | `c5fa9288` | Sections (a) to (f), the owner's eight preview fixes, the verifier's five fixes. Focused mock specs green (61), tsc and eslint clean, unit 163/163. **Does not yet merge server `051ec9f6`.** |

Base: `origin/dev` at `e8e270f8`; pull it again before the gate.

## To finish (about 1.5 to 2 hours)
1. Web: merge `origin/feat/slice-b-r3-api` (`051ec9f6`), re-record (the owner's scratch `rerecord2.sh` recipe: standard set
   `--no-exposure`, `--exposure`, `--overview` on and off, `--home-v2`, `--tracker`, `--slice-d`), run the Deals specs.
2. Remove the selected row's purple connector (`row-connector` in `components/deals/flow/queue-table.tsx`): the owner
   found it odd on 15 Oct; with the lighter selection and the 72 px rail it no longer reads as "this row opens there".
   Amend the specs that pin it.
3. Lead gate on the merged tree (pull dev first): full `tests/api`, typecheck/lint/unit, ONE whole mock run (both
   projects), ONE whole live run, zero retries. Known: #156 (a11y phone approvals, flaky), `demo.spec.ts:378` live (also
   fails on dev).
4. `--no-ff` merge into dev; close #152 and #154 with counts; comment on #153; note on #121 (#143) and #148.

## The owner's decisions in this round (record in DESIGN.md if not already)
- Agreements tier grouped by money owed: **Payment late / Awaiting payment / Closed**. Closed only when nothing is left
  owed (the tracker's `ended`); a revoked or expired deal still owed money says "Agreement revoked/expired" and stays open.
- Payment late stays in Agreements, not Needs you (lead's call; the owner may move it).
- An awaiting-payment row at agreement says "Agreed", not the tracker's "On plan" (lead's call, open to the owner).
- Layout choices reported as deviations, not yet confirmed by the owner: the mandate sentence on the Overview only; the
  header's [Review the counter] as the one filled button; the outcome table on both Compare and Cash impact; the
  company alert's link goes to Home (where the plan runs), not Cash.

## Verification record
- Server verifier (15 Oct, at `09c6ad2b`): 1 blocker, 3 should-fix; all fixed in `0fa009b7`.
- Browser verifier (15 Oct, at `a5e68ddb`): 1 blocker (revoked but owed shown Closed), 2 should-fix; fixed in
  `051ec9f6` (server) and `c5fa9288` (web). Every ¥ word on the Deals pages was found verbatim in a server response; no
  POST before the owner's click; the walk's groups, counts and tracker equality held.
- Performance: the cold picture read was 4 to 7 s (scenarios); scenarios moved to `GET /offers/{id}/scenarios`, cold
  picture read now 0.26 s golden.

## Workflow rules now in force (owner, 14 Oct)
Preview first (mock dev server in its own worktree; the round-three preview is `.claude/worktrees/preview-r3` on port
3341); focused tests while building and whole runs once at the gate; smallest coherent change; one heavy suite at a time
on this machine; report the real bottleneck. Measured on this round: 62 to 74% of agent time went to test runs and
waiting on them.

## Elsewhere
- `int/capex-buy-side` (`78cc1d5e`, pushed): the buy side reconciled with dev, held out of dev. Its full API run is still
  to do; the Buying card must move onto the round-three Deals layout after this merge.
- `docs/security-lead-handoff` (`94b4f79b`, pushed): the Security Lead handoff, not on dev (a push to dev was refused by
  the permission system; the owner merges it). The Security Lead has its own worktrees (`sec-*`); leave them alone.
