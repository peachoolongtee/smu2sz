"use client";

import { Card, Formula } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { AnnualisedLeg } from "@/lib/types";

/** The legs that belong to the offer itself, that is, not to one of its counters. */
export function offerLegs(legs: AnnualisedLeg[] | undefined, counters: { obligations: { id: string }[] }[] | undefined): AnnualisedLeg[] {
  const counterIds = new Set((counters ?? []).flatMap((c) => c.obligations.map((o) => o.id)));
  return (legs ?? []).filter((l) => !counterIds.has(l.obligation_id));
}

/** One discount's yearly rate and the committed funding it is set against. Every figure is the server's string. */
export function AnnualisedLine({ leg }: { leg: AnnualisedLeg }) {
  const { t } = useI18n();
  return (
    <div data-testid={`annualised-${leg.obligation_id}`}>
      <p className="text-sm">
        <span className="text-ink-2">{t("annualised.leg", { discount: leg.discount_display, rcv: leg.receivable_id })}</span>{" "}
        <span className="font-semibold tabular-nums">{t("annualised.line", { rate: leg.annual_rate_display, days: leg.days_early })}</span>
      </p>
      <div className="mt-1.5">
        <Formula>{leg.formula}</Formula>
      </div>
      {leg.compare_to.length ? (
        <ul className="mt-1.5 space-y-0.5 text-meta text-ink-2">
          {leg.compare_to.map((c) => (
            <li key={c.label}>{t("annualised.against", { label: c.label, rate: c.annual_rate_display })}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** The verdict page's card for the offer's own early-pay discounts. Renders nothing when the server sent none. */
export function AnnualisedCard({ legs }: { legs: AnnualisedLeg[] }) {
  const { t } = useI18n();
  if (!legs.length) return null;
  return (
    <Card id="annualised" title={t("annualised.title")} subtitle={t("annualised.sub")}>
      <ul className="space-y-4" data-testid="annualised-offer">
        {legs.map((l) => (
          <li key={l.obligation_id}>
            <AnnualisedLine leg={l} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** The same, compactly, for the chat: one line per leg, the formula in the tooltip. */
export function AnnualisedCompact({ legs }: { legs: AnnualisedLeg[] }) {
  const { t } = useI18n();
  if (!legs.length) return null;
  return (
    <ul className="space-y-0.5 text-meta text-ink-2" data-testid="chat-annualised">
      {legs.map((l) => (
        <li key={l.obligation_id} title={l.formula}>
          {t("annualised.leg", { discount: l.discount_display, rcv: l.receivable_id })}{" "}
          <span className="font-semibold tabular-nums text-ink">{t("annualised.line", { rate: l.annual_rate_display, days: l.days_early })}</span>
        </li>
      ))}
    </ul>
  );
}
