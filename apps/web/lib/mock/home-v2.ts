/**
 * Mock for Home V2: GET /home with its `home_v2` block, GET /worklist, GET /customers and the focus reads. Recordings of the real API
 * (`scripts/record-mocks.mjs --home-v2`, `mocks/home_v2/*.json`, { en, zh } each); nothing here computes or edits a figure or a sentence.
 *
 * Always on: Home V2 is the Home. The recording is chosen by the Home's own story (lib/mock/home.ts): the opening books, the opening books with the package offer
 * read, the books after the day-0 plan ran, and (the deal made and the day-2 receipt booked) day 34 with the cure open, queued for approval, and approved. At those six
 * points the Home read is the V2 recording whole. At any other point of the story (a deal made on day 0, day 2, the other receipt books of day 34, the settled day) the older
 * recording stays the read the other pages (Cash, Approvals, Receivables) take their figures from, and the Home takes its `home_v2` block from the nearest recording:
 * day 34's by the cure's stage from day 34 on, else the opening books.
 */

import type { CustomerOverviewView, CustomersView, ExposureView, HomeView, OfferPictureView, WorklistView } from "../types";
import { cureStage, isFunded, isReceipted, mockClock, mockReceiptVariant, NEWS_DAY, SETTLED_DAY } from "./home";

type Point = "day0" | "offer" | "after_fund" | "day34" | "pending" | "after";
type Loader = () => Promise<{ default: unknown }>;
const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

const HOME: Record<Point, Loader> = {
  day0: () => import("../../mocks/home_v2/home_day0.json"),
  offer: () => import("../../mocks/home_v2/home_offer.json"),
  after_fund: () => import("../../mocks/home_v2/home_after_fund.json"),
  day34: () => import("../../mocks/home_v2/home_day34.json"),
  pending: () => import("../../mocks/home_v2/home_pending.json"),
  after: () => import("../../mocks/home_v2/home_after.json"),
};
const WORKLIST: Record<Point, Loader> = {
  day0: () => import("../../mocks/home_v2/worklist_day0.json"),
  offer: () => import("../../mocks/home_v2/worklist_offer.json"),
  after_fund: () => import("../../mocks/home_v2/worklist_after_fund.json"),
  day34: () => import("../../mocks/home_v2/worklist_day34.json"),
  pending: () => import("../../mocks/home_v2/worklist_pending.json"),
  after: () => import("../../mocks/home_v2/worklist_after.json"),
};
const CUSTOMERS: Record<Point, Loader> = {
  day0: () => import("../../mocks/home_v2/customers_day0.json"),
  offer: () => import("../../mocks/home_v2/customers_offer.json"),
  after_fund: () => import("../../mocks/home_v2/customers_after_fund.json"),
  day34: () => import("../../mocks/home_v2/customers_day34.json"),
  pending: () => import("../../mocks/home_v2/customers_pending.json"),
  after: () => import("../../mocks/home_v2/customers_after.json"),
};

/** Where the story stands for the V2 recordings; null where none was taken. `counter`: the package offer is read and no reply sent. */
export function homeV2Recorded(dealt: boolean, counter: boolean): Point | null {
  if (mockClock().day >= NEWS_DAY) {
    // Day 34 was recorded on the main walk (the deal, the day-2 receipt); the other receipt books and the settled day have the older read.
    if (mockReceiptVariant() !== null || mockClock().day >= SETTLED_DAY) return null;
    return stagePoint();
  }
  if (isFunded()) return "after_fund";
  if (isReceipted() || dealt) return null;
  return counter ? "offer" : "day0";
}

/** The cure's stage from day 34 on. */
function stagePoint(): Point {
  const stage = cureStage();
  return stage === "approved" ? "after" : stage === "pending" ? "pending" : "day34";
}

/** The recording the Home takes its V2 block and lists from: the point itself where one was taken, else the nearest (from day 34 the cure's stage; before it, the opening books). */
export function homeV2Point(dealt: boolean, counter: boolean): Point {
  const exact = homeV2Recorded(dealt, counter);
  if (exact) return exact;
  return mockClock().day >= NEWS_DAY ? stagePoint() : counter ? "offer" : "day0";
}

