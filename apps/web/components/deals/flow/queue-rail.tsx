"use client";

import { useI18n } from "@/lib/i18n";
import type { PillTone } from "@/components/ui/status-pill";
import { negotiationRows, rowPill } from "./deal-model";
import { rowDecision, rowTarget, type Queue } from "./queue-model";

/** The lifecycle dot's fill by the pill's tone (amber: the owner's turn, lavender: the buyer's, green: agreed, grey: closed). The word is the row's accessible name, never the colour alone. */
const DOT: Record<PillTone, string> = { amber: "bg-warn-solid", lavender: "bg-f-purple", green: "bg-ok-solid", neutral: "bg-ink-3" };

/**
 * The queue stepping aside (round three, section 7): while Compare responses or Cash impact is open the queue is a 72 px rail. Each negotiation is its customer's initial and its lifecycle
 * dot, the selected one marked (the lavender fill and `aria-current`); "Show queue" at the top brings the queue back. The initial is the first letter of the customer's short name the
 * server wrote; the row's name for a reader is the server's subject and lifecycle word. Nothing here is a figure or a sentence of the browser's.
 */
export function QueueRail({ queue, selectedDecision, locked, onSelect, onShow }: { queue: Queue; selectedDecision: string | null; locked: boolean; onSelect: (customer: string | null, decision: string, invoice: string | null) => void; onShow: () => void }) {
  const { t } = useI18n();
  const rows = negotiationRows(queue);
  return (
    <aside aria-label={t("deals.rail.label")} className="flow-card flex w-[72px] flex-col items-center gap-2 px-1.5 py-3" data-testid="queue-rail">
      <button type="button" onClick={onShow} className="motion-press hit inline-flex min-h-11 w-full items-center justify-center rounded-control px-1 text-center text-supporting font-bold leading-tight text-brand-700 underline underline-offset-2 hover:bg-brand-50" data-testid="queue-rail-show">
        {t("deals.rail.show")}
      </button>
      <ul className="flex w-full flex-col items-center gap-1.5" aria-label={t("deals.list")}>
        {rows.map(({ tier, row }) => {
          const target = rowTarget(row);
          const decision = rowDecision(row);
          const pill = rowPill(tier, row);
          const selected = Boolean(selectedDecision) && decision === selectedDecision;
          const initial = (row.customer_short ?? row.subject_text).trim().charAt(0).toUpperCase();
          const name = [row.subject_text, pill.text].filter(Boolean).join(", ");
          return (
            <li key={row.key} className="w-full" data-testid="queue-rail-row" data-selected={selected ? "true" : "false"} data-lifecycle={pill.lifecycle ?? undefined}>
              <button
                type="button"
                aria-label={name}
                aria-current={selected ? "true" : undefined}
                title={name}
                disabled={locked || target.kind !== "select"}
                onClick={() => target.kind === "select" && onSelect(target.customer, target.decision, target.invoice)}
                className={`motion-press relative grid min-h-11 w-full place-items-center rounded-[14px] py-2 font-display text-base font-extrabold text-ink touch:min-h-11 ${selected ? "bg-f-purple-soft shadow-[inset_0_0_0_1px_var(--color-f-purple)]" : "hover:bg-panel"}`}
                data-testid="queue-rail-select"
              >
                {initial}
                <span aria-hidden className={`absolute right-1.5 top-1.5 size-2.5 rounded-pill ${DOT[pill.tone]}`} data-testid="queue-rail-dot" data-tone={pill.tone} />
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
