"use client";

import { Area, Bar, CartesianGrid, Cell, ComposedChart, Line, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisYuanK } from "@/lib/chart-helpers";
import { getHome, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractFieldName, DocumentView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { LoadingBlock } from "./ui";

/**
 * The deal at a glance, the first thing the owner sees once a document is read (a portfolio summary, for a deal): the terms
 * that move money as tiles, the cash position over the forecast with this counterparty's payments marked, the loans and credit lines
 * with how much is drawn, each source's interest rate, and the cash the owner can reach today.
 *
 * Every figure shown is a server string (`*_display`, `*_short`, `value_display`); fen and bp only size marks (INVARIANT 13). The
 * picture reads the books as they are: confirming the document does not change them, so neither does this.
 */

const C = {
  cash: "var(--color-chart-base)",
  deal: "var(--color-chart-teal)",
  plan: "var(--color-chart-purple)",
  reserve: "var(--color-chart-reserve)",
  grid: "var(--color-chart-grid)",
  axis: "var(--color-chart-axis)",
  navy: "var(--color-chart-navy)",
  sky: "var(--color-chart-sky)",
};
const SLICES = [C.cash, C.deal, C.plan, C.sky, C.navy];
const axisProps = { stroke: C.axis, fontSize: 12, tickLine: false } as const;

/** The buyer-contract terms that move money or time, in the order an owner asks about them. */
const BUYER_TILES: ContractFieldName[] = ["PRICE", "PAYMENT_TERMS", "EARLY_PAYMENT", "LATE_INTEREST", "INVOICING", "DURATION"];
/** The lender-agreement clauses, likewise. */
const LENDER_TILES = ["principal", "rate", "fee", "advance_rate", "tenor", "lead_time"];

interface Row {
  day: number;
  cash: number;
  cashDisplay: string;
  /** fen, bar height only: this counterparty's receipts that day */
  deal: number | null;
  dealShort: string[];
  plan: number | null;
  planDisplay: string | null;
}

export function DealPicture({ doc }: { doc: DocumentView }) {
  const { t, te, lang } = useI18n();
  const home = useAsync(() => getHome(lang), [lang]);
  const state = useAsync(getState, []);
  const lender = doc.kind === "LENDER_AGREEMENT";
  const focusFacility = doc.linked_facility_id ?? doc.suggested_facility_id ?? doc.compared_with ?? null;

  // ---------------------------------------------------------------- the terms, as tiles
  const tiles: { key: string; label: string; value: string | null }[] = lender
    ? LENDER_TILES.flatMap((f) => {
        const c = doc.clauses?.find((x) => x.field === f);
        return c ? [{ key: f, label: te("clausefield", f), value: c.value_text }] : [];
      })
    : BUYER_TILES.flatMap((f): { key: string; label: string; value: string | null }[] => {
        const term = doc.terms?.find((x) => x.field === f);
        if (term) return [{ key: f, label: te("contractfield", f) || term.label, value: term.value_display }];
        const blank = doc.blanks?.find((b) => b.field === f);
        return blank ? [{ key: f, label: te("contractfield", f) || blank.label, value: null }] : [];
      });

  return (
    <section aria-labelledby="deal-picture-title" className="motion-reveal space-y-4" data-testid="deal-picture">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="deal-picture-title" className="scroll-mt-24 font-display text-xl text-ink sm:text-2xl">
            {t("pic.title")}
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-ink-2">{t(lender ? "pic.sub.lender" : "pic.sub.buyer", { name: doc.counterparty_name })}</p>
        </div>
      </div>

      {tiles.length ? (
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="deal-picture-terms">
          {tiles.map((x) => (
            <div key={x.key} className="min-w-0 rounded-tile border border-line bg-surface p-4 shadow-card">
              <dt className="text-xs font-bold uppercase tracking-wide text-ink-3">{x.label}</dt>
              <dd className={`mt-1.5 break-words text-base font-bold leading-snug ${x.value ? "text-ink" : "text-ink-3"}`}>{x.value ?? t("pic.notInContract")}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {home.error ? null : !home.data || !state.data ? (
        <LoadingBlock rows={3} />
      ) : (
        <PictureBody doc={doc} lender={lender} focusFacility={focusFacility} home={home.data} state={state.data} />
      )}
    </section>
  );
}

function PictureBody({
  doc,
  lender,
  focusFacility,
  home,
  state,
}: {
  doc: DocumentView;
  lender: boolean;
  focusFacility: string | null;
  home: Awaited<ReturnType<typeof getHome>>;
  state: Awaited<ReturnType<typeof getState>>;
}) {
  const { t } = useI18n();
  const cash = home.cash;
  const name = doc.counterparty_name;

  // This counterparty's receipts are the forecast's own RECEIPT events that name it; their sum on a day sizes a bar, nothing more.
  const planByDay = new Map((cash.plan_series ?? []).map((p) => [p.day, p]));
  const rows: Row[] = cash.series.map((p) => {
    const mine = lender ? [] : p.events.filter((e) => e.kind.includes("RECEIPT") && e.label.includes(name));
    const plan = planByDay.get(p.day);
    return {
      day: p.day,
      cash: p.closing_fen,
      cashDisplay: p.closing_display,
      deal: mine.length ? mine.reduce((s, e) => s + e.amount_fen, 0) : null,
      dealShort: mine.map((e) => e.amount_short),
      plan: plan ? plan.closing_fen : null,
      planDisplay: plan ? plan.closing_display : null,
    };
  });
  const showPlan = lender && rows.some((r) => r.plan !== null);
  // The forecast runs from today; the axis and the tooltip say distances from today ("today", "+10d", "in 10 days"), never an absolute day number.
  const today = home.day;
  const to = rows.length ? rows[rows.length - 1].day : today + cash.horizon_days;
  const span = Math.max(to - today, 1);
  const tick = (d: number) => (d === today ? t("biz.when.today") : t("pic.tick", { n: d - today }));
  const ticks: number[] = [];
  for (let d = today; d <= to; d += span > 60 ? 30 : 10) ticks.push(d);
  const yMin = Math.min(0, ...rows.map((r) => r.cash), ...rows.map((r) => r.plan ?? 0));

  const facilities = state.state.facilities.filter((f) => f.limit_fen > 0 && (f.status === "COMMITTED" || f.id === focusFacility));
  const debts = state.state.debts ?? [];
  // Cash you can reach: cash today and each committed line's undrawn part. The slices are sized by fen (plotting); every label is the server's.
  const reach = [
    { name: t("pic.reach.cash"), fen: Math.max(cash.cash_fen, 0), display: cash.cash_display },
    ...home.facilities
      .filter((f) => f.status === "COMMITTED" && (f.limit_fen ?? 0) > 0)
      .map((f) => ({ name: f.name, fen: Math.max((f.limit_fen ?? 0) - (f.drawn_fen ?? 0), 0), display: f.available_display })),
  ].filter((x) => x.fen > 0);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      {/* Cash position */}
      <figure className="min-w-0 rounded-card border border-line bg-surface p-5 shadow-card" data-testid="deal-picture-cash">
        <figcaption>
          <h3 className="text-base font-bold text-ink">{t("pic.cash")}</h3>
          <p className="mt-0.5 text-xs text-ink-3">{t(lender ? "pic.cash.lender" : "pic.cash.sub", { n: span, name })}</p>
        </figcaption>
        <dl className="mt-4 grid grid-cols-3 gap-3">
          <Figure label={t("pic.cashToday")} value={cash.cash_short} />
          {/* The comparison only sizes a mark (the figure's colour); it states no money. The words and amounts are the server's. */}
          <Figure label={t("pic.lowest")} value={cash.lowest_short} sub={cash.lowest_when} bad={cash.lowest_fen < cash.floor_fen} />
          <Figure label={t("pic.reserve")} value={cash.floor_short} />
        </dl>
        <div className="mt-4 h-64 w-full sm:h-72" role="img" aria-label={t("pic.cash.aria", { today: cash.cash_short, lowest: cash.lowest_short, floor: cash.floor_short })}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="pic-cash-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={C.cash} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={C.cash} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" type="number" domain={[today, to]} ticks={ticks} tickFormatter={tick} {...axisProps} />
              <YAxis width={56} tickFormatter={axisYuanK} domain={[yMin, "auto"]} {...axisProps} />
              {yMin < 0 ? <ReferenceLine y={0} stroke={C.axis} /> : null}
              <Tooltip content={<RowTooltip dayText={(n) => (n === today ? t("biz.when.today") : t("biz.when.inDays", { n: n - today }))} cashLabel={t("pic.legend.cash")} dealLabel={t("pic.legend.deal", { name })} planLabel={showPlan ? t("pic.legend.plan") : null} />} />
              <Area type="stepAfter" dataKey="cash" stroke={C.cash} strokeWidth={2.5} fill="url(#pic-cash-fill)" isAnimationActive={false} />
              {!lender ? <Bar dataKey="deal" fill={C.deal} barSize={10} radius={[4, 4, 0, 0]} isAnimationActive={false} /> : null}
              {showPlan ? <Line type="stepAfter" dataKey="plan" stroke={C.plan} strokeWidth={2} strokeDasharray="8 5" dot={false} isAnimationActive={false} /> : null}
              <ReferenceLine y={cash.floor_fen} stroke={C.reserve} strokeDasharray="6 4" label={{ value: t("pic.reserveLine", { amount: cash.floor_short }), position: "insideTopRight", fill: C.reserve, fontSize: 12 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-2">
          <Legend color={C.cash} label={t("pic.legend.cash")} />
          {!lender ? <Legend color={C.deal} label={t("pic.legend.deal", { name })} /> : null}
          {showPlan ? <Legend color={C.plan} label={t("pic.legend.plan")} dashed /> : null}
          <Legend color={C.reserve} label={t("pic.reserve")} dashed />
        </ul>
      </figure>

      {/* Cash you can reach */}
      <figure className="min-w-0 rounded-card border border-line bg-surface p-5 shadow-card" data-testid="deal-picture-reach">
        <figcaption>
          <h3 className="text-base font-bold text-ink">{t("pic.reach")}</h3>
          <p className="mt-0.5 text-xs text-ink-3">{t("pic.reach.sub")}</p>
        </figcaption>
        <div className="mt-3 flex flex-col items-center gap-4">
          <div className="relative size-40 shrink-0" role="img" aria-label={reach.map((r) => `${r.name} ${r.display}`).join(", ")}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={reach} dataKey="fen" nameKey="name" innerRadius="68%" outerRadius="100%" paddingAngle={2} stroke="none" isAnimationActive={false}>
                  {reach.map((r, i) => (
                    <Cell key={r.name} fill={SLICES[i % SLICES.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
              <span>
                <span className="block text-xs font-bold uppercase tracking-wide text-ink-3">{t("pic.reach.cash")}</span>
                <span className="block font-display text-lg text-ink">{cash.cash_short}</span>
              </span>
            </div>
          </div>
          <ul className="w-full min-w-0 space-y-2 text-sm">
            {reach.map((r, i) => (
              <li key={r.name} className="flex items-start justify-between gap-2">
                <span className="flex min-w-0 items-start gap-2">
                  <span aria-hidden className="mt-1.5 size-2.5 shrink-0 rounded-full" style={{ background: SLICES[i % SLICES.length] }} />
                  <span className="min-w-0 text-ink-2">{r.name}</span>
                </span>
                <span className="shrink-0 font-bold tabular-nums text-ink">{r.display}</span>
              </li>
            ))}
          </ul>
        </div>
      </figure>

      {/* Loans and credit lines */}
      <figure className="min-w-0 rounded-card border border-line bg-surface p-5 shadow-card lg:col-span-2" data-testid="deal-picture-loans">
        <figcaption>
          <h3 className="text-base font-bold text-ink">{t("pic.loans")}</h3>
          <p className="mt-0.5 text-xs text-ink-3">{t("pic.loans.sub")}</p>
        </figcaption>
        <ul className="mt-3 grid gap-x-8 md:grid-cols-2">
          {facilities.map((f) => (
            <li key={f.id} className={`border-b border-line py-2.5 ${f.id === focusFacility ? "-mx-2 rounded-tile border-transparent bg-sec-deals-bg px-2" : ""}`} data-testid={`deal-picture-facility-${f.id}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="min-w-0 text-sm font-bold text-ink">
                  {f.name}
                  {f.id === focusFacility ? <span className="ml-2 rounded-pill bg-surface px-2 py-px text-xs font-bold text-sec-deals-fg">{t("pic.thisDoc")}</span> : null}
                </span>
                <span className="text-sm font-bold tabular-nums text-ink">{t("pic.rateAt", { rate: f.rate_display })}</span>
              </div>
              <Meter used={f.drawn_fen} limit={f.limit_fen} />
              <p className="mt-1 text-xs text-ink-3">{t("pic.drawnOf", { drawn: f.drawn_display, limit: f.limit_display })}</p>
            </li>
          ))}
          {debts.map((d) => (
            <li key={d.id} className="border-b border-line py-2.5" data-testid={`deal-picture-debt-${d.id}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="min-w-0 text-sm font-bold text-ink">{d.label}</span>
                {d.rate_display ? <span className="text-sm font-bold tabular-nums text-ink">{t("pic.rateAt", { rate: d.rate_display })}</span> : null}
              </div>
              <p className="mt-1 text-xs text-ink-3">{t("pic.loanLine", { principal: d.principal_display, monthly: d.monthly_debt_service_display })}</p>
            </li>
          ))}
        </ul>
      </figure>
    </div>
  );
}

function Figure({ label, value, sub, bad }: { label: string; value: string; sub?: string | null; bad?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-bold uppercase tracking-wide text-ink-3">{label}</dt>
      <dd className={`mt-0.5 font-display text-lg tabular-nums sm:text-xl ${bad ? "text-bad-fg" : "text-ink"}`}>{value}</dd>
      {sub ? <dd className="text-xs text-ink-3">{sub}</dd> : null}
    </div>
  );
}

/** How much of this line is used: the track is its own limit, the fill what is drawn. Plotting only. */
function Meter({ used, limit }: { used: number; limit: number }) {
  return (
    <div className="mt-2 h-1.5 overflow-hidden rounded-pill bg-brand-100">
      <div className="h-full rounded-pill" style={{ width: limit ? `${Math.min(100, (used / limit) * 100)}%` : 0, background: C.cash }} />
    </div>
  );
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <li className="flex items-center gap-1.5">
      <span aria-hidden className="inline-block h-0.5 w-4" style={dashed ? { borderTop: `2px dashed ${color}` } : { background: color, height: 3, borderRadius: 2 }} />
      {label}
    </li>
  );
}

function RowTooltip({
  active,
  payload,
  dayText,
  cashLabel,
  dealLabel,
  planLabel,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
  dayText: (n: number) => string;
  cashLabel: string;
  dealLabel: string;
  /** null when the plan line is not drawn, so the tooltip does not name it */
  planLabel: string | null;
}) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="max-w-64 rounded-tile border border-line-strong bg-surface p-2.5 text-xs shadow-pop">
      <p className="font-bold text-ink">
        {dayText(r.day)}
      </p>
      <p className="mt-1 flex justify-between gap-3 tabular-nums">
        <span className="text-ink-2">{cashLabel}</span>
        <span className="font-bold text-ink">{r.cashDisplay}</span>
      </p>
      {r.planDisplay && planLabel ? (
        <p className="flex justify-between gap-3 tabular-nums">
          <span className="text-ink-2">{planLabel}</span>
          <span className="font-bold text-ink">{r.planDisplay}</span>
        </p>
      ) : null}
      {r.dealShort.length ? (
        <p className="flex justify-between gap-3 tabular-nums">
          <span className="text-ink-2">{dealLabel}</span>
          <span className="font-bold text-ok-fg">{r.dealShort.join(" + ")}</span>
        </p>
      ) : null}
    </div>
  );
}
