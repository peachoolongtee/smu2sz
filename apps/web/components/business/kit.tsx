"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ChevronRightIcon } from "@/components/icons";

/**
 * The Business pages' building blocks, in one visual language (inspired by Revolut): white cards with large radii on a
 * grey canvas, round avatars, list rows that read left to right (what, then how much), pill buttons, and details that
 * stay closed until asked for. Colours and motion come from the `.biz` tokens in globals.css.
 */

export type BizTone = "neutral" | "brand" | "ok" | "warn" | "bad" | "violet" | "teal" | "orange" | "pink" | "sky";

/** Tinted discs and chips. The extra hues (violet, teal, orange, pink, sky) give each kind of thing its own colour. */
const avatarTone: Record<BizTone, string> = {
  neutral: "bg-subtle text-ink-2",
  brand: "bg-brand-50 text-brand-600",
  ok: "bg-ok-bg text-ok-fg",
  warn: "bg-warn-bg text-warn-fg",
  bad: "bg-bad-bg text-bad-fg",
  violet: "bg-violet-100 text-violet-700",
  teal: "bg-teal-100 text-teal-700",
  orange: "bg-orange-100 text-orange-700",
  pink: "bg-pink-100 text-pink-700",
  sky: "bg-sky-100 text-sky-700",
};

/** A white card. `lift` makes it rise on hover (for cards that are links). */
export function BizCard({
  children,
  className = "",
  id,
  testId,
  lift = false,
  labelledBy,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
  testId?: string;
  lift?: boolean;
  labelledBy?: string;
}) {
  return (
    <section
      id={id}
      data-testid={testId}
      aria-labelledby={labelledBy}
      className={`min-w-0 rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card) ${lift ? "lift" : ""} ${className}`}
    >
      {children}
    </section>
  );
}

