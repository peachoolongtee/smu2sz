"use client";

import Link from "next/link";
import { useEffect, useId, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CustomerName } from "@/components/customer-link";
import { Button, ButtonLink, Callout, ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { ComparisonTable, type CompareColumn, type CompareRow } from "@/components/ui/comparison-table";
import { OpenSection } from "@/components/ui/open-section";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { StateWord } from "@/components/ui/state-word";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { demoStore } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import { receiptOfPath } from "@/lib/receipt";
import type { DecisionView, NegotiationView, OpenOffer, PicturePath, QueueRowView } from "@/lib/types";
import { AUTH_TONE, Cell, NONE, toneOfDeal } from "./flow-parts";
import { Investigate, lowestOf } from "./investigate";
import { SendBlock } from "./send-block";
import { useNegotiation } from "./use-negotiation";

/** The deal's own view of the page, in the address: which investigation is open (`compare=1`, `chart=1`) and the payment-timing assumption (`scenario=late`). */
export interface DealView {
  compare: boolean;
  chart: boolean;
  late: boolean;
}

const RECORD_DONE = new Set(["AGREED", "FULFILLED", "MISSED", "EXPIRED", "REVOKED", "NO_DEAL", "DECLINED", "FAILED"]);

/** A sentence the server wrote opens with a capital in the place it stands. */
const upper = "first-letter:uppercase";

function Announce({ text }: { text: string }) {
  return (
    <p role="status" aria-live="polite" className="sr-only" data-testid="deal-announce">
      {text}
    </p>
  );
}

/** What the buyer answered once a counter was sent (this tab's answer to the send; the deal's record carries it afterwards). */
function SendResult({ n }: { n: NegotiationView }) {
  const { t } = useI18n();
  const deal = n.outcome === "DEAL";
  const accepted = n.rounds.find((r) => r.buyer_response === "ACCEPT");
  const ran = n.operations.filter((o) => o.status === "EXECUTED");
  return (
    <div role="status" className="mt-4 rounded-tile border border-line bg-subtle px-4 py-3 text-sm" data-testid="deal-sent">
      <p className="font-bold text-ink" data-testid="deal-negotiation">
        {deal ? t("biz.deals.dealDone", { counter: accepted?.counter_label_when ?? accepted?.counter_label ?? "" }) : t("biz.deals.noDeal")}
      </p>
      {!deal ? <p className="mt-1 text-ink-2">{ran.length ? t("biz.deals.gapFunded") : t("biz.deals.nothingChanged")}</p> : null}
    </div>
  );
}

/** The record's own account of where a negotiation stands, for one that is out of the owner's hands or finished. */
function RecordBlock({ record, decision }: { record: DecisionView; decision: string }) {
  const { t } = useI18n();
  const ex = record.execution;
  const money = Boolean(ex && (ex.requested_display || ex.landed_display || ex.in_transit_display));
  const agreed = record.agreement?.terms ?? [];
  const terms = agreed.length ? agreed : (record.interpretation?.terms ?? []);
  const waiting = record.waiting_for?.text ?? null;
  return (
    <div className="mt-5 space-y-3" data-testid="deal-record" data-state={record.state}>
      {waiting ? (
        <p className="text-[15px] leading-snug text-ink" data-testid="deal-waiting">
          {waiting}
        </p>
      ) : null}
      {money && ex ? (
        <p className="text-sm text-ink-2" data-testid="deal-money-lines">
          {ex.summary_text}
        </p>
      ) : null}
      {record.agreement ? (
        <p className="text-sm font-bold text-ink-2" data-testid="deal-agreement">
          {record.agreement.status_text} · {record.agreement.expires_when}
        </p>
      ) : null}
      {terms.length ? (
        <div>
          <h3 className="text-supporting font-bold text-ink-3">{agreed.length ? t("deals.agreedTerms") : t("deals.askedTerms")}</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink" data-testid="deal-terms">
            {terms.map((term, i) => (
              <li key={i}>{term}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {record.remaining_task?.text && record.remaining_task.text !== waiting ? (
        <p className="text-sm text-ink-2" data-testid="deal-left">
          {record.remaining_task.text}
        </p>
      ) : null}
      <p className="text-sm">
        <Link href={`/decisions/${encodeURIComponent(decision)}`} className={textLinkClass} data-testid="deal-record-link">
          {t("deals.record")}
        </Link>
      </p>
    </div>
  );
}

/**
 * The selected negotiation, in three levels (tickets #126, #129, #131, #132; audit UX05). It is hydrated from the server for the `decision` in the address and nothing else, so a deep link in
 * a fresh session reads what a click reads.
 *   Decide: the buyer's ask in their words, what FLOW recommends and why (the server's `recommended_reason_text` and the reply's `authority_reason_text`), the two costs each with its
 *     basis words, and the one commit area: "Review and send the counter" (the only filled button) opens the commitment receipt above a single commit button; "Compare responses" and
 *     "Cash impact" are outlined.
 *   Consequence: the request against the recommended reply (the lowest cash and when, the reserve, your limits, the approval), under the payment-timing assumption, with the sentence that
 *     says what each figure assumes.
 *   Investigate, only on request: the full table of every response, the late-payment rows, room for another payment in words, the envelope's packages, the deal's cash chart.
 * A selection the server cannot honour asks which negotiation; it never shows a sample. Every figure and sentence is the server's or the dictionary's.
 */
export function DecisionPane({
  decision,
  customer,
  row,
  open,
  view,
  pickedKey,
  onView,
  onPick,
  onClose,
  onBusy,
  irrelevantText,
}: {
  decision: string;
  /** The customer in the address, when it names one: a negotiation that is another customer's is asked about, not shown. */
  customer: string | null;
  /** The queue's row for this negotiation, when the queue holds it. */
  row: QueueRowView | null;
  /** The deals read's open offer for it (the verdict in a few words, what it asks). */
  open: OpenOffer | null;
  view: DealView;
  /** The path the address names (`path`), else null: the recommended reply. */
  pickedKey: string | null;
  onView: (patch: Partial<DealView>) => void;
  onPick: (key: string | null) => void;
  onClose: () => void;
  onBusy: (busy: boolean) => void;
  /** The server's sentence when it could not honour the selection (`context.irrelevant_text`). */
  irrelevantText: string | null;
}) {
  const { t, te } = useI18n();
  const uid = useId();
  const mode = useMode();
  // The investigation is wider than the pane beside the queue: it opens in a full-width slot the page keeps under both columns.
  const slot = typeof document !== "undefined" ? document.getElementById("deals-investigate") : null;
  const n = useNegotiation(decision);
  const [sent, setSent] = useState<NegotiationView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const offer = n.offer;
  const buyerId = offer?.offer.counterparty_id ?? null;
  // Another customer's negotiation than the address names is a selection that names nothing: ask, never substitute.
  const mismatch = Boolean(customer && buyerId && customer !== buyerId);
  useEffect(() => {
    document.getElementById(`${uid}-title`)?.focus({ preventScroll: true });
  }, [uid, decision]);

  const ask = (children: ReactNode) => (
    <div className="flow-card p-5 sm:p-7" data-testid="deal-ask-which" role="region" aria-label={t("deals.which.title")}>
      <h2 className="type-section text-ink">{t("deals.which.title")}</h2>
      <p className="mt-1 max-w-[60ch] text-sm text-ink-2" data-testid="deal-irrelevant">
        {children}
      </p>
      <div className="mt-3">
        <Button onClick={onClose} data-testid="deal-which-close">
          {t("deals.which.action")}
        </Button>
      </div>
    </div>
  );
  if (n.error && !offer) return <ErrorState error={n.error} onRetry={n.reload} />;
  if (n.missing || mismatch || (irrelevantText && !offer)) return ask(irrelevantText ?? t("deals.irrelevant"));
  if (n.loading || !offer) return <LoadingBlock rows={4} label={t("hv2.focus.working")} />;

  const record = n.record ?? null;
  const picture = n.picture;
  const exposure = n.exposure ?? null;
  const buyerName = record?.counterparty_name ?? exposure?.buyer_name ?? row?.customer_short ?? offer.offer.counterparty_id;
  const buyerShort = exposure?.concentration.buyer_name ?? row?.customer_short ?? buyerName;
  // Checked against the limits: the record says so (it leaves RECEIVED); a server without the record's first state reads the picture, which only exists for an evaluated offer.
  const evaluated = record ? record.state !== "RECEIVED" : Boolean(picture);
  const stateCode = record?.state ?? (evaluated ? "RESPONSE_READY" : "RECEIVED");
  const done = RECORD_DONE.has(stateCode);
  const title = open?.headline_short ?? open?.read_text ?? record?.headline ?? row?.subject_text ?? buyerName;
  const doc = offer.documents[0];
  const paths = (picture?.paths ?? []).filter((p) => p.kind === "asked" || p.kind === "reply");
  const asked = paths.find((p) => p.kind === "asked") ?? null;
  const recommended = paths.find((p) => p.kind === "reply" && p.recommended) ?? null;
  const picked = pickedKey ? (paths.find((p) => p.kind === "reply" && p.key === pickedKey) ?? null) : null;
  const focus: PicturePath | null = picked ?? recommended;
  const showsRecommended = focus !== null && focus.key === recommended?.key;
  // The share clause of the economics read (what this concession is, against what the customer brings in a year): drawn only when the server carries it.
  const shareClause = exposure?.economics?.context_text ?? exposure?.economics?.sentence ?? null;
  const late = view.late && Boolean(exposure?.stress.paths);
  const delay = exposure?.stress.delay_days ?? 0;
  const wordsOf = (p: PicturePath) => exposure?.paths.find((x) => x.key === p.key);
  const stressOf = (p: PicturePath) => exposure?.stress.paths[p.key] ?? null;
  const canSend = Boolean(focus && focus.kind === "reply" && focus.sendable && (stateCode === "RESPONSE_READY" || stateCode === "RECEIVED") && picture && picture.available !== false && !sent);

  async function check() {
    setChecking(true);
    setError(null);
    try {
      await evaluateAndCache(offer!.offer.offer_id);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setChecking(false);
    }
  }
  const setBusyBoth = (b: boolean) => {
    setBusy(b);
    onBusy(b);
  };

  // ---- level 2: the request against the recommended (or the picked) reply
  const pair = [asked, focus].filter((p, i, a): p is PicturePath => p !== null && a.indexOf(p) === i);
  const pairColumns: CompareColumn[] = pair.map((p) => ({ key: p.key, head: p.label, tag: <StateWord tone={toneOfDeal(p.tag_tone)}>{p.tag_text}</StateWord>, recommended: p.key === recommended?.key }));
  const lowest = (p: PicturePath) => lowestOf(p, wordsOf(p), stressOf(p), late);
  const pairRows: CompareRow[] = [
    {
      key: "lowest",
      label: t("hv2.deal.lowest"),
      cells: pair.map((p) => {
        const l = lowest(p);
        return <Cell key={p.key} value={l.value} sub={l.sub} bad={l.bad} />;
      }),
    },
    {
      key: "reserve",
      label: t("hv2.deal.reserve"),
      cells: pair.map((p) => {
        const l = lowest(p);
        return <Cell key={p.key} note={l.note} bad={l.bad} />;
      }),
    },
    {
      key: "limits",
      label: t("hv2.deal.limits"),
      cells: pair.map((p) => {
        const w = wordsOf(p);
        return w?.limit_text ? (
          <StateWord key={p.key} tone={w.limit_word === "EXCEEDED" ? "bad" : "ok"}>
            <span className={upper}>{w.limit_text}</span>
          </StateWord>
        ) : (
          <span key={p.key}>{NONE}</span>
        );
      }),
    },
    {
      key: "approval",
      label: t("hv2.deal.approval"),
      cells: pair.map((p) => (
        <StateWord key={p.key} tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"}>
          {p.authority_text ?? p.decides_text}
        </StateWord>
      )),
    },
  ];
  // What each path assumes, said under the table (the asked path carries no funding plan, a reply carries its own): one sentence per column, never merged into one.
  const assumptions = pair.map((p) => ({ p, text: late ? null : (wordsOf(p)?.scenario_assumption_text ?? p.scenario_assumption_text) })).filter((x) => x.text);
  const timingTabs = Boolean(exposure?.stress.paths);

  const askCost = asked ? (asked.cost_forward_display ?? asked.cost_total_display ?? asked.cost_display) : null;
  const askBasis = asked ? (asked.cost_forward_display && asked.cost_once_display ? asked.cost_note : (asked.cost_basis_text ?? asked.cost_note)) : null;
  const focusCost = focus ? (focus.cost_total_display ?? focus.cost_once_display ?? focus.cost_display) : null;
  const focusBasis = focus ? (focus.cost_basis_text ?? focus.cost_note) : null;
  const waitsOnApproval = stateCode === "AUTHORIZATION_REQUIRED";
  const approvalId = record?.authorization?.approval_id ?? null;
  const whatifHref = `/whatif?customer=${encodeURIComponent(buyerId ?? "")}&decision=${encodeURIComponent(decision)}&from=deal`;

  const customerLine = (
    <p className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm text-ink-2" data-testid="deal-customer-line">
      <CustomerName id={buyerId} decision={decision} className="font-bold text-ink" testId="deal-selected-customer">
        {buyerName}
      </CustomerName>
      {shareClause ? (
        <span data-testid="deal-share-clause">
          <span aria-hidden>· </span>
          {shareClause}
        </span>
      ) : null}
    </p>
  );

  const pane = (
    <section aria-labelledby={`${uid}-title`} className="flow-card min-w-0 p-5 sm:p-7" data-testid="deal-pane" data-decision={decision} data-state={stateCode}>
      <Announce text={title} />
      <div key={decision} className="motion-swap">
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="mb-1" data-testid="deal-state-chip" data-state={stateCode}>
              <StateWord tone={toneOfDeal(record?.state_tone ?? (done ? "neutral" : "warn"))}>{record?.state_text ?? row?.status_text ?? ""}</StateWord>
            </p>
            <h2 id={`${uid}-title`} tabIndex={-1} className="type-section text-balance text-ink" data-testid="queue-heading">
              {title}
            </h2>
            {customerLine}
          </div>
          <Button size="sm" variant="ghost" onClick={onClose} disabled={busy} aria-label={t("deals.close")} data-testid="deal-close">
            <span aria-hidden>×</span> {t("deals.dismiss")}
          </Button>
        </header>

        {/* Level 1: decide */}
        <div className="mt-5 space-y-5" data-testid="deal-level-decide">
          <div>
            <h3 className="text-supporting font-bold text-ink-3">{t("deals.askTitle", { buyer: buyerShort })}</h3>
            {doc?.text ? (
              <figure className="mt-1.5 border-l-2 border-line-strong pl-3" data-testid="deal-ask-quote">
                <blockquote className="max-w-[68ch] text-[15px] leading-snug text-ink">“{doc.text}”</blockquote>
                <figcaption className="mt-1 text-supporting text-ink-3">{record?.source.received_when ? t("biz.deals.messageWhen", { channel: te("channel", doc.channel ?? "chat"), when: record.source.received_when }) : te("channel", doc.channel ?? "chat")}</figcaption>
              </figure>
            ) : null}
            {open?.asks_text && !doc?.text ? (
              <p className="mt-2 max-w-[68ch] text-sm leading-snug text-ink-2" data-testid="queue-ask">
                {t("dq.ask", { buyer: buyerShort, asks: open.asks_text })}
              </p>
            ) : null}
            {asked?.terms.length ? (
              <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3" data-testid="deal-ask-terms">
                {asked.terms.map((x) => (
                  <div key={x.key} className="min-w-0">
                    <dt className="text-supporting text-ink-3">{x.label}</dt>
                    <dd className="m-0 text-[15px] font-bold text-ink">{x.value_text}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </div>

          {offer.offer.abstentions.length ? (
            <div data-testid="deal-abstentions">
              <Callout tone="warn" title={t("biz.deals.cannotEvaluate")}>
                <ul className="list-disc pl-5 text-sm">
                  {offer.offer.abstentions.map((a) => (
                    <li key={a.field}>{a.reason}</li>
                  ))}
                </ul>
                <div className="mt-2">
                  <ButtonLink href={`/chat?customer=${encodeURIComponent(buyerId ?? "")}&decision=${encodeURIComponent(decision)}`}>{t("biz.deals.clarify")}</ButtonLink>
                </div>
              </Callout>
            </div>
          ) : null}

          {done || waitsOnApproval || stateCode === "NEEDS_CLARIFICATION" ? (
            <>
              {record ? <RecordBlock record={record} decision={decision} /> : null}
              {waitsOnApproval ? (
                <ActionGroup testId="deal-actions" label={t("deals.actions")}>
                  <ButtonLink href={approvalId ? `/approvals#approval-${encodeURIComponent(approvalId)}` : "/approvals"} variant="primary" data-testid="deal-approvals-link">
                    {t("next.toApprovals")}
                  </ButtonLink>
                </ActionGroup>
              ) : null}
              {sent ? <SendResult n={sent} /> : null}
            </>
          ) : picture === undefined ? (
            <div data-testid="paths-loading">
              <LoadingBlock rows={3} />
            </div>
          ) : !picture || !evaluated ? (
            <div data-testid="queue-check">
              <p className="max-w-[60ch] text-sm text-ink-2">{t("deals.check.body")}</p>
              <ActionGroup className="mt-3" testId="deal-actions" label={t("deals.actions")}>
                <Button variant="primary" loading={checking} onClick={() => void check()} data-testid="queue-check-button">
                  {t("biz.deals.check")}
                </Button>
              </ActionGroup>
              {error ? (
                <div className="mt-2">
                  <ErrorState error={error} />
                </div>
              ) : null}
            </div>
          ) : picture.available === false ? (
            <div data-testid="deal-undrawable">
              <p className="max-w-[60ch] text-sm text-ink-2">{picture.unavailable_text}</p>
              <ActionGroup className="mt-3" testId="deal-actions" label={t("deals.actions")}>
                <Button loading={checking} onClick={() => void check()} data-testid="deal-check-again">
                  {t("biz.deals.checkAgain")}
                </Button>
              </ActionGroup>
              {error ? (
                <div className="mt-2">
                  <ErrorState error={error} />
                </div>
              ) : null}
            </div>
          ) : (
            <>
              {focus ? (
                <div className="space-y-2.5 border-t border-line pt-5" data-testid="queue-recommends" data-path={focus.key === recommended?.key ? "recommended" : "other"}>
                  <h3 className="text-supporting font-bold text-ink-3" data-testid="deal-recommends-title">
                    {showsRecommended ? t("deals.recommend", { label: focus.label }) : t("deals.selected", { label: focus.label })}
                  </h3>
                  {focus.reply_text ? (
                    <p className="max-w-[68ch] font-display text-lg font-bold leading-snug text-ink" data-testid="queue-option">
                      {focus.reply_text}
                    </p>
                  ) : null}
                  {showsRecommended && focus.recommended_reason_text ? (
                    <p className="max-w-[68ch] text-[15px] leading-snug text-ink-2" data-testid="deal-recommended-reason">
                      {focus.recommended_reason_text}
                    </p>
                  ) : null}
                  <div data-testid="queue-authority" data-authority={focus.authority ?? ""} data-tone={AUTH_TONE[focus.authority ?? ""] ?? "neutral"}>
                    <StateWord tone={AUTH_TONE[focus.authority ?? ""] ?? "neutral"}>{focus.authority_text ?? focus.decides_text}</StateWord>
                    {focus.authority_reason_text ? (
                      <p className="mt-1 max-w-[68ch] text-supporting text-ink-2" data-testid="deal-authority-reason">
                        {focus.authority_reason_text}
                      </p>
                    ) : null}
                  </div>
                  <dl className="grid gap-x-8 gap-y-3 pt-1 sm:grid-cols-2" data-testid="deal-costs">
                    {asked ? (
                      <div className="min-w-0" data-testid="deal-cost-asked">
                        <dt className="text-supporting text-ink-3">{t("deals.cost.asked")}</dt>
                        <dd className="m-0">
                          <Cell value={askCost} sub={askBasis} bad={asked.authority === "over_limit"} />
                        </dd>
                      </div>
                    ) : null}
                    <div className="min-w-0" data-testid="queue-cost">
                      <dt className="text-supporting text-ink-3">{t("deals.cost.reply", { buyer: buyerShort, label: focus.label })}</dt>
                      <dd className="m-0">
                        <Cell value={focusCost} sub={focusBasis} />
                      </dd>
                    </div>
                  </dl>
                  {!showsRecommended && recommended ? (
                    <div>
                      <Button size="sm" onClick={() => onPick(null)} disabled={busy} data-testid="path-reply-back">
                        {t("biz.deals.reply.back", { label: recommended.label })}
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-2 border-t border-line pt-5" data-testid="deal-no-reply">
                  <h3 className="text-supporting font-bold text-ink-3">{t("dq.rec.plain")}</h3>
                  <p className="max-w-[68ch] text-[15px] leading-snug text-ink">{asked?.decides_text ?? t("glance.offer.none")}</p>
                </div>
              )}

              {canSend && focus && picture && mode === "business" ? (
                <SendBlock
                  key={`${offer.offer.offer_id}:${focus.key}`}
                  offerId={offer.offer.offer_id}
                  path={focus}
                  picture={picture}
                  receipt={receiptOfPath(focus, demoStore.get().verdicts[offer.offer.offer_id], picture.verdict_id)}
                  buyer={buyerShort}
                  onSent={setSent}
                  onBusy={setBusyBoth}
                >
                  {paths.length > 1 ? <CompareButtons view={view} onView={onView} hasChart={paths.some((p) => (p.series ?? []).length > 0)} whatif={whatifHref} /> : null}
                </SendBlock>
              ) : (
                <ActionGroup className="mt-4" testId="deal-actions" label={t("deals.actions")}>
                  {paths.length > 1 ? <CompareButtons view={view} onView={onView} hasChart={paths.some((p) => (p.series ?? []).length > 0)} whatif={whatifHref} /> : null}
                  {mode === "demo" ? (
                    <Link href="/verdict#negotiation" className={textLinkClass}>
                      {t("biz.deals.negotiateLink")}
                    </Link>
                  ) : null}
                </ActionGroup>
              )}
              {sent ? <SendResult n={sent} /> : null}
            </>
          )}
        </div>

        {/* Level 2: the consequence */}
        {picture && evaluated && picture.available !== false && pair.length && !done && !waitsOnApproval ? (
          <OpenSection title={t("hv2.deal.consequence")} subtitle={t("hv2.deal.consequence.note")} testId="deal-level-consequence" className="mt-6 sm:mt-6 pt-6 sm:pt-6">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2" data-testid="deal-assumption-row">
              <p className="text-sm font-bold text-ink-2">{t("hv2.deal.timing")}</p>
              {timingTabs ? (
                <SegmentedTabs
                  compact
                  label={t("hv2.deal.timing")}
                  value={late ? "late" : "expected"}
                  onChange={(x) => onView({ late: x === "late" })}
                  tabs={[
                    { value: "expected", label: t("home.hy.scenario.expected"), testId: "deal-scenario-current" },
                    { value: "late", label: t("home.hy.scenario.late", { buyer: buyerShort, n: delay }), testId: "deal-scenario-late" },
                  ]}
                />
              ) : null}
            </div>
            <p className="mt-1 text-supporting text-ink-3">{t("hv2.deal.timing.note")}</p>
            <div className="mt-3" data-testid="deal-scenario-panel" data-scenario={late ? "late" : "current"}>
              <ComparisonTable container testId="deal-consequence" caption={t("hv2.deal.consequence")} columns={pairColumns} rows={pairRows} />
              {assumptions.length ? (
                <ul className="mt-3 space-y-1" data-testid="scenario-assumption-text">
                  {assumptions.map(({ p, text }) => (
                    <li key={p.key} className="text-supporting text-ink-2" data-testid="deal-assumption">
                      <b className="font-bold text-ink">{p.label}.</b> {text}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </OpenSection>
        ) : null}

      </div>
    </section>
  );
  const investigating = Boolean(picture && evaluated && picture.available !== false && (view.compare || view.chart) && !done);
  const investigate =
    investigating && picture ? (
      <div className="flow-card p-5 sm:p-7" data-testid="deal-investigate">
        <Investigate offerId={offer.offer.offer_id} buyer={buyerShort} buyerId={buyerId ?? ""} picture={picture} exposure={exposure} late={late} pickedKey={pickedKey} onPick={(k) => onPick(k)} compareOpen={view.compare} chartOpen={view.chart} />
      </div>
    ) : null;
  return (
    <>
      {pane}
      {investigate ? (slot ? createPortal(investigate, slot) : investigate) : null}
    </>
  );
}

/** "Compare responses" and "Cash impact": the outlined toggles of the decision level (the filled button is the commit's). */
function CompareButtons({ view, onView, hasChart, whatif }: { view: DealView; onView: (patch: Partial<DealView>) => void; hasChart: boolean; whatif: string }) {
  const { t } = useI18n();
  const chevron = (on: boolean) => (
    <svg aria-hidden viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={`transition-transform duration-(--dur) ${on ? "rotate-180" : ""}`}>
      <path d="m4 6 4 4 4-4" />
    </svg>
  );
  return (
    <>
      <Button aria-expanded={view.compare} aria-controls="deal-compare" onClick={() => onView({ compare: !view.compare })} data-testid="deal-compare-toggle">
        {t("hv2.deal.compare")}
        {chevron(view.compare)}
      </Button>
      {hasChart ? (
        <Button aria-expanded={view.chart} aria-controls="deal-chart" onClick={() => onView({ chart: !view.chart })} data-testid="deal-chart-toggle">
          {t("hv2.deal.cash")}
          {chevron(view.chart)}
        </Button>
      ) : null}
      <Link href={whatif} className={`${textLinkClass} px-1`} data-testid="deal-whatif">
        {t("deals.whatif")}
      </Link>
    </>
  );
}
