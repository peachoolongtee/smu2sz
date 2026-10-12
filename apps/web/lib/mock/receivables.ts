/**
 * Mock for GET /receivables and the buyer exposure behind the Receivables aside: recordings of the real API (scripts/record-mocks.mjs), chosen as the
 * home summary is (`home.receivablesPoint`). Nothing here computes money: every figure and sentence is the recorded string.
 *
 * Test hook, like NO_RECEIPT_KEY: set `tl-mock-receivables-offer` to "1" and, on the opening books, the read is the one taken with the buyer's
 * early-payment message open (its counter would apply to the invoice, so the row carries `pending_counter`). The exposure recording belongs to that
 * offer's decision and is served for it only. `tl-mock-receivables-absent` = "1" makes the route absent (null), as on a server without it.
 */

import type { ExposureContext } from "../api";
import { ApiError } from "../errors";
import type { BuyerExposureView, ReceivablesRead } from "../types";
import { mockClock, receivablesPoint, type ReceivablesPoint } from "./home";

export const RECEIVABLES_OFFER_KEY = "tl-mock-receivables-offer";
/**
 * Test hook for what the demo path cannot reach (an unrecorded financing, a missed promise, a partial read): set to a JSON object
 * `{ "partial": {...}, "summary": {...}, "rows": { "<receivable id>": { ...fields merged into that row, objects merged deep } } }` and the recorded
 * read is returned with it applied. A spec that uses it says so: it is a temporary in-spec patch of a recorded read until the server's fields are recorded.
 */
export const RECEIVABLES_PATCH_KEY = "tl-mock-receivables-patch";
/** Test hooks: "1" makes GET /receivables fail (503), and "1" on the second key makes GET /reconciliation fail, so the pages' failure states can be seen offline. */
export const RECEIVABLES_FAIL_KEY = "tl-mock-receivables-fail";
export const RECONCILIATION_FAIL_KEY = "tl-mock-reconciliation-fail";
/** Test hook: set to "1" and GET /receivables is absent (a server without the route), so the Receivables page keeps the reads it had. */
export const RECEIVABLES_ABSENT_KEY = "tl-mock-receivables-absent";

const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

type Loader = () => Promise<{ default: unknown }>;

const en: Record<ReceivablesPoint | "offer", Loader> = {
  day0: () => import("../../mocks/receivables/day0.json"),
  quiet: () => import("../../mocks/receivables/quiet.json"),
  day2: () => import("../../mocks/receivables/day2.json"),
  after_fund: () => import("../../mocks/receivables/after_fund.json"),
  day34: () => import("../../mocks/receivables/day34.json"),
  pending: () => import("../../mocks/receivables/pending.json"),
  after: () => import("../../mocks/receivables/after.json"),
  settled: () => import("../../mocks/receivables/settled.json"),
  day34_noreceipt: () => import("../../mocks/receivables/day34_noreceipt.json"),
  day34_half: () => import("../../mocks/receivables/day34_half.json"),
  day34_residual: () => import("../../mocks/receivables/day34_residual.json"),
  offer: () => import("../../mocks/receivables/offer.json"),
};
const zh: Record<ReceivablesPoint | "offer", Loader> = {
  day0: () => import("../../mocks/receivables/day0_zh.json"),
  quiet: () => import("../../mocks/receivables/quiet_zh.json"),
  day2: () => import("../../mocks/receivables/day2_zh.json"),
  after_fund: () => import("../../mocks/receivables/after_fund_zh.json"),
  day34: () => import("../../mocks/receivables/day34_zh.json"),
  pending: () => import("../../mocks/receivables/pending_zh.json"),
  after: () => import("../../mocks/receivables/after_zh.json"),
  settled: () => import("../../mocks/receivables/settled_zh.json"),
  day34_noreceipt: () => import("../../mocks/receivables/day34_noreceipt_zh.json"),
  day34_half: () => import("../../mocks/receivables/day34_half_zh.json"),
  day34_residual: () => import("../../mocks/receivables/day34_residual_zh.json"),
  offer: () => import("../../mocks/receivables/offer_zh.json"),
};

