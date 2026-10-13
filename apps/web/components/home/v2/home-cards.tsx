"use client";

import Link from "next/link";
import { DocumentIcon, ShieldCheckIcon } from "@/components/icons";
import { segments, r1 } from "@/components/business/cash-picture";
import { StatusPill } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeV2, HomeView } from "@/lib/types";

/** The card's title: the display face, 20 px, sentence case, never an uppercase eyebrow. */
export const cardTitle = "font-display text-[20px] font-bold leading-tight tracking-[-0.01em] text-ink";

/**
 * "Cash available today" (the mockup's first card): the server's figure, its note ("¥100k above your ¥300k minimum"), and the reserve bar: a track to the minimum and a green part for
 * the buffer above it (a risk-red fill and "Short by" when the cash is below the minimum). The fen only size the two parts; every word is the server's or a label.
 */
export function CashCard({ kpis }: { kpis: HomeV2["kpis"] }) {
  const { t } = useI18n();
  const cash = kpis.cash_available;
  const b = cash.buffer;
  const below = b.cash_fen < b.min_fen;
  const reserve = Math.max(b.min_fen, 1);
  const room = Math.max(b.cash_fen - b.min_fen, 0);
  return (
    <section aria-labelledby="hv2-cash-title" className="motion-reveal f-card flex min-w-0 flex-col p-5 sm:p-6" data-testid="hv2-cash-card">
      <h2 id="hv2-cash-title" className={cardTitle} data-testid="hv2-metric-cash-label">
        {t("hv2.card.cash")}
      </h2>
      <p className={`mt-3 font-display text-[36px] font-bold leading-none tracking-[-0.03em] tabular-nums sm:mt-6 sm:text-[52px] ${below ? "text-bad-fg" : "text-ink"}`} data-testid="home-kpi-cash-value">
        {cash.value_display}
      </p>
      <p className="mt-3 text-pretty text-sm text-ink-3" data-testid="home-kpi-cash-note">
        {cash.note}
      </p>
      <div className="mt-auto pt-4 sm:pt-8" data-testid="home-buffer" data-min={b.min_fen} data-cash={b.cash_fen}>
        <div className="flex items-baseline justify-between gap-3 text-sm text-ink-3">
          <span data-testid="home-buffer-min-text">
            {t("hv2.card.reserve")} <span className="tabular-nums">{b.minimum_text ?? b.min_display}</span>
          </span>
          <span data-testid="home-buffer-room-text">
            {below ? t("hv2.card.short") : t("hv2.card.buffer")} <span className="tabular-nums">{b.headroom_text ?? ""}</span>
          </span>
        </div>
        <div role="img" aria-label={cash.note} className="mt-2 flex h-2.5 gap-1" data-testid="home-buffer-bar">
          <span className="relative overflow-hidden rounded-pill bg-line-strong" style={{ flexGrow: reserve, flexBasis: 0 }}>
            {below ? <span className="absolute inset-y-0 left-0 rounded-pill bg-bad-solid" style={{ width: `${Math.min(Math.max((b.cash_fen / reserve) * 100, 0), 100)}%` }} data-testid="home-buffer-cash" /> : null}
          </span>
          {!below && room > 0 ? <span className="rounded-pill bg-f-green" style={{ flexGrow: room, flexBasis: 0 }} data-testid="home-buffer-cash" /> : null}
        </div>
      </div>
    </section>
  );
}

const WINDOW_FALLBACK = 30;

/**
 * The outlook card's small chart: the current books as a purple step line, the plan that is ready as a grey dashed one, the minimum as a hairline and the lowest point as a dot; no axes
 * (the expanded forecast has them). Marks only: days and fen place them, every word is outside it.
 */
