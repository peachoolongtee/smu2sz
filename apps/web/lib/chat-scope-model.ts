"use client";

/**
 * Ask FLOW's scope (ticket #130): what a question is about, shown before it is asked and sent with it. The scope comes from the address (`customer`, `decision`, `invoice`,
 * `scenario`, read for the route the owner is on) and from nothing else: no session store, no earlier conversation. A page whose selection is not in its address (a default
 * row) registers it with `usePageScope`, which goes with the page. The owner may narrow the question to a wider kind (Company, Customer, Invoice, Decision); that choice belongs
 * to the route and is gone when the route changes. The server validates every key and says what it used (`scope_used`).
 */

import { createStore } from "./create-store";
import { scopeOf, serverScenario, type ChatScope, type ScopeKind } from "./selection";
import type { NlScope } from "./types";

/** The narrowest to the widest kind, the order the chip lists them in. */
export const SCOPE_KINDS: ScopeKind[] = ["decision", "invoice", "customer", "company"];

interface Chosen {
  /** The route and selection the choice was made on; any other route or selection makes it void. */
  route: string;
  kind: ScopeKind | null;
}
export const chosenStore = createStore<Chosen>({ route: "", kind: null });

/** What a page registered as its own selection, for the route it registered on (cleared when the page unmounts). */
interface Registered {
  route: string;
  scope: ChatScope | null;
}
export const pageStore = createStore<Registered>({ route: "", scope: null });

type Params = { get(name: string): string | null; toString(): string };

/** The route a scope belongs to: the path and the selection keys of the address (the keys that name something), nothing else (a tab or a chart toggle is not a new route). */
export function routeOf(pathname: string, params: Params | null | undefined): string {
  const keys = ["customer", "decision", "invoice", "scenario"].map((k) => `${k}=${params?.get(k) ?? ""}`).join("&");
  return `${pathname}?${keys}`;
}

/** The customer a `/customers/{id}` path names. */
export function customerOfPath(pathname: string): string | null {
  const m = /^\/customers\/([^/]+)/.exec(pathname);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return m[1];
  }
}

/** The kinds a scope can be asked at (the narrowest first), and the scope that goes with each. A kind is offered only when the address holds what it needs. */
export function scopeChoices(base: ChatScope): { kind: ScopeKind; scope: ChatScope }[] {
  const out: { kind: ScopeKind; scope: ChatScope }[] = [];
  if (base.decision) out.push({ kind: "decision", scope: { kind: "decision", customer: base.customer, decision: base.decision, scenario: base.scenario } });
  if (base.invoice) out.push({ kind: "invoice", scope: { kind: "invoice", customer: base.customer, invoice: base.invoice } });
  if (base.customer) out.push({ kind: "customer", scope: { kind: "customer", customer: base.customer } });
  out.push({ kind: "company", scope: { kind: "company" } });
  return out;
}

/** The scope in force for a route: the page's registration over the address, then the owner's narrowing if it is for this route. */
export function resolveScope(pathname: string, params: Params | null | undefined): { choices: { kind: ScopeKind; scope: ChatScope }[]; chosen: ChatScope } {
  const route = routeOf(pathname, params);
  const fromAddress = scopeOf(pathname, params, customerOfPath(pathname));
  const reg = pageStore.get();
  const base: ChatScope = reg.route === pathname && reg.scope ? { ...fromAddress, ...reg.scope, kind: reg.scope.kind } : fromAddress;
  const choices = scopeChoices(base);
  const picked = chosenStore.get();
  const chosen = (picked.route === route && picked.kind ? choices.find((c) => c.kind === picked.kind) : null) ?? choices[0];
  return { choices, chosen: chosen.scope };
}

/** The scope as the request carries it: only the keys that are set (the server checks each). */
export function toNlScope(scope: ChatScope): NlScope | undefined {
  const out: NlScope = {};
  if (scope.customer) out.customer = scope.customer;
  if (scope.invoice) out.invoice = scope.invoice;
  if (scope.decision) out.decision = scope.decision;
  const scenario = serverScenario(scope.scenario);
  if (scenario) out.scenario = scenario;
  return Object.keys(out).length ? out : undefined;
}

/** The scope at the moment of a send, from the address the browser holds now (the same one the chip shows). Company when there is no browser. */
export function currentScope(): ChatScope {
  if (typeof window === "undefined") return { kind: "company" };
  return resolveScope(window.location.pathname, new URLSearchParams(window.location.search)).chosen;
}

