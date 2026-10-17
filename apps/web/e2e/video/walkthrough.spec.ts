import { expect, test } from "@playwright/test";
import { installOverlay, Reel, type Cut, type Scene } from "./reel";
import * as s from "./scenes";

/**
 * The demo videos (project `video`, E2E_TARGET=video; never part of the mock or live suites), recorded at 1080p against
 * `node scripts/demo.mjs --blank --fresh --keep` (live mode, cached LLM readings, no network, no key), which `scripts/record-demo-video.mjs`
 * (`pnpm demo:video --cut 5min|full`) starts, waits for and stops. Each test is one cut, one video, from blank books:
 *
 *   flow-demo-5min   the competition's video: the strongest end-to-end story on the owner's own books, at most 4:50
 *   flow-full-tour   every scene, at the full reading pace
 *
 * A cut is a list of scenes (scenes.ts, one per feature or step) and a pace for the viewing pauses. Out: `chapters.json` in the test's
 * output folder (each chapter's start in seconds from the start of the recording, and anything that went wrong), and key frames in
 * VIDEO_FRAMES_DIR when set. The recorder turns them into docs/deliverables/video/README.md.
 */

const CUTS: Record<Cut, { name: string; pace: number; maxSeconds: number | null; scenes: Scene[] }> = {
  "5min": {
    name: "flow-demo-5min",
    pace: 1,
    maxSeconds: 290, // the competition allows 5:00; 4:50 leaves room for the player's own start
    scenes: [s.signIn, s.setupBooks, s.homeGap, s.attachDeal, s.wrongCompany, s.contractToForecast, s.buyerRequest, s.askFlow, s.fundGap, s.activity, s.endCard],
  },
  full: {
    name: "flow-full-tour",
    pace: 1,
    maxSeconds: null,
    scenes: [
      s.signIn,
      s.setupBooks,
      s.homeGap,
      s.attachDeal,
      s.wrongCompany,
      s.newCustomer,
      s.contractToForecast,
      s.lenderAgreement,
      s.buyerRequest,
      s.askFlow,
      s.fundGap,
      s.cashFunding,
      s.capex,
      s.receivables,
      s.activity,
      s.endCard,
    ],
  },
};

for (const [cut, spec] of Object.entries(CUTS) as [Cut, (typeof CUTS)[Cut]][]) {
  test(spec.name, async ({ page }) => {
    await installOverlay(page);
    const reel = new Reel(page, cut, spec.pace, spec.scenes);
    await s.opening(reel);
    await reel.play();
    reel.write(spec.name);
    expect(reel.problems, "every chapter ran to its end").toEqual([]);
    if (spec.maxSeconds !== null) expect(reel.seconds, `${spec.name} fits its limit`).toBeLessThanOrEqual(spec.maxSeconds);
  });
}
