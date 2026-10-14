"use client";

import { useEffect, useState } from "react";
import { StateWord } from "@/components/ui/state-word";
import { useI18n } from "@/lib/i18n";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import type { OfferPictureView, PicturePath } from "@/lib/types";
import { headroomPlot } from "./deal-model";
import { AUTH_TONE, NONE } from "./flow-parts";

/**
 * Financial outcomes before the curves (round three, section 5): the outcome table, one column per response (lowest cash, when, the reserve against it, the financing needed, whether FLOW can send
 * it), then the headroom dot plot under it. Every cell is one server word; no cell is the browser's sentence. "Safe" never appears: survival and flexibility are different words.
 */
export function FinancialOutcomes({ picture, paths, heading = true }: { picture: Pick<OfferPictureView, "floor_fen" | "floor_short">; paths: PicturePath[]; heading?: boolean }) {
  const { t } = useI18n();
  if (!paths.length) return null;
  const rowHead = "border-b border-line py-2 pr-3 text-left align-top text-supporting font-bold text-ink-3";
  const cell = "border-b border-line px-1.5 py-2 align-top text-sm text-ink sm:px-3";
  const word = (text: string | null | undefined, bad = false) => (text ? <span className={bad ? "text-bad-fg" : ""}>{text}</span> : NONE);
  return (
    <section aria-labelledby="deal-outcomes-title" data-testid="deal-outcomes">
      {heading ? (
        <h3 id="deal-outcomes-title" className="type-section mb-3 text-ink">
          {t("deals.out.title")}
        </h3>
      ) : null}
      <div className="overflow-x-auto" role="region" aria-label={t("deals.out.table")} tabIndex={0} data-testid="deal-outcome-scroll">
        <table className="w-full table-fixed border-separate border-spacing-0 max-sm:table-auto" data-testid="deal-outcome-table">
          <caption className="sr-only">{t("deals.out.table")}</caption>
          <colgroup>
            <col className="w-[24%] sm:w-[28%]" />
            {paths.map((p) => (
              <col key={p.key} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <td className="border-b border-line-strong" />
              {paths.map((p) => (
                <th key={p.key} scope="col" className="border-b border-line-strong px-2 py-2 text-left align-bottom text-sm font-bold text-ink sm:px-3">
                  {p.kind === "asked" ? t("deals.cost.col.asked") : p.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr data-testid="deal-outcome-row-lowest">
              <th scope="row" className={rowHead}>
                {t("deals.out.lowest")}
              </th>
              {paths.map((p) => (
                <td key={p.key} className={`${cell} font-display font-bold tabular-nums`}>
                  {word(p.lowest_short, p.first_breach_when !== null)}
                </td>
              ))}
            </tr>
            <tr data-testid="deal-outcome-row-when">
              <th scope="row" className={rowHead}>
                {t("deals.out.when")}
              </th>
              {paths.map((p) => (
                <td key={p.key} className={cell}>
                  {word(p.lowest_when)}
                </td>
              ))}
            </tr>
            <tr data-testid="deal-outcome-row-reserve">
              <th scope="row" className={rowHead}>
                {t("deals.out.reserve")}
              </th>
              {paths.map((p) => (
                <td key={p.key} className={cell}>
                  {word(p.reserve_state_text, p.first_breach_when !== null)}
                </td>
              ))}
            </tr>
            <tr data-testid="deal-outcome-row-financing">
              <th scope="row" className={rowHead}>
                {t("deals.out.financing")}
              </th>
              {paths.map((p) => (
                <td key={p.key} className={cell}>
                  {word(p.financing_needed_text)}
                </td>
              ))}
            </tr>
            <tr data-testid="deal-outcome-row-send">
              <th scope="row" className={rowHead}>
                {t("deals.out.send")}
              </th>
              {paths.map((p) => (
                <td key={p.key} className={cell}>
                  {p.authority_short_text ? <StateWord wrap tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"}>{p.authority_short_text}</StateWord> : NONE}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <HeadroomPlot picture={picture} paths={paths} />
    </section>
  );
}

/**
 * The headroom dot plot (section 5): one row per response on one horizontal scale; the reserve a vertical amber dashed line labelled once with `floor_short`; each response a dot at its lowest cash;
 * below the reserve the dot is red, on or above it ink. Positions are scaled from the fen numbers only, with room beyond the highest mark. The words of each dot (`lowest_short` and its day) are
 * in a column of their own at the row's right end, so no label crosses the reserve line, a dot or another label. The dots slide in over the kit's expanded duration on first paint and are in place at
 * once under reduced motion.
 */
export function HeadroomPlot({ picture, paths }: { picture: Pick<OfferPictureView, "floor_fen" | "floor_short">; paths: PicturePath[] }) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const [placed, setPlaced] = useState(false);
  useEffect(() => {
    const id = window.requestAnimationFrame(() => setPlaced(true));
    return () => window.cancelAnimationFrame(id);
  }, []);
  const plot = headroomPlot(paths, picture.floor_fen);
  if (!plot) return null;
  const settled = reduced || placed;
  // The plot's own columns: the response's name, the track, the dot's words.
  const cols = "grid-cols-[5.5rem_minmax(0,1fr)_7.5rem] sm:grid-cols-[7.5rem_minmax(0,1fr)_10rem]";
  const x = (at: number) => `calc(var(--plot-name) + (100% - var(--plot-name) - var(--plot-value)) * ${at / 100})`;
  return (
    <figure className="m-0 mt-5 [--plot-name:5.5rem] [--plot-value:7.5rem] sm:[--plot-name:7.5rem] sm:[--plot-value:10rem]" data-testid="deal-headroom" aria-label={t("deals.plot.aria")}>
      <figcaption className="mb-1 text-supporting font-bold text-ink-3">{t("deals.plot.title")}</figcaption>
      <div className="relative">
        {/* The reserve: one amber dashed line through every row, labelled once, the label on the side of the line that has the room. */}
        <span aria-hidden className="absolute bottom-0 top-6 border-l-2 border-dashed border-f-amber-ink" style={{ left: x(plot.reserveAt) }} data-testid="deal-headroom-reserve" />
        <p className="m-0 flex h-6 items-center gap-2 text-supporting font-bold text-f-amber-ink" data-testid="deal-headroom-reserve-label">
          <i aria-hidden className="inline-block w-[18px] border-t-2 border-dashed border-f-amber-ink" />
          {t("biz.picture.reserve", { amount: picture.floor_short })}
        </p>
        <ul className="m-0 list-none p-0">
          {plot.dots.map((d) => (
            <li key={d.key} className={`grid h-12 items-center ${cols}`} data-testid="deal-headroom-row" data-below={d.below ? "true" : "false"}>
              <span className="pr-2 text-sm font-bold text-ink">{d.label}</span>
              <span className="relative block h-full border-b border-line">
                <span className={`absolute top-1/2 size-0 ${reduced ? "" : "transition-[left] duration-(--dur-expanded) ease-out"}`} style={{ left: settled ? `${d.at}%` : "0%" }} data-testid="deal-headroom-dot">
                  <span aria-hidden className={`absolute -left-[7px] -top-[7px] block size-3.5 rounded-pill ${d.below ? "bg-bad-solid" : "bg-f-ink"}`} />
                </span>
              </span>
              <span className={`pl-3 text-right font-display text-sm font-bold leading-tight tabular-nums ${d.below ? "text-bad-fg" : "text-ink"}`} data-testid="deal-headroom-words">
                {d.short}
                {d.when ? <span className="block font-sans text-supporting font-normal text-ink-3">{d.when}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  );
}
