"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { CodeBadge, OpStatusBadge, TierBadge } from "@/components/badges";
import { BankIcon, SparkIcon, StoreIcon, UserIcon } from "@/components/icons";
import { CustomerName } from "@/components/customer-link";
import { StateWord } from "@/components/ui/state-word";
import { SpanQuote } from "@/components/offer-parts";
import { Badge, ErrorState, Hash, LoadingBlock, PageHeader } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { getAudit, getLedger, getState } from "@/lib/api";
import { API_MODE, STRATEGY_MVP } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";
import { useAsync } from "@/lib/use-async";
import { Disclosure, FoldChevron } from "@/components/business/kit";
import { PilotJournal } from "@/components/business/pilot-journal";
import { ReconciliationSection } from "@/components/business/reconciliation-section";
import { FoldCard } from "@/components/business/surface";
import { decisionHref } from "@/components/business/open-decisions";
import type { OperationView } from "@/lib/types";

/** An empty section is a small card with its one line (it keeps the section's id). */
function QuietLine({ id, title, children }: { id: string; title: string; children: string }) {
  return (
    <section id={id} className="card-flat" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="font-display text-base font-extrabold text-ink">
        {title}
      </h2>
      <p className="mt-1 text-sm text-ink-3">{children}</p>
    </section>
  );
}

/** A section as a card: its title, a quiet line under it, then the rows. */
function Section({ id, title, sub, children }: { id: string; title: string; sub?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="card-flat scroll-mt-20">
      <div className="mb-1 border-b border-line pb-2">
        <h2 id={`${id}-title`} className="font-display text-lg font-extrabold text-ink">
          {title}
        </h2>
        {sub ? <p className="text-supporting text-ink-3">{sub}</p> : null}
      </div>
      {children}
    </section>
  );
}

type View = "timeline" | "recon";

/** The approval request's row line: the label of what it was ("Approval requested"), the decision's state today, and the way to the record. */
function ApprovalLine({ o }: { o: OperationView }) {
  const { t } = useI18n();
  const href = o.decision_link?.href ?? (o.decision_id ? decisionHref(o.decision_id) : null);
  return (
    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-ink-2" data-testid="activity-approval">
      <span className="font-medium text-ink">{o.approval_label}</span>
      {o.current_decision_state ? <span data-testid="activity-approval-state">{t("biz.activity.stateNow", { state: o.current_decision_state })}</span> : null}
      {href ? (
        <Link href={href} className="inline-flex min-h-8 items-center font-medium text-brand-700 underline underline-offset-2 touch:min-h-11" data-testid="activity-record">
          {t("biz.activity.record")}
        </Link>
      ) : null}
    </p>
  );
}

/** What kind of entry it is, for the filter chips: a fixed map of the operation kinds; a kind not listed shows under All only. */
type Category = "money" | "decisions" | "documents";
const CATEGORY: Record<string, Category> = {
  DRAW_FACILITY: "money",
  REPAY_FACILITY: "money",
  SUBMIT_INVOICE_FOR_FINANCING: "money",
  RECEIVE_PAYMENT: "money",
  APPLY_FOR_FACILITY: "money",
  ADD_FACILITY: "money",
  SIGN_PERSONAL_GUARANTEE: "money",
  PLEDGE_COLLATERAL: "money",
  ISSUE_EQUITY: "money",
  ACCEPT_OFFER: "decisions",
  COUNTER_OFFER: "decisions",
  REJECT_OFFER: "decisions",
  RECORD_COMMITMENT: "decisions",
  REQUEST_OWNER_APPROVAL: "decisions",
  CHANGE_MANDATE: "decisions",
  NEGOTIATE: "decisions",
  VERIFY: "decisions",
  CONFIRM_DOCUMENT: "documents",
  REJECT_DOCUMENT: "documents",
};
type Filter = "all" | Category;

/** Who acted, as an icon on the rail (the word is beside the status): you, FLOW, the bank or system, the buyer. */
function Actor({ who }: { who: "you" | "agent" | "system" | "buyer" }) {
  const look = {
    you: ["bg-brand-50 text-brand-700", <UserIcon key="i" width={16} height={16} />],
    agent: ["bg-sec-home-bg text-sec-home-fg", <SparkIcon key="i" width={16} height={16} />],
    system: ["bg-subtle text-ink-2", <BankIcon key="i" width={16} height={16} />],
    buyer: ["bg-sec-deals-bg text-sec-deals-fg", <StoreIcon key="i" width={16} height={16} />],
  }[who];
  return (
    <span aria-hidden className={`relative z-10 grid size-8 place-items-center rounded-pill ring-4 ring-surface ${look[0]}`} data-actor={who}>
      {look[1]}
    </span>
  );
}

