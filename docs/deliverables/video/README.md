# FLOW demo videos

The app on camera, recorded at 1920×1080 against the real API in live mode (cached model readings, no network, no key, synthetic
companies), with a caption bar and a step counter. Two cuts, each one continuous file; the takes inside a cut switch books behind a title
card (`POST /demo/reset`), and the story stepper is used only in its own take:

- **flow-demo-5min** (`apps/web/e2e/video/story.ts`): the competition's video, at most 4:50 (FEATURE_INVENTORY.md 16a): a setup clip on
  blank books, the money story on the golden demo books, then a second take for a contract set up in the books, Ask FLOW and the evidence.
- **flow-full-tour** (`apps/web/e2e/video/tour.ts`): every feature in twelve chapters (FEATURE_INVENTORY.md 16b).

The videos and key frames stay on the recording machine (they are gitignored); this README and each cut's `.chapters.json` are committed.
The timestamps come from the recording's own step timings (each chapter's start, measured from the start of the recording), so they move
with every re-recording; each cut's table is rewritten when that cut is recorded.

## flow-demo-5min (`--cut 5min`)

`flow-demo-5min.webm`: 4:27 long, 32.6 MB, recorded 2026-10-18.

| # | Starts at | Chapter | What it shows |
|---|-----------|---------|---------------|
| 1 | 0:00 | FLOW | Title card over the landing page: what FLOW is, and that everything outside FLOW is simulated. |
| 2 | 0:16 | Own books in six steps | Blank books: sign-in, the saved setup draft walked through its six steps, the first forecast, signing the limits; Home answers from the owner's own figures. |
| 3 | 0:43 | Am I safe? | Second take, on the golden demo books: Home says cash becomes unsafe in 12 days and recommends a ¥405,000 plan costing ¥3,113.93. |
| 4 | 0:56 | The buyer asks | Demo shell chat in the buyer's role: Foshan's message (EX01: 1.2% early settlement for 60-day terms and a 1% rebate); the buyer sees only FLOW's two counters. |
| 5 | 1:07 | FLOW decides | Deals: the request checked against the limits: ¥28,326.92 over 12 months against the ¥5,000 cap and a reserve breach; Options A and B side by side; Cash impact and Business consequences. |
| 6 | 1:33 | The counter is sent | Review and send Option A to the simulated buyer (Demo, open to a counter): agreed in round 1, the planned funding runs. |
| 7 | 1:48 | The deal, followed | The deal tracker (promised against actual) and Your agreements. |
| 8 | 2:00 | The bank, then time | Day 2: the synthetic bank event posts the agreed early payment (matched on Receivables); the clock moves to day 34. |
| 9 | 2:16 | A late payment | Day 34: Home's alarm and priced cure; Receivables: ¥160,000 two days late, Chase payment; Ask FLOW “What needs my attention?”. |
| 10 | 2:38 | The owner decides | Cash & funding: Queue it for my approval; Approvals: ¥200,000 at 32.5% a year, above the 15% the owner signed; the owner authorizes. |
| 11 | 2:55 | The loop closes | Day 38: the advance has landed (Cash & funding); Activity › Reconciliation: the receipt matched, chain valid. |
| 12 | 3:11 | A contract becomes invoices | Third take, fresh golden books: Dongguan's supply agreement read clause by clause, confirmed, then “Set up in my books” with the forecast before and after and the owner's yes (Tier 2). |
| 13 | 3:35 | Ask FLOW | Ask FLOW: “Are we safe?”, then “我们安全吗？” answered in Chinese, then a personal guarantee refused (Tier 3). |
| 14 | 4:01 | The record | Security and evidence: Download JSONL, then scripts/verify_evidence.py on the downloaded file prints VALID. |
| 15 | 4:15 | Results | Closing card with the offline judge results (scripts/judge_eval.py: functional tasks and adversarial attacks). |

Key frames (kept with the video on the recording machine, in `frames/`): 5min-agreed.png, 5min-approval.png, 5min-ask-zh.png, 5min-attention.png, 5min-contract-set-up.png, 5min-golden-home.png, 5min-verdict.png, 5min-verify.png.

Problems seen while recording: None: every chapter ran to its end.

## flow-full-tour (`--cut full`)

`flow-full-tour.webm`: 13:26 long, 99.3 MB (over 50 MB: ignored by git and kept on the recording machine), recorded 2026-10-18.

