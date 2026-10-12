/**
 * Mock for Home V2 (wave 2): GET /home with its `home_v2` block, GET /worklist, GET /customers and GET /health's switch. Recordings of the real API taken with
 * FEATURE_HOME_V2=1 (`scripts/record-mocks.mjs --home-v2`, `mocks/home_v2/*.json`, { en, zh } each); nothing here computes or edits a figure or a sentence.
 *
 * Test hook, like the other `tl-mock-*` keys: set the session key `tl-mock-home-v2` to "1" and the mock is a server with FEATURE_HOME_V2 on (the switch answers true,
 * the Home read carries `home_v2`, the two lists answer). Unset, the switch is off, the lists are absent (null) and the Home is the older recording, untouched.
 * The recording is chosen by the Home's own story (lib/mock/home.ts): the opening books, the opening books with the package offer read, or the books after the day-0
 * plan ran. At any other point of the story (a deal made, day 2, day 34 and later) there is no V2 recording, and the Home is the older one.
 */

import type { CustomersView, FeaturesView, HomeView, WorklistView } from "../types";
import { isFunded, isReceipted, mockClock, NEWS_DAY } from "./home";

export const HOME_V2_KEY = "tl-mock-home-v2";

type Point = "day0" | "offer" | "after_fund";
type Loader = () => Promise<{ default: unknown }>;
const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

const HOME: Record<Point, Loader> = {
  day0: () => import("../../mocks/home_v2/home_day0.json"),
  offer: () => import("../../mocks/home_v2/home_offer.json"),
  after_fund: () => import("../../mocks/home_v2/home_after_fund.json"),
};
const WORKLIST: Record<Point, Loader> = {
  day0: () => import("../../mocks/home_v2/worklist_day0.json"),
  offer: () => import("../../mocks/home_v2/worklist_offer.json"),
  after_fund: () => import("../../mocks/home_v2/worklist_after_fund.json"),
};
const CUSTOMERS: Record<Point, Loader> = {
  day0: () => import("../../mocks/home_v2/customers_day0.json"),
  offer: () => import("../../mocks/home_v2/customers_offer.json"),
  after_fund: () => import("../../mocks/home_v2/customers_after_fund.json"),
};

/** True while the session key is set: the mock plays a server that has Home V2 on. */
export function homeV2On(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(HOME_V2_KEY) === "1";
  } catch {
    return false;
  }
}

/** Where the story stands for the V2 recordings; null where none was taken (the older Home is then served). `counter`: the package offer is read and no reply sent. */
export function homeV2Point(dealt: boolean, counter: boolean): Point | null {
  if (mockClock().day >= NEWS_DAY) return null;
  if (isFunded()) return "after_fund";
  if (isReceipted() || dealt) return null;
  return counter ? "offer" : "day0";
}

export function mockFeatures(): FeaturesView {
  return { home_v2: homeV2On() };
}

async function pick<T>(table: Record<Point, Loader>, point: Point | null, lang: "en" | "zh"): Promise<T | null> {
  if (!homeV2On() || point === null) return null;
  const both = (await table[point]()).default as { en: unknown; zh: unknown };
  return clone<T>(lang === "zh" ? both.zh : both.en);
}

/** The V2 recording of GET /home for this point of the story, with the day and the version of the older recording `mockHome` served laid over it; null when there is none. */
export async function mockHomeV2(point: Point | null, lang: "en" | "zh", base: Pick<HomeView, "day" | "state_version">): Promise<HomeView | null> {
  const view = await pick<HomeView>(HOME, point, lang);
  return view ? { ...view, day: base.day, state_version: base.state_version } : null;
}

export const mockWorklist = (point: Point | null, lang: "en" | "zh") => pick<WorklistView>(WORKLIST, point, lang);
export const mockCustomers = (point: Point | null, lang: "en" | "zh") => pick<CustomersView>(CUSTOMERS, point, lang);
