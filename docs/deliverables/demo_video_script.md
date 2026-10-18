# FLOW: Demo Video Script

Team ISMOGGER · FinTechathon 2026 · International AI Track, Topic E: SME Finance Copilot. FLOW is the product name; the code still uses the working name TermsLedger.

**Deliverable:** the demo video, required for the International AI Track. The official limit is **5:00**, in 16:9 landscape at 1080p, with English narration and **English subtitles**. This script is deliberately shorter: it runs **1:55** of screen time, because the app now tells its story in six scenes and one picture per page, and a short video lets each sentence land (the 1:55 is our own choice; the 5:00 limit is the one the earlier version of this script recorded from the official guide).

**File name**, following the guide's pattern "Track-TeamName-DemoVideo": `International-AI-Track-ISMOGGER-DemoVideo.mp4` (the track string follows the guide's pattern; the organisers name no other).

**Structure** (the official guide's order):

1. Project and team introduction (scene 0).
2. End-to-end demonstration of the core scenario (scenes 1 to 6: the late-payment loop of `docs/DEMO_FLOW.md`).
3. Safety mechanisms, innovation and results (the closing card).

**What this script shows, and where it comes from.** The walk is the guided Demo as `docs/DEMO_FLOW.md` and `apps/web/e2e/demo.spec.ts` describe it: six scenes, eleven steps, on the pages as they are on `dev` (the screenshots under `docs/screenshots/ui-overhaul-2026-10-12/`). Every page answers one question in its heading, shows one picture, and offers one action. It shows nothing that is not on `dev`. The three strategy answers stay off the screen: they are behind flags that default to off (`FEATURE_ENVELOPE`, `FEATURE_PRICE_CURVE`, `FEATURE_COLLECTIONS_WORTH`).

## Recording set-up

- **Screen.** 1920×1080, browser full screen at the Business mode (the pill in the header reads Business), zoom 110 to 125% so the figures stay legible after compression. Hide bookmarks and extensions. Do not record the engine's own screens (the Demo mode's Mandate, Trajectory and Verdict pages); they are not part of this cut.
- **App mode.** Record in **live mode** against a local API in cache mode (`README.md`, quickstart, step 2):

  ```
  cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache uv run uvicorn app.main:app --port 8000
  cd apps/web && NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_DEMO=1 pnpm dev
  ```

  `NEXT_PUBLIC_DEMO=1` prefills the Owner sign-in with the published demo token (README, quickstart); use it for the recording only. If anything fails on the day, mock mode (`pnpm dev` alone) shows the same golden figures offline.
- **Navigation.** Use the Demo stepper: **Start demo**, then **Next** (README; `docs/DEMO_FLOW.md`). Every step is convergent, so a stumbled take is safe to Replay; **Reset** (or Replay of the first step) erases the books and starts over. The stepper never presses Approve: scene 5's approval is the owner's own click on the card, so click it on camera.
- **The bank event.** Scene 4's one receipt is posted by the Demo itself (`POST /demo/bank-receipt`, labelled synthetic with the reference `DEMO-RCPT-1`); no terminal command is needed.
- **Subtitles.** Burn in the narration below as English subtitles, at most 2 lines and about 42 characters per line, bottom-centred, white on a 60% black box. Keep every figure exactly as written.
- **Content check.** No logos, brand marks or screenshots of other products, and no copyrighted music [TEAM: royalty-free music or none]. Every figure on screen is synthetic; the header says "Demo data" and the sidebar says "A simulated company: the lenders, the buyer and the bank feed are simulated. No real funds move." Say so once (scene 0).
- **Voice.** Business voice only: say what the owner sees and decides. No reason codes, no ids, no day numbers, no formulas in the narration. The page's own sentences carry the figures.

## Timeline (1:55)

