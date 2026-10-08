"use client";

import Link from "next/link";
import { CodeBadge, OpStatusBadge, TierBadge } from "@/components/badges";
import { SpanQuote } from "@/components/offer-parts";
import { Badge, Card, EmptyState, ErrorState, Hash, LoadingBlock, PageHeader } from "@/components/ui";
import { getAudit, getLedger, getState } from "@/lib/api";
import { idsToNames } from "@/lib/business-words";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";
import { useAsync } from "@/lib/use-async";
import { Disclosure } from "@/components/business/kit";

/**
 * Activity: everything that happened, in order. Each row leads with the server's business sentence (`event_text`: what happened, in the owner's
 * words); an older recording without it gets `message_when`, then the executor's sentence with ids named. The executor's own
 * sentence, the operation id, the tier and the hashes are under audit details.
 */
export default function ActivityPage() {
  const { t, te } = useI18n();
  const ledger = useAsync(getLedger, []);
  const audit = useAsync(getAudit, []);
  const books = useAsync(getState, []);
  const data = ledger.data;
  // Ids in the executor's sentences become names on this screen (the ids stay in the audit details).
  const named = [...(books.data?.state.facilities ?? []), ...(books.data?.state.counterparties ?? [])].map((x) => ({ id: x.id, name: x.name }));
  const words = (text: string) => idsToNames(text, named);
  // The plain name of an operation kind; a kind the dictionary does not know reads "Change", never the raw code.
  const kindLabel = (kind: string) => {
    const label = te("opkind", kind);
    return label && label !== kind ? label : t("biz.activity.kind.other");
  };
  const ops = data ? [...data.operations].reverse() : [];
  // Today, for the distances the Business pages show instead of day numbers (the books read carries the clock).
  const today = books.data?.day ?? ops[0]?.day ?? 0;

  return (
    <>
      <PageHeader
        section="activity"
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
              <ol className="motion-rise space-y-2" data-testid="activity-list">
                {ops.map((o) => (
                  <li key={`${o.seq}-${o.op_id}`} className={`rounded-tile border px-3 py-2 ${o.status === "REFUSED" ? "border-bad-line bg-bad-bg/40" : "border-line"}`} data-testid={`activity-${o.kind}`} data-status={o.status}>
                    <p className="break-words text-sm font-medium text-ink" data-testid="activity-event">{o.event_text || o.message_when || words(o.summary) || kindLabel(o.kind)}</p>
                    {o.event_detail ? <p className="break-words text-xs text-ink-2" data-testid="activity-detail">{o.event_detail}</p> : null}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-ink-3">{whenText(o.day, today, t)}</span>
                      <span className="text-xs text-ink-3" data-testid="activity-op">{kindLabel(o.kind)}</span>
                      <OpStatusBadge status={o.status} />
                      <span className="text-xs text-ink-3">{te("actor", o.requested_by)}</span>
                    </div>
                    {o.violations.length ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {o.violations.map((v) => (
                          <CodeBadge key={v.code} code={v.code} tone="bad" />
                        ))}
                      </div>
                    ) : null}
                    <Disclosure className="mt-1" summary={t("biz.auditDetails")}>
                      <dl className="mt-1 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs text-ink-2">
                        <dt>{t("audit.executor")}</dt>
                        <dd className="break-words" data-testid="activity-raw">{o.summary}</dd>
                        <dt>{t("audit.opId")}</dt>
                        <dd className="break-all font-mono">{o.op_id}</dd>
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
                    </Disclosure>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState title={t("ledger.ops.empty")} body={t("biz.activity.empty.body")} />
            )}
          </Card>

          <Card id="activity-commitments" title={t("biz.activity.agreements")} subtitle={t("biz.activity.agreements.sub")}>
            {data.commitments.length ? (
              <ul className="space-y-2">
                {data.commitments.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-tile border border-line px-3 py-2 text-sm">
                    <span>
                      <span className="font-medium text-ink">{words(c.counterparty_id)}</span>
                      <span className="block text-xs text-ink-3">
                        {t("ledger.expires")}: {whenText(c.expires_day, today, t)} · {t("biz.activity.concessions")}: {c.forward_value_display}
                      </span>
                    </span>
                    <Badge tone={c.status === "ACTIVE" || c.status === "ACCEPTED" ? "ok" : "neutral"}>{te("commitment", c.status)}</Badge>
                    {/* The agreement's record ids are the audit level, never the row. */}
                    <Disclosure className="basis-full" summary={t("biz.auditDetails")}>
                      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs text-ink-2">
                        <dt>{t("appr.commitment")}</dt>
                        <dd className="break-all font-mono" data-testid="activity-commitment-id">{c.id}</dd>
                        <dt>{t("appr.offer")}</dt>
                        <dd className="break-all font-mono">{`${c.offer_id} v${c.offer_version}`}</dd>
                      </dl>
                    </Disclosure>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">{t("ledger.commitments.empty")}</p>
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
                  <li key={`${o.seq}-${o.op_id}`} className="rounded-tile border border-bad-line px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <OpStatusBadge status={o.status} />
                      <span className="font-medium">{kindLabel(o.kind)}</span>
                    </div>
                    <p className="mt-1 text-ink-2">{o.event_text || o.message_when || words(o.summary)}</p>
                  </li>
                ))}
                {audit.data.events.map((e) => (
                  <li key={e.id} className="rounded-tile border border-bad-line px-3 py-2 text-sm">
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
