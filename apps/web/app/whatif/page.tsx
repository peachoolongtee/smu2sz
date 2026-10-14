"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { buildQueue, rowDecision, taskRows } from "@/components/deals/flow/queue-model";
import { WhatIfControlsCard } from "@/components/whatif-controls";
import {
  WhatIfCashCard,
  WhatIfCountersCard,
  WhatIfCovenantsCard,
  WhatIfMeterCard,
  WhatIfPlanCard,
  WhatIfSummaryCard,
  WhatIfTestedCard,
  WhatIfVerdictCard,
} from "@/components/whatif-results";
import { Disclosure } from "@/components/business/kit";
import { Badge, Callout, EmptyState, ErrorState, LoadingBlock, PageHeader, ButtonLink } from "@/components/ui";
import { getClock, getDeals, getOffer, getState, getWorklist, whatIfScope } from "@/lib/api";
import type { WhatIfResult } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { offerOf, readSelection, selectionHref } from "@/lib/selection";
import type { WhatIfParams } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useDecision } from "@/lib/use-decision";
import { startOf } from "./start";
import { useWhatIf } from "./use-whatif";

/**
 * What-if (tickets #126, audit UX26): the sandbox is run for a negotiation, named in the address (`customer`, `decision`). It opens on THAT offer's terms and says so; with no
 * negotiation named it asks which one and lists the open ones. It never opens on a sample. A selection the server cannot honour (`context.irrelevant_text`, or an offer it does not
 * have) asks again. The terms the sliders start from are read off the offer's own obligations; every figure after that is the server's.
 */
export default function WhatIfPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <WhatIf />
    </Suspense>
  );
}

function WhatIf() {
  const { t, lang } = useI18n();
  const params = useSearchParams();
  const sel = readSelection(params);
  const decision = sel.decision ?? null;
  // (keyed by the language too: the server words the invoice and the labels in the language it was asked in)
  return decision ? <Run key={`${decision}|${lang}`} decision={decision} customer={sel.customer ?? null} /> : <Ask customer={sel.customer ?? null} lang={lang} t={t} />;
}

