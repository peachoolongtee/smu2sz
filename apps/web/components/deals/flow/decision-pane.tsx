"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
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
import type { BuyerAcceptedResult, DecisionView, NegotiationView, OfferedResult, OpenOffer, PicturePath, QueueRowView } from "@/lib/types";
import { AcceptBlock, type AcceptOutcome } from "./accept-block";
import { arrivalText, BuyerAnswer } from "./buyer-answer";
import { paneStatus, tabsOf, viewIn, type DealViewKey } from "./deal-model";
import { quietLink } from "./flow-parts";
import { CashTab } from "./cash-tab";
import { ScopeTerms } from "./scope-terms";
import { SendBlock } from "./send-block";
import { useNegotiation } from "./use-negotiation";
import { LifecycleStrip } from "@/components/deals/lifecycle-strip";
import { TrackerBody } from "@/components/tracker/tracker-body";
import { useTracker } from "@/lib/tracker";
import { CostTable } from "./cost-table";
import { BeforeTheyAsk } from "@/components/deals/before-they-ask";
import { STRATEGY_MVP } from "@/lib/config";
import { patchedHref } from "@/lib/selection";
import { ChoicesTable, Recommendation, SectionNav, type SectionItem } from "./deal-overview";
import { EnvelopePackages } from "./investigate";

/** The deal's own view of the page, in the address: the tab (`view=`), the accept review open on arrival (`review=1`). */
export interface DealView {
  view: DealViewKey;
  /** The accept review is open on arrival (`review=1`): a link from Home or the Customer page to a request that needs the owner's review. */
  review: boolean;
}

const AGREED_STATES: ReadonlySet<string> = new Set(["AGREED", "FULFILLED", "MISSED", "EXPIRED", "REVOKED"]);
const RECORD_DONE = new Set(["AGREED", "FULFILLED", "MISSED", "EXPIRED", "REVOKED", "NO_DEAL", "DECLINED", "FAILED", "LAPSED", "REPLIED"]);

const MD = "(min-width: 768px)";
const subscribeMd = (onChange: () => void) => {
  const list = window.matchMedia(MD);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
};
/** True from the tablet width (`md`); where it is false (a phone) the sticky part of the deal header is the compact title and tabs only. */
const useMd = () => useSyncExternalStore(subscribeMd, () => window.matchMedia(MD).matches, () => true);

/** A section change brings the page to its top (the sections replace one another in place; a tall one left behind would hide the top of the next). */
function TabScroll({ view }: { view: DealViewKey }) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo({ top: 0, behavior: "auto" });
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

/** The owner marked the message to the buyer sent: the server's sentence for what was recorded, and what marking it does (and does not do). */
function MarkedResult({ r }: { r: OfferedResult }) {
  return (
    <div role="status" className="mt-4 rounded-tile border border-line bg-subtle px-4 py-3 text-sm" data-testid="deal-marked-sent">
      <p className="font-bold text-ink" data-testid="deal-marked-sent-when">
        {r.message_when}
      </p>
      <p className="mt-1 text-ink-2" data-testid="deal-marked-sent-effect">
        {r.mark_sent_effect_text}
      </p>
    </div>
  );
}

/** The owner recorded the buyer's yes: the server's state word (agreed, or waiting for the owner's approval), what ran, and the agreement's receipt. */
function BuyerYesResult({ r, decision }: { r: BuyerAcceptedResult; decision: string }) {
  const { t } = useI18n();
  return (
    <div role="status" className="mt-4 space-y-3 rounded-tile border border-line bg-subtle px-4 py-3 text-sm" data-testid="deal-buyer-accepted" data-status={r.status}>
      <p className="flex flex-wrap items-center gap-2">
        <StatusPill tone={r.status === "agreed" ? "green" : "amber"}>{r.decision.state_text}</StatusPill>
        {r.execution?.summary_text ? (
          <span className="text-ink" data-testid="deal-buyer-accepted-ran">
            {r.execution.summary_text}
          </span>
        ) : null}
      </p>
      {r.receipt ? <CommitmentReceipt receipt={r.receipt} id={`${decision}-buyer-yes`.replace(/[^A-Za-z0-9_-]/g, "-")} title={t("receipt.title.agreed")} testId="deal-buyer-accepted-receipt" /> : null}
      {r.status === "waiting_approval" ? (
        <ButtonLink href={r.approval_id ? `/approvals#approval-${encodeURIComponent(r.approval_id)}` : "/approvals"} data-testid="deal-buyer-accepted-approvals">
          {t("next.toApprovals")}
        </ButtonLink>
      ) : null}
    </div>
  );
}

