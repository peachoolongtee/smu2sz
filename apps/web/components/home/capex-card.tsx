"use client";

import Link from "next/link";
import { CapexForm, lenderOf, useLenders } from "@/components/capex-form";
import { Badge, Card, Stat } from "@/components/ui";
import { useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";

/**
 * Home: the owner's big-purchase question. They enter what they would buy and what it should earn; the answer (the
 * same evaluation the Big purchases page shows) gives the room to negotiate the price and each lender's terms to
 * negotiate from. Evaluating writes nothing.
 */
export function CapexCard() {
  const { t } = useI18n();
  const capex = useDemo().capex;
  const lender = useLenders();
  const worth = capex?.worth_doing !== false;
  const options = capex?.structures.filter((s) => !s.hypothetical) ?? [];

  return (
    <Card id="home-capex" title={t("home.capex")} subtitle={t("home.capex.sub")}>
      <CapexForm />

      {capex ? (
        <div className="mt-5 space-y-4 border-t border-line pt-4" data-testid="home-capex-result">
          <p className={`text-base font-semibold ${worth ? "text-ok-fg" : "text-warn-fg"}`}>
            {capex.request.label}: {worth ? t("home.capex.worth") : t("home.capex.notWorth")}
          </p>
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <Stat label={t("capex.npv")} value={capex.npv_display} tone={capex.npv_positive ? "ok" : "bad"} />
            <Stat
              label={t("capex.payback")}
              value={capex.payback_month !== null ? t("capex.paybackValue", { n: capex.payback_month }) : t("common.none")}
            />
            <Stat
              label={t("capex.leverage")}
              value={capex.leverage_financed ? `${capex.leverage_financed.text}×` : t("common.none")}
              hint={t("capex.leverage.limit", { limit: capex.leverage_limit_display })}
            />
          </dl>

          {/* The appraisal is −price + the discounted gains, so its value is exactly how much more the price could be. */}
          <div className="rounded-md border border-info-line bg-info-bg px-3 py-2 text-sm text-info-fg" data-testid="home-capex-room">
            <p className="font-semibold">{t("home.capex.room")}</p>
            <p className="mt-0.5">
              {capex.npv_positive
                ? t("home.capex.room.yes", { npv: capex.npv_display, hurdle: capex.request.hurdle_display ?? "" })
                : t("home.capex.room.no", { npv: capex.npv_display, hurdle: capex.request.hurdle_display ?? "" })}
            </p>
          </div>

          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("home.capex.lenders")}</h3>
            <ul className="divide-y divide-line rounded-lg border border-line" data-testid="home-capex-lenders">
              {options.map((s) => {
                const selected = s.id === capex.selected_id;
                return (
                  <li key={s.id} className={`flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm ${selected ? "bg-ok-bg/60" : ""}`}>
                    <span className="min-w-0 flex-1 basis-56">
                      <span className="font-medium text-ink">{lenderOf(s, lender, t("capex.lender.cash"))}</span>
                      <span className="block text-xs text-ink-2">{s.label}</span>
                    </span>
                    <span className="tabular-nums">
                      {s.monthly_payment_display ? t("home.capex.monthly", { amount: s.monthly_payment_display }) : null}
                    </span>
                    <Badge tone={!s.feasible ? "bad" : selected ? "ok" : "neutral"}>
                      {!s.feasible ? t("capex.infeasible") : selected ? t("home.capex.best") : t("capex.feasible")}
                    </Badge>
                  </li>
                );
              })}
            </ul>
            <p className="mt-1.5 text-xs text-ink-3">{t("home.capex.lenders.hint")}</p>
          </div>

          <Link href="/capex" className="inline-block text-sm font-medium text-brand-700 underline underline-offset-2">
            {t("home.capex.more")}
          </Link>
        </div>
      ) : null}
    </Card>
  );
}
