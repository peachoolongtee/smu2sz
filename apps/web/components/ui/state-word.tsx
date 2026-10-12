import type { ComponentType, ReactNode } from "react";
import { AlertIcon, CalendarIcon, CheckCircleIcon, CheckIcon, ClockIcon, DashedRingIcon, DocumentIcon, HourglassIcon, RingDotIcon, RingIcon, TwoRingsIcon, XIcon } from "@/components/icons";
import { STATE_LOOK, TONE_GLYPH, TONE_INK, TONE_MARK, type StateGlyph, type StateKey, type StateTone } from "./state-word-model";

const GLYPH: Record<StateGlyph, ComponentType<{ className?: string }>> = {
  "dashed-ring": DashedRingIcon,
  "ring-dot": RingDotIcon,
  ring: RingIcon,
  check: CheckIcon,
  "check-circle": CheckCircleIcon,
  calendar: CalendarIcon,
  clock: ClockIcon,
  alert: AlertIcon,
  cross: XIcon,
  hourglass: HourglassIcon,
  document: DocumentIcon,
  rings: TwoRingsIcon,
};

type Props = {
  children: ReactNode;
  /** `word` (default): the glyph and the word in the tone's ink. `line`: the glyph, then a whole sentence the server wrote in the quiet ink. `step`: the word alone, at the size of the list it sits in. */
  variant?: "word" | "line" | "step";
  glyph?: boolean;
  /** A word that may break inside its row (the default); false keeps it on one line (a table cell). */
  wrap?: boolean;
  testId?: string;
  className?: string;
  [dataAttr: `data-${string}`]: string | undefined;
} & ({ state: StateKey; tone?: never } | { state?: never; tone: StateTone | "brand" });

/**
 * The one state vocabulary: icon, colour and the word the server wrote, drawn one way on every page (Home's rail, Receivables' rows and lifecycle, Cash's receipts, a
 * deal's status, an approval's result). Two ways in. `state` is one of the twelve states the owner's money moves through (planned, arranged, received, repaid, owed,
 * scheduled, agreed, pending, current, due_soon, overdue, promise_missed): its tone and its glyph are fixed in `state-word-model.ts` and nothing overrides them, so
 * "arranged" is the same blue on Home and on Receivables. `tone` is for a status the server names that is not one of the twelve (its mark is the tone's).
 * The browser never invents the text. The glyph is `aria-hidden`: the word is the accessible name, so colour and shape are never the only channels. 13 px at the least.
 */
export function StateWord({ state, tone, children, variant = "word", glyph = true, wrap = true, testId, className = "", ...data }: Props) {
  // A tone the server (or a status table) leaves out is neutral, never a crash.
  const resolved: StateTone = state ? STATE_LOOK[state].tone : tone === "brand" ? "info" : tone && tone in TONE_GLYPH ? tone : "neutral";
  const Glyph = GLYPH[state ? STATE_LOOK[state].glyph : TONE_GLYPH[resolved]];
  const mark = glyph ? <Glyph className={`mt-px size-3.5 shrink-0 ${TONE_MARK[resolved]}`} /> : null;
  const shape =
    variant === "line"
      ? `flex items-start gap-1.5 text-supporting ${state === "scheduled" ? "text-ink-3" : "text-ink-2"}`
      : variant === "step"
        ? `inline-flex items-start gap-1.5 ${TONE_INK[resolved]}`
        : `inline-flex items-start gap-1.5 text-supporting font-medium ${TONE_INK[resolved]}`;
  return (
    <span data-testid={testId} data-state={state} data-tone={resolved} {...data} className={`${shape} ${wrap ? "" : "whitespace-nowrap"} ${className}`}>
      {mark}
      <span className="min-w-0">{children}</span>
    </span>
  );
}
