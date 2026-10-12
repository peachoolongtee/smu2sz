"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ChevronRightIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";
import type { HomeChangesCard, HomeDealsCard, HomeReceivablesCard } from "@/lib/types";

/**
 * One card of the row under the picture: unboxed on a hairline like the rest of Home (the one raised surface is the attention card), the whole card a link (the heading's link is stretched
 * over it). A card is a place to go, not a place to act: nothing inside it is a button.
 */
function Card({ id, title, href, children }: { id: string; title: string; href: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`${id}-title`} className="motion-reveal relative min-w-0 rounded-tile px-3 pb-3 pt-3 before:absolute before:inset-x-3 before:top-0 before:h-px before:bg-line-strong hover:bg-subtle has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-focus " data-testid={id}>
      <h2 id={`${id}-title`} className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
        <Link href={href} className="flex items-center justify-between gap-2 after:absolute after:inset-0 focus-visible:outline-none" data-testid={`${id}-link`}>
          {title}
          <ChevronRightIcon aria-hidden className="shrink-0 text-ink-3" />
        </Link>
      </h2>
      <div className="mt-2.5">{children}</div>
    </section>
  );
}

/** Your deals: one line per deal, the buyer, the status word, what they ask and what FLOW recommends. No stages, no avatar, no badge. */
export function DealsCard({ card }: { card: HomeDealsCard }) {
  const { t } = useI18n();
  const rows = card.rows ?? [];
  const href = rows.length === 1 && rows[0].href ? rows[0].href : card.href || "/deals";
  return (
    <Card id="home-card-deals" title={t("biz.homeDeals.title")} href={href}>
      {rows.length ? (
        <ul className="divide-y divide-line">
          {rows.map((r) => (
            <li key={`${r.buyer}-${r.href ?? ""}`} className="py-2 first:pt-0 last:pb-0" data-testid="home-card-deal">
              <p className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="min-w-0 break-words text-sm font-bold text-ink">{r.buyer}</span>
                <span className="text-xs font-semibold text-ink-2">{r.status_text}</span>
              </p>
              {r.request_text ? <p className="text-sm text-ink-2">{r.request_text}</p> : null}
              {r.recommendation_text ? <p className="text-sm text-ink">{r.recommendation_text}</p> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-3" data-testid="home-card-deals-none">{card.empty_text || t("home.hy.deals.none")}</p>
      )}
    </Card>
  );
}

/** Receivables: what is outstanding, what is overdue, what is expected next, and, in 12 px, how the financing touches that receipt. */
export function ReceivablesCard({ card }: { card: HomeReceivablesCard }) {
  const { t } = useI18n();
  return (
    <Card id="home-card-receivables" title={t("home.hy.recv")} href={card.href || "/receivables"}>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div className="min-w-0">
          <dt className="text-xs font-semibold text-ink-3">{t("home.hy.recv.outstanding")}</dt>
          <dd className="text-lg font-extrabold tabular-nums text-ink" data-testid="home-card-outstanding">
            {card.outstanding_short ?? "—"}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs font-semibold text-ink-3">{t("home.hy.recv.overdue")}</dt>
          <dd className="text-lg font-extrabold tabular-nums text-ink" data-testid="home-card-overdue">
            {card.overdue_short ?? "—"}
          </dd>
        </div>
        {card.next_text ? (
          <div className="col-span-2 min-w-0">
            <dt className="text-xs font-semibold text-ink-3">{t("home.hy.recv.next")}</dt>
            <dd className="text-sm font-semibold text-ink" data-testid="home-card-next">
              {card.next_text}
            </dd>
          </div>
        ) : null}
      </dl>
      {card.financing_note ? (
        <p className="mt-2 text-xs text-ink-3" data-testid="home-card-financing">
          {card.financing_note}
        </p>
      ) : null}
    </Card>
  );
}

/** Recent changes: the latest ledger sentences, as the server worded them. */
export function ChangesCard({ card }: { card: HomeChangesCard }) {
  const { t } = useI18n();
  const rows = card.rows ?? [];
  return (
    <Card id="home-card-changes" title={t("biz.recent")} href={card.href || "/activity"}>
      {rows.length ? (
        <ul className="divide-y divide-line">
          {rows.map((r, i) => (
            <li key={`${r.id ?? i}-${r.text}`} className="py-2 text-sm text-ink first:pt-0 last:pb-0" data-testid="home-card-change">
              {r.text}
              {r.when ? <span className="block text-xs text-ink-3">{r.when}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-3" data-testid="home-card-changes-none">
          {card.empty_text || t("home.hy.changes.none")}
        </p>
      )}
    </Card>
  );
}
