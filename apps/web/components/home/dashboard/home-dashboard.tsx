"use client";

import Link from "next/link";
import { useState, type ComponentType, type SVGProps } from "react";
import { PartialRead } from "@/components/business/freshness";
import { usePlanRun } from "@/components/business/next-action";
import { RemainingTaskBlock } from "@/components/business/open-decisions";
import { FixResult, type useFixAlert } from "@/components/home/fix-alert";
import { CashAhead } from "@/components/home/dashboard/cash-ahead";
import { FundingRing } from "@/components/home/dashboard/funding-ring";
import { ActivityIcon, AlertIcon, ArrowRightIcon, BankIcon, CheckCircleIcon, ChevronRightIcon, ClockIcon, DealsIcon, InboxInIcon, WalletIcon } from "@/components/icons";
import { ButtonLink } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { lenderHue } from "@/lib/funding-mix";
import { useI18n } from "@/lib/i18n";
import type { HomeNextAction, HomeTone, HomeView } from "@/lib/types";

/** The funding kinds of the attention queue: the Planned funding card already says them, so the strip above the cards never repeats them. */
const FUNDING_KINDS = new Set(["funding", "landing"]);

/**
 * The Home, as a dashboard: the status sentence as the heading, three cards sized by what matters first (the cash available, the planned funding, the
 * lowest cash ahead, which opens into the full range), the shortcuts, the recent activity and, on the right, who funds the business. Every figure and
 * sentence is the server's; the fen only draw the pictures (INVARIANT 13).
 */
export function HomeDashboard({ h, fixer, loading, onRetry }: { h: HomeView; fixer: ReturnType<typeof useFixAlert>; loading: boolean; onRetry: () => void }) {
  const { t } = useI18n();
  const [ahead, setAhead] = useState(false);
  const tone = h.cash.status_tone ?? "neutral";
  return (
    <div aria-busy={loading} className="relative isolate min-w-0" data-testid="home-dashboard">
      <header className="motion-reveal mb-6 sm:mb-8" data-testid="home-status" data-status={h.status}>
        <p className="text-supporting font-semibold text-ink-3">{t("home.dash.welcome")}</p>
        <h1 className="type-headline mt-1 flex items-baseline gap-2.5 text-balance text-ink">
          <span aria-hidden className={`size-2.5 shrink-0 -translate-y-0.5 rounded-pill ${DOT[tone]}`} data-testid="home-status-dot" />
          <span className="sr-only" data-testid="home-status-word">
            {h.cash.status_word ?? h.status_text}
          </span>
          <span data-testid="home-headline">{h.cash.headline_conditional || h.headline}</span>
        </h1>
      </header>
      <PartialRead partial={h.partial} onRetry={onRetry} />
      <AttentionStrip h={h} />
      {/* One column on a phone (the cards, who funds you, then the rest); from xl the funding ring is a column of its own on the right. */}
      <div className="grid grid-cols-1 gap-6 sm:gap-8 xl:grid-cols-[minmax(0,1fr)_340px] xl:items-start">
        <section aria-label={t("home.dash.cards")} className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] xl:col-start-1 xl:row-start-1" data-testid="home-cards">
          <CashCard h={h} />
          <PlannedFundingCard h={h} fixer={fixer} />
          <LowestCard h={h} open={ahead} onToggle={() => setAhead((v) => !v)} />
          {ahead ? (
            <div id="home-cash-ahead" className="min-w-0 md:col-span-2">
              <CashAhead h={h} onClose={() => setAhead(false)} />
            </div>
          ) : null}
        </section>
        <div className="min-w-0 xl:col-start-2 xl:row-span-2 xl:row-start-1">
          <FundingRing h={h} />
        </div>
        <div className="min-w-0 space-y-6 sm:space-y-8 xl:col-start-1 xl:row-start-2">
          {/* After a cure that did not restore the reserve there is no plan to run: the one remaining task, in full. */}
          {h.remaining_task ? <RemainingTaskBlock text={h.remaining_task} links={h.remaining_task_links ?? []} decisionId={h.remaining_task_decision_id} primary={h.pending_count === 0} /> : null}
          <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
          <Shortcuts />
          <RecentActivity h={h} />
        </div>
      </div>
    </div>
  );
}

