"use client";

import { Fragment, useState, type ReactNode } from "react";
import { Avatar, Disclosure, FoldChevron, initials, toneFor } from "@/components/business/kit";
import { ChasePayment } from "@/components/business/chase-payment";
import { CustomerName } from "@/components/customer-link";
import { ActionChip, ActionText, RankingNote, WorthSentence, WorthText } from "@/components/business/strategy";
import { Badge, toggleClass } from "@/components/ui";
import { usePageScope } from "@/lib/chat-scope";
import { isOverdue } from "@/lib/receivables-order";
import { useI18n } from "@/lib/i18n";
import type { OutstandingReceivable, ReceivableWorth, ReceivablesWorthView } from "@/lib/types";
import { daysLate, whenText } from "@/lib/when";

export type RecvFilter = "all" | "late" | "soon";


/** An invoice that is not late but falls due within this many days is "Due soon" (the page counts days; it computes no money). */
export const DUE_SOON_DAYS = 14;

/**
 * The open invoices: pill filters (All / Late / Due soon), then a table on a desktop and a stacked list on a phone, the same facts
 * in both. Level 1 per row: the buyer (monogram and name), the amount, when, the status, and with the strategy MVP's worth loaded
 * the server's rank as a numeral, the one worth figure and the action as a chip. The sentence for the step, the reason behind it
 * and the record ids (audit details) are one chevron down. The rows arrive in the order the page chose; this component filters
 * by days and never computes a figure. The filter is the page's (its red Overdue tile applies Late). When any invoice is overdue and the
 * whole list shows, the overdue rows sit first under "Overdue first" and the rest under the savings ranking; a filtered view has no headings.
 */
