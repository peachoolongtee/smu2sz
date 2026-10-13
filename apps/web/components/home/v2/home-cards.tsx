"use client";

import Link from "next/link";
import { DocumentIcon, ShieldCheckIcon } from "@/components/icons";
import { segments, r1 } from "@/components/business/cash-picture";
import { StatusPill } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeV2, HomeView, OfferPictureView } from "@/lib/types";

/** The card's title: the display face, 20 px, sentence case, never an uppercase eyebrow. */
export const cardTitle = "font-display text-[16px] font-bold leading-tight tracking-[-0.01em] text-ink";

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
    <section aria-labelledby="hv2-cash-title" className="motion-reveal f-card flex min-w-0 flex-col p-4" data-testid="hv2-cash-card">
      <h2 id="hv2-cash-title" className={cardTitle} data-testid="hv2-metric-cash-label">
        {t("hv2.card.cash")}
      </h2>
      <p className={`mt-2 font-display text-[32px] font-bold leading-none tracking-[-0.03em] tabular-nums sm:mt-3 ${below ? "text-bad-fg" : "text-ink"}`} data-testid="home-kpi-cash-value">
        {cash.value_display}
      </p>
      {cash.note ? (
        <p className="mt-3 text-pretty text-sm text-ink-3" data-testid="home-kpi-cash-note">
          {cash.note}
        </p>
      ) : null}
      <div className="mt-auto pt-3 sm:pt-4" data-testid="home-buffer" data-min={b.min_fen} data-cash={b.cash_fen}>
        <div className="flex items-baseline justify-between gap-3 text-sm text-ink-3">
          <span data-testid="home-buffer-min-text">
            {t("hv2.card.reserve")} <span className="tabular-nums">{b.minimum_text ?? b.min_display}</span>
          </span>
          <span data-testid="home-buffer-room-text">
            {below ? t("hv2.card.short") : t("hv2.card.buffer")}
            {b.headroom_text ? <span className="tabular-nums"> {b.headroom_text}</span> : null}
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

interface MiniLine {
  key: string;
  points: HomeSeriesPoint[];
  cls: string;
  width: number;
  dash?: string;
  testId: string;
}

/**
 * The outlook card's small chart: step lines (the company's current books in purple and the plan that is ready as a grey dashed one; or, in a deal, the request in grey and the recommended reply in
 * purple), the minimum as a hairline and one dot; no axes (the expanded forecast has them). Marks only: days and fen place them, every word is outside it.
 */
function MiniChart({ lines, floor, today, window, dotDay, dotCls, mainKey }: { lines: MiniLine[]; floor: number; today: number; window: number; dotDay: number; dotCls: string; mainKey: string }) {
  const W = 320;
  const H = 80;
  const pad = 6;
  const end = today + window;
  const drawn = lines.map((l) => ({ ...l, segs: segments(l.points.filter((p) => p.day >= today), end) }));
  const levels = [floor, ...drawn.flatMap((l) => l.segs.map((q) => q.v))];
  const lo = Math.min(...levels);
  const hi = Math.max(...levels);
  const span = Math.max(end - today, 1);
  const x = (d: number) => r1(pad + ((Math.min(Math.max(d, today), end) - today) / span) * (W - pad * 2));
  const y = (v: number) => r1(pad + ((hi - v) / Math.max(hi - lo, 1)) * (H - pad * 2));
  const path = (s: { d0: number; d1: number; v: number }[]) => s.map((q, i) => (i === 0 ? `M${x(q.d0)},${y(q.v)}` : `H${x(q.d0)}V${y(q.v)}`)).join("") + (s.length ? `H${x(s[s.length - 1].d1)}` : "");
  const main = drawn.find((l) => l.key === mainKey)?.segs ?? [];
  const dotV = main.find((q) => dotDay >= q.d0 && dotDay < q.d1)?.v ?? main[main.length - 1]?.v ?? floor;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden className="block h-14 w-full overflow-visible" data-testid="hv2-mini">
      <line x1={pad} x2={W - pad} y1={y(floor)} y2={y(floor)} className="stroke-line-strong" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      {drawn.map((l) => (
        <path key={l.key} d={path(l.segs)} fill="none" strokeLinejoin="miter" strokeDasharray={l.dash} strokeWidth={l.width} vectorEffect="non-scaling-stroke" className={l.cls} data-testid={l.testId} />
      ))}
      <line x1={x(dotDay)} x2={x(dotDay)} y1={y(dotV)} y2={y(dotV)} strokeWidth={8} strokeLinecap="round" vectorEffect="non-scaling-stroke" className={dotCls} />
    </svg>
  );
}

