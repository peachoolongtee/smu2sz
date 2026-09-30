"use client";

import { createStore } from "./create-store";
import type { BorrowerFileView, CapexView, NegotiationView, OfferView, VerdictView } from "./types";

/**
 * Client-side session for the guided demo: which step we are on, which offer is "current", and the
 * responses the API already gave us (so screens do not re-trigger server side effects).
 */
export interface DemoState {
  /** -1 until the stepper has started. */
  step: number;
  offerId: string | null;
  offers: Record<string, OfferView>;
  verdicts: Record<string, VerdictView>;
  negotiations: Record<string, NegotiationView>;
  capex: CapexView | null;
  borrowerFile: BorrowerFileView | null;
  /** Bumped after every write so read hooks refetch. */
  version: number;
  busy: boolean;
  error: string | null;
}

export const INITIAL_DEMO: DemoState = {
  step: -1,
  offerId: null,
  offers: {},
  verdicts: {},
  negotiations: {},
  capex: null,
  borrowerFile: null,
  version: 0,
  busy: false,
  error: null,
};

export const demoStore = createStore<DemoState>(INITIAL_DEMO, {
  storage: "session",
  key: "tl-demo-v1",
  sanitize: (s) => ({ ...s, busy: false, error: null }),
});

export function useDemo(): DemoState {
  return demoStore.useValue();
}

export function bump(): void {
  demoStore.set((s) => ({ ...s, version: s.version + 1 }));
}

export function recordOffer(offer: OfferView): void {
  demoStore.set((s) => ({
    ...s,
    offerId: offer.offer.offer_id,
    offers: { ...s.offers, [offer.offer.offer_id]: offer },
    version: s.version + 1,
  }));
}

export function recordVerdict(verdict: VerdictView): void {
  demoStore.set((s) => ({ ...s, verdicts: { ...s.verdicts, [verdict.offer_id]: verdict }, version: s.version + 1 }));
}

export function recordNegotiation(n: NegotiationView): void {
  demoStore.set((s) => ({ ...s, negotiations: { ...s.negotiations, [n.offer_id]: n }, version: s.version + 1 }));
}

export function recordCapex(capex: CapexView): void {
  demoStore.set((s) => ({ ...s, capex, version: s.version + 1 }));
}

export function recordBorrowerFile(borrowerFile: BorrowerFileView): void {
  demoStore.set((s) => ({ ...s, borrowerFile, version: s.version + 1 }));
}

export function clearDemo(): void {
  demoStore.set((s) => ({ ...INITIAL_DEMO, version: s.version + 1 }));
}
