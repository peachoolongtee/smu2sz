# Session handoff 12 (12 Oct 2026, night): the connected pages shipped; Home V2 and the design system started

Read docs/handover/08 (protocol, gates, quirks), 10 (the day's state) and 11 (the three economics tracks handed to an external
engineer) first. New rules since 10: agents never run an unscoped `pkill` (kill by own ports or PIDs); the live gate is the
WHOLE live project (`E2E_TARGET=live … pnpm exec playwright test --project live`), not two files; the exposure cold-read timing
test has a 10 s bound under SKIP_PERF_BENCH (3 s otherwise).

## dev at 1c4b3bbf (+ the design merge), pushed
Merged via int/connected, every branch reviewed (code and, for pages, design) and fixed before merge; gate API 1428, mock 374,
live project 117:
- #108 Customer overview: `GET /customers/{id}/overview` and the page at /customers/[id]; every customer name in Deals,
  Receivables and Activity links there with the URL context (`customer`, `decision`, `path`, `invoice`, `from`).
- #109 Deals queue: four tabs, the list, the decision-first detail, the always-visible three-path chart with the exposure
  band, the comparison fold, the server's per-path words (`lowest_*`, `limit_word`, `share_after_text`, the `do_nothing`
  path with words only and null band/capacity/stress entries), `recheck_text`, `customer_context`, `context.back`.
- #110 Receivables in three layers: `GET /receivables` (summary counts, two server headlines, `repays_line`; rows with
  `net`, `financing_state`, `governed_by`, `early_payment`, `pending_counter`, `collection_state`, `collection_action`,
  `basis`), the lifecycle Arranged · Received · Repaid, the first collection action as the page's filled primary, the
  buyer-scoped stress aside (`GET /buyers/{id}/exposure`).
- #111 Home truth: planned vs executed funding words, `plan_line_label`, the lowest row named by its cause, one arrival
  fact per leg, `effect_rows`, the server's stress sentence, "Read today".
- #115 Cash consumes the stress deep link (`stress`, `invoice`, `customer`, `decision`, `path`, `from`); the back link by
  origin from the server.
- #116 Receipts by basis (OWED / SCHEDULED / AGREED / PENDING on series and rail events and on Receivables rows; `cash.pending`
  as the dashed alternative with `receipts_legend_text`; `scheduled_note`; `cash.stress.text/funding_text/net_later_text`
  equal to the buyer route's); Home, Cash and Receivables say the same words.
- The Demo margin is a config default (`DEMO_GROSS_MARGIN_BP`), provenance DEMO, one margin function.

## In motion
- #112 design system on feat/design-system (tokens, three cards, SegmentedTabs per the owner's pill reference, StateWord,
  the type scale, the collapsible sidebar): spec scratchpad map-econ/design-system-112.md (copy into docs/design on merge).
- Home V2 wave 1 server on feat/home-v2-api (`GET /worklist`, `GET /customers`, `home_v2` fields on /home, FEATURE_HOME_V2):
  spec map-econ/home-v2-wave1-api.md; design of record docs/design/home-v2-2026-10-12/ (five review rounds; prototype
  HomeV2Proto.dc.html; owner's go 12 Oct: "good enough to proceed, build and refine along the way").
- Handed out (handoff 11): #98 envelope, #100 comparator, #97 Inputs sheet.

## Next, in order
Home V2 wave 2 (default mode, web) once #112 and wave 1 merge; wave 3 (customer and decision focus); wave 4 (states and the
twelve-situation test matrix); wave 5 (the swap behind the flag). Then #113 (the full Financial Timeline on Cash, with the
motion), #114 (polish). Still open: #103, #104 (owner), #106, #66, #59, #101, #102, screenshots of the five pages for the
deliverables (docs/screenshots), the closed-loop demo path beside the stepper.
