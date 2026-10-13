"use client";

import { useId, useMemo } from "react";
import { CashPreview, LegendItem, type InspectorWords, type PreviewLine } from "@/components/home/v2/cash-preview";
import { pointAt, shown } from "@/components/home/v2/company-chart";
import { Breakdown } from "@/components/home/v2/breakdown";
import { fromWarm, key } from "@/components/home/v2/prefetch";
import { Announce, Dismiss, LeaveLink } from "@/components/home/v2/focus-parts";
import { ActionGroup } from "@/components/ui/action-group";
import { ComparisonTable, type CompareColumn, type CompareRow } from "@/components/ui/comparison-table";
import { OpenSection } from "@/components/ui/open-section";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { StateWord } from "@/components/ui/state-word";
import { Disclosure } from "@/components/business/kit";
import { Button, ButtonLink, ErrorState, LoadingBlock } from "@/components/ui";
import { getCustomerFocus, getDealExposure, getDealTitle, getDeals } from "@/lib/api";
import { offerOfDecision } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { ExposurePathWords, ExposureStress, HomeSeriesPoint, HomeView, OfferPictureView, PicturePath, WorklistCustomer, WorklistNeedsRow, WorklistWaitingRow } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useDelayed } from "@/lib/use-delayed";

type Tone = "ok" | "warn" | "bad" | "info" | "neutral";
const AUTH_TONE: Record<string, Tone> = { flow_may: "ok", needs_owner: "warn", over_limit: "bad" };
const TAG_TONE = (t: string): Tone => (t === "mute" ? "neutral" : (t as Tone));

/** The deal's own view of the page, kept in the address (`compare`, `chart`, `timing`): which investigation is open and which payment assumption the figures are read under. */
export interface DealView {
  compare: boolean;
  chart: boolean;
  /** The payment-timing assumption: null is the expected payments, "late" the buyer's late-payment test. */
  timing: "late" | null;
}

const upper = "first-letter:uppercase";

/** A figure with the words beside it: the server's display and its `when`, or the sentence under it. */
function Cell({ value, bad, note, sub }: { value?: string | null; bad?: boolean; note?: string | null; sub?: string | null }) {
  return (
    <>
      {value ? <span className={`block font-display text-base font-bold leading-snug tabular-nums ${bad ? "text-bad-fg" : "text-ink"}`}>{value}</span> : null}
      {sub ? <span className="block text-supporting text-ink-3">{sub}</span> : null}
      {note ? <span className={`block text-supporting ${bad ? "text-bad-fg" : "text-ink-2"} ${upper}`}>{note}</span> : null}
    </>
  );
}

/** Lowest cash for a path: from the expected payments (the exposure read's words) or the late-payment test (the stress words). */
function lowestOf(path: PicturePath, words: ExposurePathWords | undefined, stress: ExposureStress | null | undefined, late: boolean) {
  if (late) {
    if (!stress?.available) return { value: null, sub: null, note: stress?.unavailable_text ?? null, bad: false };
    return { value: stress.lowest_short ?? stress.lowest_display ?? null, sub: stress.lowest_when ?? null, note: stress.breach_days_text ?? stress.text ?? null, bad: (stress.breach_days ?? 0) > 0 };
  }
  return { value: words?.lowest_display ?? path.lowest_short ?? null, sub: words?.lowest_when ?? path.lowest_when ?? null, note: words?.lowest_when_text ?? path.band_text ?? null, bad: path.first_breach_when !== null };
}

