"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRightIcon, ChevronRightIcon } from "@/components/icons";
import { BUYER_HUE, fundingMix, lenderHue, OWN_HUE, type FundingSlice } from "@/lib/funding-mix";
import { useI18n } from "@/lib/i18n";
import type { HomeView } from "@/lib/types";

const SIZE = 112;
const STROKE = 14;
const R = (SIZE - STROKE) / 2;
const C = 2 * Math.PI * R;

const hueOf = (h: HomeView, s: FundingSlice) => (s.kind === "own" ? OWN_HUE : s.kind === "buyer" ? BUYER_HUE : lenderHue(h, s.facilityId));
/** Still to arrive (a plan's leg not run, a customer's early payment): a lighter slice and a ring for a swatch. */
const arriving = (s: FundingSlice) => s.kind === "planned" || s.kind === "buyer";

/** One fact of a source: the label on the left, the server's figure or words on the right. Nothing is drawn without a value. */
function Fact({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <dt className="text-supporting text-ink-3">{label}</dt>
      <dd className="text-right text-supporting font-semibold text-ink tabular-nums first-letter:uppercase">{value}</dd>
    </div>
  );
}

/**
 * What there is to know about one source (the ui-ux-testing ring's details): own money against the minimum; a customer's early payment, when it arrives and what it rests
 * on; a lender's limit, what is in use, what is left and how fast its money lands (and a planned leg's amount, arrival and cost). Every value is the server's.
 */
function Details({ h, s }: { h: HomeView; s: FundingSlice }) {
  const { t } = useI18n();
  if (s.kind === "own") {
    const c = h.cash;
    return (
      <div data-testid="home-mix-details" data-kind="own">
        <p className="text-supporting text-ink-2">{t("home.mix.d.ownBody")}</p>
        <dl className="mt-1 divide-y divide-line">
          <Fact label={t("home.mix.d.cashToday")} value={c.cash_display} />
          <Fact label={t("home.mix.d.minimum")} value={c.floor_display} />
          <Fact label={t("home.mix.d.above")} value={(c.headroom_fen ?? 0) >= 0 ? c.headroom_short : null} />
        </dl>
      </div>
    );
  }
  if (s.kind === "buyer") {
    return (
      <div data-testid="home-mix-details" data-kind="buyer">
        <p className="text-supporting text-ink-2">{t("home.mix.buyerBody")}</p>
        <dl className="mt-1 divide-y divide-line">
          <Fact label={t("home.mix.d.plan")} value={s.amount} />
          <Fact label={t("home.mix.d.arrives")} value={s.when} />
          <Fact label={t("home.mix.d.basis")} value={s.note} />
        </dl>
      </div>
    );
  }
  const f = h.facilities.find((x) => x.id === s.facilityId) ?? null;
  return (
    <div data-testid="home-mix-details" data-kind={s.kind}>
      <dl className="divide-y divide-line">
        {s.kind === "planned" ? (
          <>
            <Fact label={t("home.mix.d.plan")} value={s.amount} />
            <Fact label={t("home.mix.d.arrives")} value={s.when} />
            <Fact label={t("home.mix.d.cost")} value={s.cost} />
          </>
        ) : null}
        {f ? (
          <>
            <Fact label={t("home.mix.d.limit")} value={f.limit_display} />
            <Fact label={t("home.mix.d.inUse")} value={f.drawn_display} />
            <Fact label={t("home.mix.d.available")} value={f.available_display} />
            <Fact label={t("home.mix.d.lands")} value={f.lead_time_days > 0 ? t("home.mix.d.leadDays", { n: f.lead_time_days }) : t("home.mix.d.sameDay")} />
          </>
        ) : null}
      </dl>
    </div>
  );
}

/**
 * Where the cash comes from, inside "Cash available today": a ring of the owner's own money against each lender's money and a customer's agreed early payment (what is
 * still to arrive as a lighter slice), the source in the middle, and a legend. A slice or its row opens that source: the slice stands out, the middle names it and its
 * details open under the legend (the ui-ux-testing ring's behaviour). The fen only size the arcs (lib/funding-mix.ts); no percentage is printed (INVARIANT 13).
 */
