"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { CustomerName } from "@/components/customer-link";
import { Disclosure } from "@/components/business/kit";
import { ChasePayment } from "@/components/business/chase-payment";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { Button, ButtonLink, Callout, ErrorState, LoadingBlock } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { StatusPill } from "@/components/ui/status-pill";
import type { DictKey } from "@/lib/dictionary";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import type { DecisionView, NegotiationView, OpenOffer, PicturePath, QueueRowView } from "@/lib/types";
import { AcceptBlock, type AcceptOutcome } from "./accept-block";
import { paneStatus, tabsOf, viewIn, type DealViewKey } from "./deal-model";
import { quietLink } from "./flow-parts";
import { CompareTab } from "./compare-tab";
import { CashTab } from "./cash-tab";
import { DealTabs } from "./deal-tabs";
import { ScopeTerms } from "./scope-terms";
import { SendBlock } from "./send-block";
import { useNegotiation } from "./use-negotiation";
import { LifecycleStrip } from "@/components/deals/lifecycle-strip";
import { TrackerBody } from "@/components/tracker/tracker-body";
import { useTracker } from "@/lib/tracker";
import { CostTable } from "./cost-table";

/** The deal's own view of the page, in the address: the tab (`view=`), the payment-timing assumption (`scenario=late`) and the accept review open on arrival (`review=1`). */
export interface DealView {
  view: DealViewKey;
  late: boolean;
  /** The responses the chart draws (`lines`, the paths' keys, comma separated); null is the default pair. */
  lines: string | null;
  /** The accept review is open on arrival (`review=1`): a link from Home or the Customer page to a request that needs the owner's review. */
  review: boolean;
}

const AGREED_STATES: ReadonlySet<string> = new Set(["AGREED", "FULFILLED", "MISSED", "EXPIRED", "REVOKED"]);
const RECORD_DONE = new Set(["AGREED", "FULFILLED", "MISSED", "EXPIRED", "REVOKED", "NO_DEAL", "DECLINED", "FAILED", "LAPSED"]);

const MD = "(min-width: 768px)";
const subscribeMd = (onChange: () => void) => {
  const list = window.matchMedia(MD);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
};
/** True from the tablet width (`md`); where it is false (a phone) the sticky part of the deal header is the compact title and tabs only. */
const useMd = () => useSyncExternalStore(subscribeMd, () => window.matchMedia(MD).matches, () => true);

/**
 * A tab change brings the new tab's top to just below the sticky part of the deal header (the page keeps its scroll otherwise, and a tall tab left behind would hide the new one's top under the
 * header). Nothing moves when the tab's top is already in view below the header.
 */
function TabScroll({ view }: { view: DealViewKey }) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const id = window.requestAnimationFrame(() =>
      window.requestAnimationFrame(() => {
        const panel = document.querySelector<HTMLElement>('[data-testid^="deal-panel-"]');
        const header = document.querySelector<HTMLElement>('[data-testid="deal-header"]');
        const bar = document.querySelector<HTMLElement>('[data-testid="deal-sticky-bar"]');
        if (!panel) return;
        const appHeader = 64;
        const stuck = header && getComputedStyle(header).position === "sticky" ? header.offsetHeight : bar ? bar.offsetHeight : 0;
        const desired = panel.getBoundingClientRect().top + window.scrollY - appHeader - stuck - 8;
        if (window.scrollY > desired) window.scrollTo({ top: Math.max(0, desired), behavior: "auto" });
      }),
    );
    return () => window.cancelAnimationFrame(id);
  }, [view]);
  return null;
}

