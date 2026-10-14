"use client";

import { useRef, type KeyboardEvent } from "react";
import { nextTabIndex } from "@/components/ui/segmented-tabs-model";
import type { DealViewKey } from "./deal-model";

/**
 * The selected deal's tabs, on one line (round three, section 7): text tabs, the chosen one a filled pill. A tablist (one tab stop, the arrow keys, Home and End), each tab the id the
 * panel it controls names. The labels are the dictionary's; a count would be the server's, so none is drawn.
 */
export function DealTabs({ label, tabs, value, onChange, idPrefix }: { label: string; tabs: { value: DealViewKey; label: string }[]; value: DealViewKey; onChange: (v: DealViewKey) => void; idPrefix: string }) {
  const track = useRef<HTMLDivElement>(null);
  const selected = tabs.findIndex((t) => t.value === value);
  const onKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const to = nextTabIndex(e.key, i, tabs.map(() => ({})));
    if (to === null) return;
    e.preventDefault();
    if (to !== i) onChange(tabs[to].value);
    requestAnimationFrame(() => track.current?.querySelectorAll<HTMLButtonElement>("[role=tab]")[to]?.focus());
  };
  return (
    <div ref={track} role="tablist" aria-label={label} className="-mx-2 mt-3 flex gap-1 overflow-x-auto border-t border-line py-2" data-testid="deal-tabs">
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
            className={`motion-press inline-flex h-10 items-center whitespace-nowrap rounded-pill px-3.5 text-[15px] font-medium transition-colors duration-(--dur-fast) hover:text-ink touch:h-11 ${on ? "bg-subtle font-bold text-ink" : "text-ink-3"}`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
