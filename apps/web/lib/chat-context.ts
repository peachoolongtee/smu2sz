"use client";

/**
 * What the owner's page tells Ask FLOW (wayfinder #65, F08): the route, the deal the page evaluated, the invoice row the
 * owner opened, and when they last visited. Ids and a day number only (INVARIANT 13): the server checks every id against its
 * own stores and ignores what it cannot find, so nothing here can name an amount or put a figure in the conversation.
 */

import { demoStore } from "./demo-store";
import type { NlPageContext, NlScope } from "./types";

/** Written by the Home page every time it loads ("the simulated day of the owner's previous visit"). */
const LAST_VISIT_KEY = "tl-last-visit";
/** The marker as it stood when this tab session began: Home overwrites `tl-last-visit` as soon as it loads, so "since my last visit" must be read before that. */
const SESSION_SINCE_KEY = "tl-chat-since";

function asDay(raw: string | null): number | null {
  const n = raw === null || raw === "" ? NaN : Number(raw);
  return Number.isInteger(n) && n >= 0 ? n : null;
}

/** Called when this module loads (the chat is mounted by the root layout, before any page has fetched): remember the last visit once per tab session. */
function captureLastVisit(): number | null {
  if (typeof window === "undefined") return null;
  try {
    const kept = window.sessionStorage.getItem(SESSION_SINCE_KEY);
    if (kept !== null) return asDay(kept);
    const prior = window.localStorage.getItem(LAST_VISIT_KEY);
    window.sessionStorage.setItem(SESSION_SINCE_KEY, prior ?? "");
    return asDay(prior);
  } catch {
    return null;
  }
}

const visitAtOpen = captureLastVisit();

let focusedInvoice: string | null = null;

/** The invoice row the owner has open on Receivables (null when none). Read only when a turn is sent from that page. */
export function focusInvoice(receivableId: string | null): void {
  focusedInvoice = receivableId;
}

/** The route as the API's context accepts it (`^/[A-Za-z0-9/_-]{0,63}$`). */
export function pageOf(pathname: string | null | undefined): string {
  const clean = (pathname ?? "/").replace(/[^A-Za-z0-9/_-]/g, "").slice(0, 64);
  return clean.startsWith("/") ? clean : `/${clean}`;
}

/** The context to send with an owner turn: the page, the evaluated deal the page is on, the open invoice, the last-visit marker. */
export function nlContext(pathname?: string | null): NlPageContext {
  const page = pageOf(pathname ?? (typeof window === "undefined" ? "/" : window.location.pathname));
  const demo = demoStore.get();
  const context: NlPageContext = { page };
  // A deal is named only once the page has its verdict: "Why are we countering this?" is about that verdict.
  if (demo.offerId && demo.verdicts[demo.offerId]) context.offer_id = demo.offerId;
  if (page === "/receivables" && focusedInvoice) context.invoice_id = focusedInvoice;
  if (visitAtOpen !== null) context.since_day = visitAtOpen;
  return context;
}

/**
 * The scope of a question asked on the Home: what its address selects (the URL contract: `customer`, `decision`, `invoice`, `scenario`), ids only. An empty scope is the whole company. Only the Home
 * has this contract (its selection is the address); every other page sends its context as before and no scope.
 */
export function nlScope(pathname?: string | null, search?: string): NlScope | undefined {
  if (typeof window === "undefined") return undefined;
  if (pageOf(pathname ?? window.location.pathname) !== "/") return undefined;
  const q = new URLSearchParams(search ?? window.location.search);
  const scope: NlScope = {};
  for (const key of ["customer", "decision", "invoice", "scenario"] as const) {
    const v = q.get(key);
    if (v) scope[key] = v;
  }
  return scope;
}

/** What the pages hold that decides which questions are worth suggesting: an evaluated deal (and its counters), a recommended plan, an overdue invoice. */
export interface ChatFacts {
  verdict: boolean;
  counters: boolean;
  plan: boolean;
  overdue: boolean;
}

export const NO_FACTS: ChatFacts = { verdict: false, counters: false, plan: false, overdue: false };

/** The deal the page has evaluated, from the session store (Deals writes it when it evaluates). */
export function dealFacts(): Pick<ChatFacts, "verdict" | "counters"> {
  const demo = demoStore.get();
  const verdict = demo.offerId ? demo.verdicts[demo.offerId] : undefined;
  return { verdict: Boolean(verdict), counters: Boolean(verdict && verdict.counters.length > 0) };
}
