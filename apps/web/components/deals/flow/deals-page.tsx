"use client";

import "@/app/flow-look.css";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ActiveCommitments } from "@/components/deals/commitments";
import { isAgreed } from "@/components/deals/deal-summary";
import { InboxList } from "@/components/deals/inbox-list";
import { DealList, useDealRows } from "@/components/deals/deal-list";
import { DealTools } from "@/components/deals/tools";
import { FoldCard } from "@/components/business/surface";
import { ArrowLeftIcon } from "@/components/icons";
import { Button, ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { contractsOff } from "@/components/documents";
import { getClock, getCustomers, getDeals, getLedger, getState, getWorklist, submitOffer } from "@/lib/api";
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
import { dealTabCounts, dealTabOf, negotiationRows, TABLE_FROM, type DealTab } from "./deal-model";
import { QueuePanel, type QueueLayout } from "./queue-table";
import { TaskProgress } from "./next-step-guide";
import { buildQueue, rowDecision, type RowTarget } from "./queue-model";

const XL = "(min-width: 1280px)";
const subscribeXl = (onChange: () => void) => {
  const list = window.matchMedia(XL);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
};
/** True from the two-pane width (`xl`); false below it and while rendering on the server. */
const useTwoPanes = () => useSyncExternalStore(subscribeXl, () => window.matchMedia(XL).matches, () => false);

/** The address names nothing (the Deals tab itself): the page is the list of every deal. Anything it names (a customer, a deal, a tab) opens the queue and the deal in full. */
const DETAIL_PARAMS = ["customer", "buyer", "decision", "invoice", "path", "tab", "show", "scenario", "compare", "chart", "investigate"];

/**
 * Deals (tickets #126 to #129): the stable title "Deals" with the state sentence under it, the queue (one row per task, by who owes the next step) beside the selected negotiation. The
 * address is the whole selection (`customer`, `decision`, `path`, `invoice`, `scenario`, `from`, plus the view's `tab`, `compare`, `chart`): a row sets it, back and forward restore
 * it, and a deep link in a fresh session hydrates from the server. With nothing selected the page says "Select a request"; "No records" is only for a queue that is empty everywhere.
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
  const showRaw = params.get("show");
  const view: DealView = {
    compare: params.get("compare") === "1",
    chart: params.get("chart") === "1",
    late: sel.scenario === "late",
    investigate: params.get("investigate") === "1",
    show: showRaw === "cost" || showRaw === "cash" || showRaw === "none" ? showRaw : null,
  };
  const demo = useDemo();
  // What the page was opened with: the deals read then says where the owner came from (`context.back`) and whether the selection names anything; later picks in the page do not change it.
  const [opened] = useState<DealsContext>(() => ({ customer: sel.customer ?? null, invoice: sel.invoice ?? null, path: sel.path ?? null, decision: sel.decision ?? null, from: sel.from ?? null }));
  const deals = useAsync(() => getDeals(lang, opened), [lang, opened.customer, opened.invoice, opened.path, opened.decision, opened.from]);
  const dealsError = contractsOff(deals.error) ? undefined : deals.error;
  // A server that does not send the queue yet is read through today's worklist.
  const needWorklist = deals.data !== undefined && !deals.data.queue;
  const worklist = useAsync(() => (needWorklist ? getWorklist(lang) : Promise.resolve(null)), [lang, needWorklist]);
  const customers = useAsync(() => getCustomers(lang).catch(() => null), [lang]);
  const queue = deals.data === undefined ? undefined : deals.data.queue ? buildQueue(deals.data, null, customers.data, WORDS(t)) : worklist.data === undefined ? undefined : buildQueue(deals.data, worklist.data, customers.data, WORDS(t));
  const rows = queue ? negotiationRows(queue) : [];
  const row = decision ? (rows.find((x) => rowDecision(x.row) === decision)?.row ?? null) : null;
  const openOffer = decision ? (deals.data?.deals.find((d) => d.open_offer?.offer_id === offerOf(decision))?.open_offer ?? null) : null;
  const [sending, setSending] = useState(false);
  const paneRef = useRef<HTMLDivElement>(null);
  const twoPanes = useTwoPanes();

  // ---- the address is the selection
  const go = (patch: Record<string, string | null>, how: "push" | "replace" = "push") => router[how](patchedHref(pathname, search, patch), { scroll: false });
  const select = (customer: string | null, dec: string, invoice: string | null) => {
    if (sending) return;
    go({ customer, decision: dec, invoice, path: null, compare: null, chart: null, investigate: null, show: null });
  };
  const close = () => go({ decision: null, customer: null, invoice: null, path: null, compare: null, chart: null, investigate: null, show: null });
  const onTab = (k: DealTab) => go({ tab: k === "all" ? null : k }, "replace");
  // A row's target as an address (the table's links): a negotiation selects in place with this row's own customer, decision and invoice.
  const hrefOf = (target: RowTarget) => (target.kind === "go" ? target.href : patchedHref(pathname, search, { customer: target.customer, decision: target.decision, invoice: target.invoice, path: null, compare: null, chart: null, investigate: null, show: null }));
  const onView = (patch: Partial<DealView>) =>
    go(
      {
        ...(patch.compare !== undefined ? { compare: patch.compare ? "1" : null } : {}),
        ...(patch.chart !== undefined ? { chart: patch.chart ? "1" : null } : {}),
        ...(patch.late !== undefined ? { scenario: patch.late ? "late" : null } : {}),
        ...(patch.investigate !== undefined ? { investigate: patch.investigate ? "1" : null, compare: null, chart: null } : {}),
        ...(patch.show !== undefined ? { show: patch.show } : {}),
      },
      "replace",
    );
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
  // Below the two-pane width the negotiation opens under the list: bring it into view.
  useEffect(() => {
    if (!decision || typeof window === "undefined" || window.matchMedia(XL).matches) return;
    paneRef.current?.scrollIntoView({ block: "start", behavior: "auto" });
  }, [decision]);

  // ---- the inbox: buyer messages not read yet (the simulated channel); opening one reads it into a negotiation and selects it
  const books = useAsync(getState, []);
  const ledger = useAsync(() => getLedger(lang), [lang]);
  const clock = useAsync(getClock, []);
  const records = useDecisions({ family: "DEAL" });
  const known = books.data ? new Set(books.data.state.counterparties.map((c) => c.id)) : null;
  const [reading, setReading] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [inboxPref, setInboxPref] = useState<boolean | null>(null);
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
  const counts = queue ? dealTabCounts(queue) : undefined;
  const subtitle = !counts ? undefined : counts.needs_you > 0 ? t("deals.state.needs", { n: counts.needs_you, w: counts.waiting }) : counts.waiting > 0 ? t("deals.state.waiting", { w: counts.waiting }) : t("deals.state.none");
  const back = deals.data?.context?.back ?? openOffer?.context?.back ?? null;
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
  const irrelevantText = opened.decision === decision ? (deals.data?.context?.irrelevant_text ?? null) : null;

  // The one next click while nothing is selected: the first request in view that needs the owner, else the first message not read yet, else nothing here.
  const scope = sel.customer ?? params.get("buyer") ?? null;
  const inView = rows.filter((x) => !scope || x.row.customer_id === scope);
  // Only a request that needs the owner is a next click: an agreed or waiting deal is never outlined.
  const firstRequest = inView.find((x) => x.tier === "needs_you") ?? null;
  const firstUnread =
    // Only a buyer's newest message (the head of its thread, first in INBOX) is a next click; the earlier ones in the thread are history.
    INBOX.find(
      (m) =>
        INBOX.find((x) => x.counterparty_id === m.counterparty_id) === m &&
        (!scope || m.counterparty_id === scope) &&
        (mode !== "business" || (known ? known.has(m.counterparty_id) : false)) &&
        !readDocIds.includes(m.document.doc_id),
    ) ?? null;

  // The next click is a message when nothing is selected and no request is open in view (outlined in the inbox). With nothing selected the inbox IS the right-hand side, open;
  // once a negotiation is selected the negotiation takes that side and the inbox folds to one row under the queue.
  const nextIsMessage = !decision && !firstRequest && firstUnread !== null;
  const inboxOpen = !decision || (inboxPref ?? false);
  // Where the owner is on a request (open it, check it, send or approve): the selected negotiation's own step, reported by its pane; with nothing selected, the first step
  // when there is something to open, else none.
  const [paneStep, setPaneStep] = useState<number | null>(null);
  const progress = decision ? paneStep : firstRequest || firstUnread ? 0 : null;
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
      onlyCustomer={!decision ? (sel.customer ?? params.get("buyer") ?? null) : null}
      nextKey={!decision ? (firstRequest?.row.key ?? null) : null}
    />
  );
  const INBOX_NODE =
    /* Not drawn until the queue is read: whether it is open depends on what the queue says (it would open and fold under the owner's hand). */
    queue === undefined ? null : (
      <div key="inbox" className={`flow-card ${decision ? "p-4 sm:p-5" : "p-5 sm:p-7"}`} data-testid="deals-inbox">
        {inboxOpen ? null : (
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1" data-testid="inbox-collapsed">
            <h2 className="font-display text-base font-extrabold text-ink">{t("deals.inbox.title", { n: inboxCount })}</h2>
            <Button size="sm" onClick={() => setInboxPref(true)} aria-expanded={false} aria-controls="inbox-list" data-testid="inbox-back">
              {t("deals.inbox.show")}
            </Button>
          </div>
        )}
        {inboxOpen ? (
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
            onCollapse={decision ? () => setInboxPref(false) : undefined}
            nextDocId={nextIsMessage ? (firstUnread?.document.doc_id ?? null) : null}
            refusals={ledger.data?.refusals ?? null}
          />
        ) : null}
      </div>
    );
  const PANE = (
        <div key="pane" ref={paneRef} className="min-w-0 scroll-mt-4 xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)] xl:overflow-y-auto xl:rounded-[var(--radius-f-card)]" data-testid="deals-detail">
          {decision ? (
            <DecisionPane key={decision} decision={decision} customer={sel.customer ?? null} row={row} open={openOffer} view={view} pickedKey={sel.path ?? null} onView={onView} onPick={onPick} onClose={close} onBusy={setSending} irrelevantText={irrelevantText} onStep={setPaneStep} />
          ) : (
            INBOX_NODE
          )}
        </div>
  );

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
      <PageHeader section="deals" title={t("nav.deals")} subtitle={subtitle} />
      {back ? (
        <Link href={back.href} className="mb-3 inline-flex min-h-8 items-center text-sm font-bold text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-back">
          ‹ {back.label}
        </Link>
      ) : (
        // The way back to the list of every deal.
        <Link href="/deals" className="mb-3 inline-flex min-h-8 items-center gap-1 text-sm font-bold text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="deal-list-back">
          <ArrowLeftIcon width={14} height={14} />
          {t("deals.list.back")}
        </Link>
      )}
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
      {/* Round two widths: the queue is 380 px (four tabs with their counts on one line), the workspace is fluid up to 850 px (the page's content holds at 1400 px, flow-look.css). Below `xl` a selected negotiation comes first (its decision is inside the first
          screen of a phone) and the queue follows; from `xl` the queue is the left pane and the workspace scrolls on its own where it is taller than the window. The DOM order is the reading and focus order.
          From 20 negotiations the owner may switch the queue to Home's table: it then takes the full width above, and the inbox and the workspace share the row beneath. */}
      {tableMode ? <div className="mb-6">{QUEUE_NODE}</div> : null}
      {/* Where the owner is on a request, as a task's progress across the top: open it, check it against the limits, send or approve FLOW's reply. */}
      <TaskProgress current={progress} className="mb-6" />
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)] xl:items-start">
        {/* The right-hand side is the selected negotiation, or (nothing selected) the inbox; below the two-pane width it comes first. The inbox sits under the queue only
            while a negotiation holds the right-hand side. */}
        {!twoPanes && (decision || queue !== undefined) ? (
          <>
            {PANE}
            <div className="min-w-0 space-y-6">
              {tableMode ? null : QUEUE_NODE}
              {decision ? INBOX_NODE : null}
            </div>
          </>
        ) : (
          <>
            <div className="min-w-0 space-y-6">
              {tableMode ? null : QUEUE_NODE}
              {decision ? INBOX_NODE : null}
            </div>
            {PANE}
          </>
        )}
      </div>
      <div id="deals-investigate" className="mt-6 max-w-[1214px] empty:hidden" />
      {/* The agreements in force, each with its deal summary (the confirmed contract beside the books): under the panes, where the queue's Agreements tab leads the eye. */}
      <div className="mt-8" data-testid="deals-agreements">
        <ActiveCommitments
          today={today}
          buyerName={buyerName}
          hideEmpty
          agreed={(deals.data?.deals ?? []).filter(isAgreed)}
          dealsDay={deals.data?.day ?? null}
          dealsError={dealsError}
          onRetryDeals={deals.reload}
        />
      </div>
    </div>
  );
}

/** The two label sentences the fallback agreement rows are written with (the words around the server's terms and contract reference). */
const WORDS = (t: ReturnType<typeof useI18n>["t"]) => ({ agreedTerms: (terms: string) => t("dq.agreed.request", { terms }), agreedRef: (ref: string) => t("dq.agreed.ref", { ref }) });