/** Anything that needs the owner besides funding (a deal waiting for a reply, an approval): one slim line above the cards with its own link. */
function AttentionStrip({ h }: { h: HomeView }) {
  const item = (h.attention?.items ?? []).find((i) => !FUNDING_KINDS.has(i.kind)) ?? null;
  if (!item) return null;
  return (
    <div className="motion-reveal mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[18px] border border-warn-line bg-warn-bg px-4 py-3" role="status" data-testid="home-attention-strip">
      <AlertIcon aria-hidden width={16} height={16} className="shrink-0 text-warn-solid" />
      <p className="min-w-0 flex-1 text-sm text-warn-fg">
        <span className="font-bold">{item.eyebrow}</span> · {item.title}
      </p>
      {item.primary ? (
        <Link href={item.primary.href} className="inline-flex items-center gap-1 text-sm font-bold text-warn-fg underline underline-offset-2">
          {item.primary.label}
          <ArrowRightIcon width={12} height={12} />
        </Link>
      ) : null}
    </div>
  );
}

const DOT: Record<HomeTone, string> = { ok: "bg-ok-solid", warn: "bg-warn-solid", bad: "bg-bad-solid", neutral: "bg-ink-3" };
const BRIGHT: Record<HomeTone, string> = { ok: "text-ok-bright", warn: "text-warn-bright", bad: "text-bad-bright", neutral: "text-on-deep-muted" };
const BRIGHT_BG: Record<HomeTone, string> = { ok: "bg-ok-bright", warn: "bg-warn-bright", bad: "bg-bad-bright", neutral: "bg-on-deep-muted" };