/** A section heading above a card or list: a short title, an optional quiet line, an optional link on the right. */
export function SectionHead({ title, sub, action, id }: { title: ReactNode; sub?: ReactNode; action?: ReactNode; id?: string }) {
  return (
    <div className="mb-2.5 flex items-end justify-between gap-3 px-1">
      <div className="min-w-0">
        <h2 id={id} className="text-base font-semibold tracking-tight text-ink">
          {title}
        </h2>
        {sub ? <p className="text-sm text-ink-3">{sub}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

/** A round avatar: an icon or one or two letters on a tinted disc. */
export function Avatar({ children, tone = "neutral", size = "md" }: { children: ReactNode; tone?: BizTone; size?: "sm" | "md" | "lg" }) {
  const dim = size === "lg" ? "size-12 text-base" : size === "sm" ? "size-8 text-xs" : "size-10 text-sm";
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-full font-semibold ${dim} ${avatarTone[tone]}`}>
      {children}
    </span>
  );
}

/** A stable colour for a name, so each buyer keeps the same avatar colour everywhere. */
export function toneFor(name: string): BizTone {
  const tones: BizTone[] = ["violet", "teal", "orange", "pink", "sky", "brand"];
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return tones[h % tones.length];
}

/** The first letters of a name, for an avatar ("Foshan Home Retail Co." → "FH"). */
export function initials(name: string): string {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter(Boolean);
  return (words[0]?.[0] ?? "?").toUpperCase() + (words[1]?.[0] ?? "").toUpperCase();
}

/**
 * One list row: avatar, title and a quiet line on the left; the amount and its note on the right. With `href` the whole
 * row is a link with a chevron and a hover tint.
 */
export function Row({
  avatar,
  title,
  sub,
  right,
  rightSub,
  href,
  testId,
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
  tone?: "bad" | "warn";
  children?: ReactNode;
}) {
  const body = (
    <>
      {avatar}
      <span className="min-w-0 flex-1">
        <span className="block break-words font-medium text-ink">{title}</span>
        {sub ? <span className={`mt-0.5 block text-sm ${tone === "bad" ? "text-bad-fg" : tone === "warn" ? "text-warn-fg" : "text-ink-3"}`}>{sub}</span> : null}
        {children}
      </span>
      {right !== undefined || rightSub !== undefined ? (
        <span className="shrink-0 text-right">
          {right !== undefined ? <span className="figure block font-semibold text-ink">{right}</span> : null}
          {rightSub !== undefined ? <span className="mt-0.5 block text-sm text-ink-3">{rightSub}</span> : null}
        </span>
      ) : null}
      {href ? <ChevronRightIcon className="shrink-0 text-ink-3" /> : null}
    </>
  );
  const cls = "flex min-h-14 items-center gap-3 px-4 py-3";
  return href ? (
    <Link href={href} className={`${cls} press rounded-2xl hover:bg-subtle`} data-testid={testId}>
      {body}
    </Link>
  ) : (
    <div className={cls} data-testid={testId}>
      {body}
    </div>
  );
}

/**
 * Details behind a click: a native <details> (keyboard and screen-reader friendly, open state in the DOM), styled as a
 * quiet row with a turning chevron. `card` gives it its own card; otherwise it sits inside one.
 */
export function Disclosure({
  summary,
  children,
  testId,
  card = false,
  className = "",
  defaultOpen = false,
  id,
}: {
  summary: ReactNode;
  children: ReactNode;
  testId?: string;
  card?: boolean;
  className?: string;
  defaultOpen?: boolean;
  id?: string;
}) {
  return (
    <details
      id={id}
      open={defaultOpen || undefined}
      data-testid={testId}
      className={`${card ? "rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" : ""} ${className}`}
    >
      <summary className={`flex min-h-11 items-center gap-2 rounded-xl text-sm font-medium text-ink-2 hover:text-ink ${card ? "px-5 py-3" : "py-2"}`}>
        <ChevronRightIcon className="chev shrink-0 text-ink-3" />
        <span className="min-w-0 flex-1">{summary}</span>
      </summary>
      <div className={card ? "border-t border-line px-5 pb-5 pt-4" : "pb-1 pt-2"}>{children}</div>
    </details>
  );
}

/** A small figure with its label, for summary strips. */
export function Figure({ label, value, note, tone, testId, noteTestId }: { label: ReactNode; value: ReactNode; note?: ReactNode; tone?: "bad" | "ok"; testId?: string; noteTestId?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-sm text-ink-3">{label}</dt>
      <dd className={`figure mt-0.5 text-xl font-semibold ${tone === "bad" ? "text-bad-fg" : tone === "ok" ? "text-ok-fg" : "text-ink"}`} data-testid={testId}>
        {value}
      </dd>
      {note ? (
        <dd className="text-sm text-ink-3" data-testid={noteTestId}>
          {note}
        </dd>
      ) : null}
    </div>
  );
}

/** Pill link styles, matching the pill buttons. */
export const pillPrimary =
  "press inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700";
export const pillSecondary =
  "press inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-subtle px-5 text-sm font-semibold text-ink hover:bg-line-strong/60";
export const textLink = "inline-flex min-h-8 items-center text-sm font-semibold text-brand-600 hover:text-brand-700";

/** A tinted status chip. */
export function Chip({ children, tone = "neutral", testId }: { children: ReactNode; tone?: BizTone; testId?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${avatarTone[tone]}`} data-testid={testId}>
      {children}
    </span>
  );
}

/** The Business page title: large and tight, a quiet line under it, an optional action on the right. */
export function BizPageHeader({ title, sub, action, icon }: { title: ReactNode; sub?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
      {icon ? <div className="shrink-0">{icon}</div> : null}
      <div className="min-w-0 flex-1">
        <h1 className="text-[1.75rem] font-semibold leading-tight tracking-tight text-ink lg:text-[2rem]">{title}</h1>
        {sub ? <p className="mt-1 max-w-2xl text-ink-3">{sub}</p> : null}
      </div>
      {action ? <div className="flex flex-wrap items-center gap-2">{action}</div> : null}
    </header>
  );
}

/** A large tappable tile that leads somewhere: an icon disc, a title, one line, and a chevron. */
export function Tile({ href, icon, title, sub, testId, tone = "brand" }: { href: string; icon: ReactNode; title: ReactNode; sub?: ReactNode; testId?: string; tone?: BizTone }) {
  return (
    <Link href={href} data-testid={testId} className="lift press flex items-center gap-4 rounded-(--radius-card) border border-line bg-surface p-5 shadow-(--shadow-card)">
      <Avatar tone={tone} size="lg">
        {icon}
      </Avatar>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold text-ink">{title}</span>
        {sub ? <span className="mt-0.5 block text-sm text-ink-3">{sub}</span> : null}
      </span>
      <ChevronRightIcon className="shrink-0 text-ink-3" />
    </Link>
  );
}

const pageIconTone: Record<"violet" | "teal" | "orange" | "pink" | "sky" | "amber" | "brand", string> = {
  violet: "from-violet-500 to-fuchsia-500 shadow-violet-500/30",
  teal: "from-teal-400 to-emerald-500 shadow-teal-500/30",
  orange: "from-orange-400 to-amber-500 shadow-orange-500/30",
  pink: "from-pink-500 to-rose-500 shadow-pink-500/30",
  sky: "from-sky-400 to-blue-600 shadow-sky-500/30",
  amber: "from-amber-400 to-orange-500 shadow-amber-500/30",
  brand: "from-blue-500 to-indigo-600 shadow-blue-500/30",
};

/** A page's colour: a gradient tile with its icon, beside the title. Each section has its own hue. */
export function PageIcon({ tone, children }: { tone: keyof typeof pageIconTone; children: ReactNode }) {
  return (
    <span aria-hidden className={`mt-1 grid size-12 place-items-center rounded-2xl bg-linear-to-br text-white shadow-lg ${pageIconTone[tone]}`}>
      {children}
    </span>
  );
}
