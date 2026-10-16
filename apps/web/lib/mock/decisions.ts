/**
 * Mock for the durable decision record (GET /decisions, GET /decisions/{id}). The mock books nothing of its own, so a record is one of the
 * snapshots the recorder took from the real API (mocks/decisions.json, both languages), chosen by where the recorded story stands: which
 * offers were read, evaluated or answered, the simulated day and receipt variant, and the state of the cure and of each approval.
 * No sentence, state or figure is written here; this file only chooses a recording and re-keys a deal's id for a reworded offer.
 */

import { ApiError } from "../errors";
import type { ApprovalView, DecisionList, DecisionSummary, DecisionView, NegotiationView, OfferView } from "../types";

type Snap = { en: DecisionView; zh: DecisionView };
type Snaps = Record<string, Snap>;

/** The recordings load on first use, in their own chunk. */
const recordings = async (): Promise<Snaps> => (await import("../../mocks/decisions.json")).default as unknown as Snaps;

export type ReceiptVariant = "none" | "half" | "residual" | null;

/** Where the mock's story stands, read by the handlers from their own store and the home mock. */
export interface DecisionContext {
  day: number;
  /** The day the recorded story's news arrives (day 34). */
  newsDay: number;
  /** The day-0 funding plan has run. */
  funded: boolean;
  /** Where the day-34 cure stands. */
  stage: "open" | "pending" | "approved";
  /** The guided Demo's synthetic bank event has posted the agreed early payment (before day 34). */
  receipted: boolean;
  /** The day the approved cure's funding has landed and settled. */
  settledDay: number;
  receipt: ReceiptVariant;
  offers: Record<string, OfferView>;
  evaluated: string[];
  negotiated: Record<string, NegotiationView>;
  /** Offer ids that have a commitment on the books (the recorded history seeded without the walk counts). */
  commitmentOffers: string[];
  approvals: ApprovalView[];
  /** Records the story holds as recordings of their own, by id (the message sent outside FLOW: lib/mock/buyer-message.ts); they stand in for the snapshot the story would choose. */
  recorded?: Record<string, Snap>;
}

const SUMMARY_KEYS: (keyof DecisionSummary)[] = ["id", "family", "state", "state_text", "terminal", "headline", "counterparty_name", "amount_display", "opened_when", "updated_when", "waiting_for", "residual"];

const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

/** The fixture a recorded deal belongs to ("ex01", "ex01b", "sec", "accept"), from the `received.<fixture>` snapshots. */
function fixtureOf(snaps: Snaps, offerId: string): string | null {
  for (const [name, s] of Object.entries(snaps)) if (name.startsWith("received.") && s.en.source.offer_id === offerId) return name.slice("received.".length);
  return null;
}

/** The snapshot name of a deal record, or null when the mock has never seen the offer. */
function dealKey(snaps: Snaps, ctx: DecisionContext, offerId: string): { key: string; rekey: boolean } | null {
  const fixture = fixtureOf(snaps, offerId);
  if (!fixture) return null;
  const negotiation = ctx.negotiated[offerId];
  const agreed = negotiation?.outcome === "DEAL" || ctx.commitmentOffers.includes(offerId);
  // Only the first demo message (EX01) has its answer recorded; the reworded one reads as the same buyer's, same answer (the id is re-keyed).
  const answered = "ex01";
  const rekey = fixture !== "ex01";
  if (agreed && ctx.offers[offerId]) {
    if (ctx.day >= ctx.newsDay) {
      const after = ctx.receipt === "none" ? "noreceipt_day34" : ctx.receipt === "half" ? "half_day34" : "fulfilled_day34";
      return { key: `${after}.${answered}`, rekey };
    }
    // The synthetic bank event paid the agreed early payment: the deal is fulfilled from that day on (recorded with day 34's books).
    return { key: `${ctx.receipted ? "fulfilled_day34" : "agreed_day0"}.${answered}`, rekey };
  }
  if (agreed) {
    // Seeded history without an offer in this session: the deal as the recorded story left it.
    const after = ctx.day < ctx.newsDay ? "agreed_day0" : ctx.receipt === "none" ? "noreceipt_day34" : ctx.receipt === "half" ? "half_day34" : "fulfilled_day34";
    return { key: `${after}.ex01`, rekey };
  }
  if (negotiation?.outcome === "NO_DEAL") return { key: `nodeal.ex01`, rekey };
  if (ctx.evaluated.includes(offerId)) return { key: `ready.${fixture}`, rekey: false };
  if (ctx.offers[offerId]) return { key: `received.${fixture}`, rekey: false };
  return null;
}

