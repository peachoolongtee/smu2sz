"use client";

import { useEffect, useLayoutEffect, useRef, type ComponentType, type KeyboardEvent, type ReactNode } from "react";
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
 * a `#eef1f5` track on a `line-ui` hairline, the selected pill in Home's purple (every filter's selected colour) with white words and a 1 px shadow; the selected
 * label is weight 800, the rest 600 in `ink-2`.
 *
 * It is a tablist: `role="tab"` and `aria-selected` on each option, one tab stop (the selected one) and the arrow keys, Home and End to move; the selection
 * follows the focus (choosing is cheap here: a filter, a window, a scenario, a queue). Each option is as wide as its own label (a weight-800 twin reserves the
 * width, so choosing never resizes a tab); a long label wraps to two lines at the same 44 px height, or is cut with its full text as a title, and never
 * stretches its siblings. The pill is measured from the chosen tab and slides to it (`--dur-fast`, `--ease-select`, no overshoot; none under reduced motion);
 * before it is measured the chosen tab draws the pill itself. With `scroll` the track scrolls sideways where it does not fit, fades at the edge that has more
 * and keeps the chosen tab in view by its own `scrollLeft` (never the window's).
 */
export function SegmentedTabs<T extends string | number>({
  label,
  value,
  onChange,
  tabs,
  stretch = false,
  scroll = false,
  compact = false,
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
  /** Keep every label on one line and let the track scroll sideways where it does not fit (the queue's four tabs on a phone). */
  scroll?: boolean;
  /** The small size for a control that sits on a page's content, not at its head: 32 px tall, radius 10, a thin `line-strong` border, a white selected pill with its own border and no shadow, 13 px labels (Home V2's window and scenario). */
  compact?: boolean;
  className?: string;
  testId?: string;
}) {
  const reduced = useReducedMotion();
  const wrap = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const selected = tabs.findIndex((o) => o.value === value);
  const pill = useRef<HTMLSpanElement>(null);
  const mounted = useRef(false);

  const tabEls = () => Array.from(track.current?.querySelectorAll<HTMLButtonElement>("[role=tab]") ?? []);
  // The pill and the edge fades are drawn straight on the DOM from what the browser measured (no state to set from an effect): the pill takes the chosen tab's box,
  // and the track says on `data-pill` that it has one (until then the chosen tab draws the pill itself, globals.css `.seg-track`).
  const measure = () => {
    const el = tabEls()[selected];
    const p = pill.current;
    if (p && el) {
      p.style.width = `${el.offsetWidth}px`;
      p.style.transform = `translateX(${el.offsetLeft}px)`;
      track.current?.setAttribute("data-pill", "");
    }
    const w = wrap.current;
    if (w && scroll) {
      const left = w.scrollLeft > 1;
      const right = w.scrollLeft + w.clientWidth < w.scrollWidth - 1;
      w.dataset.fade = left && right ? "both" : right ? "end" : left ? "start" : "";
    }
  };

  // The pill follows the chosen tab, and the track's own width (a phone turning, a label arriving in another language).
  useLayoutEffect(measure);
  useEffect(() => {
    const t = track.current;
    if (!t || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(t);
    if (wrap.current) ro.observe(wrap.current);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, scroll]);

  // Keep the chosen tab in view by the track's own scroll position (never the page's); the first paint does not move it.
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    const w = wrap.current;
    const el = tabEls()[selected];
    if (!w || !el || w.scrollWidth <= w.clientWidth) return;
    const pad = 12;
    const left = el.offsetLeft + (track.current?.offsetLeft ?? 0);
    if (left - pad < w.scrollLeft) w.scrollLeft = Math.max(0, left - pad);
    else if (left + el.offsetWidth + pad > w.scrollLeft + w.clientWidth) w.scrollLeft = left + el.offsetWidth + pad - w.clientWidth;
  }, [selected]);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const to = nextTabIndex(e.key, i, tabs);
    if (to === null) return;
    e.preventDefault();
    if (to !== i) onChange(tabs[to].value);
    tabEls()[to]?.focus();
  };

  return (
    <div
      ref={wrap}
      onScroll={scroll ? measure : undefined}
      className={`${scroll ? `overflow-x-auto p-1 -m-1 ${stretch ? "w-[calc(100%+0.5rem)]" : "max-w-[calc(100%+0.5rem)]"} seg-scroll` : stretch ? "w-full" : "max-w-full"} ${className}`}
      data-testid={testId}
    >
      <div
        ref={track}
        role="tablist"
        aria-label={label}
        className={`seg-track relative flex border bg-track p-0.5 ${compact ? "rounded-tile border-line-strong" : "rounded-pill border-line-ui"} ${scroll ? "w-max min-w-full" : stretch ? "w-full" : "w-fit max-w-full"}`}
      >
        <span
          ref={pill}
          aria-hidden
          className={`pointer-events-none absolute inset-y-0.5 left-0 border border-f-purple bg-f-purple ${compact ? "rounded-control" : "rounded-pill shadow-pill"} ${reduced ? "" : "transition-[transform,width] duration-(--dur-fast) ease-select"} ${selected < 0 ? "opacity-0" : ""}`}
        />
        {tabs.map((o, i) => {
          const on = i === selected;
          const Icon = o.icon;
          return (
            <button
              key={String(o.value)}
              type="button"
              {...tabAttrs(i, selected, tabs)}
              title={!scroll && typeof o.label === "string" ? o.label : undefined}
              data-testid={o.testId}
              onClick={() => onChange(o.value)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={`seg-tab relative z-10 flex min-w-0 max-w-72 flex-auto cursor-pointer items-center justify-center gap-2 border border-transparent px-3 text-center leading-tight transition-colors duration-(--dur-fast) disabled:cursor-not-allowed disabled:opacity-50 ${compact ? "h-6.5 rounded-control text-supporting" : "min-h-11 rounded-pill text-sm sm:px-4"} ${scroll ? "whitespace-nowrap" : ""} ${
                on ? `font-extrabold text-f-btn-ink ${pill ? "border-transparent" : "border-f-purple bg-f-purple shadow-pill"}` : "border-transparent font-semibold text-ink-2 enabled:hover:text-f-purple-ink"
              }`}
            >
              {Icon ? <Icon className={`size-4 shrink-0 transition-colors duration-(--dur-fast) ${on ? "text-f-btn-ink" : ""}`} /> : null}
              <span
                data-label={typeof o.label === "string" ? o.label : undefined}
                className={`min-w-0 ${scroll ? "" : "max-h-9 overflow-hidden"} after:invisible after:block after:h-0 after:overflow-hidden after:font-extrabold after:content-[attr(data-label)]`}
              >
                {o.label}
              </span>
              {badgeShown(o.badge) ? (
                <span
                  data-testid={o.badgeTestId}
                  data-tone={o.badgeTone ?? "neutral"}
                  className={`grid h-5 min-w-5 shrink-0 place-items-center rounded-pill px-1.5 text-supporting font-bold leading-none tabular-nums ${BADGE_CLASS[o.badgeTone ?? "neutral"]}`}
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