function MiniOutlook({ cash, today, plan }: { cash: HomeView["cash"]; today: number; plan: HomeSeriesPoint[] | null }) {
  // The plan is drawn first, the current books over it (the dot sits on the current line).
  const lines: MiniLine[] = [];
  if (plan) lines.push({ key: "plan", points: plan, cls: "stroke-ink-3", width: 1.75, dash: "4 3", testId: "hv2-mini-plan" });
  lines.push({ key: "base", points: cash.series, cls: "stroke-chart-base", width: 2.25, testId: "hv2-mini-current" });
  return <MiniChart lines={lines} mainKey="base" floor={cash.floor_fen} today={today} window={Math.max(cash.picture_days || WINDOW_FALLBACK, cash.events_rail_days ?? 0)} dotDay={cash.lowest_day} dotCls="stroke-chart-base" />;
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
    <section aria-labelledby="hv2-outlook-title" className="motion-reveal f-card flex min-w-0 flex-col p-4" data-testid="hv2-outlook-card">
      <div className="flex items-start justify-between gap-3">
        <h2 id="hv2-outlook-title" className={cardTitle} data-testid="hv2-metric-lowest-label">
          {t("hv2.card.outlook")}
        </h2>
        {h.cash.lowest_when ? (
          <StatusPill tone="amber" testId="hv2-outlook-when">
            {h.cash.lowest_when}
          </StatusPill>
        ) : null}
      </div>
      <p className={`mt-3 font-display text-[32px] font-bold leading-none tracking-[-0.03em] tabular-nums ${low.tone === "bad" ? "text-bad-fg" : "text-ink"}`} data-testid="home-kpi-lowest-value">
        {low.value_display}
      </p>
      <p className="mt-1.5 text-sm text-ink-3">
        {t("hv2.card.without")}
        {low.short_note ?? low.note ? (
          <span className="sr-only" data-testid="home-kpi-lowest-note">
            {" "}
            {low.short_note ?? low.note}
          </span>
        ) : null}
      </p>
      <div className="mt-2 max-sm:max-w-xs">
        <MiniOutlook cash={h.cash} today={h.day} plan={plan} />
      </div>
      <div className="mt-auto flex items-center justify-between gap-3 pt-2 text-sm text-ink">
        {withPlan?.label && withPlan.value_text ? (
          <p className="tabular-nums" data-testid="home-kpi-lowest-plan">
            <span className="inline-block first-letter:uppercase">{withPlan.label}</span> {withPlan.value_text}
          </p>
        ) : (
          <span />
        )}
        <button type="button" aria-expanded={expanded} aria-controls={controls} onClick={() => onExpand(!expanded)} className="motion-press -mr-2 inline-flex min-h-8 items-center gap-1.5 rounded-control px-2 font-semibold hover:bg-subtle touch:min-h-11" data-testid="hv2-outlook-expand">
          {expanded ? t("hv2.card.close") : t("hv2.card.expand")}
          <ExpandIcon open={expanded} />
        </button>
      </div>
    </section>
  );
}

/**
 * The outlook card while a deal is selected (round two): the deal's own paths on the small chart, the request in grey and FLOW's recommended reply in purple, so the owner sees how the deal affects
 * the company's cash. The figure is the request's lowest cash in the server's short word (risk red when it breaches the minimum), the pill when that is, the footer the recommended reply's own lowest;
 * Expand opens the deal's cash chart under the deal's card. Nothing is computed here. Null while the picture is not here (the caller keeps the company's outlook).
 */