| # | Time | Page | The owner sees first (the heading sentence) | The one action | Narration (also the subtitles) |
| --- | --- | --- | --- | --- | --- |
| 0 | 0:00–0:10 | Title card | "FLOW: the supplier's agent for both of its debt books"; team ISMOGGER [TEAM: names and universities]; "FinTechathon 2026 · International AI Track · Topic E: SME Finance Copilot" | None | "We are ISMOGGER. FLOW is an agent a small supplier owns, working inside limits its owner signed. Everything you will see is simulated: the buyer, the lenders and the bank." |
| 1 | 0:10–0:22 | Deals (scene 1, "Buyer asks"): the inbox and the buyer's message | The buyer's message from Foshan Home Retail Co.: settle the ¥420k early at 1.2%, extend to 60 days, and give 1% off next quarter, with the terms FLOW found in it beside it (`docs/DEMO_FLOW.md`, step 1) | Click **Start demo**, sign in as the owner when asked, then **Next** | "A big buyer asks for three things at once: an early-payment discount, longer terms for good, and a rebate. The agent reads the message and shows each ask in plain terms." |
| 2 | 0:22–0:40 | Deals (scene 2, "FLOW decides"): FLOW's read, the asks with their costs, the chart | "Don't accept as asked: it would cost ¥28,326.92 over the next 13 invoices, plus the ¥5,040 immediate discount, above your ¥5,000.00 limit." (`deals-evaluated-1280-en.png`; read the heading from the live page at recording) Under it: three paths on one chart, As they asked, Option A (FLOW recommends, ¥3,035.99) and Option B | **Next**: FLOW checks the offer against the owner's limits; point at the heading, the chart and the three columns | "FLOW does not just say no. Accepting as asked would cost the supplier far more than the owner's limit, so it prices two counters. The one it recommends costs about three thousand yuan, and the chart shows what each path does to cash." |
| 3 | 0:40–0:54 | Deals (scene 3, "The agreement acts"), then Your agreements | "Agreed", with "The buyer accepted Option A. The agreement is on your books." Below, Your agreements: the signed contract the owner confirmed, set beside the books (`deals-agreed-1280-en.png`) | **Next**: the recommended counter is sent, bound to the verdict and the books the owner saw, and the simulated buyer accepts (the next step opens Cash; press Next through it) | "The reply goes out exactly as priced. If anything had moved in between, it would be refused. The buyer accepts. The signed contract, read by the agent and confirmed by the owner, sits beside the live books; confirming it changed nothing in them." |
| 4 | 0:54–1:08 | Home, then Receivables (scene 4, "Reality diverges") | Home: "Your cash reserve becomes unsafe in 8 days." with the plan bar "Secure ¥200k of funding", ¥1,782.19, "Needs your approval" (`home-pending-day34-1280-en.png`). Receivables: "¥160,000.00 from Foshan Home Retail Co. is 2 days late." (`receivables-day34-1280-en.png`) | **Next** twice: the agreed early payment arrives as one synthetic bank event, then time passes and the second payment does not arrive (the Demo lands on Home); then open Receivables from the sidebar | "The early payment arrives, but the rest does not. A month on, cash will fall two hundred thousand below the owner's minimum, and the buyer's invoice is late. The agent speaks first, with a cure and its price. It costs more than the owner allowed it to borrow alone, so it waits for the owner." |
| 5 | 1:08–1:30 | Approvals (scene 5, "The owner stays in control") | "Approve ¥200,000.00 of invoice financing?" with what you get, what it costs (¥1,782.19, 32.5% a year), when it lands, and "Why it needs you: The yearly cost of 32.5% is above the 15.00% limit you signed for funding without your approval." Then the cash line if you decline against if you approve (`approvals-pending-1280-en.png`) | **Next** queues the cure and opens the card; then click **Approve** yourself, on camera: nothing approves in the owner's place | "Here is the owner's decision. Decline, and cash goes under the minimum. Approve, and it stays at it. The cost is high because the lender bills in whole periods, and that is exactly why it needs a person. The agent cannot press this button, and nothing runs until the owner does." |
| 6 | 1:30–1:42 | Home (outcome), then Activity (the proof) | Home: the heading sentence the page gives on the books as they now stand (not quoted: no capture of that state is in the repository). Activity: the heading is the page's "now" sentence, with "Record chain checks passed" beneath it (`activity-day34-1280-en.png` shows the page) | **Next** three times: time moves to where the cash has landed (Cash), Home shows where the books stand, then Activity | "Time moves on, the cash lands, and the risk is gone. Every step, refusals included, is in one record, each entry sealed to the one before it, and the whole record can be checked on its own." |
| 7 | 1:42–1:55 | Closing card | Four lines (below), then the team name (ISMOGGER) and repository (https://github.com/peachoolongtee/smu2sz) | None | "We attacked it 279 ways and none moved money. All 28 findings of an independent flow audit are fixed. Contract reading is shown to the owner, never booked, and we claim no accuracy for it yet. Buyers have an agent, and banks have a model. FLOW is the supplier's own." |

**The closing card's four lines** (each with its source on the slide's footer or in the deck notes):

