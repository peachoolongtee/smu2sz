"use client";

import Link from "next/link";
import { useState } from "react";
import { Disclosure } from "@/components/business/kit";
import { authorityText, authorityTone } from "@/components/deals/path-columns";
import { PathsBody, pathsUsable, type PathsState } from "@/components/deals/paths-section";
import { RecommendedResponse } from "@/components/deals/response";
import { AdvancedDetails } from "@/components/deals/workspace";
import { Button, ErrorState, LoadingBlock, StatePill, textLinkClass } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { Mode } from "@/lib/mode";
import type { OfferItem } from "@/lib/offer-items";
import type { DealView, Displayed, ExposureView, NegotiationView, Obligation, OfferPictureView, OfferView, OpenOffer, PicturePath, VerdictView } from "@/lib/types";
import { ExposureBand, StressToggle } from "./exposure-band";
import { ImpactTable } from "./impact-table";
import { eyebrowCls } from "./queue-list";

const RULE: Record<string, string> = { accept: "border-ok-solid", counter: "border-bad-solid", decline: "border-bad-solid", cannot: "border-bad-solid", needs_owner: "border-warn-solid" };
const RULE_INK: Record<string, string> = { accept: "text-ok-fg", counter: "text-bad-fg", decline: "text-bad-fg", cannot: "text-bad-fg", needs_owner: "text-warn-fg" };

/**
 * The selected deal, in the board's order: the customer, the verdict as the heading, what they ask, why (a red rule, the server's reasons), the one blue
 * card (FLOW's recommended reply, its cost, who decides, the one filled primary), the cash on each path with the exposure band, then the comparison and the
 * evidence behind one fold. Every sentence and figure is the server's or the dictionary's; the page decides nothing. The primary opens the existing send in place
 * (the bound option, the server's "This will" lines, the confirmation); it is replaced by that send while it is open, so there is never a second filled button.
 */
