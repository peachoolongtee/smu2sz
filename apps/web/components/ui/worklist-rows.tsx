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
export function UnderlineTabs<T extends string>({ label, value, onChange, tabs, dense = false }: { label: string; value: T; onChange: (v: T) => void; tabs: UnderlineTab<T>[]; /** For a narrow card (the Deals queue): tighter padding, and the count a small badge so the tabs keep one line. */ dense?: boolean }) {
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
            className={`motion-press inline-flex h-10 items-center whitespace-nowrap rounded-pill ${dense ? "gap-1 px-1.5 text-sm" : "gap-1.5 px-3.5 text-[15px]"} font-medium transition-colors duration-(--dur-fast) hover:text-ink touch:h-11 ${on ? "bg-card text-ink shadow-f" : "text-ink-3"}`}
          >
            {t.label}
            <span
              className={`text-supporting tabular-nums ${dense ? `inline-grid min-w-[1.125rem] place-items-center rounded-pill px-1 font-semibold leading-[1.125rem] ${on ? "bg-subtle text-ink" : "bg-subtle/60 text-ink-3"}` : on ? "text-ink" : "text-ink-3"}`}
              data-testid={t.countTestId}
            >
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

/** The table's one column template (the header row and every row share it, so they align): Customer / deal 36%, Next step 44%, Status 20% (right-aligned) and the 72 px "Select" column. */
export const WORKLIST_COLUMNS = "lg:grid-cols-[minmax(0,36fr)_minmax(0,44fr)_minmax(14rem,20fr)_72px]";

/**
 * One row of the worklist table (a white 16 px row on the panel): a link that opens its item, a fixed height (56 px from `lg`, 64 px below it) so no two rows differ. From `lg` four fixed columns:
 * the subject (15 px semibold, with the server's quoted differentiator after it at 13 px muted), the next step (13 px muted, ONE line, cut with an ellipsis and whole in `title`), the status pill
 * right-aligned (a long status word wraps inside the pill to a second line, never cut), and the "Select" affordance in its own 72 px column so the pill never moves. Below `lg` the subject and the pill share the first line and the next step is the second.
 * Selected is the lavender fill with a purple hairline. `severity` is the screen-reader word (the pill carries the status for the eye).
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
  selectLabel,
  onWarm,
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
  /** "Select": the affordance that hover and keyboard focus reveal in the row's own last column (a click or Enter selects; hovering changes nothing else on the page). */
  selectLabel?: string;
  /** Called when the pointer rests on the row or focus enters it: the page starts the reads a selection would make, so the selection paints at once. */
  onWarm?: () => void;
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
        onPointerEnter={onWarm}
        onFocus={onWarm}
        data-testid="hv2-row-link"
        className={`group motion-press relative grid h-16 grid-cols-[minmax(0,1fr)_auto] content-center items-center gap-x-4 gap-y-0.5 rounded-[16px] px-4 outline-offset-0 focus-visible:outline-2 focus-visible:outline-focus lg:h-14 ${WORKLIST_COLUMNS} ${
          selected ? "bg-brand-50 ring-1 ring-f-purple" : "bg-card hover:shadow-f hover:ring-1 hover:ring-line"
        }`}
      >
        <span className="flex min-w-0 items-baseline gap-2 text-[15px] font-semibold leading-snug text-ink" data-testid="hv2-row-subject">
          <span className="min-w-0 truncate" title={subject}>
            {subject}
          </span>
          {isNew && newLabel ? (
            <span className="shrink-0 text-supporting font-semibold text-ink-2" data-testid="home-row-new">
              {newLabel}
            </span>
          ) : null}
          {qualifier ? (
            <span className="max-w-[55%] shrink-0 truncate text-supporting font-normal italic text-ink-3" title={qualifier} data-testid="hv2-row-qualifier">
              {qualifier}
            </span>
          ) : null}
        </span>
        <span className="col-span-2 row-start-2 min-w-0 truncate text-supporting text-ink-3 lg:col-span-1 lg:col-start-2 lg:row-start-1" title={nextStep ?? undefined} data-testid="hv2-row-next">
          {nextStep}
        </span>
        <span className="col-start-2 row-start-1 flex min-w-0 max-w-[14rem] justify-end justify-self-end lg:col-start-3 lg:max-w-full [&>*]:max-w-full [&>*]:!whitespace-normal [&>*]:!py-1 [&>*]:!leading-tight" data-testid="hv2-row-status">
          {pill}
        </span>
        <span aria-hidden className="hidden whitespace-nowrap text-right text-supporting font-semibold text-ink lg:block" data-testid="hv2-row-select-cell">
          {selectLabel && !selected ? (
            <span className="opacity-0 transition-opacity duration-(--dur-fast) group-hover:opacity-100 group-focus-visible:opacity-100" data-testid="hv2-row-select">
              {selectLabel} →
            </span>
          ) : null}
        </span>
        {severity}
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
