import type { ReactNode } from "react";

export type PillTone = "amber" | "lavender" | "green" | "neutral" | "bad";

const TONE: Record<PillTone, string> = {
  amber: "bg-f-amber text-f-amber-ink",
  lavender: "bg-f-purple-soft text-f-purple-ink",
  green: "bg-f-green text-f-green-ink",
  neutral: "bg-subtle text-ink-2",
  /** The tracker's bad tone (an agreed deal whose payment is late): the risk fill and ink, always with the server's word. */
  bad: "bg-bad-bg text-bad-fg",
};

/**
 * The mockup's filled status pill: the server's word on an amber (needs you, action ready, a collection), lavender (the buyer's turn, waiting, planned) or green (healthy,
 * not due) fill, pill-shaped, 13 px at the least. It carries the word and nothing else; the tone says who acts, never how much. `StateWord` stays the container-free form for the
 * state vocabulary's twelve states (a receipt, a lot); a pill is for a row's or a card's one status. The word is the accessible name: colour is never the only channel.
 */
export function StatusPill({ tone, children, testId, className = "", ...data }: { tone: PillTone; children: ReactNode; testId?: string; className?: string; [dataAttr: `data-${string}`]: string | undefined }) {
  return (
    <span data-testid={testId} data-tone={tone} {...data} className={`inline-flex min-h-7 items-center whitespace-nowrap rounded-pill px-3 py-0.5 text-supporting font-medium leading-snug ${TONE[tone]} ${className}`}>
      <span className="first-letter:uppercase">{children}</span>
    </span>
  );
}
