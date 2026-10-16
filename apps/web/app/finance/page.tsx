"use client";

import Link from "next/link";
import { useState } from "react";
import { FoldCard } from "@/components/business/surface";
import { contractsOff } from "@/components/documents";
import { cardTitle } from "@/components/home/v2/home-cards";
import { Button, EmptyState, ErrorState, inputClass, LoadingBlock, PageHeader } from "@/components/ui";
import { StatusPill, type PillTone } from "@/components/ui/status-pill";
import { addProductToMenu, getEligibility, getFinanceHealth } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { AddToMenuResult, FinanceHealthView, HealthInputsRequest, ProductEligibilityView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const INPUTS: { key: keyof HealthInputsRequest; label: DictKey }[] = [
  { key: "inventory_fen", label: "finance.in.inventory" },
  { key: "other_current_assets_fen", label: "finance.in.otherAssets" },
  { key: "trade_payables_fen", label: "finance.in.payables" },
  { key: "other_current_liabilities_fen", label: "finance.in.otherLiabilities" },
];
// The pill says who acts (Home's rule): green when the loan is there to take, amber when it needs the owner's answer, quiet when it is not on offer.
const STATUS: Record<ProductEligibilityView["status"], { key: DictKey; tone: PillTone }> = {
  ELIGIBLE: { key: "finance.elig.ELIGIBLE", tone: "green" },
  ELIGIBLE_UP_TO: { key: "finance.elig.ELIGIBLE_UP_TO", tone: "green" },
  UNKNOWN: { key: "finance.elig.UNKNOWN", tone: "amber" },
  NOT_ELIGIBLE: { key: "finance.elig.NOT_ELIGIBLE", tone: "neutral" },
};

/**
 * The company's financial health and the loans it could be eligible for (ADR-0013, phases 5 and 6), in Home's language: the server's one sentence under the title, four figure cards,
 * then what the owner can borrow and from whom as short rows. What is worth keeping but not reading first (the owner's ratio entries, each lender's criteria, the formulas and
 * assumptions) folds away. Every word and figure is the server's or the dictionary's.
 */
export default function FinancePage() {
  const { t } = useI18n();
  const [inputs, setInputs] = useState<Record<keyof HealthInputsRequest, string>>({
    inventory_fen: "", other_current_assets_fen: "", trade_payables_fen: "", other_current_liabilities_fen: "",
  });
  const [given, setGiven] = useState<HealthInputsRequest | null>(null);
  const [months, setMonths] = useState("");
  const [monthsGiven, setMonthsGiven] = useState<number | null>(null);
  const health = useAsync(() => getFinanceHealth(given), [given]);
  const elig = useAsync(() => getEligibility(monthsGiven ? { months_trading: monthsGiven } : null), [monthsGiven]);
  const [added, setAdded] = useState<Record<string, AddToMenuResult>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function readRatios() {
    // Whole yuan typed by the owner; the request carries fen (an exact integer).
    const out: HealthInputsRequest = {};
    for (const { key } of INPUTS) {
      const v = inputs[key].trim();
      out[key] = v === "" ? null : Number.parseInt(v, 10) * 100;
    }
    setGiven(out);
  }

  async function add(productId: string) {
    setBusy(productId);
    setError(null);
    try {
      const r = await addProductToMenu(productId);
      setAdded({ ...added, [productId]: r });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if ((health.error && contractsOff(health.error)) || (elig.error && contractsOff(elig.error))) {
    return (
      <>
        <PageHeader section="deals" title={t("finance.title")} subtitle={t("finance.subtitle")} />
        <EmptyState title={t("buy.off.title")} body={t("buy.off.body")} />
      </>
    );
  }
  const h = health.data;
  return (
    <div className="flow-f min-w-0">
      {/* The server's one sentence is the page's line (Home's summary under the headline), in place of the generic subtitle once it is read. */}
      <PageHeader
        section="deals"
        title={t("finance.title")}
        subtitle={h ? <span data-testid="finance-summary">{lead(h.summary)}</span> : t("finance.subtitle")}
      />
      <div className="space-y-4">
        {health.error ? <ErrorState error={health.error} onRetry={health.reload} /> : null}
        {error ? <ErrorState error={error} /> : null}
        {!h ? <LoadingBlock rows={4} /> : <Figures h={h} />}
        {h ? <Capacity h={h} /> : null}

        <section aria-labelledby="finance-loans-title" className="motion-reveal f-card p-4 sm:p-5" id="loans">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
              <h2 id="finance-loans-title" className={cardTitle}>{t("finance.loans.title")}</h2>
              <p className="mt-1 text-supporting text-ink-3">{t("finance.loans.sub")}</p>
            </div>
            <div className="flex items-end gap-2">
              <label className="grid gap-1 text-supporting text-ink-3">
                {t("finance.loans.months")}
                <input className={`${inputClass} w-24`} inputMode="numeric" value={months} onChange={(e) => setMonths(e.target.value.replace(/[^0-9]/g, ""))} data-testid="finance-months" />
              </label>
              <Button size="sm" variant="secondary" onClick={() => setMonthsGiven(months ? Number.parseInt(months, 10) : null)} data-testid="finance-read-loans">
                {t("finance.loans.read")}
              </Button>
            </div>
          </div>
          {elig.error ? <ErrorState error={elig.error} onRetry={elig.reload} /> : null}
          {elig.data ? (
            <>
              <p className="mt-3 text-supporting text-ink-3" data-testid="finance-indicative">
                {elig.data.indicative}
                {elig.data.buyer_concentration_display ? <> {t("finance.loans.concentration", { share: elig.data.buyer_concentration_display, buyer: elig.data.largest_buyer_id ?? "" })}</> : null}
              </p>
              <ul className="mt-3 divide-y divide-line" data-testid="finance-products">
                {elig.data.products.map((r) => (
                  <LoanRow key={r.product.id} r={r} done={added[r.product.id]} busy={busy === r.product.id} onAdd={() => void add(r.product.id)} />
                ))}
              </ul>
            </>
          ) : elig.error ? null : (
            <LoadingBlock rows={3} />
          )}
        </section>

        {h ? (
          <FoldCard id="ratios" testId="finance-ratios" title={t("finance.ratios.title")} hint={<span data-testid="finance-liquidity">{h.liquidity.text}</span>}>
            {h.liquidity.available ? (
              <dl className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Mini label={t("finance.ratios.current")} value={h.liquidity.current_ratio?.display ?? t("common.none")} />
                <Mini label={t("finance.ratios.quick")} value={h.liquidity.quick_ratio?.display ?? t("common.none")} />
                <Mini label={t("finance.ratios.debt12")} value={h.liquidity.debt_due_12m_display} />
                <Mini label={t("finance.ratios.capex12")} value={h.liquidity.capex_due_12m_display} />
              </dl>
            ) : null}
            <p className="text-supporting text-ink-3">{t("finance.ratios.sub")}</p>
            <div className="mt-2 grid gap-3 sm:grid-cols-4">
              {INPUTS.map(({ key, label }) => (
                <label key={key} className="grid gap-1 text-supporting text-ink-3">
                  {t(label)}
                  <input className={inputClass} inputMode="numeric" value={inputs[key]}
                    onChange={(e) => setInputs({ ...inputs, [key]: e.target.value.replace(/[^0-9]/g, "") })} data-testid={`finance-${key}`} />
                </label>
              ))}
            </div>
            <div className="mt-3">
              <Button size="sm" variant="secondary" loading={health.loading && given !== null} onClick={readRatios} data-testid="finance-read-ratios">
                {t("finance.ratios.read")}
              </Button>
            </div>
          </FoldCard>
        ) : null}

        {h ? (
          <FoldCard testId="finance-basis" title={t("finance.basis")} hint={t("finance.basis.hint")}>
            <ul className="list-disc space-y-1.5 pl-5 text-supporting text-ink-2">
              <li>{h.coverage.formula}</li>
              {h.covenants ? <li>{h.covenants.formula}</li> : null}
              <li>{h.liquidity.formula}</li>
              {h.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </FoldCard>
        ) : null}
      </div>
    </div>
  );
}

/**
 * The summary's first two sentences (where cash stands, and what covers it): the rest says the coverage and the debt readings, which the cards below carry. A sentence ends at a full stop
 * followed by a capital or a Chinese character, so the stops inside "¥300,000.00" and "1.25×" do not end one.
 */
function lead(summary: string): string {
  return summary.split(/(?<=[.。])\s*(?=[A-Z一-鿿])/).slice(0, 2).join(" ").replace(/。 /g, "。");
}

/** One of the four figure cards, in Home's card language: the title, the figure in the display face, one short line, and a pill when there is a state to say. */
function Figure({ title, value, note, bad, pill, testId }: { title: string; value: string; note?: string; bad?: boolean; pill?: { tone: PillTone; text: string } | null; testId?: string }) {
  return (
    <section className="motion-reveal f-card flex min-w-0 flex-col p-4" data-testid={testId}>
      <div className="flex items-start justify-between gap-2">
        <h2 className={cardTitle}>{title}</h2>
        {pill ? <StatusPill tone={pill.tone}>{pill.text}</StatusPill> : null}
      </div>
      <p className={`mt-3 font-display text-[28px] font-bold leading-none tracking-[-0.03em] tabular-nums ${bad ? "text-bad-fg" : "text-ink"}`}>{value}</p>
      {note ? <p className="mt-auto pt-2 text-pretty text-supporting text-ink-3">{note}</p> : null}
    </section>
  );
}

function Figures({ h }: { h: FinanceHealthView }) {
  const { t } = useI18n();
  const c = h.covenants;
  return (
    <div className="grid items-stretch gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-4" data-testid="finance-stats">
      <Figure title={t("finance.headroom")} value={h.cash.headroom_display} bad={h.cash.headroom_fen < 0} note={t("finance.headroom.note", { cash: h.cash.cash_display, reserve: h.cash.reserve_display })} />
      <Figure
        title={t("finance.lowest")}
        value={h.cash.lowest_display}
        bad={h.cash.lowest_headroom_fen < 0}
        note={t("finance.lowest.vsMin", { amount: h.cash.lowest_headroom_display })}
        pill={{ tone: h.cash.lowest_headroom_fen < 0 ? "amber" : "green", text: t("finance.lowest.day", { day: h.cash.lowest_day }) }}
      />
      <Figure title={t("finance.coverage")} value={h.coverage.ratio?.display ?? t("common.none")} note={t("finance.coverage.hint", { n: h.coverage.window_days })} />
      <Figure
        title={t("finance.dscr")}
        value={c?.worst_dscr?.display ?? t("common.none")}
        bad={c ? !c.dscr_ok : false}
        note={c ? t("finance.min", { v: c.min_dscr.display ?? "" }) : undefined}
      />
    </div>
  );
}

/** How much more the owner could borrow: one row per facility, the amount on the right (no table: three columns of the old one were one sentence each). */
function Capacity({ h }: { h: FinanceHealthView }) {
  const { t } = useI18n();
  if (!h.covenants || !h.capacity.length) return null;
  return (
    <section aria-labelledby="finance-capacity-title" className="motion-reveal f-card p-4 sm:p-5" id="capacity">
      <h2 id="finance-capacity-title" className={cardTitle}>{t("finance.capacity.title")}</h2>
      <p className="mt-1 text-supporting text-ink-3">{h.covenants.text}</p>
      <ul className="mt-3 divide-y divide-line" data-testid="finance-capacity">
        {h.capacity.map((c) => (
          <li key={c.facility_id} className="flex items-start justify-between gap-4 py-3">
            <div className="min-w-0">
              <p className="font-semibold text-ink">{c.name}</p>
              <p className="mt-0.5 text-supporting text-ink-3">{c.text}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="font-display text-lg font-bold tabular-nums text-ink">{c.capacity_display}</p>
              {c.monthly_payment_display ? <p className="text-supporting tabular-nums text-ink-3">{t("capex.monthly")} {c.monthly_payment_display}</p> : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A loan the owner may be eligible for: the name, the lender's terms on one line, the pill, the server's one sentence, the add control; the criteria fold under "why". */
function LoanRow({ r, done, busy, onAdd }: { r: ProductEligibilityView; done: AddToMenuResult | undefined; busy: boolean; onAdd: () => void }) {
  const { t } = useI18n();
  const s = STATUS[r.status];
  return (
    <li className="py-3" data-testid={`product-${r.product.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 font-semibold text-ink">
            {r.product.name}
            <StatusPill tone={s.tone}>{t(s.key)}</StatusPill>
          </p>
          <p className="mt-0.5 text-supporting text-ink-3">
            {r.product.lender_name} · {r.all_in_rate_display} · {t("finance.loans.term", { n: r.product.term_months })}
          </p>
        </div>
        <div className="shrink-0">
          {r.on_menu ? (
            <span className="text-supporting text-ink-3">{t("finance.loans.onMenu")}</span>
          ) : done ? (
            <p className="text-supporting text-ink" data-testid="finance-added">
              {t("finance.loans.added", { id: done.approval_id ?? "" })}{" "}
              <Link href="/approvals" className="font-medium text-brand-700 underline underline-offset-2">{t("buy.toApprovals")}</Link>
            </p>
          ) : (
            <Button variant="secondary" size="sm" loading={busy} onClick={onAdd} data-testid={`add-${r.product.id}`}>
              {t("finance.loans.add")}
            </Button>
          )}
        </div>
      </div>
      <p className="mt-1.5 text-sm text-ink-2">{r.text}</p>
      {r.criteria.length ? (
        <details className="mt-1">
          <summary className="cursor-pointer text-supporting font-medium text-brand-700">{t("finance.loans.why")}</summary>
          <ul className="mt-1.5 space-y-1 text-supporting">
            {r.criteria.map((c) => (
              <li key={c.name} className={c.passes === false ? "text-bad-fg" : c.passes === null ? "text-warn-fg" : "text-ink-2"}>
                {c.passes === false ? "✗" : c.passes === null ? "?" : "✓"} {c.name} {c.required}: {c.observed}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </li>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] bg-subtle px-3 py-2">
      <dt className="text-supporting text-ink-3">{label}</dt>
      <dd className="font-display text-lg font-bold tabular-nums text-ink">{value}</dd>
    </div>
  );
}
