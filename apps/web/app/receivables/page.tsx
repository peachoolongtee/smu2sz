"use client";

import { PageIcon } from "@/components/business/kit";
import { InboxInIcon } from "@/components/icons";

import { Badge, Card, ErrorState, LoadingBlock, PageHeader, Stat, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getHome, getReconciliation, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";
import { localNames } from "@/lib/business-words";
import { useAsync } from "@/lib/use-async";

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
  const data = recon.data;
  const r = home.data?.receivables;
  const name = (id: string | null) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id ?? "";
  // Late rows first, then by due day; the page counts days, the server does the money.
  const invoices = data ? [...data.outstanding].sort((a, b) => Number(b.past_due) - Number(a.past_due) || a.due_day - b.due_day) : [];
  const error = recon.error ?? home.error;
  // An early payment that arrived is listed once, under the payments received; the promise list keeps what is still awaited.
  const promised = data?.promised?.filter((p) => p.status !== "RECEIVED") ?? [];
  // A commitment id in brackets is an audit detail, not something the owner reads.
  const plain = (text: string) => localNames(text.replace(/\s*\(commitment [^)]*\)/g, ""), lang);
  const lateLabel = (dueDay: number) => t("biz.recv.late", { days: Math.max(0, (data?.as_of_day ?? 0) - dueDay) });

  return (
    <>
      <PageHeader
        icon={
          <PageIcon tone="orange">
            <InboxInIcon width={22} height={22} />
          </PageIcon>
        }
        title={t("nav.receivables")} subtitle={t("biz.recv.subtitle")} />
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
              {/* On a phone the invoices are a list; the table needs the width of a larger screen. */}
              <ul className="space-y-2 sm:hidden" data-testid="recv-open-list">
                {invoices.map((o) => (
                  <li key={o.receivable_id} className={`rounded-md border px-3 py-2 text-sm ${o.past_due ? "border-bad-line bg-bad-bg/40" : "border-line"}`}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="min-w-0 font-medium text-ink">{name(o.counterparty_id)}</span>
                      <span className="shrink-0 font-semibold tabular-nums">{o.face_display}</span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-3">
                      <span>
                        {t("biz.due")} {whenText(o.due_day, data.as_of_day, t)} · {o.receivable_id}
                      </span>
                      <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? lateLabel(o.due_day) : t("recon.onTime")}</Badge>
                    </div>
                  </li>
                ))}
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
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((o) => (
                      <tr key={o.receivable_id} className={o.past_due ? "bg-bad-bg/40" : ""} data-testid={`recv-${o.receivable_id}`}>
                        <td className={`${tdCls} font-medium`}>
                          {name(o.counterparty_id)}
                          <span className="ml-2 text-xs font-normal text-ink-3">{o.receivable_id}</span>
                        </td>
                        <td className={`${tdCls} text-right tabular-nums`}>{o.face_display}</td>
                        <td className={`${tdCls} tabular-nums`}>{whenText(o.due_day, data.as_of_day, t)}</td>
                        <td className={tdCls}>
                          <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? lateLabel(o.due_day) : t("recon.onTime")}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
              </div>
            </Card>
          ) : null}

          {!promised.length && r.promised ? (
            <Card id="recv-promised" title={t("biz.recv.promised")} subtitle={t("biz.recv.promised.sub")}>
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2 text-sm" data-testid={`promised-${r.promised.receivable_id}`} data-status="AWAITED">
                <span>
                  <span className="font-medium text-ink">{r.promised.buyer_name}</span>
                  <span className="block text-xs text-ink-2">{t("biz.recv.promisedWhen", { when: r.promised.when ?? "" })}</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="font-semibold tabular-nums">{r.promised.expected_display}</span>
                  <Badge tone="info">{te("promstatus", "AWAITED")}</Badge>
                </span>
              </div>
            </Card>
          ) : null}

          {promised.length ? (
            <Card id="recv-promised" title={t("biz.recv.promised")} subtitle={t("biz.recv.promised.sub")} actions={data.lapsed_promises ? <Badge tone="bad">{`${t("recon.lapsed")}: ${data.lapsed_promises}`}</Badge> : undefined}>
              <ul className="space-y-2">
                {promised.map((p) => (
                  <li key={`${p.commitment_id}:${p.obligation_id}:${p.receivable_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2 text-sm" data-testid={`promised-${p.receivable_id}`} data-status={p.status}>
                    <span>
                      <span className="font-medium text-ink">{name(p.counterparty_id)}</span>
                      <span className="block text-xs text-ink-2">{plain(p.detail)}</span>
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
                  <li key={x.entry_hash} className={`rounded-md border px-3 py-2 text-sm ${x.flagged ? "border-bad-line bg-bad-bg/40" : "border-line"}`} data-testid={`receipt-${x.op_id}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-ink">
                        {name(x.counterparty_id)}
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="font-semibold tabular-nums">{x.received_display}</span>
                        <Badge tone={x.flagged ? "bad" : "ok"}>{te("recstatus", x.status)}</Badge>
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-2">
                      {x.day !== null ? `${whenText(x.day, data.as_of_day, t)} · ` : ""}
                      {plain(x.detail)}
                    </p>
                    {x.bank_reference ? (
                      <p className="mt-0.5 text-xs text-ink-3" data-testid={`receipt-ref-${x.op_id}`}>
                        {t("recon.bankRef", { ref: x.bank_reference })}
                      </p>
                    ) : null}
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