/** The largest card, on the deep block: today's cash, the status word, and where it sits against the minimum reserve. */
function CashCard({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const c = h.cash;
  const tone = c.status_tone ?? "neutral";
  const above = (c.headroom_fen ?? c.cash_fen - c.floor_fen) >= 0;
  // The scale is drawn, not reported: the fill is today's cash, the tick the minimum, on a track a quarter longer than the larger of the two.
  const top = Math.max(c.cash_fen, c.floor_fen, 1) * 1.25;
  const fill = Math.min(Math.max(c.cash_fen / top, 0), 1) * 100;
  const tick = Math.min(c.floor_fen / top, 1) * 100;
  return (
    <article className="relative isolate flex min-h-[220px] flex-col overflow-hidden rounded-[24px] bg-brand-900 p-6 text-on-deep shadow-(--shadow-pop) sm:p-7 md:row-span-2 md:min-h-[300px]" data-testid="home-card-cash">
      <span aria-hidden className="dash-dots absolute inset-y-0 right-0 -z-10 w-2/3" />
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold text-on-deep-muted">{t("home.dash.cash")}</h2>
        {c.status_word ?? h.status_text ? (
          <span className={`inline-flex items-center gap-1.5 rounded-pill bg-white/10 px-2.5 py-1 text-supporting font-bold ${BRIGHT[tone]}`}>
            <span aria-hidden className={`size-1.5 rounded-pill ${BRIGHT_BG[tone]}`} />
            {c.status_word ?? h.status_text}
          </span>
        ) : null}
      </div>
      <p className="mt-6 font-display text-[44px] font-extrabold leading-none tracking-[-0.03em] tabular-nums sm:text-[52px]" data-testid="home-cash-value">
        {c.cash_short}
      </p>
      {above && c.headroom_short ? (
        <p className="mt-3 text-sm font-bold text-ok-bright">{t("biz.above", { amount: c.headroom_short })}</p>
      ) : !above ? (
        <p className="mt-3 text-sm font-bold text-bad-bright">{t("biz.shortToday")}</p>
      ) : null}
      <div className="mt-auto pt-8">
        <div className="relative h-2 rounded-pill bg-white/15" aria-hidden>
          <span className={`absolute inset-y-0 left-0 rounded-pill ${above ? "bg-ok-bright" : "bg-warn-bright"}`} style={{ width: `${fill}%` }} />
          <span className="absolute -top-1 h-4 w-0.5 rounded-pill bg-on-deep" style={{ left: `${tick}%` }} />
        </div>
        <p className="mt-2.5 text-supporting text-on-deep-muted">{t("home.dash.minimum", { amount: c.floor_short })}</p>
      </div>
    </article>
  );
}

/** The plan's run control when the server has one; the confirmation opens inside the card. */
function RunPlan({ a, stateVersion, fixer, review }: { a: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert>; review: { label: string; href: string } | null }) {
  const { primary, panel } = usePlanRun(a, stateVersion, fixer);
  return (
    <>
      <div className="flex flex-wrap items-center gap-2" data-testid="home-attention-run">
        {primary}
        {review ? (
          <ButtonLink href={review.href} data-testid="home-action-secondary">
            {review.label}
          </ButtonLink>
        ) : null}
      </div>
      {panel ? <div className="mt-3">{panel}</div> : null}
    </>
  );
}

/** One source of the plan (or one lot on its way): its lender's colour, its name, the server's amount and when it lands. */
function SourceRow({ hue, name, amount, when }: { hue: string; name: string; amount: string | null; when: string | null }) {
  return (
    <li className="flex items-start gap-2.5 text-supporting">
      <span aria-hidden className="mt-1 size-2.5 shrink-0 rounded-pill" style={{ background: hue }} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-ink-2" title={name}>
          {name}
        </span>
        {when ? <span className="block text-ink-3">{when}</span> : null}
      </span>
      {amount ? <span className="shrink-0 font-bold text-ink tabular-nums">{amount}</span> : null}
    </li>
  );
}

/**
 * The second card: the planned funding. Before the plan runs, how much it brings, from whom (a bar in each lender's colour, as on the ring), what it costs and
 * who decides, with the plan's run control; once it has run, what is still on its way; with nothing planned, the server's one sentence.
 */
function PlannedFundingCard({ h, fixer }: { h: HomeView; fixer: ReturnType<typeof useFixAlert> }) {
  const { t } = useI18n();
  const run = h.next_action;
  const review = (h.attention?.items ?? []).find((i) => i.kind === "funding")?.primary ?? null;
  const lots = (h.cash.funding_lots ?? []).filter((l) => !l.opening);
  const hueByName = (name: string) => lenderHue(h, h.facilities.find((f) => f.name === name)?.id ?? null);
  const state = run
    ? run.pending_approval_id
      ? { word: t("home.dash.plan.waiting"), cls: "bg-warn-bg text-warn-fg" }
      : run.needs_owner
        ? { word: t("home.dash.plan.needsYou"), cls: "bg-warn-bg text-warn-fg" }
        : { word: t("home.dash.plan.ready"), cls: "bg-info-bg text-info-fg" }
    : h.cash.in_transit
      ? { word: t("home.dash.plan.arriving"), cls: "bg-info-bg text-info-fg" }
      : lots.length
        ? { word: t("home.dash.plan.arranged"), cls: "bg-ok-bg text-ok-fg" }
        : null;
  const legs = run?.legs?.length ? run.legs : null;
  const legTotal = legs ? legs.reduce((s, l) => s + (l.amount_fen ?? 0), 0) : 0;
  return (
    <article className="flex min-w-0 flex-col rounded-[24px] bg-surface p-6 shadow-(--shadow-lift)" data-testid="home-card-funding" data-state={run ? "plan" : lots.length ? "arranged" : "none"}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span aria-hidden className="grid size-9 place-items-center rounded-pill bg-brand-600 text-on-deep">
            <BankIcon width={18} height={18} />
          </span>
          <h2 className="whitespace-nowrap text-sm font-semibold text-ink-3">{t("home.dash.plan")}</h2>
        </div>
        {state ? <span className={`whitespace-nowrap rounded-pill px-2.5 py-1 text-supporting font-bold ${state.cls}`}>{state.word}</span> : null}
      </div>
      {run ? (
        <>
          <p className="mt-4 font-display text-[30px] font-extrabold leading-none tracking-[-0.02em] text-ink tabular-nums" data-testid="home-plan-value">
            {run.receive_short ?? run.outcome_title}
          </p>
          {legs && legTotal > 0 ? (
            <div className="mt-4 flex h-2.5 gap-1 overflow-hidden rounded-pill" aria-hidden>
              {legs.map((l) => (
                <span key={l.index} className="h-full rounded-pill" style={{ width: `${((l.amount_fen ?? 0) / legTotal) * 100}%`, background: lenderHue(h, l.facility_id) }} />
              ))}
            </div>
          ) : null}
          <ul className="mt-3 space-y-1.5">
            {(legs ?? []).map((l) => (
              <SourceRow key={l.index} hue={lenderHue(h, l.facility_id)} name={l.name_display ?? l.facility_name} amount={l.amount_display} when={l.lands_when ?? null} />
            ))}
          </ul>
          {run.cost_total_display ?? run.cost_display ? (
            <p className="mt-3 text-supporting text-ink-3">
              {t("home.dash.plan.cost")} <span className="font-bold text-ink tabular-nums">{run.cost_total_display ?? run.cost_display}</span>
            </p>
          ) : null}
          {/* The plan's own control, under the id the rest of the app knows it by (the alert it cures). */}
          <div className="mt-4" data-testid="home-next-action" data-alert={run.alert_id}>
            <RunPlan a={run} stateVersion={h.state_version} fixer={fixer} review={review} />
          </div>
        </>
      ) : lots.length ? (
        <>
          <p className="mt-3 text-sm text-ink-2">{h.funding_line?.text}</p>
          <ul className="mt-3 space-y-1.5">
            {lots.map((l, i) => (
              <SourceRow key={i} hue={hueByName(l.facility_name)} name={l.facility_name} amount={l.amount_display} when={l.landed ? t("home.dash.plan.landed") : l.arrival_when} />
            ))}
          </ul>
        </>
      ) : (
        <div className="mt-4 flex items-start gap-2.5">
          <CheckCircleIcon aria-hidden width={18} height={18} className="mt-0.5 shrink-0 text-ok-solid" />
          <p className="text-sm text-ink-2">{h.funding_line?.text ?? t("home.dash.plan.none")}</p>
        </div>
      )}
    </article>
  );
}

/** The third card, the smallest: the lowest cash ahead, when it comes, and a small line of the days ahead. The whole card opens the full range below the cards. */
function LowestCard({ h, open, onToggle }: { h: HomeView; open: boolean; onToggle: () => void }) {
  const { t } = useI18n();
  const c = h.cash;
  const tone = c.lowest_tone ?? "ok";
  const ink = tone === "bad" ? "text-bad-fg" : tone === "warn" ? "text-warn-fg" : "text-ink";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-controls="home-cash-ahead"
      className={`motion-press group flex min-w-0 items-center gap-4 rounded-[24px] bg-surface p-5 text-left shadow-(--shadow-lift) transition-shadow hover:shadow-(--shadow-pop) ${open ? "ring-2 ring-brand-600" : ""}`}
      data-testid="home-card-lowest"
    >
      <span className="min-w-0 shrink-0">
        <span className="block text-sm font-semibold text-ink-3">{t("home.dash.lowest")}</span>
        <span className={`mt-1 block font-display text-2xl font-extrabold tracking-[-0.02em] tabular-nums ${ink}`} data-testid="home-lowest-value">
          {c.lowest_short}
        </span>
        <span className="block text-supporting text-ink-3">{c.lowest_when}</span>
      </span>
      <Sparkline h={h} tone={tone} />
      <span className="flex shrink-0 flex-col items-center gap-1 text-meta font-bold text-brand-700">
        <span aria-hidden className="grid size-7 place-items-center rounded-pill bg-brand-50 transition-colors group-hover:bg-brand-100">
          <ChevronRightIcon width={14} height={14} className={`transition-transform duration-(--dur-fast) ${open ? "-rotate-90" : "rotate-90"}`} />
        </span>
        {open ? t("home.dash.lowest.less") : t("home.dash.lowest.more")}
      </span>
    </button>
  );
}

