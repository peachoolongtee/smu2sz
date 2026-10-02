"use client";

import { useI18n } from "@/lib/i18n";
import type { Displayed, FinancialState } from "@/lib/types";

type Lot = NonNullable<Displayed<FinancialState>["lots"]>[number];

/** Funding requested but not yet credited as cash (ADR-0010): the lots the server has not settled. */
export function lotsInTransit(state: Displayed<FinancialState>): Lot[] {
  return (state.lots ?? []).filter((l) => !l.settled);
}

/** "¥210,000.00 lands on day 3", one block per lot, kept apart from cash in hand. Renders nothing when nothing is on its way. Spans only, so it can sit inside a paragraph. */
export function InTransit({ lots }: { lots: Lot[] }) {
  const { t } = useI18n();
  if (lots.length === 0) return null;
  return (
    <span className="block space-y-0.5" data-testid="in-transit">
      {lots.map((l) => (
        <span key={l.id} className="block" data-testid="in-transit-lot">
          <span className="font-semibold tabular-nums">{t("transit.lands", { amount: l.principal_display, n: l.arrival_day })}</span>
          <span className="block text-xs font-normal text-ink-3">{t("transit.hint", { from: l.request_day, facility: l.facility_id })}</span>
        </span>
      ))}
    </span>
  );
}
