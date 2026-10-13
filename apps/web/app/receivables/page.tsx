"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { PartialRead } from "@/components/business/freshness";
import { PromisedAndReceived } from "@/components/receivables/history";
import { InvoiceDetail } from "@/components/receivables/invoice-detail";
import { InvoiceList } from "@/components/receivables/invoice-list";
import { SelectedStrip } from "@/components/receivables/selected-strip";
import { inFilter, type RecvFilter } from "@/components/receivables/state";
import { STRESS_DAYS, StressAside } from "@/components/receivables/stress-aside";
import { Summary } from "@/components/receivables/summary";
import { CustomerList } from "@/components/receivables/customer-list";
import { ArrowLeftIcon } from "@/components/icons";
import Link from "next/link";
import { ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { getBuyerExposure, getDecisionExposure, getReceivables, getReconciliation, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { withContext } from "@/lib/receivables-context";
import type { BuyerExposureView, ReceivableRow, ReceivablesRead } from "@/lib/types";
import { useNarrow } from "@/lib/use-narrow";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { useAsync } from "@/lib/use-async";
import { LegacyReceivables } from "./legacy";

/**
 * Receivables in three layers (map #110): what customers owe you, what each invoice nets once its financing is repaid, and what to do about it.
 * It reads `GET /receivables?lang=`; a server that has no such route (the adapter answers null for FastAPI's own "Not Found" only) keeps the page of before
 * (`legacy.tsx`), and each section renders only when its field is present. Any other failure is an error the page shows with a Retry; it never falls back
 * silently. The chosen invoice is in the address (`?invoice=`) beside the shared context (`customer`, `decision`, `path`), and nowhere else.
 */
export default function ReceivablesPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <Receivables />
    </Suspense>
  );
}

function Receivables() {
  const { t, lang } = useI18n();
  const read = useAsync(() => getReceivables(lang), [lang]);
  const head = <PageHeader title={t("nav.receivables")} subtitle={t("biz.recv.subtitle")} />;
  if (read.error) {
    return (
      <>
        {head}
        <ErrorState error={read.error} onRetry={read.reload} />
      </>
    );
  }
  if (read.data === undefined) {
    return (
      <>
        {head}
        <LoadingBlock rows={3} />
      </>
    );
  }
  // The server has no GET /receivables yet: the page of before.
  if (read.data === null) return <LegacyReceivables />;
  // An answer with no rows array is a broken answer, not an absent route.
  if (!Array.isArray(read.data.rows)) {
    return (
      <>
        {head}
        <ErrorState error={t("recv3.read.invalid")} onRetry={read.reload} />
      </>
    );
  }
  return <Layers read={read.data} reload={read.reload} />;
}

