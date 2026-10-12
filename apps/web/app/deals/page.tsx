"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { BeforeTheyAsk } from "@/components/deals/before-they-ask";
import { BuyerAsks } from "@/components/deals/asks";
import { ActiveCommitments } from "@/components/deals/commitments";
import { isAgreed } from "@/components/deals/deal-summary";
import { contractsOff } from "@/components/documents";
import { DealHeading } from "@/components/deals/decision";
import { InboxList } from "@/components/deals/inbox-list";
import { contextQuery, exposureFor, firstOpenInvoice, openTab, queueRows, stressHref, type QueueRow, type QueueTab } from "@/components/deals/queue/model";
import { QueueAside } from "@/components/deals/queue/queue-aside";
import { QueueDetail } from "@/components/deals/queue/queue-detail";
import { QueueReadOnly } from "@/components/deals/queue/queue-readonly";
import { QueueBody, QueueHead } from "@/components/deals/queue/queue";
import { PathsBody, PathsReply, usePathsState } from "@/components/deals/paths-section";
import { AdvancedDetails, SelectedBuyer, WorkspaceAsksCost, WorkspaceWhy } from "@/components/deals/workspace";
import { NextStep, nextLinkCls } from "@/components/next-step";
import { Button, Callout, Card, ErrorState, LoadingBlock, PageHeader, ButtonLink, type Tone } from "@/components/ui";
import { STRATEGY_MVP } from "@/lib/config";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { dealRecordId, getClock, getDeals, getLedger, getOfferExposure, getOfferPicture, getState, submitOffer } from "@/lib/api";
import { recordOffer, selectOffer, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";
import { useMode } from "@/lib/mode";
import { offerItems } from "@/lib/offer-items";
import type { DealsContext, ExposureView, OfferPictureView, VerdictView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useNarrow, useShort } from "@/lib/use-narrow";
import { useCurrentOffer } from "@/lib/use-current";
import { useDecision, useDecisions } from "@/lib/use-decision";
import { dealProgress } from "@/lib/decision";
import { whenText } from "@/lib/when";
import { Disclosure } from "@/components/business/kit";

/**
 * Deals in the A1 pattern, one workspace for the selected buyer, in the remediation's order at every width: the verdict is the heading (FLOW's read of the
 * offer, under the status pill), the one Action while the offer is unchecked, the priced response (the reply bar with its bound send) directly under the
 * heading, the picture of the three paths with its moments and columns, who and where (the buyer, the five stages), then what they ask with what each costs
 * you and why it matters (both behind closed folds), the agreements and, folded, the advanced details. The inbox folds to one row once a deal is selected.
 * Buyer terms appear once. Every figure and sentence is the server's; days are distances from today; the page decides nothing.
 */
export default function DealsPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <Deals />
    </Suspense>
  );
}

