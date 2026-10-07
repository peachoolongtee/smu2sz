"use client";

import { PageIcon } from "@/components/business/kit";
import { ActivityIcon } from "@/components/icons";

import Link from "next/link";
import { CodeBadge, OpStatusBadge, TierBadge } from "@/components/badges";
import { SpanQuote } from "@/components/offer-parts";
import { Badge, Card, ErrorState, Hash, LoadingBlock, PageHeader } from "@/components/ui";
import { getApprovals, getAudit, getLedger, getState } from "@/lib/api";
import { idsToNames, localNames, plainDays } from "@/lib/business-words";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";
import { useAsync } from "@/lib/use-async";

/** Activity: everything that happened, in order, in the executor's own sentences; the hashes and codes under audit details. */
export default function ActivityPage() {
  const { t, te, lang } = useI18n();
  const ledger = useAsync(getLedger, []);
  const audit = useAsync(getAudit, []);
  const books = useAsync(getState, []);
  // A request queued for the owner stays "waiting" in the log; the approvals queue says whether it was decided since.
  const approvals = useAsync(() => getApprovals().catch(() => []), []);
  const data = ledger.data;
  const ops = data ? [...data.operations].reverse() : [];
  // Today, for the distances the Business pages show instead of day numbers (the books read carries the clock).
  const today = books.data?.day ?? ops[0]?.day ?? 0;
  // Ids in the executor's sentences become names on this screen, as whole words only (the ids stay in the audit
  // details), and day numbers become distances from today.
  const named = [...(books.data?.state.facilities ?? []), ...(books.data?.state.counterparties ?? [])].map((x) => ({ id: x.id, name: x.name }));
  const words = (text: string) => localNames(plainDays(idsToNames(text, named), today, t), lang);
  // Matched by the operation id, or by the approval number the executor writes into the entry ("APR-000001").
  const decidedLater = (o: { op_id: string; summary: string }) =>
    approvals.data?.find((a) => a.status !== "PENDING" && (a.op_id === o.op_id || o.summary.includes(`(${a.id})`)))?.status ?? null;

  return (
    <>
      <PageHeader
        icon={
          <PageIcon tone="pink">
            <ActivityIcon width={22} height={22} />
          </PageIcon>
        }
        title={t("nav.activity")}
        subtitle={t("biz.activity.subtitle")}
        actions={
          data?.chain_length ? (
            <div className="flex items-center gap-2" data-testid="chain-status">
              <Badge tone={data.chain_valid ? "ok" : "bad"} title={`${data.chain_valid ? t("ledger.chainValid") : t("ledger.chainBroken")} · ${t("ledger.entries", { n: data.chain_length })}`}>
                {data.chain_valid ? t("biz.activity.chainOk") : t("biz.activity.chainBroken")}
              </Badge>
            </div>
          ) : undefined
        }
      />
      {ledger.error ? (
        <ErrorState error={ledger.error} onRetry={ledger.reload} />
      ) : !data ? (
        <LoadingBlock rows={4} />
      ) : (
        <div className="space-y-5">
          <Card id="activity-timeline" title={t("biz.activity.timeline")} subtitle={t("biz.activity.timeline.sub")}>
            {ops.length ? (
              <ol className="-mx-1 divide-y divide-line" data-testid="activity-list">
                {ops.map((o) => (
                  <li key={`${o.seq}-${o.op_id}`} className={`px-1 py-3 ${o.status === "REFUSED" ? "text-bad-fg" : ""}`} data-testid={`activity-${o.kind}`} data-status={o.status}>
                    <p className="break-words font-medium text-ink">{words(o.summary) || te("opkind", o.kind) || o.kind}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-ink-3">{whenText(o.day, today, t)}</span>
                      <span className="text-xs text-ink-3" data-testid="activity-op">{te("opkind", o.kind) || o.kind}</span>
                      {o.status === "PENDING_APPROVAL" && decidedLater(o) ? (
                        <Badge tone={decidedLater(o) === "APPROVED" ? "ok" : "neutral"}>
                          {decidedLater(o) === "APPROVED" ? t("biz.activity.approvedLater") : t("biz.activity.declinedLater")}
                        </Badge>
                      ) : (
                        <OpStatusBadge status={o.status} />
                      )}
                      <span className="text-xs text-ink-3">· {te("actor", o.requested_by)}</span>
                    </div>
                    {o.violations.length ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {o.violations.map((v) => (
                          <CodeBadge key={v.code} code={v.code} tone="bad" />
                        ))}
                      </div>
                    ) : null}
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs text-ink-3">{t("biz.auditDetails")}</summary>
                      <dl className="mt-1 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs text-ink-2">
                        <dt>{t("ledger.seq")}</dt>
                        <dd className="tabular-nums">{o.seq}</dd>
                        <dt>{t("ledger.tier")}</dt>
                        <dd>
                          <TierBadge tier={o.tier} />
                        </dd>
                        <dt>{t("ledger.hash")}</dt>
                        <dd>
                          <Hash value={o.entry_hash} />
                        </dd>
                        <dt>{t("ledger.prevHash")}</dt>
                        <dd>
                          <Hash value={o.prev_hash} />
                        </dd>
                      </dl>
                    </details>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-ink-3">{t("biz.activity.empty.body")}</p>
            )}
          </Card>

          <Card id="activity-commitments" title={t("biz.activity.agreements")} subtitle={t("biz.activity.agreements.sub")}>
            {data.commitments.length ? (
              <ul className="space-y-2">
                {data.commitments.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2 text-sm">
                    <span>
                      <span className="font-medium text-ink">{idsToNames(c.counterparty_id, named)}</span>
                      <span className="block text-xs text-ink-3">
                        {t("ledger.expires")}: {whenText(c.expires_day, today, t)} · {t("biz.deals.giveaways")}: {c.forward_value_display}
                      </span>
                    </span>
                    <span className="flex items-center gap-2">
                      <Badge tone={c.status === "ACTIVE" || c.status === "ACCEPTED" ? "ok" : "neutral"}>{te("commitment", c.status)}</Badge>

                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">{t("biz.activity.agreements.empty")}</p>
            )}
          </Card>

          <Card id="activity-refused" title={t("biz.activity.refused")} subtitle={t("biz.activity.refused.sub")}>
            {audit.error ? (
              <ErrorState error={audit.error} onRetry={audit.reload} />
            ) : !audit.data ? (
              <LoadingBlock rows={1} />
            ) : audit.data.events.length || audit.data.refusals.length ? (
              <ul className="space-y-2">
                {audit.data.refusals.map((o) => (
                  <li key={`${o.seq}-${o.op_id}`} className="rounded-md border border-bad-line px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <OpStatusBadge status={o.status} />
                      <span className="font-medium">{te("opkind", o.kind)}</span>
                    </div>
                    <p className="mt-1 text-ink-2">{words(o.summary)}</p>
                  </li>
                ))}
                {audit.data.events.map((e) => (
                  <li key={e.id} className="rounded-md border border-bad-line px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{te("secevent", e.kind)}</span>
                      <span className="text-xs text-ink-3">{e.action_taken}</span>
                    </div>
                    <p className="mt-1 text-ink-2">{e.detail}</p>
                    {e.spans.map((s) => (
                      <SpanQuote key={`${s.doc_id}:${s.start}`} text={s.text} />
                    ))}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">{t("ledger.refusals.empty")}</p>
            )}
          </Card>

          <p className="text-xs text-ink-3">
            {t("biz.activity.trail")}{" "}
            <Link href="/evidence" className="font-medium text-brand-700 underline underline-offset-2">
              {t("biz.activity.trail.open")}
            </Link>
          </p>
        </div>
      )}
    </>
  );
}
