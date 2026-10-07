"use client";

import { Badge, Card } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeView } from "@/lib/types";

/**
 * The current funding position once no further action is needed: each lot on the books with where it came from and
 * whether it has landed or is still arriving, then each committed source's drawn and available amounts. Every figure
 * is the server's; the card adds nothing up. A lot's figure is what is still outstanding on it (`remaining_display`),
 * with the amount drawn beside it when part has been repaid; an opening balance is not "received today".
 */
export function CurrentFunding({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const lots = h.cash.funding_lots ?? [];
  // A source with something drawn: the server's `drawn_fen` (an older recording without it falls back to the display string).
  const drawn = h.facilities.filter((f) => (f.drawn_fen !== undefined ? f.drawn_fen > 0 : f.drawn_display !== "¥0.00"));
  return (
    <Card id="cash-current" title={t("biz.cash.current")} subtitle={t("biz.cash.current.sub")}>
      {lots.length ? (
        <ul className="divide-y divide-line" data-testid="cash-current-lots">
          {lots.map((lot, i) => (
            <li key={`${lot.facility_name}-${lot.arrival_day}-${i}`} className="flex flex-wrap items-center justify-between gap-2 py-2.5" data-testid={`cash-lot-${lot.landed ? "landed" : "transit"}`}>
              <div className="min-w-0">
                <p className="text-sm font-semibold tabular-nums text-ink">
                  {lot.remaining_display ?? lot.amount_display} <span className="font-normal text-ink-2">{lot.facility_name}</span>
                  {lot.remaining_display && lot.remaining_display !== lot.amount_display ? (
                    <span className="ml-1.5 text-xs font-normal text-ink-3" data-testid="cash-lot-of">{t("biz.cash.lot.of", { amount: lot.amount_display })}</span>
                  ) : null}
                </p>
                <p className="text-xs text-ink-3">
                  {lot.opening ? t("biz.cash.lot.opening") : lot.landed ? t("biz.cash.lot.landed", { when: lot.arrival_when }) : t("biz.cash.lot.arrives", { when: lot.arrival_when })}
                </p>

              </div>
              <Badge tone={lot.landed ? "ok" : "info"}>{lot.landed ? t("biz.cash.lot.received") : t("biz.cash.lot.inTransit")}</Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-2" data-testid="cash-current-none">
          {t("biz.cash.current.none")}
        </p>
      )}
      {drawn.length ? (
        <dl className="mt-3 grid gap-2 border-t border-line pt-3 sm:grid-cols-2" data-testid="cash-current-facilities">
          {drawn.map((f) => (
            <div key={f.id} className="text-sm">
              <dt className="text-xs font-medium text-ink-3">{f.name}</dt>
              <dd className="tabular-nums text-ink">{t("biz.cash.facility.drawn", { drawn: f.drawn_display, available: f.available_display })}</dd>
              {/* How much of the limit is in use, as a bar (geometry only; the words above carry the figures). Over the limit it turns red. */}
              {f.limit_fen && f.drawn_fen !== undefined ? (
                <dd className="mt-1 h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden data-testid="cash-utilisation">
                  <span className={`block h-full rounded-full ${f.drawn_fen > f.limit_fen ? "bg-bad-solid" : "bg-brand-600"}`} style={{ width: `${Math.min(100, Math.round((f.drawn_fen / f.limit_fen) * 100))}%` }} />
                </dd>
              ) : null}
            </div>
          ))}
        </dl>
      ) : null}
      <p className="mt-3 text-sm font-medium text-ok-fg" data-testid="cash-no-gap">
        {t("biz.cash.noMore")}
      </p>
    </Card>
  );
}
