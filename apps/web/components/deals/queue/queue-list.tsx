"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
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
  /** The record's state, when the line is the open deal and the record is read: the status pill then carries it (`data-state`). */
  statusState: string | null;
  selected: boolean;
}

/**
 * The four count tiles as the queue's tabs (a tablist: arrow keys move between them, the selected one is `aria-selected`, with a bar under it as well as a weight and a tint)
 * and the list they filter. The tiles are a horizontal scroll of pills on a phone (the open one scrolled into view) and a row of four from `sm`; the list keeps its five
 * columns from `lg`, and below it a line is its customer and status, the request, then the cost and what FLOW recommends.
 */
export function QueueTabs({ counts, tab, onTab }: { counts: Record<QueueTab, number>; tab: QueueTab; onTab: (t: QueueTab) => void }) {
  const { t } = useI18n();
  const group = useRef<HTMLDivElement>(null);
  useEffect(() => {
    group.current?.querySelector<HTMLElement>("[aria-selected=true]")?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [tab]);
  const move = (from: number, by: number) => {
    const next = QUEUE_TABS[(from + by + QUEUE_TABS.length) % QUEUE_TABS.length];
    onTab(next);
    group.current?.querySelectorAll<HTMLButtonElement>("[role=tab]")[QUEUE_TABS.indexOf(next)]?.focus();
  };
  return (
    <div ref={group} role="tablist" aria-label={t("dq.tabs")} className="-mx-4 -my-1.5 flex gap-2 overflow-x-auto px-4 py-1.5 sm:mx-0 sm:my-0 sm:grid sm:grid-cols-4 sm:overflow-visible sm:p-0" data-testid="queue-tabs">
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
            className={`motion-press flex min-h-14 shrink-0 flex-col items-start justify-center rounded-card border px-4 py-2 text-left transition-colors duration-(--dur) max-sm:min-h-11 max-sm:flex-row max-sm:items-center max-sm:gap-2.5 max-sm:rounded-pill max-sm:px-3.5 max-sm:py-1 short:min-h-11 short:flex-row short:items-center short:gap-2.5 short:py-1 touch:min-h-11 sm:touch:min-h-14 ${on ? "border-brand-600 border-b-[3px] bg-brand-50" : "border-line bg-surface hover:bg-subtle"}`}
          >
            <span className={`${eyebrowCls} ${k === "needs" ? "text-warn-fg" : "text-ink-3"} ${on ? "text-ink" : ""}`}>{t(`dq.tab.${k}` as DictKey)}</span>
            <span className={`font-display text-xl tabular-nums text-ink max-sm:text-base short:text-base ${on ? "font-black" : "font-extrabold"}`} data-testid={`queue-count-${k}`}>
              {counts[k]}
            </span>
          </button>
        );
      })}
    </div>
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
                  <StatePill tone={it.statusTone} wrap={false} className="!text-[0.8125rem]">{it.status}</StatePill>
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