/** An address that names a tab the deal does not have (Compare on a deal with nothing to compare, Terms before agreement) is written as the tab it shows. */
function Canonical({ want, have, onGo }: { want: DealViewKey; have: DealViewKey; onGo: (patch: Record<string, string | null>, how?: "push" | "replace") => void }) {
  useEffect(() => {
    if (want !== have) onGo({ view: have === "overview" ? null : have }, "replace");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per mismatch
  }, [want, have]);
  return null;
}

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
  onGo,
  onPick,
  onClose,
  onBusy,
  irrelevantText,
  inbox,
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
  /** Change the address in place (a null removes the key). */
  onGo: (patch: Record<string, string | null>, how?: "push" | "replace") => void;
  onPick: (key: string | null) => void;
  onClose: () => void;
  onBusy: (busy: boolean) => void;
  /** The server's sentence when it could not honour the selection (`context.irrelevant_text`). */
  irrelevantText: string | null;
  /** The buyer's thread of the inbox, for the Messages tab (the page reads and opens messages). */
  inbox?: (buyerId: string | null) => ReactNode;
}) {
  const { t, te } = useI18n();
  const uid = useId();
  const mode = useMode();
  const n = useNegotiation(decision, { agreedPicture: view.view === "terms" });
  const isMd = useMd();
  // An agreed deal's Overview is the tracker (round three, section 11): the same read and the same body as the tracker's own page.
  const agreedNow = AGREED_STATES.has(n.record?.state ?? "");
  const tracker = useTracker(agreedNow ? decision : null);
  const [sent, setSent] = useState<NegotiationView | null>(null);
  // The owner's accept or decline of a request as asked, once it has been answered: the review is gone when the record moves on, its words stay beside the record.
  const [outcome, setOutcome] = useState<AcceptOutcome | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  // The deal header's review button: each press opens the review (the send or the accept block, mounted under the header on every tab); the blocks say whether it is open.
  const [reviewing, setReviewing] = useState(false);
  const [signal, setSignal] = useState(0);
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
  const firstReply = paths.find((p) => p.kind === "reply") ?? null;
  const showsRecommended = focus !== null && focus.key === recommended?.key;
  // The share clause of the economics read (what this concession is, against what the customer brings in a year): drawn only when the server carries it.
  const shareClause = exposure?.economics?.context_text ?? exposure?.economics?.sentence ?? null;
  const late = view.late && Boolean(exposure?.stress.paths);
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

  const waitsOnApproval = stateCode === "AUTHORIZATION_REQUIRED";
  const approvalId = record?.authorization?.approval_id ?? null;
  const whatifHref = `/whatif?customer=${encodeURIComponent(buyerId ?? "")}&decision=${encodeURIComponent(decision)}&from=deal`;

  const status = paneStatus(row, record?.state_text, stateCode);
  const trackerRead = tracker.data;
  const agreedView = AGREED_STATES.has(stateCode) && trackerRead?.available === true;
  const agreedLoading = AGREED_STATES.has(stateCode) && trackerRead === undefined && !tracker.error;
  const lifeStages = (agreedView ? (trackerRead?.lifecycle_stages ?? null) : null) ?? record?.lifecycle_stages ?? picture?.lifecycle_stages ?? null;
  // The carry-over: what the buyer's last agreed or ended deal was, one quiet line; it changes no verdict, counter, plan or authority and says so in its title.
  const history = (picture?.buyer_history_text ?? record?.buyer_history_text) || null;
  const historyTitle = picture?.buyer_history_title ?? record?.buyer_history_title ?? undefined;
  const agreedPath = paths.find((p) => p.key === (record?.response as { sent?: { accepted_counter_id?: string | null } } | undefined)?.sent?.accepted_counter_id) ?? null;
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

  // ---- the tabs (round three, section 7): Overview, Compare responses, Cash impact, Messages before agreement; Overview, Terms, Messages from it
  const agreedDeal = AGREED_STATES.has(stateCode);
  // (While the picture is on its way the comparison tabs stay: an address that names one is not rewritten before its data has come.)
  const tabs = tabsOf({ agreed: agreedDeal, analysis: analysis || (picture === undefined && !done && !waitsOnApproval) });
  const current: DealViewKey = viewIn(view.view, tabs);
  const accept = picture?.accept ?? null;
  const decisionReady = Boolean(picture && evaluated && picture.available !== false && !done && !waitsOnApproval && stateCode !== "NEEDS_CLARIFICATION" && !sent);
  // The one review the header offers: the send review of the reply in focus, else the owner's accept of the request as asked (a request FLOW has no reply for).
  const reviewKind: "send" | "accept" | null = canSend && focus && picture ? "send" : decisionReady && !focus && asked && accept && (accept.available || accept.reason_text || (accept.decline_label && accept.decline_available !== false)) ? "accept" : null;
  const topic = row?.topic_text ?? title;
  const tabLabel = (k: DealViewKey) => t(`deals.pane.${k}` as DictKey);
  const reviewSlot =
    reviewKind === "send" && focus && picture ? (
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
        openSignal={signal}
        hideTrigger
        onReviewing={setReviewing}
      />
    ) : reviewKind === "accept" && asked && accept && picture ? (
      <AcceptBlock
        key={offer.offer.offer_id}
        offerId={offer.offer.offer_id}
        accept={accept}
        asked={asked}
        picture={picture}
        buyer={buyerShort}
        recordHref={`/decisions/${encodeURIComponent(decision)}`}
        initialOpen={view.review}
        onDone={setOutcome}
        onBusy={setBusyBoth}
        openSignal={signal}
        hideTrigger
        onReviewing={setReviewing}
      />
    ) : null;
  const crumbs = (label: string) => (
    <nav aria-label={t("deals.pane.crumbs")} className="mb-4" data-testid="deal-crumbs">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-2">
        <li>
          <CustomerName id={buyerId} decision={decision} className="font-bold text-ink" testId="deal-crumb-customer">
            {buyerShort}
          </CustomerName>
        </li>
        <li aria-hidden>/</li>
        <li>
          <button type="button" onClick={() => onGo({ view: null })} className="inline-flex min-h-8 items-center font-bold text-ink underline-offset-2 hover:underline focus-visible:underline touch:min-h-11" data-testid="deal-crumb-deal">
            {topic}
          </button>
        </li>
        <li aria-hidden>/</li>
        <li aria-current="page" className="font-bold text-ink">
          {label}
        </li>
      </ol>
    </nav>
  );

  // The original ask is history once the deal has an outcome: folded, and said not to be the agreement.
  const originalAsk = (
    <Disclosure testId="deal-original" className="mt-5 border-t border-line pt-1" summary={t("biz.deals.original.ask")}>
      <div className="pt-2">
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
    </Disclosure>
  );

  const pane = (
    <section aria-labelledby={`${uid}-title`} className="min-w-0" data-testid="deal-pane" data-decision={decision} data-state={stateCode} data-view={current}>
      <Announce text={title} />
      <Canonical want={view.view} have={current} onGo={onGo} />
      <TabScroll view={current} />
      <div key={decision} className="motion-slide">
        {/* The deal header holds still while the page scrolls (from md and where the window is tall enough): the primary action never leaves the screen. */}
        <div className="z-20 -mx-3 bg-canvas px-3 pb-3 pt-1 [@media(min-height:44rem)]:md:sticky [@media(min-height:44rem)]:md:top-16" data-testid="deal-header">
          <div className="flow-card px-5 pt-4 sm:px-7">
            <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
              <div className="min-w-0">
                <p className="mb-1.5" data-testid="deal-state-chip" data-state={stateCode}>
                  <StatusPill tone={status.tone}>{status.text}</StatusPill>
                </p>
                <h2 id={`${uid}-title`} tabIndex={-1} className="type-section text-balance text-ink" data-testid="queue-heading">
                  {title}
                </h2>
                {customerLine}
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2" data-testid="deal-header-actions">
                {reviewKind && !reviewing ? (
                  <Button variant={reviewKind === "send" ? "primary" : "secondary"} aria-expanded={false} onClick={() => setSignal((n) => n + 1)} data-testid={reviewKind === "send" ? "queue-review-open" : "accept-review-open"}>
                    {reviewKind === "send" ? t("deals.review.counter") : t("accept.review")}
                  </Button>
                ) : null}
                {agreedView && trackerRead?.next ? (
                  <ButtonLink href={trackerRead.next.href} variant="primary" data-testid="deal-next-action">
                    {trackerRead.next.label}
                  </ButtonLink>
                ) : null}
                <Button variant="ghost" onClick={onClose} disabled={busy} aria-label={t("deals.close")} data-testid="deal-close">
                  <span aria-hidden>×</span> {t("deals.dismiss")}
                </Button>
              </div>
            </header>
            <LifecycleStrip stages={lifeStages} scroll={!isMd} />
            {isMd ? <DealTabs label={t("deals.pane.tabs")} tabs={tabs.map((k) => ({ value: k, label: tabLabel(k) }))} value={current} onChange={(k) => onGo({ view: k === "overview" ? null : k })} idPrefix={uid} /> : <div className="pb-4" />}
          </div>
        </div>
        {/* A phone: the header above scrolls away; what stays under the app's header is the compact title and the tabs (the review button and the strip do not stick). */}
        {isMd ? null : (
          <div className="sticky top-16 z-20 -mx-3 bg-canvas px-3 pb-1 pt-1" data-testid="deal-sticky-bar">
            <div className="flow-card px-4 pt-2">
              <p className="truncate text-sm font-bold text-ink" data-testid="deal-sticky-title">
                {title}
              </p>
              <DealTabs label={t("deals.pane.tabs")} tabs={tabs.map((k) => ({ value: k, label: tabLabel(k) }))} value={current} onChange={(k) => onGo({ view: k === "overview" ? null : k })} idPrefix={uid} />
            </div>
          </div>
        )}

        {reviewSlot || sent || outcome ? (
          <div className="mt-1 space-y-3" data-testid="deal-review-slot">
            {reviewSlot ? <div className={reviewing ? "flow-card p-5 sm:p-7" : ""}>{reviewSlot}</div> : null}
            {sent && current !== "overview" ? <SendResult n={sent} /> : null}
            {outcome && current !== "overview" ? <AcceptResult outcome={outcome} /> : null}
          </div>
        ) : null}

        {current === "overview" && (agreedView || agreedLoading) ? (
          <div id={`${uid}-panel-overview`} role="tabpanel" aria-labelledby={`${uid}-tab-overview`} className="flow-card mt-1 p-5 sm:p-7" data-testid="deal-panel-overview" data-agreed="true">
            {outcome ? <AcceptResult outcome={outcome} /> : null}
            {sent ? <SendResult n={sent} /> : null}
            {agreedView && trackerRead ? (
              <div className="flex flex-col gap-6" data-testid="deal-tracker">
                <TrackerBody d={trackerRead} mode="deal" />
                <p className="text-sm">
                  <Link href={`/decisions/${encodeURIComponent(decision)}`} className={quietLink} data-testid="deal-record-link">
                    {t("deals.record")}
                  </Link>
                </p>
              </div>
            ) : (
              <LoadingBlock rows={4} />
            )}
          </div>
        ) : current === "overview" ? (
        <div id={`${uid}-panel-overview`} role="tabpanel" aria-labelledby={`${uid}-tab-overview`} className="flow-card mt-1 p-5 sm:p-7" data-testid="deal-panel-overview">
        {/* Level 1: decide */}
        <div className="space-y-4" data-testid="deal-level-decide">
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
            {doc?.text && !open?.asks_text ? (
              <figure className="mt-1.5 border-l-2 border-line-strong pl-3" data-testid="deal-ask-quote">
                <blockquote className="max-w-[68ch] text-[15px] leading-snug text-ink">“{doc.text}”</blockquote>
                <figcaption className="mt-1 text-supporting text-ink-3">{record?.source.received_when ? t("biz.deals.messageWhen", { channel: te("channel", doc.channel ?? "chat"), when: record.source.received_when }) : te("channel", doc.channel ?? "chat")}</figcaption>
              </figure>
            ) : null}
            {open?.asks_text ? (
              <p className="mt-2 max-w-[68ch] text-sm leading-snug text-ink-2" data-testid="queue-ask">
                {t("dq.ask", { buyer: buyerShort, asks: open.asks_text })}
              </p>
            ) : null}
          </div>

          )}

          {!done && history ? (
            <p className="max-w-[68ch] text-supporting text-ink-2" title={historyTitle} data-testid="deal-last-time">
              {history}
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
          ) : picture === undefined && n.error ? (
            // The reply's picture could not be read (a slow or failed read): say so, with Retry, never "Loading" for ever.
            <div data-testid="paths-failed">
              <ErrorState error={n.error} onRetry={n.reload} />
            </div>
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
                <div className="space-y-2" data-testid="queue-recommends" data-path={focus.key === recommended?.key ? "recommended" : "other"}>
                  <h3 className="text-supporting font-bold text-ink-3" data-testid="deal-recommends-title">
                    {showsRecommended ? t("deals.ov.reply", { label: focus.label }) : t("deals.selected", { label: focus.label })}
                  </h3>
                  {focus.reply_text ? (
                    <p className="max-w-[68ch] font-display text-lg font-bold leading-snug text-ink" data-testid="queue-option">
                      {focus.reply_text}
                    </p>
                  ) : null}
                  {!showsRecommended && recommended ? (
                    <div>
                      <Button size="sm" onClick={() => onPick(null)} disabled={busy} data-testid="path-reply-back">
                        {t("biz.deals.reply.back", { label: recommended.label })}
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-2" data-testid="deal-no-reply">
                  <h3 className="text-supporting font-bold text-ink-3">{t("deals.ov.noReply")}</h3>
                  <p className="max-w-[68ch] text-[15px] leading-snug text-ink">{asked?.decides_text ?? t("glance.offer.none")}</p>
                </div>
              )}

              {/* The recommendation says what it is (round three, section 3): the reply FLOW can send within the mandate, and, when another needs the owner, that one and its stated cost. Never "best". */}
              {picture.recommendation ? (
                <div className="space-y-1.5" data-testid="deal-recommendation">
                  <p className="max-w-[68ch] font-display text-base font-extrabold leading-snug text-ink" data-testid="deal-mandate">
                    {picture.recommendation.mandate_text}
                  </p>
                  {picture.recommendation.alternative_text ? (
                    <p className="max-w-[68ch] text-[15px] leading-snug text-ink-2" data-testid="deal-alternative">
                      {picture.recommendation.alternative_text}
                    </p>
                  ) : null}
                </div>
              ) : null}

              <section aria-label={t("deals.terms.title")} data-testid="deal-terms-section">
                <p className="mb-1 text-supporting font-bold text-ink-3">
                  {t("deals.terms.title")} <span className="font-normal">· {t("deals.terms.note")}</span>
                </p>
                <ScopeTerms
                  picture={picture}
                  paths={paths}
                  heads={paths.map((p) => (p.kind === "asked" ? t("deals.ov.col.asked") : p.key === firstReply?.key ? t("deals.ov.col.reply") : p.label))}
                  subs={paths.map((p) => (p.kind === "reply" && p.key === firstReply?.key ? p.label : null))}
                />
              </section>

              <ActionGroup className="mt-4" testId="deal-actions" label={t("deals.actions")}>
                {paths.length > 1 ? (
                  <Button size="sm" onClick={() => onGo({ view: "compare" })} data-testid="deal-to-compare">
                    {t("deals.pane.compare")}
                  </Button>
                ) : null}
                {paths.length > 1 ? <CompareButtons whatif={whatifHref} /> : null}
                {mode === "demo" ? (
                  <Link href="/verdict#negotiation" className={quietLink}>
                    {t("biz.deals.negotiateLink")}
                  </Link>
                ) : null}
              </ActionGroup>
              {sent ? <SendResult n={sent} /> : null}
              {outcome ? <AcceptResult outcome={outcome} /> : null}
            </>
          )}
        </div>

        </div>
        ) : null}

        {(current === "compare" || current === "cash") && picture === undefined ? (
          <div className="flow-card mt-1 p-5 sm:p-7" data-testid={n.error ? "paths-failed" : "paths-loading"}>
            {n.error ? <ErrorState error={n.error} onRetry={n.reload} /> : <LoadingBlock rows={3} />}
          </div>
        ) : null}

        {current === "compare" && picture && analysis ? (
          <div id={`${uid}-panel-compare`} role="tabpanel" aria-labelledby={`${uid}-tab-compare`} className="flow-card mt-1 p-5 sm:p-7" data-testid="deal-panel-compare">
            {crumbs(t("deals.pane.compare"))}
            <CompareTab
              picture={picture}
              paths={paths}
              buyerId={buyerId ?? ""}
              focusKey={focus?.key ?? null}
              onPick={(k) => onPick(k)}
              onReviewSelected={reviewKind === "send" && !reviewing ? () => setSignal((n) => n + 1) : undefined}
              onReviewRequest={reviewKind === "accept" && !reviewing ? () => setSignal((n) => n + 1) : undefined}
              onBack={() => onGo({ view: null })}
            />
          </div>
        ) : null}

        {current === "cash" && picture && analysis ? (
          <div id={`${uid}-panel-cash`} role="tabpanel" aria-labelledby={`${uid}-tab-cash`} className="flow-card mt-1 p-5 sm:p-7" data-testid="deal-panel-cash">
            {crumbs(t("deals.pane.cash"))}
            <CashTab offerId={offer.offer.offer_id} picture={picture} paths={paths} exposure={exposure} buyer={buyerShort} lines={view.lines} late={late} onLines={(keys) => onGo({ lines: keys.join(",") }, "replace")} onLate={(l) => onGo({ scenario: l ? "late" : null }, "replace")} />
          </div>
        ) : null}

        {current === "terms" ? (
          <div id={`${uid}-panel-terms`} role="tabpanel" aria-labelledby={`${uid}-tab-terms`} className="flow-card mt-1 p-5 sm:p-7" data-testid="deal-panel-terms">
            {/* After agreement: the terms by scope of the agreed response alone (the column "Agreed"), with the cost rows quoted when it was agreed; no comparison, no chart. */}
            {picture && agreedPath ? (
              <div className="space-y-6" data-testid="deal-agreed-terms">
                <ScopeTerms picture={picture} paths={[agreedPath]} heads={[t("deals.terms.agreed")]} testId="deal-agreed-scope-terms" />
                <div>
                  <h3 className="mb-1 text-supporting font-bold text-ink-3">{t("deals.terms.agreedCost")}</h3>
                  <CostTable paths={[agreedPath]} heads={[t("deals.terms.agreed")]} caption={t("deals.terms.agreedCost")} testId="deal-agreed-cost-table" />
                </div>
                {record ? <RecordBlock record={record} decision={decision} /> : null}
                {originalAsk}
              </div>
            ) : record ? (
              <>
                <RecordBlock record={record} decision={decision} />
                {originalAsk}
              </>
            ) : null}
          </div>
        ) : null}

        {current === "messages" ? (
          <div id={`${uid}-panel-messages`} role="tabpanel" aria-labelledby={`${uid}-tab-messages`} className="flow-card mt-1 p-5 sm:p-7" data-testid="deal-panel-messages">
            <h3 className="text-supporting font-bold text-ink-3">{t("deals.askTitle", { buyer: buyerShort })}</h3>
            {doc?.text ? (
              <figure className="mt-1.5 border-l-2 border-line-strong pl-3" data-testid="deal-ask-quote-messages">
                <blockquote className="max-w-[68ch] text-[15px] leading-snug text-ink">“{doc.text}”</blockquote>
                <figcaption className="mt-1 text-supporting text-ink-3">{record?.source.received_when ? t("biz.deals.messageWhen", { channel: te("channel", doc.channel ?? "chat"), when: record.source.received_when }) : te("channel", doc.channel ?? "chat")}</figcaption>
              </figure>
            ) : null}
            {inbox ? (
              <div className="mt-6" data-testid="deal-thread">
                {inbox(buyerId)}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );

  return pane;
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
