"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRightIcon, BankIcon, ChevronRightIcon, WalletIcon } from "@/components/icons";
import { fundingMix, lenderHue, OWN_HUE, type FundingSlice } from "@/lib/funding-mix";
import { useI18n } from "@/lib/i18n";
import type { HomeView } from "@/lib/types";

const SIZE = 196;
const STROKE = 22;
const R = (SIZE - STROKE) / 2;
const C = 2 * Math.PI * R;

const hueOf = (h: HomeView, s: FundingSlice) => (s.kind === "own" ? OWN_HUE : lenderHue(h, s.facilityId));

/** The ring: one arc per slice, round-capped with a gap between arcs; the chosen slice stands out and its share is in the middle. */
function Ring({ h, slices, chosen, onChoose, label }: { h: HomeView; slices: FundingSlice[]; chosen: FundingSlice | null; onChoose: (key: string) => void; label: string }) {
  const { t } = useI18n();
  const total = slices.reduce((s, x) => s + x.fen, 0);
  const gap = slices.length > 1 ? STROKE + 6 : 0;
  // Where each arc starts along the ring: the lengths of the arcs before it.
  const lens = slices.map((s) => (s.fen / total) * C);
  const starts = lens.map((_, i) => lens.slice(0, i).reduce((a, b) => a + b, 0));
  const centre = chosen ?? slices.find((s) => s.kind === "own") ?? null;
  return (
    <div className="relative mx-auto size-[196px]" role="img" aria-label={label} data-testid="home-mix-ring">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="size-full -rotate-90 overflow-visible" aria-hidden>
        <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="var(--color-subtle)" strokeWidth={STROKE} />
        {slices.map((s, i) => {
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
              strokeOpacity={(s.kind === "planned" ? 0.4 : 1) * (dim ? 0.3 : 1)}
              strokeWidth={on ? STROKE + 8 : STROKE}
              strokeLinecap={slices.length > 1 ? "round" : "butt"}
              strokeDasharray={`${drawn} ${C - drawn}`}
              strokeDashoffset={-(starts[i] + gap / 2)}
              onClick={() => onChoose(s.key)}
              className="cursor-pointer motion-safe:transition-[stroke-width,stroke-opacity] motion-safe:duration-(--dur-fast)"
              data-testid="home-mix-arc"
            />
          );
        })}
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="font-display text-[30px] font-extrabold leading-none tracking-[-0.02em] text-ink tabular-nums" data-testid="home-mix-own-share">
          {centre ? centre.share : 0}%
        </span>
        <span className="mt-1 line-clamp-2 max-w-[112px] text-supporting text-ink-3">{!centre || centre.kind === "own" ? t("home.dash.mix.center") : centre.name}</span>
      </div>
    </div>
  );
}

/** One fact in a source's details: the label on the left, the server's figure or words on the right. */
function Fact({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <dt className="text-supporting text-ink-3">{label}</dt>
      <dd className="text-right text-supporting font-bold text-ink tabular-nums">{value}</dd>
    </div>
  );
}

