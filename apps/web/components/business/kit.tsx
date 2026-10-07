"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ChevronRightIcon } from "@/components/icons";

/**
 * The Business pages' small shared parts, on the app's flat palette (surface cards, the brand blue, the tone tokens):
 * details that stay closed until asked for, list rows that read left to right (what, then how much), and a fact tile (a label over one figure or sentence). No colour here is
 * new; the tones come from globals.css.
 */

export type FactTone = "neutral" | "ok" | "warn" | "bad";

const factTone: Record<FactTone, { box: string; value: string }> = {
  neutral: { box: "border-line bg-subtle", value: "text-ink" },
  ok: { box: "border-ok-line bg-ok-bg", value: "text-ok-fg" },
  warn: { box: "border-warn-line bg-warn-bg", value: "text-warn-fg" },
  bad: { box: "border-bad-line bg-bad-bg", value: "text-bad-fg" },
};

/**
 * One fact as a tile: a quiet label, the value large, an optional note beneath. The tile is a `<div>` inside a `<dl>`;
 * `testId` goes on the value so a spec can read the figure itself.
 */
export function FactTile({ label, children, tone = "neutral", valueTone, testId, note, noteTestId, deep = false }: { label: ReactNode; children: ReactNode; tone?: FactTone; valueTone?: "bad"; testId?: string; note?: ReactNode; noteTestId?: string; deep?: boolean }) {
  const c = factTone[tone];
  // On the deep block (the Home hero) the tile is translucent white, its figure white, and a figure that is the status takes the bright red.
  return (
    <div className={`min-w-0 rounded-lg px-3.5 py-3 ${deep ? "bg-on-deep/10" : `border ${c.box}`}`}>
      <dt className={`text-xs font-medium ${deep ? "text-on-deep-muted" : "text-ink-3"}`}>{label}</dt>
      <dd className={`mt-0.5 break-words text-base font-semibold tabular-nums ${deep ? (valueTone === "bad" ? "text-bad-bright" : "text-on-deep") : valueTone === "bad" ? factTone.bad.value : c.value}`} data-testid={testId}>
        {children}
      </dd>
      {note ? (
        <dd className={`text-xs font-normal ${deep ? "text-on-deep-muted" : "text-ink-3"}`} data-testid={noteTestId}>
          {note}
        </dd>
      ) : null}
    </div>
  );
}

/**
 * Details behind a click: a native `<details>` (keyboard and screen-reader friendly, the open state lives in the DOM)
 * with a chevron that turns when open. Inside a card it is a quiet row; `card` gives it a card of its own.
 */
export function Disclosure({ summary, children, testId, card = false, className = "", defaultOpen = false, deep = false }: { summary: ReactNode; children: ReactNode; testId?: string; card?: boolean; className?: string; defaultOpen?: boolean; deep?: boolean }) {
  return (
    <details open={defaultOpen || undefined} data-testid={testId} className={`group ${card ? "rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" : ""} ${className}`}>
      <summary className={`flex min-h-10 cursor-pointer list-none items-center gap-2 text-sm font-medium [&::-webkit-details-marker]:hidden ${deep ? "text-on-deep" : card ? "px-4 py-3 font-semibold text-ink" : "text-brand-700"}`}>
        <ChevronRightIcon className={`shrink-0 transition-transform group-open:rotate-90 ${deep ? "text-on-deep-muted" : "text-ink-3"}`} />
        <span className="min-w-0 flex-1">{summary}</span>
      </summary>
      <div className={card ? "border-t border-line p-4" : "pb-1 pt-2"}>{children}</div>
    </details>
  );
}

/** The first letters of a name, for a quiet round avatar ("Foshan Home Retail Co." becomes "FH"). */
export function initials(name: string): string {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter(Boolean);
  return (words[0]?.[0] ?? "?").toUpperCase() + (words[1]?.[0] ?? "").toUpperCase();
}

/** An avatar's tint: a status (what a change row says) or a hue (who a buyer is). A hue says "this one", never "how it is going". */
export type AvatarTone = "neutral" | "ok" | "warn" | "bad" | "home" | "deals" | "cash" | "activity";
const avatarTone: Record<AvatarTone, string> = {
  neutral: "bg-subtle text-ink-2",
  ok: "bg-ok-bg text-ok-fg",
  warn: "bg-warn-bg text-warn-fg",
  bad: "bg-bad-bg text-bad-fg",
  home: "bg-sec-home-bg text-sec-home-fg",
  deals: "bg-sec-deals-bg text-sec-deals-fg",
  cash: "bg-sec-cash-bg text-sec-cash-fg",
  activity: "bg-sec-activity-bg text-sec-activity-fg",
};

/** A small round disc: one or two letters or a glyph, tinted by what it means (never by decoration). */
export function Avatar({ children, tone = "neutral" }: { children: ReactNode; tone?: AvatarTone }) {
  return (
    <span aria-hidden className={`grid size-9 shrink-0 place-items-center rounded-pill text-xs font-bold ${avatarTone[tone]}`}>
      {children}
    </span>
  );
}

/**
 * A stable hue for a name, so each buyer keeps the same avatar everywhere. Four of the five section tints: the orange is left
 * out because it sits next to the warning amber and an avatar must never look like a status.
 */
export function toneFor(name: string): AvatarTone {
  const hues: AvatarTone[] = ["home", "deals", "cash", "activity"];
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return hues[h % hues.length];
}

/**
 * One list row: an avatar, the title with a quiet line under it, and on the right the figure with its note. With `href`
 * the whole row is a link with a chevron. Rows sit in a card and are divided by hairlines.
 */
export function Row({
  avatar,
  title,
  sub,
  right,
  rightSub,
  href,
  testId,
  titleTestId,
  tone,
  children,
}: {
  avatar?: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
  rightSub?: ReactNode;
  href?: string;
  testId?: string;
  titleTestId?: string;
  tone?: "bad" | "warn";
  children?: ReactNode;
}) {
  const body = (
    <>
      {avatar}
      <span className="min-w-0 flex-1">
        <span className="block break-words text-sm font-medium text-ink" data-testid={titleTestId}>{title}</span>
        {sub ? <span className={`mt-0.5 block text-xs ${tone === "bad" ? "text-bad-fg" : tone === "warn" ? "text-warn-fg" : "text-ink-3"}`}>{sub}</span> : null}
        {children}
      </span>
      {right !== undefined || rightSub !== undefined ? (
        <span className="shrink-0 text-right">
          {right !== undefined ? <span className="block text-sm font-semibold tabular-nums text-ink">{right}</span> : null}
          {rightSub !== undefined ? <span className="block text-xs text-ink-3">{rightSub}</span> : null}
        </span>
      ) : null}
      {href ? <ChevronRightIcon className="shrink-0 text-ink-3" /> : null}
    </>
  );
  const cls = "flex min-h-12 items-center gap-3 py-2.5";
  return href ? (
    <Link href={href} className={`${cls} rounded-md hover:bg-subtle`} data-testid={testId}>
      {body}
    </Link>
  ) : (
    <div className={cls} data-testid={testId}>
      {body}
    </div>
  );
}
