"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BeforeTheyAsk } from "@/components/deals/before-they-ask";
import { BuyerAsks } from "@/components/deals/asks";
import { ActiveCommitments } from "@/components/deals/commitments";
import { isAgreed } from "@/components/deals/deal-summary";
import { contractsOff } from "@/components/documents";
import { DealHeading } from "@/components/deals/decision";
import { InboxList } from "@/components/deals/inbox-list";
import { PathsBody, PathsReply, usePathsState } from "@/components/deals/paths-section";
import { AdvancedDetails, SelectedBuyer, WorkspaceAsksCost, WorkspaceWhy } from "@/components/deals/workspace";
import { NextStep, nextLinkCls } from "@/components/next-step";
import { Button, Callout, Card, ErrorState, LoadingBlock, PageHeader, ButtonLink } from "@/components/ui";
import { STRATEGY_MVP } from "@/lib/config";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { dealRecordId, getClock, getDeals, getLedger, getOfferPicture, getState, submitOffer } from "@/lib/api";
import { recordOffer, selectOffer, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";
import { useMode } from "@/lib/mode";
import { offerItems } from "@/lib/offer-items";
import type { OfferPictureView, VerdictView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useNarrow } from "@/lib/use-narrow";
import { useCurrentOffer } from "@/lib/use-current";
import { useDecision, useDecisions } from "@/lib/use-decision";
import { dealProgress } from "@/lib/decision";
import { whenText } from "@/lib/when";
import { Disclosure } from "@/components/business/kit";

/**
 * Deals in the A1 pattern, one workspace for the selected buyer: the verdict is the heading (FLOW's read of the offer, under the status pill),
 * then who and where (the buyer, the five stages), the one Action while the offer is unchecked, what they ask with what each costs you, why it
 * matters, the priced response with its bound send, the agreements and, folded, the advanced details. The inbox folds to one row once a deal is
 * selected. Buyer terms appear once. Every figure and sentence is the server's; days are distances from today; the page decides nothing.
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
  // The deal summaries (contract ingestion): read again whenever a negotiation is recorded (the store's version moves) and when the language changes, since the
  // server writes their sentences. A failed read is shown, not hidden; only a server with contract reading switched off has none to show.
  const dealsView = useAsync(() => getDeals(lang), [lang]);
  const dealsError = contractsOff(dealsView.error) ? undefined : dealsView.error;
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
  // The deals read's row for this offer: FLOW's read of it (`open_offer`), the five stages and the pill's words. Null once the offer is no longer open.
  const dealRow = offer ? (dealsView.data?.deals.find((d) => d.open_offer?.offer_id === offer.offer.offer_id) ?? null) : null;
  const open = dealRow?.open_offer ?? null;
  // The offer's picture (one line per path, the moments where they part) is asked for only while the offer is open and checked: a deal that has an outcome, or an
  // offer not yet checked, does not need it. The read is keyed by the offer: another offer's picture is never shown, and a refetch (the books moved) keeps the one
  // on screen until the new one arrives, so the reply area never remounts. `undefined` is "on its way".
  const pictureOfferId = offer?.offer.offer_id ?? null;
  const wantPicture = Boolean(pictureOfferId && v && open && !cur.negotiation && !progress?.reached);
  const pictureRead = useAsync(
    async () => ({ offerId: pictureOfferId, asked: wantPicture, picture: wantPicture && pictureOfferId ? await getOfferPicture(pictureOfferId, lang).catch(() => null) : null }),
    [pictureOfferId, wantPicture, v?.id, v?.state_version, lang],
  );
  const picture: OfferPictureView | null | undefined = !wantPicture ? null : pictureRead.data?.offerId === pictureOfferId && pictureRead.data.asked ? pictureRead.data.picture : undefined;

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
  // One pick and one cursor drive the reply bar (right under the heading) and the picture with its columns (below it).
  const pathsState = usePathsState(
    picture,
    pictureOfferId,
    STRATEGY_MVP ? compareOpen : undefined,
    STRATEGY_MVP && offer ? (on: boolean) => setCompareFor(on ? offer.offer.offer_id : null) : undefined,
  );

  // Once both parties have agreed, each buyer's deal summary (the confirmed contract beside the books) sits inside that buyer's agreement: one section, not two.
  const commitments = (
    <ActiveCommitments
      key="commitments"
      today={today}
      buyerName={buyerName}
      hideEmpty
      agreed={(dealsView.data?.deals ?? []).filter(isAgreed)}
      dealsDay={dealsView.data?.day ?? null}
      dealsError={dealsError}
      onRetryDeals={dealsView.reload}
    />
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
  const ready = Boolean(offer && !cur.error && !clock.error && !cur.loading && clock.data && !(dealsView.loading && !dealsView.data));
  if (offer && ready) {
    const settledDeal = Boolean(v && ws && record && progress?.reached && progress.tone !== "open");
    dealParts.heading = (
      <DealHeading
        key="heading"
        v={v}
        record={record}
        open={open}
        pillText={dealRow?.needs_you_text ?? null}
        text={ws?.recommends.text}
        reason={ws?.why_it_matters.reasons[0] ?? null}
        title={t("nav.deals")}
      />
    );
    dealParts.buyer = (
      <SelectedBuyer
        key="buyer"
        buyer={buyerName(offer.offer.counterparty_id)}
        received={t("biz.deals.messageWhen", { channel: te("channel", offer.documents[0]?.channel ?? "chat"), when: whenText(offer.offer.received_day, today, t) })}
        evaluatedWhen={v ? (record?.evaluation?.evaluated_when ?? v.evaluated_when ?? null) : null}
        state={record ? { code: record.state, text: record.state_text, tone: record.state_tone ?? "neutral" } : null}
        open={open}
      />
    );
    if (next) {
      dealParts.next = (
        <NextStep key="next" label={t("next.label")} action={next.action} className="mb-0">
          {next.text}
        </NextStep>
      );
    }
    dealParts.buyer_asks = ws ? (
      <WorkspaceAsksCost key="asks" ws={ws} v={v} folded={Boolean(v && !settledDeal)}>{abstentions}</WorkspaceAsksCost>
    ) : (
      <Card flat key="asks" id="deal-ask" title={t("biz.deals.ask", { buyer: buyerName(offer.offer.counterparty_id) })}>
        <BuyerAsks asks={asks} />
        {abstentions}
      </Card>
    );
    if (STRATEGY_MVP) dealParts.before = <BeforeTheyAsk key="before" buyerId={offer.offer.counterparty_id} />;
    if (v && ws) {
      // Why it matters sits behind its fold (its reasons and the cash facts of the offer as asked); once the deal has an outcome it is part of the original ask's fold below.
      dealParts.why = <WorkspaceWhy key="why" ws={ws} v={v} today={today} settled={Boolean(record && progress?.reached)} folded={!settledDeal} />;
      dealParts.priced_response = (
        <PathsReply
          key="response"
          state={pathsState}
          v={v}
          offerId={offer.offer.offer_id}
          today={today}
          mode={mode}
          negotiation={cur.negotiation}
          picture={picture}
          {...(STRATEGY_MVP ? { compareOpen, onCompareChange: (on: boolean) => setCompareFor(on ? offer.offer.offer_id : null) } : {})}
        />
      );
      dealParts.paths = <PathsBody key="paths" state={pathsState} picture={picture} v={v} negotiation={cur.negotiation} />;
      // Once the deal has an outcome (an agreement in force, a missed payment, no deal) the offer as it was asked is history: what they asked and cost,
      // the most the owner could give and why it mattered sit under one heading, folded, so they are not read as part of the agreement.
      if (settledDeal) {
        dealParts.original = (
          <Disclosure key="original" className="border-t border-line pt-1" testId="deal-original" summary={t("biz.deals.original.ask")}>
            <div className="space-y-6">
              {dealParts.buyer_asks}
              {dealParts.before}
              {dealParts.why}
            </div>
          </Disclosure>
        );
        dealParts.buyer_asks = null;
        dealParts.before = null;
        dealParts.why = null;
      }
      dealParts.advanced = <AdvancedDetails key="advanced" ws={ws} v={v} offer={offer} items={items} asks={asks} />;
    }
    dealParts.agreements = commitments;
  }
  // One order at every width, so the DOM order is the visual order and the focus order follows it: the verdict (the heading), the one Action, the reply bar
  // (the priced decision, inside the first screen of a phone), the picture with its moments and the path columns, who and where, what they ask and cost, why it
  // matters (folded), the strategy block, the agreements, the folds. The server's `workspace.order` no longer decides it: the heading is the recommendation.
  const order = ["heading", "next", "priced_response", "paths", "buyer", "buyer_asks", "why", "before", "original", "agreements", "advanced"];
  const errorNode = error ? <ErrorState key="error" error={error} /> : null;

  return (
    <>
      {offer && ready ? null : <PageHeader section="deals" title={t("nav.deals")} subtitle={offer && narrow ? undefined : t("biz.deals.subtitle")} />}
      <div className="space-y-4 sm:space-y-5">
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
        ) : cur.loading || !clock.data || (offer && dealsView.loading && !dealsView.data) ? (
          <LoadingBlock rows={3} />
        ) : !offer ? (
          <>
            <div className="motion-reveal flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-line pb-4" data-testid="deals-empty">
              <p className="min-w-0 flex-[1_1_20rem] text-sm text-ink-2">
                <strong className="font-extrabold text-ink">{t("biz.deals.empty")}</strong> {t("biz.deals.empty.body")}
              </p>
              <ButtonLink href="/chat">{t("chat.open")}</ButtonLink>
            </div>
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