/**
 * Activity: what happened, in order, and who did it. The title is the server's "now" sentence; below it a vertical rail with a day caption per day, a
 * node per entry (an icon for who acted, the server's business sentence as the title, the status, one line of detail and a quiet "Details" toggle that
 * opens the audit details), and thin separators where time passed. Filter chips narrow the rail by kind and never change its order. The agreements,
 * what was refused and the chain scope sit unboxed below.
 */
export default function ActivityPage() {
  const { t, te, lang } = useI18n();
  const ledger = useAsync(() => getLedger(lang), [lang]);
  const audit = useAsync(getAudit, [lang]);
  const books = useAsync(getState, []);
  const [filter, setFilter] = useState<Filter>("all");
  // The two parts of the page: the timeline, and the reconciliation log (opened directly by `#reconciliation`).
  const [view, setView] = useState<View>("timeline");
  // The address is read once the page is on screen (the server cannot see a hash): `#reconciliation` opens the log.
  useEffect(() => {
    if (window.location.hash !== "#reconciliation") return;
    const frame = window.requestAnimationFrame(() => setView("recon"));
    return () => window.cancelAnimationFrame(frame);
  }, []);
  const data = ledger.data;
  // The server's sentences hold no ids; the one id this page shows is an agreement's buyer, said by name.
  const buyerName = (id: string) => books.data?.state.counterparties.find((x) => x.id === id)?.name ?? id;
  // The plain name of an operation kind; a kind the dictionary does not know reads "Change", never the raw code.
  const kindLabel = (kind: string) => {
    const label = te("opkind", kind);
    return label && label !== kind ? label : t("biz.activity.kind.other");
  };
  const ops = data ? [...data.operations].reverse() : [];
  const decisionOf = (o: OperationView) => o.decision_link?.decision_id ?? o.decision_id ?? null;
  // A request that waited for the owner is history once a later entry of the same decision ran (the owner decided).
  const decidedSince = (o: OperationView) => o.status === "PENDING_APPROVAL" && decisionOf(o) !== null && ops.some((x) => decisionOf(x) === decisionOf(o) && (x.seq ?? 0) > (o.seq ?? 0) && x.status !== "PENDING_APPROVAL");
  // The entry that ran after a request waited is the owner's decision (the agent only asked): the actor is "You".
  const ownerDecided = (o: OperationView) => o.status !== "PENDING_APPROVAL" && decisionOf(o) !== null && ops.some((x) => decisionOf(x) === decisionOf(o) && (x.seq ?? 0) < (o.seq ?? 0) && x.status === "PENDING_APPROVAL");
  // Today, for the distances the Business pages show instead of day numbers (the books read carries the clock).
  const today = books.data?.day ?? ops[0]?.day ?? 0;
  const nowLine = ops.find((o) => o.why_it_matters && o.why_it_matters_as_of === "now")?.why_it_matters ?? null;
  const refusedEmpty = !!audit.data && !audit.error && !audit.data.events.length && !audit.data.refusals.length;
  const sentenceOf = (o: OperationView) => o.what_changed || o.event_text || o.message_when || kindLabel(o.kind);
  const passed = (o: OperationView) => o.kind === "ADVANCE_CLOCK" && o.status === "EXECUTED";
  const whoOf = (o: OperationView): "you" | "agent" | "system" | "buyer" =>
    ownerDecided(o) || o.requested_by === "OWNER" || o.requested_by === null ? "you" : o.requested_by === "AGENT" ? "agent" : o.requested_by === "COUNTERPARTY" ? "buyer" : "system";

  // The chips: only a kind that has entries; none at all when one kind would repeat the whole rail.
  const counts: Record<Category, number> = { money: 0, decisions: 0, documents: 0 };
  for (const o of ops) if (!passed(o) && CATEGORY[o.kind]) counts[CATEGORY[o.kind]] += 1;
  const kinds = (["money", "decisions", "documents"] as const).filter((c) => counts[c] > 0);
  const entries = ops.filter((o) => !passed(o)).length;
  const showChips = kinds.length > 1 || (kinds.length === 1 && counts[kinds[0]] < entries);
  const active: Filter = filter === "all" || counts[filter] > 0 ? filter : "all";
  const shown = ops.filter((o) => (active === "all" ? true : !passed(o) && CATEGORY[o.kind] === active));
  // Groups by the entry's day number, in the list's order; the caption is the first entry's distance from today, in the dictionary's words.
  const groups: { day: number; rows: OperationView[] }[] = [];
  for (const o of shown) {
    const g = groups[groups.length - 1];
    if (g && g.day === o.day) g.rows.push(o);
    else groups.push({ day: o.day, rows: [o] });
  }

  return (
    <>
      <PageHeader
        section="activity"
        title={
          nowLine ? (
            <span data-testid="activity-now" className="break-words">
              {nowLine}
            </span>
          ) : (
            t("nav.activity")
          )
        }
        subtitle={t("biz.activity.subtitle")}
        actions={
          data?.chain_length ? (
            <div className="flex items-center gap-2" data-testid="chain-status">
              {/* The badge says only what the check does: the log's own hash chain. Hidden while the server has no words for it (an empty log). */}
              {data.chain_text !== null ? (
                <Badge tone={data.chain_valid ? "ok" : "bad"} title={`${data.chain_scope_text ?? ""} ${t("ledger.entries", { n: data.chain_length })}`.trim()}>
                  {data.chain_text ?? (data.chain_valid ? t("biz.activity.chainOk") : t("biz.activity.chainBroken"))}
                </Badge>
              ) : null}
            </div>
          ) : undefined
        }
      />
      {ledger.error ? (
        <ErrorState error={ledger.error} onRetry={ledger.reload} />
      ) : !data ? (
        <LoadingBlock rows={4} />
      ) : (
        <div className="space-y-6">
          <SegmentedTabs
            label={t("biz.activity.view")}
            value={view}
            onChange={setView}
            testId="activity-view"
            tabs={[
              { value: "timeline" as View, label: t("biz.activity.view.timeline"), testId: "activity-view-timeline" },
              { value: "recon" as View, label: t("biz.activity.view.recon"), testId: "activity-view-recon" },
            ]}
          />
          {view === "recon" ? <ReconciliationSection today={today} buyerName={buyerName} /> : (
          <>
          <section id="activity-timeline" aria-label={t("biz.activity.rail")} className="card-flat">
            <p className="mb-3 text-meta text-ink-3">{t("biz.activity.timeline.sub")}</p>
            {showChips ? (
              <div className="mb-4">
                <SegmentedTabs
                  label={t("biz.activity.filter.label")}
                  value={active}
                  onChange={setFilter}
                  testId="activity-filters"
                  tabs={([["all", t("biz.activity.filter.all"), entries], ...kinds.map((c) => [c, t(`biz.activity.filter.${c}`), counts[c]] as const)] as const).map(([id, label, n]) => ({
                    value: id as Filter,
                    label,
                    badge: n,
                    testId: `activity-filter-${id}`,
                  }))}
                />
              </div>
            ) : null}
            {ops.length ? (
              <div className="relative before:absolute before:bottom-2 before:left-4 before:top-2 before:w-px before:bg-line-strong" data-testid="activity-list">
                {groups.map((g) => (
                  <div key={`${g.day}-${g.rows[0].seq}`} className="motion-rise" data-testid="activity-day">
                    <h3 className="relative z-10 pb-1 pl-12 pt-5 text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3 first:pt-0" data-testid="activity-day-caption">
                      <span className="inline-block first-letter:uppercase">{g.rows[0].day_when || whenText(g.day, today, t)}</span>
                    </h3>
                    <ol>
                      {g.rows.map((o) =>
                        passed(o) ? (
                          // Time passing is a thin separator on the rail carrying its sentence, not an entry.
                          <li key={`${o.seq}-${o.op_id}`} className="relative flex items-center gap-3 py-1.5" data-testid={`activity-${o.kind}`} data-status={o.status}>
                            <span aria-hidden className="relative z-10 ml-[11px] size-2.5 rounded-pill border-2 border-line-strong bg-surface" />
                            <p className="flex min-w-0 flex-wrap items-baseline gap-x-2 break-words text-meta text-ink-3">
                              <span data-testid="activity-event">{sentenceOf(o)}</span>
                              <span className="font-medium" data-testid="activity-op">
                                {o.kind_text ?? kindLabel(o.kind)}
                              </span>
                            </p>
                          </li>
                        ) : (
                          <li key={`${o.seq}-${o.op_id}`} className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-x-4 py-3" data-testid={`activity-${o.kind}`} data-status={o.status}>
                            <Actor who={whoOf(o)} />
                            <div className="min-w-0 pr-24">
                              <p className="break-words text-sm font-semibold text-ink" data-testid="activity-event">
                                {sentenceOf(o)}
                              </p>
                              {o.event_detail ? (
                                <p className="mt-0.5 break-words text-meta text-ink-2" data-testid="activity-detail">
                                  {o.event_detail}
                                </p>
                              ) : null}
                              {o.why_it_matters && o.why_it_matters_as_of !== "now" && o.why_it_matters_changed !== false ? (
                                <p className="mt-1 break-words text-sm text-ink-2" data-testid="activity-why">
                                  <span className="font-medium text-ink-3">{t("biz.activity.why")}:</span> {o.why_it_matters}
                                </p>
                              ) : null}
                              {o.what_remains ? (
                                <p className="mt-0.5 break-words text-meta text-ink-2" data-testid="activity-remains">
                                  <span className="font-medium text-ink-3">{t("biz.activity.remains")}</span>
                                  {": "}
                                  {o.what_remains}
                                </p>
                              ) : null}
                              {/* An approval request is history: it says it was requested, where the decision stands today, and links to it. */}
                              {o.approval_label ? <ApprovalLine o={o} /> : null}
                              <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                                {decidedSince(o) && o.current_decision_state ? (
                                  // The request is history once the owner has decided: it wears where the decision stands today, not "Waiting for your approval".
                                  <StateWord tone="neutral" testId="activity-request-state">
                                    {o.current_decision_state}
                                  </StateWord>
                                ) : (
                                  <OpStatusBadge status={o.status} />
                                )}
                                <span className="text-meta text-ink-3" data-testid="activity-op">
                                  {o.kind_text ?? kindLabel(o.kind)}
                                </span>
                                <span className="text-meta text-ink-3" data-testid="activity-actor">
                                  {ownerDecided(o) ? t("biz.activity.you") : te("actor", o.requested_by)}
                                </span>
                              </p>
                              {o.violations.length ? (
                                <p className="mt-1 flex flex-wrap gap-1">
                                  {o.violations.map((v) => (
                                    <CodeBadge key={v.code} code={v.code} tone="bad" />
                                  ))}
                                </p>
                              ) : null}
                              {/* The owner's decision on a contract the agent read: the entry opens the document it names. */}
                              {o.document_id ? (
                                <Link href={`/documents?id=${o.document_id}`} className="mt-1 inline-block text-meta font-medium text-brand-700 underline underline-offset-2" data-testid="activity-document-link">
                                  {t("deals.summary.contract")}
                                </Link>
                              ) : null}
                            </div>
                            {/* One quiet toggle at the right opens the audit details (the executor's sentence, the ids, the tier and the hashes). */}
                            <Disclosure
                              bare
                              className="col-span-2 text-meta"
                              summaryClass="absolute right-0 top-2 inline-flex min-h-8 cursor-pointer list-none items-center gap-0.5 rounded-pill px-2.5 text-meta font-medium text-ink-3 hover:bg-subtle hover:text-ink touch:min-h-11 [&::-webkit-details-marker]:hidden"
                              summary={
                                <span className="inline-flex items-center gap-0.5" data-testid="activity-details-toggle">
                                  {t("biz.activity.details")}
                                  <FoldChevron />
                                </span>
                              }
                            >
                              <div className="pb-1 pl-12 pt-1">
                                {o.decision_id && !o.approval_label ? (
                                  <p className="pb-2 text-meta">
                                    <Link href={o.decision_link?.href ?? decisionHref(o.decision_id)} className="inline-flex min-h-8 items-center font-medium text-brand-700 underline underline-offset-2 touch:min-h-11" data-testid="activity-record">
                                      {t("biz.activity.record")}
                                    </Link>
                                  </p>
                                ) : null}
                                <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 pb-1 text-meta text-ink-2">
                                  <dt>{t("audit.executor")}</dt>
                                  <dd className="break-words" data-testid="activity-raw">
                                    {o.summary}
                                  </dd>
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
                              </div>
                            </Disclosure>
                          </li>
                        ),
                      )}
                    </ol>
                  </div>
                ))}
                {shown.length === 0 ? (
                  <p className="pl-12 text-sm text-ink-3" data-testid="activity-filter-none">
                    {t("biz.activity.filter.none")}
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-ink-3" data-testid="activity-empty">
                <span className="font-medium text-ink-2">{t("ledger.ops.empty")}.</span> {t("biz.activity.empty.body")}
              </p>
            )}
          </section>

          <div className="grid items-start gap-4 lg:grid-cols-2">
          {data.commitments.length ? (
            <Section id="activity-commitments" title={t("biz.activity.agreements")} sub={t("biz.activity.agreements.sub")}>
              <ul className="divide-y divide-line">
                {data.commitments.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                    <span>
                      <span className="font-medium text-ink">
                        <CustomerName id={c.counterparty_id}>{buyerName(c.counterparty_id)}</CustomerName>
                      </span>
                      <span className="block text-meta text-ink-3">
                        {t(c.expires_day < today ? "biz.activity.expired" : "biz.activity.expires", { when: whenText(c.expires_day, today, t) })} · {t("biz.activity.concessions")}: {c.forward_value_display}
                      </span>
                    </span>
                    <Badge tone={c.status === "ACTIVE" || c.status === "ACCEPTED" ? "ok" : "neutral"}>{te("commitment", c.status)}</Badge>
                    {/* The agreement's record ids are the audit level, never the row. */}
                    <Disclosure className="basis-full" summary={t("biz.auditDetails")}>
                      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-meta text-ink-2">
                        <dt>{t("appr.commitment")}</dt>
                        <dd className="break-all font-mono" data-testid="activity-commitment-id">
                          {c.id}
                        </dd>
                        <dt>{t("appr.offer")}</dt>
                        <dd className="break-all font-mono">{`${c.offer_id} v${c.offer_version}`}</dd>
                      </dl>
                    </Disclosure>
                  </li>
                ))}
              </ul>
            </Section>
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
            <Section id="activity-refused" title={t("biz.activity.refused")} sub={t("biz.activity.refused.sub")}>
              {audit.error ? (
                <ErrorState error={audit.error} onRetry={audit.reload} />
              ) : !audit.data ? (
                <LoadingBlock rows={1} />
              ) : (
                <ul className="divide-y divide-line">
                  {data.refusals?.set_aside_text ? (
                    <li className="py-3 text-sm text-ink-2" data-testid="activity-set-aside">
                      {data.refusals.set_aside_text}
                    </li>
                  ) : null}
                  {audit.data.refusals.map((o) => (
                    <li key={`${o.seq}-${o.op_id}`} className="py-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <OpStatusBadge status={o.status} />
                        <span className="font-medium">{kindLabel(o.kind)}</span>
                      </div>
                      <p className="mt-1 text-ink-2">{o.event_text || o.message_when || kindLabel(o.kind)}</p>
                    </li>
                  ))}
                  {audit.data.events.map((e) => (
                    <li key={e.id} className="py-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{te("secevent", e.kind)}</span>
                        <span className="text-meta text-ink-3">{e.action_taken}</span>
                      </div>
                      <p className="mt-1 text-ink-2">{e.detail}</p>
                      {e.spans.map((s) => (
                        <SpanQuote key={`${s.doc_id}:${s.start}`} text={s.text} />
                      ))}
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}

          </div>

          {/* What the chain check covers, folded; with nothing on the log yet there is no check to explain, and only the line to the evidence stays. */}
          {data.chain_scope_text && data.chain_text !== null ? (
            <FoldCard title={t("biz.activity.chainAbout")} hint={t("biz.activity.chainAbout.hint")} testId="activity-chain-scope">
              <p className="text-supporting font-bold text-ink">{t("biz.activity.chainScope")}</p>
              <p className="mt-1 text-sm text-ink-2">{data.chain_scope_text}</p>
              <p className="mt-3 text-meta text-ink-3">
                {t("biz.activity.trail")}{" "}
                <Link href="/evidence" className="inline-flex min-h-8 items-center font-medium text-brand-700 underline underline-offset-2 touch:min-h-11">
                  {t("biz.activity.trail.open")}
                </Link>
              </p>
            </FoldCard>
          ) : (
            <p className="text-meta text-ink-3">
              {t("biz.activity.trail")}{" "}
              <Link href="/evidence" className="inline-flex min-h-8 items-center font-medium text-brand-700 underline underline-offset-2 touch:min-h-11">
                {t("biz.activity.trail.open")}
              </Link>
            </p>
          )}
          </>
          )}

          {/* The shadow pilot's journal: read-only, only with the strategy build flag and a live API (the mock has none). */}
          {STRATEGY_MVP && API_MODE === "live" ? <PilotJournal /> : null}
        </div>
      )}
    </>
  );
}
