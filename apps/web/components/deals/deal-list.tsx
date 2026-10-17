"use client";

import Link from "next/link";
import { ChevronRightIcon } from "@/components/icons";
import type { StateTone } from "@/lib/types";

/** The card's own fields: one buyer's row, where it stands and where opening it leads. Every word is the server's or the dictionary's. */
export interface ListCardRow {
  key: string;
  buyerId: string;
  name: string;
  /** Where the latest word came from and when. */
  meta: string | null;
  line: string;
  pill: { text: string; tone: StateTone };
  /** A figure the row carries (what is owed, what it is worth), with its tone. */
  figure: { text: string; tone: StateTone } | null;
  href: string;
  group?: string;
  figureNote?: string | null;
}

/** Home's pill fills (StatusPill): amber for what needs the owner, lavender for what waits on someone else, green for what is settled; the one risk red for what was set aside. */
const PILL: Record<StateTone, string> = {
  ok: "bg-f-green text-f-green-ink",
  warn: "bg-f-amber text-f-amber-ink",
  bad: "bg-bad-bg text-f-risk",
  info: "bg-f-purple-soft text-f-purple-ink",
  neutral: "bg-subtle text-ink-2",
};
const FIGURE: Record<StateTone, string> = { ok: "text-f-green-ink", warn: "text-f-amber-ink", bad: "text-f-risk", info: "text-f-purple-ink", neutral: "text-ink" };
/** The avatar's tint, by the row's place on the list: decoration only (Home's soft fills), never a status. */
const AVATAR = ["bg-f-purple-soft text-f-purple-ink", "bg-f-green text-f-green-ink", "bg-f-amber text-f-amber-ink", "bg-subtle text-ink"];

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter((w) => /^[A-Za-z一-鿿]/.test(w))
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("") || name.slice(0, 1);

/** The card's avatar: the name's initials on a soft fill picked by `index` (decoration, never a status; hidden from a reader, who has the name). `className` sizes it (48 px by default). */
export function ListAvatar({ name, index, className = "size-12" }: { name: string; index: number; className?: string }) {
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-[14px] font-display text-base font-bold ${AVATAR[index % AVATAR.length]} ${className}`} data-testid="list-avatar">
      {initials(name)}
    </span>
  );
}

/**
 * One row of a Business list, as a card in Home's look: an avatar with the initials, the name with where the last word came from and when, one line, the pill and a figure on
 * the right (under the line on a phone), and a chevron. The whole card is the link.
 */
export function ListCard({ row: r, index, label, quote, testId }: { row: ListCardRow; index: number; label: string; quote?: string | null; testId: string }) {
  return (
    <Link
      href={r.href}
      aria-label={label}
      className="motion-press group flex items-center gap-4 rounded-[var(--radius-f-card)] bg-panel p-4 shadow-(--shadow-f) outline outline-2 -outline-offset-2 outline-transparent transition-[box-shadow,outline-color] hover:shadow-(--shadow-lift) hover:outline-brand-600 focus-visible:shadow-(--shadow-lift) focus-visible:outline-brand-600 sm:gap-5 sm:p-5"
      data-testid={testId}
      data-buyer={r.buyerId}
      data-group={r.group}
    >
      <ListAvatar name={r.name} index={index} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="font-display text-base font-bold text-ink sm:text-lg">{r.name}</span>
          {r.meta ? <span className="text-supporting text-ink-3">{r.meta}</span> : null}
        </span>
        <span className="mt-1 line-clamp-2 block text-sm text-ink-2" data-testid={`${testId}-line`}>
          {quote ?? r.line}
        </span>
        {/* On a phone the pill and the figure sit under the line. */}
        <span className="mt-2 flex flex-wrap items-center gap-2 sm:hidden">
          <Pill pill={r.pill} />
          {r.figure ? <span className={`text-supporting font-bold tabular-nums ${FIGURE[r.figure.tone]}`}>{r.figure.text}</span> : null}
        </span>
      </span>
      <span className="hidden shrink-0 flex-col items-end gap-1.5 sm:flex">
        <Pill pill={r.pill} />
        {r.figure ? (
          <span className={`max-w-[240px] text-right font-display text-base font-bold tabular-nums ${FIGURE[r.figure.tone]}`} data-testid={`${testId}-figure`}>
            {r.figure.text}
          </span>
        ) : null}
        {r.figureNote ? <span className="text-supporting text-ink-3">{r.figureNote}</span> : null}
      </span>
      <ChevronRightIcon aria-hidden width={16} height={16} className="shrink-0 text-ink-3 transition-transform duration-(--dur-fast) group-hover:translate-x-0.5" />
    </Link>
  );
}

/** Home's status pill (StatusPill's shape), with the risk red for what was set aside. */
function Pill({ pill }: { pill: ListCardRow["pill"] }) {
  return (
    <span className={`inline-flex min-h-7 items-center whitespace-nowrap rounded-pill px-3 py-0.5 text-supporting font-medium leading-snug ${PILL[pill.tone]}`} data-testid="deal-list-pill" data-tone={pill.tone}>
      <span className="first-letter:uppercase">{pill.text}</span>
    </span>
  );
}
