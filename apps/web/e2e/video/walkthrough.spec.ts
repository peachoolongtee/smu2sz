import { expect, test } from "@playwright/test";
import { installOverlay, Reel, type Cut, type Scene } from "./reel";
import * as story from "./story";
import * as tour from "./tour";

/**
 * The demo videos (project `video`, E2E_TARGET=video; never part of the mock or live suites), recorded at 1080p against
 * `node scripts/demo.mjs --blank --keep --data .demo-data/video.db --fresh` (live mode, cached LLM readings, no network, no key), which
 * `scripts/record-demo-video.mjs` (`pnpm demo:video --cut 5min|full`) starts, waits for and stops. Each test is one cut, one continuous video:
 *
 *   flow-demo-5min   the competition's video (FEATURE_INVENTORY.md 16a), at most 4:50: story.ts
 *   flow-full-tour   every feature in twelve chapters (FEATURE_INVENTORY.md 16b): tour.ts
 *
 * A cut is a list of scenes (one per feature or step, each with its caption) and a pace for the viewing pauses. The takes inside a cut
 * switch books behind a title card (reel.ts `take`). VIDEO_SCENES=id,id,… records only those scenes (a dry run of one chapter; each tour
 * chapter starts its own take when it needs other books). Out: `chapters.json` in the test's output folder (each chapter's start in seconds
 * from the start of the recording, and anything that went wrong), and key frames in VIDEO_FRAMES_DIR when set.
 */

const CUTS: Record<Cut, { name: string; pace: number; maxSeconds: number | null; scenes: Scene[] }> = {
  "5min": {
    name: "flow-demo-5min",
    pace: 1.3, // 3:58 at pace 1 (18 Oct): the reading pauses take the rest, under the 4:50 limit
    maxSeconds: 290, // the competition allows 5:00; 4:50 leaves room for the player's own start
    scenes: [
      story.titleCard,
      story.setupClip,
      story.goldenHome,
      story.buyerAsks,
      story.verdict,
      story.negotiate,
      story.agreement,
      story.bankAndTime,
      story.latePayment,
      story.cure,
      story.landed,
      story.contractSetUp,
      story.askFlow,
      story.evidence,
      story.closingCard,
    ],
  },
  full: {
    name: "flow-full-tour",
    pace: 1,
    maxSeconds: null,
    scenes: [
      story.titleCard,
      tour.setup,
      tour.dailyView,
      tour.documents,
      tour.customers,
      tour.deals,
      tour.money,
      tour.lifecycle,
      tour.askFlow,
      tour.sandbox,
      tour.capex,
      tour.records,
      tour.security,
    ],
  },
};

const only = (process.env.VIDEO_SCENES ?? "").split(",").filter(Boolean);

for (const [cut, spec] of Object.entries(CUTS) as [Cut, (typeof CUTS)[Cut]][]) {
  test(spec.name, async ({ page }) => {
    await installOverlay(page);
    const scenes = only.length ? spec.scenes.filter((x) => only.includes(x.id)) : spec.scenes;
    const reel = new Reel(page, cut, spec.pace, scenes);
    await page.goto("/welcome");
    if (only.length) {
      // A dry run of some scenes: signed in already (the full cut signs in on camera).
      await page.evaluate((tok) => sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: tok })), "demo-owner-token");
    }
    await reel.play();
    reel.write(spec.name);
    expect(reel.problems, "every chapter ran to its end").toEqual([]);
    if (spec.maxSeconds !== null && !only.length) expect(reel.seconds, `${spec.name} fits its limit`).toBeLessThanOrEqual(spec.maxSeconds);
  });
}
