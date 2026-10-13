"use client";

import { useEffect, useRef, useState } from "react";
import { XIcon } from "@/components/icons";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeTone, HomeView } from "@/lib/types";

const WINDOWS = [30, 60, 120] as const;
const H = 280;
const PAD = { top: 18, right: 16, bottom: 30, left: 56 };

/** One key indicator on the chart: a day the server named (the rail) or a day with flows on the books, with its words for the tooltip. */
interface Indicator {
  key: string;
  day: number;
  fen: number;
  when: string;
  title: string;
  amount: string | null;
  lines: string[];
  tone: HomeTone;
  planned: boolean;
  lowest: boolean;
}

function indicators(h: HomeView, last: number, onLine: HomeSeriesPoint[]): Indicator[] {
  const rail = (h.cash.events_rail ?? []).filter((e) => e.day <= last);
  const railDays = new Set(rail.map((e) => e.day));
  const at = new Map(onLine.map((p) => [p.day, p]));
  const out: Indicator[] = rail.map((e) => {
    const fen = (e as { cash_after_fen?: number }).cash_after_fen ?? at.get(e.day)?.closing_fen ?? 0;
    return {
      key: e.key,
      day: e.day,
      fen,
      when: e.when,
      title: e.label,
      amount: e.net_short ?? e.amount_short,
      lines: [e.note ?? null, e.basis_text ?? null, e.explain].filter((x): x is string => Boolean(x)),
      tone: e.tone ?? "neutral",
      planned: Boolean(e.planned),
      lowest: e.kind === "lowest",
    };
  });
  // Past the rail, the days with flows on the books are indicators too, so the full range keeps its landmarks.
  for (const p of h.cash.series) {
    if (p.day > last || p.day <= h.day || railDays.has(p.day) || !p.events?.length) continue;
    const ev = p.events as { label_short?: string; label: string; amount_short?: string; amount_display: string; basis_text?: string }[];
    out.push({
      key: `flow-${p.day}`,
      day: p.day,
      fen: at.get(p.day)?.closing_fen ?? p.closing_fen,
      when: p.when ?? "",
      title: ev.map((e) => e.label_short ?? e.label).join(" · "),
      amount: ev.length === 1 ? (ev[0].amount_short ?? ev[0].amount_display) : null,
      // One flow is the title and its amount; several are a line each. Then the day's closing cash.
      lines: [...(ev.length > 1 ? ev.map((e) => `${e.label_short ?? e.label}: ${e.amount_short ?? e.amount_display}`) : ev[0].basis_text ? [ev[0].basis_text] : []), p.display ?? p.closing_display],
      tone: "neutral",
      planned: false,
      lowest: false,
    });
  }
  return out.sort((a, b) => a.day - b.day);
}

const TONE_FILL: Record<HomeTone, string> = { ok: "var(--color-ok-solid)", warn: "var(--color-warn-solid)", bad: "var(--color-bad-solid)", neutral: "var(--color-chart-axis)" };

/**
 * The cash ahead over its full range: the books as they stand (solid), FLOW's plan or the comparison (dashed), the minimum reserve, and the key days as small
 * marks whose words open only while the pointer or the focus is on them. Every word and tick label is the server's; the fen only place the marks (INVARIANT 13).
 */
