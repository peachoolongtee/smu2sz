"use client";

import { demoReset, getDemoStory, type BooksGuard } from "./api";
import { createStore } from "./create-store";
import { bump, resetSession } from "./demo-store";
import { ApiError } from "./errors";
import { getLang } from "./i18n";
import type { DemoStoryView } from "./types";

/**
 * The main books are never replaced or reset silently. Every control that resets, restores or replaces the books goes through `changeBooks`: it names the scenario of the story
 * read the page is showing (`from_scenario`), opens the confirmation dialog first when that read says something would be lost (with the list from a FRESH read), and the dialog's
 * confirm sends the token of the list it is showing (`confirm_loss=<token>`), and nothing else does. A server that refuses the confirmation (LOSS_NOT_CONFIRMED, LOSS_CHANGED: the
 * books moved since the list was shown) keeps the dialog open with the list and token it returned and its own sentence, and needs a new click. One that says BOOKS_CHANGED (the page
 * was stale) has reset nothing: its sentence is shown and the story is read again.
 */
export type Books = DemoStoryView["books"];

export interface DialogOptions {
  /** Words for a control whose dialog is not the plain reset's (restoring the main books, loading the alternate books). */
  labels?: { title: string; confirm: string; cancel: string; keeps: string };
  /** Open the dialog even when the read says nothing would be lost (the alternate books always say what they are). */
  always?: boolean;
  /** Take the list and token from the story's `alternate` block, not its `books` block. */
  alternate?: boolean;
  /** The heading and sentence of what the dialog's action gives (the alternate books' scope). */
  gives?: { heading: string; text: string };
  /** The prefix of the dialog's test ids. */
  prefix?: "books-dialog" | "demo-alternate";
}

export interface Pending {
  books: Books;
  items: string[];
  lossTitle: string;
  token: string | null;
  /** The server's sentence for a list that changed under the dialog. */
  note: string | null;
  perform: (guard: BooksGuard) => Promise<unknown>;
  options: DialogOptions;
}

export const guardStore = createStore<{ pending: Pending | null; notice: string | null }>({ pending: null, notice: null });

interface GuardDetail {
  code: string;
  message_when?: string;
  message?: string;
  loss_items?: string[];
  loss_token?: string;
}

function guardDetail(e: unknown): GuardDetail | null {
  if (!(e instanceof ApiError) || e.status !== 409) return null;
  const d = e.detail as GuardDetail | undefined;
  return d && (d.code === "LOSS_NOT_CONFIRMED" || d.code === "LOSS_CHANGED" || d.code === "BOOKS_CHANGED") ? d : null;
}

/** Whether `e` is one of the refusals of the stale-page guard (a runner rethrows these instead of showing them as its own error). */
export const isGuardError = (e: unknown): boolean => guardDetail(e) !== null;

/**
 * Runs `perform` with the guard of this read. When something would be lost (or the control always says what it does) the dialog opens first, with the list of a fresh story read;
 * nothing is sent until its confirm button is clicked. The caller's busy state is its own.
 */
export async function changeBooks(books: Books, perform: Pending["perform"], options: DialogOptions = {}): Promise<void> {
  if (books.nothing_to_lose && !options.always) {
    await attempt(books, perform, null, options, books.loss_title_text);
    return;
  }
  // The list on the dialog is the books' as they stand now, not as the page last read them.
  let items = options.alternate ? [] : books.loss_items;
  let token: string | null = books.loss_token ?? null;
  let title = books.loss_title_text;
  let fresh: DemoStoryView | null = null;
  try {
    fresh = await getDemoStory(getLang(), null);
  } catch {
    fresh = null;
  }
  if (fresh) {
    const block = options.alternate ? fresh.alternate : fresh.books;
    items = block.loss_items;
    token = block.loss_token ?? null;
    title = options.alternate ? fresh.alternate.loss_title_text : fresh.books.loss_title_text;
  } else if (options.alternate) {
    items = [];
  }
  guardStore.set({ pending: { books, items, lossTitle: title, token, note: null, perform, options }, notice: null });
}

async function attempt(books: Books, perform: Pending["perform"], token: string | null, options: DialogOptions, lossTitle: string): Promise<void> {
  try {
    await perform(token ? { from: books.scenario, confirm: token } : { from: books.scenario });
    guardStore.set({ pending: null, notice: null });
  } catch (e) {
    const g = guardDetail(e);
    if (!g) {
      guardStore.set((s) => ({ ...s, pending: null }));
      throw e;
    }
    if (g.code === "BOOKS_CHANGED") {
      // The page was stale: nothing was reset. Say so in the server's words and read the story again.
      guardStore.set({ pending: null, notice: g.message_when ?? g.message ?? null });
      bump();
      return;
    }
    // The list the dialog showed is not the books' list any more: the dialog stays, with the server's list, its token and its sentence, and needs a new click.
    guardStore.set({
      pending: { books, items: g.loss_items ?? [], lossTitle, token: g.loss_token ?? null, note: g.message_when ?? g.message ?? null, perform, options },
      notice: null,
    });
  }
}

/** The dialog's confirm button, and nothing else, sends the confirmation: the token of the list the dialog is showing. */
export async function confirmPending(): Promise<void> {
  const p = guardStore.get().pending;
  if (p) await attempt(p.books, p.perform, p.token, p.options, p.lossTitle);
}

export function cancelPending(): void {
  guardStore.set((s) => ({ ...s, pending: null }));
}

export function clearNotice(): void {
  guardStore.set((s) => ({ ...s, notice: null }));
}

/** Reset the books to a scenario (the main books by default), then start the session over and open `route` (the Demo page by default; the setup for blank books). */
export const resetTo = (scenario: string | undefined, push: (route: string) => void, route = "/demo") => async (guard: BooksGuard) => {
  await demoReset(scenario, guard);
  resetSession();
  push(route);
};

/** The scenario a "reset these books" goes to: the owner's own books are not a scenario the server can reset to, so resetting them starts blank books. */
export const resetScenarioOf = (books: Books): string | undefined => (books.main ? undefined : books.scenario === "own" ? "blank" : books.scenario);
