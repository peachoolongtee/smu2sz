/**
 * Mock for the two reads the Cash page's late-payment deep link makes: GET /buyers/{id}/exposure (the buyer's late-payment test with no deal) and
 * GET /receivables (which only names the invoice the link carries). Recordings of the real API (scripts/record-mocks.mjs); nothing here computes money.
 * BUYER-1 is the one buyer the recording has; any other is unknown (null, as the server's 404 reads).
 *
 * Test hook (a spec that uses it says so: a temporary in-spec patch of a recorded read until the server's fields are recorded): set
 * `tl-mock-buyer-exposure` to "off" and the read answers null, as with the feature off; to "fail" and it answers 503; or to a JSON object and it is
 * merged deep into the recorded read, for the `context.back` a recording taken without a context does not carry.
 */

import type { ExposureContext } from "../api";
import { ApiError } from "../errors";
import type { BuyerExposureView, ReceivablesRead } from "../types";

export const BUYER_EXPOSURE_KEY = "tl-mock-buyer-exposure";
/** Test hook, as on the Receivables page: `{ "rows": { "<receivable id>": { ...fields merged deep into that row } } }` is applied to the recorded read. */
export const RECEIVABLES_PATCH_KEY = "tl-mock-receivables-patch";

const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

function merge(base: unknown, patch: unknown): unknown {
  if (patch && typeof patch === "object" && !Array.isArray(patch) && base && typeof base === "object" && !Array.isArray(base)) {
    const out: Record<string, unknown> = { ...(base as Record<string, unknown>) };
    for (const [k, v] of Object.entries(patch)) out[k] = merge(out[k], v);
    return out;
  }
  return patch;
}

/** GET /buyers/{id}/exposure. The context is the server's to turn into `context.back`; the recording carries none. */
export async function mockBuyerExposure(buyerId: string, lang: "en" | "zh", _context?: ExposureContext): Promise<BuyerExposureView | null> {
  void _context;
  let raw: string | null = null;
  try {
    raw = typeof window === "undefined" ? null : window.sessionStorage.getItem(BUYER_EXPOSURE_KEY);
  } catch {
    /* no storage: no patch */
  }
  if (raw === "fail") throw new ApiError(503, "The late-payment test is unavailable");
  if (raw === "off" || buyerId !== "BUYER-1") return null;
  const file = await (lang === "zh" ? import("../../mocks/buyer_exposure_zh.json") : import("../../mocks/buyer_exposure.json"));
  const view = clone<BuyerExposureView>(file.default);
  return raw ? (merge(view, JSON.parse(raw)) as BuyerExposureView) : view;
}

/** GET /receivables: the opening books' recording (the invoices' names do not change along the story). */
export async function mockReceivables(lang: "en" | "zh"): Promise<ReceivablesRead> {
  const file = await (lang === "zh" ? import("../../mocks/receivables/day0_zh.json") : import("../../mocks/receivables/day0.json"));
  const read = clone<ReceivablesRead>(file.default);
  let raw: string | null = null;
  try {
    raw = typeof window === "undefined" ? null : window.sessionStorage.getItem(RECEIVABLES_PATCH_KEY);
  } catch {
    /* no storage: no patch */
  }
  const rows = raw ? (JSON.parse(raw) as { rows?: Record<string, unknown> }).rows : undefined;
  if (rows) read.rows = (read.rows ?? []).map((r) => (rows[r.receivable_id] ? (merge(r, rows[r.receivable_id]) as typeof r) : r));
  return read;
}
