"use client";

import Link from "next/link";
import { StateWord } from "@/components/ui/state-word";
import { stateKey } from "@/components/ui/state-word-model";
import { useI18n } from "@/lib/i18n";
import type { ReceivableFlow } from "@/lib/types";

/**
 * From receivable to cash (round two, section 3): the customer's largest open invoice as a vertical list of steps, each a figure and a when-word (owed, financing planned, the customer pays,
 * repayment and fees, net available at collection), then one row of linked chips (negotiation, invoice, financing, payment status). Every figure and word is the server's `receivable_flow`;
 * nothing is computed here. A step the server has no figure for shows its words alone, "no financing linked" is simply fewer steps, and without steps the card is not drawn.
 */
export function ReceivableFlowCard({ flow }: { flow: ReceivableFlow }) {
  const { t } = useI18n();
  if (!flow.steps?.length) return null;
  const links = flow.links ?? [];
  return (
    <section aria-labelledby="customer-flow-title" className="flow-card p-4 sm:p-6" data-testid="customer-flow">
      <h2 id="customer-flow-title" className="type-section text-ink">
        {flow.title ?? t("customer.flow.title")}
      </h2>
      {flow.invoice_text ? <p className="mt-1 text-sm text-ink-2" data-testid="customer-flow-invoice">{flow.invoice_text}</p> : null}
      <ol className="mt-4" data-testid="customer-flow-steps">
        {flow.steps.map((s, i) => {
          const last = i === flow.steps.length - 1;
          const key = stateKey(s.state ?? undefined);
          return (
            <li key={s.key} className={`relative grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3 ${last ? "" : "pb-5"}`} data-testid={`customer-flow-step-${s.key}`}>
              {last ? null : <span aria-hidden className="absolute bottom-0 left-[13px] top-7 w-px bg-line-ui" />}
              <span aria-hidden className="relative z-[1] grid size-7 place-items-center rounded-pill bg-card text-supporting font-bold tabular-nums text-ink ring-1 ring-line-ui">
                {i + 1}
              </span>
              <div className="min-w-0 pt-0.5">
                <p className="text-supporting font-bold text-ink-3">{s.label}</p>
                {s.value_display ? <p className="font-display text-xl font-extrabold leading-tight tabular-nums text-ink">{s.value_display}</p> : null}
                {s.when_text ? <p className="text-sm text-ink-2">{s.when_text}</p> : null}
                {s.text ? <p className="text-supporting text-ink-2">{s.text}</p> : null}
                {key && s.state_text ? (
                  <p className="mt-0.5">
                    <StateWord state={key}>{s.state_text}</StateWord>
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      {links.length ? (
        <nav aria-label={t("customer.flow.links")} className="mt-5 border-t border-line pt-4" data-testid="customer-flow-links">
          <ul className="flex flex-wrap items-center gap-x-1.5 gap-y-2">
            {links.map((l, i) => (
              <li key={l.key} className="flex items-center gap-1.5">
                {i > 0 ? <span aria-hidden className="text-ink-3">›</span> : null}
                <Link href={l.href} prefetch={false} className="motion-press inline-flex min-h-8 items-center rounded-pill border border-line-ui bg-card px-3 text-supporting font-semibold text-ink hover:bg-subtle touch:min-h-11" data-testid={`customer-flow-link-${l.key}`}>
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
    </section>
  );
}
