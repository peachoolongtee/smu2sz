"use client";

import { createStore } from "./create-store";

/**
 * Whether the Business sidebar is collapsed to its icons. It only matters on a laptop (1024 to 1366 px: globals.css `laptop`); a wider screen always shows the
 * full sidebar. Kept in localStorage (`tl-sidebar`; createStore reads and writes it inside try/catch, so a browser that refuses storage still collapses for the
 * visit). The page is laid out from `<html data-sidebar="collapsed">`, which lib/pre-hydration.ts sets before the first paint from the same key, so a collapsed
 * sidebar never flashes open; this store only drives the toggle's own state and writes the attribute when the owner presses it.
 */
const sidebarStore = createStore<{ collapsed: boolean }>({ collapsed: false }, { storage: "local", key: "tl-sidebar" });

export function useSidebarCollapsed(): boolean {
  return sidebarStore.useValue().collapsed;
}

/** Flip the sidebar, and say so on <html> at once (the layout reads the attribute, not React state). */
export function toggleSidebar(): void {
  const next = !sidebarStore.get().collapsed;
  sidebarStore.set({ collapsed: next });
  document.documentElement.dataset.sidebar = next ? "collapsed" : "open";
}
