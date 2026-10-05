"use client";

import Link from "next/link";
import { contractsOff, DocStatusBadge } from "@/components/documents";
import { Card, ErrorState, LoadingBlock } from "@/components/ui";
import { getDocuments } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import { SectionLink } from "./today-card";

/** The contracts and lender agreements the agent has read (GET /documents), each with where it stands. A reading counts only once the owner confirms it. */
export function DocumentsCard() {
  const { t } = useI18n();
  const docs = useAsync(getDocuments, []);
  const list = docs.data?.documents ?? [];
  return (
    <Card id="home-documents" title={t("home.docs")} subtitle={t("home.docs.sub")} actions={<SectionLink href="/documents">{t("home.docs.open")}</SectionLink>}>
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
            <p className="text-sm text-ink-3" data-testid="home-docs-empty">
              {t("home.docs.empty")}
            </p>
          ) : (
            <ul className="divide-y divide-line" data-testid="home-docs-list">
              {list.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 first:pt-0" data-testid={`home-doc-${d.id}`} data-status={d.status}>
                  <div className="min-w-0">
                    <Link href={`/documents?id=${encodeURIComponent(d.id)}`} className="text-sm font-medium text-ink underline-offset-2 hover:underline">
                      {d.title}
                    </Link>
                    <p className="break-words text-xs text-ink-3">
                      {d.counterparty_name} · {d.summary}
                    </p>
                  </div>
                  <DocStatusBadge doc={d} />
                </li>
              ))}
            </ul>
          )}
          <Link href="/documents" className="mt-3 block rounded-md border border-dashed border-line-strong px-3 py-3 text-center text-sm text-ink-3 hover:bg-subtle">
            {t("home.docs.upload")}
          </Link>
        </>
      )}
    </Card>
  );
}
