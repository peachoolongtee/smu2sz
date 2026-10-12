"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { InputsSheet, type SaveCarry } from "@/components/customer/inputs-sheet";
import { ButtonLink, EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { getBuyerInputs } from "@/lib/api";
import { readContext } from "@/lib/customer-href";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * The owner's Inputs sheet for a customer, /customers/{id}/inputs (ticket #97): what the owner knows that the books do not (annual sales, the
 * gross margin and its basis, how the customer is classed), each with where it came from. Opened from "Edit these facts" on the customer's
 * page, with the context that page held in the URL; the server builds the back link from it. Every word and figure is the server's.
 */
export default function InputsPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={4} />}>
      <Inputs />
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

function Inputs() {
  const { t, lang } = useI18n();
  const { id: raw } = useParams<{ id: string }>();
  const id = safeDecode(raw);
  const ctx = readContext(useSearchParams());
  const asked = JSON.stringify([id, lang, ctx.decision ?? null, ctx.path ?? null, ctx.invoice ?? null]);
  const read = useAsync(async () => ({ asked, view: await getBuyerInputs(id, lang, ctx) }), [asked]);
  const missing = read.error instanceof ApiError && read.error.status === 404;
  const [carry, setCarry] = useState<SaveCarry | null>(null);

  if (missing)
    return (
      <div data-testid="inputs-missing">
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
  if (!read.data || read.data.asked !== asked) return <LoadingBlock rows={4} label={t("inputs.loading")} />;
  // keyed by the read, so a saved sheet starts again from what the server now holds
  const view = read.data.view;
  const saved = (next: SaveCarry) => {
    setCarry(next);
    read.reload();
  };
  return <InputsSheet key={JSON.stringify([...(view.fields ?? []), ...(view.firm ?? [])].map((f) => [f.input_text, f.provenance_text]))} view={view} onSaved={saved} carry={carry} />;
}