export function CashAhead({ h, onClose }: { h: HomeView; onClose: () => void }) {
  const { t } = useI18n();
  const c = h.cash;
  const [win, setWin] = useState<number>(60);
  const [hover, setHover] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(Math.round(e.contentRect.width), 280)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const last = h.day + win;
  const inWin = (s: HomeSeriesPoint[] | null | undefined) => (s ?? []).filter((p) => p.day >= h.day && p.day <= last);
  const base = inWin(c.series);
  const plan = c.plan_series ? inWin(c.plan_series) : [];
  const compare = !plan.length && c.counterfactual_series ? inWin(c.counterfactual_series) : [];
  const marks = indicators(h, last, plan.length ? plan : base);
  const axis = c.axes?.[String(win)] ?? c.axis ?? null;
  const all = [...base, ...plan, ...compare].map((p) => p.closing_fen);
  // The server's axis, widened only where a drawn line would leave it (the comparison line can fall below the picture's own range).
  const lo = Math.min(axis?.min_fen ?? 0, ...all, c.floor_fen);
  const hi = Math.max(axis?.max_fen ?? 0, ...all, c.floor_fen);
  const span = hi - lo || 1;
  const x = (day: number) => PAD.left + ((day - h.day) / win) * (width - PAD.left - PAD.right);
  const y = (fen: number) => PAD.top + (1 - (fen - lo) / span) * (H - PAD.top - PAD.bottom);
  const path = (pts: HomeSeriesPoint[]) => pts.map((p, i) => `${i ? "L" : "M"}${x(p.day).toFixed(1)},${y(p.closing_fen).toFixed(1)}`).join(" ");
  const floorY = y(c.floor_fen);
  const xTicks = [base[0], base[Math.floor((base.length - 1) / 2)], base[base.length - 1]].filter(Boolean);
  const shown = marks.find((m) => m.key === hover) ?? null;
  const baseLabel = !plan.length && c.plan_line_label ? c.plan_line_label : t("home.dash.ahead.current");

  return (
    <section className="motion-reveal rounded-[24px] bg-surface p-5 shadow-(--shadow-lift) sm:p-6 md:col-span-2" aria-labelledby="home-ahead-title" data-testid="home-cash-ahead">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="home-ahead-title" className="font-display text-lg font-extrabold tracking-[-0.01em] text-ink">
            {t("home.dash.ahead.title")}
          </h2>
          <p className="text-supporting text-ink-3">{t("home.dash.ahead.hint")}</p>
        </div>
        <div className="flex items-center gap-2">
          <SegmentedTabs compact label={t("home.dash.ahead.window")} value={win} onChange={setWin} tabs={WINDOWS.map((n) => ({ value: n, label: t("home.dash.ahead.days", { n }), testId: `home-ahead-window-${n}` }))} testId="home-ahead-window" />
          <button type="button" onClick={onClose} aria-label={t("home.dash.ahead.close")} className="motion-press grid size-8 place-items-center rounded-pill text-ink-3 hover:bg-subtle hover:text-ink" data-testid="home-ahead-close">
            <XIcon width={16} height={16} />
          </button>
        </div>
      </div>

      <div ref={box} className="relative mt-4" onPointerLeave={() => setHover(null)}>
        <svg width={width} height={H} className="block max-w-full" role="img" aria-label={t("home.dash.lowest.alt")}>
          {/* Below the minimum: a faint band, and the minimum itself as a dashed line named at its right end. */}
          <rect x={PAD.left} y={floorY} width={Math.max(width - PAD.left - PAD.right, 0)} height={Math.max(H - PAD.bottom - floorY, 0)} fill="var(--color-chart-danger)" opacity={0.6} />
          {(axis?.ticks ?? []).map((tk) => (
            <g key={tk.value_fen}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(tk.value_fen)} y2={y(tk.value_fen)} stroke="var(--color-chart-grid)" />
              <text x={PAD.left - 8} y={y(tk.value_fen)} dy="0.32em" textAnchor="end" className="fill-ink-3 text-supporting tabular-nums">
                {tk.label}
              </text>
            </g>
          ))}
          <line x1={PAD.left} x2={width - PAD.right} y1={floorY} y2={floorY} stroke="var(--color-chart-reserve)" strokeDasharray="4 4" />
          {xTicks.map((p, i) => (
            <text key={p.day} x={x(p.day)} y={H - 8} textAnchor={i === 0 ? "start" : i === xTicks.length - 1 ? "end" : "middle"} className="fill-ink-3 text-supporting">
              {p.when ?? ""}
            </text>
          ))}
          {compare.length ? <path d={path(compare)} fill="none" stroke="var(--color-chart-axis)" strokeOpacity={0.55} strokeWidth={1.5} strokeDasharray="5 5" /> : null}
          <path d={path(base)} fill="none" stroke="var(--color-chart-base)" strokeWidth={2.25} strokeLinejoin="round" />
          {plan.length ? <path d={path(plan)} fill="none" stroke="var(--color-chart-plan)" strokeWidth={2.25} strokeDasharray="6 4" strokeLinejoin="round" /> : null}
          <text x={width - PAD.right} y={floorY - 6} textAnchor="end" stroke="var(--color-surface)" strokeWidth={4} paintOrder="stroke" strokeLinejoin="round" className="fill-bad-fg text-supporting font-bold">
            {t("home.dash.minimum", { amount: c.floor_short })}
          </text>
          {marks.map((m) => {
            const on = hover === m.key;
            return (
              <g
                key={m.key}
                tabIndex={0}
                role="button"
                aria-label={`${m.when}: ${m.title}${m.amount ? `, ${m.amount}` : ""}`}
                onPointerEnter={() => setHover(m.key)}
                onFocus={() => setHover(m.key)}
                onBlur={() => setHover((k) => (k === m.key ? null : k))}
                className="cursor-pointer outline-none"
                data-testid="home-ahead-mark"
              >
                {/* A generous invisible target around a small mark. */}
                <circle cx={x(m.day)} cy={y(m.fen)} r={14} fill="transparent" />
                {on ? <line x1={x(m.day)} x2={x(m.day)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--color-chart-axis)" strokeOpacity={0.35} /> : null}
                <circle
                  cx={x(m.day)}
                  cy={y(m.fen)}
                  r={on ? 7 : m.lowest ? 6 : 4.5}
                  fill={m.planned ? "var(--color-surface)" : TONE_FILL[m.tone]}
                  stroke={m.planned ? "var(--color-chart-plan)" : "var(--color-surface)"}
                  strokeWidth={2}
                  className="motion-safe:transition-[r] motion-safe:duration-(--dur-fast)"
                />
              </g>
            );
          })}
        </svg>
        {shown ? <Tip m={shown} left={x(shown.day)} top={y(shown.fen)} width={width} /> : null}
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-supporting text-ink-2">
        <Key line="solid" colour="var(--color-chart-base)" label={baseLabel} />
        {plan.length ? <Key line="dashed" colour="var(--color-chart-plan)" label={c.plan_line_label ?? ""} /> : null}
        {compare.length && c.counterfactual_label ? <Key line="dashed" colour="var(--color-chart-axis)" label={c.counterfactual_label} /> : null}
        <Key line="dashed" colour="var(--color-chart-reserve)" label={t("home.dash.ahead.minimum")} />
      </ul>
    </section>
  );
}

