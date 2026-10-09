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

/** A short window (a 768 px laptop, a phone on its side): the answer must reach the first screen without the stat tiles. */
const SHORT = "(max-height: 800px)";

function subscribeShort(onChange: () => void): () => void {
  const list = window.matchMedia(SHORT);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
}

/** True when the window is at most 800 px tall (false while rendering on the server). Like `useNarrow`, it only changes what is folded, never what is said. */
export function useShort(): boolean {
  return useSyncExternalStore(
    subscribeShort,
    () => window.matchMedia(SHORT).matches,
    () => false,
  );
}
