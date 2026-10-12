"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { CustomerOverview } from "@/components/customer/overview";
import { ButtonLink, EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { getCustomerOverview } from "@/lib/api";
import { readContext } from "@/lib/customer-href";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * A customer's overview, /customers/{id}: what the relationship is worth and what it puts at risk, in one server read. A drill-down opened
 * from a customer's name on Deals, Receivables, Cash and Activity (never a tab). The context it was opened with (`decision`, `path`, `invoice`)
 * lives in the URL; the server builds the back link from it and the actions carry it onward. Every sentence and figure is the server's.
 */
export default function CustomerPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={4} />}>
      <Customer />
    </Suspense>
  );
}

function safeDecode(raw: string): string {
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

function Customer() {
  const { t, lang } = useI18n();
  const { id: raw } = useParams<{ id: string }>();
  const id = safeDecode(raw);
  const ctx = readContext(useSearchParams());
  // The read is keyed by what it was asked for; an answer for another customer, language or context (the previous read, kept while this one is on its way) is never shown.
  const asked = JSON.stringify([id, lang, ctx.decision ?? null, ctx.path ?? null, ctx.invoice ?? null]);
  const read = useAsync(async () => ({ asked, view: await getCustomerOverview(id, lang, ctx) }), [asked]);
  const missing = read.error instanceof ApiError && read.error.status === 404 && (read.error.detail as { code?: string } | undefined)?.code === "CUSTOMER_NOT_FOUND";

  if (missing)
    return (
      <div data-testid="customer-missing">
        <EmptyState
          title={t("customer.notFound")}
          body={t("customer.notFound.body")}
          action={
            <ButtonLink href="/deals" variant="primary">
              {t("nav.backToDeals")}
            </ButtonLink>
          }
        />
      </div>
    );
  if (read.error) return <ErrorState error={read.error} onRetry={read.reload} />;
  if (!read.data || read.data.asked !== asked) return <LoadingBlock rows={4} label={t("customer.loading")} />;
  return <CustomerOverview view={read.data.view} onRetry={read.reload} />;
}
