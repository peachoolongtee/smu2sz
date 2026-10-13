/**
 * Who funds the business: the owner's own money and each lender's share, for the Home's funding ring.
 *
 * INVARIANT 13: the fen here only size the ring's arcs and its whole-percent shares; every amount the page prints is a
 * server `*_display` string. Own money is today's cash less the borrowed money that has already landed in it (a draw still
 * in transit is owed but not yet cash). The legs of a plan not yet run are their own, lighter slices.
 */
import type { Fen, HomeView } from "./types";

export type FundingSliceKind = "own" | "lender" | "planned";

export interface FundingSlice {
  key: string;
  kind: FundingSliceKind;
  /** The facility behind a lender or planned slice (its id on the books); null for own money. */
  facilityId: string | null;
  /** The lender's name as the server wrote it; null for the owner's own money (the page names it). */
  name: string | null;
  /** The server's amount; null for own money, which the server does not state. */
  amount: string | null;
  /** The server's words for when the money lands, when it has not yet. */
  when: string | null;
  /** A planned leg's own cost, as the server priced it. */
  cost: string | null;
  fen: Fen;
  /** Whole percent of the ring. */
  share: number;
}

export interface FundingMix {
  slices: FundingSlice[];
  /** The owner's own money as a whole percent of everything funding the business. */
  ownShare: number;
  /** Nothing borrowed and nothing planned: the ring is all own money. */
  ownOnly: boolean;
}

/** The ring's hues: the owner's own money in the deep navy, each facility in a chart hue by its place on the books, so a lender keeps its colour everywhere. Never a status. */
export const OWN_HUE = "var(--color-chart-navy)";
const LENDER_HUES = ["var(--color-brand-300)", "var(--color-chart-teal)", "var(--color-chart-purple)", "var(--color-chart-sky)"];

export function lenderHue(h: HomeView, facilityId: string | null): string {
  const i = h.facilities.findIndex((f) => f.id === facilityId);
  return LENDER_HUES[(i < 0 ? h.facilities.length : i) % LENDER_HUES.length];
}

export function fundingMix(h: HomeView): FundingMix | null {
  const transit = new Map((h.cash.in_transit?.lots ?? []).map((l) => [l.facility_name, l.arrival_when]));
  // The legs of the run plan say exactly what is still arriving; without them a lender named on an in-transit lot is counted as arriving in full.
  const legs = h.home_v2?.action.legs ?? null;
  const arrivingFen = legs
    ? legs.filter((l) => l.state.toUpperCase() === "ARRANGED").reduce((s, l) => s + (l.amount_fen ?? 0), 0)
    : h.facilities.filter((f) => transit.has(f.name)).reduce((s, f) => s + (f.drawn_fen ?? 0), 0);
  const lenders = h.facilities.filter((f) => (f.drawn_fen ?? 0) > 0);
  const drawnFen = lenders.reduce((s, f) => s + (f.drawn_fen ?? 0), 0);
  const ownFen = Math.max(h.cash.cash_fen - (drawnFen - arrivingFen), 0);
  const plan = h.next_action;
  const planned: Omit<FundingSlice, "share">[] = !plan
    ? []
    : plan.legs?.length
      ? plan.legs.map((l) => ({ key: `plan-${l.index}`, kind: "planned" as const, facilityId: l.facility_id, name: l.name_display ?? l.facility_name, amount: l.amount_display, when: l.lands_when ?? null, cost: l.cost_display, fen: l.amount_fen ?? 0 }))
      : plan.components.map((c, i) => ({
          key: `plan-${i}`,
          kind: "planned" as const,
          facilityId: h.facilities.find((f) => f.name === c.name_display)?.id ?? null,
          name: c.name_display ?? c.what,
          amount: c.amount_short,
          when: c.lands_when,
          cost: c.cost_display ?? null,
          fen: c.amount_fen ?? 0,
        }));

  const raw: Omit<FundingSlice, "share">[] = [
    { key: "own", kind: "own", facilityId: null, name: null, amount: null, when: null, cost: null, fen: ownFen },
    ...lenders.map((f) => ({ key: f.id, kind: "lender" as const, facilityId: f.id, name: f.name, amount: f.drawn_display, when: transit.get(f.name) ?? null, cost: null, fen: f.drawn_fen ?? 0 })),
    ...planned,
  ];
  const total = raw.reduce((s, r) => s + r.fen, 0);
  if (total <= 0) return null;
  const slices = raw.filter((r) => r.fen > 0).map((r) => ({ ...r, share: Math.round((r.fen / total) * 100) }));
  return { slices, ownShare: Math.round((ownFen / total) * 100), ownOnly: slices.every((s) => s.kind === "own") };
}
