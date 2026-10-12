"use client";

import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { initials, toneFor, type AvatarTone } from "@/components/business/kit";
import { CustomerName } from "@/components/customer-link";
import { useI18n } from "@/lib/i18n";
import type { OutstandingReceivable, PromisedReceipt } from "@/lib/types";
import { daysLate, whenText } from "@/lib/when";

/**
 * "Who pays when": every open invoice as a mark on a time axis at its due day (late ones left of the "Today" line), its size in three steps by
 * the invoice face amount, its state said by fill and outline as well as by hue (late is filled, due soon and later are outlined, a promised early
 * payment is a diamond), each labelled with the server amount, the day in `biz.when.*` words and the buyer avatar. Pressing a mark hands the
 * invoice id to the page, which scrolls to and highlights its row; a visually hidden table says the same in text. Plain inline SVG, drawn in pixels
 * from the measured width, faded in once. Marks that would overlap stack vertically; a label that would touch another mark or label is dropped
 * (the row has it). The `*_fen` and day numbers only place and size a mark; every figure and word is the server's, or `biz.when.*`.
 */
const FONT = 12;
const AV = 11; // the avatar disc radius
const LANE = 40;
const PAD = { l: 20, r: 20, t: 34, b: 40 } as const;

type State = "late" | "soon" | "later" | "promised";
interface Mark {
  id: string;
  rowId: string;
  kind: "invoice" | "promise";
  day: number;
  state: State;
  r: number;
  buyer: string;
  /** The buyer's id, so the name in the table is the link to their overview. */
  buyerId: string | null;
  amount: string;
  when: string;
  late: string | null;
  x: number;
  lane: number;
}

const HUE: Record<AvatarTone, { bg: string; fg: string }> = {
  neutral: { bg: "fill-subtle", fg: "fill-ink-2" },
  ok: { bg: "fill-ok-bg", fg: "fill-ok-fg" },
  warn: { bg: "fill-warn-bg", fg: "fill-warn-fg" },
  bad: { bg: "fill-bad-bg", fg: "fill-bad-fg" },
  home: { bg: "fill-sec-home-bg", fg: "fill-sec-home-fg" },
  deals: { bg: "fill-sec-deals-bg", fg: "fill-sec-deals-fg" },
  cash: { bg: "fill-sec-cash-bg", fg: "fill-sec-cash-fg" },
  activity: { bg: "fill-sec-activity-bg", fg: "fill-sec-activity-fg" },
};

function textWidth(text: string, bold: boolean): number {
  let w = 0;
  for (const ch of text) w += /[⺀-鿿＀-￯]/.test(ch) ? FONT : FONT * (bold ? 0.62 : 0.57);
  return w;
}

interface Box {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}
const hit = (a: Box, b: Box) => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0;

