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
 * Business routes: the owner's six sections, the limits, and the two tools Cash & funding opens (what-if and buying
 * equipment), so following those doors does not drop the owner into the Demo shell. Everything else is an engine view.
 */
export const BUSINESS_ROUTES = ["/", "/deals", "/cash", "/receivables", "/approvals", "/activity", "/limits", "/whatif", "/capex"] as const;

export function isBusinessRoute(pathname: string): boolean {
  return (BUSINESS_ROUTES as readonly string[]).includes(pathname);
}

/** The engine views and the story page always show the Demo shell; a business route shows it only in Demo mode. */
export function shellFor(pathname: string, mode: Mode): Mode {
  if (pathname === "/chat") return mode;
  return isBusinessRoute(pathname) ? mode : "demo";
}
