/**
 * Mock for GET /receivables and the buyer exposure behind the Receivables aside: recordings of the real API (scripts/record-mocks.mjs), chosen as the
 * home summary is (`home.receivablesPoint`). Nothing here computes money: every figure and sentence is the recorded string.
 *
 * Test hook, like NO_RECEIPT_KEY: set `tl-mock-receivables-offer` to "1" and, on the opening books, the read is the one taken with the buyer's
 * early-payment message open (its counter would apply to the invoice, so the row carries `pending_counter`). The exposure recording belongs to that
 * offer's decision and is served for it only. `tl-mock-receivables-absent` = "1" makes the route absent (null), as on a server without it.
 */

import { ApiError } from "../errors";
import type { BuyerExposureView, ReceivablesRead } from "../types";
import { mockClock, receivablesPoint, type ReceivablesPoint } from "./home";

export const RECEIVABLES_OFFER_KEY = "tl-mock-receivables-offer";
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

function hook(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

/** GET /receivables for this point of the story. */
export async function mockReceivables(dealt: boolean, lang: "en" | "zh"): Promise<ReceivablesRead | null> {
  if (hook(RECEIVABLES_ABSENT_KEY)) return null;
  const point = receivablesPoint(dealt);
  const key = hook(RECEIVABLES_OFFER_KEY) && point === "day0" ? "offer" : point;
  const recorded = (await (lang === "zh" ? zh : en)[key]()).default;
  return { ...clone<ReceivablesRead>(recorded), day: mockClock().day };
}

/** GET /buyers/{id}/exposure: BUYER-1's recording, taken on the opening books and on day 34's; any other buyer has none (null, as the server's 404 reads). */
export async function mockBuyerExposure(buyerId: string, lang: "en" | "zh", news: boolean): Promise<BuyerExposureView | null> {
  if (buyerId !== "BUYER-1") return null;
  const file = news
    ? await (lang === "zh" ? import("../../mocks/buyer_exposure_day34_zh.json") : import("../../mocks/buyer_exposure_day34.json"))
    : await (lang === "zh" ? import("../../mocks/buyer_exposure_zh.json") : import("../../mocks/buyer_exposure.json"));
  return clone<BuyerExposureView>(file.default);
}

/** GET /decisions/{id}/exposure: the recording of the open offer's decision; any other decision names no buyer (404, as the server answers) and the aside shows no result. */
export async function mockDecisionExposure(decisionId: string, lang: "en" | "zh"): Promise<BuyerExposureView | null> {
  const recorded = (await (lang === "zh" ? import("../../mocks/receivables/exposure_offer_zh.json") : import("../../mocks/receivables/exposure_offer.json"))).default as BuyerExposureView;
  if (recorded.decision_id !== decisionId) throw new ApiError(404, `There is no deal decision ${decisionId}, so there is no buyer to show exposure for.`);
  return clone<BuyerExposureView>(recorded);
}
