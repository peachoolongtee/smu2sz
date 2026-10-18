# Security Lead handoff, 19 Oct 2026: certification of dev `03215a20`

Written by the Security Lead (an AI agent) to continue in a new session. Read this file first, then `CERTIFICATIONS.md`
(the `5941e95a` entry), `FINDINGS_REGISTER.md` and `RELEASE_GATE.md`.

## The request (from the integration lead, through the owner)

Certify dev `03215a20` (round seven merged as `c707ee8c`; the code equals `bee9c50d`; the later commits change documents
only). Update `RELEASE_GATE.md` and `FINDINGS_REGISTER.md`, which still name `5941e95a`. Two items: DEMO-L1 (the demo's
web dev server listens on all interfaces), and the route-policy test's one unreached route is a 404, not a feature flag.

## Where things are

| What | Where |
| --- | --- |
| Docs branch (this file) | `docs/certify-03215a20` in worktree `.claude/worktrees/sec-fix3`, from `origin/dev` `03215a20`; **not pushed** |
| DEMO-L1 fix | `sec/demo-loopback` `65ab100c` in worktree `.claude/worktrees/sec-r6`: `next dev -H 127.0.0.1` in `scripts/demo.mjs`, loopback default in `apps/web/scripts/dev-mode.mjs`; **not pushed; the netstat check is not done yet** |
| Certification checkout | worktree `.claude/worktrees/cert-719c`, detached at `03215a20`. Do not edit it |
| Run outputs | the previous session's scratchpad `cert0321/` (`%TEMP%\claude\C--Users-ian-Documents-Projects-smu2sz\aa96fbfb-4038-45c2-8bb9-e28d412a5861\scratchpad\cert0321`); copied to `evidence/2026-10-19/dev-03215a20/run/` when the run ended, if the session was still open |
| Run scripts | `evidence/2026-10-19/dev-03215a20/tools/` (`certify_0321.sh`, `web_gate.sh`, `authz_sweep_v3.py`, the reproductions, `csp_check.mjs`) |
| SEC-28 review scripts | `evidence/2026-10-19/dev-03215a20/review_sec28/repro*.py` |
| PostgreSQL URL | `pg_url.txt` in that scratchpad. Never print or commit it. If the scratchpad is gone, ask the owner for the local PostgreSQL 17 URL |

## Results so far (certification run on `03215a20`)

