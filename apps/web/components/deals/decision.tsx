"use client";

import Link from "next/link";
import { ChasePayment } from "@/components/business/chase-payment";
import { StatePill, textLinkClass } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { dealProgress } from "@/lib/decision";
import { useI18n } from "@/lib/i18n";
import { businessAction } from "@/lib/presentation-fallbacks";
import type { BusinessAction, DealTone, DecisionView, OpenOffer, VerdictView } from "@/lib/types";
import type { Tone } from "@/components/ui";

export const ACTION_KEY: Record<BusinessAction, DictKey> = {
  accept: "biz.deals.action.accept",
  counter: "biz.deals.action.counter",
  decline: "biz.deals.action.decline",
  needs_owner: "biz.deals.action.needsYou",
  cannot: "biz.deals.action.cannot",
};

const H1 = "max-w-4xl text-balance font-display text-xl font-extrabold leading-[1.15] tracking-[-0.02em] text-ink lg:text-2xl";

const toneOf = (tone: DealTone | undefined): Tone => (!tone || tone === "mute" ? "warn" : tone);

/**
 * The page's heading when a deal is selected, straight on the canvas (the A1 pattern): the status pill (the server's `needs_you_text`), the one
 * `h1`, one quiet line beneath. Evaluated and still open, the `h1` is FLOW's read of the offer (`open_offer.read_text`, else the workspace's
 * recommendation) and the line says what is ready (the server's `headline_short` is the `h1` and `headline_note` the line when it sends them, else the whole read is the `h1`); once the deal has an outcome (sent, agreed, lapsed, closed) the `h1` is the record's own words
 * ("Agreed", "No deal: the buyer did not accept") with the money and what is left beneath. Received and not yet checked, the `h1` is the server's
 * sentence about it. The sentences are the server's; nothing is composed here.
 */
export function DealHeading({
  v = null,
  record = null,
  open = null,
  pillText = null,
  text,
  reason = null,
  title,
}: {
  v?: VerdictView | null;
  record?: DecisionView | null;
  open?: OpenOffer | null;
  pillText?: string | null;
  text?: string;
  reason?: string | null;
  /** The plain title, used only when the server has said nothing about an offer that has not been checked. */
  title: string;
}) {
  const { t } = useI18n();
  const progress = record ? dealProgress(record.state) : null;
  // A record that has gone past "response ready" has an outcome; before that the recommendation is the headline.
  const outcome = v && record && progress?.reached ? record.state : null;
  const action = v ? businessAction(v) : null;
  // Open and evaluated: the server's short verdict is the heading and its note (the figures) the quiet line; an older server sends the whole sentence as the
  // heading and "Two replies are ready to send." as the line.
  const short = v && !outcome ? (open?.headline_short ?? null) : null;
  const headline = !v ? (open?.action_text ?? title) : outcome && record ? record.state_text : (short ?? open?.read_text ?? text ?? (action ? t(ACTION_KEY[action]) : title));
  const pill = !outcome ? pillText : null;
  const quiet = v && !outcome ? (short ? (open?.headline_note ?? open?.action_text ?? null) : open?.read_text ? open.action_text : null) : null;
  return (
    <header id="deal-recommendation-card" className="motion-reveal flex flex-col items-start gap-2.5 short:gap-2" data-testid="deal-heading">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {pill ? (
          <StatePill tone={toneOf(open?.tone)} testId="deal-needs-you">
            {pill}
          </StatePill>
        ) : null}
        {/* The eyebrow says what the line is: where the deal stands once it has an outcome, FLOW's recommendation while there is one and no pill. */}
        {v && (outcome || !pill) ? (
          <span className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3" data-testid="deal-eyebrow">
            {outcome ? t("biz.deals.stands") : t("biz.deals.recommends")}
          </span>
        ) : null}
      </div>
      <h1 className={H1} data-testid={v ? "deal-recommendation" : "deal-heading-title"} data-outcome={v ? (outcome ?? "") : undefined}>
        {headline}
      </h1>
      {quiet ? (
        <p className={`max-w-3xl text-pretty text-sm text-ink-2 ${short ? "short:max-sm:hidden" : "max-sm:hidden"}`} data-testid="deal-action">
          {quiet}
        </p>
      ) : null}
      {/* The first reason rides under the recommendation when the server sent no read of its own, so the answer and its cause are one glance. */}
      {v && reason && !outcome && !open?.read_text ? (
        <p className="max-w-3xl text-pretty text-sm text-ink-2" data-testid="deal-recommendation-reason">
          {reason}
        </p>
      ) : null}
      {outcome && record ? <DealMoney record={record} /> : null}
    </header>
  );
}

/**
 * After a deal: the money and what is left, from the record's execution and its lots, in the server's figures. "Received" for a lot that has
 * landed, "arrives" for one still on its way; neutral until the cash has landed (then ok). What is left is the record's own remaining task.
 */
function DealMoney({ record }: { record: DecisionView }) {
  const { t } = useI18n();
  const lots = record.settlement ?? [];
  const lines = lots.map((l) => ({
    key: l.lot_id,
    text: l.settled ? t("deal.money.received", { amount: l.principal_display, when: l.arrival_when }) : t("deal.money.arrives", { amount: l.principal_display, when: l.arrival_when }),
    landed: l.settled,
  }));
  const landed = lines.length > 0 && lines.every((l) => l.landed);
  const left = record.remaining_task?.text;
  // A missed early payment leaves the shortfall to cover: the way to the funding options is always offered beside the chase (the server's own links, when it sends them, come first).
  const sent = record.remaining_task?.links ?? [];
  const links = record.state === "MISSED" && !sent.some((l) => l.href.startsWith("/cash")) ? [...sent, { label: t("deal.left.compare"), href: "/cash#cash-options" }] : sent;
  // A missed early payment is the one state where the owner can chase: the invoice and the buyer come from the record's own promise.
  const promise = record.state === "MISSED" ? (record.promises[0] as { receivable_id?: string } | undefined) : undefined;
  if (!lines.length && !left && !links.length) return null;
  const tone: Tone = landed ? "ok" : "neutral";
  return (
    <dl className="mt-2 space-y-1.5 border-t border-line pt-2 text-sm" data-testid="deal-money" data-tone={tone}>
      {lines.length ? (
        <div className="flex flex-wrap gap-x-3">
          <dt className="text-meta font-semibold uppercase tracking-wide text-ink-3">{t("deal.money")}</dt>
          <dd className={landed ? "font-medium text-ok-fg" : "text-ink"} data-testid="deal-money-lines">
            {lines.map((l) => (
              <span key={l.key} className="mr-2 inline-block">
                {l.text}
              </span>
            ))}
          </dd>
        </div>
      ) : null}
      {left ? (
        <div className="flex flex-wrap gap-x-3">
          <dt className="text-meta font-semibold uppercase tracking-wide text-ink-3">{t("common.left")}</dt>
          <dd className="text-ink" data-testid="deal-left">
            {left}
          </dd>
        </div>
      ) : null}
      {links.length || promise?.receivable_id ? (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1" data-testid="deal-left-links">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className={textLinkClass}>
              {l.label}
            </Link>
          ))}
          {promise?.receivable_id ? <ChasePayment receivableId={promise.receivable_id} buyer={record.counterparty_name ?? ""} /> : null}
        </div>
      ) : null}
    </dl>
  );
}
