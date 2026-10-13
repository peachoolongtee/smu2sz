"use client";

import { useId, useState } from "react";
import { StateWord } from "@/components/ui/state-word";
import { stateKey, STATE_LOOK, TONE_MARK } from "@/components/ui/state-word-model";
import { CheckCircleIcon, CheckIcon, DashedRingIcon, RingDotIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";
import type { HomeV2Leg } from "@/lib/types";

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
  const [shown, setShown] = useState<number | null>(null);
  // The line runs from today (0) to the plan's last repayment day (else its last landing day); a marker sits at the day its leg lands. The days only place a mark.
  const lands = legs.map((l) => l.lands_day).filter((d): d is number => typeof d === "number");
  const repaid = legs.map((l) => l.repaid_day).filter((d): d is number => typeof d === "number");
  const placed = lands.length === legs.length && Math.max(...lands, ...repaid) > 0;
  const end = Math.max(...repaid, ...(repaid.length ? [] : lands), 1);
  const big = Math.max(...legs.map((l) => l.amount_fen ?? 0), 0);
  const left = (l: HomeV2Leg, i: number) => (placed ? Math.min(Math.max(((l.lands_day ?? 0) / end) * 100, 0), 100) : legs.length === 1 ? 0 : (i / (legs.length - 1)) * 100);
  // Sized by the leg's amount in a 10 to 18 px range (the largest is 18); alike when the server sends no amounts.
  const size = (l: HomeV2Leg) => (big > 0 && l.amount_fen ? 10 + Math.round((l.amount_fen / big) * 8) : 14);
  return (
    <div className="min-w-0" data-testid="hv2-timeline" data-legs={legs.length}>
      <p className="text-supporting text-ink-3">{t("hv2.timeline.title")}</p>
      {/* Desktop: the timeline */}
      <div className="relative mt-2 hidden h-[88px] sm:block" role="list" aria-label={t("hv2.timeline.title")} onKeyDown={(e) => e.key === "Escape" && setShown(null)}>
        <span aria-hidden className="absolute left-0 right-[8.5rem] top-3.5 h-0.5 rounded-pill bg-line-strong" />
        {legs.map((l, i) => {
          const px = size(l);
          const open = shown === i;
          return (
            <div key={`${l.label}-${i}`} role="listitem" className="absolute top-0 -translate-x-1/2" style={{ left: `calc(0.75rem + (100% - 8.5rem - 1.5rem) * ${left(l, i) / 100})` }} data-testid={`hv2-leg-${i}`} data-state={l.state}>
              <button
                type="button"
                aria-describedby={open ? `${uid}-${i}` : undefined}
                aria-expanded={open}
                aria-label={`${l.label}, ${l.amount_display}, ${l.state_text}`}
                onPointerEnter={() => setShown(i)}
                onPointerLeave={() => setShown((s) => (s === i ? null : s))}
                onFocus={() => setShown(i)}
                onBlur={() => setShown((s) => (s === i ? null : s))}
                onClick={() => setShown(open ? null : i)}
                className="relative mx-auto mt-0.5 grid size-6 place-items-center rounded-pill"
                data-testid={`hv2-leg-marker-${i}`}
              >
                <span className="grid place-items-center rounded-pill bg-brand-50 ring-2 ring-surface" style={{ width: px, height: px }} data-testid={`hv2-leg-dot-${i}`}>
                  <Glyph state={l.state} className="size-full" />
                </span>
              </button>
              <p className="mt-2 max-w-32 text-center text-supporting leading-tight text-ink-2">{l.label}</p>
              <p className="text-center text-sm font-bold tabular-nums text-ink">{l.amount_display}</p>
              <div
                id={`${uid}-${i}`}
                role="tooltip"
                hidden={!open}
                className="motion-reveal absolute left-1/2 top-full z-20 mt-1 w-64 -translate-x-1/2 rounded-tile bg-surface px-3.5 py-3 text-left shadow-pop"
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
        <div className="absolute right-0 top-0 w-32 text-right">
          <p className="mt-0.5 text-supporting text-ink-3">{t("hv2.timeline.total")}</p>
          <p className="font-display text-lg font-bold tabular-nums text-brand-600" data-testid="hv2-timeline-total">
            {total}
          </p>
        </div>
      </div>
      {/* Phone: the legs as rows, each opening on a tap */}
      <ul className="mt-1 divide-y divide-line sm:hidden" data-testid="hv2-timeline-rows">
        {legs.map((l, i) => (
          <li key={`${l.label}-${i}`} data-testid={`hv2-leg-row-${i}`}>
            <details className="group">
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden">
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
        <li className="flex items-baseline justify-between py-2 text-sm">
          <span className="text-ink-3">{t("hv2.timeline.total")}</span>
          <b className="font-display text-base font-bold tabular-nums text-brand-600">{total}</b>
        </li>
      </ul>
    </div>
  );
}
