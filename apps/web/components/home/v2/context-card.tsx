"use client";

import { Disclosure } from "@/components/business/kit";
import { ButtonLink } from "@/components/ui";
import { StatusPill, type PillTone } from "@/components/ui/status-pill";
import { getCustomerFocus } from "@/lib/api";
import { customerHref } from "@/lib/customer-href";
import { useI18n } from "@/lib/i18n";
import type { WorklistCustomer, WorklistNeedsRow, WorklistWaitingRow } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/**
 * "Deal context" (the mockup's right-hand panel while a row is selected, in place of the upcoming movements): the deal's subject, the current stage as the row's own status pill, one
 * server sentence (the row's consequence), "Customer profile" (an outlined button to the customer's page) and the "Agreement & supporting evidence" fold (the deal's own sentence from the
 * overview read: what the buyer asks and what FLOW recommends). For a customer with no deal chosen it is "Customer context" with the overview's own sentence. Every word is the server's.
 */
export function ContextCard({ customerId, decision, row, customer, onBack, dealCash }: { customerId: string; decision: string | null; row: WorklistNeedsRow | WorklistWaitingRow | null; customer: WorklistCustomer | null; onBack: () => void; dealCash?: React.ReactNode }) {
  const { t, lang } = useI18n();
  const overview = useAsync(() => getCustomerFocus(customerId, lang, decision ? { decision } : {}), [customerId, decision, lang]);
  const v = overview.data;
  const name = v?.name ?? customer?.name ?? "";
  const tone: PillTone = row ? (row.owner === "NEEDS_YOU" ? "amber" : "lavender") : customer && (customer.tone === "bad" || customer.tone === "warn") ? "amber" : customer?.tone === "ok" ? "green" : "lavender";
  const stage = row?.status_text ?? customer?.status_text ?? null;
  const sentence = row?.consequence_text ?? v?.summary_text ?? customer?.detail_text ?? null;
  const evidence = decision ? (v?.decision?.text ?? null) : (v?.summary_text ?? null);
  return (
    <section aria-labelledby="hv2-context-title" className="motion-reveal f-card min-w-0 p-4" data-testid="hv2-context">
      <button type="button" onClick={onBack} className="motion-press -ml-2 mb-2 inline-flex min-h-10 items-center gap-1.5 rounded-control px-2 text-[15px] font-semibold text-ink hover:bg-subtle touch:min-h-11" data-testid="hv2-context-back">
        <span aria-hidden>←</span>
        {t("hv2.context.back")}
      </button>
      <h2 id="hv2-context-title" className="font-display text-[18px] font-bold leading-tight tracking-[-0.01em] text-ink">
        {decision ? t("hv2.context.title") : t("hv2.context.titleCustomer")}
      </h2>
      {/* The deal's own cash impact (as asked against FLOW's reply): the first block of the panel */}
      {dealCash}
      <p className="mt-3 border-b border-line pb-4 text-[15px] text-ink-3" data-testid="hv2-context-subject">
        {[row?.subject_text, name].filter(Boolean).join(" · ")}
      </p>
      {stage ? (
        <div className="mt-4 flex items-center justify-between gap-3">
          <span className="text-[15px] font-medium text-ink">{t("hv2.context.stage")}</span>
          <StatusPill tone={tone} testId="hv2-context-stage">
            {stage}
          </StatusPill>
        </div>
      ) : null}
      {sentence ? (
        <p className="mt-4 text-pretty text-[15px] leading-snug text-ink-2" data-testid="hv2-context-sentence">
          {sentence}
        </p>
      ) : null}
      <ButtonLink href={customerHref(customerId, decision ? { decision } : undefined)} className="mt-4 w-full" data-testid="focus-open-customer">
        {t("hv2.context.profile")}
      </ButtonLink>
      {evidence ? (
        <Disclosure summary={t("hv2.context.evidence")} testId="hv2-context-evidence" className="mt-5 border-t border-line pt-1">
          <p className="pb-1 text-pretty text-sm text-ink-2" data-testid="hv2-context-evidence-text">
            {evidence}
          </p>
        </Disclosure>
      ) : null}
    </section>
  );
}
