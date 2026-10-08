"use client";

import Link from "next/link";
import { CodeBadge, OpStatusBadge, TierBadge } from "@/components/badges";
import { SpanQuote } from "@/components/offer-parts";
import { Badge, Card, ErrorState, Hash, LoadingBlock, PageHeader } from "@/components/ui";
import { getAudit, getLedger, getState } from "@/lib/api";
import { API_MODE, STRATEGY_MVP } from "@/lib/config";
import { idsToNames } from "@/lib/business-words";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";
import { useAsync } from "@/lib/use-async";
import { Disclosure, FoldChevron } from "@/components/business/kit";
import { PilotJournal } from "@/components/business/pilot-journal";
import { decisionHref } from "@/components/business/open-decisions";

/** An empty section is one quiet line under the timeline, not a card around nothing (it keeps the section's id). */
function QuietLine({ id, title, children }: { id: string; title: string; children: string }) {
  return (
    <p id={id} className="text-sm text-ink-3">
      <span className="font-medium text-ink-2">{title}:</span> {children}
    </p>
  );
}

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
  const refusedEmpty = !!audit.data && !audit.error && !audit.data.events.length && !audit.data.refusals.length;

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
              <ol className="motion-rise divide-y divide-line" data-testid="activity-list">
                {ops.map((o) => (
                  <li key={`${o.seq}-${o.op_id}`} data-testid={`activity-${o.kind}`} data-status={o.status}>
                    {/* One list row: the sentence, its meta line and, at the trailing edge, the fold that holds the record. */}
                    <Disclosure
                      bare
                      summaryClass="flex cursor-pointer list-none flex-col gap-1 py-3 sm:flex-row sm:items-start sm:gap-4 [&::-webkit-details-marker]:hidden"
                      summary={
                        <>
                          <span className="min-w-0 flex-1">
                            <span className="block break-words text-sm font-medium text-ink" data-testid="activity-event">{o.event_text || o.message_when || words(o.summary) || kindLabel(o.kind)}</span>
                            {o.event_detail ? <span className="block break-words text-xs text-ink-2" data-testid="activity-detail">{o.event_detail}</span> : null}
                            <span className="mt-1 flex flex-wrap items-center gap-2">
                              <span className="text-xs text-ink-3">{whenText(o.day, today, t)}</span>
                              <span className="text-xs text-ink-3" data-testid="activity-op">{kindLabel(o.kind)}</span>
                              {/* Time passing is not an outcome to confirm: it carries no "Executed" chip. */}
                              {o.kind === "ADVANCE_CLOCK" && o.status === "EXECUTED" ? null : <OpStatusBadge status={o.status} />}
                              <span className="text-xs text-ink-3">{te("actor", o.requested_by)}</span>
                            </span>
                            {o.violations.length ? (
                              <span className="mt-1 flex flex-wrap gap-1">
                                {o.violations.map((v) => (
                                  <CodeBadge key={v.code} code={v.code} tone="bad" />
                                ))}
                              </span>
                            ) : null}
                          </span>
                          <span className="hit flex shrink-0 items-center gap-1 self-start text-xs font-medium text-brand-700 sm:min-h-8">
                            {t("biz.auditDetails")}
                            <FoldChevron />
                          </span>
                        </>
                      }
                    >
                      {o.decision_id ? (
                        <p className="pb-2 text-xs">
                          <Link href={decisionHref(o.decision_id)} className="inline-flex min-h-8 items-center font-medium text-brand-700 underline underline-offset-2 touch:min-h-11" data-testid="activity-record">
                            {t("biz.activity.record")}
                          </Link>
                        </p>
                      ) : null}
                      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 pb-3 text-xs text-ink-2">
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
              <p className="text-sm text-ink-3" data-testid="activity-empty">
                <span className="font-medium text-ink-2">{t("ledger.ops.empty")}.</span> {t("biz.activity.empty.body")}
              </p>
            )}
          </Card>

          {data.commitments.length ? (
            <Card id="activity-commitments" title={t("biz.activity.agreements")} subtitle={t("biz.activity.agreements.sub")}>
              <ul className="space-y-2">
                {data.commitments.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-tile border border-line px-3 py-2 text-sm">
                    <span>
                      <span className="font-medium text-ink">{words(c.counterparty_id)}</span>
                      <span className="block text-xs text-ink-3">
                        {t(c.expires_day < today ? "biz.activity.expired" : "biz.activity.expires", { when: whenText(c.expires_day, today, t) })} · {t("biz.activity.concessions")}: {c.forward_value_display}
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
            </Card>
          ) : (
            <QuietLine id="activity-commitments" title={t("biz.activity.agreements")}>
              {t("ledger.commitments.empty")}
            </QuietLine>
          )}

          {refusedEmpty ? (
            <QuietLine id="activity-refused" title={t("biz.activity.refused")}>
              {t("ledger.refusals.empty")}
            </QuietLine>
          ) : (
            <Card id="activity-refused" title={t("biz.activity.refused")} subtitle={t("biz.activity.refused.sub")}>
              {audit.error ? (
                <ErrorState error={audit.error} onRetry={audit.reload} />
              ) : !audit.data ? (
                <LoadingBlock rows={1} />
              ) : (
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
              )}
            </Card>
          )}

          <p className="text-xs text-ink-3">
            {t("biz.activity.trail")}{" "}
            <Link href="/evidence" className="inline-flex min-h-8 items-center font-medium text-brand-700 underline underline-offset-2 touch:min-h-11">
              {t("biz.activity.trail.open")}
            </Link>
          </p>

          {/* The shadow pilot's journal: read-only, only with the strategy build flag and a live API (the mock has none). */}
          {STRATEGY_MVP && API_MODE === "live" ? <PilotJournal /> : null}
        </div>
      )}
    </>
  );
}
