import type { ComponentType, ReactNode } from "react";
import { AlertIcon, CalendarIcon, CheckCircleIcon, CheckIcon, ClockIcon, DashedRingIcon, RingDotIcon, RingIcon, XIcon } from "@/components/icons";
import { STATE_LOOK, TONE_INK, TONE_MARK, type StateGlyph, type StateKey, type StateTone } from "./state-word-model";

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
};

/** A tinted pill, as a `Badge` is: the tone's fill, line and text. */
const PILL: Record<StateTone, string> = {
  neutral: "border-line bg-subtle text-ink-2",
  ok: "border-ok-line bg-ok-bg text-ok-fg",
  warn: "border-warn-line bg-warn-bg text-warn-fg",
  bad: "border-bad-line bg-bad-bg text-bad-fg",
  info: "border-info-line bg-info-bg text-info-fg",
};

/**
 * A state as the server names it, drawn one way everywhere (Home's rail, Receivables' rows and lifecycle, Cash's receipts): the word the server wrote (`children`),
 * the tone and the glyph the state always has (components/ui/state-word-model.ts). No page composes a state word itself, and the browser never invents the text.
 *
 *   word  (default) the glyph and the word in the tone's ink: a quiet word beside a figure (the rail's "planned").
 *   pill            the same on the tone's tint: a status in a table (an invoice's collection state).
 *   step            the word alone in the tone's ink, at the size and weight of the list it sits in (the lifecycle's three steps).
 *   line            the glyph in the tone, then a whole sentence the server wrote in the quiet ink (a receipt's "owed: invoiced 13 days ago, due in 32 days").
 *
 * `glyph={false}` leaves the mark to the parent (the lifecycle draws its own step discs); `tone` replaces the state's tone where a parent knows more than the state does
 * (a step already passed is green). The glyph is `aria-hidden`: the word is the accessible name, so colour and shape are never the only channels. 13 px at the least.
 */
export function StateWord({
  state,
  children,
  variant = "word",
  tone,
  glyph = true,
  testId,
  className = "",
  ...data
}: {
  state: StateKey;
  children: ReactNode;
  variant?: "word" | "pill" | "line" | "step";
  tone?: StateTone;
  glyph?: boolean;
  testId?: string;
  className?: string;
  [dataAttr: `data-${string}`]: string | undefined;
}) {
  const look = STATE_LOOK[state];
  const t = tone ?? look.tone;
  const Glyph = GLYPH[look.glyph];
  const mark = glyph ? <Glyph className={`mt-px size-3.5 shrink-0 ${variant === "pill" ? "" : TONE_MARK[t]}`} /> : null;
  const shape =
    variant === "pill"
      ? `inline-flex max-w-full items-center gap-1.5 rounded-pill border px-2.5 py-0.5 text-supporting font-medium ${PILL[t]}`
      : variant === "line"
        ? `flex items-start gap-1.5 text-supporting leading-snug ${state === "scheduled" ? "text-ink-3" : "text-ink-2"}`
        : variant === "step"
          ? `inline-flex items-start gap-1.5 ${TONE_INK[t]}`
          : `inline-flex items-start gap-1.5 text-supporting font-medium ${TONE_INK[t]}`;
  return (
    <span data-testid={testId} data-state={state} data-tone={t} {...data} className={`${shape} ${className}`}>
      {mark}
      <span className="min-w-0">{children}</span>
    </span>
  );
}
