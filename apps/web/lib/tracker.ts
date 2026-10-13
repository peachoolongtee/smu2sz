"use client";

/**
 * Deal tracker (map #148, ticket #150): GET /decisions/{id}/tracker?lang= for an agreed deal. The server writes every word and figure
 * (the verdict so far, the stage, the cost expected against the cost so far, each promise and whether it was kept, what it says about
 * the buyer, the one next step); the browser shows them. The types are the server's contract and nothing is derived from them for display.
 */

import { apiMode } from "./api";
import { ApiError } from "./errors";
import { useI18n } from "./i18n";
import { readSelection, selectionQuery, type Selection } from "./selection";
import { useAsync, type AsyncState } from "./use-async";

export type TrackerTone = "ok" | "warn" | "bad" | "neutral";
export type TrackerStageState = "done" | "now" | "todo" | "missed" | "part";
export type TrackerCertainty = "RECORDED" | "QUOTED" | "ATTRIBUTED";
export type TrackerPromiseState = "kept" | "part" | "late" | "missed" | "awaited" | "in_force" | "ended";

export interface TrackerStage {
  key: string;
  label: string;
  state: TrackerStageState;
  state_text: string;
}

export interface TrackerLine {
  key: string;
  label: string;
  expected_fen: number;
  expected_display: string;
  actual_fen: number | null;
  actual_display: string | null;
  actual_note_text: string | null;
  certainty: TrackerCertainty;
  certainty_text: string;
  tone: TrackerTone;
  evidence_href: string | null;
}

export interface TrackerCost {
  expected: { amount_fen: number; amount_display: string; basis_text: string; certainty: TrackerCertainty };
  actual: { amount_fen: number; amount_display: string; note_text: string; tone: "bad" | "ok" | "neutral" };
  to_come: { amount_fen: number | null; amount_display: string | null; note_text: string };
  difference_fen: number;
  difference_display: string;
  lines: TrackerLine[];
  method_text: string;
}

export interface TrackerPromise {
  party: "buyer" | "you";
  party_text: string;
  title_text: string;
  detail_text: string;
  state: TrackerPromiseState;
  state_word: string;
  tone: TrackerTone;
  evidence_href: string | null;
}

export interface TrackerView {
  decision_id: string;
  lang: "en" | "zh";
  available: boolean;
  unavailable_text: string | null;
  buyer_id: string | null;
  buyer_name: string | null;
  agreed_when: string | null;
  terms_text: string | null;
  headline_text: string | null;
  state_word: string | null;
  state_tone: TrackerTone;
  state_text: string | null;
  stages: TrackerStage[];
  cost: TrackerCost | null;
  promises: TrackerPromise[];
  promise_counts: { buyer_kept: number; buyer_total: number; text: string } | null;
  buyer: { text: string; note_text: string | null; href: string | null } | null;
  next: { label: string; text: string; href: string } | null;
  closeout_text: string | null;
  links: { record_href: string; activity_href: string | null };
  context?: { back?: { label: string; href: string } | null } | null;
}

const enc = encodeURIComponent;

/** The request path: the selection the owner arrived with travels along so the server can write the way back. */
export function trackerPath(id: string, lang: "en" | "zh", sel: Selection = {}): string {
  const q = selectionQuery({ ...sel, decision: undefined });
  return `/decisions/${enc(id)}/tracker?lang=${lang}${q ? `&${q}` : ""}`;
}

/**
 * The tracker read. Null when the server has no such read (an older API, FastAPI's own 404) or no such record: the page then says so in
 * words and the link on the decision record is not shown. Any other failure is an error the page shows.
 */
export async function getTracker(id: string, lang: "en" | "zh", sel: Selection = {}): Promise<TrackerView | null> {
  try {
    if (apiMode === "mock") return await (await import("./mock/handlers")).getTracker(id, lang);
    const { http } = await import("./live/http");
    return await http<TrackerView>("GET", trackerPath(id, lang, sel));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** The tracker for one decision in the language on screen; read again whenever the session writes (useAsync). `data` is null for "no such read". */
export function useTracker(id: string | null, sel: Selection = {}): AsyncState<TrackerView | null> {
  const { lang } = useI18n();
  const key = selectionQuery(sel);
  const state = useAsync<TrackerView | null>(async () => (id ? getTracker(id, lang, readSelection(new URLSearchParams(key))) : null), [id, lang, key]);
  return { ...state, data: state.data && state.data.decision_id === id ? state.data : state.data === null ? null : undefined };
}
