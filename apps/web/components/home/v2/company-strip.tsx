"use client";

import { useId, useState, type ReactNode } from "react";
import { DashedRingIcon, RingDotIcon } from "@/components/icons";
import { Card } from "@/components/ui";
import { TONE_INK, TONE_MARK } from "@/components/ui/state-word-model";
import { useI18n } from "@/lib/i18n";
import type { HomeTone, HomeV2 } from "@/lib/types";

/** The figure's colour comes from its meaning and from the state vocabulary's tones only: green when the cash is above the minimum, amber at it, red below it. A safe lowest figure is the plain ink. */
const FIGURE: Record<HomeTone, string> = { ok: "text-ink", warn: "text-warn-fg", bad: "text-bad-fg", neutral: "text-ink" };

type Buffer = HomeV2["kpis"]["cash_available"]["buffer"];

/**
 * A thin scale that tells what the number cannot: where the minimum sits and where today's cash is against it. Not a progress bar (nothing fills). The fen only place
 * the two marks; the words are the server's: `minimum_text` under the mark and the short `headroom_text` above the dot in green (until the server sends them, the
 * dictionary's "min" and the minimum's own display, and no headroom: the cell's note sentence says it).
 */
export function CashBufferIndicator({ buffer }: { buffer: Buffer }) {
  const { t } = useI18n();
  const hi = Math.max(buffer.cash_fen, buffer.min_fen, 1) * 1.25;
  const lo = Math.min(0, buffer.cash_fen * 1.25);
  const at = (fen: number) => Math.min(Math.max(((fen - lo) / (hi - lo)) * 100, 0), 100);
  const min = at(buffer.min_fen);
  const cash = at(buffer.cash_fen);
  const clamp = (pos: number) => Math.min(Math.max(pos, 14), 86);
  return (
    <div aria-hidden className="mt-2" data-testid="home-buffer" data-min={min.toFixed(0)} data-cash={cash.toFixed(0)}>
      <div className="relative h-5">
        {buffer.headroom_text ? (
          <span className="absolute -translate-x-1/2 whitespace-nowrap text-supporting font-bold text-ok-fg" style={{ left: `${clamp(cash)}%` }} data-testid="home-buffer-headroom">
            {buffer.headroom_text}
          </span>
        ) : null}
      </div>
      <div className="relative h-4">
        <span className="absolute inset-x-0 top-1.75 h-0.5 rounded-pill bg-line-strong" />
        <span className="absolute top-0.5 h-3 w-0.5 bg-warn-solid" style={{ left: `${min}%` }} data-testid="home-buffer-min" />
        <span className="absolute top-0.75 size-2.5 -translate-x-1/2 rounded-pill bg-brand-600 ring-2 ring-surface" style={{ left: `${cash}%` }} data-testid="home-buffer-cash" />
      </div>
      <div className="relative h-5">
        <span className="absolute -translate-x-1/2 whitespace-nowrap text-supporting text-warn-fg" style={{ left: `${clamp(min)}%` }} data-testid="home-buffer-min-text">
          {buffer.minimum_text ?? t("hv2.buffer.min", { amount: buffer.min_display })}
        </span>
      </div>
    </div>
  );
}

/**
 * One KPI: its eyebrow, its figure and one note line. A second sentence (`hint`) is not on the page until it is asked for: hovering or focusing the cell reveals it under
 * the cell (a quiet popover, `--dur-fast`, no motion under reduced motion), a tap does the same on a phone (and again to close), and the focusable cell names it as its
 * description either way.
 */
