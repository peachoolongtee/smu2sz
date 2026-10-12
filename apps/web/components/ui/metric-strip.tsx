"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { InfoIcon } from "@/components/ui/info-icon";

/** The value's colour is its meaning: the plain ink, the bad tone below the minimum, the planned (brand) tone for funding that is only planned, green above a minimum. */
export type MetricTone = "ink" | "bad" | "plan" | "ok" | "warn";
const VALUE_TONE: Record<MetricTone, string> = { ink: "text-ink", bad: "text-bad-fg", plan: "text-brand-600", ok: "text-ok-fg", warn: "text-warn-fg" };

/**
 * Three company values on one line: hairlines above, below and between the cells, no card. A phone gives the first cell the whole width and the other two a column each.
 * Each cell is one rhythm: a label, the figure, one note; a second sentence is behind the cell's own info control.
 */
export function MetricStrip({ label, children, testId }: { label: string; children: ReactNode; testId?: string }) {
  return (
    <div role="group" aria-label={label} data-testid={testId} className="grid grid-cols-2 border-y border-line md:grid-cols-3">
      {children}
    </div>
  );
}

/**
 * One cell. `value` is the server's string in the display face at 32 px (28 and 22 on a phone), tabular figures. `info` is a sentence the owner can ask for: a 20 px control
 * opens it in a popover (`--shadow-pop`, radius 14, a fade over `--dur`, Escape or a press elsewhere closes it, focus stays on the control). `children` are the cell's own
 * lines (the buffer scale, the "with plan" figure).
 */
export function Metric({
  id,
  label,
  labelMark,
  value,
  tone = "ink",
  note,
  info,
  infoLabel,
  children,
  testId,
}: {
  id: string;
  label: string;
  /** A glyph before the label (the planned state's dashed ring). */
  labelMark?: ReactNode;
  value: string;
  tone?: MetricTone;
  note?: string | null;
  info?: string | null;
  infoLabel: string;
  children?: ReactNode;
  testId?: string;
}) {
  const uid = useId();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);
  return (
    <div
      ref={root}
      data-testid={testId ?? `hv2-metric-${id}`}
      className="group relative min-w-0 py-3 pr-4 first:col-span-2 first:border-b first:border-line first:pl-0 max-md:nth-[3]:pl-3 md:border-l md:border-line md:px-5 md:py-5 md:first:col-span-1 md:first:border-b-0 md:first:border-l-0 md:first:pl-0"
    >
      <div className="flex items-center gap-1">
        <p id={`${uid}-label`} className="flex items-center gap-1.5 text-supporting font-bold text-ink-3" data-testid={`hv2-metric-${id}-label`}>
          {labelMark}
          {label}
        </p>
        {info ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={`${uid}-info`}
            aria-label={infoLabel}
            onClick={() => setOpen((o) => !o)}
            onKeyDown={(e) => {
              if (e.key === "Escape" && open) {
                e.stopPropagation();
                setOpen(false);
              }
            }}
            className={`motion-press grid size-5 shrink-0 place-items-center rounded-pill hover:bg-brand-50 hover:text-brand-600 ${open ? "bg-brand-50 text-brand-600" : "text-ink-3"}`}
            data-testid={`hv2-metric-${id}-info`}
          >
            <InfoIcon className="size-3.5" />
          </button>
        ) : null}
      </div>
      <p className={`mt-1 whitespace-nowrap font-display text-[22px] font-bold leading-tight tabular-nums tracking-[-0.02em] group-first:text-[28px] md:mt-2 md:text-[32px] md:group-first:text-[32px] ${VALUE_TONE[tone]}`} data-testid={`home-kpi-${id}-value`}>
        {value}
      </p>
      {note ? (
        <p className="mt-1 text-pretty text-supporting text-ink-2 md:mt-1.5 md:text-sm" data-testid={`home-kpi-${id}-note`}>
          {note}
        </p>
      ) : null}
      {children}
      {info ? (
        <div
          id={`${uid}-info`}
          role="note"
          hidden={!open}
          className="motion-reveal absolute left-0 top-full z-20 mt-1 w-[min(20rem,calc(100vw-2.5rem))] rounded-card bg-surface px-4 py-3.5 text-sm text-ink-2 shadow-pop md:left-5 md:first:left-0"
          data-testid={`hv2-metric-${id}-pop`}
        >
          {info}
        </div>
      ) : null}
    </div>
  );
}