export function DealOutlookCard({ h, picture, expanded, onExpand, controls }: { h: HomeView; picture: OfferPictureView | null | undefined; expanded: boolean; onExpand: (open: boolean) => void; controls?: string }) {
  const { t } = useI18n();
  const paths = (picture?.paths ?? []).filter((p) => p.kind === "asked" || p.kind === "reply");
  const asked = paths.find((p) => p.kind === "asked") ?? null;
  const rec = paths.find((p) => p.kind === "reply" && p.recommended) ?? null;
  if (!picture || !asked?.series?.length || !rec?.series?.length) return null;
  const lines: MiniLine[] = [
    { key: "asked", points: asked.series, cls: "stroke-ink-3", width: 2, testId: "hv2-mini-asked" },
    { key: "rec", points: rec.series, cls: "stroke-chart-base", width: 2.25, testId: "hv2-mini-rec" },
  ];
  const lowestDay = asked.series.filter((p) => p.day >= h.day).reduce<HomeSeriesPoint | null>((a, b) => (a === null || b.closing_fen < a.closing_fen ? b : a), null)?.day ?? h.day;
  return (
    <section aria-labelledby="hv2-outlook-title" className="motion-reveal f-card flex min-w-0 flex-col p-4" data-testid="hv2-outlook-card" data-mode="deal">
      <div className="flex items-start justify-between gap-3">
        <h2 id="hv2-outlook-title" className={cardTitle} data-testid="hv2-metric-lowest-label">
          {t("hv2.deal.outlook")}
        </h2>
        {asked.lowest_when ? (
          <StatusPill tone="amber" testId="hv2-outlook-when">
            {asked.lowest_when}
          </StatusPill>
        ) : null}
      </div>
      {asked.lowest_short ? (
        <p className={`mt-3 font-display text-[32px] font-bold leading-none tracking-[-0.03em] tabular-nums ${asked.first_breach_when !== null ? "text-bad-fg" : "text-ink"}`} data-testid="home-kpi-lowest-value">
          {asked.lowest_short}
        </p>
      ) : null}
      <p className="mt-1.5 text-sm text-ink-3" data-testid="hv2-outlook-asked">
        {asked.label || t("hv2.deal.outlook.asked")}
      </p>
      <div className="mt-2 max-sm:max-w-xs">
        <MiniChart lines={lines} mainKey="asked" floor={picture.floor_fen} today={h.day} window={picture.picture_days ?? h.cash.picture_days ?? WINDOW_FALLBACK} dotDay={lowestDay} dotCls="stroke-bad-solid" />
      </div>
      <div className="mt-auto flex items-center justify-between gap-3 pt-2 text-sm text-ink">
        <p className="tabular-nums" data-testid="hv2-outlook-rec">
          {rec.label}
          {rec.lowest_short ? ` ${rec.lowest_short}` : ""}
        </p>
        <button type="button" aria-expanded={expanded} aria-controls={controls} onClick={() => onExpand(!expanded)} className="motion-press -mr-2 inline-flex min-h-8 items-center gap-1.5 rounded-control px-2 font-semibold hover:bg-subtle touch:min-h-11" data-testid="hv2-outlook-expand">
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
  // The server's own three nearest movements (`home_v2.upcoming`); an older server falls back to the rail's rows that move cash.
  const server = h.home_v2?.upcoming ?? null;
  const events = server
    ? server.map((u, i) => ({ key: `${u.label}-${i}`, label: u.label, amount: u.amount_display, when: u.when, kind: u.kind }))
    : (h.cash.events_rail ?? [])
        .filter((e) => !e.planned && e.amount_fen !== 0 && e.day >= h.day)
        .slice(0, 3)
        .map((e) => ({ key: e.key, label: e.label_short ?? e.label, amount: e.amount_short, when: e.when, kind: (e.amount_fen ?? 0) < 0 ? "outflow" : "inflow" }));
  return (
    <section aria-labelledby="hv2-upcoming-title" className="motion-reveal f-card min-w-0 p-4" data-testid="hv2-upcoming">
      <h2 id="hv2-upcoming-title" className="font-display text-[18px] font-bold leading-tight tracking-[-0.01em] text-ink">
        {t("hv2.upcoming.title")}
      </h2>
      {events.length ? (
        <ul className="mt-3 divide-y divide-line" data-testid="hv2-upcoming-list">
          {events.map((e) => (
            <li key={e.key} className="flex min-h-11 items-center justify-between gap-4 py-1.5 first:pt-0" data-testid="hv2-upcoming-row" data-kind={e.kind}>
              <span className="min-w-0 text-[15px] text-ink">
                <span className="block leading-tight first-letter:uppercase">{e.label}</span>
                <span className="block text-supporting text-ink-3 first-letter:uppercase">{e.when}</span>
              </span>
              <b className="shrink-0 font-semibold tabular-nums text-ink">{e.amount}</b>
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
export function FooterLinks({ separate = false }: { separate?: boolean }) {
  const { t } = useI18n();
  return (
    <nav aria-label={t("hv2.foot")} className="mt-6 border-t border-line pt-3" data-testid="home-v2-links">
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
      {separate ? (
        <p className="mt-1 pb-1 text-supporting text-ink-3" data-testid="hv2-foot-separate">
          {t("hv2.foot.separate")}
        </p>
      ) : null}
    </nav>
  );
}
