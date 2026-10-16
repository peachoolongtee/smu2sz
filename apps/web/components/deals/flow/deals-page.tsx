"use client";

import "@/app/flow-look.css";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BuyingCard } from "@/components/deals/buying-card";
import { ActiveCommitments, type AgreementGroups } from "@/components/deals/commitments";
import { isAgreed } from "@/components/deals/deal-summary";
import { DealList, useDealRows } from "@/components/deals/deal-list";
import { InboxList } from "@/components/deals/inbox-list";
import { DealTools } from "@/components/deals/tools";
import { FoldCard } from "@/components/business/surface";
import { Button, ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { WorklistAlertLine } from "@/components/ui/worklist-rows";
import { contractsOff } from "@/components/documents";
import { getClock, getCustomers, getDeals, getLedger, getPurchases, getState, getWorklist, submitOffer } from "@/lib/api";
import { dealRecordId } from "@/lib/decision";
import { recordOffer, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";
import { useMode } from "@/lib/mode";
import { offerOf, patchedHref, readSelection } from "@/lib/selection";
import type { DealsContext } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useDecisions } from "@/lib/use-decision";
import { type DealView, DecisionPane } from "./decision-pane";
import { afterGroupCounts, afterGroupOf, dealTabCounts, dealTabOf, dealWalk, type DealWalk, LEGACY_VIEW_KEYS, negotiationRows, sortRows, TABLE_FROM, viewOf, type DealTab } from "./deal-model";
import { QueuePanel, type QueueLayout } from "./queue-table";
import { buildQueue, rowDecision, type RowTarget } from "./queue-model";

/** The address names nothing (the Deals tab itself): the page is the list of every deal. Anything it names (a customer, a deal, a tab) opens the queue and the deal in full. */
const DETAIL_PARAMS = ["customer", "buyer", "decision", "invoice", "path", "tab", "view", "review", "lines", "show", "scenario", "compare", "chart", "investigate"];

/** The keys of round two that opened sections under the page: an address that carries one has the key dropped (the choices table replaced Compare responses). */
const RETIRED: Record<string, null> = Object.fromEntries(LEGACY_VIEW_KEYS.map((k) => [k, null]));
const HINT_KEY = "tl-deals-hint";

/**
 * Deals (tickets #126 to #129): the stable title "Deals" with the state sentence under it and the queue (one row per task, by who owes the next step). A selected negotiation replaces the list with its
 * own full-width page ("All deals (N)" at its top, "Deal i of N" with previous and next in the list's order); going back restores the list where it was. The
 * address is the whole selection (`customer`, `decision`, `path`, `invoice`, `scenario`, `from`, plus the view's `tab`, `compare`, `chart`): a row sets it, back and forward restore
 * it, and a deep link in a fresh session hydrates from the server. Opening a deal pushes one history entry; changing its sections replaces it, so Back leaves the deal in one step. "No records" is only for a queue that is empty everywhere.
 * Buyer messages that are not read yet wait in the inbox under the queue; opening one reads it into a negotiation and selects it. Every word and figure is the server's.
 */
export function DealsPage() {
  const { t, lang } = useI18n();
  const mode = useMode();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const sel = readSelection(params);
  const search = params.toString();
  const decision = sel.decision ?? null;
  const tab = dealTabOf(params.get("tab")) ?? "all";
  // Home's table is the queue's layout from 20 negotiations; the compact rows are the default (a view choice, held by the page so the queue can take the full width).
  const [layout, setLayout] = useState<QueueLayout>("compact");
  const { view: viewKey, legacy } = viewOf(params);
  const view: DealView = { view: viewKey, review: params.get("review") === "1" };
  const demo = useDemo();
  // What the page was opened with: the deals read then says where the owner came from (`context.back`) and whether the selection names anything; later picks in the page do not change it.
  const [opened] = useState<DealsContext>(() => ({ customer: sel.customer ?? null, invoice: sel.invoice ?? null, path: sel.path ?? null, decision: sel.decision ?? null, from: sel.from ?? null }));
  const deals = useAsync(() => getDeals(lang, opened), [lang, opened.customer, opened.invoice, opened.path, opened.decision, opened.from]);
  const dealsError = contractsOff(deals.error) ? undefined : deals.error;
  // A server that does not send the queue yet is read through today's worklist.
  const needWorklist = deals.data !== undefined && !deals.data.queue;
  const worklist = useAsync(() => (needWorklist ? getWorklist(lang) : Promise.resolve(null)), [lang, needWorklist]);
  // The buying side (ADR-0013): its card shows on the list only when the server answers (the feature can be switched off).
  // It is read once when the list is on screen, not with the page's other reads: those are read again after every write (an accept, a send), and on a server that
  // answers one request at a time this card's read would stand in the queue before the open deal's own record. With a deal open (the list is hidden) nothing is read.
  const [purchases, setPurchases] = useState<NonNullable<Awaited<ReturnType<typeof getPurchases>>>["purchases"] | null>(null);
  const listOpen = decision === null;
  useEffect(() => {
    if (!listOpen) return;
    let live = true;
    getPurchases(lang).then(
      (v) => live && setPurchases(v.purchases),
      () => live && setPurchases(null),
    );
    return () => {
      live = false;
    };
  }, [lang, listOpen]);
  const customers = useAsync(() => getCustomers(lang).catch(() => null), [lang]);
  const queue = deals.data === undefined ? undefined : deals.data.queue ? buildQueue(deals.data, null, customers.data, WORDS(t)) : worklist.data === undefined ? undefined : buildQueue(deals.data, worklist.data, customers.data, WORDS(t));
  const rows = queue ? negotiationRows(queue) : [];
  const row = decision ? (rows.find((x) => rowDecision(x.row) === decision)?.row ?? null) : null;
  const openOffer = decision ? (deals.data?.deals.find((d) => d.open_offer?.offer_id === offerOf(decision))?.open_offer ?? null) : null;
  const [sending, setSending] = useState(false);
  // The list's scroll, kept while it is on screen and restored when the owner comes back to it (from the page's own link, Escape or the browser's Back).
  const listScroll = useRef(0);
  const lastDecision = useRef<string | null>(decision);
  useEffect(() => {
    if (decision) return;
    const on = () => {
      listScroll.current = window.scrollY;
    };
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, [decision]);
  useEffect(() => {
    const before = lastDecision.current;
    lastDecision.current = decision;
    if (decision === before) return;
    // A deal opens at its top; the list comes back where it was left.
    const top = decision ? 0 : listScroll.current;
    const id = window.requestAnimationFrame(() => window.scrollTo({ top, behavior: "auto" }));
    return () => window.cancelAnimationFrame(id);
  }, [decision]);
  // An old address (`investigate`, `compare`, `chart`, `show`) is written as the view it means.
  useEffect(() => {
    if (legacy) router.replace(patchedHref(pathname, search, { view: viewKey === "overview" ? null : viewKey, ...RETIRED }), { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per address
  }, [legacy, search]);
  // First visit with nothing selected: the top row's chevron pulses twice (remembered in this browser once it has been shown; none is drawn, and nothing remembered, under reduced motion).
  const [hint, setHint] = useState(false);
  // Under reduced motion there is no cue to give, so the one-time flag is not spent: the owner who later allows motion still gets it.
  const hintable = !decision && rows.length > 0;
  useEffect(() => {
    if (!hintable) return;
    // Asked of the browser here, not of a hook: a hook reads "no preference" during hydration, before the reader's setting is known.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    try {
      if (window.localStorage.getItem(HINT_KEY)) return;
      window.localStorage.setItem(HINT_KEY, "1");
    } catch {
      return;
    }
    const on = window.setTimeout(() => setHint(true), 0);
    const off = window.setTimeout(() => setHint(false), 1500);
    return () => {
      window.clearTimeout(on);
      window.clearTimeout(off);
    };
  }, [hintable]);

  // ---- the address is the selection
  const go = (patch: Record<string, string | null>, how: "push" | "replace" = "push") => router[how](patchedHref(pathname, search, patch), { scroll: false });
  const select = (customer: string | null, dec: string, invoice: string | null) => {
    if (sending) return;
    go({ customer, decision: dec, invoice, path: null, view: null, lines: null, review: null, ...RETIRED });
  };
  const close = () => go({ decision: null, customer: null, invoice: null, path: null, view: null, lines: null, review: null, ...RETIRED });
  // Previous and next walk the list's order and REPLACE the entry, so Back still leaves the deal in one step.
  const walkTo = (to: { customer: string | null; decision: string; invoice: string | null }) => {
    if (sending) return;
    go({ customer: to.customer, decision: to.decision, invoice: to.invoice, path: null, view: null, lines: null, review: null, ...RETIRED }, "replace");
  };
  const inTab = tab === "all" ? rows : rows.filter((x) => x.tier === tab);
  const walkTab = dealWalk(sortRows(inTab, "urgency"), decision);
  const walk = decision && walkTab.index === null ? dealWalk(sortRows(rows, "urgency"), decision) : walkTab;
  const onTab = (k: DealTab) => go({ tab: k === "all" ? null : k }, "replace");
  // A row's target as an address (the table's links): a negotiation selects in place with this row's own customer, decision and invoice.
  const hrefOf = (target: RowTarget) => (target.kind === "go" ? target.href : patchedHref(pathname, search, { customer: target.customer, decision: target.decision, invoice: target.invoice, path: null, view: null, lines: null, review: null, ...RETIRED }));
  const onPick = (key: string | null) => go({ path: key }, "replace");

  // Escape closes the selection (not while typing in a field or with a dialog open).
  useEffect(() => {
    if (!decision) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || sending || document.querySelector("dialog[open]")) return;
      const el = e.target instanceof HTMLInputElement ? e.target : null;
      if (el && el.value) return;
      close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- close reads the current address
  }, [decision, sending, search]);

  // ---- the inbox: buyer messages not read yet (the simulated channel); opening one reads it into a negotiation and selects it
  const books = useAsync(getState, []);
  const ledger = useAsync(() => getLedger(lang), [lang]);
  const clock = useAsync(getClock, []);
  const records = useDecisions({ family: "DEAL" });
  const known = books.data ? new Set(books.data.state.counterparties.map((c) => c.id)) : null;
  const [reading, setReading] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [inboxPref, setInboxPref] = useState<boolean | null>(null);
  // Open while nothing is selected and nothing needs the owner (the next thing to do is read a message); folded to one row once a negotiation is selected.
  const inboxOpen = inboxPref ?? Boolean(queue && !decision && queue.counts.needs_you === 0);
  // The messages Business mode shows: the senders the books know (the same rule as the list itself).
  const inboxCount = INBOX.filter((m) => mode !== "business" || (known ? known.has(m.counterparty_id) : false)).length;
  async function openMessage(m: InboxMessage) {
    const seen = Object.values(demo.offers).find((o) => o.documents[0]?.doc_id === m.document.doc_id);
    if (seen) return select(seen.offer.counterparty_id, dealRecordId(seen.offer.offer_id), null);
    setReading(m.id);
    setReadError(null);
    try {
      const read = await submitOffer(m.fixtureId ? { fixture_id: m.fixtureId } : { counterparty_id: m.counterparty_id, documents: [m.document] });
      recordOffer(read, m.fixtureId);
      select(read.offer.counterparty_id, dealRecordId(read.offer.offer_id), null);
    } catch (e) {
      setReadError(e instanceof Error ? e.message : String(e));
    } finally {
      setReading(null);
    }
  }
  const statusFor = (docId: string): string | null => {
    const o = Object.values(demo.offers).find((x) => x.documents[0]?.doc_id === docId);
    return o ? (records.data?.decisions.find((d) => d.id === dealRecordId(o.offer.offer_id))?.state_text ?? null) : null;
  };

  // ---- the state sentence under the stable title
  // A company opened from the list (`?customer=`, no deal selected): the page is that company's deals only.
  const focus = !decision ? (sel.customer ?? params.get("buyer") ?? null) : null;
  const focusRows = focus ? rows.filter((x) => x.row.customer_id === focus) : null;
  const counts = queue ? (focusRows ? focusCounts(focusRows) : dealTabCounts(queue)) : undefined;
  // The server's sentence counts every task that needs the owner (an approval and a payment to chase too); the tabs count the negotiations listed here. When the two differ the page
  // says how many of them are the deals below and where the others wait, so "7 tasks need you" never sits over "Needs you 5" unexplained.
  const outside = !focus && queue && counts && queue.counts.needs_you > counts.needs_you ? ` ${t("deals.state.outside", { n: counts.needs_you })}` : "";
  const subtitle = !counts ? undefined : focus ? (counts.needs_you > 0 ? t("deals.state.needs", { n: counts.needs_you, w: counts.waiting }) : counts.waiting > 0 ? t("deals.state.waiting", { w: counts.waiting }) : t("deals.state.none")) : queue?.headline_text ? queue.headline_text + outside : counts.needs_you > 0 ? t("deals.state.needs", { n: counts.needs_you, w: counts.waiting }) : counts.waiting > 0 ? t("deals.state.waiting", { w: counts.waiting }) : t("deals.state.none");
  const back = deals.data?.context?.back ?? openOffer?.context?.back ?? null;
  const irrelevantText = opened.decision === decision ? (deals.data?.context?.irrelevant_text ?? null) : null;

  // The money groups the queue files the agreements in, by the deal's record id: the server's group and label (nothing is decided here).
  const agreementGroups: AgreementGroups | undefined = queue
    ? {
        byRecord: Object.fromEntries(
          [...queue.needs_you, ...queue.waiting, ...queue.agreements].flatMap((r) => {
            const g = afterGroupOf(r);
            return g && r.decision_id ? [[r.decision_id, { group: g, label: r.after_group_label ?? null }] as const] : [];
          }),
        ),
        counts: afterGroupCounts(queue),
      }
    : undefined;
  const tableMode = Boolean(queue) && layout === "table" && rows.length >= TABLE_FROM;
  const QUEUE_NODE = (
    <QueuePanel
      key="queue"
      queue={queue}
      customers={customers.data}
      loading={deals.loading || worklist.loading}
      error={dealsError}
      onRetry={deals.reload}
      tab={tab}
      onTab={onTab}
      selectedDecision={decision}
      locked={sending}
      onSelect={select}
      hrefOf={hrefOf}
      layout={layout}
      onLayout={setLayout}
      hint={hint && !decision}
      onlyCustomer={!decision ? (sel.customer ?? params.get("buyer") ?? null) : null}
      onShowAll={() => go({ customer: null, buyer: null })}
    />
  );
  const INBOX_NODE =
    /* Not drawn until the queue is read: whether it is open depends on what the queue says (it would open and fold under the owner's hand). */
    queue === undefined ? null : (
      <div key="inbox" className="flow-card p-4 sm:p-5" data-testid="deals-inbox">
        {inboxOpen ? null : (
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1" data-testid="inbox-collapsed">
            <h2 className="font-display text-lg font-extrabold text-ink">{t("deals.inbox.title", { n: inboxCount })}</h2>
            <Button size="sm" onClick={() => setInboxPref(true)} aria-expanded={false} aria-controls="inbox-list" data-testid="inbox-back">
              {t("deals.inbox.show")}
            </Button>
          </div>
        )}
        {inboxOpen ? (
          <InboxList
            onlyCounterparty={sel.customer ?? params.get("buyer") ?? null}
            currentDocId={decision ? (demo.offers[offerOf(decision) ?? ""]?.documents[0]?.doc_id ?? null) : null}
            readDocIds={Object.values(demo.offers).map((o) => o.documents[0]?.doc_id)}
            known={known}
            busy={reading}
            today={clock.data?.day ?? books.data?.day ?? 0}
            mode={mode}
            statusFor={statusFor}
            onOpen={(m) => void openMessage(m)}
            loadError={books.error}
            onRetry={books.reload}
            onCollapse={() => setInboxPref(false)}
            refusals={ledger.data?.refusals ?? null}
          />
        ) : null}
      </div>
    );
  // With a deal selected its buyer's messages are in its Messages tab; the inbox card is the way to start a negotiation, so it stands under the queue only while nothing is selected.
  const INBOX_SLOT = decision ? null : INBOX_NODE;
  const inboxFor = (buyer: string | null) => (
    <InboxList
      currentDocId={decision ? (demo.offers[offerOf(decision) ?? ""]?.documents[0]?.doc_id ?? null) : null}
      readDocIds={Object.values(demo.offers).map((o) => o.documents[0]?.doc_id)}
      known={known}
      busy={reading}
      today={clock.data?.day ?? books.data?.day ?? 0}
      mode={mode}
      statusFor={statusFor}
      onOpen={(m) => void openMessage(m)}
      loadError={books.error}
      onRetry={books.reload}
      refusals={ledger.data?.refusals ?? null}
      onlyCounterparty={buyer}
    />
  );
  const PANE = (
        <div key="pane" className="min-w-0" data-testid="deals-detail">
          {decision ? <DecisionPane key={decision} decision={decision} customer={sel.customer ?? null} row={row} open={openOffer} view={view} pickedKey={sel.path ?? null} onGo={go} inbox={inboxFor} onPick={onPick} onClose={close} onBusy={setSending} irrelevantText={irrelevantText} /> : null}
        </div>
  );

  const listMode = !DETAIL_PARAMS.some((k) => params.get(k));
  const today = clock.data?.day ?? books.data?.day ?? 0;
  const buyerName = (id: string) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? deals.data?.deals.find((d) => d.counterparty_id === id)?.counterparty_name ?? id;
  const readDocIds = Object.values(demo.offers)
    .map((o) => o.documents[0]?.doc_id)
    .filter((d): d is string => Boolean(d));
  // The list's rows are read from what the page already has: the deals read, the deals' records, the offers read and the inbox.
  const listRows = useDealRows({
    deals: deals.data?.deals ?? [],
    records: records.data?.decisions ?? [],
    offers: Object.values(demo.offers),
    negotiations: demo.negotiations,
    verdicts: demo.verdicts,
    readDocIds,
    known,
    nameOf: buyerName,
    today,
  });

  if (listMode)
    return (
      <div className="flow-f min-w-0" data-testid="deals-page" data-view="list">
        <PageHeader section="deals" title={t("nav.deals")} subtitle={t("deals.list.pageSub")} />
        <div className="space-y-6">
          <DealTools />
          {dealsError ? <ErrorState error={dealsError} onRetry={deals.reload} /> : null}
          {books.error ? <ErrorState error={books.error} onRetry={books.reload} /> : null}
          {readError ? <ErrorState error={readError} /> : null}
          {(deals.loading && !deals.data) || (!books.data && !books.error) ? <LoadingBlock rows={3} /> : <DealList rows={listRows} />}
          {purchases ? <BuyingCard purchases={purchases} /> : null}
          {/* Every message, as it arrived: a dropdown under the list. Opening one reads it and opens its deal in full. */}
          <FoldCard title={t("deals.list.messages")} hint={t("deals.list.messages.hint", { n: inboxCount })} testId="deal-list-messages">
            <InboxList
              currentDocId={null}
              readDocIds={readDocIds}
              known={known}
              busy={reading}
              today={today}
              mode={mode}
              statusFor={statusFor}
              onOpen={(m) => void openMessage(m)}
              loadError={books.error}
              onRetry={books.reload}
              refusals={ledger.data?.refusals ?? null}
            />
          </FoldCard>
        </div>
      </div>
    );

  return (
    <div className="flow-f min-w-0" data-testid="deals-page">
      {decision ? null : <PageHeader section="deals" title={focus ? buyerName(focus) : t("nav.deals")} subtitle={subtitle} />}
      {back ? (
        <Link href={back.href} className="mb-3 inline-flex min-h-8 items-center text-sm font-bold text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-back">
          ‹ {back.label}
        </Link>
      ) : null}
      {/* The company funding alert is the list's own row, full width under the header (the component Home's worklist uses); it is never one of the queue's rows or counts, and a deal's page does not carry it. */}
      {queue?.alert && !decision ? (
        <div className="mb-4" data-testid="deals-alert-row">
          <WorklistAlertLine
            testId="queue-alert"
            tone={queue.alert.tone === "bad" ? "bad" : "warn"}
            eyebrow={queue.alert.kind_text ?? queue.alert.eyebrow}
            text={queue.alert.pending_text ?? queue.alert.text}
            action={
              <Link href={queue.alert.primary.href} className="inline-flex min-h-8 items-center gap-1 text-sm font-bold text-brand-700 underline-offset-[3px] hover:underline touch:min-h-11" data-testid="queue-alert-go">
                {queue.alert.primary.label} <span aria-hidden>→</span>
              </Link>
            }
          />
        </div>
      ) : null}
      {dealsError ? (
        <div className="mb-4">
          <ErrorState error={dealsError} onRetry={deals.reload} />
        </div>
      ) : null}
      {readError ? (
        <div className="mb-4">
          <ErrorState error={readError} />
        </div>
      ) : null}
      {/* A selected deal is its own page, the full width of the content (up to 1180 px). The list stays mounted, hidden, so its search, sort and grouping are still there on the way back. */}
      {decision ? (
        <div className="mx-auto w-full max-w-[1180px] space-y-5" data-testid="deal-page">
          <DealTopBar total={walk.total || counts?.all || 0} walk={walk} locked={sending} onAll={close} onWalk={walkTo} />
          {PANE}
        </div>
      ) : null}
      <div hidden={Boolean(decision)} data-testid="deals-list-view">
        {tableMode ? <div className="mb-6">{QUEUE_NODE}</div> : null}
        <div className="grid gap-6" data-testid="deals-grid">
          <div className="min-w-0 space-y-6" data-testid="deals-side">
            {tableMode ? null : QUEUE_NODE}
            {/* The buying side (ADR-0013) sits between the selling list and the buyers' messages: selling stays first. */}
            {purchases && !focus ? <BuyingCard purchases={purchases} /> : null}
            {INBOX_SLOT}
          </div>
        </div>
        {/* The agreements in force, each with its deal summary (the confirmed contract beside the books): under the list, where the queue's Agreements tab leads the eye. */}
        <div className="mt-8" data-testid="deals-agreements">
          <ActiveCommitments
            today={clock.data?.day ?? books.data?.day ?? 0}
            buyerName={(id: string) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? deals.data?.deals.find((d) => d.counterparty_id === id)?.counterparty_name ?? id}
            hideEmpty
            agreed={(deals.data?.deals ?? []).filter((d) => isAgreed(d) && (!focus || d.counterparty_id === focus))}
            dealsDay={deals.data?.day ?? null}
            dealsError={dealsError}
            onRetryDeals={deals.reload}
            groups={agreementGroups}
            groupsPending={queue === undefined}
            reads={{ ledger, records }}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * The top line of a deal's page: "All deals (N)" (clears the selection; the list is where it was), and, when the deal is one of several in the list, "Deal i of N" with previous and next in the
 * list's order. The words are the dictionary's; the numbers are positions in the list the page holds.
 */
function DealTopBar({ total, walk, locked, onAll, onWalk }: { total: number; walk: DealWalk; locked: boolean; onAll: () => void; onWalk: (to: NonNullable<DealWalk["prev"]>) => void }) {
  const { t } = useI18n();
  const round = "motion-press inline-grid size-11 place-items-center rounded-pill border border-line-ui bg-card text-ink hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-40";
  const chevron = (d: string) => (
    <svg aria-hidden viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
  return (
    <div className="flex items-center justify-between gap-3" data-testid="deal-topbar">
      <button type="button" onClick={onAll} disabled={locked} className="motion-press inline-flex min-h-11 items-center gap-2 rounded-pill pr-3 text-[15px] font-medium text-ink hover:text-ink-2 disabled:opacity-50" data-testid="deal-back-all">
        {chevron("M15 18l-6-6 6-6")}
        <span className="max-sm:hidden">{t("deals.top.all", { n: total })}</span>
        <span className="sm:hidden">{t("deals.top.allBare")}</span>
      </button>
      {walk.index !== null && walk.total > 1 ? (
        <div className="flex items-center gap-2 text-sm text-ink-2" data-testid="deal-walk">
          <span data-testid="deal-position">{t("deals.top.pos", { i: walk.index, n: walk.total })}</span>
          <button type="button" aria-label={t("deals.top.prev")} disabled={locked || !walk.prev} onClick={() => walk.prev && onWalk(walk.prev)} className={round} data-testid="deal-prev">
            {chevron("M15 18l-6-6 6-6")}
          </button>
          <button type="button" aria-label={t("deals.top.next")} disabled={locked || !walk.next} onClick={() => walk.next && onWalk(walk.next)} className={round} data-testid="deal-next">
            {chevron("M9 18l6-6-6-6")}
          </button>
        </div>
      ) : null}
    </div>
  );
}

/** The tab counts of one company's rows (the server's counts are the whole queue's). */
function focusCounts(rows: ReturnType<typeof negotiationRows>): Record<DealTab, number> {
  const n = (tier: DealTab) => rows.filter((x) => x.tier === tier).length;
  return { all: rows.length, needs_you: n("needs_you"), waiting: n("waiting"), agreements: n("agreements") };
}

/** The two label sentences the fallback agreement rows are written with (the words around the server's terms and contract reference). */
const WORDS = (t: ReturnType<typeof useI18n>["t"]) => ({ agreedTerms: (terms: string) => t("dq.agreed.request", { terms }), agreedRef: (ref: string) => t("dq.agreed.ref", { ref }) });
