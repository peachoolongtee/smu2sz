import type { ReactNode } from "react";
import { StateWord } from "@/components/ui/state-word";
import type { StateTone } from "@/components/ui/state-word-model";
import type { DealTone, PathAuthority } from "@/lib/types";

/** The fill of a status pill by tone (the fills are the scope's: amber needs you, lavender waits, green is healthy). */
const FILL: Record<StateTone, string> = { neutral: "bg-subtle", ok: "bg-ok-bg", warn: "bg-warn-bg", bad: "bg-bad-bg", info: "bg-info-bg" };

/**
 * A status as the mockup's pill: the kit's `StateWord` (a mark, the word the server wrote, the tone's ink) on the tone's fill. The word is the accessible name and the mark is
 * never colour alone; 13 px at the least. `wrap` false keeps a one-line status in its cell.
 */
export function StatusPill({ tone, children, wrap = true, testId, ...data }: { tone: StateTone; children: ReactNode; wrap?: boolean; testId?: string; [attr: `data-${string}`]: string | undefined }) {
  return (
    <span className={`inline-flex max-w-full rounded-pill px-2.5 py-1 ${FILL[tone]}`} data-testid={testId} {...data}>
      <StateWord tone={tone} wrap={wrap}>
        {children}
      </StateWord>
    </span>
  );
}

/** The server names a tone from its own five (`mute` is a quiet one); the kit calls that neutral. */
export const toneOfDeal = (t: DealTone | string | null | undefined): StateTone => (t === "mute" || !t ? "neutral" : (t as StateTone));

/** Who decides, in the verifier's three classes, as a tone: FLOW may send it (ok), you approve first (warn), over a limit you signed (bad). */
export const AUTH_TONE: Record<PathAuthority | string, StateTone> = { flow_may: "ok", needs_owner: "warn", over_limit: "bad" };

/** A figure with the words beside it: the server's display, its `when`, and the sentence under it. Words under a figure are 13 px (a qualifier, never the 12 px label size). */
export function Cell({ value, bad, note, sub }: { value?: string | null; bad?: boolean; note?: string | null; sub?: string | null }) {
  return (
    <>
      {value ? <span className={`block font-display text-base font-bold leading-snug tabular-nums ${bad ? "text-bad-fg" : "text-ink"}`}>{value}</span> : null}
      {sub ? <span className="block text-supporting text-ink-3">{sub}</span> : null}
      {note ? <span className={`block text-supporting first-letter:uppercase ${bad ? "text-bad-fg" : "text-ink-2"}`}>{note}</span> : null}
    </>
  );
}

export const NONE = <span className="text-supporting text-ink-3">—</span>;

/** A quiet text link or text button: 13 px (the kit's own is 12 px, which this page keeps for labels only), brand ink, underlined, a 32 px target (44 px on touch). */
export const quietLink = "motion-press hit inline-flex min-h-8 items-center rounded-pill px-2 text-supporting font-bold text-brand-700 underline underline-offset-2 hover:bg-brand-50 touch:min-h-11";
