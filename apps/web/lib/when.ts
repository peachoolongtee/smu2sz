import type { I18n } from "./i18n";

/**
 * A simulated day as a distance from today, for the Business pages ("in 12 days", "today", "3 days ago"). Counting
 * days is the one arithmetic the browser may do (INVARIANT 13 is about money); the Demo views keep "Day N". Where the
 * server already sends a `*_when` string, prefer it.
 */
export function whenText(day: number | null | undefined, today: number, t: I18n["t"]): string {
  if (day === null || day === undefined) return "";
  const n = day - today;
  if (n === 0) return t("biz.when.today");
  if (n === 1) return t("biz.when.tomorrow");
  if (n === -1) return t("biz.when.yesterday");
  return n > 0 ? t("biz.when.inDays", { n }) : t("biz.when.daysAgo", { n: -n });
}

/** "1 day late" / "2 days late": the badge on a late invoice, with its plural. */
export function daysLate(days: number, t: I18n["t"]): string {
  return t(days === 1 ? "biz.recv.late.one" : "biz.recv.late", { days });
}
