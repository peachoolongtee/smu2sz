"use client";

import Link from "next/link";
import { Avatar, initials, toneFor } from "@/components/business/kit";
import { StageTrack } from "@/components/deals/stage-track";
import { contractsOff } from "@/components/documents";
import { ButtonLink, ErrorState, LoadingBlock, StatePill, textLinkClass, type Tone } from "@/components/ui";
import { getDeals } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import type { DealTone, DealView } from "@/lib/types";

const toneOf = (tone: DealTone): Tone => (tone === "mute" ? "neutral" : tone);

type Change = NonNullable<DealView["changes"]>[number];

/** The newest entry of a deal's changes: the one with the latest day (the server lists them oldest first, so a tie goes to the later row). */
function latest(changes: Change[]): Change | null {
  let best: Change | null = null;
  for (const c of changes) if (!best || (c.day ?? -1) >= (best.day ?? -1)) best = c;
  return best;
}

function DealRow({ deal }: { deal: DealView }) {
  const { t } = useI18n();
  const c = deal.contract;
  if (!deal.has_contract || !c) {
    return (
      <article className="flex flex-wrap items-center justify-between gap-x-8 gap-y-2 border-b border-line-strong py-4" data-testid={`home-deal-${deal.counterparty_id}`}>
        <div className="flex min-w-0 flex-[1_1_18rem] items-center gap-3">
          <Avatar tone="neutral">{initials(deal.counterparty_name)}</Avatar>
          <div className="min-w-0">
            <h3 className="break-words text-base font-extrabold text-ink">{deal.counterparty_name}</h3>
            <p className="text-sm text-ink-3">{t("biz.homeDeals.noContract")}</p>
          </div>
        </div>
        <Link href="/documents" className={`${textLinkClass} font-bold`}>
          {t("biz.homeDeals.add")}
        </Link>
      </article>
    );
  }
  const meta = [c.title, c.signed_display ? t("deal.signed", { date: c.signed_display }) : null, c.term_display, c.cadence_display].filter(Boolean).join(" · ");
  const open = deal.open_offer;
  const link = `/deals?buyer=${encodeURIComponent(deal.counterparty_id)}`;
  if (open) {
    const bad = open.over_limit && open.cost_display ? open.cost_display : null;
    const readParts = open.read_text ? (bad && open.read_text.includes(bad) ? open.read_text.split(bad) : [open.read_text]) : [];
    return (
      <article className="space-y-4 border-b border-line-strong py-5" data-testid={`home-deal-${deal.counterparty_id}`}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <Avatar tone={toneFor(deal.counterparty_name)}>{initials(deal.counterparty_name)}</Avatar>
          <h3 className="break-words text-base font-extrabold text-ink">{deal.counterparty_name}</h3>
          {deal.needs_you_text ? (
            <StatePill tone="warn" testId={`home-deal-needs-${deal.counterparty_id}`}>
              {deal.needs_you_text}
            </StatePill>
          ) : null}
          <span className="text-sm text-ink-3">{t("biz.homeDeals.received", { when: open.received_when })}</span>
        </div>
        <div className="max-w-3xl">
          <StageTrack stages={open.stages} testId={`home-deal-stages-${deal.counterparty_id}`} />
        </div>
        <div className="grid gap-x-9 gap-y-3 md:grid-cols-2" data-testid={`home-deal-offer-${deal.counterparty_id}`}>
          <div className="min-w-0">
            <h4 className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("biz.homeDeals.asks")}</h4>
            <p className="mt-1 break-words text-sm text-ink" data-testid="home-deal-asks">
              {open.asks_text}
            </p>
          </div>
          {readParts.length ? (
            <div className="min-w-0">
              <h4 className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("biz.homeDeals.read")}</h4>
              <p className="mt-1 break-words text-sm text-ink" data-testid="home-deal-read">
                {readParts.map((part, i) => (
                  <span key={i}>
                    {i > 0 ? (
                      <strong className="font-bold text-bad-fg" data-testid="home-deal-cost">
                        {bad}
                      </strong>
                    ) : null}
                    {part}
                  </span>
                ))}
              </p>
            </div>
          ) : null}
        </div>
        <p className="text-sm text-ink-2" data-testid="home-deal-action">
          {open.action_text}
        </p>
        {c.replaces_text ? <p className="text-sm text-ink-3">{c.replaces_text}</p> : null}
        <div>
          <ButtonLink href={link} data-testid={`home-deal-open-${deal.counterparty_id}`}>
            {t("biz.homeDeals.open")}
          </ButtonLink>
        </div>
      </article>
    );
  }
  const change = latest(deal.changes ?? []);
  return (
    <article className="flex flex-wrap items-start gap-x-9 gap-y-5 border-b border-line-strong py-5" data-testid={`home-deal-${deal.counterparty_id}`}>
      <div className="flex min-w-0 flex-[1_1_20rem] gap-3">
        <Avatar tone={toneFor(deal.counterparty_name)}>{initials(deal.counterparty_name)}</Avatar>
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="break-words text-base font-extrabold text-ink">{deal.counterparty_name}</h3>
            {deal.pills?.map((p) => (
              <StatePill key={p.label} tone={toneOf(p.tone)}>
                {p.label}
              </StatePill>
            ))}
          </div>
          {meta ? <p className="break-words text-sm text-ink-3">{meta}</p> : null}
          {c.replaces_text ? <p className="text-sm text-ink-3">{c.replaces_text}</p> : null}
          {change ? (
            <p className="text-sm text-ink">
              <strong className="font-bold">{change.label}:</strong> {change.text}
            </p>
          ) : null}
          {deal.next_action?.text ? <p className="text-sm text-ink-2">{deal.next_action.text}</p> : null}
          <div className="mt-1">
            <ButtonLink href={link} data-testid={`home-deal-open-${deal.counterparty_id}`}>
              {t("biz.homeDeals.open")}
            </ButtonLink>
          </div>
        </div>
      </div>
      {deal.stages?.length ? (
        <div className="min-w-0 flex-[1_1_22rem] pt-1">
          <StageTrack stages={deal.stages} testId={`home-deal-stages-${deal.counterparty_id}`} />
        </div>
      ) : null}
    </article>
  );
}

