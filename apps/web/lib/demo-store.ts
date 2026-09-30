"use client";

import { createStore } from "./create-store";
import type { BorrowerFileView, CapexView, FundingView, NegotiationView, OfferView, VerdictView } from "./types";

/**
 * Client-side session for the guided demo: which step we are on, which offer is "current", and the
 * responses the API already gave us (so screens do not re-trigger server side effects).
 */
export interface DemoState {
  /** -1 until the stepper has started. */
  step: number;
  offerId: string | null;
  offers: Record<string, OfferView>;
  /** offer_id -> server fixture id, for offers compiled from a demo fixture (evaluate passes it back). */
  fixtures: Record<string, string>;
  verdicts: Record<string, VerdictView>;
  negotiations: Record<string, NegotiationView>;
  capex: CapexView | null;
  borrowerFile: BorrowerFileView | null;
  /**
   * The Debt Desk view as it stood when the decision was made. Executing a plan changes the books, so
   * a live re-plan afterwards would show "no funding needed"; the Funding screen shows this snapshot instead.
   */
  funding: FundingView | null;
  /** The reworded offer (EX01B), evaluated on the same books as EX01 before any operation executes. */
  rewordedId: string | null;
  /** Bumped after every write so read hooks refetch. */
  version: number;
  busy: boolean;
  error: string | null;
}

export const INITIAL_DEMO: DemoState = {
  step: -1,
  offerId: null,
  offers: {},
  fixtures: {},
  verdicts: {},
  negotiations: {},
  capex: null,
  borrowerFile: null,
  funding: null,
  rewordedId: null,
  version: 0,
  busy: false,
  error: null,
};

export const demoStore = createStore<DemoState>(INITIAL_DEMO, {
  storage: "session",
  key: "tl-demo-v2",
  sanitize: (s) => ({ ...s, busy: false, error: null }),
});

export function useDemo(): DemoState {
  return demoStore.useValue();
}

export function bump(): void {
  demoStore.set((s) => ({ ...s, version: s.version + 1 }));
}

export function recordOffer(offer: OfferView, fixtureId?: string): void {
  demoStore.set((s) => ({
    ...s,
    offerId: offer.offer.offer_id,
    offers: { ...s.offers, [offer.offer.offer_id]: offer },
    fixtures: fixtureId ? { ...s.fixtures, [offer.offer.offer_id]: fixtureId } : s.fixtures,
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

export function recordFunding(funding: FundingView): void {
  demoStore.set((s) => ({ ...s, funding, version: s.version + 1 }));
}

/** Makes an already-compiled offer the one the screens show. */
export function selectOffer(offerId: string, rewordedId?: string): void {
  demoStore.set((s) => ({ ...s, offerId, rewordedId: rewordedId ?? s.rewordedId, version: s.version + 1 }));
}

export function clearDemo(): void {
  demoStore.set((s) => ({ ...INITIAL_DEMO, version: s.version + 1 }));
}
