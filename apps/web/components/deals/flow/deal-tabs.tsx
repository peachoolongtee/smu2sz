"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { nextTabIndex } from "@/components/ui/segmented-tabs-model";
import type { DealViewKey } from "./deal-model";

/**
 * The selected deal's tabs, on one line (round three, section 7): text tabs, the chosen one a filled pill. A tablist (one tab stop, the arrow keys, Home and End), each tab the id the
 * panel it controls names. The labels are the dictionary's; a count would be the server's, so none is drawn. Where the four do not fit (a phone) the row scrolls sideways and says so: an edge
 * fades on the side that has more, and the chosen tab is kept in view.
 */
export function DealTabs({ label, tabs, value, onChange, idPrefix }: { label: string; tabs: { value: DealViewKey; label: string }[]; value: DealViewKey; onChange: (v: DealViewKey) => void; idPrefix: string }) {
  const track = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  const selected = tabs.findIndex((t) => t.value === value);
  const measure = () => {
    const el = track.current;
    if (!el) return;
    setEdges({ left: el.scrollLeft > 2, right: el.scrollLeft + el.clientWidth < el.scrollWidth - 2 });
  };
  useEffect(() => {
    const el = track.current;
    if (!el) return;
    // The chosen tab is kept in view (by this row's own scroll; the page does not move).
    const tab = el.querySelectorAll<HTMLElement>("[role=tab]")[selected];
    if (tab) el.scrollTo({ left: Math.max(0, tab.offsetLeft - (el.clientWidth - tab.offsetWidth) / 2), behavior: "auto" });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [selected, tabs.length]);
  const onKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const to = nextTabIndex(e.key, i, tabs.map(() => ({})));
    if (to === null) return;
    e.preventDefault();
    if (to !== i) onChange(tabs[to].value);
    requestAnimationFrame(() => track.current?.querySelectorAll<HTMLButtonElement>("[role=tab]")[to]?.focus());
  };
  const fade = edges.left || edges.right ? `linear-gradient(to right, ${edges.left ? "transparent, #000 28px" : "#000, #000 0"}, ${edges.right ? "#000 calc(100% - 28px), transparent" : "#000 100%, #000"})` : undefined;
  return (
    <div
      ref={track}
      role="tablist"
      aria-label={label}
      onScroll={measure}
      className="-mx-2 mt-3 flex gap-1 overflow-x-auto border-t border-line py-2 max-md:mt-0 max-md:border-t-0 max-md:py-1.5"
      style={fade ? { maskImage: fade, WebkitMaskImage: fade } : undefined}
      data-testid="deal-tabs"
      data-more-left={edges.left ? "true" : undefined}
      data-more-right={edges.right ? "true" : undefined}
    >
      {tabs.map((tab, i) => {
        const on = i === selected;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${tab.value}`}
            aria-selected={on}
            aria-controls={`${idPrefix}-panel-${tab.value}`}
            tabIndex={on ? 0 : -1}
            data-testid={`deal-tab-${tab.value}`}
            onClick={() => onChange(tab.value)}
            onKeyDown={(e) => onKey(e, i)}
            className={`motion-press inline-flex h-10 shrink-0 items-center whitespace-nowrap rounded-pill px-3.5 text-[15px] font-medium transition-colors duration-(--dur-fast) hover:text-ink touch:h-11 ${on ? "bg-subtle font-bold text-ink" : "text-ink-3"}`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
