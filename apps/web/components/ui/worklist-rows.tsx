"use client";

import Link from "next/link";
import { useRef, type KeyboardEvent, type MouseEventHandler, type ReactNode } from "react";
import { nextTabIndex } from "@/components/ui/segmented-tabs-model";

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
 * The worklist's filters as the mockup's: text tabs, the chosen one a white pill (the count beside each label at 13 px in neutral text; colour is for the status pill only). A tablist:
 * one tab stop, arrow keys, Home and End move and the choice follows the focus.
 */
export function UnderlineTabs<T extends string>({ label, value, onChange, tabs }: { label: string; value: T; onChange: (v: T) => void; tabs: UnderlineTab<T>[] }) {
  const track = useRef<HTMLDivElement>(null);
  const selected = tabs.findIndex((t) => t.value === value);
  const els = () => Array.from(track.current?.querySelectorAll<HTMLButtonElement>("[role=tab]") ?? []);
  const onKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const to = nextTabIndex(e.key, i, tabs.map(() => ({})));
    if (to === null) return;
    e.preventDefault();
    if (to !== i) onChange(tabs[to].value);
    els()[to]?.focus();
  };
  return (
    <div ref={track} role="tablist" aria-label={label} className="flex flex-wrap gap-1">
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
            className={`motion-press inline-flex h-10 items-center gap-1.5 whitespace-nowrap rounded-pill px-3.5 text-[15px] font-medium transition-colors duration-(--dur-fast) hover:text-ink touch:h-11 ${on ? "bg-card text-ink shadow-f" : "text-ink-3"}`}
          >
            {t.label}
            <span className={`text-supporting tabular-nums ${on ? "text-ink" : "text-ink-3"}`} data-testid={t.countTestId}>
              {t.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** The search: an icon, the field and one bottom hairline (no box). */
export function WorklistSearch({ value, onChange, label, testId, found, foundTestId }: { value: string; onChange: (v: string) => void; label: string; testId?: string; found?: string; foundTestId?: string }) {
  return (
    <div className="flex h-10 min-w-0 items-center gap-2 border-b border-line-ui px-0.5 text-ink-3 focus-within:border-ink">
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
        <b className="font-bold text-ink">{eyebrow}</b> <span aria-hidden className="text-ink-3">·</span> {text}
      </p>
      <div className="mt-0.5">{action}</div>
      {note}
    </div>
  );
}

/**
 * One row of the worklist table (a white 16 px row on the panel): a link that opens its item. Columns from `md`: the subject (15 px, with a quoted differentiator under it when the
 * server sends one for two alike subjects), the next step (the server's consequence, 14 px muted) and the status pill at the right; on a phone the subject and the pill share the first
 * line and the next step sits under the subject. Selected is the lavender fill with a purple hairline. `severity` is the screen-reader word (the pill carries the status for the eye).
 */
export function WorklistRow({
  href,
  selected,
  subject,
  isNew,
  newLabel,
  qualifier,
  nextStep,
  pill,
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
  nextStep?: string | null;
  pill?: ReactNode;
  severity?: ReactNode;
  /** Under the row's lines (the reason the first row is first). */
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
        className={`motion-press relative grid grid-cols-1 items-center gap-x-4 gap-y-1.5 rounded-[16px] px-4 py-3.5 outline-offset-0 focus-visible:outline-2 focus-visible:outline-focus md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(7.5rem,auto)] ${
          selected ? "bg-brand-50 ring-1 ring-f-purple" : "bg-card hover:shadow-f hover:ring-1 hover:ring-line"
        }`}
      >
        <span className="min-w-0 text-[15px] font-medium leading-snug text-ink">
          {subject}
          {isNew && newLabel ? (
            <span className="ml-2 text-supporting font-semibold text-ink-2" data-testid="home-row-new">
              {newLabel}
            </span>
          ) : null}
          {qualifier ? (
            <span className="mt-0.5 block text-supporting font-normal italic text-ink-3" data-testid="hv2-row-qualifier">
              “{qualifier}”
            </span>
          ) : null}
        </span>
        {nextStep ? <span className="min-w-0 text-supporting text-ink-3 md:text-sm">{nextStep}</span> : <span className="hidden md:block" />}
        <span className="flex min-w-0 items-center justify-start">{pill}</span>
        {severity}
        {after ? <span className="col-span-full mt-1 block">{after}</span> : null}
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
