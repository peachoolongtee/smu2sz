# FLOW demo videos

The app walked from empty books, recorded at 1920×1080 against the real API in live mode (cached LLM readings, no network, no key,
synthetic companies). Two cuts of the same scenes (`apps/web/e2e/video/scenes.ts`, one per feature or step):

- **flow-demo-5min**: the competition's video, at most 4:50: the strongest end-to-end story on the owner's own books.
- **flow-full-tour**: every scene at the full reading pace.

The timestamps come from the recording's own step timings (each chapter's start, measured from the start of the recording), so they move
with every re-recording; each cut's table is rewritten when that cut is recorded.

## flow-demo-5min (`--cut 5min`)

`flow-demo-5min.webm`: 4:02 long, 29.9 MB, recorded 2026-10-17.

| # | Starts at | Chapter | What it shows |
|---|-----------|---------|---------------|
| 1 | 0:04 | Sign in | the landing page, then the owner sign-in with the demo build's pre-filled token. Empty books: Home cannot answer yet. |
| 2 | 0:15 | Set up your books | the six-step setup wizard on blank books. Lingnan Homeware Manufacturing Co., Ltd.: cash ¥400,000; a ¥150,000 credit line at 6.4% (Pearl River Commercial Bank) and ¥350,000 of invoice financing; Foshan Home Retail Co. with an open ¥420,000 invoice on 45-day terms and a contract invoicing ¥420,000 every 30 days; Dongguan Office Supplies Ltd. with an open ¥180,000 invoice; payroll ¥340,000 every month and a ¥120,000 supplier payment; a ¥300,000 minimum and the default limits. The review's first forecast, then the owner signs and opens the books. |
| 3 | 1:07 | Home: the forecast and the gap | the cash forecast, the gap before payroll and FLOW's funding plan (not approved yet). |
| 4 | 1:19 | Attach a deal | Foshan's supply agreement (PDF) read, the deal at a glance, each term beside its clause, confirmed. |
| 5 | 1:39 | Safety: the wrong company | the same contract filed under Dongguan is blocked (it names other companies), filed again under Foshan in one press, and the duplicate reading rejected. |
| 6 | 1:55 | From contract to forecast | Dongguan's new supply agreement confirmed, then “Set up in my books” with the forecast before and after, confirmed by the owner (Tier 2); Home's 120-day forecast reflects it. |
| 7 | 2:28 | Deals: a buyer asks for 60 days | Foshan asks for 60-day terms on its own keyed channel (the API's demo buyer key); FLOW's verdict and its counters side by side; Your agreements when Deals lists the confirmed contracts; in the full tour, Foshan's customer record. |
| 8 | 2:49 | Ask FLOW | “Are we safe?”, “What if Foshan pays 30 days late?” (the full tour adds “Who owes us the most?” and “Can we clear all our debts?”), then “我们安全吗？” with the app in Chinese; the full tour ends on a new conversation. |
| 9 | 3:17 | Fund the gap | the plan run from Cash & funding (all Tier 1 on these books; a Tier 2 step would be approved in Approvals); Home holds the reserve. |
| 10 | 3:36 | Activity and evidence | the hash-chained activity record in the owner's words, then the evidence view (each entry with its hash and the one before). |
| 11 | 3:53 | FLOW | “FLOW · supplier-owned working-capital agent · every figure from the books, every action logged”. |

Key frames: [5min-activity.png](frames/5min-activity.png), [5min-ask-flow-zh.png](frames/5min-ask-flow-zh.png), [5min-blocked.png](frames/5min-blocked.png), [5min-contract-to-forecast.png](frames/5min-contract-to-forecast.png), [5min-deal-at-a-glance.png](frames/5min-deal-at-a-glance.png), [5min-deal-verdict.png](frames/5min-deal-verdict.png), [5min-home-gap.png](frames/5min-home-gap.png), [5min-reserve-held.png](frames/5min-reserve-held.png), [5min-setup-review.png](frames/5min-setup-review.png).

Problems seen while recording: None: every chapter ran to its end.

## flow-full-tour (`--cut full`)

`flow-full-tour.webm`: 5:29 long, 40.9 MB, recorded 2026-10-17.

| # | Starts at | Chapter | What it shows |
|---|-----------|---------|---------------|
| 1 | 0:04 | Sign in | the landing page, then the owner sign-in with the demo build's pre-filled token. Empty books: Home cannot answer yet. |
| 2 | 0:15 | Set up your books | the six-step setup wizard on blank books. Lingnan Homeware Manufacturing Co., Ltd.: cash ¥400,000; a ¥150,000 credit line at 6.4% (Pearl River Commercial Bank) and ¥350,000 of invoice financing; Foshan Home Retail Co. with an open ¥420,000 invoice on 45-day terms and a contract invoicing ¥420,000 every 30 days; Dongguan Office Supplies Ltd. with an open ¥180,000 invoice; payroll ¥340,000 every month and a ¥120,000 supplier payment; a ¥300,000 minimum and the default limits. The review's first forecast, then the owner signs and opens the books. |
| 3 | 1:06 | Home: the forecast and the gap | the cash forecast, the gap before payroll and FLOW's funding plan (not approved yet). |
| 4 | 1:24 | Attach a deal | Foshan's supply agreement (PDF) read, the deal at a glance, each term beside its clause, confirmed. |
| 5 | 1:48 | Safety: the wrong company | the same contract filed under Dongguan is blocked (it names other companies), filed again under Foshan in one press, and the duplicate reading rejected. |
| 6 | 2:04 | A new customer | Shunde Kitchen Supply Co. added from the upload form. |
| 7 | 2:14 | From contract to forecast | Dongguan's new supply agreement confirmed, then “Set up in my books” with the forecast before and after, confirmed by the owner (Tier 2); Home's 120-day forecast reflects it. |
| 8 | 2:47 | A lender agreement | the bank's credit-line agreement (PDF) confirmed and linked to the credit line. |
| 9 | 3:04 | Deals: a buyer asks for 60 days | Foshan asks for 60-day terms on its own keyed channel (the API's demo buyer key); FLOW's verdict and its counters side by side; Your agreements when Deals lists the confirmed contracts; in the full tour, Foshan's customer record. |
| 10 | 3:34 | Ask FLOW | “Are we safe?”, “What if Foshan pays 30 days late?” (the full tour adds “Who owes us the most?” and “Can we clear all our debts?”), then “我们安全吗？” with the app in Chinese; the full tour ends on a new conversation. |
| 11 | 4:18 | Fund the gap | the plan run from Cash & funding (all Tier 1 on these books; a Tier 2 step would be approved in Approvals); Home holds the reserve. |
| 12 | 4:37 | Cash & funding | each funding source, how much is drawn and what is left. |
| 13 | 4:43 | Capex & purchases | the capex check on a ¥600k machine: NPV, payback and which financing holds every covenant and the reserve. |
| 14 | 4:55 | Receivables | who owes what, when it is due, and what is left once financing is repaid. |
| 15 | 5:03 | Activity and evidence | the hash-chained activity record in the owner's words, then the evidence view (each entry with its hash and the one before). |
| 16 | 5:21 | FLOW | “FLOW · supplier-owned working-capital agent · every figure from the books, every action logged”. |

Key frames: [full-activity.png](frames/full-activity.png), [full-ask-flow-zh.png](frames/full-ask-flow-zh.png), [full-blocked.png](frames/full-blocked.png), [full-contract-to-forecast.png](frames/full-contract-to-forecast.png), [full-deal-at-a-glance.png](frames/full-deal-at-a-glance.png), [full-deal-verdict.png](frames/full-deal-verdict.png), [full-home-gap.png](frames/full-home-gap.png), [full-reserve-held.png](frames/full-reserve-held.png), [full-setup-review.png](frames/full-setup-review.png).

Problems seen while recording: None: every chapter ran to its end.

## Notes from the walkthrough

- **Deals, "Your agreements" stays empty on these books (product bug).** A customer with a confirmed contract and open invoices but no
  negotiation (Foshan and Dongguan here) is neither "agreed" (`isAgreed` needs the "Terms negotiated" stage done) nor "invoices only"
  (`hasInvoicesOnly` needs no contract) in `apps/web/components/deals/deal-summary.tsx`, so confirming a customer's contract removes its
  row from Deals (a fix is in progress on fix/deals-contracts-upload). The Deals scene opens Your agreements whenever the page lists a
  confirmed contract.
- **A question typed in Chinese while the app is in English is answered in English.** The web sends the page's language with every chat
  message, and it overrides the API's own language detection, so the Ask FLOW scene switches the app to 中文 before asking “我们安全吗？”.
- **Why Dongguan has an open invoice in the setup.** With it, FLOW finds counters to Foshan's 60-day request inside the limits; without it
  (monthly payroll, no other receipts) FLOW finds no counter and recommends declining, and the deal shows no counters.
- **The buyer's request** arrives through the API's keyed buyer channel (`POST /offers` with the demo key for BUYER-1, Foshan, which is the
  first customer the setup enters) carrying the worked example EX01's message, whose reading is cached; the demo books are never loaded.

## Re-record

From the repository root, with the web app's packages installed (`cd apps/web; pnpm install`), `uv` on the PATH and Playwright's
Chromium installed (`pnpm exec playwright install chromium` in apps/web):

```
pnpm demo:video              # flow-demo-5min
pnpm demo:video --cut full   # flow-full-tour
```

Each run starts `node scripts/demo.mjs --blank --fresh --keep --api-port 8090 --web-port 3090` (ports 8090 and 3090 must be free;
`--fresh` resets the kept demo books in `.demo-data/flow-demo.db`), warms every page, records the cut's test in
`apps/web/e2e/video/walkthrough.spec.ts` headless (Playwright project `video`, `E2E_TARGET=video`), writes this folder, and stops only
the processes it started. `VIDEO_SLOWMO_MS` (default 180) sets the pause after every browser action. A cut is a list of scenes and a pace
for the viewing pauses (`CUTS` in walkthrough.spec.ts). The mock and live suites never run the video spec.