function MiniOutlook({ cash, today, plan }: { cash: HomeView["cash"]; today: number; plan: HomeSeriesPoint[] | null }) {
  const W = 320;
  const H = 104;
  const pad = 6;
  const end = today + Math.max(cash.picture_days || WINDOW_FALLBACK, cash.events_rail_days ?? 0);
  const main = segments(cash.series.filter((p) => p.day >= today), end);
  const alt = plan ? segments(plan.filter((p) => p.day >= today), end) : [];
  const floor = cash.floor_fen;
  const levels = [floor, ...main.map((s) => s.v), ...alt.map((s) => s.v)];
  const lo = Math.min(...levels);
  const hi = Math.max(...levels);
  const span = Math.max(end - today, 1);
  const x = (d: number) => r1(pad + ((Math.min(Math.max(d, today), end) - today) / span) * (W - pad * 2));
  const y = (v: number) => r1(pad + ((hi - v) / Math.max(hi - lo, 1)) * (H - pad * 2));
  const path = (s: { d0: number; d1: number; v: number }[]) => s.map((q, i) => (i === 0 ? `M${x(q.d0)},${y(q.v)}` : `H${x(q.d0)}V${y(q.v)}`)).join("") + (s.length ? `H${x(s[s.length - 1].d1)}` : "");
  const lowDay = cash.lowest_day;
  const lowV = main.find((q) => lowDay >= q.d0 && lowDay < q.d1)?.v ?? main[main.length - 1]?.v ?? floor;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} aria-hidden className="block h-auto w-full overflow-visible" data-testid="hv2-mini">
      <line x1={pad} x2={W - pad} y1={y(floor)} y2={y(floor)} className="stroke-line-strong" strokeWidth={1} />
      {alt.length ? <path d={path(alt)} fill="none" strokeLinejoin="miter" strokeDasharray="4 3" strokeWidth={1.75} className="stroke-ink-3" data-testid="hv2-mini-plan" /> : null}
      <path d={path(main)} fill="none" strokeLinejoin="miter" strokeWidth={2.25} className="stroke-chart-base" data-testid="hv2-mini-current" />
      <circle cx={x(lowDay)} cy={y(lowV)} r={4} className="fill-chart-base" />
    </svg>
  );
}

const ExpandIcon = ({ open }: { open: boolean }) => (
  <svg aria-hidden viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
    {open ? <path d="m4 10 4-4 4 4" /> : <path d="M9.5 2.5h4v4M13.5 2.5 9 7M6.5 13.5h-4v-4M2.5 13.5 7 9" />}
  </svg>
);

/**
 * "Company cash outlook" (the mockup's third card): the lowest cash ahead as the figure (the one risk red when it is below the minimum), "Without new funding", the small step chart,
 * the plan's cash ("With plan ¥300,000") and Expand, which opens the full forecast in place under the cards (`?expand=1`; Close restores). The pill says when the lowest point is.
 */
export function OutlookCard({ h, kpis, plan, expanded, onExpand, controls }: { h: HomeView; kpis: HomeV2["kpis"]; plan: HomeSeriesPoint[] | null; expanded: boolean; onExpand: (open: boolean) => void; controls?: string }) {
  const { t } = useI18n();
  const low = kpis.lowest_ahead;
  const withPlan = low.with_plan ?? null;
  return (
    <section aria-labelledby="hv2-outlook-title" className="motion-reveal f-card flex min-w-0 flex-col p-5 sm:p-6" data-testid="hv2-outlook-card">
      <div className="flex items-start justify-between gap-3">
        <h2 id="hv2-outlook-title" className={cardTitle} data-testid="hv2-metric-lowest-label">
          {t("hv2.card.outlook")}
        </h2>
        <StatusPill tone="amber" testId="hv2-outlook-when">
          {h.cash.lowest_when}
        </StatusPill>
      </div>
      <p className={`mt-4 font-display text-[44px] font-bold leading-none tracking-[-0.03em] tabular-nums sm:text-[52px] ${low.tone === "bad" ? "text-bad-fg" : "text-ink"}`} data-testid="home-kpi-lowest-value">
        {low.value_display}
      </p>
      <p className="mt-2 text-sm text-ink-3">
        {t("hv2.card.without")}
        <span className="sr-only" data-testid="home-kpi-lowest-note">
          {" "}
          {low.short_note ?? low.note}
        </span>
      </p>
      <div className="mt-3 max-sm:max-w-xs">
        <MiniOutlook cash={h.cash} today={h.day} plan={plan} />
      </div>
      <div className="mt-auto flex items-center justify-between gap-3 pt-3 text-sm text-ink">
        {withPlan ? (
          <p className="tabular-nums" data-testid="home-kpi-lowest-plan">
            <span className="inline-block first-letter:uppercase">{withPlan.label}</span> {withPlan.value_text}
          </p>
        ) : (
          <span />
        )}
        <button type="button" aria-expanded={expanded} aria-controls={controls} onClick={() => onExpand(!expanded)} className="motion-press -mr-2 inline-flex min-h-10 items-center gap-1.5 rounded-control px-2 font-semibold hover:bg-subtle touch:min-h-11" data-testid="hv2-outlook-expand">
          {expanded ? t("hv2.card.close") : t("hv2.card.expand")}
          <ExpandIcon open={expanded} />
        </button>
      </div>
    </section>
  );
}

