"use client";

import { Badge, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getReconciliation, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";
import { useAsync } from "@/lib/use-async";

/** Receivables: who owes what, who is late, what was promised early, what arrived. Names from the books; ids beside them. */
export default function ReceivablesPage() {
  const { t, te } = useI18n();
  const recon = useAsync(getReconciliation, []);
  const books = useAsync(getState, []);
  const data = recon.data;
  const name = (id: string | null) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id ?? "";

  return (
    <>
      <PageHeader title={t("nav.receivables")} subtitle={t("biz.recv.subtitle")} />
      {recon.error ? (
        <ErrorState error={recon.error} onRetry={recon.reload} />
      ) : !data ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-5">
          <Card id="recv-open" title={t("biz.recv.open")} subtitle={t("biz.recv.open.sub")}>
            {data.outstanding.length ? (
              <TableWrap label={t("biz.recv.open")}>
                <table className={tableCls}>
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("biz.buyer")}</th>
                      <th scope="col" className={thCls}>{t("biz.invoice")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("biz.amount")}</th>
                      <th scope="col" className={thCls}>{t("biz.due")}</th>
                      <th scope="col" className={thCls}>{t("common.status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.outstanding.map((o) => (
                      <tr key={o.receivable_id} className={o.past_due ? "bg-bad-bg/40" : ""} data-testid={`recv-${o.receivable_id}`}>
                        <td className={`${tdCls} font-medium`}>{name(o.counterparty_id)}</td>
                        <td className={`${tdCls} font-mono text-xs text-ink-2`}>{o.receivable_id}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{o.face_display}</td>
                        <td className={`${tdCls} tabular-nums`}>{whenText(o.due_day, data.as_of_day, t)}</td>
                        <td className={tdCls}>
                          <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? t("biz.recv.late", { days: Math.max(0, data.as_of_day - o.due_day) }) : t("recon.onTime")}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : (
              <EmptyState title={t("recon.outstanding.empty")} />
            )}
          </Card>

          <Card id="recv-promised" title={t("biz.recv.promised")} subtitle={t("biz.recv.promised.sub")} actions={data.lapsed_promises ? <Badge tone="bad">{`${t("recon.lapsed")}: ${data.lapsed_promises}`}</Badge> : undefined}>
            {data.promised?.length ? (
              <ul className="space-y-2">
                {data.promised.map((p) => (
                  <li key={`${p.commitment_id}:${p.obligation_id}:${p.receivable_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2 text-sm" data-testid={`promised-${p.receivable_id}`} data-status={p.status}>
                    <span>
                      <span className="font-medium text-ink">{name(p.counterparty_id)}</span>
                      <span className="block text-xs text-ink-2">{p.detail}</span>
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="font-semibold tabular-nums">{p.expected_display}</span>
                      <Badge tone={p.status === "RECEIVED" ? "ok" : p.status === "AWAITED" ? "info" : "bad"}>{te("promstatus", p.status)}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">{t("recon.promised.empty")}</p>
            )}
          </Card>

          <Card id="recv-receipts" title={t("biz.recv.receipts")} subtitle={t("biz.recv.receipts.sub", { matched: data.matched, flagged: data.flagged })}>
            {data.receipts.length ? (
              <ul className="space-y-2">
                {data.receipts.map((r) => (
                  <li key={r.entry_hash} className={`rounded-md border px-3 py-2 text-sm ${r.flagged ? "border-bad-line bg-bad-bg/40" : "border-line"}`} data-testid={`receipt-${r.op_id}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-ink">
                        {name(r.counterparty_id)} · {r.receivable_id}
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="font-semibold tabular-nums">{r.received_display}</span>
                        <Badge tone={r.flagged ? "bad" : "ok"}>{te("recstatus", r.status)}</Badge>
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-2">
                      {r.day !== null ? `${whenText(r.day, data.as_of_day, t)} · ` : ""}
                      {r.detail}
                    </p>
                    {r.bank_reference ? (
                      <p className="mt-0.5 font-mono text-xs text-ink-3" data-testid={`receipt-ref-${r.op_id}`}>
                        {t("recon.bankRef", { ref: r.bank_reference })}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">{t("recon.receipts.empty.body")}</p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
