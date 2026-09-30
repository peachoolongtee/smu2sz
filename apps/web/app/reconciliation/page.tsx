"use client";

import { CheckIcon, XIcon } from "@/components/icons";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Hash,
  LoadingBlock,
  PageHeader,
  Stat,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
import { getReconciliation } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

export default function ReconciliationPage() {
  const { t, te } = useI18n();
  const recon = useAsync(getReconciliation, []);
  const data = recon.data;

  return (
    <>
      <PageHeader
        title={t("recon.title")}
        subtitle={t("recon.subtitle")}
        actions={data ? <span className="text-xs text-ink-3">{t("recon.asof", { day: data.as_of_day })}</span> : undefined}
      />

      {recon.error ? (
        <ErrorState error={recon.error} onRetry={recon.reload} />
      ) : !data ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-6">
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label={t("recon.matched")} value={data.matched} tone="ok" />
            <Stat label={t("recon.flagged")} value={data.flagged} tone={data.flagged ? "bad" : "neutral"} />
            <Stat label={t("recon.received")} value={data.received_total_display} />
            <Stat label={t("recon.expected")} value={data.expected_total_display} />
            <Stat
              label={t("recon.chain")}
              value={
                <Badge tone={data.chain_valid ? "ok" : "bad"}>
                  {data.chain_valid ? <CheckIcon /> : <XIcon />}
                  {data.chain_valid ? t("ledger.chainValid") : t("ledger.chainBroken")}
                </Badge>
              }
              hint={data.chain_head_hash ? <Hash value={data.chain_head_hash} /> : undefined}
            />
          </dl>

          <Card id="receipts" title={t("recon.receipts")} subtitle={t("recon.receipts.sub")}>
            {data.receipts.length ? (
              <TableWrap label={t("recon.receipts")}>
                <table className={`${tableCls} min-w-[52rem]`}>
                  <caption className="sr-only">{t("recon.receipts")}</caption>
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("recon.col.receivable")}</th>
                      <th scope="col" className={thCls}>{t("common.day")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("recon.col.received")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("recon.col.expected")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("recon.col.difference")}</th>
                      <th scope="col" className={thCls}>{t("recon.col.status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.receipts.map((r) => (
                      <tr key={r.entry_hash} className={r.flagged ? "bg-bad-bg/50" : ""} data-testid={`receipt-${r.op_id}`}>
                        <td className={tdCls}>
                          <p className="font-medium">{r.receivable_id}</p>
                          <p className="text-xs text-ink-2">{r.detail}</p>
                        </td>
                        <td className={`${tdCls} tabular-nums`}>{r.day ?? t("common.none")}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{r.received_display}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{r.expected_display ?? t("common.none")}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{r.difference_display ?? t("common.none")}</td>
                        <td className={tdCls}>
                          <Badge tone={r.flagged ? "bad" : "ok"}>{te("recstatus", r.status)}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : (
              <EmptyState title={t("recon.receipts.empty.title")} body={t("recon.receipts.empty.body")} />
            )}
          </Card>

          <Card id="outstanding" title={t("recon.outstanding")} subtitle={t("recon.outstanding.sub")}>
            {data.outstanding.length ? (
              <TableWrap label={t("recon.outstanding")}>
                <table className={tableCls}>
                  <caption className="sr-only">{t("recon.outstanding")}</caption>
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("recon.col.receivable")}</th>
                      <th scope="col" className={thCls}>{t("recon.col.counterparty")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("recon.col.face")}</th>
                      <th scope="col" className={thCls}>{t("recon.col.due")}</th>
                      <th scope="col" className={thCls}>{t("recon.col.status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.outstanding.map((o) => (
                      <tr key={o.receivable_id}>
                        <td className={`${tdCls} font-medium`}>{o.receivable_id}</td>
                        <td className={tdCls}>{o.counterparty_id}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{o.face_display}</td>
                        <td className={`${tdCls} tabular-nums`}>{t("common.dayN", { n: o.due_day })}</td>
                        <td className={tdCls}>
                          <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? t("recon.pastDue") : t("recon.onTime")}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : (
              <p className="text-sm text-ink-2">{t("recon.outstanding.empty")}</p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
