"use client";

/**
 * "The books were replaced" (a demo reset, the story's restore, Set up your books), said to every tab of this browser. The server forgets
 * every Ask FLOW session when its books are replaced (Runtime.clear_session_caches); this tells the chat to forget its side too: the
 * transcript, the session id and the draft (lib/chat.ts). It is a marker in localStorage (`tl-books-epoch`), so a tab that was open, or
 * reloaded, after another tab reset the books sees it too: the `storage` event for an open tab, a comparison on load for a reloaded one.
 * It holds no figure and no id, only an opaque value that changes with each replacement.
 */

const KEY = "tl-books-epoch";
const listeners = new Set<() => void>();

/** The current marker, or null when this browser has not seen the books replaced. */
export function booksEpoch(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** Called after the server confirmed a replacement of the books: the chat in this tab and in every other tab starts over. */
export function markBooksReplaced(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`);
  } catch {
    /* storage unavailable: this tab still hears it below */
  }
  listeners.forEach((l) => l());
}

/** Runs `l` whenever the books are replaced, from this tab or another one. */
export function onBooksReplaced(l: () => void): () => void {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key === KEY) listeners.forEach((l) => l());
  });
}
