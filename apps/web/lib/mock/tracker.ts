/**
 * Mock for the deal tracker: GET /decisions/{id}/tracker. Recordings of the real API (`scripts/record-mocks.mjs --tracker`, `mocks/tracker/*.json`,
 * { en, zh } each), chosen by the mock's own story; nothing here computes or edits a figure or a sentence. Until a recording exists the route answers
 * 404 (the page then says so in words and the decision record shows no link).
 */

import { ApiError } from "../errors";
import type { TrackerView } from "../tracker";

export async function mockTracker(id: string, _lang: "en" | "zh"): Promise<TrackerView> {
  void _lang;
  throw new ApiError(404, "No tracker has been recorded for this deal.", { code: "TRACKER_NOT_RECORDED", id });
}
