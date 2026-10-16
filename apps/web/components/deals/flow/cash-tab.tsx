"use client";

import { useRef, useState } from "react";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { getOfferScenarios } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";
import { pairWords } from "@/lib/point-comparison";
import type { OfferPictureView, PicturePath, PictureScenarioRow } from "@/lib/types";
import { useWidth } from "@/components/business/cash-picture";
import { cashScale, dayTicks, lineWindow } from "./deal-model";

/**
 * Cash impact (Deals redesign, board 3): two charts, each answering one question, then the business consequences.
 *   1. "Does cash stay above your minimum?": one thin bar per choice to its lowest cash on a real scale (the server's labelled ticks), the minimum as a dashed line through every bar, the server's words
 *      for the lowest point on the right.
 *   2. "How your cash moves, day by day": exactly two lines, the request (dashed, risk red) and the chosen reply (ink), a toggle between the replies, the band below the minimum, the server's sentence
 *      on the days below, "Why the lines differ" (the server's `cause_lines`) and the two lowest points.
 * The browser positions marks from `*_fen` and the series' days only; every label and sentence is the server's or the dictionary's.
 */
export function CashTab({ offerId, picture, paths }: { offerId: string; picture: OfferPictureView; paths: PicturePath[] }) {
  const asked = paths.find((p) => p.kind === "asked") ?? null;
  const replies = paths.filter((p) => p.kind === "reply");
  return (
    <div className="space-y-8" data-testid="deal-cash">
      <LowestBars picture={picture} paths={paths} />
      <MoveChart picture={picture} asked={asked} replies={replies} />
      <BusinessConsequences offerId={offerId} />
    </div>
  );
}

const tickClass = "absolute top-0 whitespace-nowrap text-supporting text-ink-2";

/** Chart 1: one thin bar per choice to its lowest cash. */
function LowestBars({ picture, paths }: { picture: OfferPictureView; paths: PicturePath[] }) {
  const { t } = useI18n();
  const drawn = paths.filter((p): p is PicturePath & { lowest_fen: number } => typeof p.lowest_fen === "number");
  if (!drawn.length) return null;
  const scale = cashScale([...drawn.map((p) => p.lowest_fen), picture.floor_fen], picture.axis);
  const floorAt = scale.at(picture.floor_fen);
  const rec = paths.find((p) => p.kind === "reply" && p.recommended)?.key ?? null;
  const fill = (p: PicturePath & { lowest_fen: number }) => (p.first_breach_when !== null ? "bg-bad-solid" : p.key === rec ? "bg-f-ink" : "bg-ink-3");
  return (
    <section aria-labelledby="deal-lowest-title" className="space-y-4" data-testid="deal-lowest">
      <div>
        <h2 id="deal-lowest-title" className="type-section text-ink">
          {t("deals.cash.lowest.title", { amount: picture.floor_short })}
        </h2>
        <p className="mt-1.5 text-[15px] text-ink-2">{t("deals.cash.lowest.sub")}</p>
      </div>
      <ul className="m-0 list-none space-y-5 p-0 md:space-y-3">
        {drawn.map((p) => (
          <li key={p.key} className="grid grid-cols-1 gap-x-5 gap-y-2 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_minmax(0,17rem)] md:items-center" data-testid="deal-lowest-row" data-below={p.first_breach_when !== null ? "true" : "false"}>
            <p className="m-0 text-[15px] font-bold text-ink md:order-1">
              {p.label}
              {p.key === rec ? <span className="ml-2 text-supporting font-bold text-f-purple-ink">{t("deals.choices.recommended")}</span> : null}
            </p>
            <div className="relative h-2.5 rounded-pill bg-subtle md:order-2" aria-hidden>
              <div className={`absolute inset-y-0 left-0 rounded-pill ${fill(p)}`} style={{ width: `${scale.at(p.lowest_fen)}%` }} data-testid="deal-lowest-bar" />
              <span className="absolute -inset-y-1.5 border-l-2 border-dashed border-f-amber-ink" style={{ left: `${floorAt}%` }} data-testid="deal-lowest-floor" />
            </div>
            <p className="m-0 text-[15px] md:order-3">
              <span className={`font-bold tabular-nums ${p.first_breach_when !== null ? "text-bad-fg" : "text-ink"}`}>{p.lowest_short}</span>
              {p.lowest_when ? <span className="ml-1.5 text-ink-2">{p.lowest_when}</span> : null}
              {p.reserve_state_text ? <span className={`block text-supporting ${p.first_breach_when !== null ? "text-bad-fg" : "text-ink-2"}`}>{p.reserve_state_text}</span> : null}
            </p>
          </li>
        ))}
      </ul>
      {/* The scale: the server's labelled ticks under the bars' column (the grid's middle column from the tablet width). */}
      <div className="grid grid-cols-1 gap-x-5 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_minmax(0,17rem)]">
        <div className="relative h-5 md:col-start-2" aria-hidden data-testid="deal-lowest-ticks">
          {scale.ticks.map((k) => (
            <span key={k.label} className={tickClass} style={{ left: `${k.at}%`, transform: k.at < 4 ? undefined : k.at > 96 ? "translateX(-100%)" : "translateX(-50%)" }}>
              {k.label}
            </span>
          ))}
        </div>
      </div>
      <p className="flex items-center gap-2 text-supporting text-ink-2">
        <i aria-hidden className="inline-block w-[18px] border-t-2 border-dashed border-f-amber-ink" />
        {t("biz.picture.reserve", { amount: picture.floor_short })}
      </p>
    </section>
  );
}

