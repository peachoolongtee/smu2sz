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
import { getClock, getDeals, getOffer, getState, getWorklist } from "@/lib/api";
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
  return decision ? <Run key={decision} decision={decision} customer={sel.customer ?? null} /> : <Ask customer={sel.customer ?? null} lang={lang} t={t} />;
}

/** No negotiation named: ask which one, from the queue's own rows (one per negotiation). */
function Ask({ customer, lang, t }: { customer: string | null; lang: "en" | "zh"; t: ReturnType<typeof useI18n>["t"] }) {
  const deals = useAsync(() => getDeals(lang, {}).catch(() => null), [lang]);
  const needWorklist = deals.data !== undefined && !deals.data?.queue;
  const worklist = useAsync(() => (needWorklist ? getWorklist(lang).catch(() => null) : Promise.resolve(null)), [lang, needWorklist]);
  const queue = deals.data === undefined || (needWorklist && worklist.data === undefined) ? undefined : buildQueue(deals.data, worklist.data, { agreedTerms: (x) => x, agreedRef: (x) => x });
  const open = queue ? taskRows(queue).filter((x) => x.tier !== "agreements" && rowDecision(x.row) && (!customer || x.row.customer_id === customer)) : [];
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
  const { t } = useI18n();
  const offerId = offerOf(decision);
  const offer = useAsync(async () => ({ offerId, view: offerId ? await getOffer(offerId).catch(() => null) : null }), [offerId]);
  const books = useAsync(getState, []);
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
  return <Sandbox decision={decision} customer={buyerId} start={startOf(read.view, books.data)} title={record.data?.headline ?? record.data?.counterparty_name ?? null} />;
}

function Sandbox({ decision, customer, start, title }: { decision: string; customer: string | null; start: WhatIfParams; title: string | null }) {
  const { t } = useI18n();
  const [params, setParams] = useState<WhatIfParams>(start);
  const { result, error, loading, reload } = useWhatIf(params, { customer, decision });
  // Days are said as distances from the simulated today.
  const clock = useAsync(getClock, []);
  const today = clock.data?.day ?? 0;
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
      <p className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm text-ink-2" data-testid="whatif-scope">
        <span className="font-bold text-ink">{t("whatif.scope")}</span>
        <span>{title ?? ""}</span>
        <Link href={`/deals?decision=${encodeURIComponent(decision)}${customer ? `&customer=${encodeURIComponent(customer)}` : ""}&from=whatif`} className="font-bold text-brand-700 underline underline-offset-2" data-testid="whatif-scope-back">
          {t("whatif.scope.back")}
        </Link>
      </p>
      {other ? (
        <div className="mb-4" data-testid="whatif-scope-mismatch">
          <Callout tone="warn">{t("whatif.scope.mismatch")}</Callout>
        </div>
      ) : null}

      {!result ? (
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
            <WhatIfSummaryCard r={result} loading={loading} today={today} />
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