/**
 * "Upcoming cash movements": the Home read's own rail events (the nearest that move cash, each with the server's label, amount and when; the plan's landings are the plan's, not
 * movements), never a second computation, and the way to the full forecast on Cash & Funding.
 */
export function UpcomingCard({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const events = (h.cash.events_rail ?? []).filter((e) => !e.planned && e.amount_fen !== 0 && e.day >= h.day).slice(0, 4);
  return (
    <section aria-labelledby="hv2-upcoming-title" className="motion-reveal f-card min-w-0 p-6" data-testid="hv2-upcoming">
      <h2 id="hv2-upcoming-title" className="font-display text-[22px] font-bold leading-tight tracking-[-0.01em] text-ink">
        {t("hv2.upcoming.title")}
      </h2>
      {events.length ? (
        <ul className="mt-5 divide-y divide-line" data-testid="hv2-upcoming-list">
          {events.map((e) => (
            <li key={e.key} className="flex items-start justify-between gap-4 py-3.5 first:pt-0" data-testid="hv2-upcoming-row">
              <span className="min-w-0 text-[15px] text-ink">
                <span className="block first-letter:uppercase">{e.label_short ?? e.label}</span>
                <span className="mt-0.5 block text-sm text-ink-3 first-letter:uppercase">{e.when}</span>
              </span>
              <b className="shrink-0 font-semibold tabular-nums text-ink">{e.amount_short}</b>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-ink-3" data-testid="hv2-upcoming-none">
          {t("hv2.upcoming.none")}
        </p>
      )}
      <Link href="/cash" className="motion-press mt-3 inline-flex min-h-10 items-center gap-1.5 text-[15px] font-semibold text-ink hover:underline hover:underline-offset-[3px] touch:min-h-11" data-testid="home-chart-full">
        {t("hv2.upcoming.explore")} <span aria-hidden>↗</span>
      </Link>
    </section>
  );
}

const FOOT = [
  { href: "/documents", key: "hv2.foot.documents", Icon: DocumentIcon },
  { href: "/whatif", key: "hv2.foot.whatif", Icon: ShieldCheckIcon },
  { href: "/capex", key: "hv2.foot.capex", Icon: ShieldCheckIcon },
  { href: "/approvals", key: "hv2.foot.approvals", Icon: ShieldCheckIcon },
] as const;

/** The footer row: the four secondary destinations of the mockup, linking to the existing routes (their pages change in their own slices). */
export function FooterLinks() {
  const { t } = useI18n();
  return (
    <nav aria-label={t("hv2.foot")} className="mt-8 border-t border-line pt-4" data-testid="home-v2-links">
      <ul className="flex flex-wrap gap-x-7 gap-y-1">
        {FOOT.map(({ href, key, Icon }) => (
          <li key={href}>
            <Link href={href} className="motion-press inline-flex min-h-11 items-center gap-2 text-[15px] font-medium text-ink hover:underline hover:underline-offset-[3px]" data-testid={`hv2-foot-${href.slice(1)}`}>
              <Icon width={18} height={18} aria-hidden className="text-ink-2" />
              {t(key)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