export function hook(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function merge(base: unknown, patch: unknown): unknown {
  if (patch && typeof patch === "object" && !Array.isArray(patch) && base && typeof base === "object" && !Array.isArray(base)) {
    const out: Record<string, unknown> = { ...(base as Record<string, unknown>) };
    for (const [k, v] of Object.entries(patch)) out[k] = merge(out[k], v);
    return out;
  }
  return patch;
}

function patched(read: ReceivablesRead): ReceivablesRead {
  if (typeof window === "undefined") return read;
  let raw: string | null = null;
  try {
    raw = window.sessionStorage.getItem(RECEIVABLES_PATCH_KEY);
  } catch {
    /* no storage: no patch */
  }
  if (!raw) return read;
  const patch = JSON.parse(raw) as { partial?: unknown; summary?: unknown; rows?: Record<string, unknown> };
  const out = { ...read } as Record<string, unknown>;
  if (patch.partial !== undefined) out.partial = patch.partial;
  if (patch.summary) out.summary = merge(read.summary, patch.summary);
  if (patch.rows) out.rows = (read.rows ?? []).map((r) => (patch.rows![r.receivable_id] ? merge(r, patch.rows![r.receivable_id]) : r));
  return out as ReceivablesRead;
}

/** GET /receivables for this point of the story. */
export async function mockReceivables(dealt: boolean, lang: "en" | "zh"): Promise<ReceivablesRead | null> {
  if (hook(RECEIVABLES_FAIL_KEY)) throw new ApiError(503, "The receivables are unavailable");
  if (hook(RECEIVABLES_ABSENT_KEY)) return null;
  const point = receivablesPoint(dealt);
  const key = hook(RECEIVABLES_OFFER_KEY) && point === "day0" ? "offer" : point;
  const recorded = (await (lang === "zh" ? zh : en)[key]()).default;
  return patched({ ...clone<ReceivablesRead>(recorded), day: mockClock().day });
}

/**
 * GET /buyers/{id}/exposure: BUYER-1's recording, taken on the opening books and on day 34's; any other buyer has none (null, as the server's 404 reads).
 * The page context the read was asked with is kept in the session (`LAST_EXPOSURE_CONTEXT_KEY`, as JSON) so a spec can see what reached the request; the
 * recording carries no `context.back` (it was taken with no context), so `tl-mock-buyer-exposure` lays one over it: "off" answers null (the feature
 * off), "fail" answers 503, a JSON object is merged deep into the recorded read. A spec that uses it says so: a temporary in-spec patch.
 */
export const BUYER_EXPOSURE_KEY = "tl-mock-buyer-exposure";
export const LAST_EXPOSURE_CONTEXT_KEY = "tl-mock-last-exposure-context";

export async function mockBuyerExposure(buyerId: string, lang: "en" | "zh", news: boolean, context?: ExposureContext): Promise<BuyerExposureView | null> {
  let raw: string | null = null;
  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.setItem(LAST_EXPOSURE_CONTEXT_KEY, JSON.stringify(Object.fromEntries(Object.entries(context ?? {}).filter(([, v]) => v))));
      raw = window.sessionStorage.getItem(BUYER_EXPOSURE_KEY);
    } catch {
      /* no storage: no patch */
    }
  }
  if (raw === "fail") throw new ApiError(503, "The late-payment test is unavailable");
  if (raw === "off" || buyerId !== "BUYER-1") return null;
  const file = news
    ? await (lang === "zh" ? import("../../mocks/buyer_exposure_day34_zh.json") : import("../../mocks/buyer_exposure_day34.json"))
    : await (lang === "zh" ? import("../../mocks/buyer_exposure_zh.json") : import("../../mocks/buyer_exposure.json"));
  const view = clone<BuyerExposureView>(file.default);
  return raw ? (merge(view, JSON.parse(raw)) as BuyerExposureView) : view;
}

/** GET /decisions/{id}/exposure: the recording of the open offer's decision; any other decision names no buyer (404, as the server answers) and the aside shows no result. */
export async function mockDecisionExposure(decisionId: string, lang: "en" | "zh"): Promise<BuyerExposureView | null> {
  const recorded = (await (lang === "zh" ? import("../../mocks/receivables/exposure_offer_zh.json") : import("../../mocks/receivables/exposure_offer.json"))).default as BuyerExposureView;
  if (recorded.decision_id !== decisionId) throw new ApiError(404, `There is no deal decision ${decisionId}, so there is no buyer to show exposure for.`);
  return clone<BuyerExposureView>(recorded);
}
