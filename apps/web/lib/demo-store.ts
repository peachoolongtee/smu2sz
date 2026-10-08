"use client";

import { createStore } from "./create-store";
import type { Lang } from "./i18n";
import type { BorrowerFileView, CapexApplyResult, CapexView, FundingView, NegotiationView, OfferView, VerdictView } from "./types";

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
  /** The application POST /capex/apply queued for the selected structure (waiting for the owner in Approvals). */
  capexApplication: CapexApplyResult | null;
  borrowerFile: BorrowerFileView | null;
  /**
   * The Debt Desk view as it stood when the decision was made. Executing a plan changes the books, so
   * a live re-plan afterwards would show "no funding needed"; the Funding screen shows this snapshot instead.
   */
  funding: FundingView | null;
  /** The reworded offer (EX01B), evaluated on the same books as EX01 before any operation executes. */
  rewordedId: string | null;
  /** The buyer's message the story is about. The optional scenes read other messages; this is the one Deals returns to. */
  storyOfferId: string | null;
  /** The cure the story queued for the owner's approval (the approval card, its record and the day its cash lands), once it has been queued. */
  cure: StoryCure | null;
  /**
   * What each finished step was told by the server (the sentences and figures of the responses it just received), by step id and in the
   * language they were written in. The step's narration is built from these; a step with none, or in another language, shows its plain sentence.
   */
  facts: Record<string, StepFacts>;
  /** Bumped after every write so read hooks refetch. */
  version: number;
  busy: boolean;
  /**
   * The step being run, set when a run starts and cleared when it commits or fails. It is saved with the session, so a
   * reload in the middle of a step leaves `running` set with `busy` false: the stepper then says the step was interrupted.
   */
  running: number | null;
  error: string | null;
}

/** The cure waiting for (or past) the owner's decision: ids and the server's own display strings, nothing computed. */
export interface StoryCure {
  approvalId: string;
  decisionId: string | null;
  /** The amount the owner is asked to approve, as the server wrote it ("¥200,000.00"); empty when the queue row had none. */
  amount: string;
  /** The day the cash lands, from the approval card; null when the card did not say. */
  landsDay: number | null;
}

export interface StepFacts {
  lang: Lang;
  values: Record<string, string>;
}

export const INITIAL_DEMO: DemoState = {
  step: -1,
  offerId: null,
  offers: {},
  fixtures: {},
  verdicts: {},
  negotiations: {},
  capex: null,
  capexApplication: null,
  borrowerFile: null,
  funding: null,
  rewordedId: null,
  storyOfferId: null,
  cure: null,
  facts: {},
  version: 0,
  busy: false,
  running: null,
  error: null,
};

export const demoStore = createStore<DemoState>(INITIAL_DEMO, {
  storage: "session",
  key: "tl-demo-v3",
  // A reload never restores a locked stepper: `busy` is not saved, `running` is (it is how a reload mid-step is recognised).
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

export function recordCapexApplication(capexApplication: CapexApplyResult): void {
  demoStore.set((s) => ({ ...s, capexApplication, version: s.version + 1 }));
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

export function recordFacts(stepId: string, facts: StepFacts): void {
  demoStore.set((s) => ({ ...s, facts: { ...s.facts, [stepId]: facts } }));
}

export function recordCure(cure: StoryCure): void {
  demoStore.set((s) => ({ ...s, cure, version: s.version + 1 }));
}

/** The story's own offer is the current one again (the optional scenes read other messages and leave the story's where it was). */
export function selectStoryOffer(): void {
  const id = demoStore.get().storyOfferId;
  if (id && demoStore.get().offerId !== id && demoStore.get().offers[id]) demoStore.set((s) => ({ ...s, offerId: id, version: s.version + 1 }));
}

/** Makes an already-compiled offer the one the screens show. */
export function selectOffer(offerId: string, rewordedId?: string): void {
  demoStore.set((s) => ({ ...s, offerId, rewordedId: rewordedId ?? s.rewordedId, version: s.version + 1 }));
}

/**
 * Clears the scenario's data (offers, verdicts, negotiations, funding, ids) and nothing that controls the running step: `busy`,
 * `running`, `step` and `error` stay as they are, so a step that clears the books half-way (Setup, the walk) stays locked and
 * keeps its place until `goToStep` commits it.
 */
export function clearDemo(): void {
  demoStore.set((s) => ({ ...INITIAL_DEMO, busy: s.busy, running: s.running, step: s.step, error: s.error, version: s.version + 1 }));
}

/** Back to the first screen: the data and the step pointer both cleared (the Reset action, after the server has reset the books). */
export function resetSession(): void {
  demoStore.set((s) => ({ ...INITIAL_DEMO, version: s.version + 1 }));
}
