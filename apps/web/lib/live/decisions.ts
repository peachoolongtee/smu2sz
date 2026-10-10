/**
 * The durable decision record (ADR-0011): GET /decisions and GET /decisions/{id}. Owner only. Every sentence and figure is the
 * server's; nothing here reshapes or computes them. An id carries colons (`deal:OFF-…`, `alert:ALERT-…:v6`), so it is encoded.
 */

import type { DecisionList, DecisionView } from "../types";
import { http } from "./http";

export interface DecisionQuery {
  lang: "en" | "zh";
  family?: "DEAL" | "FUNDING";
  /** Only the records that are not finished. */
  open?: boolean;
  limit?: number;
}

export function getDecisions(q: DecisionQuery): Promise<DecisionList> {
  const params = new URLSearchParams({ lang: q.lang });
  if (q.family) params.set("family", q.family);
  if (q.open) params.set("open", "true");
  if (q.limit !== undefined) params.set("limit", String(q.limit));
  return http<DecisionList>("GET", `/decisions?${params.toString()}`);
}

export function getDecision(id: string, lang: "en" | "zh"): Promise<DecisionView> {
  return http<DecisionView>("GET", `/decisions/${encodeURIComponent(id)}?lang=${lang}`);
}
