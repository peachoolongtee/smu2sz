"use client";

import { createStore } from "./create-store";

/**
 * The Business navigation rail. From `lg` it is a 56 px icon rail by default and opens as an overlay (the content does not move) while the pointer is on it or focus is in it;
 * "Keep open" pins it open and lays the page out beside it. The pin is kept in localStorage (`tl-sidebar`, `{ pinned: true }`; createStore reads and writes it inside try/catch, so a
 * browser that refuses storage still pins for the visit). The page is laid out from `<html data-sidebar="pinned">`, which lib/pre-hydration.ts sets before the first paint from the
 * same key, so a pinned rail never flashes collapsed; this store drives the toggle's own state and writes the attribute when the owner presses it. An older `{ collapsed }` value is
 * ignored: the rail is collapsed by default now.
 */
const sidebarStore = createStore<{ pinned: boolean }>({ pinned: false }, { storage: "local", key: "tl-sidebar" });

export function useSidebarPinned(): boolean {
  return sidebarStore.useValue().pinned === true;
}

/** Pin or release the rail, and say so on <html> at once (the layout reads the attribute, not React state). */
export function toggleSidebarPin(): void {
  const next = sidebarStore.get().pinned !== true;
  sidebarStore.set({ pinned: next });
  if (next) document.documentElement.dataset.sidebar = "pinned";
  else delete document.documentElement.dataset.sidebar;
}