/** The days ahead as one line with the minimum dashed under it; the lowest point is a dot. Drawn from fen, labelled by the card. */
function Sparkline({ h, tone }: { h: HomeView; tone: "ok" | "warn" | "bad" }) {
  const days = h.cash.picture_days ?? 60;
  const pts = h.cash.series.filter((p) => p.day - h.day <= days);
  if (pts.length < 2) return null;
  const W = 160;
  const H = 56;
  const vals = pts.map((p) => p.closing_fen);
  const hi = Math.max(...vals, h.cash.floor_fen);
  const lo = Math.min(...vals, h.cash.floor_fen);
  const span = hi - lo || 1;
  const x = (i: number) => (i / (pts.length - 1)) * W;
  const y = (fen: number) => 4 + (1 - (fen - lo) / span) * (H - 8);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.closing_fen).toFixed(1)}`).join(" ");
  const low = vals.indexOf(Math.min(...vals));
  const stroke = tone === "bad" ? "var(--color-bad-solid)" : tone === "warn" ? "var(--color-warn-solid)" : "var(--color-chart-base)";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="ml-auto h-14 w-full min-w-0 max-w-[180px]" aria-hidden preserveAspectRatio="none">
      <line x1={0} x2={W} y1={y(h.cash.floor_fen)} y2={y(h.cash.floor_fen)} stroke="var(--color-chart-reserve)" strokeWidth={1} strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      <path d={d} fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={x(low)} cy={y(vals[low])} r={3.5} fill={stroke} />
    </svg>
  );
}

const SHORTCUTS: { href: string; key: DictKey; icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { href: "/cash", key: "nav.cash", icon: WalletIcon },
  { href: "/deals", key: "nav.deals", icon: DealsIcon },
  { href: "/receivables", key: "nav.receivables", icon: InboxInIcon },
  { href: "/activity", key: "nav.activity", icon: ActivityIcon },
];

/** The shortcuts: one pill per section, an icon in a dark circle and the section's name. */
function Shortcuts() {
  const { t } = useI18n();
  return (
    <nav aria-label={t("home.dash.shortcuts")} data-testid="home-shortcuts">
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {SHORTCUTS.map(({ href, key, icon: Icon }) => (
          <li key={href}>
            <Link
              href={href}
              className="motion-press group flex items-center gap-3 rounded-[18px] bg-surface py-2.5 pl-2.5 pr-4 text-sm font-bold text-ink shadow-(--shadow-lift) transition-colors hover:bg-brand-600 hover:text-on-deep focus-visible:bg-brand-600 focus-visible:text-on-deep"
            >
              <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-pill bg-brand-900 text-on-deep transition-colors group-hover:bg-on-deep group-hover:text-brand-600">
                <Icon width={18} height={18} />
              </span>
              <span className="min-w-0 leading-tight">{t(key)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

const KIND_TONE: Record<string, HomeTone> = { OPERATION: "ok", RECEIPT: "ok", LANDED: "ok", AGREEMENT: "ok", WAITING: "neutral", REFUSED: "bad", LATE: "bad" };
const CHIP: Record<HomeTone, string> = { ok: "bg-ok-bg text-ok-fg", warn: "bg-warn-bg text-warn-fg", bad: "bg-bad-bg text-bad-fg", neutral: "bg-subtle text-ink-2" };

/** Recent activity: the server's last few changes, one row each with when and a state chip. */
function RecentActivity({ h }: { h: HomeView }) {
  const { t, te } = useI18n();
  const rows = h.changes_card?.rows ?? h.changes.map((c) => ({ id: c.id ?? undefined, text: c.event_text ?? c.text, when: c.when, kind: String(c.kind) }));
  const shown = rows.slice(0, 4);
  return (
    <section aria-labelledby="home-recent-title" data-testid="home-recent">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 id="home-recent-title" className="font-display text-lg font-extrabold tracking-[-0.01em] text-ink">
          {t("home.dash.recent")}
        </h2>
        <Link href={h.changes_card?.href ?? "/activity"} className="inline-flex items-center gap-1 text-supporting font-semibold text-ink-3 hover:text-brand-700">
          {t("home.dash.seeAll")}
          <ArrowRightIcon width={12} height={12} />
        </Link>
      </div>
      {shown.length ? (
        <ul className="space-y-2.5">
          {shown.map((r, i) => {
            const tone = KIND_TONE[r.kind ?? ""] ?? "neutral";
            return (
              <li key={r.id ?? i} className="flex items-center gap-3 rounded-[18px] bg-surface px-4 py-3 shadow-(--shadow-lift)" data-testid="home-recent-row">
                <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-pill bg-subtle text-ink-2">
                  <ClockIcon width={16} height={16} />
                </span>
                <p className="min-w-0 flex-1 text-sm text-ink line-clamp-2">{r.text}</p>
                {r.when ? <span className="hidden shrink-0 text-supporting text-ink-3 sm:block">{r.when}</span> : null}
                {r.kind ? (
                  <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-pill px-2.5 py-1 text-supporting font-bold ${CHIP[tone]}`}>
                    <span aria-hidden className={`size-1.5 rounded-pill ${DOT[tone]}`} />
                    {te("home.dash.kind", r.kind)}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="rounded-[18px] bg-surface px-4 py-4 text-sm text-ink-3 shadow-(--shadow-lift)">{h.changes_card?.empty_text ?? t("home.hy.changes.none")}</p>
      )}
    </section>
  );
}
