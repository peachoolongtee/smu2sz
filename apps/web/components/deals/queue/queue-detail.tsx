"use client";

import Link from "next/link";
import { useState } from "react";
import { Disclosure } from "@/components/business/kit";
import { authorityText, authorityTone } from "@/components/deals/path-columns";
import { PathsBody, PathsReply, pathsUsable, type PathsState } from "@/components/deals/paths-section";
import { RecommendedResponse } from "@/components/deals/response";
import { AdvancedDetails } from "@/components/deals/workspace";
import { NextStep } from "@/components/next-step";
import { Button, ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { Mode } from "@/lib/mode";
import type { OfferItem } from "@/lib/offer-items";
import type { DealView, Displayed, ExposureView, NegotiationView, Obligation, OfferPictureView, OfferView, OpenOffer, PicturePath, VerdictView } from "@/lib/types";
import { ExposureBand, StressToggle } from "./exposure-band";
import { ImpactTable } from "./impact-table";
import { eyebrowCls } from "./queue-list";
import { WhyFacts } from "./why-facts";

const RULE: Record<string, string> = { accept: "border-ok-solid", counter: "border-bad-solid", decline: "border-bad-solid", cannot: "border-bad-solid", needs_owner: "border-warn-solid" };
const AUTHORITY_INK: Record<string, string> = { ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };
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
  onSending,
  after = null,
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
  /** Told whenever a send is in flight: the page then holds the selection, so nothing that would unmount the send can be pressed. */
  onSending: (sending: boolean) => void;
  /** Anything the page adds under the comparison (the strategy build's "Before they ask" card). */
  after?: React.ReactNode;
}) {
  const { t } = useI18n();
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [stress, setStress] = useState(false);
  // A send is in flight: the picks, the close and the selection are held until it ends, so it cannot be unmounted mid-send and a second one cannot start.
  const [sendingNow, setSendingNow] = useState(false);
  const lockedPaths: PathsState = sendingNow ? { ...paths, onPick: () => undefined, locked: true } : paths;
  const ws = verdict?.workspace ?? null;
  const buyer = exposure.concentration.buyer_name;
  const heading = open.headline_short ?? open.read_text ?? open.asks_text;
  const action = ws?.recommends.action ?? null;
  const asked = paths.paths.find((p) => p.kind === "asked") ?? null;
  const reply = paths.paths.find((p) => p.kind === "reply" && p.recommended) ?? null;
  const usable = Boolean(verdict && pathsUsable(picture, negotiation, verdict));
  const picked = paths.picked;
  // The card follows the pick: the recommended reply by default, another reply (you approve first) or the asked path (nothing to send, the way back).
  const card = picked ?? reply;
  // (by the reply's name, not its id: checking again names new counters, and the review that is open stays open)
  const reviewKey = `${offer.offer.offer_id}:${card?.label ?? ""}`;
  const opened = reviewing === reviewKey;
  const stressLine = stress && picked ? exposure.stress.paths[picked.key] : null;
  const cost =
    card && card.kind === "reply"
      ? card.cost_once_display
        ? t("dq.cost.once", { amount: card.cost_once_display, buyer })
        : card.cost_total_display
          ? t("dq.cost.total", { amount: card.cost_total_display, basis: card.cost_basis_text ?? "", buyer })
          : null
      : null;

  return (
    <div className="flex min-w-0 flex-col gap-2.5 sm:gap-4 short:gap-3" data-testid="queue-detail" data-offer={offer.offer.offer_id}>
      <p className={`${eyebrowCls} text-ink-3`}>
        {t("dq.eyebrow")} ·{" "}
        <Link href={customerHref} className="inline-flex min-h-8 items-center text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-detail-customer">
          {deal.counterparty_name} ›
        </Link>
      </p>
      <h2 tabIndex={-1} className="type-section text-balance text-ink" data-testid="queue-heading">
        {heading}
      </h2>
      <p className="text-sm leading-snug text-ink-2 sm:text-body-lg sm:leading-normal" data-testid="queue-ask">
        {t("dq.ask", { buyer, asks: open.asks_text })}
      </p>

      {ws && ws.why_it_matters.reasons.length ? (
        <div className={`flex flex-col gap-0.5 border-l-[3px] py-0.5 pl-3 sm:gap-1 sm:pl-3.5 ${RULE[action ?? "counter"] ?? "border-line-strong"}`} data-testid="queue-why">
          <p className={`${eyebrowCls} ${RULE_INK[action ?? "counter"] ?? "text-ink-3"}`}>{t(`dq.why.${action ?? "counter"}` as DictKey)}</p>
          {ws.why_it_matters.reasons.slice(0, 2).map((r) => (
            <p key={r} className="text-sm leading-snug text-ink sm:text-body-lg sm:leading-normal">
              {r}
            </p>
          ))}
        </div>
      ) : null}

      {negotiation && verdict ? (
        <RecommendedResponse v={verdict} offerId={offer.offer.offer_id} today={today} mode={mode} negotiation={negotiation} />
      ) : !verdict ? (
        <div data-testid="queue-check">
          <NextStep
            label={t("next.label")}
            className="mb-0"
            action={
              <Button variant="primary" loading={busy} onClick={onCheck} data-testid="queue-check-button">
                {t("biz.deals.check")}
              </Button>
            }
          >
            {t("next.inbox")}
          </NextStep>
          {error ? (
            <div className="mt-2">
              <ErrorState error={error} />
            </div>
          ) : null}
        </div>
      ) : (
        <section aria-labelledby="dq-rec" className="flex flex-col gap-1.5 rounded-card border border-brand-100 bg-brand-50 p-3 sm:gap-2 sm:p-5 short:p-4" data-testid="queue-recommends" data-path={!card ? "" : card.kind === "asked" ? "asked" : card.recommended ? "recommended" : "other"}>
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <h3 id="dq-rec" className={`${eyebrowCls} ${card && !card.sendable ? "text-ink-3" : "text-brand-700"}`}>
              {!card ? t("dq.rec.plain") : card.kind === "asked" ? t("biz.deals.reply.cannot") : card.recommended ? t("dq.rec.eyebrow", { label: card.label }) : card.needs_owner ? t("biz.deals.reply.approveFirst", { label: card.label }) : t("biz.deals.reply.eyebrow", { label: card.label })}
            </h3>
          </div>
          <p className="font-display text-body-lg font-bold leading-snug text-ink sm:text-body-lg" data-testid="queue-option">
            {card ? (card.sendable ? (card.reply_text ?? card.decides_text) : authorityText(card)) : (ws?.recommends.text ?? open.read_text)}
          </p>
          {cost ? (
            <p className="text-sm leading-snug text-ink sm:text-body-lg" data-testid="queue-cost">
              {cost}
            </p>
          ) : null}
          {card && card.kind === "reply" ? (
            <p className={`text-sm font-semibold leading-snug sm:text-body-lg ${AUTHORITY_INK[authorityTone(card)] ?? "text-ink"}`} data-testid="queue-authority" data-authority={card.authority ?? ""} data-tone={authorityTone(card)}>
              {card.decides_text}
            </p>
          ) : null}
          {card && card.kind === "asked" && reply && usable ? (
            <div className="pt-0.5">
              <Button variant="secondary" onClick={() => lockedPaths.onPick(reply.key)} data-testid="path-reply-back">
                {t("biz.deals.reply.back", { label: reply.label })}
              </Button>
            </div>
          ) : null}
          {card && card.sendable && usable && mode === "business" ? (
            opened ? (
              <div role="region" aria-label={t("dq.review.region")} className="flex flex-col gap-3 pt-1" data-testid="queue-review">
                <RecommendedResponse v={verdict} offerId={offer.offer.offer_id} today={today} mode={mode} negotiation={negotiation} reply={{ path: card, recommended: reply, onBack: () => setReviewing(null) }} bare onBusy={(b) => { setSendingNow(b); onSending(b); }} />
                <div>
                  <button type="button" onClick={() => setReviewing(null)} disabled={sendingNow} className={`${textLinkClass} disabled:opacity-50`} data-testid="queue-review-close">
                    {t("dq.review.close")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-0.5">
                <Button variant="primary" aria-expanded={false} onClick={() => setReviewing(reviewKey)} data-testid="queue-review-open">
                  {t("dq.review")}
                </Button>
                {ws?.priced_response?.recheck_text ? <span className="min-w-0 flex-[1_1_16rem] text-supporting text-ink-2">{ws.priced_response.recheck_text}</span> : null}
              </div>
            )
          ) : null}
        </section>
      )}

      {/* Whenever the reply cannot be reviewed here (the picture cannot be drawn, no reply to send, or the Demo view), the page's own response stands in the card's place: the server's
          sentence when the offer can no longer be drawn, the counter cards with their sends in Business, the hint in the Demo. The owner can always send. */}
      {verdict && !negotiation && picture !== undefined && (!usable || mode !== "business") ? (
        <PathsReply picture={picture} state={paths} v={verdict} offerId={offer.offer.offer_id} today={today} mode={mode} negotiation={negotiation} />
      ) : null}

      {picture === undefined && verdict && !negotiation && verdict.counters.length > 0 ? (
        <div data-testid="paths-loading">
          <LoadingBlock rows={3} />
        </div>
      ) : usable && verdict ? (
        <PathsBody
          picture={picture}
          state={lockedPaths}
          v={verdict}
          negotiation={negotiation}
          title={t("dq.chart.title")}
          above={<StressToggle exposure={exposure} on={stress} onChange={setStress} />}
          below={
            <>
              <WhyFacts v={verdict} today={today} />
              <ExposureBand exposure={exposure} pick={paths.pick} />
            </>
          }
          stress={stressLine?.series?.length ? { series: stressLine.series, label: stressLine.text ?? "" } : null}
        />
      ) : null}

      {verdict && ws && asked && reply ? (
        <Disclosure testId="queue-compare" className="border-t border-line pt-2" summary={t("dq.compare")}>
          <div className="space-y-3 pt-1">
            <p className="text-supporting text-ink-3">{t("dq.compare.note")}</p>
            <ImpactTable asked={asked as PicturePath} reply={reply as PicturePath} exposure={exposure} verdict={verdict} buyer={buyer} windowDays={picture?.picture_days ?? null} />
            <AdvancedDetails ws={ws} v={verdict} offer={offer} items={items} asks={asks} only={["source_text", "formula"]} />
          </div>
        </Disclosure>
      ) : null}
      {after}
    </div>
  );
}
