# Screenshots after the 12 October merge (contract ingestion, its review fixes, the reskin)

Taken with `apps/web/scripts/capture-remediation.mjs` against a live stack of `int/contracts` (the walks of `e2e/live.spec.ts` and `e2e/demo.spec.ts`), at desktop 1440, laptop 1366, tablet 820 and phone 412 widths; a `manifest.json` per width records the page height and the primary action's position. The phone set was re-taken after the script's brand-blue constant was moved to the reskin's token (`--color-brand-600`, #0368e9); on a 915 px phone viewport the primary action's bottom edge is at 819 (Home), 852 (Deals), 813 (Cash), 826 (Approvals) and 907 (the Demo's decide scene), all inside the first screen. The Documents page and the deal picture are not in the walks yet (ticket #103).

The cold read of eight shots (12 Oct): Home 8, Approvals 8, Cash 7, Deals 6, Demo 6, zh Home 7; no blocker; the follow-ups are on #103.