function Deals() {
  const { t, te, lang } = useI18n();
  const params = useSearchParams();
  const mode = useMode();
  // On a phone, once a deal is open the page's own subtitle gives way to the deal: the answer comes up the screen.
  const narrow = useNarrow();
  const short = useShort();
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
  // What the page was opened with (a link from a customer or an invoice names them): the deals read then says where the owner came from (`open_offer.context.back`).
  const [opened] = useState<DealsContext>(() => ({ customer: params.get("customer"), invoice: params.get("invoice"), path: params.get("path") }));
  const dealsView = useAsync(() => getDeals(lang, opened), [lang, opened.customer, opened.invoice, opened.path]);
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

  // ---- The decision queue (the open offer's exposure read): the same reads, laid out as four tabs, a list, one selected deal and its aside.
  // The exposure read is asked for as soon as an offer is open (it needs no verdict). The server's FEATURE_EXPOSURE decides: with it off the read is absent and the page below is the page as it was.
  // `undefined` is "on its way", null "the server has no exposure read": the page then keeps its current form. Once the queue has shown it stays for the visit.
  const exposureRead = useAsync(
    async () => ({ offerId: pictureOfferId, asked: Boolean(open), view: pictureOfferId && open ? await getOfferExposure(pictureOfferId, lang) : null }),
    [pictureOfferId, Boolean(open), v?.id, v?.state_version, lang],
  );
  const exposureNow: ExposureView | null | undefined = !pictureOfferId || !open ? null : exposureRead.data?.offerId === pictureOfferId && exposureRead.data.asked ? exposureRead.data.view : undefined;
  // Only a server that has the read switched off (403 FEATURE_DISABLED) or lacks the route (404) answers "absent" (null); any other failure is said, with Retry.
  const exposureError = open && exposureRead.error ? <ErrorState key="exposure-error" error={exposureRead.error} onRetry={exposureRead.reload} /> : null;
  // A line the owner opened that has no open request (agreed, setup), and whether a send is in flight (nothing may change the selection under it).
  const [rowSel, setRowSel] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [queueSeen, setQueueSeen] = useState(false);
  if (exposureNow && !queueSeen) setQueueSeen(true);
  const queueOn = queueSeen || Boolean(exposureNow);
  // While the page cannot yet tell (the deals read has not listed the offer just read, or its exposure read is on its way) it waits, so the current page never shows for a moment
  // before the queue; a server without the read answers at once (absent), and the current page follows.
  const queuePending = !queueOn && Boolean(offer) && ((Boolean(open) && exposureNow === undefined && !exposureRead.error) || (!open && dealsView.loading));
  // The address is written with the history's own replaceState (Next keeps `useSearchParams` in step): no navigation, no server round trip, the hash kept.
  // The context in the address and nowhere else: `customer`, `decision` (the deal's record), `path` (the picked path), and the `tab`. The address leads: a path or a
  // decision it names is picked when it arrives (a back link, a reload); a pick or a selection the owner makes is written to it. The address is only filled in where it is silent.
  const setQuery = (set: Record<string, string | null>, force = false) => {
    const q = new URLSearchParams(window.location.search);
    let changed = false;
    for (const [k, val] of Object.entries(set)) {
      if (val && q.get(k) !== val) {
        q.set(k, val);
        changed = true;
      } else if (!val && q.has(k)) {
        q.delete(k);
        changed = true;
      }
    }
    if (changed || force) window.history.replaceState(null, "", `/deals?${q.toString()}${window.location.hash}`);
  };
  // The paths this page has written to the address and that have not come back yet, in order: an address that is none of them was changed from outside (a back link, a reload),
  // and only then does it pick. (Two quick picks leave two writes in flight; the first one landing must not undo the second.)
  const writes = useRef<string[]>([]);
  const pathParam = params.get("path");
  useEffect(() => {
    if (!pathParam) return;
    const mine = writes.current.indexOf(pathParam);
    if (mine >= 0) {
      writes.current = writes.current.slice(mine + 1);
      return;
    }
    if (pathsState.picked?.key !== pathParam && pathsState.paths.some((p) => p.key === pathParam)) pathsState.onPick(pathParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- follows the address (a back link, a reload) and the arrival of the paths
  }, [pathParam, pathsState.paths]);
  // The offer the address itself selected (a back link): any other change of the selected offer is the owner's, and starts on that deal's own recommended path.
  const fromAddress = useRef<string | null>(null);
  const lastOffer = useRef<string | null>(null);
  const decisionParam = params.get("decision");
  useEffect(() => {
    const id = decisionParam?.startsWith("deal:") ? decisionParam.slice(5) : null;
    if (id && id !== cur.offerId) {
      fromAddress.current = id;
      selectOffer(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- follows the address (a back link), not the store
  }, [decisionParam]);
  const decisionNow = offer && open ? dealRecordId(offer.offer.offer_id) : null;
  const pickNow = pathsState.picked?.key ?? null;
  const offerNow = offer?.offer.offer_id ?? null;
  useEffect(() => {
    const changedByOwner = lastOffer.current !== null && offerNow !== null && offerNow !== lastOffer.current && fromAddress.current !== offerNow;
    if (offerNow) lastOffer.current = offerNow;
    if (queueOn && decisionNow) setQuery({ decision: decisionNow, ...(changedByOwner ? { path: null } : {}) });
  }, [queueOn, decisionNow, offerNow]);
  useEffect(() => {
    if (queueOn && !pathParam && pickNow) setQuery({ path: pickNow });
  }, [queueOn, pathParam, pickNow]);
  const queuePaths: typeof pathsState = {
    ...pathsState,
    onPick: (key) => {
      pathsState.onPick(key);
      writes.current = [...writes.current, key];
      setQuery({ path: key }, true);
    },
  };

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
        buyerId={offer.offer.counterparty_id}
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
      // The two closed folds (what they ask, why it matters) sit side by side from `lg`, so the page stays within its two screens.
      if (!settledDeal) {
        dealParts.folds = (
          <div key="folds" className="grid items-start gap-x-6 gap-y-4 lg:grid-cols-2">
            {dealParts.buyer_asks}
            {dealParts.why}
          </div>
        );
        dealParts.buyer_asks = null;
        dealParts.why = null;
      }
      dealParts.advanced = <AdvancedDetails key="advanced" ws={ws} v={v} offer={offer} items={items} asks={asks} />;
    }
    dealParts.agreements = commitments;
  }
  // One order at every width, so the DOM order is the visual order and the focus order follows it: the verdict (the heading), the one Action, the reply bar
  // (the priced decision, inside the first screen of a phone), the picture with its moments and the path columns, who and where, what they ask and cost, why it
  // matters (folded), the strategy block, the agreements, the folds. The server's `workspace.order` no longer decides it: the heading is the recommendation.
  const order = ["heading", "next", "priced_response", "paths", "buyer", "folds", "buyer_asks", "why", "before", "original", "agreements", "advanced"];
  const errorNode = error ? <ErrorState key="error" error={error} /> : null;

  if (queuePending)
    return (
      <>
        <PageHeader section="deals" title={t("nav.deals")} />
        <LoadingBlock rows={3} />
      </>
    );
  if (queueOn) {
    const rows = queueRows(dealsView.data?.deals ?? []);
    const tab: QueueTab = openTab(params.get("tab"), rows);
    const selectedId = offer && open ? offer.offer.offer_id : null;
    const exposure = exposureFor(exposureNow, selectedId);
    const pick = pathsState.picked?.key ?? null;
    const ctx = offer ? contextQuery({ customer: offer.offer.counterparty_id, decision: selectedId ? dealRecordId(selectedId) : null, path: pick }) : "";
    const customerHref = offer ? `/customers/${encodeURIComponent(offer.offer.counterparty_id)}?${ctx}` : "#";
    // Where the owner came from, when the page was opened from a customer or an invoice: the server's words and address.
    const backLink = (open?.context?.back ?? (dealsView.data?.deals ?? []).find((d) => d.open_offer?.context?.back)?.open_offer?.context?.back) ?? null;
    const onTab = (k: QueueTab) => {
      if (sending) return;
      const q = new URLSearchParams(window.location.search);
      q.set("tab", k);
      window.history.replaceState(null, "", `/deals?${q.toString()}${window.location.hash}`);
    };
    // A selection is a line: an open deal (it selects the offer, read here or fetched) or an agreed or setup line (read only). It is held while a send is in flight.
    const onSelect = (row: QueueRow) => {
      if (sending) return;
      if (row.offerId) {
        setRowSel(null);
        selectOffer(row.offerId);
      } else setRowSel(row.key);
    };
    // The detail belongs to a line of the open tab: a tab that does not hold the selected line shows none (it comes back with its tab).
    const rowSelRow = rowSel ? (rows.find((r) => r.key === rowSel) ?? null) : null;
    if (rowSel && (!rowSelRow || rowSelRow.tab !== tab)) setRowSel(null);
    const offerRow = selectedId ? (rows.find((r) => r.offerId === selectedId) ?? null) : null;
    const offerVisible = !offerRow || offerRow.tab === tab;
    // A deal that has an outcome has no open request, and an offer the server has no exposure for (a message not yet read through, an older server) has no queue detail: the
    // queue keeps its tabs and list, and the deal's own parts (the page as it was: where it stands, the answer, the paths, the agreements) take the detail's place.
    const settledNow = Boolean(v && ws && record && progress?.reached && progress.tone !== "open");
    const showQueueDetail = Boolean(offer && open && exposure && !settledNow);
    const outcome = offer && ready && !showQueueDetail ? order.map((k) => dealParts[k] ?? null) : null;
    const state = showQueueDetail && record ? { code: record.state, text: record.state_text, tone: (record.state_tone ?? "neutral") as Tone } : null;
    const heading = open?.headline_short ?? open?.read_text ?? open?.asks_text ?? "";
    const detailNode =
      cur.error || clock.error ? (
        <ErrorState
          error={(cur.error ?? clock.error)!}
          onRetry={() => {
            cur.reload();
            clock.reload();
          }}
        />
      ) : cur.loading || !clock.data || (offer && dealsView.loading && !dealsView.data) ? (
        <LoadingBlock rows={3} />
      ) : rowSelRow && rowSelRow.tab === tab ? (
        <QueueBody
          offerKey={rowSelRow.key}
          announce={t("dq.selected", { title: rowSelRow.deal.counterparty_name })}
          detail={<QueueReadOnly deal={rowSelRow.deal} tab={tab} today={today} customerHref={`/customers/${encodeURIComponent(rowSelRow.deal.counterparty_id)}?${contextQuery({ customer: rowSelRow.deal.counterparty_id, decision: selectedId ? dealRecordId(selectedId) : null, path: pick })}`} />}
          aside={null}
        />
      ) : !offerVisible ? null : showQueueDetail && offer && open && exposure ? (
        <QueueBody
          offerKey={offer.offer.offer_id}
          announce={t("dq.selected", { title: heading })}
          detail={
            <QueueDetail
              deal={dealRow!}
              open={open}
              offer={offer}
              verdict={v}
              negotiation={cur.negotiation}
              exposure={exposure}
              picture={picture}
              paths={queuePaths}
              today={today}
              mode={mode}
              customerHref={customerHref}
              items={items}
              asks={asks}
              busy={busy}
              error={error}
              onCheck={() => void evaluate()}
              onSending={setSending}
              after={STRATEGY_MVP ? <BeforeTheyAsk buyerId={offer.offer.counterparty_id} /> : null}
            />
          }
          aside={<QueueAside exposure={exposure} customerHref={exposure.customer_context?.profile_href ? `${exposure.customer_context.profile_href}?${ctx}` : customerHref} stressHref={stressHref(exposure.buyer_id, exposure.stress.delay_days, dealRow ? firstOpenInvoice(dealRow) : null, ctx)} pathLabel={pathsState.picked?.label ?? ""} />}
        />
      ) : outcome ? (
        <div className="space-y-6">{outcome}</div>
      ) : null;
    return (
      <>
        <PageHeader section="deals" title={t("nav.deals")} subtitle={(narrow || short) && offer ? undefined : rows.some((r) => r.tab === "needs") ? t("dq.sub.needs") : t("dq.sub.none")} />
        <div className="space-y-4">
          {backLink ? (
            <Link href={backLink.href} className="inline-flex min-h-8 items-center text-sm font-bold text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-back">
              ‹ {backLink.label}
            </Link>
          ) : null}
          {!offer || !(narrow || short) ? inbox : null}
          {errorNode}
          {exposureError}
          {dealsError ? <ErrorState error={dealsError} onRetry={dealsView.reload} /> : null}
          <QueueHead deals={dealsView.data?.deals ?? []} tab={tab} onTab={onTab} selectedOfferId={offerVisible ? selectedId : null} selectedKey={rowSelRow?.key ?? null} onSelect={onSelect} pick={pick} state={state} />
          {detailNode}
          {!offer ? commitments : null}
          {offer && (narrow || short) ? inbox : null}
        </div>
      </>
    );
  }

  return (
    <>
      {offer && ready ? null : <PageHeader section="deals" title={t("nav.deals")} subtitle={offer && narrow ? undefined : t("biz.deals.subtitle")} />}
      <div className="space-y-4">
        {inbox}

        {errorNode}
        {exposureError}

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