/** The record's own account of where a negotiation stands, for one that is out of the owner's hands or finished. */
function RecordBlock({ record, decision, actions }: { record: DecisionView; decision: string; /** What the owner can do while the record waits (the buyer's answer to a counter sent outside FLOW), under the waiting line. */ actions?: ReactNode }) {
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
      {actions}
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
  // The message to the buyer marked sent, and the buyer's yes recorded: the server's answers, kept beside the record that moved on.
  const [marked, setMarked] = useState<OfferedResult | null>(null);
  const [buyerYes, setBuyerYes] = useState<BuyerAcceptedResult | null>(null);
  // A buyer's reply pasted on the deal it answered: that deal's sentence, said here on the reply's own deal.
  const [arrived] = useState(() => arrivalText(decision));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  // The deal header's review button: each press opens the review (the send or the accept block, mounted under the header on every tab); the blocks say whether it is open.
  const [reviewingSend, setReviewingSend] = useState(false);
  const [reviewingAccept, setReviewingAccept] = useState(false);
  const [sendSignal, setSendSignal] = useState(0);
  const [acceptSignal, setAcceptSignal] = useState(0);
  const [declineSignal, setDeclineSignal] = useState(0);
  // A reply picked in the choices table whose review opens as soon as that reply's review block is there.
  const [wantReview, setWantReview] = useState<string | null>(null);
  const [lastOpen, setLastOpen] = useState(false);
  const pathname = usePathname();
  const search = useSearchParams();
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
  // The owner sent a counter outside FLOW and the buyer has not answered: the owner records the answer (the counter sent is the record's).
  const awaitingBuyer = stateCode === "AWAITING_BUYER";
  const sentOutside = record?.response?.sent && record.response.sent.recorded && record.response.sent.outside_flow ? record.response.sent : null;
  const doc = offer.documents[0];
  const paths = (picture?.paths ?? []).filter((p) => p.kind === "asked" || p.kind === "reply");
  const asked = paths.find((p) => p.kind === "asked") ?? null;
  const recommended = paths.find((p) => p.kind === "reply" && p.recommended) ?? null;
  const picked = pickedKey ? (paths.find((p) => p.kind === "reply" && p.key === pickedKey) ?? null) : null;
  const focus: PicturePath | null = picked ?? recommended;
  // The share clause of the economics read (what this concession is, against what the customer brings in a year): drawn only when the server carries it.
  const shareClause = exposure?.economics?.context_text ?? exposure?.economics?.sentence ?? null;

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

  // ---- the sections: Overview, Cash impact, Messages before agreement; Overview, Terms, Messages from it
  const agreedDeal = AGREED_STATES.has(stateCode);
  // (While the picture is on its way the cash section stays: an address that names it is not rewritten before its data has come.)
  const tabs = tabsOf({ agreed: agreedDeal, analysis: analysis || (picture === undefined && !done && !waitsOnApproval) });
  const current: DealViewKey = viewIn(view.view, tabs);
  const accept = picture?.accept ?? null;
  const decisionReady = Boolean(picture && evaluated && picture.available !== false && !done && !waitsOnApproval && stateCode !== "NEEDS_CLARIFICATION" && !sent);
  const sendable = (p: PicturePath) => p.kind === "reply" && p.sendable && (stateCode === "RESPONSE_READY" || stateCode === "RECEIVED") && Boolean(picture) && picture?.available !== false && !sent;
  const canSend = Boolean(focus && sendable(focus));
  // The owner's accept or decline of the request as asked: offered while the request is the question (the server says whether it may be accepted and whether it may be declined).
  const canAccept = decisionReady && Boolean(asked && accept?.available);
  const canDecline = decisionReady && Boolean(asked && accept?.decline_label && accept.decline_available !== false);
  const acceptMounted = decisionReady && Boolean(asked && accept && (accept.available || accept.reason_text || canDecline));
  const reviewing = reviewingSend || reviewingAccept;
  const ready = Boolean(picture && evaluated && picture.available !== false && !done && !waitsOnApproval && stateCode !== "NEEDS_CLARIFICATION" && paths.length > 0);
  // The ask in the buyer's words is the deal's one name (the server's `asks_text` in the dictionary's sentence); it stays when the deal is sent. Without it the queue row's subject, else the record's headline.
  const askTitle = open?.asks_text ? t("dq.ask", { buyer: buyerShort, asks: open.asks_text }) : null;
  const nameFallback = row?.subject_text ?? record?.headline ?? buyerName;

  const startSend = (p: PicturePath) => {
    if (focus?.key === p.key) setSendSignal((x) => x + 1);
    else {
      onPick(p.key === recommended?.key ? null : p.key);
      setWantReview(p.key);
    }
  };

  const reviewSlot = (
    <>
      {canSend && focus && picture ? (
        <SendBlock
          // (keyed by the reply's name, not its id: checking again names new counters, and the review that is open stays open)
          key={`${offer.offer.offer_id}:${focus.label}`}
          offerId={offer.offer.offer_id}
          path={focus}
          picture={picture}
          buyer={buyerShort}
          recordHref={`/decisions/${encodeURIComponent(decision)}`}
          onSent={(r) => {
            setSent(r);
            // The review is gone with the send: it cannot report that its flight ended.
            setBusyBoth(false);
          }}
          onMarked={(r) => {
            setMarked(r);
            // The review is gone with the mark (the deal now waits for the buyer): it cannot report that it closed.
            setReviewingSend(false);
            setBusyBoth(false);
          }}
          onBusy={setBusyBoth}
          openSignal={sendSignal}
          hideTrigger
          onReviewing={setReviewingSend}
        />
      ) : null}
      {acceptMounted && asked && accept && picture ? (
        <AcceptBlock
          key={offer.offer.offer_id}
          offerId={offer.offer.offer_id}
          accept={accept}
          asked={asked}
          picture={picture}
          buyer={buyerShort}
          recordHref={`/decisions/${encodeURIComponent(decision)}`}
          initialOpen={view.review}
          onDone={(o) => {
            setOutcome(o);
            setBusyBoth(false);
          }}
          onBusy={setBusyBoth}
          openSignal={acceptSignal}
          declineSignal={declineSignal}
          hideTrigger
          onReviewing={setReviewingAccept}
        />
      ) : null}
    </>
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

  const abstentions =
    offer.offer.abstentions.length && !done && !waitsOnApproval ? (
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
    ) : null;

  // The section links: the address changes in place (replace), so Back leaves the deal in one step.
  const sectionHref = (k: DealViewKey) => patchedHref(pathname, search.toString(), { view: k === "overview" ? null : k, review: null });
  const sectionLabel = (k: DealViewKey) => (k === "messages" ? t("deals.sec.messages", { buyer: buyerShort }) : k === "overview" ? t(agreedDeal ? "deals.pane.overview" : "deals.choices.title") : t(`deals.pane.${k}` as DictKey));
  const nav = (items: DealViewKey[]): SectionItem[] => items.map((k) => ({ key: k, label: sectionLabel(k), href: sectionHref(k), current: current === k }));
  const sectionNav = (items: DealViewKey[], extra: SectionItem[] = []) => <SectionNav label={t("deals.sec.nav")} items={[...nav(items), ...extra]} busy={busy} />;
  const lastItem: SectionItem[] = history ? [{ key: "last", label: t("deals.sec.last", { buyer: buyerShort }), expanded: lastOpen, onClick: () => setLastOpen((x) => !x) }] : [];

  const answer =
    awaitingBuyer && sentOutside && offer ? (
      <BuyerAnswer
        offerId={offer.offer.offer_id}
        counterId={sentOutside.chosen_counter_id}
        onAccepted={(r) => {
          setBuyerYes(r);
          setBusyBoth(false);
        }}
        onReplied={() => setBusyBoth(false)}
        onBusy={setBusyBoth}
      />
    ) : null;

  const pane = (
    <section aria-labelledby={`${uid}-title`} className="min-w-0" data-testid="deal-pane" data-decision={decision} data-state={stateCode} data-view={current}>
      <Canonical want={view.view} have={current} onGo={onGo} />
      <TabScroll view={current} />
      <Starter want={wantReview} ready={canSend && focus?.key === wantReview} fire={() => setSendSignal((x) => x + 1)} done={() => setWantReview(null)} />
      <div key={decision} className="motion-slide space-y-5">
        <div className="flow-card px-5 pb-4 pt-4 sm:px-7 sm:pb-5 sm:pt-6" data-testid="deal-header">
          <header className="space-y-2">
            <p data-testid="deal-state-chip" data-state={stateCode}>
              <StatusPill tone={status.tone}>{status.text}</StatusPill>
            </p>
            <StableTitle id={`${uid}-title`} ask={askTitle} fallback={nameFallback} />
            {customerLine}
          </header>
          {agreedView && trackerRead?.next ? (
            <div className="mt-3" data-testid="deal-header-actions">
              <ButtonLink href={trackerRead.next.href} variant="primary" data-testid="deal-next-action">
                {trackerRead.next.label}
              </ButtonLink>
            </div>
          ) : null}
          {agreedDeal ? <LifecycleStrip stages={lifeStages} scroll={!isMd} /> : null}
        </div>

        {arrived ? (
          // A buyer's reply the owner just pasted on the deal it answered: the server's sentence, here on the reply's own request.
          <p role="status" className="flow-card max-w-full px-5 py-3 text-[15px] leading-snug text-ink sm:px-7" data-testid="deal-reply-arrived">
            {arrived}
          </p>
        ) : null}

        {current !== "overview" ? sectionNav(tabs) : null}

        {current === "overview" && (reviewSlot || sent || outcome) ? (
          <div className="space-y-3" data-testid="deal-review-slot">
            <div className={reviewing ? "flow-card p-5 sm:p-7" : ""}>{reviewSlot}</div>
          </div>
        ) : null}

        {current === "overview" && (agreedView || agreedLoading) ? (
          <div className="space-y-5">
          <div id={`${uid}-panel-overview`} className="flow-card p-5 sm:p-7" data-testid="deal-panel-overview" data-agreed="true">
            {outcome ? <AcceptResult outcome={outcome} /> : null}
            {sent ? <SendResult n={sent} /> : null}
            {buyerYes ? <BuyerYesResult r={buyerYes} decision={decision} /> : null}
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
          {sectionNav(tabs.filter((k) => k !== "overview"))}
          </div>
        ) : current === "overview" && ready ? (
          <div id={`${uid}-panel-overview`} className="space-y-5" data-testid="deal-panel-overview">
            {sent ? <SendResult n={sent} /> : null}
            {outcome ? <AcceptResult outcome={outcome} /> : null}
            {abstentions}
            <Recommendation
              picture={picture!}
              asked={asked}
              rec={recommended}
              accept={accept}
              reviewing={reviewing}
              canSend={Boolean(recommended && sendable(recommended))}
              canAccept={canAccept}
              canDecline={canDecline}
              onReview={startSend}
              onAcceptReview={() => setAcceptSignal((x) => x + 1)}
              onDecline={() => setDeclineSignal((x) => x + 1)}
              whatif={
                <>
                  {paths.length > 1 ? <CompareButtons whatif={whatifHref} /> : null}
                  {mode === "demo" ? (
                    <Link href="/verdict#negotiation" className={quietLink}>
                      {t("biz.deals.negotiateLink")}
                    </Link>
                  ) : null}
                </>
              }
            />
            <ChoicesTable
              paths={paths}
              recKey={recommended?.key ?? null}
              reviewing={reviewing}
              canReview={sendable}
              canAccept={canAccept}
              onReview={startSend}
              onAcceptReview={() => setAcceptSignal((x) => x + 1)}
              note={
                // Whenever the server withheld a reply (a single reply, or none) it says why: one line each under the table.
                picture?.withheld?.length ? (
                  <div className="space-y-1" data-testid="deal-withheld">
                    {picture.withheld.map((w) => (
                      <p key={w.kind} className="max-w-[68ch] text-[15px] leading-snug text-ink-2">
                        {w.text}
                      </p>
                    ))}
                  </div>
                ) : null
              }
            />
            {sectionNav(
              tabs.filter((k) => k !== "overview"),
              lastItem,
            )}
            {history && lastOpen ? (
              <p className="flow-card max-w-[68ch] p-5 text-[15px] leading-snug text-ink-2" title={historyTitle} data-testid="deal-last-time">
                {history}
              </p>
            ) : null}
          </div>
        ) : current === "overview" ? (
          <div className="space-y-5">
          <div id={`${uid}-panel-overview`} className="flow-card p-5 sm:p-7" data-testid="deal-panel-overview">
            <div className="space-y-4" data-testid="deal-level-decide">
              {done ? originalAsk : null}
              {abstentions}
              {done || waitsOnApproval || stateCode === "NEEDS_CLARIFICATION" || awaitingBuyer ? (
                <>
                  {outcome ? <AcceptResult outcome={outcome} /> : null}
                  {marked ? <MarkedResult r={marked} /> : null}
                  {buyerYes ? <BuyerYesResult r={buyerYes} decision={decision} /> : null}
                  {sentOutside ? (
                    <p className="text-sm text-ink-2" data-testid="deal-sent-outside">
                      {sentOutside.text}
                    </p>
                  ) : null}
                  {record ? <RecordBlock record={record} decision={decision} actions={answer} /> : null}
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
              ) : (
                <div data-testid="deal-undrawable">
                  <p className="max-w-[60ch] text-sm text-ink-2">{picture.unavailable_text ?? t("glance.offer.none")}</p>
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
              )}
            </div>
          </div>
          {sectionNav(tabs.filter((k) => k !== "overview"))}
          </div>
        ) : null}

        {current === "cash" && picture === undefined ? (
          <div className="flow-card p-5 sm:p-7" data-testid={n.error ? "paths-failed" : "paths-loading"}>
            {n.error ? <ErrorState error={n.error} onRetry={n.reload} /> : <LoadingBlock rows={3} />}
          </div>
        ) : null}

        {current === "cash" && picture && analysis ? (
          <div id={`${uid}-panel-cash`} className="flow-card p-5 sm:p-7" data-testid="deal-panel-cash">
            <CashTab offerId={offer.offer.offer_id} picture={picture} paths={paths} />
            {/* The evidence behind the choices: what the owner can live with for this buyer, then the envelope's packages by who may send them (the strategy build). */}
            {STRATEGY_MVP ? (
              <div className="mt-8" data-testid="deal-before-they-ask">
                <BeforeTheyAsk buyerId={buyerId ?? ""} />
              </div>
            ) : null}
            <div className="mt-8">
              <EnvelopePackages buyerId={buyerId ?? ""} />
            </div>
          </div>
        ) : null}

        {current === "terms" ? (
          <div id={`${uid}-panel-terms`} className="flow-card p-5 sm:p-7" data-testid="deal-panel-terms">
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
          <div id={`${uid}-panel-messages`} className="flow-card p-5 sm:p-7" data-testid="deal-panel-messages">
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

/** The deal's one name: the buyer's ask in words. It is kept once seen, so it does not change when the deal is sent and its open offer is gone. */
function StableTitle({ id, ask, fallback }: { id: string; ask: string | null; fallback: string }) {
  const [kept, setKept] = useState<string | null>(ask);
  if (ask && ask !== kept) setKept(ask);
  const text = ask ?? kept ?? fallback;
  return (
    <>
      {/* What a screen reader is told when the deal opens: the same name, never the verdict's short heading. */}
      <Announce text={text} />
      <h1 id={id} tabIndex={-1} className="type-section text-balance text-ink outline-none" data-testid="queue-heading">
        {text}
      </h1>
    </>
  );
}

/** Starts the send review of a reply picked from the choices table once that reply's review block is mounted (it is keyed by the reply, so it is new after the pick). */
function Starter({ want, ready, fire, done }: { want: string | null; ready: boolean; fire: () => void; done: () => void }) {
  useEffect(() => {
    if (!want || !ready) return;
    fire();
    done();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per pick
  }, [want, ready]);
  return null;
}

/** The way to try other terms (a quiet link beside the recommendation's buttons). */
function CompareButtons({ whatif }: { whatif: string }) {
  const { t } = useI18n();
  return (
    <Link href={whatif} className={`${quietLink} px-1`} data-testid="deal-whatif">
      {t("deals.whatif")}
    </Link>
  );
}