/** No negotiation named: ask which one, from the queue's own rows that are negotiations (kind DECISION: a loan approval, a promise or an agreement is not one, though it may carry a record id). */
function Ask({ customer, lang, t }: { customer: string | null; lang: "en" | "zh"; t: ReturnType<typeof useI18n>["t"] }) {
  const deals = useAsync(() => getDeals(lang, {}).catch(() => null), [lang]);
  const needWorklist = deals.data !== undefined && !deals.data?.queue;
  const worklist = useAsync(() => (needWorklist ? getWorklist(lang).catch(() => null) : Promise.resolve(null)), [lang, needWorklist]);
  const queue = deals.data === undefined || (needWorklist && worklist.data === undefined) ? undefined : buildQueue(deals.data, worklist.data, null, { agreedTerms: (x: string) => x, agreedRef: (x: string) => x });
  const open = queue ? taskRows(queue).filter((x) => x.tier !== "agreements" && (x.row.kind === "DECISION" || x.row.kind === "BUYER_REPLY") && rowDecision(x.row) && (!customer || x.row.customer_id === customer)) : [];
  return (
    <>
      <PageHeader title={t("whatif.title")} subtitle={t("whatif.ask.sub")} actions={<Badge tone="info">{t("whatif.hypothetical")}</Badge>} />
      <section aria-labelledby="whatif-ask-title" className="max-w-2xl" data-testid="whatif-ask">
        <h2 id="whatif-ask-title" className="type-section text-ink">
          {t("deals.which.title")}
        </h2>
        <p className="mt-1 text-sm text-ink-2">{t("whatif.ask.body")}</p>
        {queue === undefined ? (
          <div className="mt-3">
            <LoadingBlock rows={2} />
          </div>
        ) : open.length ? (
          <ul className="mt-3 divide-y divide-line border-y border-line" data-testid="whatif-choices">
            {open.map(({ row }) => (
              <li key={row.key}>
                <Link href={selectionHref("/whatif", { customer: row.customer_id, decision: rowDecision(row), from: "deal" })} className="flex min-h-11 flex-col justify-center gap-0.5 px-1 py-2.5 hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2" data-testid="whatif-choice">
                  <span className="text-[15px] font-bold text-ink">{row.subject_text}</span>
                  {row.consequence_text ? <span className="text-supporting text-ink-3">{row.consequence_text}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-3" data-testid="whatif-none">
            <EmptyState title={t("whatif.ask.none")} body={t("whatif.ask.none.body")} action={<ButtonLink href="/deals">{t("nav.backToDeals")}</ButtonLink>} />
          </div>
        )}
      </section>
    </>
  );
}

/** A negotiation named: the sandbox opens on its terms. */
function Run({ decision, customer }: { decision: string; customer: string | null }) {
  const { t, lang } = useI18n();
  const offerId = offerOf(decision);
  const offer = useAsync(async () => ({ offerId, view: offerId ? await getOffer(offerId).catch(() => null) : null }), [offerId]);
  const books = useAsync(getState, []);
  // Whether the sandbox can act on this buyer at all, before any slider is sent (a buyer with no recurring invoice has no terms to start from).
  const scope = useAsync(async () => ({ offerId, scope: offerId ? await whatIfScope(offerId, lang) : null }), [offerId, lang]);
  const record = useDecision(decision);
  const read = offer.data && offer.data.offerId === offerId ? offer.data : undefined;
  const buyerId = read?.view?.offer.counterparty_id ?? null;
  const mismatch = Boolean(customer && buyerId && customer !== buyerId);
  const ask = (text: string) => (
    <>
      <PageHeader title={t("whatif.title")} subtitle={t("whatif.ask.sub")} actions={<Badge tone="info">{t("whatif.hypothetical")}</Badge>} />
      <div data-testid="whatif-ask" className="max-w-2xl">
        <h2 className="type-section text-ink">{t("deals.which.title")}</h2>
        <p className="mt-1 text-sm text-ink-2" data-testid="whatif-irrelevant">
          {text}
        </p>
        <div className="mt-3">
          <ButtonLink href="/whatif">{t("whatif.ask.choose")}</ButtonLink>
        </div>
      </div>
    </>
  );
  if (offer.error) return <ErrorState error={offer.error} onRetry={offer.reload} />;
  if (!read || !books.data) return books.error ? <ErrorState error={books.error} onRetry={books.reload} /> : <LoadingBlock rows={4} />;
  if (!read.view || mismatch) return ask(t("deals.irrelevant"));
  if (!scope.data || scope.data.offerId !== offerId) return scope.error ? <ErrorState error={scope.error} onRetry={scope.reload} /> : <LoadingBlock rows={4} />;
  if (scope.data.scope && scope.data.scope.available === false) {
    const s = scope.data.scope;
    return (
      <>
        <PageHeader title={t("whatif.title")} subtitle={t("whatif.subtitle")} actions={<Badge tone="info">{t("whatif.hypothetical")}</Badge>} />
        <p className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm text-ink-2" data-testid="whatif-scope">
          <span className="font-bold text-ink">{t("whatif.scope")}</span>
          <span>{record.data?.headline ?? record.data?.counterparty_name ?? ""}</span>
          {s.invoice_text ? <span data-testid="whatif-invoice">{s.invoice_text}</span> : null}
          <Link href={`/deals?decision=${encodeURIComponent(decision)}${buyerId ? `&customer=${encodeURIComponent(buyerId)}` : ""}&from=whatif`} className="font-bold text-brand-700 underline underline-offset-2" data-testid="whatif-scope-back">
            {t("whatif.scope.back")}
          </Link>
        </p>
        <div className="max-w-2xl" data-testid="whatif-unscoped">
          <Callout tone="warn">{s.scope_text}</Callout>
        </div>
      </>
    );
  }
  return <Sandbox decision={decision} customer={buyerId} start={startOf(read.view, books.data)} title={record.data?.headline ?? record.data?.counterparty_name ?? null} />;
}

function Sandbox({ decision, customer, start, title }: { decision: string; customer: string | null; start: WhatIfParams; title: string | null }) {
  const { t, lang } = useI18n();
  const [params, setParams] = useState<WhatIfParams>(start);
  const { result: answer, error, loading, reload } = useWhatIf(params, { offerId: offerOf(decision), lang });
  // Days are said as distances from the simulated today.
  const clock = useAsync(getClock, []);
  const today = clock.data?.day ?? 0;
  // The server says which invoice it ran on (`invoice_text`), or why the buyer has none the sandbox can act on (`scope_text`, with no verdict and no controls).
  const unscoped = answer && answer.available === false ? answer : null;
  const result: WhatIfResult | undefined = answer && answer.available !== false ? answer : undefined;
  const near = result?.mock_nearest;
  // The server says what it ran for (`context`): another customer than the one asked about is shown, not hidden, and a selection it cannot honour asks again.
  const ran = result?.context ?? null;
  const other = Boolean(ran?.customer && customer && ran.customer !== customer);
  if (ran?.irrelevant_text) {
    return (
      <>
        <PageHeader title={t("whatif.title")} subtitle={t("whatif.ask.sub")} actions={<Badge tone="info">{t("whatif.hypothetical")}</Badge>} />
        <div data-testid="whatif-ask" className="max-w-2xl">
          <h2 className="type-section text-ink">{t("deals.which.title")}</h2>
          <p className="mt-1 text-sm text-ink-2" data-testid="whatif-irrelevant">
            {ran.irrelevant_text}
          </p>
          <div className="mt-3">
            <ButtonLink href="/whatif">{t("whatif.ask.choose")}</ButtonLink>
          </div>
        </div>
      </>
    );
  }
  return (
    <>
      <PageHeader title={t("whatif.title")} subtitle={t("whatif.subtitle")} actions={<Badge tone="info">{t("whatif.hypothetical")}</Badge>} />
      <p className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm text-ink-2 ${result?.scope_text || result?.compare_text ? "mb-1" : "mb-4"}`} data-testid="whatif-scope">
        <span className="font-bold text-ink">{t("whatif.scope")}</span>
        <span>{title ?? ""}</span>
        {(result ?? unscoped)?.invoice_text ? <span data-testid="whatif-invoice">{(result ?? unscoped)?.invoice_text}</span> : null}
        <Link href={`/deals?decision=${encodeURIComponent(decision)}${customer ? `&customer=${encodeURIComponent(customer)}` : ""}&from=whatif`} className="font-bold text-brand-700 underline underline-offset-2" data-testid="whatif-scope-back">
          {t("whatif.scope.back")}
        </Link>
      </p>
      {result?.scope_text || result?.compare_text ? (
        <div className="mb-4 max-w-[68ch] space-y-1 text-sm text-ink-2">
          {result.scope_text ? <p data-testid="whatif-scope-text">{result.scope_text}</p> : null}
          {result.compare_text ? <p data-testid="whatif-compare">{result.compare_text}</p> : null}
        </div>
      ) : null}
      {other ? (
        <div className="mb-4" data-testid="whatif-scope-mismatch">
          <Callout tone="warn">{t("whatif.scope.mismatch")}</Callout>
        </div>
      ) : null}

      {unscoped ? (
        <div className="max-w-2xl" data-testid="whatif-unscoped">
          <Callout tone="warn">{unscoped.scope_text}</Callout>
        </div>
      ) : !result ? (
        error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : (
          <LoadingBlock rows={4} />
        )
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <div className="lg:sticky lg:top-4 lg:self-start">
            <WhatIfControlsCard controls={result.controls} params={params} onChange={setParams} />
          </div>

          <div className={`min-w-0 space-y-6 transition-opacity ${loading ? "opacity-75" : ""}`} aria-busy={loading}>
            {error ? <ErrorState error={error} onRetry={reload} /> : null}
            {near ? (
              <Callout tone="warn">
                {t("whatif.mockNearest", {
                  terms: near.params.terms_days,
                  discount: result.controls.rate_labels[String(near.params.discount_bp)] ?? "",
                  rebate: result.controls.rate_labels[String(near.params.rebate_bp)] ?? "",
                })}
              </Callout>
            ) : null}
            <WhatIfSummaryCard r={result} loading={loading} />
            <WhatIfCashCard r={result} today={today} />
            <Disclosure className="border-t border-line pt-1" summary={t("whatif.details")} testId="whatif-details">
              <div className="space-y-6">
                <WhatIfVerdictCard r={result} loading={loading} />
                <div className="grid gap-6 xl:grid-cols-2">
                  <WhatIfMeterCard r={result} />
                  <div className="space-y-6">
                    <WhatIfCovenantsCard r={result} />
                    <WhatIfPlanCard r={result} />
                  </div>
                </div>
                <WhatIfCountersCard r={result} />
                <WhatIfTestedCard r={result} />
              </div>
            </Disclosure>
          </div>
        </div>
      )}
    </>
  );
}
