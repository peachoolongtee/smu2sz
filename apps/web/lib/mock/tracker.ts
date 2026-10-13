/**
 * Mock for the deal tracker: GET /decisions/{id}/tracker. Recordings of the real API (`scripts/record-mocks.mjs --tracker`, `mocks/tracker/<moment>.json`,
 * { en, zh } each), chosen by the mock's own story (the same state the decision record's snapshots use, lib/mock/decisions.ts); nothing here computes or
 * edits a figure or a sentence. The moments: the offer not yet agreed (`available: false`), agreed (day 0), receipt (the day-2 bank receipt), late (day 34),
 * pending (the cure queued for approval), approved, settled (day 38). A decision the story has not made answers 404, as the API does.
 */

import { ApiError } from "../errors";
import { offerOf } from "../selection";
import type { TrackerView } from "../tracker";
import type { DecisionContext } from "./decisions";

type Moment = "offer" | "agreed" | "receipt" | "late" | "pending" | "approved" | "settled";
type Recording = { en: TrackerView; zh: TrackerView };
const LOAD: Record<Moment, () => Promise<{ default: unknown }>> = {
  offer: () => import("../../mocks/tracker/offer.json"),
  agreed: () => import("../../mocks/tracker/agreed.json"),
  receipt: () => import("../../mocks/tracker/receipt.json"),
  late: () => import("../../mocks/tracker/late.json"),
  pending: () => import("../../mocks/tracker/pending.json"),
  approved: () => import("../../mocks/tracker/approved.json"),
  settled: () => import("../../mocks/tracker/settled.json"),
};

/** Which recording the story is at: the deal made or not, then the clock and the cure's stage. */
export function trackerMoment(ctx: DecisionContext, id: string): Moment {
  const offer = offerOf(id);
  if (!offer || !ctx.commitmentOffers.includes(offer)) return "offer";
  if (ctx.day >= ctx.newsDay) return ctx.stage === "approved" ? (ctx.day >= ctx.settledDay ? "settled" : "approved") : ctx.stage === "pending" ? "pending" : "late";
  return ctx.receipted ? "receipt" : "agreed";
}

export async function mockTracker(ctx: DecisionContext, id: string, lang: "en" | "zh"): Promise<TrackerView> {
  const rec = JSON.parse(JSON.stringify((await LOAD[trackerMoment(ctx, id)]()).default)) as Recording;
  const read = rec[lang];
  // The recording is of the story's own deal; any other decision is one the story has not made.
  if (read.decision_id !== id) throw new ApiError(404, "Not Found", { code: "DECISION_NOT_FOUND" });
  return read;
}
