"use client";

import "@/app/flow-look.css";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ActiveCommitments } from "@/components/deals/commitments";
import { isAgreed } from "@/components/deals/deal-summary";
import { InboxList } from "@/components/deals/inbox-list";
import { Button, ErrorState, PageHeader } from "@/components/ui";
import { WorklistAlertLine } from "@/components/ui/worklist-rows";
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
import { dealTabCounts, dealTabOf, LEGACY_VIEW_KEYS, negotiationRows, TABLE_FROM, viewOf, WIDE_VIEWS, type DealTab } from "./deal-model";
import { QueueRail } from "./queue-rail";
import { QueuePanel, type QueueLayout } from "./queue-table";
import { buildQueue, rowDecision, type RowTarget } from "./queue-model";

const XL = "(min-width: 1280px)";
/** The keys of round two that opened sections under the page: an address that carries one lands on `view=compare` and the key is dropped. */
const RETIRED: Record<string, null> = Object.fromEntries(LEGACY_VIEW_KEYS.map((k) => [k, null]));
const subscribeXl = (onChange: () => void) => {
  const list = window.matchMedia(XL);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
};
/** True from the two-pane width (`xl`); false below it and while rendering on the server. */
const HINT_KEY = "tl-deals-hint";
const useTwoPanes = () => useSyncExternalStore(subscribeXl, () => window.matchMedia(XL).matches, () => false);

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
  const { view: viewKey, legacy } = viewOf(params);
  const view: DealView = { view: viewKey, late: sel.scenario === "late", lines: params.get("lines"), review: params.get("review") === "1" };
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
  // The queue steps aside to its rail while Compare responses or Cash impact is open (the owner may bring it back for that view; Escape does too).
  const [shownFor, setShownFor] = useState<string | null>(null);
  const railKey = `${decision ?? ""}:${viewKey}`;
  const paneRef = useRef<HTMLDivElement>(null);
  const twoPanes = useTwoPanes();
  const railed = twoPanes && Boolean(decision) && WIDE_VIEWS.has(viewKey) && shownFor !== railKey && Boolean(queue);
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
      // With the queue folded to its rail the first Escape brings it back; the next closes the selection.
      if (railed) return setShownFor(railKey);
      close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- close reads the current address
  }, [decision, sending, search, railed, railKey]);
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
  const counts = queue ? dealTabCounts(queue) : undefined;
  const subtitle = !counts ? undefined : counts.needs_you > 0 ? t("deals.state.needs", { n: counts.needs_you, w: counts.waiting }) : counts.waiting > 0 ? t("deals.state.waiting", { w: counts.waiting }) : t("deals.state.none");
  const back = deals.data?.context?.back ?? openOffer?.context?.back ?? null;
  const irrelevantText = opened.decision === decision ? (deals.data?.context?.irrelevant_text ?? null) : null;

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
        <div key="pane" ref={paneRef} className="min-w-0 scroll-mt-4" data-testid="deals-detail">
          {decision ? (
            <DecisionPane key={decision} decision={decision} customer={sel.customer ?? null} row={row} open={openOffer} view={view} pickedKey={sel.path ?? null} onGo={go} inbox={inboxFor} onPick={onPick} onClose={close} onBusy={setSending} irrelevantText={irrelevantText} />
          ) : queue === undefined ? null : (
            <section className="flow-card p-5 sm:p-7" data-testid="deals-select" aria-label={t("deals.select.title")}>
              <h2 className="type-section text-ink">{t("deals.select.title")}</h2>
              <p className="mt-1 flex max-w-[56ch] items-center gap-2 text-sm text-ink-2" data-testid="deals-select-body">
                {/* The queue's chevron, turned toward the queue (left from xl, where it is beside the workspace; up where it is above). */}
                <span aria-hidden className={`grid size-6 shrink-0 place-items-center text-ink-3 ${twoPanes ? "rotate-180" : "-rotate-90"}`}>
                  <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m6 3.5 4.5 4.5L6 12.5" />
                  </svg>
                </span>
                {twoPanes ? t("deals.select.body") : t("deals.select.body.above")}
              </p>
            </section>
          )}
        </div>
  );

  return (
    <div className="flow-f min-w-0" data-testid="deals-page">
      <PageHeader section="deals" title={t("nav.deals")} subtitle={subtitle} />
      {back ? (
        <Link href={back.href} className="mb-3 inline-flex min-h-8 items-center text-sm font-bold text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-back">
          ‹ {back.label}
        </Link>
      ) : null}
      {/* The company funding alert is the page's own row, full width under the header (the component Home's worklist uses); it is never one of the queue's rows or counts. */}
      {queue?.alert ? (
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
      {/* Round two widths: the queue is 380 px (four tabs with their counts on one line), the workspace is fluid up to 850 px (the page's content holds at 1400 px, flow-look.css). Below `xl` a selected negotiation comes first (its decision is inside the first
          screen of a phone) and the queue follows; from `xl` the queue is the left pane and the workspace scrolls on its own where it is taller than the window. The DOM order is the reading and focus order.
          From 20 negotiations the owner may switch the queue to Home's table: it then takes the full width above, and the inbox and the workspace share the row beneath. */}
      {tableMode ? <div className="mb-6">{QUEUE_NODE}</div> : null}
      <div className={`grid gap-6 xl:items-start ${railed ? "xl:grid-cols-[72px_minmax(0,1400px)]" : "xl:grid-cols-[380px_minmax(0,850px)]"}`} data-testid="deals-grid" data-rail={railed ? "true" : "false"}>
        {!twoPanes && decision ? (
          <>
            {PANE}
            <div className="min-w-0 space-y-6">
              {tableMode ? null : QUEUE_NODE}
              {INBOX_SLOT}
            </div>
          </>
        ) : railed && queue ? (
          <>
            <div className="min-w-0 xl:sticky xl:top-20" data-testid="deals-side">
              <QueueRail queue={queue} selectedDecision={decision} locked={sending} onSelect={select} onShow={() => setShownFor(railKey)} />
            </div>
            {PANE}
          </>
        ) : (
          <>
            <div className="min-w-0 space-y-6 xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)] xl:overflow-y-auto" data-testid="deals-side">
              {tableMode ? null : QUEUE_NODE}
              {INBOX_SLOT}
            </div>
            {PANE}
          </>
        )}
      </div>
      {/* The agreements in force, each with its deal summary (the confirmed contract beside the books): under the panes, where the queue's Agreements tab leads the eye. */}
      <div className="mt-8" data-testid="deals-agreements">
        <ActiveCommitments
          today={clock.data?.day ?? books.data?.day ?? 0}
          buyerName={(id: string) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? deals.data?.deals.find((d) => d.counterparty_id === id)?.counterparty_name ?? id}
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