async function pick<T>(table: Record<Point, Loader>, point: Point, lang: "en" | "zh"): Promise<T> {
  const both = (await table[point]()).default as { en: unknown; zh: unknown };
  return clone<T>(lang === "zh" ? both.zh : both.en);
}

/** The V2 recording of GET /home for this point, with the day and the version of the older recording `mockHome` served laid over it. */
export async function mockHomeV2(point: Point, lang: "en" | "zh", base: Pick<HomeView, "day" | "state_version">): Promise<HomeView> {
  const view = await pick<HomeView>(HOME, point, lang);
  return { ...view, day: base.day, state_version: base.state_version };
}

/** Only the `home_v2` block of the recording at this point: the page's block where the older read is what the other pages need. */
export async function mockHomeV2Block(point: Point, lang: "en" | "zh"): Promise<HomeView["home_v2"]> {
  return (await pick<HomeView>(HOME, point, lang)).home_v2;
}

export const mockWorklist = (point: Point, lang: "en" | "zh") => pick<WorklistView>(WORKLIST, point, lang);
export const mockCustomers = (point: Point, lang: "en" | "zh") => pick<CustomersView>(CUSTOMERS, point, lang);

// The focus reads: GET /customers/{id}/overview for each customer at each point, and (with the package offer read) for its deal with each scenario, each carrying the
// context echoes; and the deal's exposure read.
const FOCUS: Record<Point, Loader> = {
  day0: () => import("../../mocks/home_v2/focus_day0.json"),
  offer: () => import("../../mocks/home_v2/focus_offer.json"),
  after_fund: () => import("../../mocks/home_v2/focus_after_fund.json"),
  day34: () => import("../../mocks/home_v2/focus_day34.json"),
  pending: () => import("../../mocks/home_v2/focus_pending.json"),
  after: () => import("../../mocks/home_v2/focus_after.json"),
};
type FocusRec = { customers: Record<string, CustomerOverviewView>; deals: Record<string, CustomerOverviewView> };

/** The overview a customer (or its deal, with the scenario) was recorded with; null for a customer the books do not have (the caller answers 404 as the server does). A deal or scenario that was not recorded answers the customer's own read, whose echoes then say it names nothing. */
export async function mockFocus(point: Point, lang: "en" | "zh", id: string, sel: { decision?: string | null; scenario?: string | null }): Promise<CustomerOverviewView | null> {
  const rec = ((await FOCUS[point]()).default as { en: FocusRec; zh: FocusRec })[lang === "zh" ? "zh" : "en"];
  const base = rec.customers[id];
  if (!base) return null;
  const deal = sel.decision ? (rec.deals[sel.scenario ?? "none"] ?? null) : null;
  return clone<CustomerOverviewView>(deal && deal.customer_id === id && deal.context?.deal === sel.decision ? deal : base);
}

/** GET /offers/{id}/picture as the server answered it (the package offer, read by FLOW): only while that offer is open on the books. */
export async function mockDealPicture(point: Point | null, lang: "en" | "zh"): Promise<OfferPictureView | null> {
  if (point !== "offer") return null;
  const both = (await import("../../mocks/home_v2/picture_offer.json")).default as unknown as { en: OfferPictureView; zh: OfferPictureView };
  return clone<OfferPictureView>(lang === "zh" ? both.zh : both.en);
}

/** The deal chart's title as the server worded it for the package offer's decision (null where it had none). */
export async function mockDealTitle(point: Point | null, lang: "en" | "zh"): Promise<string | null> {
  if (point !== "offer") return null;
  const both = (await import("../../mocks/home_v2/deal_title_offer.json")).default as unknown as { en: string | null; zh: string | null };
  return (lang === "zh" ? both.zh : both.en) ?? null;
}

export async function mockDealExposure(point: Point | null, lang: "en" | "zh"): Promise<ExposureView | null> {
  if (point !== "offer") return null;
  const both = (await import("../../mocks/home_v2/exposure_offer.json")).default as unknown as { en: ExposureView; zh: ExposureView };
  return clone<ExposureView>(lang === "zh" ? both.zh : both.en);
}