/**
 * A decision, in place, in three levels of which only the first two are on the page until asked.
 * Level 1, the decision: the way up, the verdict word, "{Customer} · {subject}", the customer line with "View customer", the buyer's ask in one line, FLOW's recommendation with its
 * own sentence and cost, the request's cost, and the action group: "Review counter" (the page's one filled button, the same control Deals uses), "Compare responses" and
 * "Cash impact" (outlined toggles) and "Open in Deals".
 * Level 2, the consequence: the payment-timing assumption, then one table of the request against the recommended option (the lowest cash, the reserve, the limit, the approval)
 * and the one line saying what the scenario assumes.
 * Level 3, only on request: the full table of every response with FLOW's reasons under it ("Compare responses"), and the deal's own cash chart with its same-day inspector ("Cash impact").
 * Every figure and sentence is the server's (the offer picture, the exposure read, the overview); the dictionary supplies only labels.
 */
export function DealFocusPanel({
  customerId,
  buyer,
  decision,
  row,
  customer,
  h,
  picture,
  view,
  onView,
  onAll,
  onCustomer,
}: {
  customerId: string;
  buyer: string;
  decision: string;
  row: WorklistNeedsRow | WorklistWaitingRow | null;
  customer: WorklistCustomer | null;
  h: HomeView;
  /** The offer's picture (one read, lifted to the page: the outlook card draws its paths too). */
  picture: { data: OfferPictureView | null | undefined; error: Error | undefined; loading: boolean };
  view: DealView;
  onView: (patch: Partial<DealView>) => void;
  onAll: () => void;
  onCustomer: () => void;
}) {
  const { t, lang } = useI18n();
  const uid = useId();
  const offerId = offerOfDecision(decision);
  const overview = useAsync(() => fromWarm(key.overview(customerId, decision, lang), () => getCustomerFocus(customerId, lang, { decision })), [customerId, decision, lang]);
  const exposure = useAsync(() => fromWarm(key.exposure(offerId, customerId, lang), () => getDealExposure(offerId, lang, customerId).catch(() => null)), [offerId, customerId, lang]);
  const deals = useAsync(() => fromWarm(key.deals(lang), () => getDeals(lang).catch(() => null)), [lang]);
  const serverTitle = useAsync(() => fromWarm(key.title(decision, lang), () => getDealTitle(decision, lang)), [decision, lang]);
  // The card keeps its height while its first read is on its way and shows a skeleton only after 300 ms, so a quick read never flashes one and nothing below jumps.
  const slow = useDelayed(overview.data === undefined && !overview.error, 300);
  const v = overview.data;
  const settled = !overview.loading && v !== undefined;
  const gone = settled && v.context?.deal !== decision;
  const decisionCard = v?.decision ?? null;
  const open = deals.data?.deals.find((d) => d.counterparty_id === customerId)?.open_offer ?? null;
  const paths = useMemo(() => (picture.data?.paths ?? []).filter((p) => p.kind === "asked" || p.kind === "reply"), [picture.data]);
  const asked = paths.find((p) => p.kind === "asked") ?? null;
  const recommended = paths.find((p) => p.kind === "reply" && p.recommended) ?? null;
  const wordsOf = (p: PicturePath) => exposure.data?.paths.find((x) => x.key === p.key);
  const stressOf = (p: PicturePath) => exposure.data?.stress.paths[p.key] ?? null;
  const late = view.timing === "late";
  const lateDays = exposure.data?.stress.delay_days ?? 0;
  const title = row?.subject_text ?? decisionCard?.headline_short ?? v?.name ?? "";
  const timingWord = late ? t("home.hy.scenario.late", { buyer, n: lateDays }) : t("home.hy.scenario.expected");
  const authority = (p: PicturePath) => <StateWord tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"}>{p.authority_text ?? p.decides_text}</StateWord>;
  const limit = (p: PicturePath) => {
    const w = wordsOf(p);
    if (!w?.limit_text) return null;
    return (
      <StateWord tone={w.limit_word === "EXCEEDED" ? "bad" : "ok"}>
        <span className={upper}>{w.limit_text}</span>
      </StateWord>
    );
  };

  // ---- level 2: the request against the recommended option
  const pair = [asked, recommended].filter((p): p is PicturePath => p !== null);
  const pairColumns: CompareColumn[] = pair.map((p) => ({ key: p.key, head: p.label, tag: <StateWord tone={TAG_TONE(p.tag_tone)}>{p.tag_text}</StateWord>, recommended: p.recommended }));
  const lowestRow = (p: PicturePath) => lowestOf(p, wordsOf(p), stressOf(p), late);
  const pairRows: CompareRow[] = [
    { key: "lowest", label: t("hv2.deal.lowest"), cells: pair.map((p) => { const l = lowestRow(p); return <Cell key={p.key} value={l.value} sub={l.sub} bad={l.bad} />; }) },
    { key: "reserve", label: t("hv2.deal.reserve"), cells: pair.map((p) => { const l = lowestRow(p); return <Cell key={p.key} note={l.note} bad={l.bad} />; }) },
    { key: "limits", label: t("hv2.deal.limits"), cells: pair.map((p) => limit(p) ?? <span key={p.key} className="text-supporting text-ink-3">—</span>) },
    { key: "approval", label: t("hv2.deal.approval"), cells: pair.map((p) => <span key={p.key}>{authority(p)}</span>) },
  ];
  const assumption = (recommended?.scenario_assumption_text ?? wordsOf(recommended ?? asked ?? ({ key: "" } as PicturePath))?.scenario_assumption_text) || null;

  // ---- level 3: every response
  const term = (p: PicturePath, key: string) => p.terms.find((x) => x.key === key);
  const fullColumns: CompareColumn[] = paths.map((p) => ({
    key: p.key,
    head: p.label,
    tag: <StateWord tone={TAG_TONE(p.tag_tone)}>{p.tag_text}</StateWord>,
    evidence: p.recommended ? p.recommended_reason_text : p.authority_reason_text,
    recommended: p.recommended,
  }));
  const termCell = (p: PicturePath, key: string) => {
    const x = term(p, key);
    return x ? <Cell key={`${p.key}-${key}`} value={x.value_text} sub={x.instead_of_text} /> : <span key={`${p.key}-${key}`}>—</span>;
  };
  const economics = (p: PicturePath) => {
    const parts = p.cost_components ?? [];
    if (p.cost_forward_display && p.cost_once_display) {
      return (
        <span key={p.key}>
          <Cell value={p.cost_forward_display} bad={p.authority === "over_limit"} />
          <Cell value={p.cost_once_display} sub={p.cost_basis_text} />
        </span>
      );
    }
    return (
      <span key={p.key}>
        <Cell value={p.cost_total_display ?? p.cost_display} sub={p.cost_basis_text ?? p.cost_note} />
        {parts.length ? (
          <span className="mt-1.5 block border-t border-dashed border-line-strong pt-1.5 text-supporting text-ink-2">
            {parts.map((c) => (
              <span key={c.label} className="flex justify-between gap-2">
                <span>{c.label}</span>
                <span className="whitespace-nowrap tabular-nums">{c.display}</span>
              </span>
            ))}
          </span>
        ) : null}
      </span>
    );
  };
  const fullRows: CompareRow[] = [
    { key: "terms", label: t("hv2.deal.terms"), cells: paths.map((p) => termCell(p, "payment_terms")) },
    { key: "change", label: t("hv2.deal.change"), cells: paths.map((p) => (<span key={p.key}>{termCell(p, "early_payment")}<span className="mt-2 block">{termCell(p, "rebate_or_price")}</span></span>)) },
    { key: "economics", label: t("hv2.deal.economics"), cells: paths.map(economics) },
    { key: "lowest", label: t("hv2.deal.lowest"), cells: paths.map((p) => { const l = lowestRow(p); return <Cell key={p.key} value={l.value} sub={l.sub} note={l.note} bad={l.bad} />; }) },
    { key: "limits", label: t("hv2.deal.limits"), cells: paths.map((p) => limit(p) ?? <span key={p.key}>—</span>) },
    { key: "approval", label: t("hv2.deal.approval"), cells: paths.map((p) => <span key={p.key}>{authority(p)}</span>) },
  ];

  // ---- the deal's cash chart: the recommended option solid, the request grey with its stretches under the reserve in red
  const seriesOf = (p: PicturePath | null): HomeSeriesPoint[] => {
    if (!p) return [];
    const s = late ? stressOf(p) : null;
    if (late && s?.series?.length) return s.series.map((x) => ({ ...x, events: [] }));
    return p.series ?? [];
  };
  const lines: PreviewLine[] = [];
  if (asked) lines.push({ key: asked.key, label: asked.label, style: "request", points: seriesOf(asked) });
  if (recommended) lines.push({ key: recommended.key, label: recommended.label, style: "option", points: seriesOf(recommended) });
  const lowestDayOf = (pts: HomeSeriesPoint[]) => pts.filter((p) => p.day >= h.day).reduce<HomeSeriesPoint | null>((a, b) => (a === null || b.closing_fen < a.closing_fen ? b : a), null)?.day ?? h.day;
  const askedLow = lowestDayOf(seriesOf(asked));
  const moments = picture.data?.moments ?? [];
  const chartDays = [...new Set([...moments.map((m) => m.day), askedLow, lowestDayOf(seriesOf(recommended))])].sort((a, b) => a - b);
  const chartWords = (day: number): InspectorWords => {
    const whenWord = pointAt(h.cash.series, day)?.when ?? moments.find((m) => m.day === day)?.word ?? moments.find((m) => m.day === day)?.label ?? "";
    const a = pointAt(seriesOf(asked), day);
    const o = pointAt(seriesOf(recommended), day);
    // The picture's own same-day comparison (the request, the recommended reply and the server's signed difference); until the server sends it, the two series' figures and the moment's difference.
    const cmp = pointAt(late ? [] : (recommended?.series ?? []), day)?.comparison ?? null;
    const diff = cmp?.difference_display ?? moments.find((m) => m.day === day)?.values.find((x) => x.key === recommended?.key)?.vs_asked_short;
    return {
      cells: [
        { key: "when", label: t("hv2.chart.when"), value: whenWord },
        { key: "request", label: asked?.label ?? "", value: cmp?.asked_display ?? shown(a), tone: a && a.closing_fen < h.cash.floor_fen ? "bad" : undefined },
        { key: "option", label: recommended?.label ?? "", value: cmp?.recommended_display ?? shown(o), tone: "opt" },
        ...(diff ? [{ key: "diff", label: t("hv2.inspect.diff"), value: diff }] : []),
      ],
      events: (pointAt(h.cash.series, day)?.events ?? []).filter((e) => e.amount_fen !== 0).map((e) => ({ label: e.label_short ?? e.label, amount: e.amount_display })),
      note: t("hv2.deal.sameDay"),
    };
  };
  // The deal's picture has its own window and axis (it reaches the day the request is lowest); the company's reserve and horizon are the same.
  const pic = picture.data;
  const dealCash: HomeView["cash"] = pic ? { ...h.cash, picture_days: pic.picture_days ?? h.cash.picture_days, axis: pic.axis ?? h.cash.axis, axes: null, events_rail_days: 0 } : h.cash;
  const chartSubtitle = (late ? null : (serverTitle.data ?? h.home_v2?.chart.scenario_title_text)) ?? `${title} · ${asked?.label ?? ""} · ${recommended?.label ?? ""} · ${timingWord}`;

  const requestCost = asked && (asked.cost_forward_display || asked.cost_display) ? t("hv2.deal.request", { amount: asked.cost_forward_display ?? asked.cost_display, note: asked.cost_note }) : null;
  const recCost = recommended ? (recommended.cost_once_display ? t("dq.cost.once", { amount: recommended.cost_once_display, buyer }) : recommended.cost_total_display ? t("dq.cost.total", { amount: recommended.cost_total_display, basis: recommended.cost_basis_text ?? "", buyer }) : null) : null;
  const consequenceOpen = view.chart || view.timing === "late";
  // The card's three figures, every word the server's: what is outstanding with the buyer (the overview's own figure) and the asked path's early-payment and payment-terms words.
  // The server's `ask_facts` (invoice value, requested discount, requested term) when it sends them; until then the overview's outstanding figure and the asked path's own term words.
  const facts = asked?.ask_facts ?? null;
  const outstanding = v?.figures?.find((f) => f.key === "outstanding") ?? null;
  const askTerm = (key: string) => asked?.terms.find((x) => x.key === key) ?? null;
  const kpis = [
    facts?.invoice_value_display ? { key: "invoice", label: t("hv2.deal.invoice"), value: facts.invoice_value_display } : !facts && outstanding ? { key: "outstanding", label: outstanding.label, value: outstanding.value_display } : null,
    facts?.requested_discount_display ? { key: "discount", label: t("hv2.deal.discount"), value: facts.requested_discount_display } : !facts && askTerm("early_payment") ? { key: "early_payment", label: askTerm("early_payment")!.label, value: askTerm("early_payment")!.value_text } : null,
    facts?.requested_term_text ? { key: "term", label: t("hv2.deal.term"), value: facts.requested_term_text } : !facts && askTerm("payment_terms") ? { key: "payment_terms", label: askTerm("payment_terms")!.label, value: askTerm("payment_terms")!.value_text } : null,
  ].filter((k): k is { key: string; label: string; value: string } => k !== null);

  return (
    <div id="home-focus" data-testid="home-deal-focus" data-decision={decision} className="f-card f-card-white min-w-0 p-4">
      <Announce text={title} />
      <div key={decision} className="motion-swap">
        {gone ? (
          <div className="mt-4 space-y-2" data-testid="home-deal-gone">
            <p className="text-sm text-ink-2">{t("hv2.deal.gone")}</p>
            <Button onClick={onCustomer}>{v?.name ?? buyer}</Button>
          </div>
        ) : !v ? (
          <div className="mt-4 min-h-[22rem]" data-testid="hv2-deal-reserved">
            {overview.error ? <ErrorState error={t("hv2.focus.failed")} onRetry={overview.reload} /> : slow ? <LoadingBlock rows={3} label={t("hv2.focus.working")} /> : null}
          </div>
        ) : (
          <>
            {/* Level 1: the decision */}
            <div data-testid="hv2-level-decision">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 id="home-focus-title" tabIndex={-1} className="font-display text-[18px] font-bold leading-tight tracking-[-0.01em] text-ink" data-testid="focus-title">
                    {title}
                  </h2>
                  <p className="mt-1.5 text-[15px] text-ink-3" data-testid="hv2-customer-line">
                    {[v.name, customer?.detail_text].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <Dismiss onDismiss={onAll} />
              </div>
              {kpis.length ? (
                <dl className="mt-2 grid grid-cols-1 gap-y-2 border-y border-line py-2.5 sm:grid-cols-3 sm:gap-x-6" data-testid="hv2-deal-kpis">
                  {kpis.map((k) => (
                    <div key={k.key} className="min-w-0" data-testid={`hv2-deal-kpi-${k.key}`}>
                      <dt className="text-supporting text-ink-3">{k.label}</dt>
                      <dd className="mt-1 break-words font-display text-[24px] font-bold leading-tight tracking-[-0.02em] tabular-nums text-ink">{k.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              {asked?.ask_breakdown?.length ? <Breakdown rows={asked.ask_breakdown} total={facts?.invoice_value_display} testId="hv2-deal-breakdown" /> : null}
              {row && "why_first_text" in row && row.why_first_text ? (
                <p className="mt-2 border-l-2 border-line-strong pl-3 text-sm text-ink-2" data-testid="home-why-first">
                  {row.why_first_text}
                </p>
              ) : null}
              <p className="mt-2 max-w-[68ch] text-sm leading-snug text-ink" data-testid="deal-ask">
                {open ? t("dq.ask", { buyer, asks: open.asks_text }) : (decisionCard?.text ?? "")}
              </p>
              {recommended ? (
                <div className="mt-2 space-y-0.5" data-testid="hv2-recommendation">
                  <p className="text-supporting font-bold text-brand-700" data-testid="deal-recommends">
                    {t("hv2.deal.recommends", { label: recommended.label })}
                  </p>
                  {recommended.reply_text ? <p className="max-w-[68ch] text-sm text-ink">{recommended.reply_text}</p> : null}
                  {recCost ? (
                    <p className="text-sm font-bold text-ink" data-testid="queue-cost">
                      {recCost}
                    </p>
                  ) : null}
                  {requestCost ? (
                    <p className="text-sm text-ink-2" data-testid="deal-request-cost">
                      {requestCost}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {/* The one commit area: what waits, then [Review the counter] filled, the two quiet toggles and the way into Deals, in one row */}
              {decisionCard ? (
                <p className="mt-2 border-t border-line pt-2 text-sm text-ink" data-testid="hv2-deal-next">
                  <span data-testid="hv2-deal-next-line">{decisionCard.eyebrow}</span>
                </p>
              ) : null}
              <ActionGroup className="mt-2" testId="hv2-deal-actions" label={t("hv2.deal.actions")}>
                {decisionCard ? (
                  <ButtonLink href={decisionCard.primary.href} variant="primary" data-testid="deal-primary">
                    {decisionCard.primary.label}
                  </ButtonLink>
                ) : null}
                {paths.length > 1 ? (
                  <Button aria-expanded={view.compare} aria-controls={`${uid}-compare`} onClick={() => onView({ compare: !view.compare })} data-testid="hv2-compare-toggle">
                    {t("hv2.deal.compare")}
                    <svg aria-hidden viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={`transition-transform duration-(--dur) ${view.compare ? "rotate-180" : ""}`}>
                      <path d="m4 6 4 4 4-4" />
                    </svg>
                  </Button>
                ) : null}
                {lines.length ? (
                  <Button aria-expanded={view.chart} aria-controls={`${uid}-chart`} onClick={() => onView({ chart: !view.chart })} data-testid="hv2-chart-toggle">
                    {t("hv2.deal.cash")}
                    <svg aria-hidden viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={`transition-transform duration-(--dur) ${view.chart ? "rotate-180" : ""}`}>
                      <path d="m4 6 4 4 4-4" />
                    </svg>
                  </Button>
                ) : null}
                <LeaveLink href={`/deals?customer=${encodeURIComponent(customerId)}&decision=${encodeURIComponent(decision)}`} testId="deal-open" className="px-1">
                  {t("hv2.deal.open")}
                </LeaveLink>
              </ActionGroup>
            </div>

            {/* Level 2: the consequence, closed until the Cash impact toggle (or a timing assumption in the address) opens it */}
            {consequenceOpen ? (
            <OpenSection title={t("hv2.deal.consequence")} subtitle={t("hv2.deal.consequence.note")} testId="hv2-level-consequence" className="mt-6 sm:mt-6 pt-6 sm:pt-6">
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2" data-testid="hv2-assumption">
                <p className="text-sm font-bold text-ink-2">{t("hv2.deal.timing")}</p>
                {exposure.data?.stress.paths ? (
                  <SegmentedTabs
                    compact
                    label={t("hv2.deal.timing")}
                    value={late ? "late" : "expected"}
                    onChange={(x) => onView({ timing: x === "late" ? "late" : null })}
                    tabs={[
                      { value: "expected", label: t("home.hy.scenario.expected"), testId: "deal-scenario-current" },
                      { value: "late", label: t("home.hy.scenario.late", { buyer, n: lateDays }), testId: "deal-scenario-late" },
                    ]}
                  />
                ) : null}
              </div>
              <p className="mt-1 text-supporting text-ink-3">{t("hv2.deal.timing.note")}</p>
              <div className="mt-3" data-testid="deal-scenario-panel" data-scenario={late ? "late" : "current"} aria-busy={exposure.loading || picture.loading}>
                {pair.length ? (
                  <ComparisonTable testId="hv2-consequence" caption={t("hv2.deal.consequence")} columns={pairColumns} rows={pairRows} />
                ) : picture.data === undefined && !picture.error ? (
                  <LoadingBlock rows={2} label={t("hv2.focus.working")} />
                ) : (
                  <p className="text-sm text-ink-2" data-testid="deal-current-note">
                    {decisionCard?.text}
                  </p>
                )}
                {assumption ? (
                  <p className="mt-3 text-supporting text-ink-2" data-testid="deal-assumption">
                    {assumption}
                  </p>
                ) : null}
              </div>
            </OpenSection>
            ) : null}

            {/* Level 3: investigation, only on request */}
            {view.compare && paths.length > 1 ? (
              <OpenSection id={`${uid}-compare`} title={t("hv2.deal.responses")} testId="hv2-compare" className="mt-8">
                <ComparisonTable testId="hv2-compare-table" caption={t("hv2.deal.responses")} columns={fullColumns} rows={fullRows} />
                <div className="mt-6" data-testid="hv2-why">
                  <h3 className="font-display text-base font-extrabold text-ink">{t("hv2.deal.why", { label: recommended?.label ?? "" })}</h3>
                  <ul className="mt-2 divide-y divide-line">
                    {[...paths].reverse().map((p) => (
                      <li key={p.key} className="grid gap-x-3 gap-y-0.5 py-2 text-sm text-ink-2 sm:grid-cols-[7rem_minmax(0,1fr)]">
                        <b className="font-bold text-ink">{p.label}</b>
                        <span className="flex items-start gap-2">
                          <StateWord tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"} glyph>
                            {p.authority_reason_text ?? p.authority_text ?? p.decides_text}
                          </StateWord>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                <Disclosure summary={t("hv2.deal.impact")} testId="hv2-impact" className="mt-5 border-y border-line">
                  <div className="space-y-3 pb-1 text-sm text-ink-2">
                    {exposure.data?.band.concentration ? <p data-testid="hv2-impact-concentration">{exposure.data.band.concentration}</p> : null}
                    {paths.map((p) => {
                      const cap = exposure.data?.band.by_path[p.key]?.capacity;
                      return cap ? (
                        <p key={p.key} data-testid="hv2-impact-capacity">
                          <b className="font-bold text-ink">{p.label}.</b> {cap}
                        </p>
                      ) : null;
                    })}
                  </div>
                </Disclosure>
              </OpenSection>
            ) : null}
            {view.chart && lines.length ? (
              <div id={`${uid}-chart`} className="mt-8" data-testid="hv2-deal-chart">
                <CashPreview
                  cash={dealCash}
                  today={h.day}
                  title={t("hv2.chart.title")}
                  subtitle={chartSubtitle}
                  lines={lines}
                  floorLabel={t("biz.picture.reserve", { amount: h.cash.floor_short })}
                  selectable={chartDays}
                  initialDay={askedLow}
                  lowestDay={null}
                  words={chartWords}
                  testId="hv2-chart"
                  legend={
                    <>
                      {asked ? <LegendItem kind="request">{asked.label}</LegendItem> : null}
                      <LegendItem kind="below">{t("hv2.chart.below")}</LegendItem>
                      {recommended ? (
                        <LegendItem kind="option" quiet={recommended.assumption_text}>
                          {recommended.label}
                        </LegendItem>
                      ) : null}
                      <LegendItem kind="reserve">{t("biz.picture.reserve", { amount: h.cash.floor_short })}</LegendItem>
                    </>
                  }
                />
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