export function ReceivablesTable({
  invoices,
  asOfDay,
  buyerName,
  worth,
  worthOf,
  rank,
  chase,
  filter,
  onFilter,
  highlight = null,
}: {
  invoices: OutstandingReceivable[];
  asOfDay: number;
  buyerName: (id: string | null) => string;
  worth: ReceivablesWorthView | null | undefined;
  worthOf: Map<string, ReceivableWorth>;
  rank: Map<string, number>;
  /** The invoices that offer "Chase payment" (late, due inside the forecast's shortfall, or with a lapsed promise); the page chose them. */
  chase: Set<string>;
  filter: RecvFilter;
  onFilter: (f: RecvFilter) => void;
  /** The row the picture's mark pointed at: it takes a quiet tint and a brand edge until another is chosen. */
  highlight?: string | null;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState<Set<string>>(new Set());
  const isLate = (o: OutstandingReceivable) => isOverdue(o, worthOf.get(o.receivable_id));
  const isSoon = (o: OutstandingReceivable) => !isLate(o) && o.due_day - asOfDay <= DUE_SOON_DAYS;
  const late = invoices.filter(isLate).length;
  const soon = invoices.filter(isSoon).length;
  // A filter the list cannot honour (Late with nothing late) shows everything.
  const active: RecvFilter = (filter === "late" && late > 0) || (filter === "soon" && soon > 0) ? filter : "all";
  const shown = invoices.filter((o) => (active === "late" ? isLate(o) : active === "soon" ? isSoon(o) : true));
  // Overdue first: with the whole list showing and something overdue, the overdue rows are their own group above the rest.
  // Every row keeps the server's own rank numeral, so a pinned row shows where the savings ranking put it.
  const grouped = active === "all" && late > 0 && late < shown.length;
  const groups: { id: "overdue" | "rest" | "all"; heading: string | null; rows: OutstandingReceivable[] }[] = grouped
    ? [
        { id: "overdue", heading: t("biz.recv.group.overdue"), rows: shown.filter(isLate) },
        { id: "rest", heading: worth ? t("biz.recv.group.ranked") : t("biz.recv.group.rest"), rows: shown.filter((o) => !isLate(o)) },
      ]
    : [{ id: "all", heading: null, rows: shown }];
  // A filter that would repeat the whole list (one invoice, or all in one bucket) is not offered.
  const filters: { id: RecvFilter; label: string; n: number }[] = [
    { id: "all", label: t("biz.recv.filter.all"), n: invoices.length },
    ...(late > 0 ? [{ id: "late" as const, label: t("biz.recv.filter.late"), n: late }] : []),
    ...(soon > 0 ? [{ id: "soon" as const, label: t("biz.recv.filter.soon"), n: soon }] : []),
  ];
  const showFilters = invoices.length > 1 && filters.length > 1;
  // Ask FLOW is told which invoice row is open (an id only), so "What happens if this payment is late?" is about that one; the scope goes with the page.
  const openInvoice = invoices.find((o) => open.has(o.receivable_id));
  usePageScope(openInvoice ? { invoice: openInvoice.receivable_id, customer: openInvoice.counterparty_id } : null);
  const toggle = (id: string) => {
    setOpen((cur) => {
      const next = new Set(cur);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  };
  const status = (o: OutstandingReceivable) => (
    <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? daysLate(Math.max(0, asOfDay - o.due_day), t) : t("recon.onTime")}</Badge>
  );
  const cols = worth ? 7 : 5;

  return (
    <section id="recv-open" aria-labelledby="recv-open-title" className="scroll-mt-20">
      <div className="mb-3 border-b border-line pb-2">
        <h2 id="recv-open-title" className="text-base font-extrabold text-ink">
          {t("biz.recv.open")}
        </h2>
        <p className="text-supporting text-ink-3">{t("biz.recv.open.sub")}</p>
      </div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        {showFilters ? (
          <div role="group" aria-label={t("biz.recv.filter.label")} className="flex flex-wrap gap-1.5" data-testid="recv-filters">
            {filters.map((f) => (
              <button key={f.id} type="button" aria-pressed={active === f.id} onClick={() => onFilter(f.id)} className={toggleClass(active === f.id, "sm")} data-testid={`recv-filter-${f.id}`}>
                {f.label}
                <span className="tabular-nums text-ink-3">{f.n}</span>
              </button>
            ))}
          </div>
        ) : null}
        {worth ? <RankingNote worth={worth} /> : null}
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="recv-filter-none">
          {t("biz.recv.filter.none")}
        </p>
      ) : null}

      {/* On a phone the invoices are a list; the table needs the width of a larger screen. */}
      {shown.length ? (
        <div className="lg:hidden" data-testid="recv-open-list">
          {groups.map((g) => (
            <div key={g.id} data-testid={`recv-list-group-${g.id}`}>
              {g.heading ? <GroupHeading>{g.heading}</GroupHeading> : null}
              <ul className="motion-rise divide-y divide-line">
          {g.rows.map((o) => {
            const w = worthOf.get(o.receivable_id);
            const buyer = buyerName(o.counterparty_id);
            const n = rank.get(o.receivable_id);
            return (
              <li key={o.receivable_id} id={o.receivable_id} className={`scroll-mt-20 py-3 text-sm ${highlight === o.receivable_id ? "-mx-2 rounded-tile bg-brand-50 px-2" : ""}`} data-highlight={highlight === o.receivable_id ? "true" : undefined}>
                <div className="flex items-center gap-3">
                  <Avatar tone={toneFor(buyer)}>{initials(buyer)}</Avatar>
                  <span className="min-w-0 flex-1">
                    <span className="block break-words font-medium text-ink">
                      {worth && n !== undefined ? <span className="mr-1.5 tabular-nums text-ink-3">{n + 1}</span> : null}
                      <CustomerName id={o.counterparty_id}>{buyer}</CustomerName>
                    </span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-supporting text-ink-3">
                      <span>
                        {t("biz.due")} {whenText(o.due_day, asOfDay, t)}
                      </span>
                      {status(o)}
                    </span>
                  </span>
                  <span className="shrink-0 font-semibold tabular-nums text-ink">{o.face_display}</span>
                </div>
                {w ? (
                  <div className="mt-2 space-y-1.5 pl-12">
                    <div>
                      <span className="block text-supporting text-ink-3">{t("biz.strategy.worth")}</span>
                      <WorthText row={w} testId={`recv-list-worth-${o.receivable_id}`} />
                    </div>
                    <ActionChip action={w.action} />
                  </div>
                ) : null}
                {chase.has(o.receivable_id) ? <ChasePayment list className="mt-2 ml-12" receivableId={o.receivable_id} buyer={buyer} /> : null}
                <Disclosure className="mt-1 pl-12" summary={w ? t("biz.details.plan") : t("biz.auditDetails")}>
                  <RowDetail o={o} w={w} testId={`recv-list-action-${o.receivable_id}`} />
                </Disclosure>
              </li>
            );
          })}
              </ul>
            </div>
          ))}
        </div>
      ) : null}

      {shown.length ? (
        <div className="hidden lg:block">
          <div role="region" aria-label={t("biz.recv.open")} tabIndex={0} className="overflow-x-auto">
            <table className={tableCls}>
              <thead>
                <tr>
                  {worth ? (
                    <th scope="col" className={`${thCls} w-10 text-right`}>
                      <span aria-hidden>#</span>
                      <span className="sr-only">{t("biz.recv.rank")}</span>
                    </th>
                  ) : null}
                  <th scope="col" className={thCls}>{t("biz.buyer")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("biz.amount")}</th>
                  <th scope="col" className={thCls}>{t("biz.due")}</th>
                  <th scope="col" className={thCls}>{t("common.status")}</th>
                  {worth ? <th scope="col" className={`${thCls} text-right`}>{t("biz.strategy.worth")}</th> : null}
                  <th scope="col" className={thCls}>{worth ? t("biz.strategy.action") : <span className="sr-only">{t("biz.details.plan")}</span>}</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <Fragment key={g.id}>
                    {g.heading ? (
                      <tr data-testid={`recv-group-${g.id}`} data-group={g.id}>
                        <th scope="colgroup" colSpan={cols} className="border-b border-line px-3 pb-1.5 pt-3 text-left">
                          <GroupHeading table>{g.heading}</GroupHeading>
                        </th>
                      </tr>
                    ) : null}
                {g.rows.map((o) => {
                  const w = worthOf.get(o.receivable_id);
                  const buyer = buyerName(o.counterparty_id);
                  const n = rank.get(o.receivable_id);
                  const expanded = open.has(o.receivable_id);
                  const panel = `recv-detail-${o.receivable_id}`;
                  return [
                    <tr
                      key={o.receivable_id}
                      id={o.receivable_id}
                      className={`scroll-mt-20 ${highlight === o.receivable_id ? "bg-brand-50" : o.past_due ? "bg-bad-bg/40" : ""}`}
                      data-testid={`recv-${o.receivable_id}`}
                      data-highlight={highlight === o.receivable_id ? "true" : undefined}
                    >
                      {worth ? <td className={`${tdCls} text-right font-semibold tabular-nums text-ink-3`}>{n !== undefined ? n + 1 : ""}</td> : null}
                      <td className={`${tdCls} min-w-52 font-medium`}>
                        <span className="flex items-center gap-3">
                          <Avatar tone={toneFor(buyer)}>{initials(buyer)}</Avatar>
                          <span className="min-w-0 break-words">
                            <CustomerName id={o.counterparty_id}>{buyer}</CustomerName>
                          </span>
                        </span>
                      </td>
                      <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{o.face_display}</td>
                      <td className={`${tdCls} whitespace-nowrap tabular-nums`}>{whenText(o.due_day, asOfDay, t)}</td>
                      <td className={tdCls}>{status(o)}</td>
                      {worth ? <td className={`${tdCls} max-w-44 text-right`}>{w ? <WorthText row={w} testId={`recv-worth-${o.receivable_id}`} align="right" /> : null}</td> : null}
                      <td className={tdCls}>
                        <span className="flex items-center justify-between gap-2">
                          {w ? <ActionChip action={w.action} /> : <span />}
                          {chase.has(o.receivable_id) ? <ChasePayment receivableId={o.receivable_id} buyer={buyer} /> : null}
                          <button
                            type="button"
                            aria-expanded={expanded}
                            aria-controls={panel}
                            aria-label={`${t("biz.details.plan")}: ${buyer}`}
                            onClick={() => toggle(o.receivable_id)}
                            className="motion-press hit grid size-8 shrink-0 place-items-center rounded-pill hover:bg-subtle"
                            data-testid={`recv-toggle-${o.receivable_id}`}
                          >
                            <FoldChevron open={expanded} />
                          </button>
                        </span>
                      </td>
                    </tr>,
                    expanded ? (
                      <tr key={`${o.receivable_id}-detail`} id={panel} data-testid={panel}>
                        <td colSpan={cols} className="border-b border-line px-3 py-3">
                          <div className={worth ? "pl-12" : ""}>
                            <RowDetail o={o} w={w} testId={`recv-action-${o.receivable_id}`} />
                          </div>
                        </td>
                      </tr>
                    ) : null,
                  ];
                })}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

const tableCls = "w-full border-collapse text-left text-sm [&_tbody_tr:last-child_td]:border-b-0";
const thCls = "whitespace-nowrap border-b border-line-strong px-3 py-2 text-meta font-semibold uppercase tracking-wide text-ink-3";
const tdCls = "border-b border-line px-3 py-3 align-middle";

/** The small heading over a group of rows ("Overdue first", "Ranked by what collecting saves you"); in the table it is the row-group's header cell. */
function GroupHeading({ children, table = false }: { children: ReactNode; table?: boolean }) {
  const cls = "text-meta font-semibold uppercase tracking-wide text-ink-3";
  return table ? <span className={cls}>{children}</span> : <h3 className={`${cls} pb-1 pt-3 first:pt-0`}>{children}</h3>;
}

/**
 * What one chevron opens: the sentence for the step and the reason behind it (the server's text), then the record id as an audit
 * detail. With no worth loaded there is no sentence, so the id is all there is and it shows at once.
 */
function RowDetail({ o, w, testId }: { o: OutstandingReceivable; w: ReceivableWorth | undefined; testId: string }) {
  const { t } = useI18n();
  if (!w) return <p className="font-mono text-meta text-ink-3">{o.receivable_id}</p>;
  return (
    <div className="max-w-3xl space-y-2 text-sm">
      {w.no_saving ? null : <WorthSentence row={w} testId={`${testId}-worth`} />}
      <ActionText row={w} testId={testId} />
      <Disclosure summary={t("biz.auditDetails")} testId={`recv-audit-${o.receivable_id}`}>
        <p className="font-mono text-meta text-ink-3">{o.receivable_id}</p>
      </Disclosure>
    </div>
  );
}