| Check | Result |
| --- | --- |
| Full suite (155 processes) | **11,368 passed, 0 failed, 47 skipped**; the one non-zero shard is `tests/__pycache__` (no tests, exit 5), as on `70f23ac5` |
| Attack catalogue | detection 0.9766, events 0.7422, 120/128 defended, 0 NOT_REACHED, 0 control not seen, 8 known gaps (as on `bee9c50d`) |
| Sweep, three modes | 112 routes swept, **0 policy violations** in each mode. The diff against `70f23ac5` exits 1 only because the three pause routes are new; every non-owner gets 401 `OWNER_TOKEN_REQUIRED` on them, and nothing else differs |
| Reproductions, approval flip, language boundary, PostgreSQL ×3 and guards, audits, mock web gate | running when this was written: read `run/steps.txt` (or the scratchpad's). It ends with `ALL DONE` |

If the run did not finish, re-run it: `bash tools/certify_0321.sh`. It expects the paths at its top (the scratchpad `S`,
the `cert-719c` checkout `W`), so edit `S` if the scratchpad is gone. It takes about 35 minutes; the web gate uses port 3419.

## Still to do, in order

1. **Read the run's `steps.txt`.** Expected: sweep policy 0 violations (the diff baseline is `2026-10-18/dev-70f23ac5`; only the
   three pause routes are new); r3, repro1, repro3 and approval_flip refuse (their non-zero exits are the refusals, as before:
   read the outputs); language boundary 0 WRONG_MATERIAL in both backends; PostgreSQL 3 of 3 and guards 10 passed; pip-audit
   clean, `pnpm audit --prod` 0; web gate 479 passed, 77 skipped. Check the `tests_security` shard for the route-policy
   result (16 tests; the owner's misses: 1 in demo mode, `POST /documents/{id}/terms/undo` answering 404 `UNKNOWN_SET_UP`).
2. **CSP check on a production build:** API on :8420 and `next start` on :3420 from `cert-719c`, `csp_check.mjs` copied into
   `apps/web` as `.csp_check.mjs` and removed afterwards; stop both by PID. Expect 16 pages, 0 violations.
3. **Secret scan (E10):** tracked files and every branch's history; only the two `.env.example` files tracked. Never open `.env`.
4. **Decide the SEC-28 question (below)**, then write the verdict.
5. **Evidence folder:** summary, `security_manifest.py --checkout ../cert-719c` → `MANIFEST.json` and `SHA256SUMS`;
   grep the folder for the PostgreSQL password before committing.
6. **`CERTIFICATIONS.md`:** a `03215a20` entry in the usual form (changes since `5941e95a`, evidence id, the check table, code
   review, verdict). Also change "enforced in the executor" in the `5941e95a` entry to "enforced in front of the executor"
   (the pause wraps `Executor.execute`; the self-assessment's wording is the accurate one).
7. **`RELEASE_GATE.md`:** replace the "Submission build (integration lead's note)" paragraph; add verdict rows for `5941e95a`
   (NOT CERTIFIED, PAY-1) and `03215a20`; stop calling `70f23ac5` "the final assessed build"; S's definition says web and API on
   loopback, which `pnpm demo` does not do: add DEMO-L1 as an S condition (a trusted machine and network, or a firewall rule)
   until `sec/demo-loopback` is merged, and record that the condition also applied to `70f23ac5`.
8. **`FINDINGS_REGISTER.md`:** the header date and build; replace the "Submission build" notes on SEC-28, REG-8, REG-9 and CT-2b
   and the paragraph after the table; mark PAY-1 to PAY-3, PAUSE-1 and APR-1 merged (`c707ee8c`) and certified; add DEMO-L1;
   add the SEC-28 follow-ups below; CT-2b closes for the borrower file only.
9. **Self-assessment** (`docs/SECURITY_SELF_ASSESSMENT.md`): see the corrections list below. Then rebuild with
   `scripts/build_deliverables.py --word`, restore the technical document's and execution evidence's outputs from `origin/dev`,
   commit, push the docs branch, send the docx and PDF to the owner, and write the hand-in for the integration lead.
10. **DEMO-L1 branch:** run `node scripts/demo.mjs --mock --web-port 3417` in `sec-r6`, check with `netstat -ano` that :3417
    listens on 127.0.0.1 only and the page loads at `http://localhost:3417`, stop it by PID, update the commit's `Tests:` line,
    run the mock browser suite, push, and offer it to the integration lead (a launcher-only change; a delta check suffices).
11. **README.md:282-293** (on the docs branch): it cites self-assessment v2.0 at `719c9dcf` and gives a network demo "conditional
    GO"; the gate says NO-GO until a tested deployment profile exists. Correct it.

## The open question: SEC-28's reporting is not fully fixed

The self-assessment (Table 27, SA:1145) and the integration lead close "SEC-28 (reporting)" on `f52870d1`. A reviewer agent
checked it on `03215a20` (scripts in `review_sec28/`). It found the queued and refused legs reported correctly on `/negotiate`
(deal and no-deal, en and zh), on `/alerts/{id}/act` and on the chat paths, and the commit reporting-only (no engine module).
But it found:

| Proposed id | Finding | Severity (proposed) |
| --- | --- | --- |
| FUND-1 | `/negotiate` with no admissible funding plan (`actions=[]`) reports FUNDED: `funding_status([])` is true for an empty list (`app/api/funding_report.py:44`), and `runnable()` skips the not-funded branch (`app/api/refusal.py:45-46`), so the reply says "the near-term gap is funded another way" (deal branch: "the remaining gap is funded") when ¥405,000 or ¥147,210 is unfunded (`repro4.py`, `repro6.py`; facility limits cut in the store to make the menu inadmissible) | Medium |
| FUND-2 | The web's send result (`apps/web/components/deals/flow/decision-pane.tsx:98`) writes "The agreement is on your books." whenever `outcome == DEAL`, also when the accept waits for approval or was refused; the web reads none of `accept_status`, `funding_status` or `funding_legs` | Medium |
| FUND-3 | Chat "go ahead" on a no-deal send with no admissible plan replies "NO DEAL, and there is no gap to cover." (`app/nl/offers.py:602`; `committed_plan` returns None, `app/nl/pipeline.py:229-237`) while its own verdict line shows a reserve breach (`repro7.py`) | Low / Medium |
| FUND-4 | Smaller wording: "funded" when no funding was needed; a refused accept in chat says only "The buyer accepted"; the decision record's `waiting_for` says nothing waits when two legs wait (`app/decisions/state.py:792-823`); "Could not run; nothing changed" after legs ran; the fix-alert line understates a mixed run (`fix-alert.tsx:232`) | Low |

To decide before the verdict: check whether FUND-1 to FUND-3 also exist on `70f23ac5` (likely: they are older code than
`f52870d1`). If they do, they are part of SEC-28, which `70f23ac5` was certified with as disclosed, and they need not block
`03215a20`. Then the honest record is: SEC-28 reporting **partly** fixed (queued and refused legs), FUND-1 to FUND-4 open, and
the self-assessment must stop saying the reporting is closed. If any is new since `70f23ac5`, treat it as PAY-1 was treated.
Also check whether an owner can reach "no admissible plan" through the API or UI (the repro wrote facility limits into the
store). Fixes (product code, not the engine): an empty or inadmissible plan with need > 0 is NOT_FUNDED; the chat no-deal
branch worded the same; the web send result worded from `accept_status`.

## Self-assessment corrections (docs review of c73d720e → 03215a20, verified where noted)

- SA:726 and SA:1249 and SA:57/1409 assume the certification: reword to the actual verdict once recorded.
- SA:1233-1236 (Table 27): REG-8 and REG-9 closed on the submission build once certified; **CT-2b** row → "CT-2b (borrower
  file)", keep the rest disclosed in 4.4; **SEC-28 (reporting)** → partly, with FUND-1 to FUND-4 (above). Same at SA:1145.
- SA:1093: "two changed facts lower the impact of R-14 and SEC-28" is a rating judgement. The Security Lead's decision to record:
  ratings unchanged on `03215a20` (the pause does not revoke a mandate; plans are still not reversed, and the reporting is
  only partly fixed).
- SA:1249 adds DEMO-L1 as a condition to the `70f23ac5` GO row: correct in substance; approve it and say so in the gate.
- SA:116-124 (Table 3): E2, E3, E6, E8, E10 on the submission build are the integration lead's runs with no committed output;
  replace them with this certification's results, or attribute them. "Round seven changes no reading path" (E6) is wrong
  (round seven changed `app/nl/rules.py`, `service.py`, `ask.py`, `answers.py`): use this run's language-boundary result.
- SA:1353: the live browser suite (171 passed, 6 failed on the merge, per the technical document) was dropped: add it back.
- SA:874 and the technical document line 326: "every model call logged a `model.redaction` line" is false: the router redacts
  (`app/nl/router/route.py:434`) but never calls `log_counts` (verified). SA:864 "redaction on by default" is the code
  default, not recorded in the frozen-run files.
- SA:467: "every operation requested by the agent or a buyer is refused" while paused: `Executor.propose_commitment` is not
  covered (verified; a PROPOSED agreement moves no money and its acceptance is refused). Say so.
- Risk acceptance now reads "the team" in the self-assessment and "the owner" in the Security Lead's records: leave the
  records as they are (the owner made those decisions) and tell the integration lead.
- Table E1 and its editorial list omit: the coverage definition change (SA:193, 1466), "second reader in live mode only",
  the new legal claims in Table 24, the document-control fields removed, and the docs commits `c73d720e`, `02629eab`,
  `49f017cf`. For the integration lead to add. fig4.html still says "the assessed build".
- Already correct at `03215a20`: the 1.5 route sentence names the 404 on `/terms/undo` (SA:281-283). The route counts (113
  routes, 97 owner or demo routes) match the app.

## Standing rules (unchanged)

Own worktrees only; never merge into dev (the integration lead does); never read `.env`; no real funds, databases or the
real Supabase project; no bare `git stash`; stop processes by PID; ports 3417-3421 and 8420 only; escalate Critical findings
at once; never claim absolute security; commits in `type(area) subject` form with why, bullets, `Tests:`, `Refs:`, and
**no Co-Authored-By line**; engine changes need the owner's approval.
