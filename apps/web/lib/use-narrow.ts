"use client";

import { useSyncExternalStore } from "react";

/** The width below which the layout is one column (Tailwind's `max-lg`, the same 1024 px as the `touch:` variant's width rule). */
const NARROW = "(max-width: 63.999rem)";

function subscribe(onChange: () => void): () => void {
  const list = window.matchMedia(NARROW);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
}

/**
 * True on a narrow screen (a phone or a small tablet), false on a desktop and while rendering on the server. A page uses it to put the
 * parts in the order a phone owner reads them, rather than the desktop's: the DOM order itself changes, so the focus order and the reading
 * order follow what is on screen. It never decides what is shown, only the order; every part keeps its key so its state survives a resize.
 */
export function useNarrow(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(NARROW).matches,
    () => false,
  );
}