| # | Starts at | Chapter | What it shows |
|---|-----------|---------|---------------|
| 1 | 0:00 | FLOW | Title card over the landing page: what FLOW is, and that everything outside FLOW is simulated. |
| 2 | 0:12 | Setup | Landing and sign-in; the six setup steps field by field, with Fill from an agreement (credit line) and Fill from a contract (Foshan); the first forecast; signing the limits; Home on own books; the launcher modes; Which books? and loading the golden books. |
| 3 | 1:56 | Daily view | Home card by card (outlook, recommendation, forecast windows, worklist, cash today and the funding ring, upcoming movements, owed by customer); Business and Demo modes; Operator tools and an engine view; the tour; 中文. |
| 4 | 3:00 | Documents | The Foshan contract read (recorded reading), each term beside its clause, the deal at a glance, Confirm and the outcome card; the party check (the contract under Dongguan), refile and reject; a new customer; Dongguan's contract set up in the books, then undone; the credit-line agreement linked to the credit line. |
| 5 | 4:25 | Customers | Foshan's overview (contribution, outstanding, financing, share owed), the receivable-to-cash flow, exposure and the 30-day-late stress on Cash; the inputs sheet's notice (customer economics is off in pnpm demo). |
| 6 | 4:52 | Deals | Busy books: the queue's tabs, a request accepted as asked (Zhuhai, 75 days), previous and next, a request declined (Dongguan); then the golden books: Foshan's WeChat in the inbox, the verdict and counters, Business consequences, the message to the buyer copied and marked sent, the buyer's acceptance recorded, the agreement, its tracker and its decision record. |
| 7 | 6:41 | Money | Fresh golden books: Cash & funding, every plan FLOW weighed, the plan run inside the limits (Tier 1) and the funding ring; Limits in plain words; the Approvals page. |
| 8 | 7:19 | Lifecycle | Fresh golden books: the counter agreed with the simulated buyer; day 2: the synthetic bank receipt matched; day 34: the late-payment alert, Chase payment, the cure above the owner's ceiling approved; day 38: landed and reconciled; day 77: the signed limits about to expire (Alerts). |
| 9 | 8:30 | Ask FLOW | Suggested prompts; questions in English and Chinese; a plan and “go ahead”; a fact chat will not record; the nearest thing FLOW can do; a pasted approval ignored; Tier 3 refused; New conversation; the buyer role and the FastCapital message. |
| 10 | 9:46 | Sandbox | The sandbox from Foshan's request: its verdict, then the Option A preset (45 days, 0.85% on ¥260,000) and back; the 30-day-late stress on Cash; a note on the strategy features a pnpm demo build leaves off. |
| 11 | 10:19 | Capex & purchases | The quick check on a ¥600k machine (structures screened, the lease selected), Apply queued for approval, the borrower file; the vendor contract read, its payment schedule, Commit and its approval; financial health and loan eligibility; long-term plans. |
| 12 | 11:28 | Records and judging | The Demo story end to end in one take (the owner's approval clicked); Activity with its filters and evidence; Security and evidence: the FastCapital scene, Download JSONL and the offline check; the judge report. |
| 13 | 12:48 | Security | Demo credentials off by default (card); a buyer over its daily budget is told to write tomorrow; Tier 3 refused; the buyer sees only its reply. |

Key frames (kept with the video on the recording machine, in `frames/`): full-tour-buyer-accepted.png, full-tour-buyer-budget.png, full-tour-capex.png, full-tour-day-77.png, full-tour-deal-choices.png, full-tour-doc-terms.png, full-tour-funding.png, full-tour-golden-home.png, full-tour-limits.png, full-tour-own-home.png, full-tour-purchase.png, full-tour-whatif.png.

Problems seen while recording: None: every chapter ran to its end.

## Notes from the recordings

- **Deals, "Your agreements" leaves out a confirmed contract that was never negotiated (product bug; fix in progress on
  fix/deals-contracts-upload).** `isAgreed` needs the "Terms negotiated" stage done and `hasInvoicesOnly` needs no contract
  (`apps/web/components/deals/deal-summary.tsx`), so confirming a customer's contract on own books removes the customer from Deals.
- **A question typed in Chinese while the app is in English is answered in English** (fix pending): the web sends the page's language with
  every chat message and it overrides the API's detection, so the Ask FLOW scenes switch the app to 中文 first (`ZH_NEEDS_SWITCH` in
  story.ts and tour.ts: set it to false once the fix lands).
- **The worklist outlives a reset (product bug).** `Runtime.clear_session_caches` (`services/api/app/api/runtime.py`) does not clear the
  worklist cache (`services/api/app/api/worklist.py`), whose key (books, document ids, change counts) repeats when the same steps are taken
  again after `POST /demo/reset`; Deals then lists a deal of the earlier session and opening it says "Which negotiation?". The recorder
  starts a fresh API for every run, so recordings are not affected; a second walk on one running demo is.
- **Fill from an agreement** (setup step 2) names the row after the file, not the lender; the full tour retypes the lender's name.
- **Recording the buyer's acceptance in Business mode** books the agreement but not the planned funding (the Demo shell's simulated send runs
  it), so the full tour's lifecycle chapter meets a larger day-34 gap than the 5-minute cut.
- **The buyer's 60-day request** in the 5-minute cut is sent in the Demo shell's chat in the buyer's role (no channel key); the full tour reads
  it from the Deals inbox.

## Re-record

From the repository root, with the web app's packages installed (`cd apps/web; pnpm install`), `uv` on the PATH, Python 3 on the PATH (for
`scripts/verify_evidence.py`) and Playwright's Chromium installed (`pnpm exec playwright install chromium` in apps/web):

```
pnpm demo:video              # flow-demo-5min
pnpm demo:video --cut full   # flow-full-tour (about 20 minutes to record)
```

Each run starts `node scripts/demo.mjs --blank --keep --data .demo-data/video.db --fresh --api-port 8090 --web-port 3090` (ports 8090
and 3090 must be free; `--books golden` starts on the demo books instead). The recorder keeps its books in its own file, so the owner's
kept demo books (`.demo-data/flow-demo.db`) are never touched. It warms every page, records the cut's test in
`apps/web/e2e/video/walkthrough.spec.ts` headless (Playwright project `video`, `E2E_TARGET=video`), writes this folder, and stops only
the processes it started. `VIDEO_SLOWMO_MS` (default 180) sets the pause after every browser action; a cut's `pace` stretches its
reading pauses. `VIDEO_SCENES=id,id` records only those scenes (a dry run of one chapter against a running demo). The mock and live suites
never run the video spec.
