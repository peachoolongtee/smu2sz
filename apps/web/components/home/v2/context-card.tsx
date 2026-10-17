"use client";

import { Disclosure } from "@/components/business/kit";
import { ButtonLink } from "@/components/ui";
import { StatusPill, type PillTone } from "@/components/ui/status-pill";
import { getCustomerFocus } from "@/lib/api";
import { customerHref } from "@/lib/customer-href";
import { useI18n } from "@/lib/i18n";
import type { WorklistCustomer } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/**
 * "Customer context" (the mockup's right-hand panel while a customer is selected, in place of the upcoming movements): the customer's name, its current stage as a status pill, the
 * overview's own sentence, "Customer profile" (an outlined button to the customer's page) and the supporting-evidence fold. A deal is not opened on Home (its row leads to Deals), so this
 * panel never describes one. Every word is the server's.
 */
export function ContextCard({ customerId, customer, onBack }: { customerId: string; customer: WorklistCustomer | null; onBack: () => void }) {
  const { t, lang } = useI18n();
  const overview = useAsync(() => getCustomerFocus(customerId, lang), [customerId, lang]);
  const v = overview.data;
  const name = v?.name ?? customer?.name ?? "";
  const tone: PillTone = customer && (customer.tone === "bad" || customer.tone === "warn") ? "amber" : customer?.tone === "ok" ? "green" : "lavender";
  const stage = customer?.status_text ?? null;
  const sentence = v?.summary_text ?? customer?.detail_text ?? null;
  const evidence = v?.summary_text ?? null;
  return (
    <section aria-labelledby="hv2-context-title" className="motion-reveal f-card min-w-0 p-4" data-testid="hv2-context">
      <button type="button" onClick={onBack} className="motion-press -ml-2 mb-2 inline-flex min-h-10 items-center gap-1.5 rounded-control px-2 text-[15px] font-semibold text-ink hover:bg-subtle touch:min-h-11" data-testid="hv2-context-back">
        <span aria-hidden>←</span>
        {t("hv2.context.back")}
      </button>
      <h2 id="hv2-context-title" className="font-display text-[22px] font-bold leading-tight tracking-[-0.01em] text-ink">
        {t("hv2.context.titleCustomer")}
      </h2>
      <p className="mt-3 border-b border-line pb-4 text-[15px] text-ink-3" data-testid="hv2-context-subject">
        {name}
      </p>
      {stage ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <span className="text-[15px] font-medium text-ink">{t("hv2.context.stage")}</span>
          {/* A long stage word wraps inside the pill instead of widening the column (no sideways scroll at 1100). */}
          <span className="flex min-w-0 max-w-full justify-end [&>*]:max-w-full [&>*]:!whitespace-normal [&>*]:!py-1 [&>*]:!leading-tight">
            <StatusPill tone={tone} testId="hv2-context-stage">
              {stage}
            </StatusPill>
          </span>
        </div>
      ) : null}
      {sentence ? (
        <p className="mt-4 text-pretty text-[15px] leading-snug text-ink-2" data-testid="hv2-context-sentence">
          {sentence}
        </p>
      ) : null}
      <ButtonLink href={customerHref(customerId)} className="mt-4 w-full" data-testid="focus-open-customer">
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
