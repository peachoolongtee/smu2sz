/**
 * The cue that a queue row opens something beside it: a right-pointing chevron at the row's right edge. Quiet (`ink-3`) at rest, ink on hover and keyboard focus of its row (the row must be a
 * `group`; the overlay button of a compact row is reached with `group-has-[:focus-visible]`), and on the selected row an ink disc with the chevron cut out of it. Decorative: the row's accessible
 * name is its own words. `hint` pulses it twice (the first visit's cue, `.row-hint`; none under reduced motion).
 */
export function RowChevron({ selected = false, hint = false, className = "" }: { selected?: boolean; hint?: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      data-testid="row-chevron"
      data-selected={selected ? "true" : "false"}
      data-hint={hint ? "true" : undefined}
      className={`pointer-events-none grid size-6 shrink-0 place-items-center rounded-pill transition-colors duration-(--dur) ${
        selected ? "bg-ink text-card" : "text-ink-3 group-hover:text-ink group-focus-visible:text-ink group-has-[:focus-visible]:text-ink"
      } ${hint ? "row-hint" : ""} ${className}`}
    >
      <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="m6 3.5 4.5 4.5L6 12.5" />
      </svg>
    </span>
  );
}
