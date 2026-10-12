"use client";

import Link from "next/link";
import { AlertIcon, CheckIcon, ClockIcon, UserIcon } from "@/components/icons";
import { type Tone } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import { SegmentedTabs, type TabIcon } from "@/components/ui/segmented-tabs";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { QUEUE_TABS, type QueueTab } from "./model";

/** The small-caps label of a tile, a column and an aside: 13 px, the page's one eyebrow style. */
export const eyebrowCls = "text-supporting font-extrabold uppercase tracking-[0.06em]";

/** One line of the list, every word already said: the page builds it from the server's reads and the dictionary, the list only lays it out. */
export interface ListItem {
  key: string;
  customer: string;
  customerHref: string;
  request: string;
  /** The cost as asked, the server's figure and its window; empty for a line that has none. */
  cost: string;
  costTone: "bad" | "neutral";
  recommends: string;
  status: string;
  statusTone: Tone;
  /** The record's state, when the line is the open deal and the record is read: the status pill then carries it (`data-state`). */
  statusState: string | null;
  selected: boolean;
}

/** One glyph per tab: the owner's reply, a reply out with a buyer, an agreement in force, a customer to set up. */
const TAB_ICON: Record<QueueTab, TabIcon> = { needs: AlertIcon, wait: ClockIcon, agreed: CheckIcon, setup: UserIcon };

/**
 * The four tabs of the queue, a SegmentedTabs tablist (arrow keys move between them, the selected one is `aria-selected`): an icon, the label and the count
 * in a badge, red only on the tab that needs the owner's reply and only while it holds one. It fills the width from `sm` and scrolls sideways on a phone (the open tab
 * scrolled into view). The list they filter keeps its five columns from `lg`, and below it a line is its customer and status, the request, then the cost and what FLOW
 * recommends.
 */
export function QueueTabs({ counts, tab, onTab }: { counts: Record<QueueTab, number>; tab: QueueTab; onTab: (t: QueueTab) => void }) {
  const { t } = useI18n();
  return (
    <SegmentedTabs
      label={t("dq.tabs")}
      value={tab}
      onChange={onTab}
      stretch
      scroll
      testId="queue-tabs"
      tabs={QUEUE_TABS.map((k) => ({
        value: k,
        label: t(`dq.tab.${k}` as DictKey),
        icon: TAB_ICON[k],
        badge: counts[k],
        badgeTone: k === "needs" && counts[k] > 0 ? "alert" : "neutral",
        id: `dq-tab-${k}`,
        controls: "dq-list",
        testId: `queue-tab-${k}`,
        badgeTestId: `queue-count-${k}`,
      }))}
    />
  );
}

const COLS = "lg:grid-cols-[1.3fr_1.6fr_1fr_1.2fr_1fr]";

/** The list of the open tab. Every line selects (its request is the button) and its customer is always a link. */
export function QueueList({ tab, items, emptyText }: { tab: QueueTab; items: (ListItem & { select: () => void })[]; emptyText: string }) {
  const { t } = useI18n();
  return (
    <section id="dq-list" role="tabpanel" aria-labelledby={`dq-tab-${tab}`} className="overflow-hidden rounded-card border border-line bg-surface" data-testid="queue-list">
      <div role="table" aria-label={t("dq.list")}>
        <div role="row" className={`hidden gap-3 border-b border-line px-4 py-2.5 lg:grid short:sr-only ${COLS} ${eyebrowCls} text-ink-3`}>
          {(["customer", "request", "cost", "rec", "status"] as const).map((c) => (
            <span key={c} role="columnheader">
              {t(`dq.col.${c}` as DictKey)}
            </span>
          ))}
        </div>
        {items.length === 0 ? (
          <p className="px-4 py-4 text-sm text-ink-3" data-testid="queue-empty">
            {emptyText}
          </p>
        ) : (
          items.map((it) => (
            <div
              key={it.key}
              role="row"
              aria-current={it.selected ? "true" : undefined}
              data-testid="queue-row"
              data-selected={it.selected ? "true" : "false"}
              onClick={(e) => {
                if (!(e.target as HTMLElement).closest("a,button")) it.select();
              }}
              className={`relative grid cursor-pointer grid-cols-2 items-center gap-x-3 gap-y-0.5 border-t border-line px-4 py-2 text-sm first:border-t-0 sm:py-3 short:py-2 lg:gap-3 ${COLS} ${it.selected ? "bg-brand-50/60 before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-brand-600" : "hover:bg-subtle"} transition-colors duration-(--dur)`}
            >
              <span role="cell" className="min-w-0 font-bold max-lg:col-span-1 lg:col-start-1 lg:row-start-1">
                <Link href={it.customerHref} className="inline-flex min-h-8 max-w-full items-center text-ink underline-offset-2 hover:text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-customer">
                  <span className="max-lg:truncate">{it.customer}</span>
                </Link>
              </span>
              <span role="cell" className="min-w-0 justify-self-end lg:col-start-5 lg:row-start-1 lg:justify-self-start">
                <span data-testid={it.statusState ? "deal-state-chip" : undefined} data-state={it.statusState ?? undefined}>
                  <StateWord tone={it.statusTone} wrap={false} >{it.status}</StateWord>
                </span>
              </span>
              {/* On a phone the selected line gives its request to the detail right below (the ask sentence says it in full), which brings the primary up the screen. */}
              <span role="cell" className={`col-span-2 min-w-0 lg:col-span-1 lg:col-start-2 lg:row-start-1 ${it.selected ? "max-lg:hidden" : ""}`}>
                <button type="button" onClick={it.select} className="motion-press min-h-8 w-full rounded-pill text-left text-ink first-letter:uppercase focus-visible:underline" data-testid="queue-select">
                  <span className="block max-lg:truncate">{it.request}</span>
                </button>
              </span>
              <span role="cell" className={`lg:col-start-3 lg:row-start-1 ${it.costTone === "bad" ? "font-bold text-bad-fg" : it.cost ? "font-bold" : "text-ink-3"}`}>
                {it.cost || "—"}
              </span>
              <span role="cell" className="min-w-0 font-bold lg:col-start-4 lg:row-start-1">
                {it.recommends}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
