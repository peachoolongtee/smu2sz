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
  const cell = "border-b border-line px-2 py-2 align-top text-sm text-ink sm:px-3";
  const word = (text: string | null | undefined, bad = false) => (text ? <span className={bad ? "text-bad-fg" : ""}>{text}</span> : NONE);
  return (
    <section aria-labelledby="deal-outcomes-title" data-testid="deal-outcomes">
      {heading ? (
        <h3 id="deal-outcomes-title" className="type-section mb-3 text-ink">
          {t("deals.out.title")}
        </h3>
      ) : null}
      <div className="overflow-x-auto" data-testid="deal-outcome-scroll">
        <table className="w-full min-w-[420px] table-fixed border-separate border-spacing-0" data-testid="deal-outcome-table">
          <caption className="sr-only">{t("deals.out.table")}</caption>
          <colgroup>
            <col className="w-[28%]" />
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
                  {p.authority_short_text ? <StateWord tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"}>{p.authority_short_text}</StateWord> : NONE}
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
 * The headroom dot plot (section 5): one row per response on one horizontal scale; the reserve a vertical amber dashed line labelled with `floor_short`; each response a dot at its lowest cash
 * labelled with `lowest_short` (and its day); below the reserve the dot is red, on or above it ink. Positions are scaled from the fen numbers only. The dots slide in over 300 ms on first paint
 * and are in place at once under reduced motion.
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
  const x = `calc(7.5rem + (100% - 7.5rem) * ${plot.reserveAt / 100})`;
  return (
    <figure className="m-0 mt-5" data-testid="deal-headroom" aria-label={t("deals.plot.aria")}>
      <figcaption className="mb-1 text-supporting font-bold text-ink-3">{t("deals.plot.title")}</figcaption>
      <div className="relative">
        {/* The reserve: one amber dashed line through every row, labelled once with the server's words. */}
        <span aria-hidden className="absolute bottom-0 top-5 border-l-2 border-dashed border-f-amber-ink" style={{ left: x }} data-testid="deal-headroom-reserve" />
        <p className="relative m-0 h-5 text-supporting font-bold text-f-amber-ink" data-testid="deal-headroom-reserve-label">
          <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: x }}>
            {t("biz.picture.reserve", { amount: picture.floor_short })}
          </span>
        </p>
        <ul className="m-0 list-none space-y-1 p-0">
          {plot.dots.map((d) => (
            <li key={d.key} className="grid h-12 grid-cols-[7.5rem_minmax(0,1fr)] items-center" data-testid="deal-headroom-row" data-below={d.below ? "true" : "false"}>
              <span className="pr-2 text-sm font-bold text-ink">{d.label}</span>
              <span className="relative block h-full border-b border-line">
                <span className={`absolute top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center ${reduced ? "" : "transition-[left] duration-300 ease-out"}`} style={{ left: settled ? `${d.at}%` : "0%" }} data-testid="deal-headroom-dot">
                  <span aria-hidden className={`size-3.5 rounded-pill ${d.below ? "bg-bad-solid" : "bg-f-ink"}`} />
                  <span className={`mt-0.5 whitespace-nowrap font-display text-supporting font-bold tabular-nums ${d.below ? "text-bad-fg" : "text-ink"}`}>
                    {d.short}
                    {d.when ? <span className="font-normal text-ink-3"> · {d.when}</span> : null}
                  </span>
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  );
}