/**
 * "Your deals" on Home: one unboxed row per deal from GET /deals, a hairline between rows. A deal with a confirmed contract shows the buyer, the
 * server's pills, the contract in the read's own display strings, the five-step track, the newest change and the next thing to do; a deal
 * with an open offer leads with it (the `needs_you_text` pill, the offer's five-step track, what it asks, FLOW's read and what to do); a deal
 * without one says so quietly and links to where the contract is added. A failed read is one quiet line with Retry and never blanks Home.
 * Every word is the server's, or a label of the app's.
 */
export function HomeDeals({ deals, loading, failed, onRetry }: { deals: DealView[] | undefined; loading: boolean; failed: boolean; onRetry: () => void }) {
  const { t } = useI18n();
  if (!failed && !loading && !deals?.length) return null;
  return (
    <section aria-labelledby="home-deals-title" className="pt-1" data-testid="home-deals">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="home-deals-title" className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">
          {t("biz.homeDeals.title")}
        </h2>
        <Link href="/deals" className={`${textLinkClass} text-sm font-bold`} data-testid="home-deals-all">
          {t("biz.homeDeals.all")}
        </Link>
      </div>
      {failed ? (
        <div className="mt-3" data-testid="home-deals-failed">
          <ErrorState error={t("biz.homeDeals.failed")} onRetry={onRetry} />
        </div>
      ) : loading && !deals ? (
        <div className="mt-3">
          <LoadingBlock rows={2} />
        </div>
      ) : (
        <div>{deals?.map((d) => <DealRow key={d.counterparty_id} deal={d} />)}</div>
      )}
    </section>
  );
}

/**
 * The older Home's deals, with their own read (GET /deals): a failed read is one quiet line with Retry and never blanks the page (a server with contract
 * reading off has none to show). Only mounted when the home read has no `deals_card`, so the hybrid Home never makes this read.
 */
export function HomeDealsRead() {
  const { lang } = useI18n();
  const read = useAsync(() => getDeals(lang), [lang]);
  return <HomeDeals deals={read.data?.deals} loading={read.loading} failed={Boolean(read.error) && !contractsOff(read.error)} onRetry={read.reload} />;
}
