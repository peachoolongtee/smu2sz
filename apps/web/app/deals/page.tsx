"use client";

import Link from "next/link";
import { Fragment, useEffect, useRef, useState } from "react";
import { BeforeTheyAsk } from "@/components/deals/before-they-ask";
import { BuyerAsks } from "@/components/deals/asks";
import { ActiveCommitments } from "@/components/deals/commitments";
import { AgreedDeals } from "@/components/deals/deal-summary";
import { DealDecision } from "@/components/deals/decision";
import { InboxList } from "@/components/deals/inbox-list";
import { RecommendedResponse } from "@/components/deals/response";
import { AdvancedDetails, SelectedBuyer, WorkspaceAsks, WorkspaceImpact } from "@/components/deals/workspace";
import { NextStep, nextLinkCls } from "@/components/next-step";
import { Button, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, ButtonLink } from "@/components/ui";
import { STRATEGY_MVP } from "@/lib/config";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { dealRecordId, getClock, getDeals, getLedger, getState, submitOffer } from "@/lib/api";
import { recordOffer, selectOffer, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";
import { useMode } from "@/lib/mode";
import { offerItems } from "@/lib/offer-items";
import type { VerdictView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useNarrow } from "@/lib/use-narrow";
import { useCurrentOffer } from "@/lib/use-current";
import { useDecision, useDecisions } from "@/lib/use-decision";
import { dealProgress } from "@/lib/decision";
import { whenText } from "@/lib/when";
import { Disclosure } from "@/components/business/kit";

/**
 * Deals, one workspace for the selected buyer, in the server's order (`workspace.order`, wayfinder #65 Wave 3): a compact header (the buyer,
 * the offer's one-line ask, when it was checked), what the buyer asks, what it costs (the immediate discount and the forward figure on their
 * own lines), why it matters, what FLOW recommends, the one priced response with its bound send, the one Action, the agreements, and last,
 * folded, the advanced details. The inbox folds to one row once a deal is selected. Buyer terms appear once. Every figure and sentence is
 * the server's; days are distances from today; the page decides nothing.
 */
export default function DealsPage() {
  const { t, te, lang } = useI18n();
  const mode = useMode();
  // On a phone, once a deal is open the page's own subtitle gives way to the deal: the answer comes up the screen.
  const narrow = useNarrow();
  const cur = useCurrentOffer();
  const demo = useDemo();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The id of the inbox message being read, or null.
  const [reading, setReading] = useState<string | null>(null);
  // Whether the other counters are shown (Option B), tied to the offer it was opened for.
  // Passed down only with STRATEGY_MVP: without the flag the response card keeps its own state, exactly as before the card existed.
  const [compareFor, setCompareFor] = useState<string | null>(null);
  // The offer for which the owner asked for the full inbox ("Back to inbox"); selecting another deal folds it again.
  const [inboxFor, setInboxFor] = useState<string | null>(null);
  const books = useAsync(getState, []);
  // The books' refusal block: the set-aside line in the inbox is the ledger's count, never the page's.
  const ledger = useAsync(() => getLedger(lang), [lang]);
  // The deals' records: each message's words in the inbox are its record's state, read again whenever the books or the clock move.
  const records = useDecisions({ family: "DEAL" });
  const clock = useAsync(getClock, []);
  // The deal summaries (contract ingestion): read again whenever a negotiation is recorded, since the store's version moves.
  const dealsView = useAsync(() => getDeals().catch(() => null), []);
  // The simulated clock: every day on this page is said as a distance from it.
  const today = clock.data?.day ?? books.data?.day ?? 0;
  const known = books.data ? new Set(books.data.state.counterparties.map((c) => c.id)) : null;
  const buyerName = (id: string) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id;

  async function evaluate() {
    if (!cur.offerId) return;
    setBusy(true);
    setError(null);
    try {
      await evaluateAndCache(cur.offerId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  /** Opening a message reads it. One already read is just shown again, so clicking around costs nothing. */
  async function openMessage(m: InboxMessage) {
    setInboxFor(null);
    const seen = Object.values(demo.offers).find((o) => o.documents[0]?.doc_id === m.document.doc_id);
    if (seen) return selectOffer(seen.offer.offer_id);
    setReading(m.id);
    setError(null);
    try {
      const read = await submitOffer(m.fixtureId ? { fixture_id: m.fixtureId } : { counterparty_id: m.counterparty_id, documents: [m.document] });
      recordOffer(read, m.fixtureId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReading(null);
    }
  }

  // `?buyer=BUYER-1` (the chase dialog's thread link) selects that buyer's current deal: the one already read most recently, else the buyer's
  // newest message is read. Once, after the books say who the known buyers are; a buyer the books do not know selects nothing.
  const buyerParam = useRef<{ id: string | null; done: boolean } | null>(null);
  useEffect(() => {
    if (!buyerParam.current) buyerParam.current = { id: new URLSearchParams(window.location.search).get("buyer"), done: false };
    const want = buyerParam.current;
    if (!want.id || want.done || !known) return;
    want.done = true;
    if (!known.has(want.id)) return;
    const mine = INBOX.filter((m) => m.counterparty_id === want.id);
    const readOffers = Object.values(demo.offers).filter((o) => o.offer.counterparty_id === want.id);
    if (cur.offer?.offer.counterparty_id === want.id) return;
    const latest = readOffers[readOffers.length - 1];
    if (latest) selectOffer(latest.offer.offer_id);
    else if (mine[0]) void openMessage(mine[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once, when the books arrive
  }, [Boolean(known)]);

  /** The state of a message's deal in the server's words ("Counter recommended", "Agreed", "Expired"), for its inbox row; null until the record has one. */
  function statusFor(docId: string): string | null {
    const o = Object.values(demo.offers).find((x) => x.documents[0]?.doc_id === docId);
    return o ? (records.data?.decisions.find((d) => d.id === dealRecordId(o.offer.offer_id))?.state_text ?? null) : null;
  }

  const offer = cur.offer;
  const v: VerdictView | null = cur.verdict;
  const ws = v?.workspace ?? null;
  // The deal's record: where it stands (sent, agreed, lapsed, closed) is read from it, never from the answer the browser kept from a click.
  const record = useDecision(offer ? dealRecordId(offer.offer.offer_id) : null).data ?? null;
  const progress = record ? dealProgress(record.state) : null;
  const items = offer ? offerItems(offer.offer) : [];
  const obligations = items.flatMap((i) => (i.group === "obligation" ? [i.obligation] : []));
  // The verdict's bound obligations carry the terms delta ("45 → 60 days"); before the check, the compiled offer's.
  const asks = v?.bound_obligations?.length ? v.bound_obligations : obligations;
  const inboxOpen = !offer || inboxFor === offer.offer.offer_id;

  // The one Action, read from the page's own state (it decides nothing): check the offer, or where the deal stands. A counter to send carries
  // its own primary action in the priced response, so the Action then has nothing to add.
  let next: { text: string; action: React.ReactNode } | null = null;
  if (offer && !v) {
    next = {
      text: t("next.inbox"),
      action: (
        <Button variant="primary" loading={busy} onClick={() => void evaluate()}>
          {t("biz.deals.check")}
        </Button>
      ),
    };
  } else if (offer && v && record && progress?.reached) {
    // The band appears only where it names a real action: the approval still to answer, or the way back to the other offers. An agreement in
    // force or a closed matter is said by the state chip and the Agreements card, and needs no band.
    next =
      progress.tone === "open"
        ? { text: t("next.approval"), action: <Link href="/approvals" className={nextLinkCls}>{t("next.toApprovals")}</Link> }
        : record.state === "NO_DEAL"
          ? {
              text: t("next.noDeal"),
              action: (
                <button type="button" className={nextLinkCls} onClick={() => setInboxFor(offer.offer.offer_id)}>
                  {t("next.backToOffers")}
                </button>
              ),
            }
          : null;
  }

  const compareOpen = Boolean(offer && compareFor === offer.offer.offer_id);

  // Once both parties have agreed, the deal summary (the confirmed contract beside the books) comes before the commitments.
  const commitments = (
    <Fragment key="commitments">
      <AgreedDeals deals={dealsView.data?.deals ?? []} />
      <ActiveCommitments today={today} buyerName={buyerName} hideEmpty />
    </Fragment>
  );

  const abstentions = offer?.offer.abstentions.length ? (
    <div className="mt-3" data-testid="deal-abstentions">
      <Callout tone="warn" title={t("biz.deals.cannotEvaluate")}>
        <ul className="list-disc pl-5 text-sm">
          {offer.offer.abstentions.map((a) => (
            <li key={a.field}>{a.reason}</li>
          ))}
        </ul>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <ButtonLink href="/chat">{t("biz.deals.clarify")}</ButtonLink>
          <Disclosure className="text-xs" summary={t("biz.auditDetails")}>
            <ul className="mt-1 list-disc pl-5 font-mono">
              {offer.offer.abstentions.map((a) => (
                <li key={a.field} className="break-all">
                  {a.field}
                </li>
              ))}
            </ul>
          </Disclosure>
        </div>
      </Callout>
    </div>
  ) : null;

  const inbox = (
    <InboxList
      key="inbox"
      currentDocId={offer?.documents[0]?.doc_id ?? null}
      readDocIds={Object.values(demo.offers).map((o) => o.documents[0]?.doc_id)}
      known={known}
      busy={reading}
      today={today}
      mode={mode}
      statusFor={statusFor}
      onOpen={(m) => void openMessage(m)}
      loadError={books.error}
      onRetry={books.reload}
      collapsed={Boolean(offer) && !inboxOpen}
      onExpand={offer ? () => setInboxFor(offer.offer.offer_id) : undefined}
      onCollapse={offer && inboxOpen ? () => setInboxFor(null) : undefined}
      refusals={ledger.data?.refusals ?? null}
    />
  );

  // The parts of a selected deal, each with its key so the order can differ without losing what a part holds.
  const dealParts: Record<string, React.ReactNode> = {};
  if (offer && !cur.error && !clock.error && !cur.loading && clock.data) {
    dealParts.buyer = (
      <SelectedBuyer
        key="buyer"
        buyer={buyerName(offer.offer.counterparty_id)}
        received={t("biz.deals.messageWhen", { channel: te("channel", offer.documents[0]?.channel ?? "chat"), when: whenText(offer.offer.received_day, today, t) })}
        evaluatedWhen={v ? (record?.evaluation?.evaluated_when ?? v.evaluated_when ?? null) : null}
        state={record ? { code: record.state, text: record.state_text, tone: record.state_tone ?? "neutral" } : null}
      />
    );
    dealParts.buyer_asks = ws ? (
      <WorkspaceAsks key="asks" ws={ws}>{abstentions}</WorkspaceAsks>
    ) : (
      <Card key="asks" id="deal-ask" title={t("biz.deals.ask", { buyer: buyerName(offer.offer.counterparty_id) })}>
        <BuyerAsks asks={asks} />
        {abstentions}
      </Card>
    );
    if (STRATEGY_MVP) dealParts.before = <BeforeTheyAsk key="before" buyerId={offer.offer.counterparty_id} />;
    if (v && ws) {
      dealParts.financial_impact = <WorkspaceImpact key="impact" ws={ws} v={v} today={today} settled={Boolean(record && progress?.reached)} />;
      // Once the deal has an outcome (an agreement in force, a missed payment, no deal) the offer as it was asked is history: its cost, the most the owner
      // could give and the first reserve breach sit under one heading, folded, so they are not read as part of the agreement.
      if (progress?.reached && progress.tone !== "open") {
        dealParts.financial_impact = (
          <Disclosure key="original" card testId="deal-original" summary={t("biz.deals.original.ask")}>
            <div className="space-y-6">
              {dealParts.before}
              {dealParts.financial_impact}
            </div>
          </Disclosure>
        );
        dealParts.before = null;
      }
      dealParts.recommends = <DealDecision key="decision" v={v} record={record} text={ws.recommends.text} reason={ws.why_it_matters.reasons[0] ?? null} />;
      dealParts.priced_response = (
        <RecommendedResponse
          key="response"
          v={v}
          offerId={offer.offer.offer_id}
          today={today}
          mode={mode}
          negotiation={cur.negotiation}
          {...(STRATEGY_MVP ? { compareOpen, onCompareChange: (open: boolean) => setCompareFor(open ? offer.offer.offer_id : null) } : {})}
        />
      );
      dealParts.advanced = <AdvancedDetails key="advanced" ws={ws} v={v} offer={offer} items={items} asks={asks} />;
    }
    if (next) {
      dealParts.next = (
        <NextStep key="next" label={t("next.label")} action={next.action} className="mb-0">
          {next.text}
        </NextStep>
      );
    }
    dealParts.agreements = commitments;
  }
  // One order at every width, the server's (`workspace.order`): the buyer, what FLOW recommends, the priced response, what the buyer asks, what it costs
  // (with why it matters inside), the agreements, the folded details. The Action and the "Before they ask" card sit beside the part they belong to.
  const serverOrder = (ws?.order ?? ["buyer", "recommends", "priced_response", "buyer_asks", "financial_impact", "why_it_matters", "agreements", "advanced"]).filter((k) => k !== "why_it_matters");
  const order = serverOrder.flatMap((k) => (k === "priced_response" ? [k, "next"] : k === "buyer_asks" ? [k, "before"] : [k]));
  const errorNode = error ? <ErrorState key="error" error={error} /> : null;

  return (
    <>
      <PageHeader section="deals" title={t("nav.deals")} subtitle={offer && narrow ? undefined : t("biz.deals.subtitle")} />
      <div className="space-y-6">
        {inbox}

        {errorNode}

        {cur.error || clock.error ? (
          <ErrorState
            error={(cur.error ?? clock.error)!}
            onRetry={() => {
              cur.reload();
              clock.reload();
            }}
          />
        ) : cur.loading || !clock.data ? (
          <LoadingBlock rows={3} />
        ) : !offer ? (
          <>
            <EmptyState title={t("biz.deals.empty")} body={t("biz.deals.empty.body")} action={<ButtonLink href="/chat">{t("chat.open")}</ButtonLink>} />
            {commitments}
          </>
        ) : (
          <>
            {order.map((k) => dealParts[k] ?? null)}
          </>
        )}
      </div>
    </>
  );
}
