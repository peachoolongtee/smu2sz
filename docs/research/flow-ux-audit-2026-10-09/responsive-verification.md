# FLOW Assessment B — bounded screenshot follow-up

STATUS: Complete. No new app defect confirmed for invisible motion-reveal headings/cards.

FILES CHANGED: /tmp/flow-screenshots-b.spec.ts, /tmp/flow-screenshots-b.config.ts, /tmp/flow-assessment-b-screenshot-verification.md, /tmp/flow-shots-b/{desktop,phone,tablet,small-laptop}/ and /tmp/flow-pw-b-extra/. No source edits or native Safari actions.

FINDINGS: The representative settled Chromium captures show headings, card borders, card text and recommendations visibly rendered. This rules out a general permanently-hidden-card defect in the tested Chromium runtime. It does not prove the cause of native Safari background screenshots or rule out a Safari-specific rendering problem. Do not classify that observation as an app defect or as a proven compositor problem from this evidence.

## Source and capture procedure

Existing apps/web/e2e/screenshots.spec.ts was the only browser interaction workflow used. The repo spec explicitly skips the live project, and its contexts assume mock isolation. A /tmp-only copy removed that live skip and added a beforeEach reset to the disposable in-memory API at http://localhost:8012/demo/reset; its import of the repo's live fixture retained demo-owner-token. Project remains named live. Existing page navigation, deal reading/evaluation, funding confirmation, screenshot timing and product assertions were retained. Only the first existing screenshot test (opening books, deal read/checked, plan run) was executed at each viewport. No broad functional test suite was rerun.

Capture provenance: Playwright Chromium, full-page PNG screenshot API, deviceScaleFactor=1, API8012 and web3002, LLM_MODE=cache, TERMSLEDGER_NO_DOTENV=1, DATABASE_URL=memory. Parent's temporary touch CSS correction was present. These are patched-runtime screenshot assets, not original startup evidence or Safari screenshots.

| Capture folder | Viewport | Motion preference | Result |
|---|---|---|---|
| /tmp/flow-shots-b/desktop | 1440×900 | reduce | 1 existing screenshot walk passed in 18.6s; 11 PNGs |
| /tmp/flow-shots-b/phone | 412×915 | reduce | 1 passed in 17.2s; 11 PNGs |
| /tmp/flow-shots-b/tablet | 820×1180 | reduce | 1 passed in 17.4s; 11 PNGs |
| /tmp/flow-shots-b/small-laptop | 1366×768 | no-preference | 1 passed in 17.2s; 11 PNGs |

Each folder contains manifest.json recording URL, viewport, document height and viewport-screen count for every capture. Total: 44 PNG assets. The phone and tablet runs enable touch; phone enables mobile emulation. These are responsive viewport classes in Chromium, not certifications for particular device models.

## Representative assets visually inspected

- desktop/05-cash-day0.png: Cash & funding heading, status/figure cards, recommendation, alternative table, cash forecast and action doors all visible.
- desktop/04-deals-evaluated.png: Deals heading, inbox, parsed asks, Counter recommended, recommended response and folds all visible.
- phone/01-home-day0.png: navy status card, all financial figures, next action, cost/availability/authority tiles, receivables and details visibly rendered.
- phone/02-deals-inbox.png: Deals heading, inbox and empty-selection body visibly rendered.
- tablet/03-deals-read.png: heading, next-step action, inbox and extracted buyer asks visibly rendered.
- small-laptop/01-home-day0.png (normal motion): status card, recommendation, tiles, receivables and disclosures visibly rendered.
- small-laptop/07-activity-day0.png (normal motion): heading, timeline card, empty states and evidence link visibly rendered.

Full-page PNGs retain fixed navigation and Ask FLOW at their viewport-relative capture position. A fixed bar drawn part-way through a long image should not by itself be treated as proof of live page content coverage; the earlier responsive tests check actual hit boxes separately.

## Source corroboration

apps/web/app/globals.css:199 defines biz-reveal from opacity:0/translateY(6px) to opacity:1/transform:none. At :258 .motion-reveal uses animation-fill-mode:backwards rather than forwards; the underlying element has no permanent opacity:0 rule. For normal motion, the animation reaches visible state and then drops its animation style. Reduced motion at :471 shortens animation duration to 0.001ms. The existing screenshot helper waits for networkidle plus 300ms before capture. This source is consistent with the visible settled snapshots.

TEST COMMAND (repeated sequentially with each viewport's variables):

`UV_CACHE_DIR=/tmp/flow-uv-cache UV_NO_SYNC=1 E2E_TARGET=live E2E_LIVE_PORT=3002 E2E_API_PORT=8012 SHOTS_DIR=/tmp/flow-shots-b FLOW_B_VIEWPORT=<label> FLOW_B_WIDTH=<width> FLOW_B_HEIGHT=<height> [FLOW_B_MOTION=no-preference] pnpm exec playwright test --config=/tmp/flow-screenshots-b.config.ts -g 'opening books'`

TEST RESULT: Four successful existing screenshot walks, 44 PNGs. No failures. Each test run started and stopped its own disposable servers. Existing user API/web/Safari untouched.

REGRESSIONS: None introduced.

INTERFACE CHANGE REQUESTS: None.

ASSUMPTIONS: Conclusions apply to settled Chromium snapshots under the temporary touch-rule correction. Native Safari rendering/capture cause remains unverified; do not overstate cross-browser support.
