"use client";

import { Breakdown } from "@/components/home/v2/breakdown";
import { ButtonLink } from "@/components/ui";
import { getHomeInvoices } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * The selected customer's invoice, as the mockup's agreement and overdue-invoice cards show it: the net cash after repayment (the server's own "about ¥163k"), the invoice value, when it is collected
 * (the server's "In 32 days", "5 days overdue"), the breakdown of what the face becomes at collection (the financing repayment and the cash remaining, each with its share word; the donut sized by those words)
 * and the one filled button, "View invoice", which opens Receivables with the invoice in the address. An invoice with no financing to repay has no breakdown and no card. A failed or absent read shows nothing.
 */
export function InvoiceCards({ customerId }: { customerId: string }) {
  const { t, lang } = useI18n();
  const read = useAsync(() => getHomeInvoices(lang).catch(() => null), [lang]);
  const rows = (read.data?.rows ?? []).filter((r) => r.buyer_id === customerId && (r.breakdown?.length ?? 0) > 0);
  if (!rows.length) return null;
  return (
    <div className="mt-5 space-y-5" data-testid="hv2-invoices">
      {rows.map((r) => (
        <div key={r.receivable_id} data-testid="hv2-invoice" data-invoice={r.receivable_id}>
          <dl className="grid grid-cols-1 gap-y-3 border-y border-line py-4 sm:grid-cols-3 sm:gap-x-6">
            {[
              { key: "net", label: t("hv2.inv.net"), value: r.net_after_repayment_display ?? r.net_short },
              { key: "value", label: t("hv2.inv.value"), value: r.face_display },
              { key: "due", label: t("hv2.inv.due"), value: r.collection_due_text },
            ].map((k) =>
              k.value ? (
                <div key={k.key} className="min-w-0" data-testid={`hv2-invoice-${k.key}`}>
                  <dt className="text-[15px] text-ink-3">{k.label}</dt>
                  <dd className="mt-1 break-words font-display text-[26px] font-bold leading-tight tracking-[-0.02em] tabular-nums text-ink first-letter:uppercase sm:text-[30px]">{k.value}</dd>
                </div>
              ) : null,
            )}
          </dl>
          <Breakdown rows={r.breakdown ?? []} total={r.face_display} testId="hv2-invoice-breakdown" />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
            {r.net?.repays_text ?? r.collection_state_text ? (
              <p className="min-w-0 text-[15px] text-ink" data-testid="hv2-invoice-note">
                {r.net?.repays_text ?? r.collection_state_text}
              </p>
            ) : (
              <span />
            )}
            <ButtonLink href={`/receivables?invoice=${encodeURIComponent(r.receivable_id)}`} variant="primary" data-testid="hv2-invoice-view">
              {t("hv2.inv.view")}
            </ButtonLink>
          </div>
        </div>
      ))}
    </div>
  );
}
