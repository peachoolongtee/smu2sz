import type { LateRead } from "@/components/home/event-picture";
import type { ExposureContext } from "./api";
import type { useI18n } from "./i18n";
import type { BuyerExposureView, ReceivableRow } from "./types";

/** The address the Receivables page, the Customer page and the Deals queue open Cash with: `?stress=<buyer>:30` and the shared context beside it. */
export interface StressLink {
  buyerId: string;
  /** The delay the link names, in days (the server's read says the delay it tested; this only keeps the link whole). */
  days: number | null;
}

/** `BUYER-1:30` is the buyer and the delay. A buyer id with no delay (`BUYER-1`) is the buyer alone; nothing else (an empty value) is no link. */
export function parseStress(raw: string | null): StressLink | null {
  const value = raw?.trim();
  if (!value) return null;
  const at = value.lastIndexOf(":");
  if (at > 0 && /^[0-9]{1,3}$/.test(value.slice(at + 1))) return { buyerId: value.slice(0, at), days: Number(value.slice(at + 1)) };
  return { buyerId: value, days: null };
}

/** The origin a stress link names (`from`): only the three the server knows are passed on; anything else is the link without one. */
export const originOf = (v: string | null): ExposureContext["from"] => (v === "deal" || v === "invoice" || v === "customer" ? v : null);

/** The windows the picture offers beyond its own; the late path is shown in the shortest that holds its lowest point and a week after it. */
const WINDOWS = [60, 120] as const;

type T = ReturnType<typeof useI18n>["t"];

/**
 * The picture's late-payment scenario from the buyer's exposure read: its series, the delay, the server's assumption and the stress sentence (the server's
 * `text` and `funding_text`: the lowest point and when, the days under the minimum, what no facility covers and the plan), then what the buyer's open invoices leave a
 * month later and the invoice's financing charges when it has them. Every word is the server's or the dictionary's; the day numbers only size the window.
 * Null when the read has no test to draw (unavailable, or no series).
 */
export function lateReadOf(view: BuyerExposureView, row: ReceivableRow | null | undefined, t: T): LateRead | null {
  const now = view.stress?.now;
  if (!now || now.available === false || !now.series?.length || !now.lowest_short || !now.lowest_when) return null;
  const buyer = view.buyer_short ?? view.concentration?.buyer_name ?? view.buyer_name ?? "";
  // The stress sentence is the server's two: `text` (the lowest point and when, the days under the minimum, what no facility covers) and `funding_text` (the plan).
  const sentence = [now.text, now.funding_text].filter(Boolean).join(" ");
  const span = Math.max((now.lowest_day ?? 0) - (view.day ?? 0), 0) + 7;
  const lines = [now.net_later_text ? t("cash.stress.later", { net: now.net_later_text }) : "", row?.net?.per_period_text ? t("cash.stress.charges", { text: row.net.per_period_text }) : ""].filter(Boolean);
  return {
    startLate: true,
    sentence,
    lines,
    stress: {
      delay_days: view.stress?.delay_days ?? now.delay_days,
      buyer,
      buyer_id: view.buyer_id,
      series: now.series.map((p) => ({ ...p, events: [] })),
      lowest_short: now.lowest_short,
      lowest_when: now.lowest_when,
      breach_days: now.breach_days ?? 0,
      assumption_text: now.assumption ?? "",
      window_days_needed: WINDOWS.find((w) => w >= span) ?? WINDOWS[WINDOWS.length - 1],
    },
  };
}
