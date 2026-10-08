"use client";

import { decisionMissing, getDecision, getDecisions } from "./api";
import { useI18n } from "./i18n";
import type { DecisionList, DecisionView } from "./types";
import { useAsync, type AsyncState } from "./use-async";

/**
 * One decision record, read from GET /decisions/{id} in the language on screen. It is read again whenever the session writes (a send, an
 * approval, a clock move bumps the demo version), so a page never keeps a lifecycle it read before the books moved. `data` is the record
 * for this id only (never the previous id's while the next loads); a 404 DECISION_NOT_FOUND is `data: null`, not an error.
 */
export function useDecision(id: string | null): AsyncState<DecisionView | null> {
  const { lang } = useI18n();
  const state = useAsync<DecisionView | null>(async () => {
    if (!id) return null;
    try {
      return await getDecision(id, lang);
    } catch (e) {
      if (decisionMissing(e)) return null;
      throw e;
    }
  }, [id, lang]);
  return { ...state, data: state.data && state.data.id === id ? state.data : state.data === null ? null : undefined };
}

/** The record's list (newest first), read again when the session writes. */
export function useDecisions(opts: { family?: "DEAL" | "FUNDING"; open?: boolean; limit?: number } = {}): AsyncState<DecisionList> {
  const { lang } = useI18n();
  return useAsync(() => getDecisions({ lang, ...opts }), [lang, opts.family, opts.open, opts.limit]);
}
