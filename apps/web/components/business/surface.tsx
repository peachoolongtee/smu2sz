"use client";

import Link from "next/link";
import type { ComponentType, ReactNode, SVGProps } from "react";
import { ArrowRightIcon, ChevronRightIcon } from "@/components/icons";

/**
 * The Business pages' surfaces, after the dashboard revamp: the quiet backdrop behind every page, a fold that is a card of its own (for what is worth
 * keeping but not worth showing first), and the tool tile (a door to a tool, sized by how much it matters). Decoration and layout only; every word in them
 * is the caller's, from the server's read or the dictionary.
 */

/** The page's background: a soft wash of the brand blue in one corner, teal in the other, and thin contour lines. Behind everything, never in the way. */
export function PageBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" data-testid="page-backdrop">
      <div className="absolute -right-64 -top-72 size-[1100px] rounded-full bg-[radial-gradient(closest-side,rgb(3_104_233/0.2),transparent)]" />
      <div className="absolute -bottom-96 -left-72 size-[1000px] rounded-full bg-[radial-gradient(closest-side,rgb(56_208_199/0.2),transparent)]" />
      <div className="absolute left-1/3 top-1/3 size-[700px] rounded-full bg-[radial-gradient(closest-side,rgb(155_95_255/0.08),transparent)]" />
      <svg className="absolute inset-0 size-full" preserveAspectRatio="xMidYMid slice" viewBox="0 0 1440 900">
        {/* Two families of contour waves: one sweeping across the lower half, one curling out of the top-right corner. */}
        <g fill="none" stroke="var(--color-brand-600)" strokeWidth="1.5">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <path key={`low-${i}`} d={`M-80 ${560 + i * 34} C 260 ${430 + i * 30}, 540 ${720 + i * 26}, 880 ${560 + i * 30} S 1400 ${380 + i * 34}, 1540 ${470 + i * 34}`} opacity={0.2 - i * 0.022} />
          ))}
        </g>
        <g fill="none" stroke="var(--color-chart-teal)" strokeWidth="1.5">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <path key={`top-${i}`} d={`M${880 - i * 46} -60 C ${980 - i * 40} ${150 + i * 34}, ${1220 - i * 20} ${200 + i * 40}, 1540 ${130 + i * 46}`} opacity={0.32 - i * 0.045} />
          ))}
        </g>
        <circle cx="1300" cy="780" r="260" fill="none" stroke="var(--color-brand-600)" strokeOpacity="0.12" strokeWidth="1.5" />
        <circle cx="1300" cy="780" r="190" fill="none" stroke="var(--color-brand-600)" strokeOpacity="0.08" strokeWidth="1.5" />
      </svg>
    </div>
  );
}

/**
 * A dropdown that is a card: a title and one line saying what is inside, and the content only once opened. For the parts of a page that are worth keeping
 * but not worth reading first (the readings, the basis, the full tables).
 */
export function FoldCard({ title, hint, children, testId, defaultOpen = false, id }: { title: ReactNode; hint?: ReactNode; children: ReactNode; testId?: string; defaultOpen?: boolean; id?: string }) {
  return (
    <details id={id} open={defaultOpen || undefined} className="group motion-reveal card-flat !p-0" data-testid={testId}>
      <summary className="flex cursor-pointer list-none items-center gap-3 rounded-[22px] px-5 py-4 hover:bg-canvas/60 sm:px-6 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0 flex-1">
          <span className="block font-display text-base font-extrabold tracking-[-0.01em] text-ink">{title}</span>
          {hint ? <span className="mt-0.5 block text-supporting text-ink-3">{hint}</span> : null}
        </span>
        <span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-pill bg-subtle text-ink-2 transition-transform duration-(--dur-fast) group-open:rotate-90">
          <ChevronRightIcon width={14} height={14} />
        </span>
      </summary>
      <div className="border-t border-line px-5 pb-5 pt-4 sm:px-6">{children}</div>
    </details>
  );
}

export type ToolTone = "feature" | "plain";

/**
 * A door to a tool, as a tile: an icon, a name, one line of what it does and, when there is one, a count that needs the owner. `feature` is the loud tile
 * (the deep block, for the tool that needs the owner now); `plain` is a white tile. The caller decides which by what matters.
 */
export function ToolTile({
  href,
  icon: Icon,
  title,
  body,
  tone = "plain",
  badge,
  testId,
  className = "",
}: {
  href: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  title: string;
  body: string;
  tone?: ToolTone;
  badge?: string | null;
  testId?: string;
  className?: string;
}) {
  const loud = tone === "feature";
  return (
    <Link
      href={href}
      className={`motion-press group relative isolate flex flex-col overflow-hidden rounded-[22px] p-4 shadow-(--shadow-lift) sm:min-h-[132px] sm:p-5 transition-shadow hover:shadow-(--shadow-pop) focus-visible:shadow-(--shadow-pop) ${
        loud ? "bg-brand-900 text-on-deep" : "bg-surface text-ink"
      } ${className}`}
      data-testid={testId}
    >
      {loud ? <span aria-hidden className="dash-dots absolute inset-y-0 right-0 -z-10 w-2/3" /> : null}
      <span className="flex items-start justify-between gap-3">
        <span aria-hidden className={`grid size-10 place-items-center rounded-pill sm:size-11 ${loud ? "bg-brand-600 text-on-deep" : "bg-brand-50 text-brand-700"}`}>
          <Icon width={20} height={20} />
        </span>
        {badge ? <span className={`rounded-pill px-2.5 py-1 text-supporting font-extrabold ${loud ? "bg-warn-bright text-brand-900" : "bg-warn-bg text-warn-fg"}`}>{badge}</span> : null}
      </span>
      <span className={`mt-3 flex items-center gap-1.5 font-display font-extrabold leading-tight tracking-[-0.01em] sm:mt-4 ${loud ? "text-lg sm:text-xl" : "text-[15px] sm:text-base"}`}>
        {title}
        <ArrowRightIcon width={14} height={14} className="transition-transform duration-(--dur-fast) group-hover:translate-x-0.5" />
      </span>
      {/* On a phone the tiles sit two by two: the name carries them, the line is for wider screens. */}
      <span className={`mt-1 hidden text-supporting sm:block ${loud ? "text-on-deep-muted" : "text-ink-3"}`}>{body}</span>
    </Link>
  );
}
