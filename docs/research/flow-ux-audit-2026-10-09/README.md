# FLOW independent UX audit evidence — 9 October 2026

Read [the complete 32-section audit](../independent-flow-ux-audit-2026-10-09.md).

Baseline: `e15e3eebec3b25d245eb67c7306f02d92b0e6bb2`. All responses and screenshots contain synthetic fixtures, in-memory state, and cached model output. No real bank, lender, production database or live-model certification is implied.

The shared checkout advanced through concurrent pilot work during the audit; the report records that boundary. These captured default golden-book workflows do not certify the newer entire checkout or its pilot features. The non-reloading primary API and the shared frontend/source reads are explicitly distinguished.

- `original-startup-error.html`: HTTP 500 response from the documented dev startup before the temporary touch-rule correction.
- `home-missed-payment.json`, `state-missed-payment.json`: current day-34 cash was presented at a past first-breach date (F01).
- `approval-after-decision.json`, `home-after-decision.json`: approved quote disappeared and the zero-floor rescue left the reserve risk unresolved (F12/F13/F17).
- `receipt-reconciliation-day2.json` and `receipt-reconciliation-day34.json`: a historical receipt's expired deadline remained “by today” (F03).
- `receipt-*`, `home-partial-payment.json`: partial payment, matching, residual face and duplicate handling; the UI summary's loss of partial-payment meaning (F25).
- `receipt-evaluation.json`: exact counter gross/offset/net economics and original offer impact.
- `abstention-foreign-currency.json`: safe but unhelpfully generic clarification (F24).
- `demo-completed-ledger.json`: operations after the fifteen-step run; compare the unchanged verdict label (F04).
- `api-probe-manifest.json` and `api-probes.py`: direct API probe sequence and timings. Script resets only the expressly disposable localhost:8015 audit server; do not aim it at business data.
- `demo-timing.json`: native guarded fifteen-step run, 17.997 seconds excluding reading/narration; earlier rapid-click restart recorded separately.
- `screenshots/`: 44 current Chromium full-page PNGs and four manifests. Widths: 1440, 1366, 820, 412. All ran after the temporary CSS correction. Fixed bars inside a full-page capture are not evidence that a live bar permanently obstructs the page.
- `technical-assessment.md`: detector, test commands, failure coverage, exact limitations, and infrastructure failures/reruns.
- `responsive-verification.md`: screenshot provenance and the unconfirmed Safari capture observation.
- `primary-audit-provenance.json`: hash of the primary report before the optional comparison with earlier audits.

The original touch rule and generated source/configuration side effects were restored after inspection. Only audit artifacts are intended to remain. The audit's proposed fixes are not implemented by these files.
