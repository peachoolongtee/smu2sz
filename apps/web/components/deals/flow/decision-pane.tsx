"use client";

import Link from "next/link";
import { useEffect, useId, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CustomerName } from "@/components/customer-link";
import { Disclosure } from "@/components/business/kit";
import { ChasePayment } from "@/components/business/chase-payment";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { Button, ButtonLink, Callout, ErrorState, LoadingBlock } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { ComparisonTable, type CompareColumn, type CompareRow } from "@/components/ui/comparison-table";
import { OpenSection } from "@/components/ui/open-section";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { StateWord } from "@/components/ui/state-word";
import { StatusPill } from "@/components/ui/status-pill";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import type { DecisionView, NegotiationView, OpenOffer, PicturePath, QueueRowView } from "@/lib/types";
import { AcceptBlock, type AcceptOutcome } from "./accept-block";
import { AnalysisCards, type ShowKey } from "./analysis-cards";
import { CostTable } from "./cost-table";
import { costHeadline, paneStatus, timingOf } from "./deal-model";
import { AUTH_TONE, Cell, NONE, quietLink, toneOfDeal } from "./flow-parts";
import { Investigate, lowestOf } from "./investigate";
import { TermsTable } from "./terms-table";
import { TimingDiagram } from "./timing-diagram";
import { SendBlock } from "./send-block";
import { useNegotiation } from "./use-negotiation";

/** The deal's own view of the page, in the address: which investigation is open (`compare=1`, `chart=1`) and the payment-timing assumption (`scenario=late`). */
export interface DealView {
  compare: boolean;
  chart: boolean;
  late: boolean;
  /** "Full analysis" is open (`investigate=1`): the Investigate level with the reasons. */
  investigate: boolean;
  /** Which of the two cards is open (`show=cost|cash`; `none` both folded); null is the default card. */
  show: ShowKey | null;
  /** The accept review is open on arrival (`review=1`): a link from Home or the Customer page to a request that needs the owner's review. */
  review: boolean;
}

const RECORD_DONE = new Set(["AGREED", "FULFILLED", "MISSED", "EXPIRED", "REVOKED", "NO_DEAL", "DECLINED", "FAILED", "LAPSED"]);

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
  const summary = n.execution?.summary_text || null;
  return (
    <div role="status" className="mt-4 rounded-tile border border-line bg-subtle px-4 py-3 text-sm" data-testid="deal-sent">
      <p className="font-bold text-ink" data-testid="deal-negotiation">
        {deal ? t("biz.deals.dealDone", { counter: accepted?.counter_label_when ?? accepted?.counter_label ?? "" }) : t("biz.deals.noDeal")}
      </p>
      {/* What ran, in the server's own words (the negotiation result's execution summary); the web adds no sentence of its own about the funding. */}
      {summary ? (
        <p className="mt-1 text-ink-2" data-testid="deal-sent-ran">
          {summary}
        </p>
      ) : null}
    </div>
  );
}

/** What the owner's accept (or a refusal of it) said, in the server's words, beside the record that moved on: the execution's summary after an accept, the 409's sentence after a refusal. A decline says nothing more than the record's Declined. */
function AcceptResult({ outcome }: { outcome: AcceptOutcome }) {
  if (outcome.kind === "declined") return null;
  const text = outcome.text;
  if (!text) return null;
  return (
    <div role={outcome.kind === "refused" ? "alert" : "status"} className="mt-5 rounded-tile border border-line bg-subtle px-4 py-3 text-sm text-ink" data-testid={outcome.kind === "accepted" ? "deal-accepted" : "deal-accept-refused"}>
      <p data-testid={outcome.kind === "accepted" ? "deal-accepted-ran" : undefined}>{text}</p>
    </div>
  );
}

