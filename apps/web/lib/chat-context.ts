"use client";

/**
 * What the owner's page tells Ask FLOW: the route and when they last visited. Ids and a day number only (INVARIANT 13): the server checks every id against its
 * own stores and ignores what it cannot find, so nothing here can name an amount or put a figure in the conversation. What the question is about is the scope (lib/chat-scope.ts).
 */

import type { NlPageContext } from "./types";

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

/** The route as the API's context accepts it (`^/[A-Za-z0-9/_-]{0,63}$`). */
export function pageOf(pathname: string | null | undefined): string {
  const clean = (pathname ?? "/").replace(/[^A-Za-z0-9/_-]/g, "").slice(0, 64);
  return clean.startsWith("/") ? clean : `/${clean}`;
}

/**
 * The context to send with an owner turn: the page and the last-visit marker, and nothing about a deal or an invoice. What the question is about travels as the request's `scope`
 * (lib/chat-scope.ts), chosen before it is asked; the old global "the offer this tab evaluated last" is gone (audit UX01, UX20). `legacy` is the same scope in the two ids today's
 * server reads, derived from it and nothing else.
 */
export function nlContext(pathname?: string | null, legacy: { offer_id?: string; invoice_id?: string } = {}): NlPageContext {
  const page = pageOf(pathname ?? (typeof window === "undefined" ? "/" : window.location.pathname));
  const context: NlPageContext = { page, ...legacy };
  if (visitAtOpen !== null) context.since_day = visitAtOpen;
  return context;
}

/**
 * What the pages hold that decides which questions are worth suggesting: an evaluated deal (and its counters), a recommended plan, an overdue invoice. The deal facts come from the
 * decision record of the scope's own decision (a server read, lib/use-chat-facts.ts), never from what this tab evaluated.
 */
export interface ChatFacts {
  verdict: boolean;
  counters: boolean;
  plan: boolean;
  overdue: boolean;
}

export const NO_FACTS: ChatFacts = { verdict: false, counters: false, plan: false, overdue: false };
