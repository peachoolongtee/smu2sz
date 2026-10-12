"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { InvoiceDetail } from "@/components/receivables/invoice-detail";
import { InvoiceList } from "@/components/receivables/invoice-list";
import { inFilter, type RecvFilter } from "@/components/receivables/state";
import { STRESS_DAYS, StressAside } from "@/components/receivables/stress-aside";
import { Summary } from "@/components/receivables/summary";
import { PartialRead } from "@/components/business/freshness";
import { ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { PromisedAndReceived } from "@/components/receivables/history";
import { getDecisionExposure, getReceivables, getReconciliation, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { withContext } from "@/lib/receivables-context";
import type { ReceivableRow, ReceivablesRead } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { LegacyReceivables } from "./legacy";

/**
 * Receivables in three layers (map #110): what customers owe you, what each invoice nets once its financing is repaid, and what to do about it.
 * It reads `GET /receivables?lang=`; a server without that route (null) keeps the page of before (`legacy.tsx`), and each section renders only when its
 * field is present. The chosen invoice is in the address (`?invoice=`) beside the shared context (`customer`, `decision`, `path`), and nowhere else.
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
  if (read.error) {
    return (
      <>
        <PageHeader section="recv" title={t("nav.receivables")} subtitle={t("biz.recv.subtitle")} />
        <ErrorState error={read.error} onRetry={read.reload} />
      </>
    );
  }
  if (read.data === undefined) {
    return (
      <>
        <PageHeader section="recv" title={t("nav.receivables")} subtitle={t("biz.recv.subtitle")} />
        <LoadingBlock rows={3} />
      </>
    );
  }
  // The server has no GET /receivables yet: the page of before.
  if (read.data === null || !Array.isArray(read.data.rows)) return <LegacyReceivables />;
  return <Layers read={read.data} reload={read.reload} />;
}

function Layers({ read, reload }: { read: ReceivablesRead; reload: () => void }) {
  const { t, lang } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const rows = read.rows ?? [];
  const [filter, setFilter] = useState<RecvFilter>("all");
  const invoiceParam = params.get("invoice");
  const shown = rows.filter((r) => inFilter(r, filter));
  const selected: ReceivableRow | null = rows.find((r) => r.receivable_id === invoiceParam) ?? shown[0] ?? rows[0] ?? null;

  const select = (id: string) => {
    const q = new URLSearchParams(params.toString());
    q.set("invoice", id);
    router.replace(`/receivables?${q.toString()}`, { scroll: false });
  };

  // A link such as /receivables#RI:BUYER-1:2 (the home's remaining task) chooses that invoice and brings its row into view.
  useEffect(() => {
    if (typeof window === "undefined" || !window.location.hash || params.get("invoice")) return;
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (!rows.some((r) => r.receivable_id === id)) return;
    const q = new URLSearchParams(params.toString());
    q.set("invoice", id);
    router.replace(`/receivables?${q.toString()}${window.location.hash}`, { scroll: false });
    document.getElementById(id)?.scrollIntoView({ block: "center" });
    // Once per load: the hash is the arrival, the address is the state afterwards.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The late-payment test needs a deal to be read against: the one whose counter would apply to this invoice, else the one in the address.
  const decisionId = selected?.pending_counter?.decision_id ?? params.get("decision");
  const exposure = useAsync(() => (decisionId ? getDecisionExposure(decisionId, lang) : Promise.resolve(null)), [decisionId, lang]);
  const forBuyer = selected && exposure.data && exposure.data.buyer_id === selected.buyer_id ? exposure.data : null;

  // What was promised early and what arrived, under the layers: the reconciliation read, as the page has always shown it. If it cannot be read
  // the page stands without it (the server's own `partial` says so for the rows' side); nothing is shown in its place.
  const recon = useAsync(getReconciliation, [lang]);
  const books = useAsync(getState, []);
  const nameOf = (id: string | null) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? rows.find((r) => r.buyer_id === id)?.buyer_name ?? id ?? "";

  const customerHref = (r: ReceivableRow) =>
    withContext(`/customers/${encodeURIComponent(r.buyer_id ?? "")}`, params, { customer: r.buyer_id ?? null, invoice: r.receivable_id });
  const dealHref = (r: ReceivableRow) =>
    r.pending_counter?.decision_id ? withContext("/deals", params, { decision: r.pending_counter.decision_id, customer: r.buyer_id ?? null, invoice: r.receivable_id }, r.buyer_id ? { buyer: r.buyer_id } : {}) : null;

  return (
    <div className="space-y-6" data-testid="recv3-page">
      <div>
        <Summary read={read} rows={rows} />
      </div>
      <PartialRead partial={read.partial} onRetry={reload} />
      <InvoiceList rows={rows} selectedId={selected?.receivable_id ?? null} onSelect={select} filter={filter} onFilter={setFilter} customerHref={customerHref} />

      {selected ? (
        <section
          aria-labelledby="recv3-detail-title"
          className="grid gap-6 rounded-card border border-line bg-surface p-5 shadow-card lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:gap-8"
          data-testid="recv3-selected"
        >
          <p role="status" aria-live="polite" className="sr-only" data-testid="recv3-announce">
            {t("recv3.selected", { invoice: selected.invoice ?? selected.buyer_name ?? "" })}
          </p>
          <div key={selected.receivable_id} className="motion-swap min-w-0">
            <InvoiceDetail row={selected} customerHref={customerHref(selected)} dealHref={dealHref(selected)} history={forBuyer?.payments?.sentence ?? null} />
          </div>
          <div key={`${selected.receivable_id}-aside`} className="motion-swap min-w-0">
            <StressAside
              row={selected}
              exposure={forBuyer}
              loading={Boolean(decisionId) && exposure.loading}
              failed={Boolean(decisionId) && Boolean(exposure.error)}
              onRetry={exposure.reload}
              exploreHref={withContext("/cash", params, { customer: selected.buyer_id ?? null, invoice: selected.receivable_id }, selected.buyer_id ? { stress: `${selected.buyer_id}:${forBuyer?.stress?.delay_days ?? STRESS_DAYS}` } : {})}
              customerHref={customerHref(selected)}
            />
          </div>
        </section>
      ) : null}

      {recon.data ? (
        <div className="space-y-7" data-testid="recv3-history-sections">
          <PromisedAndReceived data={recon.data} name={nameOf} />
        </div>
      ) : null}
    </div>
  );
}