/** The record's own account of where a negotiation stands, for one that is out of the owner's hands or finished. */
function RecordBlock({ record, decision }: { record: DecisionView; decision: string }) {
  const { t } = useI18n();
  const ex = record.execution;
  // The money: each lot the record holds, "Received ¥… today" once it has landed and "¥… arrives in 3 days" while it is on its way; else the execution's own sentence when something ran.
  const lots = (record.settlement ?? []).map((l) => ({
    key: l.lot_id,
    landed: l.settled,
    text: l.settled ? t("deal.money.received", { amount: l.principal_display, when: l.arrival_when }) : t("deal.money.arrives", { amount: l.principal_display, when: l.arrival_when }),
  }));
  const ran = Boolean(ex && (ex.requested_display || ex.landed_display || ex.in_transit_display));
  const agreed = record.agreement?.terms ?? [];
  const terms = agreed.length ? agreed : (record.interpretation?.terms ?? []);
  const waiting = record.waiting_for?.text ?? null;
  // A missed early payment leaves the shortfall to cover: the way to the funding options is always offered beside the chase (the server's own links come first).
  const sent = record.remaining_task?.links ?? [];
  const links = record.state === "MISSED" && !sent.some((l) => l.href.startsWith("/cash")) ? [...sent, { label: t("deal.left.compare"), href: "/cash#cash-options" }] : sent;
  const promise = record.state === "MISSED" ? (record.promises[0] as { receivable_id?: string } | undefined) : undefined;
  return (
    <div className="mt-5 space-y-3" data-testid="deal-record" data-state={record.state}>
      {waiting ? (
        <p className="text-[15px] leading-snug text-ink" data-testid="deal-waiting">
          {waiting}
        </p>
      ) : null}
      {lots.length || (ran && ex) ? (
        <p className="text-sm text-ink-2" data-testid="deal-money-lines">
          {lots.length ? lots.map((l) => <span key={l.key} className="mr-2 inline-block">{l.text}</span>) : ex?.summary_text}
        </p>
      ) : null}
      {record.agreement ? (
        <p className="text-sm font-bold text-ink-2" data-testid="deal-agreement">
          {[record.agreement.status_text, record.agreement.expires_when].filter(Boolean).join(" · ")}
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
      {record.agreement?.receipt ? <CommitmentReceipt receipt={record.agreement.receipt} id={`${decision}-agreement-receipt`.replace(/[^A-Za-z0-9_-]/g, "-")} title={t("receipt.title.agreed")} testId="deal-agreement-receipt" /> : null}
      {record.remaining_task?.text && record.remaining_task.text !== waiting ? (
        <p className="text-sm text-ink-2" data-testid="deal-left">
          {record.remaining_task.text}
        </p>
      ) : null}
      {links.length || promise?.receivable_id ? (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1" data-testid="deal-left-links">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className={quietLink}>
              {l.label}
            </Link>
          ))}
          {promise?.receivable_id ? <ChasePayment receivableId={promise.receivable_id} buyer={record.counterparty_name ?? ""} /> : null}
        </div>
      ) : null}
      <p className="text-sm">
        <Link href={`/decisions/${encodeURIComponent(decision)}`} className={quietLink} data-testid="deal-record-link">
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
  // The owner's accept or decline of a request as asked, once it has been answered: the review is gone when the record moves on, its words stay beside the record.
  const [outcome, setOutcome] = useState<AcceptOutcome | null>(null);
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
  // A decision that is not a deal (`approval:…`, anything else) names no negotiation: ask at once, never wait for a read that will not come.
  if (!n.offerId || n.missing || mismatch || (irrelevantText && !offer)) return ask(irrelevantText ?? t("deals.irrelevant"));
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
  // The funding each path's cash rests on, in the server's short words: its own row. A server that does not send it keeps the longer assumption sentence under the table.
  const fundingOf = (p: PicturePath) => wordsOf(p)?.funding_assumption_text ?? p.funding_assumption_text ?? null;
  const hasFunding = pair.some((p) => fundingOf(p));
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
      key: "approval",
      label: t("deals.row.authority"),
      cells: pair.map((p) => (
        <StateWord key={p.key} tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"}>
          {p.authority_text ?? p.decides_text}
        </StateWord>
      )),
    },
    ...(hasFunding
      ? [
          {
            key: "funding",
            label: t("deals.row.funding"),
            cells: pair.map((p) => {
              const f = fundingOf(p);
              return f ? <Cell key={p.key} note={f} /> : <span key={p.key}>{NONE}</span>;
            }),
          },
        ]
      : []),
  ];
  // What each path assumes, said under the table (the asked path carries no funding plan, a reply carries its own): one sentence per column, never merged into one.
  const assumptions = hasFunding ? [] : pair.map((p) => ({ p, text: late ? null : (wordsOf(p)?.scenario_assumption_text ?? p.scenario_assumption_text) })).filter((x) => x.text);
  const timingTabs = Boolean(exposure?.stress.paths);

  const timing = picture ? timingOf(picture, asked, focus) : null;
  // The open card: the address's, else the one the recommendation reason names (cash when the request breaches the reserve or exceeds the mandate, whose authority row is in the cash table), cost when the server does not say.
  const shown: ShowKey = view.show ?? (["cash", "authority"].includes((recommended ?? focus)?.recommended_reason_kind ?? "") ? "cash" : "cost");
  const waitsOnApproval = stateCode === "AUTHORIZATION_REQUIRED";
  const approvalId = record?.authorization?.approval_id ?? null;
  const whatifHref = `/whatif?customer=${encodeURIComponent(buyerId ?? "")}&decision=${encodeURIComponent(decision)}&from=deal`;

  const status = paneStatus(row, record?.state_text, stateCode);
  const analysis = Boolean(picture && evaluated && picture.available !== false && pair.length && !done && !waitsOnApproval);
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
      <div key={decision} className="motion-slide">
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="mb-1.5" data-testid="deal-state-chip" data-state={stateCode}>
              <StatusPill tone={status.tone}>{status.text}</StatusPill>
            </p>
            <h2 id={`${uid}-title`} tabIndex={-1} className="type-section text-balance text-ink" data-testid="queue-heading">
              {title}
            </h2>
            {customerLine}
          </div>
          <Button variant="ghost" onClick={onClose} disabled={busy} aria-label={t("deals.close")} data-testid="deal-close">
            <span aria-hidden>×</span> {t("deals.dismiss")}
          </Button>
        </header>

        {/* Level 1: decide */}
        <div className="mt-5 space-y-5" data-testid="deal-level-decide">
          {/* What the buyer asked: open while it is the question; once the deal has an outcome it is history, folded and said not to be the agreement. */}
          {done ? (
            <Disclosure testId="deal-original" className="border-t border-line pt-1" summary={t("biz.deals.original.ask")}>
              <div className="pt-2">
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
          </div>

              </div>
            </Disclosure>
          ) : (
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
          </div>

          )}

          {/* A request FLOW has a reply for that the owner still cannot accept as asked: the server's reason, said once under the ask ("only a new mandate changes that"); no button. */}
          {!done && !waitsOnApproval && focus && picture?.accept && !picture.accept.available && picture.accept.reason_text ? (
            <p className="max-w-[68ch] text-supporting text-ink-2" data-testid="accept-reason-asked">
              {picture.accept.reason_text}
            </p>
          ) : null}

          {/* The evaluation prompt belongs to a negotiation still open to evaluate: an agreed or finished one shows its record (receipt and terms) and nothing to clarify, and one that waits on an approval is past it. */}
          {offer.offer.abstentions.length && !done && !waitsOnApproval ? (
            <div data-testid="deal-abstentions">
              <Callout tone="warn" title={t("biz.deals.cannotEvaluate")}>
                <ul className="list-disc pl-5 text-sm">
                  {offer.offer.abstentions.map((a) => ((a.reason_when === undefined ? a.reason : a.reason_when) ? <li key={a.field}>{a.reason_when === undefined ? a.reason : a.reason_when}</li> : null))}
                </ul>
                <div className="mt-2">
                  <ButtonLink href={`/chat?customer=${encodeURIComponent(buyerId ?? "")}&decision=${encodeURIComponent(decision)}`}>{t("biz.deals.clarify")}</ButtonLink>
                </div>
              </Callout>
            </div>
          ) : null}

          {done || waitsOnApproval || stateCode === "NEEDS_CLARIFICATION" ? (
            <>
              {outcome ? <AcceptResult outcome={outcome} /> : null}
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
            <div data-testid="next-step">
              <p className="max-w-[60ch] text-sm text-ink-2" data-testid="queue-check">
                {t("deals.check.body")}
              </p>
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
                  {!showsRecommended && recommended ? (
                    <div>
                      <Button size="sm" onClick={() => onPick(null)} disabled={busy} data-testid="path-reply-back">
                        {t("biz.deals.reply.back", { label: recommended.label })}
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-2.5 border-t border-line pt-5" data-testid="deal-no-reply">
                  <h3 className="text-supporting font-bold text-ink-3">{t("dq.rec.plain")}</h3>
                  <p className="max-w-[68ch] text-[15px] leading-snug text-ink">{asked?.decides_text ?? t("glance.offer.none")}</p>
                  {/* No reply FLOW can send: the ask itself is what the owner can accept or decline, so its authority, the server's words for what the owner can do, and its cost with the basis are
                      said first; then the commit area below ("Review the request", the accept review) when the server offers it. Nothing is invented. */}
                  {asked ? (
                    <div data-testid="queue-authority" data-authority={asked.authority ?? ""} data-tone={AUTH_TONE[asked.authority ?? ""] ?? "neutral"}>
                      {asked.authority_text && asked.authority_text !== asked.decides_text ? <StateWord tone={AUTH_TONE[asked.authority ?? ""] ?? "neutral"}>{asked.authority_text}</StateWord> : null}
                      {asked.authority_reason_text ? (
                        <p className="mt-1 max-w-[68ch] text-supporting text-ink-2" data-testid="deal-authority-reason">
                          {asked.authority_reason_text}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              )}

              {canSend && focus && picture ? (
                <SendBlock
                  // (keyed by the reply's name, not its id: checking again names new counters, and the review that is open stays open)
                  key={`${offer.offer.offer_id}:${focus.label}`}
                  offerId={offer.offer.offer_id}
                  path={focus}
                  picture={picture}
                  buyer={buyerShort}
                  recordHref={`/decisions/${encodeURIComponent(decision)}`}
                  onSent={setSent}
                  onBusy={setBusyBoth}
                >
                  {paths.length > 1 ? <CompareButtons whatif={whatifHref} /> : null}
                  {mode === "demo" ? (
                    <Link href="/verdict#negotiation" className={quietLink}>
                      {t("biz.deals.negotiateLink")}
                    </Link>
                  ) : null}
                </SendBlock>
              ) : !focus && asked && picture.accept && !sent ? (
                <AcceptBlock
                  key={offer.offer.offer_id}
                  offerId={offer.offer.offer_id}
                  accept={picture.accept}
                  asked={asked}
                  picture={picture}
                  buyer={buyerShort}
                  recordHref={`/decisions/${encodeURIComponent(decision)}`}
                  initialOpen={view.review}
                  onDone={setOutcome}
                  onBusy={setBusyBoth}
                />
              ) : (
                <ActionGroup className="mt-4" testId="deal-actions" label={t("deals.actions")}>
                  {paths.length > 1 ? <CompareButtons whatif={whatifHref} /> : null}
                  {mode === "demo" ? (
                    <Link href="/verdict#negotiation" className={quietLink}>
                      {t("biz.deals.negotiateLink")}
                    </Link>
                  ) : null}
                </ActionGroup>
              )}
              {sent ? <SendResult n={sent} /> : null}
            </>
          )}
        </div>

        {/* The analysis (round two): open sections on dividers, not nested cards. Terms with the timing diagram, what it costs, then the cash comparison. */}
        {analysis ? (
          <>
            <OpenSection title={t("deals.terms.title")} subtitle={t("deals.terms.note")} testId="deal-terms-section" className="mt-6 sm:mt-6 pt-6 sm:pt-6">
              {/* "FLOW recommends" stands only above the recommended reply; a reply the owner picked is "Your pick". */}
              <TermsTable
                paths={pair}
                heads={pair.map((p) => (p.kind === "asked" ? t("deals.terms.col.asked") : p.key === recommended?.key ? t("deals.terms.col.reply") : t("deals.terms.col.pick", { label: p.label })))}
                subs={pair.map((p) => (p.kind === "asked" || p.key !== recommended?.key ? null : p.label))}
                caption={t("deals.terms.title")}
              />
              {timing ? (
                <div className="mt-6">
                  <TimingDiagram timing={timing} />
                </div>
              ) : null}
            </OpenSection>
            {/* Cost and cash: two cards under the diagram, one open to its full table (the address), the other folded to its headline; then the quiet way to the full analysis. */}
            <div className="mt-6 border-t border-line pt-6" data-testid="deal-level-consequence" role="region" aria-label={t("deals.cards.region")}>
              <AnalysisCards
                open={shown}
                onShow={(k) => onView({ show: k })}
                costTitle={t("deals.card.cost")}
                cashTitle={t("deals.card.cash")}
                cost={pair.map((p) => ({ label: p.kind === "asked" ? t("deals.cost.col.asked") : p.label, value: costHeadline(p).display, note: costHeadline(p).basis }))}
                cash={pair.map((p) => ({ label: p.kind === "asked" ? t("deals.cost.col.asked") : p.label, value: lowest(p).value, note: lowest(p).sub }))}
                costBody={
                  <div data-testid="deal-cost-section">
                    <p className="mb-2 text-supporting text-ink-3">{t("deals.cost.note")}</p>
                    <CostTable paths={pair} heads={pair.map((p) => (p.kind === "asked" ? t("deals.cost.col.asked") : p.label))} caption={t("deals.cost.title")} />
                  </div>
                }
                cashBody={
                  <div data-testid="deal-cash-section">
                    <p className="text-supporting text-ink-3">{t("hv2.deal.consequence.note")}</p>
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2" data-testid="deal-assumption-row">
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
                  </div>
                }
              />
              {paths.length > 1 ? (
                <p className="mt-3">
                  <Button size="sm" aria-expanded={view.investigate} aria-controls="deal-investigate-panel" onClick={() => onView({ investigate: !view.investigate })} data-testid="deal-compare-toggle">
                    {t("deals.full")}
                    <Chevron on={view.investigate} />
                  </Button>
                </p>
              ) : null}
            </div>
          </>
        ) : null}

      </div>
    </section>
  );
  const investigating = Boolean(picture && evaluated && picture.available !== false && (view.compare || view.chart || view.investigate) && !done);
  const investigate =
    investigating && picture ? (
      <div id="deal-investigate-panel" className="flow-card p-5 sm:p-7" data-testid="deal-investigate">
        <Investigate offerId={offer.offer.offer_id} buyer={buyerShort} buyerId={buyerId ?? ""} picture={picture} exposure={exposure} late={late} pickedKey={pickedKey} onPick={(k) => onPick(k)} compareOpen={view.compare || view.investigate} chartOpen={view.chart || view.investigate} why={view.investigate} />
      </div>
    ) : null;
  return (
    <>
      {pane}
      {investigate ? (slot ? createPortal(investigate, slot) : investigate) : null}
    </>
  );
}

function Chevron({ on }: { on: boolean }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={`transition-transform duration-(--dur) ${on ? "rotate-180" : ""}`}>
      <path d="m4 6 4 4 4-4" />
    </svg>
  );
}

/** The commit area's companion: the way to try other terms (the filled button is the commit's; the cash chart and every response are the full analysis, under the cost and cash cards). */
function CompareButtons({ whatif }: { whatif: string }) {
  const { t } = useI18n();
  return (
    <Link href={whatif} className={`${quietLink} px-1`} data-testid="deal-whatif">
      {t("deals.whatif")}
    </Link>
  );
}
