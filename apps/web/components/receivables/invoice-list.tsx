"use client";

import { Avatar, initials, toneFor } from "@/components/business/kit";
import { CustomerName } from "@/components/customer-link";
import { Badge, toggleClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { ReceivableRow } from "@/lib/types";
import { FinancingSteps } from "./financing-steps";
import { inFilter, stateTone, type RecvFilter } from "./state";

const COLS = "lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.7fr)_minmax(0,1fr)_minmax(0,1fr)]";

/**
 * The invoices as one table on a desktop and one card each on a phone: the filter pills by the server's collection state (a pill with nothing in it is
 * disabled, never hidden), then a row per invoice: the customer (a link to its page, carrying the context), what is outstanding, the due day in the
 * server's words, the financing with its three steps, the net to the owner and the state word. A row is chosen with one stretched button (its amount),
 * so the customer link stays a link; the chosen row is `aria-current`. The server's order is kept; the filter only hides rows. The chosen row carries a 3 px left rule as well as the tint (a selection is never colour alone).
 */
export function InvoiceList({
  rows,
  selectedId,
  onSelect,
  filter,
  onFilter,
}: {
  rows: ReceivableRow[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  filter: RecvFilter;
  onFilter: (f: RecvFilter) => void;
}) {
  const { t } = useI18n();
  const pills: { id: RecvFilter; label: string }[] = [
    { id: "all", label: t("biz.recv.filter.all") },
    { id: "soon", label: t("biz.recv.filter.soon") },
    { id: "overdue", label: t("recv3.filter.overdue") },
    { id: "promises", label: t("recv3.filter.promises") },
  ];
  const shown = rows.filter((r) => inFilter(r, filter));

  return (
    <section aria-label={t("recv3.list.label")} className="space-y-3" data-testid="recv3-list">
      <div role="group" aria-label={t("biz.recv.filter.label")} className="flex flex-wrap gap-1.5" data-testid="recv-filters">
        {pills.map((p) => {
          // A pill with nothing behind it is disabled (not counted for the owner: the page shows no number the server did not write).
          const empty = p.id !== "all" && !rows.some((r) => inFilter(r, p.id));
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={filter === p.id}
              disabled={empty}
              onClick={() => onFilter(p.id)}
              className={toggleClass(filter === p.id, "md")}
              data-testid={`recv-filter-${p.id}`}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      {shown.length === 0 ? (
        <p className="rounded-card border border-dashed border-line-strong px-4 py-6 text-center text-sm text-ink-2" data-testid="recv-filter-none">
          {rows.length === 0 ? t("recv3.list.empty") : t("biz.recv.filter.none")}
        </p>
      ) : (
        <div role="table" aria-label={t("recv3.list.label")} className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <div role="rowgroup">
            <div role="row" className={`hidden gap-x-4 border-b border-l-[3px] border-b-line-strong border-l-transparent bg-subtle px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-3 lg:grid ${COLS}`}>
              <span role="columnheader">{t("recv3.col.customer")}</span>
              <span role="columnheader">{t("recv3.col.outstanding")}</span>
              <span role="columnheader">{t("recv3.col.due")}</span>
              <span role="columnheader">{t("recv3.col.financing")}</span>
              <span role="columnheader">{t("recv3.col.net")}</span>
              <span role="columnheader">{t("recv3.col.status")}</span>
            </div>
          </div>
          <div role="rowgroup" className="motion-rise divide-y divide-line">
            {shown.map((r) => {
              const buyer = r.buyer_name ?? "";
              const selected = r.receivable_id === selectedId;
              return (
                <div
                  key={r.receivable_id}
                  id={r.receivable_id}
                  role="row"
                  data-testid={`recv-${r.receivable_id}`}
                  data-selected={selected ? "true" : undefined}
                  data-state={r.collection_state}
                  className={`relative grid scroll-mt-20 grid-cols-2 items-start gap-x-4 gap-y-3 border-l-[3px] px-4 py-3 has-[button:focus-visible]:outline has-[button:focus-visible]:outline-2 has-[button:focus-visible]:-outline-offset-2 has-[button:focus-visible]:outline-focus lg:items-center ${COLS} ${selected ? "border-brand-600 bg-brand-50" : "border-transparent hover:bg-subtle"} transition-colors duration-(--dur)`}
                >
                  <div role="cell" className="col-span-2 flex min-w-0 items-center gap-3 lg:col-span-1">
                    <Avatar tone={toneFor(buyer)}>{initials(buyer)}</Avatar>
                    <CustomerName id={r.buyer_id} className="hit relative z-10 min-w-0 break-words text-sm font-semibold text-brand-700" testId={`recv-customer-${r.receivable_id}`}>
                      {buyer}
                    </CustomerName>
                  </div>
                  <div role="cell" className="min-w-0">
                    <Label>{t("recv3.col.outstanding")}</Label>
                    <button
                      type="button"
                      aria-current={selected ? "true" : undefined}
                      aria-label={t("recv3.select.aria", { invoice: r.invoice ?? buyer })}
                      onClick={() => onSelect(r.receivable_id)}
                      className="text-left text-sm font-bold tabular-nums text-ink after:absolute after:inset-0 focus-visible:outline-none"
                      data-testid={`recv-select-${r.receivable_id}`}
                    >
                      {r.outstanding_display}
                    </button>
                  </div>
                  <div role="cell" className="min-w-0 text-sm text-ink">
                    <Label>{t("recv3.col.due")}</Label>
                    <span data-testid={`recv-due-${r.receivable_id}`}>{r.due_when}</span>
                    {/* What the payment rests on, in the server's sentence (the same words the cash picture says). */}
                    {r.basis_text ? (
                      <span className="mt-0.5 block text-[13px] leading-snug text-ink-2" data-testid={`recv-basis-${r.receivable_id}`} data-basis={r.basis ?? undefined}>
                        {r.basis_text}
                      </span>
                    ) : null}
                  </div>
                  <div role="cell" className="col-span-2 min-w-0 space-y-1 lg:col-span-1">
                    <Label>{t("recv3.col.financing")}</Label>
                    {r.financing_state && r.financing_state !== "NONE" ? <div className="text-sm font-semibold tabular-nums text-ink">{r.net?.advance_display}</div> : null}
                    <FinancingSteps state={r.financing_state} testId={`recv-steps-${r.receivable_id}`} />
                  </div>
                  <div role="cell" className="min-w-0 text-sm font-bold tabular-nums text-ok-fg">
                    <Label>{t("recv3.col.net")}</Label>
                    {r.net?.unrecorded_text ? (
                      <span className="block font-medium text-warn-fg" data-testid={`recv-net-${r.receivable_id}`}>{r.net.unrecorded_text}</span>
                    ) : (
                      <span data-testid={`recv-net-${r.receivable_id}`}>{r.net?.net_short}</span>
                    )}
                  </div>
                  <div role="cell" className="min-w-0">
                    <Label>{t("recv3.col.status")}</Label>
                    <Badge tone={stateTone(r)} wrap>
                      <span data-testid={`recv-state-${r.receivable_id}`}>{r.collection_state_text}</span>
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

/** The column's name on a phone, where the header row is hidden. */
function Label({ children }: { children: string }) {
  return <span className="mb-0.5 block text-xs font-semibold uppercase tracking-wide text-ink-3 lg:hidden">{children}</span>;
}
