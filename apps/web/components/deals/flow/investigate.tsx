"use client";

import { useMemo } from "react";
import { CashPreview, LegendItem, type InspectorWords, type PreviewLine } from "@/components/home/v2/cash-preview";
import { Disclosure } from "@/components/business/kit";
import { BeforeTheyAsk } from "@/components/deals/before-they-ask";
import { Button, ErrorState, LoadingBlock } from "@/components/ui";
import { ComparisonTable, type CompareColumn, type CompareRow } from "@/components/ui/comparison-table";
import { OpenSection } from "@/components/ui/open-section";
import { StateWord } from "@/components/ui/state-word";
import { getEnvelope, getOfferCompare } from "@/lib/api";
import { STRATEGY_MVP } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import type { CompareRowView, CompareView, EnvelopePackageView, EnvelopeView, ExposurePathWords, ExposureStress, ExposureView, HomeSeriesPoint, HomeView, OfferPictureView, PicturePath } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { AUTH_TONE, Cell, NONE, toneOfDeal } from "./flow-parts";

/** The lowest cash of a path: from the expected payments (the exposure read's words, else the picture's) or from the late-payment test (the stress words). */
export function lowestOf(path: PicturePath, words: ExposurePathWords | undefined, stress: ExposureStress | null | undefined, late: boolean) {
  if (late) {
    if (!stress?.available) return { value: null, sub: null, note: stress?.unavailable_text ?? null, bad: false };
    return { value: stress.lowest_short ?? stress.lowest_display ?? null, sub: stress.lowest_when ?? null, note: stress.breach_days_text ?? stress.text ?? null, bad: (stress.breach_days ?? 0) > 0 };
  }
  return { value: words?.lowest_display ?? path.lowest_short ?? null, sub: words?.lowest_when ?? path.lowest_when ?? null, note: words?.lowest_when_text ?? path.band_text ?? null, bad: path.first_breach_when !== null };
}

/** The chart's frame from the picture: the reserve, the window and the axis the server drew it with (the chart needs no company read to draw one deal). */
export function chartCashOf(picture: OfferPictureView): HomeView["cash"] {
  return { floor_fen: picture.floor_fen, floor_short: picture.floor_short, picture_days: picture.picture_days ?? 0, horizon_days: picture.horizon_days, axis: picture.axis ?? null, axes: null, events_rail_days: 0 } as unknown as HomeView["cash"];
}

const pointAt = (points: HomeSeriesPoint[] | null | undefined, day: number): HomeSeriesPoint | undefined => {
  let best: HomeSeriesPoint | undefined;
  for (const p of points ?? []) {
    if (p.day > day) break;
    best = p;
  }
  return best;
};
const shown = (p: HomeSeriesPoint | undefined): string => p?.display ?? p?.closing_display ?? "";

/** The authority class of a package of the envelope, from the verifier's own outcome and tier (the server's enums; the words are the dictionary's). */
export function packageClass(p: Pick<EnvelopePackageView, "outcome" | "tier">): "flow_may" | "needs_owner" | "over_limit" {
  if (p.outcome === "ACCEPT" || p.tier === "TIER_1") return "flow_may";
  return p.outcome === "NEEDS_OWNER_APPROVAL" || p.tier === "TIER_2" ? "needs_owner" : "over_limit";
}

const SHOWN_FIRST = 3;

/**
 * What the owner can live with for this buyer, by who may act on it (FLOW may send it, you approve first, over a limit you signed): the envelope's packages in the server's
 * one-line words, the first three of each class and the rest behind "more". Read only when the investigation is open and only with the strategy flag; a server without the
 * route (or with the feature off) mounts nothing.
 */
