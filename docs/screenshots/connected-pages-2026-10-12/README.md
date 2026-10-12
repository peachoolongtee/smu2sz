# Connected pages at dev 1a6b613b, 12 Oct 2026

Home, Deals, Receivables, the Customer overview and Cash, at 1440 wide (`desktop`) and 390 wide (`phone`), in English (`en`) and Chinese (`zh`). Taken by `apps/web/scripts/capture-connected-pages.mjs` against a fresh in-memory API (day 0, `FEATURE_ENVELOPE`, `FEATURE_PRICE_CURVE`, `FEATURE_COLLECTIONS_WORTH`, `FEATURE_EXPOSURE` on) and a live-mode production build. Full-page shots; on the phone the fixed header and tab bar land mid-image, which is a full-page capture artefact. `manifest.json` lists every shot with the money figures read from its page text.

File name: `NN-<page>-<state>-<desktop|phone>-<en|zh>.png`. Shots 01 to 05 are one walk at day 0 with the funding plan not yet run; 06 is taken after the plan ran.

| File (per width and language) | State | Cash today | Lowest cash | Foshan receipt |
|---|---|---|---|---|
| 01-home-day0-before-plan | Home, day 0, plan not run | tile Cash today: ¥400k | tile Lowest point with the plan: ¥300k (headline: falls to ¥60k, ¥240k below the ¥300k minimum, if nothing is done) | tile Arriving next: ¥420k, Foshan, in 32 days |
| 02-deals-foshan-comparison | Deals queue, Foshan decision selected and checked, comparison fold open | "Today" row of the cash table: ¥400,000.00 | the "Lowest" row and the ¥300k reserve line | the ask on ¥420,000.00 |
| 03-receivables-three-layers | Receivables, invoice RCV-A selected (the three layers) | not shown as cash | not shown | owed ¥420,000.00, about ¥420k at collection, due in 32 days |
| 04-customer-buyer1 | Customer overview, BUYER-1 | not shown | not shown | invoice ¥420,000.00 |
| 05-cash-stress-link | Cash, `/cash?stress=BUYER-1:30&invoice=RCV-A&customer=BUYER-1&from=customer`, "Back to Foshan" link | ¥400,000.00 in the cash table, ¥400k on the chart | falls to ¥60k in 12 days without the plan (stressed line lower still: -¥250k in 60 days) | Foshan pays +¥420k in 32 days (key events), invoice ¥420,000.00 |
| 06-home-after-plan | Home after Run funding plan | Cash today: ¥550k (the ¥150k credit-line draw landed) | Lowest point: ¥300k | Arriving next: ¥255k (the invoice financing); Foshan's ¥420k is no longer the next arrival |

How to check across pages: the day 0 figures 400k, 300k reserve and 420k must read the same on 01, 02 and 05; the invoice is ¥420,000.00 on 02 to 05. The pre-plan lowest on Cash (¥60k) matches the Home headline.
