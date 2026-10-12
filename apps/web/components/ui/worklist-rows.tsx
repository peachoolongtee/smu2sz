"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, type KeyboardEvent, type MouseEventHandler, type ReactNode } from "react";
import { nextTabIndex } from "@/components/ui/segmented-tabs-model";
import { useReducedMotion } from "@/lib/use-reduced-motion";

export interface UnderlineTab<T extends string> {
  value: T;
  label: string;
  /** The count, in neutral text beside the label; "0" is an answer. */
  count: number;
  /** A tab's own hint is its `title` (it is not a line on the page). */
  title?: string;
  testId?: string;
  countTestId?: string;
  id?: string;
  controls?: string;
}

/**
 * The worklist's filters as an inbox's: text tabs on a hairline, a 2 px ink underline that slides to the chosen one (`--dur`, `--ease-select`; none under reduced motion), the
 * count beside each label at 13 px in neutral text (colour is for severity only). A tablist: one tab stop, arrow keys, Home and End move and the choice follows the focus.
 */
export function UnderlineTabs<T extends string>({ label, value, onChange, tabs }: { label: string; value: T; onChange: (v: T) => void; tabs: UnderlineTab<T>[] }) {
  const reduced = useReducedMotion();
  const track = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLSpanElement>(null);
  const selected = tabs.findIndex((t) => t.value === value);
  const els = () => Array.from(track.current?.querySelectorAll<HTMLButtonElement>("[role=tab]") ?? []);
  const measure = () => {
    const el = els()[selected];
    const b = bar.current;
    if (el && b) {
      b.style.width = `${el.offsetWidth}px`;
      b.style.transform = `translateX(${el.offsetLeft}px)`;
    }
  };
  useLayoutEffect(measure);
  useEffect(() => {
    const t = track.current;
    if (!t || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(t);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);
  const onKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const to = nextTabIndex(e.key, i, tabs.map(() => ({})));
    if (to === null) return;
    e.preventDefault();
    if (to !== i) onChange(tabs[to].value);
    els()[to]?.focus();
  };
  return (
    <div ref={track} role="tablist" aria-label={label} className="relative flex gap-5 border-b border-line">
      {tabs.map((t, i) => {
        const on = i === selected;
        return (
          <button
            key={t.value}
            type="button"
            role="tab"
            id={t.id}
            aria-selected={on}
            aria-controls={t.controls}
            tabIndex={on ? 0 : -1}
            title={t.title}
            data-testid={t.testId}
            onClick={() => onChange(t.value)}
            onKeyDown={(e) => onKey(e, i)}
            className={`inline-flex h-10 items-center gap-1.5 whitespace-nowrap rounded-control text-sm font-bold transition-colors duration-(--dur-fast) hover:text-ink touch:h-11 ${on ? "text-ink" : "text-ink-3"}`}
          >
            {t.label}
            <span className={`text-supporting font-bold tabular-nums ${on ? "text-ink-2" : "text-ink-3"}`} data-testid={t.countTestId}>
              {t.count}
            </span>
          </button>
        );
      })}
      <span
        ref={bar}
        aria-hidden
        className={`pointer-events-none absolute -bottom-px left-0 h-0.5 rounded-pill bg-ink ${reduced ? "" : "transition-[transform,width] duration-(--dur) ease-select"} ${selected < 0 ? "opacity-0" : ""}`}
      />
    </div>
  );
}

/** The search: an icon, the field and one bottom hairline (no box). */
export function WorklistSearch({ value, onChange, label, testId, found, foundTestId }: { value: string; onChange: (v: string) => void; label: string; testId?: string; found?: string; foundTestId?: string }) {
  return (
    <div className="mt-2 flex h-10 items-center gap-2 border-b border-line px-0.5 text-ink-3 focus-within:border-line-ui">
      <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden className="shrink-0">
        <circle cx="7" cy="7" r="4.75" />
        <path d="m10.6 10.6 3 3" />
      </svg>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        placeholder={label}
        className="h-full min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
        data-testid={testId}
      />
      {found !== undefined ? (
        <span className="sr-only" role="status" aria-live="polite" data-testid={foundTestId}>
          {found}
        </span>
      ) : null}
    </div>
  );
}

/** The company alert, as one line with a 2 px bad-tone rule: its eyebrow and sentence, then the way to act on it. `describedBy` names what it is, for a reader who asks. */
export function WorklistAlertLine({ tone, eyebrow, text, action, describedBy, note, testId }: { tone: "bad" | "warn"; eyebrow: string; text: string; action: ReactNode; describedBy?: string; note?: ReactNode; testId?: string }) {
  return (
    <div role="group" aria-label={eyebrow} aria-describedby={describedBy} data-testid={testId} data-tone={tone} className={`mt-3 border-l-2 py-0.5 pl-3 text-sm text-ink-2 ${tone === "bad" ? "border-bad-solid" : "border-warn-solid"}`}>
      <p className="text-pretty">
        <b className="font-bold text-ink">{eyebrow}.</b> {text}
      </p>
      <div className="mt-0.5">{action}</div>
      {note}
    </div>
  );
}

/**
 * One row of the inbox: a link that opens its item (padding 14 and 10, radius 10, the canvas on hover). The subject is 15 px 700, the status 13 px ink-2, the consequence 13 px
 * ink-3 (never the 12 px metadata size: they qualify a figure); `qualifier` is the italic quoted line that tells two alike subjects apart. The severity is the dot and its word
 * at the right (CAUTION and CRITICAL only). Selected is the `brand-50` fill with a 2 px brand rule on the left and the focus ring when focused. Dividers are inset to the text
 * and hide beside the selected row.
 */
export function WorklistRow({
  href,
  selected,
  subject,
  isNew,
  newLabel,
  qualifier,
  status,
  consequence,
  severity,
  after,
  onClick,
  testId,
  data,
}: {
  href: string;
  selected?: boolean;
  subject: string;
  isNew?: boolean;
  newLabel?: string;
  qualifier?: string | null;
  status?: string | null;
  consequence?: string | null;
  severity?: ReactNode;
  /** Under the three lines (the reason the first row is first). */
  after?: ReactNode;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
  testId?: string;
  data?: Record<string, string>;
}) {
  return (
    <li data-testid={testId} {...data} className="relative">
      <Link
        href={href}
        scroll={false}
        aria-current={selected ? "true" : undefined}
        onClick={onClick}
        className={`motion-press relative -mx-3.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-2.5 rounded-tile px-3.5 py-3 outline-offset-0 hover:bg-surface focus-visible:outline-2 focus-visible:outline-brand-600 ${selected ? "bg-brand-50 hover:bg-brand-50 before:absolute before:inset-y-2.5 before:left-0 before:w-0.5 before:rounded-pill before:bg-brand-600" : ""}`}
      >
        <span className="min-w-0 text-[15px] font-bold leading-snug text-ink">
          {subject}
          {isNew && newLabel ? (
            <span className="ml-2 text-supporting font-semibold text-brand-700" data-testid="home-row-new">
              {newLabel}
            </span>
          ) : null}
        </span>
        <span className="row-start-1 col-start-2 self-center">{severity}</span>
        {qualifier ? <span className="col-start-1 text-supporting italic text-ink-3" data-testid="hv2-row-qualifier">“{qualifier}”</span> : null}
        {status ? <span className="col-start-1 text-supporting text-ink-2">{status}</span> : null}
        {consequence ? <span className="col-start-1 text-supporting text-ink-3">{consequence}</span> : null}
        {after ? <span className="col-span-2 mt-1.5 block">{after}</span> : null}
      </Link>
    </li>
  );
}

/** Nothing to do: a short title and one line, with room above it. */
export function WorklistEmpty({ title, body, testId }: { title: string; body?: string | null; testId?: string }) {
  return (
    <div className="py-8" data-testid={testId}>
      <h3 className="font-display text-base font-bold text-ink">{title}</h3>
      {body ? <p className="mt-1 text-sm text-ink-3">{body}</p> : null}
    </div>
  );
}