function EnvelopePackages({ buyerId }: { buyerId: string }) {
  const { t, lang } = useI18n();
  const read = useAsync<EnvelopeView | null>(async () => (STRATEGY_MVP ? await getEnvelope(buyerId, lang, false) : null), [buyerId, lang]);
  const e = read.data;
  if (!STRATEGY_MVP) return null;
  if (read.error) return <ErrorState error={t("biz.strategy.envelope.error")} onRetry={read.reload} />;
  if (read.loading && !e) return <LoadingBlock rows={3} label={t("biz.strategy.envelope.loading")} />;
  if (!e || e.refused || !e.packages.length) return null;
  const classes = (["flow_may", "needs_owner", "over_limit"] as const).map((c) => ({ c, items: e.packages.filter((p) => packageClass(p) === c) })).filter((x) => x.items.length);
  return (
    <OpenSection title={t("deals.envelope.title")} subtitle={t("deals.envelope.sub", { buyer: e.buyer_name })} testId="deal-envelope-packages" id="deal-envelope-section">
      <div className="space-y-4">
        {classes.map(({ c, items }) => (
          <div key={c} data-testid={`envelope-class-${c}`}>
            <p className="mb-1 text-supporting font-bold text-ink-2">
              <StateWord tone={AUTH_TONE[c]}>{t(`deals.class.${c}` as const)}</StateWord>
            </p>
            <ul className="divide-y divide-line">
              {items.slice(0, SHOWN_FIRST).map((p, i) => (
                <PackageLine key={i} p={p} />
              ))}
            </ul>
            {items.length > SHOWN_FIRST ? (
              <Disclosure testId={`envelope-more-${c}`} summary={t("deals.envelope.more", { n: items.length - SHOWN_FIRST })}>
                <ul className="divide-y divide-line">
                  {items.slice(SHOWN_FIRST).map((p, i) => (
                    <PackageLine key={i} p={p} />
                  ))}
                </ul>
              </Disclosure>
            ) : null}
          </div>
        ))}
        {e.unlisted_counters.map((s, i) => (
          <p key={i} className="text-supporting text-ink-2">
            {s}
          </p>
        ))}
      </div>
    </OpenSection>
  );
}

function PackageLine({ p }: { p: EnvelopePackageView }) {
  return (
    <li className="py-2 text-sm text-ink" data-testid="envelope-package">
      {p.summary}
      {p.flags.length ? <span className="text-ink-2">{` · ${p.flags.join(", ")}`}</span> : null}
    </li>
  );
}

/**
 * Level 3, only on request (ticket #129, UX): the full table of every response (the request, each reply, doing nothing and, when the comparator carries it, the buyer stopping), each cost
 * with its basis words, the lowest cash labelled with what it assumes, the late-payment test, who decides and why; then room for another payment in words, the envelope, and the
 * deal's cash chart. Every figure and sentence is the server's; the table compares nothing itself, and a comparison never binds the commit (the pick only chooses which reply
 * the review above is about).
 */
