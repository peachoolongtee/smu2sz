"use client";

import Link from "next/link";
import { ContractCard, contractsOff, DocStatusBadge } from "@/components/documents";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { getDocuments } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * The contracts and lender agreements the agent has read (GET /documents), each with where it stands, laid out as the
 * brief-03 prototype. A reading counts only once the owner confirms it.
 */
export function DocumentsCard() {
  const { t } = useI18n();
  const docs = useAsync(getDocuments, []);
  const list = docs.data?.documents ?? [];
  return (
    <ContractCard id="home-documents" title={t("home.docs")} aside={<span className="text-[13px] text-ink-3">{t("home.docs.sub")}</span>}>
      {contractsOff(docs.error) ? (
        <p className="text-sm text-ink-3" data-testid="home-docs-off">
          {t("home.deals.off")}
        </p>
      ) : docs.error ? (
        <ErrorState error={docs.error} onRetry={docs.reload} />
      ) : !docs.data ? (
        <LoadingBlock rows={2} />
      ) : (
        <>
          {list.length === 0 ? (
            <p className="text-ink-3" data-testid="home-docs-empty">
              {t("home.docs.empty")}
            </p>
          ) : (
            <ul className="grid" data-testid="home-docs-list">
              {list.map((d) => (
                <li
                  key={d.id}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-b border-line py-2.5 first:pt-0 last:border-b-0"
                  data-testid={`home-doc-${d.id}`}
                  data-status={d.status}
                >
                  <div className="min-w-0">
                    <Link href={`/documents?id=${encodeURIComponent(d.id)}`} className="font-medium text-ink hover:underline">
                      {d.title}
                    </Link>
                    <p className="break-words text-[12.5px] text-ink-3">
                      {d.counterparty_name} · {d.summary}
                    </p>
                  </div>
                  <DocStatusBadge doc={d} />
                </li>
              ))}
            </ul>
          )}
          <Link href="/documents" className="mt-2.5 block rounded-lg border border-dashed border-line-strong p-3 text-center text-[13px] text-ink-3 hover:bg-subtle">
            {t("home.docs.upload")}
          </Link>
        </>
      )}
    </ContractCard>
  );
}
