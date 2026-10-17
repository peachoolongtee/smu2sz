import type { HomeV2Action, HomeView } from "@/lib/types";

/**
 * Whether the Home shows "You're covered!" (the quiet card's celebration). The decision is the server's (`home_v2.action.covered`, the same
 * rule as `cash.covered`: nothing to fund, the cash under the minimum neither today nor on any day ahead); the page never weighs figures to
 * reach it. An older server or recording carries neither field: then the flags it does carry (no plan to run, no unsafe day, not under the
 * minimum today) decide, as they did before the server said so.
 */
export function homeCovered(h: Pick<HomeView, "next_action" | "cash">, action: Pick<HomeV2Action, "covered">): boolean {
  if (typeof action.covered === "boolean") return action.covered;
  if (typeof h.cash.covered === "boolean") return h.cash.covered;
  return !h.next_action && h.cash.first_breach_day == null && !h.cash.below_reserve_today;
}
