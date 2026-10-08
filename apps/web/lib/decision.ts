import type { CounterChangedDetail, DecisionState } from "./types";

/** The record id of a buyer deal. */
export const dealRecordId = (offerId: string): string => `deal:${offerId}`;

/** An API failure as the client throws it (lib/errors.ts `ApiError`), read by its members so this file needs no import. */
type Failure = { status?: unknown; detail?: unknown };
const failure = (e: unknown): Failure | null => (e instanceof Error ? (e as Failure) : null);

/** The detail of a 409 COUNTER_CHANGED answer (the send was refused, nothing was sent), or null for any other error. */
export function counterChanged(e: unknown): CounterChangedDetail | null {
  const f = failure(e);
  if (!f || f.status !== 409) return null;
  const d = f.detail as Partial<CounterChangedDetail> | undefined;
  return d && d.code === "COUNTER_CHANGED" ? (d as CounterChangedDetail) : null;
}

/** True for the 404 DECISION_NOT_FOUND answer: the server has no such record (a state to say in words, not a failure). */
export function decisionMissing(e: unknown): boolean {
  const f = failure(e);
  return f?.status === 404 && (f.detail as { code?: string } | undefined)?.code === "DECISION_NOT_FOUND";
}

/**
 * How far a buyer deal has come, read from the record's state and nothing else (ADR-0011, F06). The steps are
 * Received · Analysed · Response ready · Sent · the outcome; the outcome's words are the record's own `state_text`.
 * An evaluation's verdict.outcome, a clicked button or the session cache never moves a step.
 */
export type OutcomeTone = "open" | "good" | "closed" | "bad";

export interface DealProgress {
  /** How many of the four steps before the outcome are complete (0 to 4). The next one is the current step. */
  done: number;
  /** True when the outcome step has been reached; false while it is still ahead (it then reads "Agreement"). */
  reached: boolean;
  tone: OutcomeTone;
  /** The record needs the owner or the buyer before the line can go on, and says so in the current step's place. */
  stalled: boolean;
}

export function dealProgress(state: DecisionState): DealProgress {
  switch (state) {
    case "RECEIVED":
      return { done: 1, reached: false, tone: "open", stalled: false };
    case "NEEDS_CLARIFICATION":
      return { done: 1, reached: false, tone: "open", stalled: true };
    case "RESPONSE_READY":
      return { done: 3, reached: false, tone: "open", stalled: false };
    case "AUTHORIZATION_REQUIRED":
      return { done: 4, reached: true, tone: "open", stalled: false };
    case "AGREED":
    case "FULFILLED":
      return { done: 4, reached: true, tone: "good", stalled: false };
    case "MISSED":
    case "FAILED":
      return { done: 4, reached: true, tone: "bad", stalled: false };
    // EXPIRED, REVOKED, NO_DEAL and DECLINED close the deal without an agreement in force.
    default:
      return { done: 4, reached: true, tone: "closed", stalled: false };
  }
}
