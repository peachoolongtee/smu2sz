"use client";

import { useId, useRef, useState } from "react";
import { useWidth } from "@/components/business/cash-picture";
import { StateWord } from "@/components/ui/state-word";
import { stateKey, STATE_LOOK, TONE_MARK } from "@/components/ui/state-word-model";
import { CheckCircleIcon, CheckIcon, DashedRingIcon, RingDotIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";
import type { HomeV2Leg } from "@/lib/types";

/** Label width (5.5 rem), the total column (8.5 rem) and the room a marker keeps at the left (half a label). */
const LABEL = 88;
const TOTAL = 136;
const PAD = 44;

const GLYPH = { planned: DashedRingIcon, arranged: RingDotIcon, received: CheckIcon, repaid: CheckCircleIcon } as const;

function Glyph({ state, className = "" }: { state: string; className?: string }) {
  const key = stateKey(state) ?? "planned";
  const Icon = GLYPH[key as keyof typeof GLYPH] ?? DashedRingIcon;
  return <Icon className={`${TONE_MARK[STATE_LOOK[key].tone]} ${className}`} />;
}

/** The leg's own words as rows: lands when, its cost, repaid when, who decides. A row with no word is not drawn. */
function Details({ leg }: { leg: HomeV2Leg }) {
  const { t } = useI18n();
  const rows = [
    { k: "lands", label: t("hv2.leg.lands"), v: leg.lands_when },
    { k: "cost", label: t("hv2.leg.cost"), v: leg.cost_display },
    { k: "repaid", label: t("hv2.leg.repaid"), v: leg.repaid_when },
    { k: "authority", label: t("hv2.leg.authority"), v: leg.authority_text },
  ].filter((r): r is { k: string; label: string; v: string } => Boolean(r.v));
  return (
    <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-supporting">
      {rows.map((r) => (
        <div key={r.k} className="contents" data-testid={`hv2-leg-${r.k}`}>
          <dt className="text-ink-3">{r.label}</dt>
          <dd className="font-bold text-ink">{r.v}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * When does the money land: a thin horizontal timeline, one marker per leg of the plan, in the planned tone with the state's own glyph (the dashed ring while planned, the ring with a
 * dot once arranged, the check once landed), the source and the amount under each marker and the total at the right end. Markers sit at the day the leg lands and are sized by its amount
 * when the server sends those numbers (they only place and size a mark); without them the legs are spaced evenly and sized alike. Pointing at a marker or focusing it opens a card with
 * the leg's words (lands, cost, repaid, who decides); Escape closes it. On a phone the legs are stacked rows, each opening on a tap. Nothing animates but the card's opacity.
 * Every word is the server's `action.legs[]`; the dictionary supplies only the labels.
 */
export function FundingTimeline({ legs, total }: { legs: HomeV2Leg[]; total: string }) {
  const { t } = useI18n();
  const uid = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const W = useWidth(wrap);
  const [shown, setShown] = useState<number | null>(null);
  // The line runs from today (0) to the plan's last repayment day (else its last landing day); a marker sits at the day its leg lands. The days only place a mark.
  const lands = legs.map((l) => l.lands_day).filter((d): d is number => typeof d === "number");
  const repaid = legs.map((l) => l.repaid_day).filter((d): d is number => typeof d === "number");
  const placed = lands.length === legs.length && Math.max(...lands, ...repaid) > 0;
  const end = Math.max(...repaid, ...(repaid.length ? [] : lands), 1);
  const big = Math.max(...legs.map((l) => l.amount_fen ?? 0), 0);
  const pct = (l: HomeV2Leg, i: number) => (placed ? Math.min(Math.max(((l.lands_day ?? 0) / end) * 100, 0), 100) : legs.length === 1 ? 0 : (i / (legs.length - 1)) * 100);
  // Sized by the leg's amount in a 10 to 18 px range (the largest is 18); alike when the server sends no amounts.
  const size = (l: HomeV2Leg) => (big > 0 && l.amount_fen ? 10 + Math.round((l.amount_fen / big) * 8) : 14);
  // Where each marker sits in pixels, and so which labels would run into each other: two that are closer than a label is wide alternate (below the line, then above it) with a
  // 1 px leader to the marker; three in a run drop their labels for a legend row under the line, in landing order.
  const span = Math.max(W - TOTAL - 2 * PAD, 0);
  const xs = legs.map((l, i) => PAD + (span * pct(l, i)) / 100);
  const order = legs.map((_, i) => i).sort((p, q) => xs[p] - xs[q] || p - q);
  let run = 1;
  let longest = 1;
  let touching = false;
  for (let k = 1; k < order.length; k++) {
    if (xs[order[k]] - xs[order[k - 1]] < LABEL + 8) {
      touching = true;
      run += 1;
      longest = Math.max(longest, run);
    } else run = 1;
  }
  const measured = W > 0;
  const legend = measured && longest >= 3;
  const stagger = measured && touching && !legend;
  const H = stagger ? 176 : legend ? 80 : 96;
  const lineY = stagger ? 82 : 14;
  const above = (i: number) => stagger && order.indexOf(i) % 2 === 1;
  return (
    <div className="min-w-0" data-testid="hv2-timeline" data-legs={legs.length} data-layout={legend ? "legend" : stagger ? "staggered" : "plain"}>
      <p className="text-supporting text-ink-3 max-sm:sr-only">{t("hv2.timeline.title")}</p>
      {/* Desktop: the timeline */}
      <div ref={wrap} className="relative mt-2 hidden sm:block" style={{ height: H }} role="list" aria-label={t("hv2.timeline.title")} onKeyDown={(e) => e.key === "Escape" && setShown(null)}>
        <span aria-hidden className="absolute left-0 top-0 h-0.5 rounded-pill bg-line-strong" style={{ right: TOTAL, top: lineY }} />
        {legs.map((l, i) => {
          const px = size(l);
          const open = shown === i;
          const up = above(i);
          return (
            <div key={`${l.label}-${i}`} role="listitem" className="absolute top-0 w-0" style={{ left: xs[i], height: H }} data-testid={`hv2-leg-${i}`} data-state={l.state}>
              <button
                type="button"
                aria-describedby={open ? `${uid}-${i}` : undefined}
                aria-expanded={open}
                aria-label={`${l.label}, ${l.amount_display}, ${l.state_text}`}
                onPointerEnter={() => setShown(i)}
                onPointerLeave={() => setShown((s) => (s === i ? null : s))}
                onMouseEnter={() => setShown(i)}
                onMouseLeave={() => setShown((s) => (s === i ? null : s))}
                onFocus={() => setShown(i)}
                onBlur={() => setShown((s) => (s === i ? null : s))}
                onClick={() => setShown(open ? null : i)}
                className="absolute z-10 grid size-6 -translate-x-1/2 place-items-center rounded-pill"
                style={{ top: lineY - 12 }}
                data-testid={`hv2-leg-marker-${i}`}
              >
                <span className="grid place-items-center rounded-pill bg-brand-50 ring-2 ring-surface" style={{ width: px, height: px }} data-testid={`hv2-leg-dot-${i}`}>
                  <Glyph state={l.state} className="size-full" />
                </span>
              </button>
              {legend ? null : (
                <>
                  {stagger ? <span aria-hidden className="absolute w-px -translate-x-1/2 bg-line-strong" style={up ? { bottom: H - lineY + 12, height: 10 } : { top: lineY + 12, height: 10 }} data-testid={`hv2-leg-leader-${i}`} /> : null}
                  <div className="absolute w-22 -translate-x-1/2 text-center" style={up ? { bottom: H - lineY + 22 } : { top: lineY + (stagger ? 22 : 18) }} data-testid={`hv2-leg-label-${i}`}>
                    <p className="text-supporting leading-tight text-ink-2">{l.label}</p>
                    <p className="text-sm font-bold tabular-nums text-ink">{l.amount_display}</p>
                  </div>
                </>
              )}
              <div
                id={`${uid}-${i}`}
                role="tooltip"
                hidden={!open}
                className="motion-reveal absolute left-0 z-20 w-64 -translate-x-1/2 rounded-tile bg-surface px-3.5 py-3 text-left shadow-pop"
                style={{ top: H + 4 }}
                data-testid={`hv2-leg-card-${i}`}
              >
                <p className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2 text-sm font-bold text-ink">
                  <span>{l.label}</span>
                  <span className="tabular-nums">{l.amount_display}</span>
                </p>
                <StateWord state={stateKey(l.state) ?? "planned"} className="mb-1.5">
                  {l.state_text}
                </StateWord>
                <Details leg={l} />
              </div>
            </div>
          );
        })}
        <div className="absolute right-0 w-32 text-right" style={{ top: lineY - 14 }}>
          <p className="text-supporting text-ink-3">{t("hv2.timeline.total")}</p>
          <p className="font-display text-lg font-bold tabular-nums text-brand-600" data-testid="hv2-timeline-total">
            {total}
          </p>
        </div>
        {legend ? (
          <ul className="absolute inset-x-0 flex flex-wrap gap-x-5 gap-y-1 text-supporting text-ink-2" style={{ top: lineY + 22 }} data-testid="hv2-timeline-legend">
            {order.map((i) => (
              <li key={i}>
                {legs[i].label} · <b className="font-bold tabular-nums text-ink">{legs[i].amount_display}</b> · {legs[i].lands_when}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {/* Phone: the legs as rows, each opening on a tap */}
      <ul className="mt-1 divide-y divide-line sm:hidden" data-testid="hv2-timeline-rows">
        {legs.map((l, i) => (
          <li key={`${l.label}-${i}`} data-testid={`hv2-leg-row-${i}`}>
            <details className="group">
              <summary className="flex min-h-8 cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden">
                <Glyph state={l.state} className="size-4 shrink-0" />
                <span className="min-w-0 flex-1 text-sm text-ink-2">{l.label}</span>
                <span className="text-sm font-bold tabular-nums text-ink">{l.amount_display}</span>
              </summary>
              <div className="pb-2 pl-6">
                <StateWord state={stateKey(l.state) ?? "planned"} className="mb-1">
                  {l.state_text}
                </StateWord>
                <Details leg={l} />
              </div>
            </details>
          </li>
        ))}
        <li className="hidden items-baseline justify-between py-2 text-sm">
          <span className="text-ink-3">{t("hv2.timeline.total")}</span>
          <b className="font-display text-base font-bold tabular-nums text-brand-600">{total}</b>
        </li>
      </ul>
    </div>
  );
}
