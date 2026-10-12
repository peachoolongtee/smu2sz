import type { ReactNode } from "react";

/**
 * An open section: content grouped by space and type, with no card. A hairline above it (not above the first), then 32 px of margin and padding. Its heading is sentence case,
 * the display face at weight 800; `scope` is the small label that names a financial scope ("Company cash", "Impact of ...") and is 13 px, 700, ink-3 (never the 12 px metadata
 * size: it qualifies a figure). `subtitle` is one quiet line saying what the section is. The default container of Home V2, in place of `Card`.
 */
export function OpenSection({
  id,
  title,
  titleId,
  scope,
  subtitle,
  actions,
  first = false,
  children,
  className = "",
  testId,
}: {
  id?: string;
  title?: ReactNode;
  /** The id of the heading, for a section that is named by it. */
  titleId?: string;
  scope?: ReactNode;
  subtitle?: ReactNode;
  /** A control that belongs to the section's head (a window switch). */
  actions?: ReactNode;
  /** The first section of a column has no hairline and no margin above it. */
  first?: boolean;
  children?: ReactNode;
  className?: string;
  testId?: string;
}) {
  const heading = titleId ?? (id && title ? `${id}-title` : undefined);
  return (
    <section id={id} aria-labelledby={title ? heading : undefined} data-testid={testId} className={`min-w-0 ${first ? "" : "mt-7 border-t border-line pt-7 sm:mt-8 sm:pt-8"} ${className}`}>
      {title || actions ? (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            {scope ? <p className="mb-1 text-supporting font-bold uppercase tracking-[0.04em] text-ink-3">{scope}</p> : null}
            {title ? (
              <h2 id={heading} className="type-section text-ink">
                {title}
              </h2>
            ) : null}
            {subtitle ? <p className="mt-1 text-pretty text-sm text-ink-2">{subtitle}</p> : null}
          </div>
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}
