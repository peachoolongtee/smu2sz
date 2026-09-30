/**
 * GET /trajectory and the evaluate response carry the trajectory as `{fen, text}` money pairs. The pages
 * read the flat `*_fen` / `*_display` shape, so this adapter renames fields. It does no money arithmetic:
 * every string shown is one the server wrote, and every number is an integer fen passed through for axes.
 */

import type {
  Displayed,
  MandateView,
  Mode,
  MoneyTrajectory,
  ObligationType,
  TextRatio,
  StateView,
  Trajectory,
  TrajectoryView,
  VerdictView,
} from "../types";
import { http } from "./http";

/** "1.92x" -> { text: "1.92" }. The server formats the ratio; we only drop its unit suffix. */
function ratioText(s: string | null): TextRatio | null {
  return s === null ? null : { text: s.replace(/[x×]$/i, "") };
}

export function toTrajectory(
  raw: MoneyTrajectory,
  ctx: { horizon: number; ebitda_fen: number; ebitda_display: string },
): Displayed<Trajectory> {
  return {
    mode: raw.mode,
    horizon_days: ctx.horizon,
    days: raw.days.map((d) => ({
      day: d.day,
      closing_fen: d.closing.fen,
      closing_display: d.closing.text,
      debt_outstanding_fen: d.debt.fen,
      debt_outstanding_display: d.debt.text,
      forward_concession_fen: d.forward_concession.fen,
      forward_concession_display: d.forward_concession.text,
      events: d.events.map((e) => ({
        day: d.day,
        kind: e.kind as Trajectory["days"][number]["events"][number]["kind"],
        amount_fen: e.amount.fen,
        amount_display: e.amount.text,
        label: e.label,
        ref: e.ref,
        formula: e.formula,
      })),
    })),
    months: raw.months.map((m) => ({
      month: m.month,
      ebitda_fen: ctx.ebitda_fen,
      ebitda_display: ctx.ebitda_display,
      debt_service_fen: m.debt_service.fen,
      debt_service_display: m.debt_service.text,
      total_debt_fen: m.total_debt.fen,
      total_debt_display: m.total_debt.text,
      dscr: ratioText(m.dscr),
      leverage: ratioText(m.leverage) ?? { text: "" },
    })),
    min_cash_fen: raw.min_cash.fen,
    min_cash_display: raw.min_cash.text,
    min_cash_day: raw.min_cash_day,
    first_breach_day: raw.first_breach_day,
    interest_posted_fen: raw.interest.fen,
    interest_posted_display: raw.interest.text,
    fees_posted_fen: raw.fees.fen,
    fees_posted_display: raw.fees.text,
    discounts_posted_fen: raw.discounts.fen,
    discounts_posted_display: raw.discounts.text,
  } as Displayed<Trajectory>;
}

const PART_LABEL: Partial<Record<ObligationType, string>> = {
  TERMS_EXTENSION: "Terms extension, 12-month funding cost",
  CONTINGENT_REBATE: "Contingent rebate, at maximum",
  PRICE_ADJUSTMENT: "Price adjustment",
  VOLUME_COMMITMENT: "Volume commitment",
  OPERATIONAL_CONCESSION: "Operational concession",
};

function forwardParts(verdict: VerdictView): TrajectoryView["forward_concession"]["parts"] {
  const typeOf = new Map((verdict.bound_obligations ?? []).map((o) => [o.id, o.type] as const));
  return verdict.concession_values
    .filter((c) => typeOf.get(c.obligation_id) !== "IMMEDIATE_DISCOUNT") // capped separately, not a forward concession
    .map((c) => {
      const type = typeOf.get(c.obligation_id);
      return {
        label: (type && PART_LABEL[type]) ?? type ?? c.obligation_id,
        value_fen: c.value_fen,
        value_display: c.value_display,
      };
    });
}

/** The RESERVE_BREACH violation carries the shortfall as server-formatted strings; read them, never recompute. */
function shortfall(verdict: VerdictView): { fen: number | null; display: string | null } {
  const v = verdict.violations.find((x) => x.code === "RESERVE_BREACH");
  const display = v?.inputs.max_shortfall ?? null;
  const fen = v?.inputs.shortfall_fen !== undefined ? Number(v.inputs.shortfall_fen) : null;
  return { fen: Number.isFinite(fen) ? fen : null, display };
}

const NOTE: Record<Mode, string> = {
  CONSERVATIVE:
    "Conservative mode decides. Unconfirmed inflows are ignored and only COMMITTED facilities can be used. The monthly ratios are the projection itself; the pro forma ratios with a terms extension funded are in the verdict's covenant checks.",
  EXPECTED:
    "Expected mode is shown, never relied on. It is the current position without any offer applied; unconfirmed inflows and pending facilities may be included.",
};

/**
 * Composes the trajectory screen from GET /trajectory (the position today), GET /state, GET /mandate and,
 * when an offer has been evaluated, that verdict's own trajectory and forward-concession totals.
 */
export async function getTrajectory(mode: Mode, verdict?: VerdictView | null): Promise<TrajectoryView> {
  const [raw, state, mandate] = await Promise.all([
    http<MoneyTrajectory>("GET", `/trajectory?mode=${mode}`),
    http<StateView>("GET", "/state"),
    http<MandateView>("GET", "/mandate"),
  ]);
  const ctx = {
    horizon: mandate.mandate.horizon_days,
    ebitda_fen: state.state.monthly_ebitda_fen,
    ebitda_display: state.state.monthly_ebitda_display,
  };
  // The verdict's trajectory is the conservative projection with the offer applied. Expected mode has no
  // offer-applied counterpart in the API, so it shows the position today.
  const withOffer = mode === "CONSERVATIVE" && verdict?.trajectory ? (verdict.trajectory as unknown as MoneyTrajectory) : null;
  // The API projects the offer with its committed cure plan applied (display only; the verdict already priced it).
  const curedRaw = withOffer && verdict?.cured_trajectory ? (verdict.cured_trajectory as unknown as MoneyTrajectory) : null;
  const used = withOffer ?? raw;
  const short = withOffer && verdict ? shortfall(verdict) : { fen: null, display: null };
  const fwd = withOffer && verdict ? verdict.forward_concession : null;
  return {
    mode,
    floor: { min_cash_fen: used.floor.fen, min_cash_display: used.floor.text },
    shortfall_fen: short.fen,
    shortfall_display: short.display,
    trajectory: toTrajectory(used, ctx),
    cured_trajectory: curedRaw ? toTrajectory(curedRaw, ctx) : null,
    forward_concession: {
      total_fen: fwd?.total_fen ?? 0,
      total_display: fwd?.total_display ?? used.days[used.days.length - 1]?.forward_concession.text ?? "",
      cap_fen: fwd?.cap_fen ?? mandate.mandate.max_aggregate_forward_concession_fen,
      cap_display: fwd?.cap_display ?? mandate.mandate.max_aggregate_forward_concession_display,
      over_cap: fwd?.over_cap ?? false,
      parts: withOffer && verdict ? forwardParts(verdict) : [],
    },
    covenant_limits: {
      min_dscr_display: mandate.mandate.min_dscr_display,
      max_leverage_display: mandate.mandate.max_leverage_display,
    },
    note: NOTE[mode],
  } as TrajectoryView;
}
