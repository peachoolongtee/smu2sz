"use client";

import { Badge, Card, ErrorState, LoadingBlock, PageHeader, Stat, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getHome, getReceivablesWorth, getReconciliation, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { daysLate, whenText } from "@/lib/when";
import { useAsync, useStrategyAsync } from "@/lib/use-async";
import { Disclosure } from "@/components/business/kit";
import { ActionChip, ActionText, WorthText } from "@/components/business/strategy";

/**
 * Receivables, in the order the owner asks: who owes me and how much (the summary, from the home read), when and who is
 * late (the invoices, late first), what was promised early and what arrived. The last two appear only when there is
 * something to show. Names from the books; ids beside them.
 */
export default function ReceivablesPage() {
  const { t, te, lang } = useI18n();
  const recon = useAsync(getReconciliation, []);
  const books = useAsync(getState, []);
  const home = useAsync(() => getHome(lang), [lang]);
  // The worth of collecting each invoice (strategy MVP, build-time flag): null while loading, when the server has it off, or
  // when the read fails; the page then shows the table it always had. Matched to the invoices by receivable_id.
  const worth = useStrategyAsync(() => getReceivablesWorth(lang), [lang]).data;
  const worthOf = new Map((worth?.rows ?? []).map((w) => [w.receivable_id, w]));
  const data = recon.data;
  const r = home.data?.receivables;
  const name = (id: string | null) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id ?? "";
  // Late rows first, then by due day; the page counts days, the server does the money.
  // With the worth loaded the server's own rank leads (what collecting each saves), the rest keep the late-first order.
  const rank = new Map((worth?.rows ?? []).map((w, i) => [w.receivable_id, i]));
  const invoices = data
    ? [...data.outstanding].sort((a, b) => (rank.get(a.receivable_id) ?? rank.size) - (rank.get(b.receivable_id) ?? rank.size) || Number(b.past_due) - Number(a.past_due) || a.due_day - b.due_day)
    : [];
  const error = recon.error ?? home.error;

  return (
    <>
      <PageHeader section="recv" title={t("nav.receivables")} subtitle={t("biz.recv.subtitle")} />
      {error ? (
        <ErrorState error={error} onRetry={() => { recon.reload(); home.reload(); }} />
      ) : !data || !r ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-5">
          <section id="recv-summary" aria-label={t("nav.receivables")} data-testid="recv-summary">
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Stat label={t("biz.recv.sum.outstanding")} value={<span data-testid="recv-outstanding">{r.open_total_display}</span>} hint={t("biz.recv.sum.count", { n: r.open_count })} />
              <Stat
                label={t("biz.recv.sum.overdue")}
                value={<span data-testid="recv-overdue">{r.overdue_total_display}</span>}
                hint={r.past_due.length ? t("biz.recv.sum.overdue.n", { n: r.past_due.length }) : undefined}
                tone={r.past_due.length ? "bad" : "neutral"}
              />
              <Stat
                label={t("biz.recv.sum.next")}
                value={<span data-testid="recv-next-amount">{r.next_receipt ? r.next_receipt.face_display : "-"}</span>}
                hint={r.next_receipt ? <span data-testid="recv-next-hint">{t("biz.recv.sum.next.hint", { buyer: r.next_receipt.buyer_name, when: r.next_receipt.due_when })}</span> : undefined}
              />
            </dl>
            {r.open_count === 0 ? <p className="mt-3 text-sm text-ink-3" data-testid="recv-none">{t("recon.outstanding.empty")}</p> : null}
          </section>

          {invoices.length ? (
            <Card id="recv-open" title={t("biz.recv.open")} subtitle={t("biz.recv.open.sub")}>
              {worth ? (
                <p className="mb-3 text-xs text-ink-3" data-testid="recv-ranking-note">
                  {worth.ranking_note}
                </p>
              ) : null}
              {/* On a phone the invoices are a list; the table needs the width of a larger screen. */}
              <ul className="motion-rise divide-y divide-line sm:hidden" data-testid="recv-open-list">
                {invoices.map((o) => {
                  const w = worthOf.get(o.receivable_id);
                  return (
                  <li key={o.receivable_id} className="py-2.5 text-sm">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="min-w-0 font-medium text-ink">{name(o.counterparty_id)}</span>
                      <span className="shrink-0 font-semibold tabular-nums">{o.face_display}</span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-3">
                      <span>
                        {t("biz.due")} {whenText(o.due_day, data.as_of_day, t)}
                      </span>
                      <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? daysLate(Math.max(0, data.as_of_day - o.due_day), t) : t("recon.onTime")}</Badge>
                    </div>
                    {w ? (
                      <div className="mt-2 space-y-2">
                        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                          <ActionChip action={w.action} />
                          <div className="min-w-0 text-right">
                            <span className="block text-xs text-ink-3">{t("biz.strategy.worth")}</span>
                            <WorthText row={w} testId={`recv-list-worth-${o.receivable_id}`} />
                          </div>
                        </div>
                        <ActionText row={w} testId={`recv-list-action-${o.receivable_id}`} />
                      </div>
                    ) : null}
                  </li>
                  );
                })}
              </ul>
              <div className="hidden sm:block">
              <TableWrap label={t("biz.recv.open")}>
                <table className={tableCls}>
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("biz.buyer")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("biz.amount")}</th>
                      <th scope="col" className={thCls}>{t("biz.due")}</th>
                      <th scope="col" className={thCls}>{t("common.status")}</th>
                      {worth ? <th scope="col" className={thCls}>{t("biz.strategy.worth")}</th> : null}
                      {worth ? <th scope="col" className={thCls}>{t("biz.strategy.action")}</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((o) => {
                      const w = worthOf.get(o.receivable_id);
                      return (
                      <tr key={o.receivable_id} className={o.past_due ? "bg-bad-bg/40" : ""} data-testid={`recv-${o.receivable_id}`}>
                        <td className={`${tdCls} font-medium`}>
                          {name(o.counterparty_id)}
                          <span className="block font-mono text-xs font-normal text-ink-3">{o.receivable_id}</span>
                        </td>
                        <td className={`${tdCls} text-right tabular-nums`}>{o.face_display}</td>
                        <td className={`${tdCls} tabular-nums`}>{whenText(o.due_day, data.as_of_day, t)}</td>
                        <td className={tdCls}>
                          <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? daysLate(Math.max(0, data.as_of_day - o.due_day), t) : t("recon.onTime")}</Badge>
                        </td>
                        {worth ? (
                          <td className={tdCls}>{w ? <WorthText row={w} testId={`recv-worth-${o.receivable_id}`} /> : null}</td>
                        ) : null}
                        {worth ? (
                          <td className={`${tdCls} min-w-64 max-w-md`}>
                            {w ? (
                              <div className="space-y-1">
                                <ActionChip action={w.action} />
                                <ActionText row={w} testId={`recv-action-${o.receivable_id}`} />
                              </div>
                            ) : null}
                          </td>
                        ) : null}
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TableWrap>
              </div>
            </Card>
          ) : null}

          {data.promised?.length ? (
            <Card id="recv-promised" title={t("biz.recv.promised")} subtitle={t("biz.recv.promised.sub")} actions={data.lapsed_promises ? <Badge tone="bad">{`${t("recon.lapsed")}: ${data.lapsed_promises}`}</Badge> : undefined}>
              <ul className="motion-rise space-y-2">
                {data.promised.map((p) => (
                  <li key={`${p.commitment_id}:${p.obligation_id}:${p.receivable_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-tile border border-line px-3 py-2 text-sm" data-testid={`promised-${p.receivable_id}`} data-status={p.status}>
                    <span>
                      <span className="font-medium text-ink">{name(p.counterparty_id)}</span>
                      <span className="block text-xs text-ink-2">{p.detail_when ?? p.detail}</span>
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="font-semibold tabular-nums">{p.expected_display}</span>
                      <Badge tone={p.status === "RECEIVED" ? "ok" : p.status === "AWAITED" ? "info" : "bad"}>{te("promstatus", p.status)}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {data.receipts.length ? (
            <Card id="recv-receipts" title={t("biz.recv.receipts")} subtitle={t("biz.recv.receipts.sub", { matched: data.matched, flagged: data.flagged })}>
              <ul className="space-y-2">
                {data.receipts.map((x) => (
                  <li key={x.entry_hash} className={`rounded-tile border px-3 py-2 text-sm ${x.flagged ? "border-bad-line bg-bad-bg/40" : "border-line"}`} data-testid={`receipt-${x.op_id}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-ink">{name(x.counterparty_id)}</span>
                      <span className="flex items-center gap-2">
                        <span className="font-semibold tabular-nums">{x.received_display}</span>
                        <Badge tone={x.flagged ? "bad" : "ok"}>{te("recstatus", x.status)}</Badge>
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-2">
                      {x.day !== null ? `${whenText(x.day, data.as_of_day, t)} · ` : ""}
                      {x.detail_when ?? x.detail}
                    </p>
                    {/* The record ids (invoice, bank reference) are the audit level. */}
                    <Disclosure className="mt-1" testId={`receipt-audit-${x.op_id}`} summary={t("biz.auditDetails")}>
                      <p className="mt-1 text-xs text-ink-3">
                        {x.receivable_id}
                        {x.bank_reference ? (
                          <span data-testid={`receipt-ref-${x.op_id}`}>
                            {" · "}
                            {t("recon.bankRef", { ref: x.bank_reference })}
                          </span>
                        ) : null}
                      </p>
                    </Disclosure>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>
      )}
    </>
  );
}