/** Chart 2: the request against the chosen reply, day by day. */
function MoveChart({ picture, asked, replies }: { picture: OfferPictureView; asked: PicturePath | null; replies: PicturePath[] }) {
  const { t } = useI18n();
  const [pick, setPick] = useState<string | null>(null);
  // The days row is as wide as the plot: its measured width decides how many day labels fit without touching.
  const daysRef = useRef<HTMLDivElement>(null);
  const plotWidth = useWidth(daysRef);
  const reply = replies.find((p) => p.key === pick) ?? replies.find((p) => p.recommended) ?? replies[0] ?? null;
  const today = picture.day;
  const days = picture.picture_days ?? 0;
  const askedPts = lineWindow(asked?.series, today, days);
  const replyPts = lineWindow(reply?.series, today, days);
  if (!askedPts.length && !replyPts.length) return null;
  const scale = cashScale([...askedPts, ...replyPts].map((p) => p.fen).concat(picture.floor_fen), picture.axis);
  const y = (fen: number) => 100 - scale.at(fen);
  const floorY = y(picture.floor_fen);
  const poly = (pts: typeof askedPts) => pts.map((p) => `${p.x},${y(p.fen)}`).join(" ");
  const xTicks = dayTicks(picture.moments, today, days, plotWidth);
  const breach = asked && asked.first_breach_when !== null;
  // The server's words for the difference between the two lines: the cause, per line, as of the last day drawn.
  const pointOf = (key: string) => (key === asked?.key ? asked : reply)?.series?.find((s) => s.day === (replyPts[replyPts.length - 1] ?? askedPts[askedPts.length - 1])?.day);
  const words = asked && reply ? pairWords(asked, reply, (k) => (k === reply.key ? pointOf(reply.key) : pointOf(asked.key))) : null;
  const askedLabel = t("deals.cash.line.asked");
  const replyLabel = reply ? t("deals.cash.line.reply", { label: reply.label }) : "";
  const tile = "rounded-tile bg-subtle px-4 py-3.5";
  return (
    <section aria-labelledby="deal-move-title" className="space-y-4 border-t border-line pt-7" data-testid="deal-chart">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h2 id="deal-move-title" className="type-section text-ink">
            {t("deals.cash.move.title")}
          </h2>
          <p className="mt-1.5 text-[15px] text-ink-2">{t("deals.cash.move.sub")}</p>
        </div>
        {replies.length > 1 ? (
          <div role="group" aria-label={t("deals.cash.compare")} className="flex flex-wrap gap-2" data-testid="deal-reply-toggle">
            {replies.map((p) => (
              <button
                key={p.key}
                type="button"
                aria-pressed={reply?.key === p.key}
                onClick={() => setPick(p.key)}
                className={`motion-press min-h-11 rounded-pill border px-4 text-sm ${reply?.key === p.key ? "border-f-purple bg-f-purple font-bold text-f-btn-ink" : "border-line-ui bg-surface text-ink hover:bg-subtle"}`}
                data-testid={`deal-reply-${p.key}`}
              >
                {p.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <ul className="m-0 flex list-none flex-wrap gap-x-6 gap-y-2 p-0 text-sm text-ink-2" data-testid="deal-chart-legend">
        {reply ? (
          <li className="inline-flex items-center gap-2">
            <i aria-hidden className="inline-block w-[22px] border-t-[3px] border-f-ink" />
            {replyLabel}
          </li>
        ) : null}
        {asked ? (
          <li className="inline-flex items-center gap-2">
            <i aria-hidden className="inline-block w-[22px] border-t-[3px] border-dashed border-bad-fg" />
            {askedLabel}
          </li>
        ) : null}
        <li className="inline-flex items-center gap-2">
          <i aria-hidden className="inline-block h-2.5 w-[22px]" style={{ background: "var(--color-chart-danger)" }} />
          {t("hv2.chart.below")}
        </li>
      </ul>
      <div className="grid grid-cols-[3.75rem_minmax(0,1fr)] gap-x-2 pt-3 sm:grid-cols-[4.5rem_minmax(0,1fr)]" data-testid="deal-chart-picture">
        <div className="relative h-72" aria-hidden>
          {scale.ticks.map((k) => (
            <span key={k.label} className="absolute right-0 -translate-y-1/2 whitespace-nowrap text-supporting text-ink-2" style={{ top: `${100 - k.at}%` }}>
              {k.label}
            </span>
          ))}
          <span className="absolute right-0 -translate-y-1/2 whitespace-nowrap text-supporting font-bold text-f-amber-ink" style={{ top: `${floorY}%` }} data-testid="deal-chart-floor-label">
            {picture.floor_short}
          </span>
        </div>
        <div className="relative h-72" role="img" aria-label={t("deals.cash.aria", { reply: reply?.label ?? "", a: asked?.lowest_short ?? "", aw: asked?.lowest_when ?? "", b: reply?.lowest_short ?? "", bw: reply?.lowest_when ?? "" })}>
          {/* The band below the minimum, the minimum as a dashed line, and the two lines (positions from fen and day numbers only). */}
          <div aria-hidden className="absolute inset-x-0 bottom-0" style={{ top: `${floorY}%`, background: "var(--color-chart-danger)" }} data-testid="deal-chart-band" />
          <span aria-hidden className="absolute inset-x-0 border-t-[1.5px] border-dashed border-f-amber-ink" style={{ top: `${floorY}%` }} data-testid="deal-chart-reserve" />
          {scale.ticks.map((k) => (
            <span key={k.label} aria-hidden className="absolute inset-x-0 border-t border-line" style={{ top: `${100 - k.at}%` }} />
          ))}
          <svg aria-hidden className="absolute inset-0 size-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
            {askedPts.length ? <polyline points={poly(askedPts)} fill="none" stroke="var(--color-bad-fg)" strokeWidth="3" strokeDasharray="8 6" vectorEffect="non-scaling-stroke" data-testid="deal-line-asked" /> : null}
            {replyPts.length ? <polyline points={poly(replyPts)} fill="none" stroke="var(--color-f-ink)" strokeWidth="3" vectorEffect="non-scaling-stroke" data-testid="deal-line-reply" /> : null}
          </svg>
          {breach && asked?.band_text ? (
            <p className="absolute bottom-3 right-3 m-0 rounded-tile border border-bad-fg bg-surface px-3 py-1.5 text-sm font-bold text-bad-fg" data-testid="deal-chart-below">
              {asked.band_text}
            </p>
          ) : null}
        </div>
        <div />
        <div ref={daysRef} className="relative h-6" aria-hidden data-testid="deal-chart-days">
          {xTicks.map((k) => (
            <span key={k.label} className={tickClass} style={{ left: `${k.x}%`, transform: k.align === "end" ? "translateX(-100%)" : k.align === "center" ? "translateX(-50%)" : undefined }}>
              {k.label}
            </span>
          ))}
        </div>
      </div>
      <div className="grid items-start gap-3 md:grid-cols-3">
        {words?.causeLines?.length || words?.cause ? (
          <div className={tile} data-testid="deal-why-lines">
            <p className="text-sm text-ink-2">{t("deals.cash.why")}</p>
            {words?.causeLines?.length ? (
              <ul className="m-0 mt-1.5 list-none space-y-2 p-0 text-[15px] text-ink">
                {words.causeLines.map((l) => (
                  <li key={l.label}>
                    <span className="block text-supporting font-bold text-ink-2">{l.label}</span>
                    <ul className="m-0 list-disc space-y-0.5 pl-5">
                      {l.items.map((it) => (
                        <li key={it}>{it}</li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1.5 text-[15px] text-ink">{words?.cause}</p>
            )}
          </div>
        ) : null}
        {asked?.lowest_short ? (
          <div className={tile} data-testid="deal-lowest-asked">
            <p className="text-sm text-ink-2">{t("deals.cash.lowest.of", { label: asked.label })}</p>
            <p className={`mt-1.5 font-display text-lg font-bold leading-snug sm:text-xl ${asked.first_breach_when !== null ? "text-bad-fg" : "text-ink"}`}>
              <span>{asked.lowest_short}</span>
              {asked.lowest_when ? <span className="ml-2 font-sans text-sm font-normal text-ink-2">{asked.lowest_when}</span> : null}
            </p>
          </div>
        ) : null}
        {reply?.lowest_short ? (
          <div className={tile} data-testid="deal-lowest-reply">
            <p className="text-sm text-ink-2">{t("deals.cash.lowest.of", { label: reply.label })}</p>
            <p className="mt-1.5 font-display text-lg font-bold leading-snug text-ink sm:text-xl">
              <span>{reply.lowest_short}</span>
              {reply.lowest_when ? <span className="ml-2 font-sans text-sm font-normal text-ink-2">{reply.lowest_when}</span> : null}
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

/**
 * Business consequences (round three, section 4): the scenarios apart from the responses, one read-only card at a time behind three controls (Continue current position, Buyer pays 30 days late,
 * Buyer stops placing new orders; the labels are the server's). A card says its assumption first ("an estimate under the model's assumptions, not a forecast"), then its rows: for the customer
 * loss, what is lost in billings and in contribution, the effect on cash and the invoice that stays payable, each its own sentence; for the late payment, the lowest cash of each response. Nothing
 * here is the browser's; with no `scenarios` from the server nothing is drawn.
 */
export function BusinessConsequences({ offerId }: { offerId: string }) {
  const { t, lang } = useI18n();
  const [pick, setPick] = useState<string | null>(null);
  // The scenarios are their own read, made when Cash impact opens (composing them is slow on a cold start): a skeleton while it is on its way, the error with Retry when it fails.
  const read = useAsync(() => getOfferScenarios(offerId, lang), [offerId, lang]);
  if (read.error)
    return (
      <section aria-labelledby="deal-biz-title" className="border-t border-line pt-7" data-testid="deal-scenarios-failed">
        <h3 id="deal-biz-title" className="type-section mb-3 text-ink">
          {t("deals.biz.title")}
        </h3>
        <ErrorState error={read.error} onRetry={read.reload} />
      </section>
    );
  if (read.data === undefined)
    return (
      <section aria-labelledby="deal-biz-title" aria-busy className="border-t border-line pt-7" data-testid="deal-scenarios-loading">
        <h3 id="deal-biz-title" className="type-section mb-3 text-ink">
          {t("deals.biz.title")}
        </h3>
        <LoadingBlock rows={3} />
      </section>
    );
  const scenarios = read.data;
  if (!scenarios?.length) return null;
  const current = scenarios.find((x) => x.key === pick) ?? scenarios[0];
  // The server's rows say each sentence with its label; a card that carries only the named sentences (an older shape) is read from them.
  const named: PictureScenarioRow[] = [
    ...(current.lost_billings_text ? [{ key: "lost_billings", label: t("deals.biz.billings"), text: current.lost_billings_text }] : []),
    ...(current.lost_contribution_text ? [{ key: "lost_contribution", label: t("deals.biz.contribution"), text: current.lost_contribution_text }] : []),
    ...(current.cash_effect_text ? [{ key: "cash_effect", label: t("deals.biz.cash"), text: current.cash_effect_text }] : []),
    ...(current.invoice_remains_text ? [{ key: "invoice_remains", label: t("deals.biz.invoice"), text: current.invoice_remains_text }] : []),
  ];
  const rows = current.rows?.length ? current.rows : named;
  return (
    <section aria-labelledby="deal-biz-title" className="border-t border-line pt-7" data-testid="deal-scenarios">
      <h3 id="deal-biz-title" className="type-section mb-3 text-ink">
        {t("deals.biz.title")}
      </h3>
      <SegmentedTabs value={current.key} onChange={setPick} label={t("deals.biz.tabs")} compact tabs={scenarios.map((s) => ({ value: s.key, label: s.label, testId: `deal-scenario-tab-${s.key}` }))} />
      <div className="mt-4 space-y-3 rounded-tile border border-line bg-subtle/50 p-4" data-testid="deal-scenario-card" data-scenario={current.key}>
        {current.assumption_text ? (
          <p className="max-w-[68ch] text-[15px] leading-snug text-ink" data-testid="deal-scenario-assumption">
            {current.assumption_text}
          </p>
        ) : null}
        {current.available === false && current.unavailable_text ? (
          <p className="max-w-[68ch] text-sm text-ink-2" role="status" data-testid="deal-scenario-unavailable">
            {current.unavailable_text}
          </p>
        ) : null}
        {rows.length ? (
          <dl className="divide-y divide-line" data-testid="deal-scenario-rows">
            {rows.map((r) => (
              <div key={r.key} className="py-2" data-testid={`deal-scenario-${r.key}`}>
                <dt className="flex flex-wrap items-baseline justify-between gap-x-3 text-supporting font-bold text-ink-3">
                  <span>{r.label}</span>
                  {r.lowest_short ? (
                    <span className="text-right text-sm text-ink" data-testid="deal-scenario-lowest">
                      <b className="font-display tabular-nums">{r.lowest_short}</b>
                      {r.lowest_when ? <span className="font-normal text-ink-3"> · {r.lowest_when}</span> : null}
                    </span>
                  ) : null}
                </dt>
                <dd className="m-0 mt-0.5 max-w-[68ch] text-sm text-ink">{r.text}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </section>
  );
}