- "279 attacks (128 through the API, 151 through chat): 0 with harm, ¥0 moved" (`python -m app.security.attacks`, re-run on 18 Oct 2026 at `b0cc7a4b`; execution evidence, section 01).
- "49 of 49 scripted tasks; every evidence chain verifies" (`scripts/run_scenarios.py --inproc`; `scripts/verify_evidence.py` over the 49 files: 49 VALID).
- "28 of 28 audit findings fixed, with the decision record that keeps each decision's state" (`docs/UX_REMEDIATION_REPORT.md`, sections 1 and 5).
- "Nothing executes outside the owner's signed limits; contract reading and the strategy answers change no books; no reading-accuracy claim until held-out contracts exist" (ADR-0012; `docs/STRATEGY_MVP_REPORT.md` section 1).

## Numbers used, and their sources

Every figure in the narration or on the screens comes from the page itself (the screenshots named above), `fixtures/golden/golden_values.json` or a report; all are synthetic.

| Figure | Source |
| --- | --- |
| ¥28,326.92 over the next 13 invoices, plus the ¥5,040 immediate discount, against a ¥5,000.00 limit | Deals heading (`deals-evaluated-1280-en.png`); `docs/DEMO_FLOW.md` scene 1 step 4 (`forward_ledger_total`, `concession_cap`) |
| Option A ¥3,035.99 | Deals paths columns (`deals-paths-option-a-1280-en.png`); `docs/DEMO_FLOW.md` scene 1 step 6 (`counter_a_total`) |
| ¥257,790.00 arrives early (on ¥260,000.00 at 0.85%); ¥160,000.00 is late | `docs/DEMO_FLOW.md`, scene 4 steps 2 and 3; `docs/deliverables/evidence/demo_run_output.txt` (18 Oct, `b0cc7a4b`); Activity and Receivables captures |
| Cash falls ¥200k below the ¥300k minimum | Home capture (`home-pending-day34-1280-en.png`) |
| ¥200,000.00 financing, ¥1,782.19, 32.5% a year, 15.00% limit | Approvals capture (`approvals-pending-1280-en.png`); `docs/DEMO_FLOW.md` scene 4 step 4 |
| 279 attacks, 0 with harm | `python -m app.security.attacks` on 18 Oct 2026 at `b0cc7a4b` (128 API, 151 chat); `docs/deliverables/execution_evidence.md` section 01 |
| 49 of 49 tasks, 49 chains VALID | README, quickstart step 1 and step 4; `services/api/evals/e2e/latest/summary.md` |
| 28 of 28 findings fixed | `docs/UX_REMEDIATION_REPORT.md` section 1 |
| The Demo is six scenes and eleven steps | `docs/DEMO_FLOW.md`; `apps/web/lib/demo.ts` |

## Claims to keep, and claims to avoid (spec v2 §13)

- **Say** "the cheapest option among your facilities, under your limits", not "the best loan"; "decision support; the owner decides and signs", not "financial advice"; "record", "verdict" and "reason", never "proof".
- **Say** "simulation" for the buyer, the lenders, the bank event and the clock; "screens the entered obligations only"; "internally checkable" for the record. **Never say** "cannot be fooled", "safe by construction", "solves prompt injection", "understands every message" or "bank-grade". Make no claim of bank-covenant compliance.
- **Say** "the agent read it, the owner confirmed it", never "the AI signs" or "legally verified". The demo contract was written to match the synthetic books. Quote no reading-accuracy figure: the held-out contract set is pending.
- **Say** "the agent proposed it and the owner approved it" for the cure; do not say the agent decided alone, and do not hide that its cost is above the limit the owner signed (the code never approves for the owner).
- **Do not** show or describe a real bank integration, and do not show the strategy answers or the engine's own pages in this cut.
- **Do not** claim the Chinese pages are reviewed: the Chinese sentences are templates that await a native reader (`docs/UX_REMEDIATION_REPORT.md`; `docs/SYSTEM_WALKTHROUGH.md` section 12). This cut is English only.

## Final check before upload

- [ ] Running time 1:55 (the official limit is 5:00), 1920×1080, 16:9.
- [ ] English subtitles burned in and legible; every figure matches this script and its page.
- [ ] No logos, product screenshots or copyrighted music; the synthetic-data notice is said once.
- [ ] Team names and universities filled [TEAM].
- [ ] File named `International-AI-Track-ISMOGGER-DemoVideo.mp4`.
- [ ] Video link added to `docs/deliverables/execution_evidence.md` ("Video link: to be added at upload") and the Execution Evidence docx rebuilt.
- [ ] A backup recording made in mock mode, in case the live demo fails at the finals.
- [ ] The Home heading of scene 6 read from the live page at recording time and checked against the narration.
