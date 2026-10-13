"use client";

import { useEffect, useRef, useState } from "react";
import { DashedRingIcon, RingDotIcon, CheckIcon, CheckCircleIcon } from "@/components/icons";
import { stateKey, STATE_LOOK, TONE_MARK } from "@/components/ui/state-word-model";
import { useI18n } from "@/lib/i18n";
import type { HomeV2Leg } from "@/lib/types";

const GLYPH = { planned: DashedRingIcon, arranged: RingDotIcon, received: CheckIcon, repaid: CheckCircleIcon } as const;
/** The bar's legs in the planned tone: brand, then a lighter brand, then the sky (the tokens' own; nothing new). */
const SEGMENT = ["bg-brand-600", "bg-brand-300", "bg-chart-sky", "bg-brand-100"] as const;

/**
 * The funding fact's own state: open while the pointer is on the fact or the composition, or while keyboard focus is on the fact (desktop), or once it has been pressed (a tap on a phone,
 * `?funding=1`: `pinned`). Leaving closes it after 150 ms unless it is pinned. The fact is a button: its press pins or releases.
 */
export function useFunding(pinned: boolean, onPin: (on: boolean) => void) {
  const [hover, setHover] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancel = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };
  useEffect(() => cancel, []);
  const show = () => {
    cancel();
    setHover(true);
  };
  const hide = () => {
    cancel();
    timer.current = setTimeout(() => setHover(false), 150);
  };
  return {
    open: pinned || hover,
    pointer: { onPointerEnter: show, onPointerLeave: hide, onMouseEnter: show, onMouseLeave: hide },
    focus: {
      onFocus: (e: React.FocusEvent<HTMLElement>) => {
        if ((e.target as HTMLElement).matches(":focus-visible")) show();
      },
      onBlur: hide,
    },
    toggle: () => onPin(!pinned),
    close: () => {
      cancel();
      setHover(false);
      if (pinned) onPin(false);
    },
  };
}

/** "Funding timing": the server's label and sentence as a button that opens the funding composition under the facts row. */
export function FundingFact({ label, value, open, controls, id, toggle, pointer, focus, hasLegs }: { label: string; value: string; open: boolean; controls: string; id: string; toggle: () => void; pointer: object; focus: object; hasLegs: boolean }) {
  const { t } = useI18n();
  if (!hasLegs)
    return (
      <div data-testid="hv2-funding-text">
        <p className="text-supporting text-ink-3">{label}</p>
        <p className="mt-1 text-supporting font-bold text-ink sm:text-sm">{value}</p>
      </div>
    );
  return (
    <button
      type="button"
      id={id}
      aria-expanded={open}
      aria-controls={controls}
      aria-label={`${label}: ${value}. ${t("hv2.funding.open")}`}
      onClick={toggle}
      {...pointer}
      {...focus}
      className="group -mx-2 -my-1 block w-[calc(100%+1rem)] rounded-control px-2 py-1 text-left hover:bg-subtle"
      data-testid="hv2-funding-fact"
    >
      <span className="block text-supporting text-ink-3">{label}</span>
      <span className="mt-1 flex items-start gap-1.5 text-supporting font-bold text-ink sm:text-sm">
        <span className="min-w-0 flex-1">{value}</span>
        <svg aria-hidden viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={`mt-0.5 shrink-0 text-ink-3 transition-transform duration-(--dur) ${open ? "rotate-180" : ""}`}>
          <path d="m4 6 4 4 4-4" />
        </svg>
      </span>
    </button>
  );
}

/**
 * How the funding is made up, under the facts row: one row per leg ("¥150,000 · Credit-line draw · today · planned" in the server's words), the total, a thin stacked bar whose widths
 * are the legs' amounts (`amount_fen` as the flex weights; no percentage is worked out here) and, under each segment, the server's `share_text` when it sends one (else no label).
 * Under the bar the plan's own basis for its cost, when the server has it. Opacity only moves it.
 */
export function FundingComposition({ legs, total, id, labelledBy, basis, pointer }: { legs: HomeV2Leg[]; total: string; id: string; labelledBy: string; basis?: string | null; pointer: object }) {
  const { t } = useI18n();
  const weights = legs.map((l) => (l.amount_fen && l.amount_fen > 0 ? l.amount_fen : 1));
  const shares = legs.some((l) => l.share_text);
  return (
    <div id={id} role="region" aria-labelledby={labelledBy} {...pointer} className="motion-reveal mt-3 border-t border-line pt-3" data-testid="hv2-funding-composition">
      <ul className="divide-y divide-line" data-testid="hv2-comp-rows">
        {legs.map((l, i) => {
          const key = stateKey(l.state) ?? "planned";
          const Icon = GLYPH[key as keyof typeof GLYPH] ?? DashedRingIcon;
          return (
            <li key={`${l.label}-${i}`} className="flex items-center gap-2 py-1.5 text-sm" data-testid={`hv2-comp-row-${i}`} data-state={l.state}>
              <span aria-hidden className={`size-2.5 shrink-0 rounded-pill ${SEGMENT[i % SEGMENT.length]}`} />
              <b className="font-bold tabular-nums text-ink">{l.amount_display}</b>
              <span className="min-w-0 flex-1 text-ink-2">
                {l.label} · {l.lands_when}
              </span>
              <span className="inline-flex shrink-0 items-center gap-1.5 text-supporting font-medium text-ink-2">
                <Icon className={`size-3.5 ${TONE_MARK[STATE_LOOK[key].tone]}`} />
                {l.state_text}
              </span>
            </li>
          );
        })}
        <li className="flex items-baseline justify-between py-1.5 text-sm" data-testid="hv2-comp-total">
          <span className="text-ink-3">{t("hv2.timeline.total")}</span>
          <b className="font-display text-base font-bold tabular-nums text-brand-600">{total}</b>
        </li>
      </ul>
      <div role="img" aria-label={t("hv2.funding.bar")} className="mt-2 flex h-2 gap-px overflow-hidden rounded-pill" data-testid="hv2-comp-bar">
        {legs.map((l, i) => (
          <span key={`${l.label}-${i}`} className={SEGMENT[i % SEGMENT.length]} style={{ flexGrow: weights[i], flexBasis: 0 }} data-testid={`hv2-comp-seg-${i}`} />
        ))}
      </div>
      {shares ? (
        <div className="mt-1 flex gap-px text-supporting tabular-nums text-ink-2" data-testid="hv2-comp-shares">
          {legs.map((l, i) => (
            <span key={`${l.label}-${i}`} className="min-w-0 text-center" style={{ flexGrow: weights[i], flexBasis: 0 }} data-testid={`hv2-comp-share-${i}`}>
              {l.share_text}
            </span>
          ))}
        </div>
      ) : null}
      {basis ? (
        <p className="mt-2 text-supporting text-ink-2" data-testid="hv2-comp-basis">
          {basis}
        </p>
      ) : null}
    </div>
  );
}