function Key({ line, colour, label }: { line: "solid" | "dashed"; colour: string; label: string }) {
  return (
    <li className="flex items-center gap-2">
      <svg width="22" height="6" aria-hidden>
        <line x1="1" x2="21" y1="3" y2="3" stroke={colour} strokeWidth={2.25} strokeDasharray={line === "dashed" ? "5 3" : undefined} strokeLinecap="round" />
      </svg>
      <span className="first-letter:uppercase">{label}</span>
    </li>
  );
}

/** The words of one indicator, beside its mark: when, what and how much, then the server's sentence. */
function Tip({ m, left, top, width }: { m: Indicator; left: number; top: number; width: number }) {
  const w = 240;
  const l = Math.min(Math.max(left - w / 2, 0), Math.max(width - w, 0));
  const below = top < 110;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-10 rounded-tile bg-brand-900 px-3.5 py-3 text-on-deep shadow-(--shadow-pop)"
      style={{ left: l, width: w, ...(below ? { top: top + 16 } : { bottom: H - top + 16 }) }}
      data-testid="home-ahead-tip"
    >
      <p className="text-meta font-semibold text-on-deep-muted first-letter:uppercase">{m.when}</p>
      <p className="mt-0.5 flex items-baseline justify-between gap-3 text-sm font-bold">
        <span className="first-letter:uppercase">{m.title}</span>
        {m.amount ? <span className="shrink-0 tabular-nums">{m.amount}</span> : null}
      </p>
      {m.lines.map((line, i) => (
        <p key={i} className="mt-1 text-supporting text-on-deep-muted">
          {line}
        </p>
      ))}
    </div>
  );
}