/** The funding or approval record's snapshot, chosen by the state of its approval in the mock's queue. */
function otherKey(snaps: Snaps, ctx: DecisionContext, id: string): string | null {
  const row = ctx.approvals.find((a) => a.decision_id === id);
  const has = (name: string) => snaps[name]?.en.id === id;
  if (has("cure_residual") && ctx.receipt === "residual") return "cure_residual";
  if (has("cure_day0") && ctx.funded) return "cure_day0";
  if (has("cure_pending")) {
    const refused = row?.status === "APPROVED" && (row.execution_status === "REFUSED" || row.presentation?.execution_status === "REFUSED");
    const settled = has("cure_settled") && ctx.day >= ctx.settledDay ? "cure_settled" : "cure_approved";
    if (row) return refused ? "cure_failed" : row.status === "PENDING" ? "cure_pending" : settled;
    if (ctx.day >= ctx.newsDay && ctx.stage !== "open") return ctx.stage === "approved" ? settled : "cure_pending";
    return null;
  }
  if (has("apply_pending")) {
    if (!row) return null;
    return row.status === "PENDING" ? "apply_pending" : row.status === "APPROVED" ? "apply_approved" : "apply_rejected";
  }
  return null;
}

async function resolve(ctx: DecisionContext, id: string, lang: "en" | "zh"): Promise<DecisionView | null> {
  const snaps = await recordings();
  const own = ctx.recorded?.[id];
  if (own) return clone(own[lang]);
  if (id.startsWith("deal:")) {
    const offerId = id.slice("deal:".length);
    const found = dealKey(snaps, ctx, offerId);
    if (!found) return null;
    const view = clone(snaps[found.key][lang]);
    if (found.rekey) {
      view.id = id;
      if (view.source.offer_id) view.source.offer_id = offerId;
    }
    return view;
  }
  const key = otherKey(snaps, ctx, id);
  return key ? clone(snaps[key][lang]) : null;
}

export async function mockDecision(ctx: DecisionContext, id: string, lang: "en" | "zh"): Promise<DecisionView> {
  const view = await resolve(ctx, id, lang);
  if (!view) throw new ApiError(404, "Decision not found.", { code: "DECISION_NOT_FOUND", decision_id: id });
  return view;
}

const summaryOf = (v: DecisionView): DecisionSummary => Object.fromEntries(SUMMARY_KEYS.map((k) => [k, v[k]])) as unknown as DecisionSummary;

/** The records the story has so far, newest kind first (funding, then deals), as the list route would give them. */
export async function mockDecisions(ctx: DecisionContext, q: { lang: "en" | "zh"; family?: "DEAL" | "FUNDING"; open?: boolean; limit?: number }): Promise<DecisionList> {
  const snaps = await recordings();
  const ids: string[] = [];
  const add = (id: string | null | undefined) => id && !ids.includes(id) && ids.push(id);
  for (const a of ctx.approvals) add(a.decision_id);
  if (ctx.funded) add(snaps.cure_day0?.en.id);
  if (ctx.receipt === "residual") add(snaps.cure_residual?.en.id);
  if (ctx.day >= ctx.newsDay && ctx.stage !== "open") add(snaps.cure_pending?.en.id);
  for (const offerId of new Set([...ctx.evaluated, ...ctx.commitmentOffers])) add(`deal:${offerId}`);
  for (const id of Object.keys(ctx.recorded ?? {})) add(id);
  const rows: DecisionSummary[] = [];
  for (const id of ids) {
    const v = await resolve(ctx, id, q.lang);
    if (v) rows.push(summaryOf(v));
  }
  let out = rows;
  if (q.family) out = out.filter((r) => r.family === q.family);
  if (q.open) out = out.filter((r) => !r.terminal);
  if (q.limit !== undefined) out = out.slice(0, q.limit);
  return { day: ctx.day, lang: q.lang, count: out.length, decisions: out };
}