export function CashMix({ h, customers, bare = false }: { h: HomeView; customers?: { name: string; short: string }[]; /** On its own (the summary at the top of Cash & funding): no rule above it. */ bare?: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState<string | null>(null);
  const mix = fundingMix(h, customers);
  if (!mix) return null;
  const total = mix.slices.reduce((s, x) => s + x.fen, 0);
  const gap = mix.slices.length > 1 ? 3 : 0;
  const lens = mix.slices.map((s) => (s.fen / total) * C);
  const starts = lens.map((_, i) => lens.slice(0, i).reduce((a, b) => a + b, 0));
  const chosen = mix.slices.find((s) => s.key === open) ?? null;
  const centre = chosen ?? mix.slices.find((s) => s.kind === "own") ?? mix.slices[0];
  const nameOf = (s: FundingSlice) => (s.kind === "own" ? t("home.mix.own") : (s.name ?? ""));
  const toggle = (key: string) => setOpen((k) => (k === key ? null : key));
  return (
    <div className={bare ? "" : "mt-4 border-t border-line pt-4 max-sm:hidden"} data-testid="home-mix" data-tour="home-mix">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-supporting font-semibold text-ink-2">{t("home.mix.title")}</h3>
        <Link href="/cash#cash-sources-now" className="inline-flex items-center gap-1 text-supporting font-semibold text-brand-700 hover:underline" data-testid="home-mix-more">
          {t("home.mix.more")}
          <ArrowRightIcon aria-hidden width={11} height={11} />
        </Link>
      </div>
      <div className="mt-3 flex items-center gap-4">
        <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }} role="img" aria-label={t("home.mix.alt")} data-testid="home-mix-ring">
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="size-full -rotate-90 overflow-visible" aria-hidden>
            <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="var(--color-subtle)" strokeWidth={STROKE} />
            {mix.slices.map((s, i) => {
              const drawn = Math.max(lens[i] - gap, 0.5);
              const on = chosen?.key === s.key;
              const dim = chosen !== null && !on;
              return (
                <circle
                  key={s.key}
                  cx={SIZE / 2}
                  cy={SIZE / 2}
                  r={R}
                  fill="none"
                  stroke={hueOf(h, s)}
                  strokeOpacity={(arriving(s) ? 0.45 : 1) * (dim ? 0.3 : 1)}
                  strokeWidth={on ? STROKE + 6 : STROKE}
                  strokeDasharray={`${drawn} ${C - drawn}`}
                  strokeDashoffset={-(starts[i] + gap / 2)}
                  onClick={() => toggle(s.key)}
                  className="f-slice cursor-pointer motion-safe:transition-[stroke-width,stroke-opacity] motion-safe:duration-(--dur-fast)"
                  style={{ ["--f-c" as string]: C }}
                  data-testid="home-mix-arc"
                  data-key={s.key}
                />
              );
            })}
          </svg>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-3 text-center">
            {/* INVARIANT 13: the browser prints no percentage. The middle names the source and, where the server states one, its amount. */}
            {centre.amount ? (
              <span className="font-display text-base font-bold leading-none text-ink tabular-nums" data-testid="home-mix-centre-amount">
                {centre.amount}
              </span>
            ) : null}
            <span className="mt-0.5 line-clamp-2 text-supporting leading-tight text-ink-3">{centre.kind === "own" ? t("home.mix.center") : nameOf(centre)}</span>
          </div>
        </div>
        <ul className="min-w-0 flex-1 space-y-0.5" data-testid="home-mix-legend">
          {mix.slices.map((s) => {
            const on = open === s.key;
            // Who stands behind the money: the customer paying early, or the customer whose invoice a financing leg is secured on.
            const sub = s.kind === "buyer" ? t("home.mix.buyerSub", { amount: s.amount ?? "", when: s.when ?? "" }) : s.kind === "planned" && s.buyer ? t("home.mix.against", { buyer: s.buyer }) : null;
            return (
              <li key={s.key} data-testid="home-mix-row" data-kind={s.kind}>
                <button
                  type="button"
                  aria-expanded={on}
                  aria-controls="home-mix-panel"
                  aria-label={t("home.mix.open", { name: nameOf(s) })}
                  onClick={() => toggle(s.key)}
                  className={`motion-press flex w-full items-start gap-2 rounded-control px-1.5 py-1 text-left text-supporting transition-colors duration-(--dur-fast) hover:bg-subtle ${on ? "bg-subtle" : ""}`}
                  data-testid="home-mix-toggle"
                >
                  <span
                    aria-hidden
                    className={`mt-1 size-2.5 shrink-0 rounded-pill ${arriving(s) ? "border-2 bg-transparent" : ""}`}
                    style={arriving(s) ? { borderColor: hueOf(h, s) } : { background: hueOf(h, s) }}
                  />
                  <span className="min-w-0 flex-1">
                    <span className={`block truncate ${s.kind === "buyer" ? "font-semibold text-ok-fg" : on ? "font-semibold text-ink" : "text-ink"}`}>{nameOf(s)}</span>
                    {sub ? (
                      <span className="block truncate text-supporting leading-tight text-ink-3" data-testid="home-mix-sub">
                        {sub}
                      </span>
                    ) : null}
                  </span>
                  {s.amount ? <span className="shrink-0 font-bold tabular-nums text-ink">{s.amount}</span> : null}
                  <ChevronRightIcon aria-hidden width={12} height={12} className={`mt-0.5 shrink-0 text-ink-3 transition-transform duration-(--dur-fast) ${on ? "rotate-90" : ""}`} />
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      {chosen ? (
        <div id="home-mix-panel" className="motion-reveal mt-3 rounded-tile bg-card px-3 py-2.5 shadow-(--shadow-f)" data-testid="home-mix-panel">
          <p className="mb-1 flex items-center gap-2 text-supporting font-bold text-ink">
            <span aria-hidden className="size-2.5 rounded-pill" style={{ background: hueOf(h, chosen) }} />
            {nameOf(chosen)}
          </p>
          <Details h={h} s={chosen} />
        </div>
      ) : null}
    </div>
  );
}