export function WhoPaysWhen({
  invoices,
  promised,
  asOfDay,
  buyerName,
  isLate,
  dueSoonDays,
  selected,
  onSelect,
}: {
  invoices: OutstandingReceivable[];
  promised: PromisedReceipt[] | undefined;
  asOfDay: number;
  buyerName: (id: string | null) => string;
  isLate: (o: OutstandingReceivable) => boolean;
  dueSoonDays: number;
  selected: string | null;
  onSelect: (rowId: string) => void;
}) {
  const { t } = useI18n();
  const frame = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(0);
  const [intro, setIntro] = useState(true);
  useLayoutEffect(() => {
    const el = frame.current;
    if (!el) return;
    const read = () => setW(Math.floor(el.clientWidth));
    read();
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const id = window.setTimeout(() => setIntro(false), 1200);
    return () => window.clearTimeout(id);
  }, []);

  const awaited = (promised ?? []).filter((p) => p.status === "AWAITED" && p.promised_day !== null);
  if (!invoices.length) return null;

  // ---- the window and the scale: from the earliest to the latest day shown, today always inside
  const days = [asOfDay, ...invoices.map((o) => o.due_day), ...awaited.map((p) => p.promised_day as number)];
  const span0 = Math.max(Math.max(...days) - Math.min(...days), 10);
  const pad = Math.max(span0 * 0.06, 2);
  const lo = Math.min(...days) - pad;
  const hi = Math.max(...days) + pad;
  // Room to the left of the earliest late mark for its label (late marks sit left of the Today line, which a label may not cross).
  const room = invoices.some(isLate) ? Math.min(230, W * 0.36) : 0;
  const pl = PAD.l + room;
  const pr = Math.max(W - PAD.r, pl + 1);
  const xOf = (d: number) => Math.round((pl + ((d - lo) / (hi - lo)) * (pr - pl)) * 10) / 10;
  const todayX = xOf(asOfDay);

  // ---- the marks: three sizes by face amount, stacked into lanes where they would overlap
  const faces = invoices.map((o) => o.face_fen).concat(awaited.map((p) => p.face_fen));
  const biggest = Math.max(...faces);
  const radius = (f: number) => (f >= (biggest * 2) / 3 ? 11 : f >= biggest / 3 ? 8 : 5.5);
  const marks: Mark[] = [
    ...invoices.map<Mark>((o) => {
      const late = isLate(o);
      const soon = !late && o.due_day - asOfDay <= dueSoonDays;
      return {
        id: o.receivable_id,
        rowId: o.receivable_id,
        kind: "invoice",
        day: o.due_day,
        state: late ? "late" : soon ? "soon" : "later",
        r: radius(o.face_fen),
        buyer: buyerName(o.counterparty_id),
        buyerId: o.counterparty_id,
        amount: o.face_display,
        when: whenText(o.due_day, asOfDay, t),
        late: late ? daysLate(Math.max(0, asOfDay - o.due_day), t) : null,
        x: xOf(o.due_day),
        lane: 0,
      };
    }),
    ...awaited.map<Mark>((p) => ({
      id: `promise:${p.commitment_id}:${p.obligation_id}:${p.receivable_id}`,
      rowId: `promised-${p.receivable_id}`,
      kind: "promise",
      day: p.promised_day as number,
      state: "promised",
      r: radius(p.face_fen),
      buyer: buyerName(p.counterparty_id),
      buyerId: p.counterparty_id,
      amount: p.expected_display,
      when: whenText(p.promised_day, asOfDay, t),
      late: null,
      x: xOf(p.promised_day as number),
      lane: 0,
    })),
  ].sort((a, b) => a.x - b.x || a.r - b.r);
  const laneEnd: number[] = [];
  for (const m of marks) {
    let k = laneEnd.findIndex((end) => m.x - m.r > end + 5);
    if (k < 0) k = laneEnd.length;
    laneEnd[k] = m.x + m.r;
    m.lane = k;
  }
  const lanes = Math.max(laneEnd.length, 1);
  const H = PAD.t + lanes * LANE + PAD.b - 8;
  const axisY = H - PAD.b;
  const yOfLane = (k: number) => axisY - 24 - k * LANE;

  // ---- labels: to the right of the mark, else to its left; one that touches a mark, another label or the Today line is dropped
  const own = new Map<string, Box>();
  const obstacles: Box[] = [{ x0: todayX - 2, x1: todayX + 2, y0: 0, y1: axisY }];
  for (const m of marks) {
    const y = yOfLane(m.lane);
    const b = { x0: m.x - m.r - 2, x1: m.x + m.r + 2, y0: y - m.r - 2, y1: y + m.r + 2 };
    own.set(m.id, b);
    obstacles.push(b);
  }
  const labels = new Map<string, { x: number }>();
  for (const m of [...marks].sort((a, b) => b.r - a.r || a.x - b.x)) {
    const text = `${m.amount} · ${m.when}`;
    const w = AV * 2 + 6 + textWidth(text, true);
    const y = yOfLane(m.lane);
    for (const x0 of [m.x + m.r + 6, m.x - m.r - 6 - w]) {
      const box = { x0, x1: x0 + w, y0: y - AV - 1, y1: y + AV + 1 };
      if (box.x0 < 0 || box.x1 > W) continue;
      if (obstacles.some((o) => o !== own.get(m.id) && hit(box, o))) continue;
      labels.set(m.id, { x: x0 });
      obstacles.push(box);
      break;
    }
  }

  // ---- ticks: today, then a distance every 5, 10, 20, 30 or 60 days on both sides, at least 80 px apart
  const stepDays = [5, 10, 20, 30, 60].find((s) => (s / (hi - lo)) * (pr - pl) >= 80) ?? 60;
  const ticks = new Set<number>([asOfDay]);
  for (let d = asOfDay + stepDays; d <= hi; d += stepDays) ticks.add(d);
  for (let d = asOfDay - stepDays; d >= lo; d -= stepDays) ticks.add(d);

  const key = (e: KeyboardEvent, id: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(id);
    }
  };
  const fade = intro ? "picture-fade" : "";
  const stateWord = (m: Mark) => (m.state === "late" ? (m.late ?? t("biz.recv.pic.late")) : m.state === "soon" ? t("biz.recv.pic.soon") : m.state === "promised" ? t("biz.recv.pic.promised") : t("biz.recv.pic.later"));
  const markClass = (s: State) => (s === "late" ? "fill-bad-solid stroke-bad-solid" : s === "soon" ? "fill-surface stroke-warn-solid" : "fill-surface stroke-ink-3");

  return (
    <section aria-labelledby="recv-pic-title" className="space-y-2.5" data-testid="recv-picture">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h2 id="recv-pic-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
          {t("biz.recv.pic.title")}
        </h2>
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2" data-testid="recv-picture-legend">
          {(["late", "soon", "later", "promised"] as const).map((s) => (
            <li key={s} className="flex items-center gap-1.5">
              <svg width="16" height="16" viewBox="-8 -8 16 16" aria-hidden>
                {s === "promised" ? <polygon points="0,-6 6,0 0,6 -6,0" className="fill-surface stroke-info-solid" strokeWidth={2} /> : <circle r={5.5} className={markClass(s)} strokeWidth={2} />}
              </svg>
              {s === "late" ? t("biz.recv.pic.late") : s === "soon" ? t("biz.recv.pic.soon") : s === "later" ? t("biz.recv.pic.later") : t("biz.recv.pic.promised")}
            </li>
          ))}
        </ul>
      </div>
      <div ref={frame} className="w-full" style={{ minHeight: H }}>
        {W > 0 ? (
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="group" aria-label={t("biz.recv.pic.axis")} className="block max-w-full select-none overflow-visible tabular-nums" fontSize={FONT} data-testid="recv-picture-svg">
            <rect x={PAD.l} y={PAD.t - 10} width={Math.max(todayX - PAD.l, 0)} height={axisY - PAD.t + 10} className="fill-bad-bg" opacity={0.45} />
            <line x1={PAD.l} x2={pr} y1={axisY} y2={axisY} className="stroke-line-strong" strokeWidth={1.5} />
            <line x1={todayX} x2={todayX} y1={PAD.t - 12} y2={axisY} className="stroke-ink" strokeWidth={1.5} data-testid="recv-today-line" />
            <text x={todayX} y={PAD.t - 18} textAnchor="middle" className="fill-ink" fontWeight={700}>
              {t("biz.picture.today")}
            </text>
            {[...ticks]
              .filter((d) => d !== asOfDay)
              .map((d) => (
                <text key={d} x={xOf(d)} y={axisY + 20} textAnchor="middle" className="fill-ink-3">
                  {whenText(d, asOfDay, t)}
                </text>
              ))}
            <g className={fade}>
              {marks.map((m) => {
                const y = yOfLane(m.lane);
                const on = selected === m.rowId;
                const label = labels.get(m.id);
                const hue = HUE[toneFor(m.buyer)];
                const name = `${m.buyer}, ${m.amount}, ${t("biz.due")} ${m.when}, ${stateWord(m)}`;
                return (
                  <g
                    key={m.id}
                    role="button"
                    tabIndex={0}
                    aria-label={name}
                    aria-controls={m.rowId}
                    aria-pressed={on}
                    onClick={() => onSelect(m.rowId)}
                    onKeyDown={(e) => key(e, m.rowId)}
                    className="cursor-pointer"
                    data-testid={`recv-mark-${m.id}`}
                    data-state={m.state}
                    data-day={m.day}
                  >
                    <circle cx={m.x} cy={y} r={Math.max(m.r + 10, 22)} className="fill-transparent" />
                    {on ? <circle cx={m.x} cy={y} r={m.r + 5} className="fill-brand-600/12 stroke-brand-600" strokeWidth={2} /> : null}
                    {m.state === "promised" ? (
                      <polygon points={`${m.x},${y - m.r - 1} ${m.x + m.r + 1},${y} ${m.x},${y + m.r + 1} ${m.x - m.r - 1},${y}`} className="fill-surface stroke-info-solid" strokeWidth={2.5} />
                    ) : (
                      <circle cx={m.x} cy={y} r={m.r} strokeWidth={2.5} className={markClass(m.state)} />
                    )}
                    {label ? (
                      <g data-testid={`recv-mark-label-${m.id}`}>
                        <circle cx={label.x + AV} cy={y} r={AV} className={hue.bg} />
                        <text x={label.x + AV} y={y + 4} textAnchor="middle" className={hue.fg} fontWeight={700}>
                          {initials(m.buyer)}
                        </text>
                        <text x={label.x + AV * 2 + 6} y={y + 4} className="fill-ink stroke-canvas" fontWeight={700} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">
                          {m.amount} {"·"} {m.when}
                        </text>
                      </g>
                    ) : null}
                  </g>
                );
              })}
            </g>
          </svg>
        ) : null}
      </div>
      <div className="sr-only">
        <table data-testid="recv-picture-table">
          <caption>{t("biz.recv.pic.table")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("biz.buyer")}</th>
              <th scope="col">{t("biz.amount")}</th>
              <th scope="col">{t("biz.due")}</th>
              <th scope="col">{t("common.status")}</th>
            </tr>
          </thead>
          <tbody>
            {[...marks]
              .sort((a, b) => a.day - b.day)
              .map((m) => (
                <tr key={m.id}>
                  <th scope="row">
                    <CustomerName id={m.buyerId}>{m.buyer}</CustomerName>
                  </th>
                  <td>{m.amount}</td>
                  <td>{m.when}</td>
                  <td>{stateWord(m)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
