"use client";

import { usePathname } from "next/navigation";
import { getClock } from "./api";
import { shellFor, useMode } from "./mode";
import { useAsync } from "./use-async";

/** Whether the current page shows the Business shell (a business route in Business mode); the engine views are always Demo. */
export function useBusinessShell(): boolean {
  const pathname = usePathname();
  return shellFor(pathname ?? "/", useMode()) === "business";
}

/**
 * For a shared card (plan, violation, counter) that says days as "Day N" in the Demo views and as distances from today on
 * the Business pages: whether this is a Business page and, if so, today. The page may pass `today` (its own clock read);
 * otherwise the simulated clock is read once here, only on a Business page. `today` is null in Demo and until the clock
 * has loaded; the card then keeps the day number.
 */
export function useBusinessToday(today?: number): { business: boolean; today: number | null } {
  const business = useBusinessShell();
  const needsClock = business && today === undefined;
  const clock = useAsync(() => (needsClock ? getClock() : Promise.resolve(null)), [needsClock]);
  return { business, today: business ? (today ?? clock.data?.day ?? null) : null };
}
