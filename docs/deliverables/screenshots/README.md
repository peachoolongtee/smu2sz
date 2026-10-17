# Annotated product screenshots

Screenshots of FLOW for the final technical document (FinTechathon 2026). They were taken on 17 Oct 2026 from `dev` at
975e082f. The app ran in live mode with `node scripts/demo.mjs --api-port 8131 --web-port 3231`: in-memory golden books,
cached model outputs and no real funds. The browser was Chromium (Playwright) at 1440×900 and device scale 2, with
reduced motion. The phone shot is 390×844. The app was in Business mode, signed in with the local demo owner token.

Each shot comes in two versions:

- `shotN-*.png` is annotated. It has orange (#E8590C) numbered callouts and a legend band underneath.
- `shotN-*-raw.png` is the same crop without annotations.

The orange callouts are filled circles. The Home chart has its own numbered markers (outlined, red or teal), which are part of
the product.

Shots 1, 8 and 9 show day 0. Shots 2 and 7 show day 0 after the buyer's message was received and checked (story scenes 1
and 2). Shot 5 shows day 34. Shot 3 shows day 34 after the cure was queued. Shots 4 and 6 show day 38, after the whole
story.

| Shot | Caption | Callouts |
|---|---|---|
| `shot1-home.png` | Home on day 0: without new funding, cash falls to −¥105,000 in 30 days. FLOW recommends securing ¥405,000 before payroll in 12 days, at a cost of ¥3,113.93, with no approval needed. | 1 · Cash in 30 days: −¥105,000 without new funding, ¥300,000 with the plan. 2 · The recommendation: secure ¥405,000 before payroll in 12 days. 3 · What the plan costs: ¥3,113.93. 4 · Inside the signed limits: no approval needed. |
| `shot2-deal-decision.png` | Foshan's WeChat request from the Inbox (top), and the deal FLOW checked against the books (below): the verdict, why the request cannot be accepted as asked, and the priced choices. | 1 · Foshan's WeChat request, as it arrived in the Inbox. 2 · The verdict: Option A, and why not accept as asked (breached by ¥135k for 15 days; outside the signed limits). 3 · The choices side by side, each priced: accept as asked ¥5,040.00 once plus ¥28,326.92 over 12 months; Option A ¥3,035.99; Option B about ¥0. 4 · Nothing is sent until you click. |
| `shot3-approval.png` | The cure on day 34: a ¥200,000 invoice-financing request at 32.5% a year, above the 15% ceiling. It waits on Approvals and nothing has run. | 1 · Why it needs you: 32.5% a year is above the 15% ceiling you signed. 2 · What it costs: ¥1,782.19 for ¥200,000. 3 · Waiting for your approval: nothing has run. 4 · Nothing runs until you authorize or decline. |
| `shot4-record.png` | Activity after the story, with "Record chain checks passed" (top). Below are evidence entries 8 to 10: each entry's previous hash is the hash of the entry before it, and the executor recorded the queued approval as APR-000001. | 1 · Record chain checks passed. 2 · The approval in plain words: asked at 32.5% a year, above the 15% ceiling, then approved by you. 3 · Entry 9's previous hash equals entry 8's hash. 4 · The executor's record: queued for owner approval as APR-000001. |
| `shot5-chat.png` | Ask FLOW on Home, day 34: "Am I safe this month?" The answer comes from the books: ¥200,000 short in 8 days, with DSCR, leverage and concessions inside their limits. | 1 · The owner's question, in plain words. 2 · The answer, worked out from the books. 3 · Details: the figures behind the answer. 4 · What the answer covers: the whole company. |
| `shot6-capex.png` | The Capex and purchases hub. At the top are the health figures. Below them, Your purchases holds the demo vendor contract (GZPM-2026-114, ¥600,000, reading to review), followed by the workbench for testing a machine without a contract. | 1 · Financial health: headroom, lowest point, 90-day coverage, worst DSCR against its 1.25× covenant. 2 · Your purchases: the demo vendor contract FLOW has read. 3 · The owner reviews the agent's reading first. 4 · The workbench: test a machine without a contract. |
| `shot7-deal-zh.png` | The same deal page as shot 2, in Chinese. The buyer's message stays in the words it was sent in. | Same as shot 2. The legend is in Chinese. |
| `shot8-phone-home.png` | Home at 390 px on day 0: the outlook and the recommendation card, with the tab bar at the bottom. | 1 · Cash in 30 days without new funding. 2 · The amount to secure. 3 · What it costs. 4 · No approval needed. |
| `shot9-attach.png` | Attach deals: the agent's reading of supply agreement FHR-2026-07. Each term sits beside its quoted clause, and the focused term (Price, §3.1) lights its clause in the contract text. | 1 · Each term the agent read, with its clause number and the exact words it quoted. 2 · The clause lights up in the contract text when you focus its term. 3 · Numbered markers show which terms each clause holds. |
| `shot10-ask-answer.png` | Ask FLOW's full page on day 0 answering "Are we safe?" as an answer card: the lead sentence, three key figures, the plan's cost and two links. Cropped, without annotations, from `docs/screenshots/ask-ui/after/page-desktop-en-answer.png` (taken 18 Oct 2026 on `feat/ask-ui` against the live API on the opening books, 1440×900). | none |

## Notes for the document

- **Shot 2.** The deal is titled "60-day terms on future invoices and 2 more terms". The Option B row reads "0.30% price
  rise", not "price adjustment", and its cost is "About ¥0 (net economic cost over 12 months)".
- **Shot 3.** The approval card does not show the id APR-000001. The id appears in the page address
  (`#approval-APR-000001`) and in the evidence record, which shot 4 shows.
- **Shot 6.** The figures are from day 38, after the story: ¥200,000 above the minimum, lowest point ¥300,000 on day 42,
  coverage 2.24× and worst DSCR 1.92×. On day 0 they read ¥100,000, −¥105,000 on day 30, 2.55× and 2.00×.
- **Shot 8.** At 390 px the recommendation headline is cut off: "Secure ¥405,000 before payroll in 12…".
- **Shot 9.** The Attach deals page is being redesigned on `feat/attach-fullwidth`. Retake this shot once that branch lands
  on dev.
