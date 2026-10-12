"use client";

import { useEffect, useRef, type ComponentType, type KeyboardEvent, type ReactNode } from "react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { BADGE_CLASS, badgeShown, nextTabIndex, tabAttrs, type BadgeTone } from "./segmented-tabs-model";

export type TabIcon = ComponentType<{ className?: string }>;

export interface SegmentedTabOption<T extends string | number> {
  value: T;
  label: ReactNode;
  /** A glyph from components/icons.tsx, before the label. */
  icon?: TabIcon;
  /** A count (or a short word) in a small filled circle after the label; hidden when null. */
  badge?: string | number | null;
  /** Red only for a count that needs the owner; neutral for any other. */
  badgeTone?: BadgeTone;
  /** Nothing behind this tab: shown dimmed, not reachable by the arrow keys. */
  disabled?: boolean;
  testId?: string;
  badgeTestId?: string;
  /** The tab's own id and the panel it controls, for a tablist that has a tabpanel. */
  id?: string;
  controls?: string;
}

/**
 * The one segmented control (the owner's reference: a pill track, a raised selected pill, an icon and a label on each, an optional count badge), light:
 * a `#eef1f5` track, a white selected pill with the hairline and a 1 px shadow, `ink` text on it and `ink-2` on the rest.
 *
 * It is a tablist: `role="tab"` and `aria-selected` on each option, one tab stop (the selected one) and the arrow keys, Home and End to move; the selection
 * follows the focus (choosing is cheap here: a filter, a window, a scenario, a queue). The pill slides between the options on `transform` alone (`--dur-fast`,
 * `--ease-select`; none under reduced motion). The options share one width (the widest) so the pill is one option wide; where they do not fit the track scrolls
 * sideways and keeps the selected tab in view. Each tab is 44 px tall.
 */
export function SegmentedTabs<T extends string | number>({
  label,
  value,
  onChange,
  tabs,
  stretch = false,
  scroll = false,
  className = "",
  testId,
}: {
  /** The tablist's accessible name. */
  label: string;
  value: T;
  onChange: (v: T) => void;
  tabs: SegmentedTabOption<T>[];
  /** Fill the width of the parent (the queue's four tabs); the default is as narrow as the options allow. */
  stretch?: boolean;
  /** Keep every label on one line and let the track scroll sideways where it does not fit (the queue's four tabs on a phone); the default shrinks the options and wraps a long label on a phone (one line from `sm`). */
  scroll?: boolean;
  className?: string;
  testId?: string;
}) {
  const reduced = useReducedMotion();
  const list = useRef<HTMLDivElement>(null);
  const selected = tabs.findIndex((o) => o.value === value);

  // Keep the chosen tab in view when the track scrolls (a phone); a track that fits does not move.
  useEffect(() => {
    const el = list.current;
    if (!el || el.scrollWidth <= el.clientWidth) return;
    el.querySelector<HTMLElement>("[aria-selected=true]")?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selected]);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const to = nextTabIndex(e.key, i, tabs);
    if (to === null) return;
    e.preventDefault();
    if (to !== i) onChange(tabs[to].value);
    list.current?.querySelectorAll<HTMLButtonElement>("[role=tab]")[to]?.focus();
  };

  return (
    <div className={`${stretch ? "w-full" : "max-w-full"} ${scroll ? "overflow-x-auto" : ""} p-1 -m-1 ${className}`} ref={list} data-testid={testId}>
      <div
        role="tablist"
        aria-label={label}
        className={`relative grid auto-cols-fr grid-flow-col rounded-pill bg-track p-0.5 ${scroll ? "min-w-max" : "max-w-full"} ${stretch ? "" : "w-max"}`}
        style={{ ["--n" as string]: tabs.length }}
      >
        <span
          aria-hidden
          className={`pointer-events-none absolute inset-y-0.5 left-0.5 w-[calc((100%-0.25rem)/var(--n))] rounded-pill border border-line bg-surface shadow-pill ${reduced ? "" : "transition-transform duration-(--dur-fast) ease-select"} ${selected < 0 ? "opacity-0" : ""}`}
          style={{ transform: `translateX(${Math.max(selected, 0) * 100}%)` }}
        />
        {tabs.map((o, i) => {
          const on = i === selected;
          const Icon = o.icon;
          return (
            <button
              key={String(o.value)}
              type="button"
              {...tabAttrs(i, selected, tabs)}
              data-testid={o.testId}
              onClick={() => onChange(o.value)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={`relative z-10 flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-pill px-3 text-center text-sm font-semibold leading-tight sm:px-4 ${scroll ? "whitespace-nowrap" : "sm:whitespace-nowrap"} transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${on ? "text-ink" : "text-ink-2 enabled:hover:text-ink"}`}
            >
              {Icon ? <Icon className="size-4 shrink-0" /> : null}
              <span className="min-w-0">{o.label}</span>
              {badgeShown(o.badge) ? (
                <span
                  data-testid={o.badgeTestId}
                  data-tone={o.badgeTone ?? "neutral"}
                  className={`grid h-5 min-w-5 place-items-center rounded-pill px-1.5 text-supporting font-bold leading-none tabular-nums ${BADGE_CLASS[o.badgeTone ?? "neutral"]}`}
                >
                  {o.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
