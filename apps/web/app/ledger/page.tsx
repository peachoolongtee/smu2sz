"use client";

import { CheckIcon, XIcon } from "@/components/icons";
import { CodeBadge, OpStatusBadge, TierBadge } from "@/components/badges";
import { SpanQuote } from "@/components/offer-parts";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Hash,
  LoadingBlock,
  PageHeader,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
import { getAudit, getLedger } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

export default function LedgerPage() {
  const { t, te } = useI18n();
  const ledger = useAsync(getLedger, []);
  const audit = useAsync(getAudit, []);
  const data = ledger.data;

  return (
    <>
      <PageHeader title={t("ledger.title")} subtitle={t("ledger.subtitle")} />
      {ledger.error ? (
        <ErrorState error={ledger.error} onRetry={ledger.reload} />
      ) : !data ? (
        <LoadingBlock rows={4} />
      ) : (
        <div className="space-y-6">
          <Card id="commitments" title={t("ledger.commitments")} subtitle={t("ledger.commitments.sub")}>
            {data.commitments.length ? (
              <TableWrap label={t("ledger.commitments")}>
                <table className={`${tableCls} min-w-[46rem]`}>
                  <caption className="sr-only">{t("ledger.commitments")}</caption>
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("common.id")}</th>
                      <th scope="col" className={thCls}>{t("ledger.counterparty")}</th>
                      <th scope="col" className={thCls}>{t("common.status")}</th>
                      <th scope="col" className={thCls}>{t("ledger.expires")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("ledger.forward")}</th>
                      <th scope="col" className={thCls}>{t("ledger.nonce")}</th>
                      <th scope="col" className={thCls}>{t("ledger.termsHash")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.commitments.map((c) => (
                      <tr key={c.id}>
                        <td className={`${tdCls} font-mono text-xs`}>{c.id}</td>
                        <td className={tdCls}>{c.counterparty_id}</td>
                        <td className={tdCls}>
                          <Badge tone={c.status === "ACTIVE" || c.status === "ACCEPTED" ? "ok" : "neutral"}>{te("commitment", c.status)}</Badge>
                        </td>
                        <td className={`${tdCls} tabular-nums`}>{t("common.dayN", { n: c.expires_day })}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{c.forward_value_display}</td>
                        <td className={`${tdCls} font-mono text-xs`}>{c.nonce}</td>
                        <td className={tdCls}>
                          <Hash value={c.terms_hash} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : (
              <EmptyState title={t("ledger.commitments.empty")} />
            )}
          </Card>

          <Card
            id="operations"
            title={t("ledger.ops")}
            subtitle={t("ledger.ops.sub")}
            actions={
              data.chain_length ? (
                <div className="flex flex-wrap items-center gap-2" data-testid="chain-status">
                  <Badge tone={data.chain_valid ? "ok" : "bad"}>
                    {data.chain_valid ? <CheckIcon /> : <XIcon />}
                    {data.chain_valid ? t("ledger.chainValid") : t("ledger.chainBroken")}
                  </Badge>
                  <span className="text-xs text-ink-3">{t("ledger.entries", { n: data.chain_length })}</span>
                </div>
              ) : undefined
            }
          >
            {data.operations.length ? (
              <TableWrap label={t("ledger.ops")}>
                <table className={`${tableCls} min-w-[64rem]`}>
                  <caption className="sr-only">{t("ledger.ops")}</caption>
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("ledger.seq")}</th>
                      <th scope="col" className={thCls}>{t("ledger.operation")}</th>
                      <th scope="col" className={thCls}>{t("common.status")}</th>
                      <th scope="col" className={thCls}>{t("ledger.tier")}</th>
                      <th scope="col" className={thCls}>{t("ledger.actor")}</th>
                      <th scope="col" className={thCls}>{t("ledger.prevHash")}</th>
                      <th scope="col" className={thCls}>{t("ledger.hash")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.operations.map((o) => (
                      <tr key={o.op_id} className={o.status === "REFUSED" ? "bg-bad-bg/50" : ""}>
                        <td className={`${tdCls} tabular-nums`}>{o.seq}</td>
                        <td className={`${tdCls} min-w-72`}>
                          <p className="font-medium">{te("opkind", o.kind)}</p>
                          <p className="text-xs text-ink-2">{o.summary}</p>
                          {o.violations.length ? (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {o.violations.map((v) => (
                                <CodeBadge key={v.code} code={v.code} tone="bad" />
                              ))}
                            </div>
                          ) : null}
                        </td>
                        <td className={tdCls}>
                          <OpStatusBadge status={o.status} />
                        </td>
                        <td className={tdCls}>
                          <TierBadge tier={o.tier} />
                        </td>
                        <td className={tdCls}>{te("actor", o.requested_by)}</td>
                        <td className={tdCls}>
                          <Hash value={o.prev_hash} />
                        </td>
                        <td className={tdCls}>
                          <Hash value={o.entry_hash} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : (
              <EmptyState title={t("ledger.ops.empty")} body={t("ledger.ops.empty.body")} />
            )}
          </Card>

          <Card id="refusals" title={t("ledger.refusals")} subtitle={t("ledger.refusals.sub")}>
            {audit.error ? (
              <ErrorState error={audit.error} onRetry={audit.reload} />
            ) : !audit.data ? (
              <LoadingBlock rows={2} />
            ) : audit.data.events.length || audit.data.refusals.length ? (
              <ul className="space-y-3">
                {audit.data.refusals.map((o) => (
                  <li key={o.op_id} className="rounded-lg border border-bad-line p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <OpStatusBadge status={o.status} />
                      <span className="text-sm font-medium">{te("opkind", o.kind)}</span>
                    </div>
                    <p className="mt-1 text-sm text-ink-2">{o.summary}</p>
                  </li>
                ))}
                {audit.data.events.map((e) => (
                  <li key={e.id} className="rounded-lg border border-bad-line p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <CodeBadge code={e.kind} tone="bad" />
                      <span className="text-sm">{e.action_taken}</span>
                    </div>
                    <p className="mt-1 text-sm text-ink-2">{e.detail}</p>
                    {e.spans.map((s) => (
                      <SpanQuote key={`${s.doc_id}:${s.start}`} text={s.text} />
                    ))}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-2">{t("ledger.refusals.empty")}</p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
