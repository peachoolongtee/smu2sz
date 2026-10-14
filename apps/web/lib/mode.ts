"use client";

import { createStore } from "./create-store";

/**
 * The two shells. Business is the product the owner uses: no demo controls, navigation by business question. Demo is
 * for judges: the guided story, the clock, the scenes and the engine views. The choice is remembered per browser.
 */
export type Mode = "business" | "demo";

const modeStore = createStore<{ mode: Mode }>({ mode: "business" }, { storage: "local", key: "tl-mode" });

export function useMode(): Mode {
  return modeStore.useValue().mode;
}

export function getMode(): Mode {
  return modeStore.get().mode;
}

export function setMode(mode: Mode): void {
  modeStore.set({ mode });
}

/**
 * Owner detail routes: pages the owner opens from a section and returns to (Cash opens what-if and equipment; a deal summary
 * on Deals opens the contract documents). They render in the Business shell when the mode is Business, with a way back to
 * the section.
 */
export const OWNER_DETAIL_ROUTES: Record<string, string> = { "/whatif": "/cash", "/capex": "/cash" };

/** Business routes: the owner's six sections (Documents among them), the limits and sign-in, and the detail routes opened from them. Everything else is an engine view of the demo. */
export const BUSINESS_ROUTES = ["/", "/deals", "/documents", "/cash", "/receivables", "/approvals", "/activity", "/limits", "/trust", ...Object.keys(OWNER_DETAIL_ROUTES)] as const;

/** A decision's record (`/decisions/{id}`) is an owner page opened from Home, Activity or an approval; it has no section of its own. */
export const DECISION_ROUTE_PREFIX = "/decisions/";

/** A customer's overview (`/customers/{id}`) is an owner page opened from a customer's name on Deals, Receivables, Cash and Activity; like a record it has no section of its own. */
export const CUSTOMER_ROUTE_PREFIX = "/customers/";

export function isBusinessRoute(pathname: string): boolean {
  return (BUSINESS_ROUTES as readonly string[]).includes(pathname) || pathname.startsWith(DECISION_ROUTE_PREFIX) || pathname.startsWith(CUSTOMER_ROUTE_PREFIX);
}

/** The engine views and the story page always show the Demo shell; a business route shows it only in Demo mode. */
export function shellFor(pathname: string, mode: Mode): Mode {
  if (pathname === "/chat") return mode;
  return isBusinessRoute(pathname) ? mode : "demo";
}
