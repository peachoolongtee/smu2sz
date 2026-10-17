"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ContractWorkbench } from "@/components/capex/contract-workbench";
import { contractsOff } from "@/components/documents";
import { EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { getPurchase } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

export default function Page() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <ContractPage />
    </Suspense>
  );
}

/** One capex contract on the owner's timeline, on a page of its own: the same workbench as Capex. */
function ContractPage() {
  const { t, lang } = useI18n();
  const id = useSearchParams().get("id") ?? "";
  const row = useAsync(() => getPurchase(id, lang), [id, lang]);

  if (row.error && contractsOff(row.error)) {
    return <EmptyState title={t("buy.off.title")} body={t("buy.off.body")} />;
  }
  const p = row.data;
  return (
    <div className="flow-f min-w-0">
      <PageHeader
        title={p?.title ?? t("buy.contract.title")}
        subtitle={p ? `${p.vendor_name}${p.price_display ? ` · ${p.price_display}` : ""}` : t("buy.contract.sub")}
      />
      {row.error ? <ErrorState error={row.error} onRetry={row.reload} /> : null}
      <ContractWorkbench id={id} row={p} onCommitted={row.reload} />
    </div>
  );
}
