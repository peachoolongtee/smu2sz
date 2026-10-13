"use client";

import { Announce, Dismiss, Reading } from "@/components/home/v2/focus-parts";
import { InvoiceCards } from "@/components/home/v2/invoice-card";
import { ActionRow } from "@/components/home/v2/worklist";
import { OpenSection } from "@/components/ui/open-section";
import { StateWord } from "@/components/ui/state-word";
import { stateKey } from "@/components/ui/state-word-model";
import { getCustomerFocus } from "@/lib/api";
import type { HomeSelection } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { CustomerOverviewView, OverviewFigure, OverviewTone, WorklistView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const TONE_TEXT: Record<OverviewTone, string> = { neutral: "text-ink", ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };

function Figure({ figure }: { figure: OverviewFigure }) {
  const key = stateKey(figure.state);
  return (
    <div className="min-w-0 py-3 pr-4 sm:border-l sm:border-line sm:px-4 sm:first:border-l-0 sm:first:pl-0" data-testid={`focus-figure-${figure.key}`}>
      <dt className="text-supporting font-bold text-ink-3">{figure.label}</dt>
      <dd className={`mt-1 break-words font-display text-xl font-bold tabular-nums ${TONE_TEXT[figure.tone]}`} data-testid={`focus-figure-${figure.key}-value`}>
        {figure.value_display}
      </dd>
      {key && figure.state_text ? (
        <dd className="mt-0.5">
          <StateWord state={key} testId={`focus-figure-${figure.key}-state`}>
            {figure.state_text}
          </StateWord>
        </dd>
      ) : null}
      <dd className="mt-0.5 break-words text-supporting text-ink-2">{figure.note}</dd>
    </div>
  );
}

/**
 * A customer, in place: the way up, the name and the server's sentence with the way to the customer's page, the four figures on hairlines with their state words (the Customer
 * overview's own read), and what is open with this customer from the worklist's rows (a decision opens in place, another row leads where the server says). The company
 * strip and the alert stay where they are (the alert as the health band above). Closing (Escape, "All business") clears the selection.
 */
export function CustomerFocusPanel({ customerId, worklist, selection, onAll }: { customerId: string; worklist: WorklistView | null | undefined; selection: HomeSelection; onAll: () => void }) {
  const { t, lang } = useI18n();
  const view = useAsync(() => getCustomerFocus(customerId, lang), [customerId, lang]);
  const rows = [...(worklist?.needs_you ?? []), ...(worklist?.waiting ?? [])].filter((r) => r.customer_id === customerId);
  return (
    <div id="home-focus" data-testid="home-customer-focus" data-customer={customerId} className="f-card f-card-white min-w-0 p-6">
      <Announce text={view.data?.name ?? ""} />
      <div key={customerId} className="motion-swap">
        <Reading read={view}>
          {(v: CustomerOverviewView) => (
            <>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 id="home-focus-title" tabIndex={-1} className="font-display text-[22px] font-bold leading-tight tracking-[-0.01em] text-ink" data-testid="focus-title">
                    {v.name}
                  </h2>
                  {v.summary_text ? <p className="mt-1.5 text-pretty text-[15px] text-ink-3">{v.summary_text}</p> : null}
                </div>
                <Dismiss onDismiss={onAll} />
              </div>
              {v.figures?.length ? (
                <dl aria-label={t("hv2.focus.figures")} className="mt-4 grid grid-cols-2 border-y border-line sm:grid-cols-4" data-testid="focus-figures">
                  {v.figures.map((f) => (
                    <Figure key={f.key} figure={f} />
                  ))}
                </dl>
              ) : null}
              <InvoiceCards customerId={customerId} />
              <OpenSection title={t("hv2.focus.rows")} first className="mt-7">
                {rows.length ? (
                  <ul className="divide-y divide-line" data-testid="focus-rows">
                    {rows.map((r) => (
                      <ActionRow key={r.key} row={r} selection={selection} />
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-ink-2" data-testid="focus-rows-none">
                    {v.none_text ?? t("hv2.focus.none")}
                  </p>
                )}
              </OpenSection>
            </>
          )}
        </Reading>
      </div>
    </div>
  );
}
