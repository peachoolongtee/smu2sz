"use client";

import { useI18n } from "@/lib/i18n";
import type { ReceivableRow } from "@/lib/types";
import { ActionButton, actionsOf } from "./actions";

/**
 * On a phone, under the three cards and before the list: the chosen invoice in one compact strip (the invoice in the server's words, what it nets, and
 * the first action as the page's one filled primary), so the answer to "what do I do" is in the first screen. The detail below carries the rest.
 */
export function SelectedStrip({ row, customerHref }: { row: ReceivableRow; customerHref: string }) {
  const { t } = useI18n();
  const first = actionsOf(row)[0];
  return (
    <section aria-label={t("recv3.strip.label")} className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card" data-testid="recv3-strip" data-receivable={row.receivable_id}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="min-w-0 flex-1 break-words text-sm font-semibold text-ink" data-testid="recv3-strip-invoice">
          <span className="first-letter:uppercase">{row.invoice ?? row.buyer_name}</span>
        </p>
        {row.net?.net_short ? (
          <p className="text-sm text-ink-2">
            {t("recv3.col.net")} <span className="font-bold tabular-nums text-ok-fg" data-testid="recv3-strip-net">{row.net.net_short}</span>
          </p>
        ) : null}
      </div>
      {first ? (
        <div data-testid="recv3-strip-primary">
          <ActionButton row={row} action={first} primary scope="strip-" customerHref={customerHref} testId="recv3-strip-action" />
        </div>
      ) : null}
    </section>
  );
}
