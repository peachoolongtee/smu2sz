"use client";

import "@/app/flow-look.css";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { InboxList } from "@/components/deals/inbox-list";
import { Button, ErrorState, PageHeader } from "@/components/ui";
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
import { QueuePanel } from "./queue-table";
import { buildQueue, rowDecision, tabOf, taskRows, type TabKey } from "./queue-model";

const XL = "(min-width: 1280px)";

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
  const tab = tabOf(params.get("tab")) ?? "all";
  const view: DealView = { compare: params.get("compare") === "1", chart: params.get("chart") === "1", late: sel.scenario === "late" };
  const demo = useDemo();
  // What the page was opened with: the deals read then says where the owner came from (`context.back`) and whether the selection names anything; later picks in the page do not change it.
  const [opened] = useState<DealsContext>(() => ({ customer: sel.customer ?? null, invoice: sel.invoice ?? null, path: sel.path ?? null, decision: sel.decision ?? null, from: sel.from ?? null }));
  const deals = useAsync(() => getDeals(lang, opened), [lang, opened.customer, opened.invoice, opened.path, opened.decision, opened.from]);
  const dealsError = contractsOff(deals.error) ? undefined : deals.error;
  // A server that does not send the queue yet is read through today's worklist.
  const needWorklist = deals.data !== undefined && !deals.data.queue;
  const worklist = useAsync(() => (needWorklist ? getWorklist(lang) : Promise.resolve(null)), [lang, needWorklist]);
  const customers = useAsync(() => getCustomers(lang).catch(() => null), [lang]);
  const queue = deals.data === undefined ? undefined : deals.data.queue ? buildQueue(deals.data, null, WORDS(t)) : worklist.data === undefined ? undefined : buildQueue(deals.data, worklist.data, WORDS(t));
  const rows = queue ? taskRows(queue) : [];
  const row = decision ? (rows.find((x) => rowDecision(x.row) === decision)?.row ?? null) : null;
  const openOffer = decision ? (deals.data?.deals.find((d) => d.open_offer?.offer_id === offerOf(decision))?.open_offer ?? null) : null;
  const [sending, setSending] = useState(false);
  const paneRef = useRef<HTMLDivElement>(null);

  // ---- the address is the selection
  const go = (patch: Record<string, string | null>, how: "push" | "replace" = "push") => router[how](patchedHref(pathname, search, patch), { scroll: false });
  const select = (customer: string | null, dec: string, invoice: string | null) => {
    if (sending) return;
    go({ customer, decision: dec, invoice, path: null, compare: null, chart: null });
  };
  const close = () => go({ decision: null, customer: null, invoice: null, path: null, compare: null, chart: null });
  const onTab = (k: TabKey) => go({ tab: k === "all" ? null : k }, "replace");
  const onView = (patch: Partial<DealView>) =>
    go(
      {
        ...(patch.compare !== undefined ? { compare: patch.compare ? "1" : null } : {}),
        ...(patch.chart !== undefined ? { chart: patch.chart ? "1" : null } : {}),
        ...(patch.late !== undefined ? { scenario: patch.late ? "late" : null } : {}),
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
  const inboxOpen = inboxPref ?? Boolean(queue && rows.length === 0 && queue.customers.length === 0);
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
  const counts = queue?.counts;
  const subtitle = !counts ? undefined : counts.needs_you > 0 ? t("deals.state.needs", { n: counts.needs_you, w: counts.waiting }) : counts.waiting > 0 ? t("deals.state.waiting", { w: counts.waiting }) : t("deals.state.none");
  const back = deals.data?.context?.back ?? openOffer?.context?.back ?? null;
  const irrelevantText = opened.decision === decision ? (deals.data?.context?.irrelevant_text ?? null) : null;

  return (
    <div className="flow-f min-w-0" data-testid="deals-page">
      <PageHeader section="deals" title={t("nav.deals")} subtitle={subtitle} />
      {back ? (
        <Link href={back.href} className="mb-3 inline-flex min-h-8 items-center text-sm font-bold text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-back">
          ‹ {back.label}
        </Link>
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
      <div className="grid gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] xl:items-start">
        <div className="min-w-0 space-y-5">
          <QueuePanel queue={queue} customers={customers.data} loading={deals.loading || worklist.loading} error={dealsError} onRetry={deals.reload} tab={tab} onTab={onTab} selectedDecision={decision} locked={sending} onSelect={select} />
          <div className="flow-card p-4 sm:p-5" data-testid="deals-inbox">
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
                currentDocId={null}
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
        </div>
        <div ref={paneRef} className="min-w-0 scroll-mt-4" aria-live="polite" data-testid="deals-detail">
          {decision ? (
            <DecisionPane key={decision} decision={decision} customer={sel.customer ?? null} row={row} open={openOffer} view={view} pickedKey={sel.path ?? null} onView={onView} onPick={onPick} onClose={close} onBusy={setSending} irrelevantText={irrelevantText} />
          ) : queue === undefined ? null : (
            <section className="flow-card p-5 sm:p-7" data-testid="deals-select" aria-label={t("deals.select.title")}>
              <h2 className="type-section text-ink">{t("deals.select.title")}</h2>
              <p className="mt-1 max-w-[56ch] text-sm text-ink-2">{t("deals.select.body")}</p>
            </section>
          )}
        </div>
      </div>
      <div id="deals-investigate" className="mt-5 empty:hidden" />
    </div>
  );
}

/** The two label sentences the fallback agreement rows are written with (the words around the server's terms and contract reference). */
const WORDS = (t: ReturnType<typeof useI18n>["t"]) => ({ agreedTerms: (terms: string) => t("dq.agreed.request", { terms }), agreedRef: (ref: string) => t("dq.agreed.ref", { ref }) });
