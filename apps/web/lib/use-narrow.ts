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

const WIDE = "(min-width: 64rem)";

function subscribeWide(onChange: () => void): () => void {
  const list = window.matchMedia(WIDE);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
}

/**
 * True on a desktop width (1024 px and up) once the page is in the browser; false while rendering on the server and during hydration, so a part that only a desktop has (the header's Ask FLOW input) is
 * never in the server's HTML, where it would overflow a phone's first paint until hydration removed it.
 */
export function useWide(): boolean {
  return useSyncExternalStore(
    subscribeWide,
    () => window.matchMedia(WIDE).matches,
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