function Layers({ read, reload }: { read: ReceivablesRead; reload: () => void }) {
  const { t, lang } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const narrow = useNarrow();
  const reduced = useReducedMotion();
  const allRows = read.rows ?? [];
  // The address names a customer (a card on the list, or a link with `customer`) or an invoice: the page is that customer in full. Otherwise it is the list.
  const focusBuyer = params.get("buyer") ?? allRows.find((r) => r.receivable_id === params.get("invoice"))?.buyer_id ?? params.get("customer") ?? null;
  const listMode = !focusBuyer && !params.get("decision");
  const rows = focusBuyer ? allRows.filter((r) => r.buyer_id === focusBuyer) : allRows;
  const [filter, setFilter] = useState<RecvFilter>("all");
  const detailRef = useRef<HTMLElement>(null);
  const [scrollTo, setScrollTo] = useState(0);
  const invoiceParam = params.get("invoice");
  const shown = rows.filter((r) => inFilter(r, filter));
  // The chosen invoice is the address's; when the filter hides it the first visible one takes its place (none: the detail is hidden).
  const chosen = rows.find((r) => r.receivable_id === invoiceParam) ?? null;
  const selected: ReceivableRow | null = chosen && shown.includes(chosen) ? chosen : (shown[0] ?? null);

  const choose = (id: string | null) => {
    const q = new URLSearchParams(params.toString());
    if (id) q.set("invoice", id);
    else q.delete("invoice");
    const qs = q.toString();
    router.replace(qs ? `/receivables?${qs}` : "/receivables", { scroll: false });
  };
  const select = (id: string) => {
    choose(id);
    // On a phone the detail is far below the card that was tapped: bring it into view.
    if (narrow) setScrollTo((n) => n + 1);
  };
  const applyFilter = (next: RecvFilter) => {
    setFilter(next);
    const visible = rows.filter((r) => inFilter(r, next));
    if (!chosen || !visible.includes(chosen)) choose(visible[0]?.receivable_id ?? null);
  };
  useEffect(() => {
    if (scrollTo > 0) detailRef.current?.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
    // Only a new selection scrolls.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scrollTo]);

  // A link such as /receivables#RI:BUYER-1:2 (the home's remaining task) chooses that invoice and brings its row into view.
  useEffect(() => {
    if (typeof window === "undefined" || !window.location.hash || params.get("invoice")) return;
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (!allRows.some((r) => r.receivable_id === id)) return;
    const q = new URLSearchParams(params.toString());
    q.set("invoice", id);
    router.replace(`/receivables?${q.toString()}${window.location.hash}`, { scroll: false });
    document.getElementById(id)?.scrollIntoView({ block: "center" });
    // Once per load: the hash is the arrival, the address is the state afterwards.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The late-payment test, the concentration and the payment history are the buyer's, read with no deal needed. When the address carries a deal
  // (`?decision=`) its own read is used instead, provided it is about this buyer.
  const buyerId = selected?.buyer_id ?? null;
  const decisionId = params.get("decision");
  const buyerRead = useAsync(() => (buyerId ? getBuyerExposure(buyerId, lang) : Promise.resolve(null)), [buyerId, lang]);
  const dealRead = useAsync(() => (decisionId ? getDecisionExposure(decisionId, lang) : Promise.resolve(null)), [decisionId, lang]);
  const forBuyer = (view: BuyerExposureView | null | undefined) => (view && view.buyer_id === buyerId ? view : null);
  const deal = decisionId ? forBuyer(dealRead.data) : null;
  const exposure = deal ? dealRead : buyerRead;
  const view = deal ?? forBuyer(buyerRead.data);

  // What was promised early and what arrived, under the layers: the reconciliation read, as the page has always shown it. A failed read says so with a Retry.
  const recon = useAsync(getReconciliation, [lang]);
  const books = useAsync(getState, []);
  const nameOf = (id: string | null) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? rows.find((r) => r.buyer_id === id)?.buyer_name ?? id ?? "";

  const customerHref = (r: ReceivableRow) =>
    withContext(`/customers/${encodeURIComponent(r.buyer_id ?? "")}`, params, { customer: r.buyer_id ?? null, invoice: r.receivable_id });
  const dealHref = (r: ReceivableRow) =>
    r.pending_counter?.decision_id ? withContext("/deals", params, { decision: r.pending_counter.decision_id, customer: r.buyer_id ?? null, invoice: r.receivable_id }, r.buyer_id ? { buyer: r.buyer_id } : {}) : null;

  const history = recon.error ? (
    <div data-testid="recv3-history-failed">
      <ErrorState error={recon.error} onRetry={recon.reload} />
    </div>
  ) : recon.data ? (
    <div className="space-y-7" data-testid="recv3-history-sections">
      <PromisedAndReceived data={recon.data} name={nameOf} />
    </div>
  ) : null;

  // The list: what customers owe in total, then every customer as a card; a card opens that customer's invoices in full.
  if (listMode) {
    return (
      <div className="space-y-6" data-testid="recv3-page" data-view="list">
        <div>
          <Summary read={read} rows={allRows} />
        </div>
        <PartialRead partial={read.partial} onRetry={reload} />
        <CustomerList rows={allRows} customers={(books.data?.state.counterparties ?? []).filter((c) => c.role === "BUYER").map((c) => ({ id: c.id, name: c.name }))} />
        {history}
      </div>
    );
  }

  const buyerName = nameOf(focusBuyer);
  return (
    <div className="space-y-6" data-testid="recv3-page" data-view="customer">
      <Link href="/receivables" className="inline-flex min-h-8 items-center gap-1 text-sm font-bold text-brand-700 hover:underline touch:min-h-11" data-testid="recv-list-back">
        <ArrowLeftIcon width={14} height={14} />
        {t("recv.list.back")}
      </Link>
      <PageHeader
        title={buyerName}
        subtitle={t("recv.detail.sub")}
        actions={
          focusBuyer ? (
            <Link href={`/customers/${encodeURIComponent(focusBuyer)}?from=receivables`} className="inline-flex min-h-8 items-center text-sm font-bold text-brand-700 hover:underline">
              {t("recv.detail.profile")}
            </Link>
          ) : undefined
        }
      />
      <PartialRead partial={read.partial} onRetry={reload} />
      {rows.length === 0 ? <p className="card-flat text-sm text-ink-3">{t("recv.list.none")}</p> : null}
      {narrow && selected ? <SelectedStrip row={selected} customerHref={customerHref(selected)} /> : null}
      <InvoiceList rows={rows} selectedId={selected?.receivable_id ?? null} onSelect={select} filter={filter} onFilter={applyFilter} />

      {selected ? (
        <section
          ref={detailRef}
          aria-labelledby="recv3-detail-eyebrow"
          className="grid scroll-mt-20 gap-6 card-standard p-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:gap-8"
          data-testid="recv3-selected"
        >
          <p role="status" aria-live="polite" className="sr-only" data-testid="recv3-announce">
            {t("recv3.selected", { invoice: selected.invoice ?? selected.buyer_name ?? "" })}
          </p>
          <div key={selected.receivable_id} className="motion-swap min-w-0">
            <InvoiceDetail row={selected} customerHref={customerHref(selected)} dealHref={dealHref(selected)} history={view?.payments?.sentence ?? null} primaryHere={!narrow} />
          </div>
          <div key={`${selected.receivable_id}-aside`} className="motion-swap min-w-0">
            <StressAside
              row={selected}
              exposure={view}
              loading={exposure.loading && !view}
              failed={Boolean(exposure.error) && !view}
              onRetry={exposure.reload}
              exploreHref={withContext("/cash", params, { customer: selected.buyer_id ?? null, invoice: selected.receivable_id }, selected.buyer_id ? { stress: `${selected.buyer_id}:${view?.stress?.delay_days ?? STRESS_DAYS}` } : {})}
              customerHref={customerHref(selected)}
            />
          </div>
        </section>
      ) : null}

      {history}
    </div>
  );
}