function Cell({
  id,
  eyebrow,
  eyebrowMark,
  value,
  valueClass,
  note,
  hint,
  children,
}: {
  id: string;
  eyebrow: string;
  eyebrowMark?: ReactNode;
  value: string;
  valueClass: string;
  note: string | null;
  hint?: string | null;
  children?: ReactNode;
}) {
  const uid = useId();
  const [tapped, setTapped] = useState(false);
  const hinted = Boolean(hint);
  return (
    <div
      className="group relative min-w-0 rounded-tile py-3 first:pt-0 last:pb-0 md:px-5 md:py-0 md:first:pl-0 md:last:pr-0"
      data-testid={`home-kpi-${id}`}
      {...(hinted ? { tabIndex: 0, role: "group", "aria-labelledby": `${uid}-eyebrow`, "aria-describedby": `${uid}-hint`, onClick: () => setTapped((o) => !o), onKeyDown: (e: React.KeyboardEvent) => e.key === "Escape" && tapped && (e.stopPropagation(), setTapped(false)), "data-open": tapped } : {})}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 md:block">
        <p id={`${uid}-eyebrow`} className="flex items-center gap-1.5 text-meta font-extrabold tracking-[0.08em] text-ink-3" data-testid={`home-kpi-${id}-eyebrow`}>
          {eyebrowMark}
          {eyebrow}
        </p>
        <p className={`type-value break-words md:mt-1.5 ${valueClass}`} data-testid={`home-kpi-${id}-value`}>
          {value}
        </p>
      </div>
      {note ? (
        <p className="mt-1 text-pretty text-supporting text-ink-2 md:mt-1.5" data-testid={`home-kpi-${id}-note`}>
          {note}
        </p>
      ) : null}
      {children}
      {hinted ? (
        <p
          id={`${uid}-hint`}
          className={`pointer-events-none invisible absolute inset-x-0 top-full z-20 mt-1 rounded-tile border border-line bg-surface p-3 text-pretty text-supporting text-ink-2 opacity-0 shadow-pop motion-safe:transition-[opacity,visibility] motion-safe:duration-(--dur-fast) motion-safe:ease-ui group-hover:visible group-hover:opacity-100 group-focus-visible:visible group-focus-visible:opacity-100 group-data-[open=true]:visible group-data-[open=true]:opacity-100`}
          data-testid={`home-kpi-${id}-hint`}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The company strip: three KPIs in one `Card`, hairline dividers between (rows on a phone, columns from `md`). Company-wide, never a customer's and never hypothetical.
 * Every eyebrow, figure, note and hint is the server's string; the browser chooses the colour by the tone and the glyph by the state vocabulary, and nothing else. Planned
 * funding wears the planned state's dashed ring and blue (arranged funding the arranged ring and the same blue); no sparklines, the cash cell has the buffer scale.
 */
export function CompanyStrip({ kpis }: { kpis: HomeV2["kpis"] }) {
  const { t } = useI18n();
  const { cash_available: cash, lowest_ahead: low, funding } = kpis;
  // The headroom and the minimum sit on the scale when the server sends their words; until then the one note line says it.
  const scaleSaysIt = Boolean(cash.buffer.headroom_text);
  const funded = funding.state === "PROPOSED" ? { Icon: DashedRingIcon } : funding.state === "ARRANGED" ? { Icon: RingDotIcon } : null;
  const withPlan = low.with_plan ?? null;
  return (
    <Card id="home-v2-strip" labelledBy="home-v2-strip-name">
      <h2 id="home-v2-strip-name" className="sr-only">
        {t("hv2.strip")}
      </h2>
      <div className="grid divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
        <Cell id="cash" eyebrow={cash.eyebrow} value={cash.value_display} valueClass={cash.tone === "ok" ? "text-ok-fg" : FIGURE[cash.tone ?? "neutral"]} note={scaleSaysIt ? null : cash.note}>
          <CashBufferIndicator buffer={cash.buffer} />
        </Cell>
        <Cell id="lowest" eyebrow={low.eyebrow} value={low.value_display} valueClass={FIGURE[low.tone ?? "neutral"]} note={low.note} hint={withPlan ? null : low.with_plan_hint}>
          {withPlan ? (
            <p className={`mt-1 flex items-center gap-1.5 text-supporting font-bold tabular-nums ${TONE_INK.info}`} data-testid="home-kpi-lowest-plan">
              <DashedRingIcon className={`size-3.5 shrink-0 ${TONE_MARK.info}`} />
              {withPlan.label} {withPlan.value_text}
            </p>
          ) : null}
        </Cell>
        <Cell
          id="funding"
          eyebrow={funding.eyebrow}
          eyebrowMark={funded ? <funded.Icon className={`size-3.5 shrink-0 ${TONE_MARK.info}`} /> : null}
          value={funding.value_display}
          valueClass={funded ? TONE_INK.info : "text-ink"}
          note={funding.note}
          hint={funding.hint}
        />
      </div>
    </Card>
  );
}