export function Investigate({
  offerId,
  buyer,
  buyerId,
  picture,
  exposure,
  late,
  pickedKey,
  onPick,
  compareOpen,
  chartOpen,
}: {
  offerId: string;
  buyer: string;
  buyerId: string;
  picture: OfferPictureView;
  exposure: ExposureView | null | undefined;
  late: boolean;
  pickedKey: string | null;
  onPick: (key: string) => void;
  /** The full table of every response is open (`compare=1`), and the deal's cash chart (`chart=1`): each is asked for by its own button. */
  compareOpen: boolean;
  chartOpen: boolean;
}) {
  const { t, lang } = useI18n();
  // The comparator is the heavier read: asked for only while the full table is open.
  const compare = useAsync<CompareView | null>(() => (compareOpen ? getOfferCompare(offerId, lang).catch(() => null) : Promise.resolve(null)), [offerId, lang, compareOpen]);
  const cmp = compare.data && compare.data.offer_id === offerId ? compare.data : null;
  const paths = useMemo(() => (picture.paths ?? []).filter((p) => p.kind === "asked" || p.kind === "reply"), [picture.paths]);
  const wordsOf = (key: string) => exposure?.paths.find((x) => x.key === key);
  const stressOf = (key: string) => exposure?.stress.paths[key] ?? null;
  const nothing = exposure?.paths.find((x) => x.kind === "do_nothing") ?? null;
  const rowOf = (kind: string, key?: string): CompareRowView | undefined => cmp?.rows.find((r) => (key ? r.key === key : r.kind === kind) && r.available);
  const loss = cmp?.rows.find((r) => r.kind === "customer_loss" && r.available) ?? null;
  const delay = exposure?.stress.delay_days ?? 0;

  const term = (p: PicturePath, key: string) => p.terms.find((x) => x.key === key);
  const termCell = (p: PicturePath, key: string) => {
    const x = term(p, key);
    return x && (x.value_text || x.instead_of_text) ? <Cell key={`${p.key}-${key}`} value={x.value_text} sub={x.instead_of_text} /> : <span key={`${p.key}-${key}`}>{NONE}</span>;
  };

  const columns: CompareColumn[] = [
    ...paths.map((p) => ({
      key: p.key,
      head: p.label,
      tag: <StateWord tone={toneOfDeal(p.tag_tone)}>{p.tag_text}</StateWord>,
      evidence: p.recommended ? p.recommended_reason_text : p.authority_reason_text,
      recommended: p.recommended,
    })),
    ...(nothing ? [{ key: "do_nothing", head: nothing.label }] : []),
    ...(loss ? [{ key: "customer_loss", head: loss.label }] : []),
  ];
  const extra = <T,>(path: (p: PicturePath) => T, doNothing: T, lossCell: T): T[] => [...paths.map(path), ...(nothing ? [doNothing] : []), ...(loss ? [lossCell] : [])];
  const cost = (p: PicturePath) => {
    const parts = p.cost_components ?? [];
    const headline = p.cost_forward_display && p.cost_once_display ? p.cost_forward_display : (p.cost_total_display ?? p.cost_display);
    const basis = p.cost_forward_display && p.cost_once_display ? p.cost_note : (p.cost_basis_text ?? p.cost_note);
    return (
      <span key={p.key}>
        <Cell value={headline} bad={p.authority === "over_limit"} sub={basis} />
        {p.cost_forward_display && p.cost_once_display ? <Cell value={p.cost_once_display} sub={t("deals.cost.onceNow")} /> : null}
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
  const lowest = (p: PicturePath) => {
    const l = lowestOf(p, wordsOf(p.key), stressOf(p.key), late);
    const assumes = late ? null : (wordsOf(p.key)?.scenario_assumption_text ?? p.scenario_assumption_text);
    return (
      <span key={p.key}>
        <Cell value={l.value} sub={l.sub} note={l.note} bad={l.bad} />
        {assumes ? <span className="mt-1 block text-supporting text-ink-3">{assumes}</span> : null}
      </span>
    );
  };
  const limit = (p: PicturePath) => {
    const w = wordsOf(p.key);
    if (!w?.limit_text) return <span key={p.key}>{NONE}</span>;
    return (
      <StateWord key={p.key} tone={w.limit_word === "EXCEEDED" ? "bad" : "ok"}>
        <span className="first-letter:uppercase">{w.limit_text}</span>
      </StateWord>
    );
  };
  const nothingRow = rowOf("current");
  const rows: CompareRow[] = [
    { key: "terms", label: t("hv2.deal.terms"), cells: extra((p) => termCell(p, "payment_terms"), NONE, NONE) },
    {
      key: "change",
      label: t("hv2.deal.change"),
      cells: extra(
        (p) => (
          <span key={p.key}>
            {termCell(p, "early_payment")}
            <span className="mt-2 block">{termCell(p, "rebate_or_price")}</span>
          </span>
        ),
        NONE,
        NONE,
      ),
    },
    {
      key: "economics",
      label: t("hv2.deal.economics"),
      cells: extra(cost, nothingRow?.funding_text ? <Cell sub={nothingRow.funding_text} /> : NONE, loss?.loss ? <Cell note={loss.loss.loss_text} sub={loss.loss.costs_text} /> : NONE),
    },
    {
      key: "lowest",
      label: t("hv2.deal.lowest"),
      cells: extra(
        lowest,
        nothing ? (
          <Cell value={nothing.lowest_display} sub={nothing.lowest_when} note={nothing.lowest_when_text} bad={nothingRow ? (nothingRow.breach_days ?? 0) > 0 : false} />
        ) : (
          NONE
        ),
        loss ? <Cell value={loss.lowest_cash_display} sub={loss.lowest_when} note={loss.loss?.receipts_text ?? loss.first_breach_when} /> : NONE,
      ),
    },
    {
      key: "stress",
      label: t("deals.row.stress", { buyer, n: delay }),
      cells: extra(
        (p) => {
          const l = lowestOf(p, wordsOf(p.key), stressOf(p.key), true);
          return l.value || l.note ? <Cell key={p.key} value={l.value} sub={l.sub} note={l.note} bad={l.bad} /> : <span key={p.key}>{NONE}</span>;
        },
        NONE,
        NONE,
      ),
    },
    { key: "limits", label: t("hv2.deal.limits"), cells: extra(limit, NONE, NONE) },
    {
      key: "approval",
      label: t("hv2.deal.approval"),
      cells: extra(
        (p) => (
          <StateWord key={p.key} tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"}>
            {p.authority_text ?? p.decides_text}
          </StateWord>
        ),
        NONE,
        NONE,
      ),
    },
    {
      key: "use",
      label: t("deals.row.use"),
      cells: extra(
        (p) =>
          p.kind === "reply" && p.sendable ? (
            <Button key={p.key} size="sm" variant="secondary" aria-pressed={pickedKey === p.key} onClick={() => onPick(p.key)} data-testid={`deal-use-${p.key}`}>
              {pickedKey === p.key ? t("deals.use.picked", { label: p.label }) : t("deals.use", { label: p.label })}
            </Button>
          ) : (
            <span key={p.key}>{NONE}</span>
          ),
        NONE,
        NONE,
      ),
    },
  ].filter((r) => (r.key === "stress" ? Boolean(exposure) : true));

  // ---- the deal's cash chart: the recommended reply solid, the request grey with its stretches under the reserve in red
  const asked = paths.find((p) => p.kind === "asked") ?? null;
  const focus = paths.find((p) => p.key === pickedKey) ?? paths.find((p) => p.kind === "reply" && p.recommended) ?? null;
  const seriesOf = (p: PicturePath | null): HomeSeriesPoint[] => {
    if (!p) return [];
    const s = late ? stressOf(p.key) : null;
    if (late && s?.series?.length) return s.series.map((x) => ({ ...x, events: [] }));
    return p.series ?? [];
  };
  const lines: PreviewLine[] = [];
  if (asked) lines.push({ key: asked.key, label: asked.label, style: "request", points: seriesOf(asked) });
  if (focus) lines.push({ key: focus.key, label: focus.label, style: "option", points: seriesOf(focus) });
  const today = picture.day;
  const lowestDayOf = (pts: HomeSeriesPoint[]) => pts.filter((p) => p.day >= today).reduce<HomeSeriesPoint | null>((a, b) => (a === null || b.closing_fen < a.closing_fen ? b : a), null)?.day ?? today;
  const askedLow = lowestDayOf(seriesOf(asked));
  const moments = picture.moments ?? [];
  const chartDays = [...new Set([...moments.map((m) => m.day), askedLow, lowestDayOf(seriesOf(focus))])].sort((a, b) => a - b);
  const chartWords = (day: number): InspectorWords => {
    const whenWord = pointAt(seriesOf(asked), day)?.when ?? moments.find((m) => m.day === day)?.word ?? moments.find((m) => m.day === day)?.label ?? "";
    const a = pointAt(seriesOf(asked), day);
    const o = pointAt(seriesOf(focus), day);
    const cmp2 = pointAt(late ? [] : (focus?.series ?? []), day)?.comparison ?? null;
    const diff = cmp2?.difference_display ?? moments.find((m) => m.day === day)?.values.find((x) => x.key === focus?.key)?.vs_asked_short;
    return {
      cells: [
        { key: "when", label: t("hv2.chart.when"), value: whenWord },
        { key: "request", label: asked?.label ?? "", value: cmp2?.asked_display ?? shown(a), tone: a && a.closing_fen < picture.floor_fen ? "bad" : undefined },
        { key: "option", label: focus?.label ?? "", value: cmp2?.recommended_display ?? shown(o), tone: "opt" },
        ...(diff ? [{ key: "diff", label: t("hv2.inspect.diff"), value: diff }] : []),
      ],
      events: (pointAt(focus?.series ?? [], day)?.events ?? []).filter((e) => e.amount_fen !== 0).map((e) => ({ label: e.label_short ?? e.label, amount: e.amount_display })),
      note: t("hv2.deal.sameDay"),
    };
  };
  const caps = paths.map((p) => ({ p, cap: exposure?.band.by_path[p.key]?.capacity ?? null })).filter((x) => x.cap);

  return (
    <div data-testid="deal-level-investigate" className="space-y-0">
      {compareOpen ? (
        <>
      <OpenSection id="deal-compare" title={t("hv2.deal.responses")} subtitle={t("deals.compare.note")} testId="deal-compare" className="mt-8">
        <ComparisonTable testId="deal-compare-table" caption={t("hv2.deal.responses")} columns={columns} rows={rows} />
        {compare.loading && !cmp ? (
          <p className="mt-2 text-supporting text-ink-3" role="status">
            {t("deals.compare.loading")}
          </p>
        ) : null}
        {loss?.assumption_text ? <p className="mt-3 text-supporting text-ink-2">{loss.assumption_text}</p> : null}
        {cmp?.note ? <p className="mt-1 text-supporting text-ink-3">{cmp.note}</p> : null}
        {exposure?.band.concentration || caps.length ? (
          <Disclosure summary={t("hv2.deal.impact")} testId="deal-impact" className="mt-5 border-y border-line">
            <div className="space-y-3 pb-1 text-sm text-ink-2">
              {exposure?.band.concentration ? <p data-testid="deal-impact-concentration">{exposure.band.concentration}</p> : null}
              {caps.map(({ p, cap }) => (
                <p key={p.key} data-testid="deal-impact-capacity">
                  <b className="font-bold text-ink">{p.label}.</b> {cap}
                </p>
              ))}
            </div>
          </Disclosure>
        ) : null}
      </OpenSection>
      {/* What the owner can live with for this buyer (the strategy build): the ceilings and the levers behind a fold, then the packages by who may send them. */}
      {STRATEGY_MVP ? (
        <div className="mt-8" data-testid="deal-before-they-ask">
          <BeforeTheyAsk buyerId={buyerId} />
        </div>
      ) : null}
      <EnvelopePackages buyerId={buyerId} />
        </>
      ) : null}
      {chartOpen && lines.length ? (
        <div id="deal-chart" className="mt-8" data-testid="deal-chart">
          <CashPreview
            cash={chartCashOf(picture)}
            today={today}
            title={t("deals.chart.title")}
            subtitle={`${asked?.label ?? ""} · ${focus?.label ?? ""} · ${late ? t("home.hy.scenario.late", { buyer, n: delay }) : t("home.hy.scenario.expected")}`}
            lines={lines}
            floorLabel={t("biz.picture.reserve", { amount: picture.floor_short })}
            selectable={chartDays}
            initialDay={askedLow}
            lowestDay={null}
            words={chartWords}
            testId="deal-chart-picture"
            legend={
              <>
                {asked ? <LegendItem kind="request">{asked.label}</LegendItem> : null}
                <LegendItem kind="below">{t("hv2.chart.below")}</LegendItem>
                {focus ? (
                  <LegendItem kind="option" quiet={focus.assumption_text}>
                    {focus.label}
                  </LegendItem>
                ) : null}
                <LegendItem kind="reserve">{t("biz.picture.reserve", { amount: picture.floor_short })}</LegendItem>
              </>
            }
          />
        </div>
      ) : null}
    </div>
  );
}
