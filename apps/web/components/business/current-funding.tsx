"use client";

import type { ReactNode } from "react";
import { BankIcon, CheckIcon, ClockIcon, StoreIcon } from "@/components/icons";
import { Card } from "@/components/ui";
import { BUYER_HUE, fundingMix, lenderHue, type FundingSlice } from "@/lib/funding-mix";
import { useI18n } from "@/lib/i18n";
import type { HomeView, MenuRow } from "@/lib/types";

type Tone = "ok" | "info" | "plan" | "idle";
const PILL: Record<Tone, string> = { ok: "bg-f-green text-f-green-ink", info: "bg-f-purple-soft text-f-purple-ink", plan: "bg-subtle text-ink-2", idle: "bg-subtle text-ink-3" };

function StatusPill({ text, tone }: { text: string; tone: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-pill px-2.5 py-0.5 text-supporting font-semibold ${PILL[tone]}`} data-testid="cash-current-status" data-tone={tone}>
      {tone === "ok" ? <CheckIcon aria-hidden width={12} height={12} /> : tone === "idle" ? null : <ClockIcon aria-hidden width={12} height={12} />}
      <span className="first-letter:uppercase">{text}</span>
    </span>
  );
}

/**
 * "Your funding": every source of money in one card (it was two, "Current funding" and "Your funding sources"). One row per facility: how much is in use (or in FLOW's
 * plan), from where, its status (received, arriving, in the plan, not used), then how much of the limit is used, what is left and how fast its money lands. A customer's
 * agreed early payment is a row of its own. The amounts, names and words are the server's (the facilities, the plan's legs, the rail, read through lib/funding-mix.ts);
 * the bar's width is only the drawn share of the limit. Only money in use or arriving is a row: a facility the plan would draw shows once the plan has run, never before.
 * `ring` (where the cash comes from) sits beside the rows on a wide screen, above them on a narrow one.
 */
export function FundingCard({ h, customers, menu, ring, children }: { h: HomeView; customers?: { name: string; short: string }[]; menu?: MenuRow[]; ring?: ReactNode; children?: ReactNode }) {
  const { t } = useI18n();
  const slices = fundingMix(h, customers, { withPlan: false })?.slices ?? [];
  const facilities = h.facilities.filter((f) => (f.limit_fen ?? 1) > 0 && slices.some((s) => s.facilityId === f.id && s.kind !== "own"));
  const buyers = slices.filter((s) => s.kind === "buyer");
  const sliceOf = (id: string) => slices.find((s) => s.facilityId === id && s.kind !== "own") ?? null;
  const status = (s: FundingSlice | null): { text: string; tone: Tone } => {
    if (!s) return { text: t("biz.cash.fund.unused"), tone: "idle" };
    if (s.kind === "buyer") return { text: t("biz.cash.fund.agreed", { when: s.when ?? "" }), tone: "info" };
    if (s.kind === "planned") return { text: t("biz.cash.fund.planned", { when: s.when ?? "" }), tone: "plan" };
    return s.when ? { text: t("biz.cash.fund.arriving", { when: s.when }), tone: "info" } : { text: t("biz.cash.fund.received"), tone: "ok" };
  };
  return (
    <Card flat id="cash-sources-now" title={t("biz.cash.funding.title")} subtitle={t("biz.cash.funding.sub")}>
      <div className={ring ? "grid gap-5 lg:grid-cols-[minmax(16rem,1fr)_minmax(0,1.7fr)] lg:gap-6" : ""}>
        {ring ? <div className="min-w-0 lg:border-r lg:border-line lg:pr-6">{ring}</div> : null}
        {facilities.length || buyers.length ? (
          <ul className="motion-rise min-w-0 divide-y divide-line" data-testid="cash-current-lots">
            {facilities.map((f) => {
              const s = sliceOf(f.id);
              const st = status(s);
              const pct = f.limit_fen && f.drawn_fen !== undefined && f.limit_fen > 0 ? Math.min((f.drawn_fen / f.limit_fen) * 100, 100) : 0;
              const ttc = menu?.find((m) => m.facility.id === f.id)?.time_to_cash_display;
              const hue = lenderHue(h, f.id);
              return (
                <li key={f.id} className="py-3.5" data-testid={`cash-facility-${f.id}`} data-kind={s?.kind ?? "unused"}>
                  <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 sm:grid-cols-[auto_minmax(0,1fr)_auto_auto]">
                    <span aria-hidden className={`grid size-10 place-items-center rounded-pill ${s ? "text-white" : "bg-subtle text-ink-3"}`} style={s ? { background: hue } : undefined}>
                      <BankIcon width={18} height={18} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-ink" data-testid="cash-current-from">
                        {f.name}
                      </span>
                      {/* How fast its money lands: true of every facility (a facility does not say whether it is a lender or a buyer's offer, so the line never guesses). */}
                      <span className="block truncate text-supporting text-ink-3">
                        {ttc ? t("biz.facility.speed", { ttc }) : `${t("home.mix.d.lands")}: ${(f.lead_time_days > 0 ? t("home.mix.d.leadDays", { n: f.lead_time_days }) : t("home.mix.d.sameDay")).replace(/^[A-Z]/, (c) => c.toLowerCase())}`}
                      </span>
                    </span>
                    <span className={`text-right font-display text-lg font-bold tabular-nums ${s ? "text-ink" : "text-ink-3"}`} data-testid="cash-current-amount">
                      {s?.amount ?? f.drawn_display}
                    </span>
                    <span className="col-start-2 justify-self-start sm:col-start-auto sm:justify-self-end">
                      <StatusPill {...st} />
                    </span>
                  </div>
                  {/* How much of the limit is in use and what is left: the drawn share as a bar in the source's own colour. */}
                  <div className="mt-2 sm:pl-14">
                    <div role="img" aria-label={`${t("biz.cash.sources.used")}: ${f.drawn_display} / ${f.limit_display}`} className="h-1.5 max-w-md rounded-pill bg-subtle" data-testid="cash-facility-bar" data-pct={Math.round(pct)}>
                      <div className="h-full rounded-pill" style={{ width: `${pct}%`, background: hue }} />
                    </div>
                    <dl className="mt-1.5 flex flex-wrap gap-x-6 gap-y-0.5 text-supporting text-ink-2">
                      <div className="flex gap-1.5">
                        <dt>{t("fund.limit")}</dt>
                        <dd className="font-semibold tabular-nums text-ink">{f.limit_display}</dd>
                      </div>
                      <div className="flex gap-1.5">
                        <dt>{t("biz.drawn")}</dt>
                        <dd className="font-semibold tabular-nums text-ink">{f.drawn_display}</dd>
                      </div>
                      <div className="flex gap-1.5">
                        <dt>{t("biz.available")}</dt>
                        <dd className="font-semibold tabular-nums text-ink">{f.available_display}</dd>
                      </div>
                    </dl>
                  </div>
                </li>
              );
            })}
            {buyers.map((s) => (
              <li key={s.key} className="py-3.5" data-testid="cash-current-row" data-kind="buyer">
                <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 sm:grid-cols-[auto_minmax(0,1fr)_auto_auto]">
                  <span aria-hidden className="grid size-10 place-items-center rounded-pill text-white" style={{ background: BUYER_HUE }}>
                    <StoreIcon width={18} height={18} />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-ink" data-testid="cash-current-from">
                      {s.name}
                    </span>
                    <span className="block truncate text-supporting text-ink-3">{t("biz.cash.fund.fromCustomer")}</span>
                  </span>
                  <span className="text-right font-display text-lg font-bold tabular-nums text-ink" data-testid="cash-current-amount">
                    {s.amount}
                  </span>
                  <span className="col-start-2 justify-self-start sm:col-start-auto sm:justify-self-end">
                    <StatusPill {...status(s)} />
                  </span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="min-w-0 self-center text-sm text-ink-2" data-testid="cash-current-none">
            {t("biz.cash.fund.none")}
          </p>
        )}
      </div>
      {children}
    </Card>
  );
}
