"use client";

import Link from "next/link";
import { DocumentIcon, ShieldCheckIcon } from "@/components/icons";
import { segments, r1 } from "@/components/business/cash-picture";
import { Breakdown } from "@/components/home/v2/breakdown";
import { StatusPill } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeV2, HomeView, WorklistCustomer } from "@/lib/types";

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
  const scale = Math.max(b.cash_fen, b.min_fen, 1);
  const pct = (fen: number) => Math.min(Math.max((fen / scale) * 100, 0), 100);
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
        <div className="relative mt-2" data-testid="home-buffer-track">
          <div role="img" aria-label={cash.note} className="flex h-2.5 gap-1" data-testid="home-buffer-bar">
            <span className="relative overflow-hidden rounded-pill bg-line-strong" style={{ width: `${pct(b.min_fen)}%` }}>
              {below ? <span className="absolute inset-y-0 left-0 rounded-pill bg-bad-solid" style={{ width: `${Math.min(Math.max((b.cash_fen / Math.max(b.min_fen, 1)) * 100, 0), 100)}%` }} data-testid="home-buffer-cash" /> : null}
            </span>
            {!below && room > 0 ? <span className="rounded-pill bg-f-green" style={{ width: `${(room / scale) * 100}%` }} data-testid="home-buffer-cash" /> : null}
          </div>
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


/** The number and its percent sign in a share word ("19.5% of what you are owed", "占您应收款的 19.5%" are "19.5%"): the centre of the owed donut says the figure, the legend keeps the server's whole phrase. */
const percentOf = (share: string | null | undefined): string | null => /(\d+(?:\.\d+)?\s*%)/.exec(share ?? "")?.[1] ?? null;

/**
 * "What you are owed, by customer" (round four: on a selection the outlook card becomes this donut): a slice for each customer with something outstanding, from the `/customers` rows the page already
 * reads (name, `outstanding_display`, `share_text`, the server's words); the selected customer's slice is lifted 4 px and named in the centre ("Zhuhai · ¥150,000 · 19.5%"); another slice or its
 * row SELECTS that customer (the address changes and the cards follow).
 */
export function owedRowsOf(customers: WorklistCustomer[] | null | undefined): WorklistCustomer[] {
  return (customers ?? []).filter((c) => {
    const pct = percentOf(c.share_text);
    return pct !== null && parseFloat(pct) > 0;
  });
}

export function OwedCard({ customers, selected, onSelect }: { customers: WorklistCustomer[] | null | undefined; selected: string | null; onSelect: (customerId: string) => void }) {
  const { t } = useI18n();
  const rows = owedRowsOf(customers);
  if (!rows.length) return null;
  // Fewer than two customers owed: the one figure, no ring (a single slice says nothing a number does not).
  if (rows.length === 1) {
    const only = rows[0];
    return (
      <section aria-labelledby="hv2-owed-title" className="motion-reveal f-card min-w-0 p-4" data-testid="hv2-owed-card" data-ring="false">
        <h2 id="hv2-owed-title" className={cardTitle} data-testid="hv2-owed-title">
          {t("hv2.owed.title")}
        </h2>
        <button type="button" aria-pressed={selected === only.customer_id} onClick={() => onSelect(only.customer_id)} className="motion-press mt-2 block w-full rounded-control px-1 py-1 text-left hover:bg-subtle touch:min-h-11" data-testid="hv2-owed-one">
          <b className="block font-display text-[26px] font-bold leading-none tracking-[-0.02em] tabular-nums text-ink">{only.outstanding_display}</b>
          <span className="mt-1 block text-sm text-ink-2">{only.name}</span>
          <span className="block text-supporting text-ink-3">{only.share_text}</span>
        </button>
      </section>
    );
  }
  const at = rows.findIndex((c) => c.customer_id === selected);
  const on = at >= 0 ? rows[at] : null;
  return (
    <section aria-labelledby="hv2-owed-title" className="motion-reveal f-card min-w-0 p-4" data-testid="hv2-owed-card">
      <h2 id="hv2-owed-title" className={cardTitle} data-testid="hv2-owed-title">
        {t("hv2.owed.title")}
      </h2>
      <Breakdown
        stacked
        size={128}
        testId="hv2-owed"
        rows={rows.map((c) => ({ label: c.name, amount_display: c.outstanding_display, share_text: c.share_text as string }))}
        lifted={at >= 0 ? at : null}
        onPick={(i) => onSelect(rows[i].customer_id)}
        centre={
          on ? (
            <span className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-5 text-center leading-tight" data-testid="hv2-owed-centre">
              <span className="max-w-full truncate text-supporting text-ink-3">{on.short}</span>
              <b className="font-display text-[15px] font-bold tabular-nums text-ink">{on.outstanding_display}</b>
              <span className="text-supporting tabular-nums text-ink-3">{percentOf(on.share_text)}</span>
            </span>
          ) : undefined
        }
      />
    </section>
  );
}

/**
 * "Upcoming cash movements": the Home read's own rail events (the nearest that move cash, each with the server's label, amount and when; the plan's landings are the plan's, not
 * movements), never a second computation, and the way to the full forecast on Cash & Funding.
 */
export function UpcomingCard({ h, overdue }: { h: HomeView; overdue?: { short: string; count: number } | null }) {
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
      {events.length || overdue ? (
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
          {overdue ? (
            <li className="min-h-11 py-1.5" data-testid="hv2-upcoming-overdue-row">
              <Link href="/receivables?from=home" className="motion-press flex min-h-8 items-center justify-between gap-4 rounded-control text-[15px] text-ink hover:underline hover:underline-offset-[3px] touch:min-h-11" data-testid="hv2-upcoming-overdue">
                <span className="min-w-0">
                  <span className="block leading-tight">{t("hv2.upcoming.overdue")}</span>
                  <span className="block text-supporting text-ink-3">{t(overdue.count === 1 ? "hv2.upcoming.overdue.one" : "hv2.upcoming.overdue.many", { n: overdue.count })}</span>
                </span>
                <b className="shrink-0 font-semibold tabular-nums text-bad-fg">{overdue.short}</b>
              </Link>
            </li>
          ) : null}
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
