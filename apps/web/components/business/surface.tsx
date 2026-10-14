"use client";

import Link from "next/link";
import type { ComponentType, ReactNode, SVGProps } from "react";
import { FlowLines } from "./flow-lines";
import { ArrowRightIcon, ChevronRightIcon } from "@/components/icons";

/**
 * The Business pages' surfaces in Home's look: the quiet backdrop behind every page, a fold that is a card of its own (for what is worth keeping but not worth showing first) and the tool tile
 * (a door to a tool, sized by how much it matters). Layout only; every word in them is the caller's, from the server's read or the dictionary.
 */

/** The page's backdrop, behind everything: thin lines flowing across the page in the section's hue (`--sec` on an ancestor). Decoration only. */
export function PageBackdrop({ sectionKey = "home" }: { sectionKey?: string }) {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" data-testid="page-backdrop">
      <FlowLines sectionKey={sectionKey} />
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
      <summary className="flex cursor-pointer list-none items-center gap-3 rounded-[var(--radius-f-card)] px-5 py-4 hover:bg-subtle/60 sm:px-6 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0 flex-1">
          <span className="sec-title block font-display text-base font-bold tracking-[-0.01em] text-ink">{title}</span>
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
 * (the ink block, Home's primary, for the tool that needs the owner now); `plain` is a panel tile. The caller decides which by what matters.
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
  compact = false,
  hue,
}: {
  href: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  title: string;
  body: string;
  tone?: ToolTone;
  badge?: string | null;
  testId?: string;
  className?: string;
  /** One low row (icon, name and one line beside it) for a strip of shortcuts that must not take the page's room. */
  compact?: boolean;
  /** The tile's own colour (a CSS colour): a solid icon disc and a faint tint of it, so shortcuts side by side tell apart at a glance. Decoration only, never a status. */
  hue?: string;
}) {
  const loud = tone === "feature";
  if (compact)
    return (
      <Link
        href={href}
        className={`motion-press group relative flex min-h-16 items-center gap-3 rounded-[18px] px-3.5 py-2.5 shadow-(--shadow-f) transition-shadow hover:shadow-(--shadow-lift) focus-visible:shadow-(--shadow-lift) ${loud ? "bg-f-btn text-f-btn-ink" : "bg-panel text-ink"} ${className}`}
        style={hue && !loud ? { background: `color-mix(in srgb, ${hue} 9%, var(--color-panel))`, boxShadow: `inset 3px 0 0 ${hue}` } : undefined}
        data-testid={testId}
        data-hue={hue ? "true" : undefined}
      >
        <span aria-hidden className={`grid size-9 shrink-0 place-items-center rounded-pill ${loud ? "bg-white/15" : hue ? "text-white" : "bg-subtle"}`} style={hue && !loud ? { background: hue } : undefined}>
          <Icon width={18} height={18} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-sm font-bold leading-tight">
            <span className="truncate">{title}</span>
            <ArrowRightIcon aria-hidden width={12} height={12} className="shrink-0 transition-transform duration-(--dur-fast) group-hover:translate-x-0.5" />
          </span>
          <span className={`mt-0.5 block truncate text-supporting ${loud ? "text-f-btn-ink/70" : "text-ink-3"}`}>{body}</span>
        </span>
        {badge ? <span className="shrink-0 rounded-pill bg-f-amber px-2 py-0.5 text-supporting font-bold text-f-amber-ink">{badge}</span> : null}
      </Link>
    );
  return (
    <Link
      href={href}
      className={`motion-press group relative isolate flex flex-col overflow-hidden rounded-[var(--radius-f-card)] p-4 shadow-(--shadow-f) transition-shadow hover:shadow-(--shadow-lift) focus-visible:shadow-(--shadow-lift) sm:min-h-[132px] sm:p-5 ${
        loud ? "bg-f-btn text-f-btn-ink" : "bg-panel text-ink"
      } ${className}`}
      data-testid={testId}
    >
      {loud ? <span aria-hidden className="dash-dots absolute inset-y-0 right-0 -z-10 w-2/3" /> : null}
      <span className="flex items-start justify-between gap-3">
        <span aria-hidden className={`grid size-10 place-items-center rounded-pill sm:size-11 ${loud ? "bg-white/15 text-f-btn-ink" : "bg-subtle text-ink"}`}>
          <Icon width={20} height={20} />
        </span>
        {badge ? <span className="rounded-pill bg-f-amber px-2.5 py-1 text-supporting font-bold text-f-amber-ink">{badge}</span> : null}
      </span>
      <span className={`mt-3 flex items-center gap-1.5 font-display font-bold leading-tight tracking-[-0.01em] sm:mt-4 ${loud ? "text-lg sm:text-xl" : "text-[15px] sm:text-base"}`}>
        {title}
        <ArrowRightIcon width={14} height={14} className="transition-transform duration-(--dur-fast) group-hover:translate-x-0.5" />
      </span>
      {/* On a phone the tiles sit two by two: the name carries them, the line is for wider screens. */}
      <span className={`mt-1 hidden text-supporting sm:block ${loud ? "text-f-btn-ink/70" : "text-ink-3"}`}>{body}</span>
    </Link>
  );
}
