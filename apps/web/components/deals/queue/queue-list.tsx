"use client";

import Link from "next/link";
import { useRef } from "react";
import { StatePill, type Tone } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { QUEUE_TABS, type QueueTab } from "./model";

/** The small-caps label of a tile, a column and an aside: 13 px, the page's one eyebrow style. */
export const eyebrowCls = "text-[0.8125rem] font-extrabold uppercase tracking-[0.06em]";

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
  /** The offer a click selects; null for a line that is not a request (terms in force, a customer to set up). */
  offerId: string | null;
  selected: boolean;
}

/**
 * The four count tiles as the queue's tabs (a tablist: arrow keys move between them, the selected one is `aria-selected`) and the list they filter.
 * The tiles are a horizontal scroll of pills on a phone and a row of four from `sm`; the list keeps its five columns from `lg` and is two lines per row below.
 */
export function QueueTabs({ counts, tab, onTab }: { counts: Record<QueueTab, number>; tab: QueueTab; onTab: (t: QueueTab) => void }) {
  const { t } = useI18n();
  const group = useRef<HTMLDivElement>(null);
  const move = (from: number, by: number) => {
    const next = QUEUE_TABS[(from + by + QUEUE_TABS.length) % QUEUE_TABS.length];
    onTab(next);
    group.current?.querySelectorAll<HTMLButtonElement>("[role=tab]")[QUEUE_TABS.indexOf(next)]?.focus();
  };
  return (
    <div ref={group} role="tablist" aria-label={t("dq.tabs")} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-4 sm:overflow-visible sm:px-0 sm:pb-0" data-testid="queue-tabs">
      {QUEUE_TABS.map((k, i) => {
        const on = k === tab;
        return (
          <button
            key={k}
            type="button"
            role="tab"
            id={`dq-tab-${k}`}
            aria-selected={on}
            aria-controls="dq-list"
            tabIndex={on ? 0 : -1}
            data-testid={`queue-tab-${k}`}
            onClick={() => onTab(k)}
            onKeyDown={(e) => {
              const by = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
              if (!by) return;
              e.preventDefault();
              move(i, by);
            }}
            className={`motion-press flex min-h-14 shrink-0 flex-col items-start justify-center rounded-card border px-4 py-2 text-left transition-colors duration-(--dur) max-sm:min-h-11 max-sm:flex-row max-sm:items-center max-sm:gap-2.5 max-sm:rounded-pill max-sm:px-3.5 max-sm:py-1 touch:min-h-11 sm:touch:min-h-14 ${on ? "border-brand-600 bg-brand-50" : "border-line bg-surface hover:bg-subtle"}`}
          >
            <span className={`${eyebrowCls} ${k === "needs" ? "text-warn-fg" : "text-ink-3"}`}>{t(`dq.tab.${k}` as DictKey)}</span>
            <span className="font-display text-xl font-extrabold tabular-nums text-ink max-sm:text-base" data-testid={`queue-count-${k}`}>
              {counts[k]}
            </span>
          </button>
        );
      })}
    </div>
  );
}

const COLS = "lg:grid-cols-[1.3fr_1.6fr_1fr_1.2fr_1fr]";

/** The list of the open tab. A line with an offer behind it selects that deal (its request is the button); the customer is always a link. */
export function QueueList({ tab, items, onSelect, emptyText }: { tab: QueueTab; items: ListItem[]; onSelect: (offerId: string) => void; emptyText: string }) {
  const { t } = useI18n();
  return (
    <section id="dq-list" role="tabpanel" aria-labelledby={`dq-tab-${tab}`} className="overflow-hidden rounded-card border border-line bg-surface" data-testid="queue-list">
      <div role="table" aria-label={t("dq.list")}>
        <div role="row" className={`hidden gap-3 border-b border-line px-4 py-2.5 lg:grid ${COLS} ${eyebrowCls} text-ink-3`}>
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
                if (it.offerId && !(e.target as HTMLElement).closest("a,button")) onSelect(it.offerId);
              }}
              className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-t border-line px-4 py-3 text-sm first:border-t-0 lg:gap-3 ${COLS} ${it.offerId ? "cursor-pointer" : ""} ${it.selected ? "border-l-[3px] border-l-brand-600 bg-brand-50/60" : "hover:bg-subtle"} transition-colors duration-(--dur)`}
            >
              <span role="cell" className="min-w-0 font-bold lg:col-auto">
                <Link href={it.customerHref} className="break-words text-ink underline-offset-2 hover:text-brand-700 hover:underline focus-visible:underline" data-testid="queue-customer">
                  {it.customer}
                </Link>
              </span>
              <span role="cell" className="min-w-0 max-lg:order-3 max-lg:col-span-2 lg:col-auto">
                {it.offerId ? (
                  <button type="button" onClick={() => onSelect(it.offerId as string)} className="motion-press min-h-8 w-full rounded-pill text-left text-ink focus-visible:underline max-lg:line-clamp-1 touch:min-h-11" data-testid="queue-select">
                    {it.request}
                    <span className="lg:hidden">
                      {it.cost ? <span className={it.costTone === "bad" ? " font-bold text-bad-fg" : " font-bold"}>{` · ${it.cost}`}</span> : null}
                    </span>
                  </button>
                ) : (
                  <span className={`max-lg:line-clamp-1 ${it.cost ? "" : "text-ink-3"}`}>
                    {it.request}
                    {it.cost ? <span className="lg:hidden font-bold">{` · ${it.cost}`}</span> : null}
                  </span>
                )}
              </span>
              <span role="cell" className={`hidden lg:block ${it.costTone === "bad" ? "font-bold text-bad-fg" : it.cost ? "font-bold" : "text-ink-3"}`}>
                {it.cost || "—"}
              </span>
              <span role="cell" className="hidden font-bold lg:block">
                {it.recommends}
              </span>
              <span role="cell" className="max-lg:order-2 lg:col-auto">
                <StatePill tone={it.statusTone}>{it.status}</StatePill>
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