/** What there is to know about one source: for own money the cash against the minimum; for a lender its limit, what is in use, what is left, how fast its money lands and each lot. */
function Details({ h, s }: { h: HomeView; s: FundingSlice }) {
  const { t } = useI18n();
  if (s.kind === "own") {
    const c = h.cash;
    return (
      <div data-testid="home-mix-details" data-kind="own">
        <p className="text-supporting text-ink-2">{t("home.dash.mix.ownBody")}</p>
        <dl className="mt-2 divide-y divide-line">
          <Fact label={t("home.dash.mix.cashToday")} value={c.cash_display} />
          <Fact label={t("home.dash.mix.minimum")} value={c.floor_display} />
          <Fact label={t("home.dash.mix.above")} value={(c.headroom_fen ?? 0) >= 0 ? c.headroom_short : null} />
        </dl>
      </div>
    );
  }
  const f = h.facilities.find((x) => x.id === s.facilityId) ?? null;
  const lots = f ? (h.cash.funding_lots ?? []).filter((l) => l.facility_name === f.name) : [];
  return (
    <div data-testid="home-mix-details" data-kind={s.kind}>
      <dl className="divide-y divide-line">
        {s.kind === "planned" ? (
          <>
            <Fact label={t("home.dash.mix.plan")} value={s.amount} />
            <Fact label={t("home.dash.mix.arrives")} value={s.when} />
            <Fact label={t("home.dash.mix.cost")} value={s.cost} />
          </>
        ) : null}
        {f ? (
          <>
            <Fact label={t("home.dash.mix.limit")} value={f.limit_display} />
            <Fact label={t("home.dash.mix.inUse")} value={f.drawn_display} />
            <Fact label={t("home.dash.mix.available")} value={f.available_display} />
            <Fact label={t("home.dash.mix.lands")} value={f.lead_time_days > 0 ? t("home.dash.mix.leadDays", { n: f.lead_time_days }) : t("home.dash.mix.sameDay")} />
          </>
        ) : null}
      </dl>
      {lots.length ? (
        <>
          <p className="mt-3 text-meta font-bold uppercase tracking-wide text-ink-3">{t("home.dash.mix.lots")}</p>
          <ul className="mt-1.5 space-y-1.5">
            {lots.map((l, i) => (
              <li key={i} className="flex items-baseline justify-between gap-3 rounded-tile bg-subtle px-3 py-2 text-supporting">
                <span className="font-bold text-ink tabular-nums">{l.amount_display}</span>
                <span className="text-right text-ink-3">
                  {t(l.landed ? "home.dash.mix.lotLanded" : "home.dash.mix.lotArriving", { when: l.arrival_when })}
                  {l.maturity_when ? ` · ${t("home.dash.mix.lotRepaid", { when: l.maturity_when })}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

function Row({ h, s, open, onToggle }: { h: HomeView; s: FundingSlice; open: boolean; onToggle: () => void }) {
  const { t } = useI18n();
  const own = s.kind === "own";
  const hue = hueOf(h, s);
  const name = own ? t("home.dash.mix.own") : (s.name ?? "");
  const sub = own
    ? t("home.dash.mix.ownNote")
    : s.kind === "planned"
      ? t("home.dash.mix.planned", { amount: s.amount ?? "" })
      : s.when
        ? t("home.dash.mix.arriving", { amount: s.amount ?? "", when: s.when })
        : t("home.dash.mix.received", { amount: s.amount ?? "" });
  const Icon = own ? WalletIcon : BankIcon;
  const panel = `home-mix-panel-${s.key}`;
  return (
    <li className={`rounded-[18px] transition-colors duration-(--dur-fast) ${open ? "bg-canvas" : ""}`} data-testid="home-mix-row" data-kind={s.kind}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panel}
        onClick={onToggle}
        className="motion-press flex w-full items-center gap-3 rounded-[18px] p-2 text-left hover:bg-canvas"
        data-testid="home-mix-toggle"
      >
        <span
          aria-hidden
          className={`grid size-10 shrink-0 place-items-center rounded-tile ${own ? "text-on-deep" : "text-ink"} ${s.kind === "planned" ? "border-2 border-dashed" : ""}`}
          style={s.kind === "planned" ? { borderColor: hue, background: "var(--color-surface)" } : { background: hue }}
        >
          <Icon width={18} height={18} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-bold leading-snug text-ink">{name}</span>
          <span className="block truncate text-supporting text-ink-3">{sub}</span>
        </span>
        <span className="shrink-0 font-display text-sm font-extrabold text-ink tabular-nums">{s.share}%</span>
        <ChevronRightIcon aria-hidden width={14} height={14} className={`shrink-0 text-ink-3 transition-transform duration-(--dur-fast) ${open ? "rotate-90" : ""}`} />
      </button>
      {open ? (
        <div id={panel} className="motion-reveal px-3 pb-3 pt-1">
          <Details h={h} s={s} />
        </div>
      ) : null}
    </li>
  );
}

/**
 * "Who funds you": the owner's own money against each lender's money, as a ring with a share in the middle and one row per source under it. Choosing a row
 * (or its arc) brings that source forward on the ring and opens its details. Lenders and amounts are the server's; the fen only size the arcs and the
 * whole-percent shares (lib/funding-mix.ts).
 */
export function FundingRing({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const [open, setOpen] = useState<string | null>(null);
  const mix = fundingMix(h);
  if (!mix) return null;
  const chosen = mix.slices.find((s) => s.key === open) ?? null;
  const toggle = (key: string) => setOpen((k) => (k === key ? null : key));
  const hasPlanned = mix.slices.some((s) => s.kind === "planned");
  return (
    <section aria-labelledby="home-mix-title" className="rounded-[24px] bg-surface p-5 shadow-(--shadow-lift) sm:p-6" data-testid="home-mix">
      <div className="mb-5 flex items-baseline justify-between gap-3">
        <h2 id="home-mix-title" className="font-display text-lg font-extrabold tracking-[-0.01em] text-ink">
          {t("home.dash.mix")}
        </h2>
        <Link href="/cash#facility-headroom" className="inline-flex items-center gap-1 text-supporting font-semibold text-ink-3 hover:text-brand-700">
          {t("home.dash.mix.more")}
          <ArrowRightIcon width={12} height={12} />
        </Link>
      </div>
      <Ring h={h} slices={mix.slices} chosen={chosen} onChoose={toggle} label={t("home.dash.mix.alt", { share: mix.ownShare })} />
      {mix.ownOnly ? <p className="mt-5 text-center text-supporting text-ink-3">{t("home.dash.mix.ownOnly")}</p> : null}
      <p className="mt-5 text-center text-meta text-ink-3">{t("home.dash.mix.hint")}</p>
      <ul className="mt-3 space-y-1">
        {mix.slices.map((s) => (
          <Row key={s.key} h={h} s={s} open={open === s.key} onToggle={() => toggle(s.key)} />
        ))}
      </ul>
      {hasPlanned ? <p className="mt-4 border-t border-line pt-3 text-supporting text-ink-3">{t("home.dash.mix.dashed")}</p> : null}
    </section>
  );
}
