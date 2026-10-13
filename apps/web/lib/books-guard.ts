"use client";

import { demoReset, type BooksGuard } from "./api";
import { createStore } from "./create-store";
import { bump, resetSession } from "./demo-store";
import { ApiError } from "./errors";
import type { DemoStoryView } from "./types";

/**
 * The main books are never replaced or reset silently. Every control that resets, restores or replaces the books goes through `changeBooks`: it names the scenario of the story
 * read the page is showing (`from_scenario`), opens the confirmation dialog first when that read says something would be lost, and sends `confirm_loss=1` only from that dialog's
 * confirm button (`confirmPending`). A server that says LOSS_NOT_CONFIRMED anyway opens the dialog with the list it returned; one that says BOOKS_CHANGED (the page was stale) has
 * reset nothing: its sentence is shown and the story is read again.
 */
export type Books = DemoStoryView["books"];

export interface Pending {
  books: Books;
  items: string[];
  perform: (guard: BooksGuard) => Promise<unknown>;
  /** Words for a control whose dialog is not the plain reset's (restoring the main books). */
  labels?: { title: string; confirm: string; cancel: string; keeps: string };
}

export const guardStore = createStore<{ pending: Pending | null; notice: string | null }>({ pending: null, notice: null });

interface GuardDetail {
  code: string;
  message_when?: string;
  message?: string;
  loss_items?: string[];
}

function guardDetail(e: unknown): GuardDetail | null {
  if (!(e instanceof ApiError) || e.status !== 409) return null;
  const d = e.detail as GuardDetail | undefined;
  return d && (d.code === "LOSS_NOT_CONFIRMED" || d.code === "BOOKS_CHANGED") ? d : null;
}

/** Whether `e` is one of the two refusals of the stale-page guard (a runner rethrows these instead of showing them as its own error). */
export const isGuardError = (e: unknown): boolean => guardDetail(e) !== null;

/** Runs `perform` with the guard of this read; the dialog first when something would be lost. The caller's busy state is its own. */
export async function changeBooks(books: Books, perform: Pending["perform"], labels?: Pending["labels"]): Promise<void> {
  if (!books.nothing_to_lose) {
    guardStore.set({ pending: { books, items: books.loss_items, perform, labels }, notice: null });
    return;
  }
  await attempt(books, perform, false, labels);
}

/** The confirm button of a dialog that already listed what is lost (the alternate books' own), and nothing else, calls this: it sends `confirm_loss=1`. */
export async function changeBooksConfirmed(books: Books, perform: Pending["perform"]): Promise<void> {
  await attempt(books, perform, true);
}

async function attempt(books: Books, perform: Pending["perform"], confirm: boolean, labels?: Pending["labels"]): Promise<void> {
  try {
    await perform({ from: books.scenario, confirm });
    guardStore.set({ pending: null, notice: null });
  } catch (e) {
    const g = guardDetail(e);
    if (!g) {
      guardStore.set((s) => ({ ...s, pending: null }));
      throw e;
    }
    if (g.code === "LOSS_NOT_CONFIRMED") guardStore.set({ pending: { books, items: g.loss_items ?? books.loss_items, perform, labels }, notice: null });
    else {
      // The page was stale: nothing was reset. Say so in the server's words and read the story again.
      guardStore.set({ pending: null, notice: g.message_when ?? g.message ?? null });
      bump();
    }
  }
}

/** The dialog's confirm button, and nothing else, sends `confirm_loss=1`. */
export async function confirmPending(): Promise<void> {
  const p = guardStore.get().pending;
  if (p) await attempt(p.books, p.perform, true, p.labels);
}

export function cancelPending(): void {
  guardStore.set((s) => ({ ...s, pending: null }));
}

export function clearNotice(): void {
  guardStore.set((s) => ({ ...s, notice: null }));
}

/** Reset the books to a scenario (the main books by default), then start the session over. */
export const resetTo = (scenario: string | undefined, push: (route: string) => void) => async (guard: BooksGuard) => {
  await demoReset(scenario, guard);
  resetSession();
  push("/demo");
};