export function QueueDetail({
  deal,
  open,
  offer,
  verdict,
  negotiation,
  exposure,
  picture,
  paths,
  today,
  mode,
  customerHref,
  items,
  asks,
  busy,
  error,
  onCheck,
}: {
  deal: DealView;
  open: OpenOffer;
  offer: OfferView;
  verdict: VerdictView | null;
  negotiation: NegotiationView | null;
  exposure: ExposureView;
  /** The offer's picture: undefined while it is on its way, null when there is none (an older server, or a deal that has an outcome). */
  picture: OfferPictureView | null | undefined;
  paths: PathsState;
  today: number;
  mode: Mode;
  customerHref: string;
  items: OfferItem[];
  asks: Displayed<Obligation>[];
  busy: boolean;
  error: string | null;
  onCheck: () => void;
}) {
  const { t } = useI18n();
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [stress, setStress] = useState(false);
  const ws = verdict?.workspace ?? null;
  const buyer = exposure.concentration.buyer_name;
  const heading = open.headline_short ?? open.read_text ?? open.asks_text;
  const action = ws?.recommends.action ?? null;
  const asked = paths.paths.find((p) => p.kind === "asked") ?? null;
  const reply = paths.paths.find((p) => p.kind === "reply" && p.recommended) ?? null;
  const usable = Boolean(verdict && pathsUsable(picture, negotiation, verdict));
  const opened = reviewing === offer.offer.offer_id;
  const picked = paths.picked;
  const stressLine = stress && picked ? exposure.stress.paths[picked.key] : null;
  const cost = reply
    ? reply.cost_once_display
      ? t("dq.cost.once", { amount: reply.cost_once_display, buyer })
      : reply.cost_total_display
        ? t("dq.cost.total", { amount: reply.cost_total_display, basis: reply.cost_basis_text ?? "", buyer })
        : null
    : null;

  return (
    <div className="flex min-w-0 flex-col gap-3 sm:gap-4" data-testid="queue-detail" data-offer={offer.offer.offer_id}>
      {/* Announced once per selection, politely: the page does not move focus. */}
      <p role="status" aria-live="polite" className="sr-only" data-testid="queue-announce">
        {t("dq.selected", { title: heading })}
      </p>
      <p className={`${eyebrowCls} text-ink-3`}>
        {t("dq.eyebrow")} ·{" "}
        <Link href={customerHref} className="text-brand-700 hover:underline focus-visible:underline" data-testid="queue-detail-customer">
          {deal.counterparty_name} ›
        </Link>
      </p>
      <h2 tabIndex={-1} className="text-balance font-display text-xl font-extrabold leading-tight tracking-tight text-ink sm:text-[1.625rem]" data-testid="queue-heading">
        {heading}
      </h2>
      <p className="text-sm leading-normal text-ink-2 sm:text-[0.9375rem]" data-testid="queue-ask">
        {t("dq.ask", { buyer, asks: open.asks_text })}
      </p>

      {ws && ws.why_it_matters.reasons.length ? (
        <div className={`flex flex-col gap-1 border-l-[3px] py-0.5 pl-3.5 ${RULE[action ?? "counter"] ?? "border-line-strong"}`} data-testid="queue-why">
          <p className={`${eyebrowCls} ${RULE_INK[action ?? "counter"] ?? "text-ink-3"}`}>{t(`dq.why.${action ?? "counter"}` as DictKey)}</p>
          {ws.why_it_matters.reasons.slice(0, 2).map((r) => (
            <p key={r} className="text-[0.9375rem] leading-normal text-ink">
              {r}
            </p>
          ))}
        </div>
      ) : null}

      {negotiation && verdict ? (
        <RecommendedResponse v={verdict} offerId={offer.offer.offer_id} today={today} mode={mode} negotiation={negotiation} />
      ) : !verdict ? (
        <div className="flex flex-col gap-2 rounded-card border border-brand-100 bg-brand-50 p-4" data-testid="queue-check">
          <p className="text-sm text-ink-2">{open.action_text}</p>
          <div>
            <Button variant="primary" loading={busy} onClick={onCheck} data-testid="queue-check-button">
              {t("dq.check")}
            </Button>
          </div>
          {error ? <ErrorState error={error} /> : null}
        </div>
      ) : (
        <section aria-labelledby="dq-rec" className="flex flex-col gap-2 rounded-card border border-brand-100 bg-brand-50 p-3.5 sm:p-5" data-testid="queue-recommends">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <h3 id="dq-rec" className={`${eyebrowCls} text-brand-700`}>
              {reply ? t("dq.rec.eyebrow", { label: reply.label }) : t("dq.rec.plain")}
            </h3>
            {reply ? (
              <span data-testid="queue-authority" data-authority={reply.authority ?? ""}>
                <StatePill tone={authorityTone(reply)}>{authorityText(reply)}</StatePill>
              </span>
            ) : null}
          </div>
          <p className="font-display text-base font-bold leading-snug text-ink sm:text-[1.0625rem]" data-testid="queue-option">
            {reply ? (reply.reply_text ?? reply.decides_text) : (ws?.recommends.text ?? open.read_text)}
          </p>
          {cost ? (
            <p className="text-[0.9375rem] text-ink" data-testid="queue-cost">
              {cost}
            </p>
          ) : null}
          {reply && usable && mode === "business" ? (
            opened ? (
              <div role="region" aria-label={t("dq.review.region")} className="flex flex-col gap-3 pt-1" data-testid="queue-review">
                <RecommendedResponse v={verdict} offerId={offer.offer.offer_id} today={today} mode={mode} negotiation={negotiation} reply={{ path: reply, recommended: reply, onBack: () => setReviewing(null) }} bare />
                <div>
                  <button type="button" onClick={() => setReviewing(null)} className={textLinkClass} data-testid="queue-review-close">
                    {t("dq.review.close")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-0.5">
                <Button variant="primary" aria-expanded={false} onClick={() => setReviewing(offer.offer.offer_id)} data-testid="queue-review-open">
                  {t("dq.review")}
                </Button>
                {ws?.priced_response?.recheck_text ? <span className="min-w-0 flex-[1_1_16rem] text-[0.8125rem] text-ink-2">{ws.priced_response.recheck_text}</span> : null}
              </div>
            )
          ) : null}
        </section>
      )}

      {picture === undefined && verdict && !negotiation && verdict.counters.length > 0 ? (
        <div data-testid="paths-loading">
          <LoadingBlock rows={3} />
        </div>
      ) : usable && verdict ? (
        <PathsBody
          picture={picture}
          state={paths}
          v={verdict}
          negotiation={negotiation}
          title={t("dq.chart.title")}
          above={<StressToggle exposure={exposure} on={stress} onChange={setStress} />}
          below={<ExposureBand exposure={exposure} pick={paths.pick} />}
          stress={stressLine?.series?.length ? { series: stressLine.series, label: stressLine.text ?? "" } : null}
        />
      ) : null}

      {verdict && ws && asked && reply ? (
        <Disclosure testId="queue-compare" className="border-t border-line pt-2" summary={t("dq.compare")}>
          <div className="space-y-3 pt-1">
            <p className="text-[0.8125rem] text-ink-3">{t("dq.compare.note")}</p>
            <ImpactTable asked={asked as PicturePath} reply={reply as PicturePath} exposure={exposure} verdict={verdict} buyer={buyer} />
            <AdvancedDetails ws={ws} v={verdict} offer={offer} items={items} asks={asks} />
          </div>
        </Disclosure>
      ) : null}
    </div>
  );
}
