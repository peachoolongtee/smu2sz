"use client";

import Link from "next/link";
import { useState } from "react";
import { contractsOff } from "@/components/documents";
import {
  Badge,
  Button,
  Callout,
  Card,
  EmptyState,
  ErrorState,
  inputClass,
  LoadingBlock,
  PageHeader,
  Stat,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
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
const STATUS: Record<ProductEligibilityView["status"], { key: DictKey; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  ELIGIBLE: { key: "finance.elig.ELIGIBLE", tone: "ok" },
  ELIGIBLE_UP_TO: { key: "finance.elig.ELIGIBLE_UP_TO", tone: "ok" },
  UNKNOWN: { key: "finance.elig.UNKNOWN", tone: "warn" },
  NOT_ELIGIBLE: { key: "finance.elig.NOT_ELIGIBLE", tone: "bad" },
};

/** The company's financial health and the loans it could be eligible for (ADR-0013, phases 5 and 6). */
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
        <PageHeader title={t("finance.title")} subtitle={t("finance.subtitle")} />
        <EmptyState title={t("buy.off.title")} body={t("buy.off.body")} />
      </>
    );
  }
  const h = health.data;
  return (
    <>
      <PageHeader title={t("finance.title")} subtitle={t("finance.subtitle")}
        actions={<Link className="text-sm font-medium text-brand-700 underline underline-offset-2" href="/buy">{t("buy.back")}</Link>} />
      {health.error ? <ErrorState error={health.error} onRetry={health.reload} /> : null}
      {error ? <ErrorState error={error} /> : null}
      {!h ? <LoadingBlock rows={4} /> : <Health h={h} />}

      {h ? (
        <Card flat id="ratios" title={t("finance.ratios.title")} subtitle={t("finance.ratios.sub")}>
          <p className="text-sm text-ink" data-testid="finance-liquidity">{h.liquidity.text}</p>
          {h.liquidity.available ? (
            <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 lg:grid-cols-4">
              <Stat bare label={t("finance.ratios.current")} value={h.liquidity.current_ratio?.display ?? t("common.none")} />
              <Stat bare label={t("finance.ratios.quick")} value={h.liquidity.quick_ratio?.display ?? t("common.none")} />
              <Stat bare label={t("finance.ratios.debt12")} value={h.liquidity.debt_due_12m_display} />
              <Stat bare label={t("finance.ratios.capex12")} value={h.liquidity.capex_due_12m_display} />
            </dl>
          ) : null}
          <div className="mt-3 grid gap-3 sm:grid-cols-4">
            {INPUTS.map(({ key, label }) => (
              <label key={key} className="grid gap-1 text-meta text-ink-2">
                {t(label)}
                <input className={inputClass} inputMode="numeric" value={inputs[key]}
                  onChange={(e) => setInputs({ ...inputs, [key]: e.target.value.replace(/[^0-9]/g, "") })} data-testid={`finance-${key}`} />
              </label>
            ))}
          </div>
          <div className="mt-3">
            <Button variant="secondary" loading={health.loading && given !== null} onClick={readRatios} data-testid="finance-read-ratios">
              {t("finance.ratios.read")}
            </Button>
          </div>
          <p className="mt-2 text-meta text-ink-3">{h.liquidity.formula}</p>
        </Card>
      ) : null}

      <div className="mt-6">
        <Card flat id="loans" title={t("finance.loans.title")} subtitle={t("finance.loans.sub")}>
          {elig.error ? <ErrorState error={elig.error} onRetry={elig.reload} /> : null}
          <div className="mb-3 flex flex-wrap items-end gap-2">
            <label className="grid gap-1 text-meta text-ink-2">
              {t("finance.loans.months")}
              <input className={inputClass} inputMode="numeric" value={months} onChange={(e) => setMonths(e.target.value.replace(/[^0-9]/g, ""))} data-testid="finance-months" />
            </label>
            <Button variant="secondary" onClick={() => setMonthsGiven(months ? Number.parseInt(months, 10) : null)} data-testid="finance-read-loans">
              {t("finance.loans.read")}
            </Button>
          </div>
          {elig.data ? (
            <>
              <Callout tone="warn">
                <p data-testid="finance-indicative">{elig.data.indicative}</p>
                {elig.data.buyer_concentration_display ? (
                  <p className="mt-1 text-meta">{t("finance.loans.concentration", { share: elig.data.buyer_concentration_display, buyer: elig.data.largest_buyer_id ?? "" })}</p>
                ) : null}
              </Callout>
              <ul className="mt-3 grid gap-4 xl:grid-cols-2" data-testid="finance-products">
                {elig.data.products.map((r) => {
                  const s = STATUS[r.status];
                  const done = added[r.product.id];
                  return (
                    <li key={r.product.id} className="rounded-card border border-line p-4" data-testid={`product-${r.product.id}`}>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold text-ink">{r.product.name}</p>
                          <p className="text-meta text-ink-3">{r.product.lender_name} · {r.all_in_rate_display} · {t("finance.loans.term", { n: r.product.term_months })}</p>
                        </div>
                        <Badge tone={s.tone}>{t(s.key)}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-ink-2">{r.text}</p>
                      <ul className="mt-2 space-y-1 text-meta">
                        {r.criteria.map((c) => (
                          <li key={c.name} className={c.passes === false ? "text-bad-fg" : c.passes === null ? "text-warn-fg" : "text-ink-2"}>
                            {c.passes === false ? "✗" : c.passes === null ? "?" : "✓"} {c.name} {c.required}: {c.observed}
                          </li>
                        ))}
                      </ul>
                      <div className="mt-3">
                        {r.on_menu ? (
                          <span className="text-meta text-ink-3">{t("finance.loans.onMenu")}</span>
                        ) : done ? (
                          <p className="text-meta text-ink" data-testid="finance-added">
                            {t("finance.loans.added", { id: done.approval_id ?? "" })}{" "}
                            <Link href="/approvals" className="font-medium text-brand-700 underline underline-offset-2">{t("buy.toApprovals")}</Link>
                          </p>
                        ) : (
                          <Button variant="secondary" size="sm" loading={busy === r.product.id} onClick={() => void add(r.product.id)} data-testid={`add-${r.product.id}`}>
                            {t("finance.loans.add")}
                          </Button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <LoadingBlock rows={3} />
          )}
        </Card>
      </div>
    </>
  );
}

function Health({ h }: { h: FinanceHealthView }) {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      <Callout tone={h.cash.status === "OK" ? "info" : "warn"}>
        <p data-testid="finance-summary">{h.summary}</p>
      </Callout>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 lg:grid-cols-4" data-testid="finance-stats">
        <Stat bare label={t("finance.headroom")} value={h.cash.headroom_display} tone={h.cash.headroom_fen < 0 ? "bad" : "ok"} />
        <Stat bare label={t("finance.lowest")} value={h.cash.lowest_headroom_display} tone={h.cash.lowest_headroom_fen < 0 ? "bad" : "ok"} hint={t("finance.lowest.day", { day: h.cash.lowest_day })} />
        <Stat bare label={t("finance.coverage")} value={h.coverage.ratio?.display ?? t("common.none")} hint={t("finance.coverage.hint", { n: h.coverage.window_days })} />
        <Stat bare label={t("finance.dscr")} value={h.covenants?.worst_dscr?.display ?? t("common.none")} hint={h.covenants ? t("finance.min", { v: h.covenants.min_dscr.display ?? "" }) : undefined} />
      </dl>
      <p className="text-meta text-ink-3">{h.coverage.formula}</p>
      {h.covenants ? (
        <Card flat id="capacity" title={t("finance.capacity.title")} subtitle={h.covenants.text}>
          <TableWrap label={t("finance.capacity.title")}>
            <table className={tableCls} data-testid="finance-capacity">
              <thead>
                <tr>
                  <th scope="col" className={thCls}>{t("finance.capacity.facility")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("finance.capacity.amount")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("capex.monthly")}</th>
                  <th scope="col" className={thCls}>{t("finance.capacity.binding")}</th>
                </tr>
              </thead>
              <tbody>
                {h.capacity.map((c) => (
                  <tr key={c.facility_id}>
                    <th scope="row" className={`${tdCls} text-left font-medium`}>
                      {c.name}
                      {!c.counts_now ? <Badge tone="neutral" className="ml-2">{t("finance.capacity.zero")}</Badge> : null}
                    </th>
                    <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{c.capacity_display}</td>
                    <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{c.monthly_payment_display ?? t("common.none")}</td>
                    <td className={`${tdCls} text-meta text-ink-2`}>{c.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
          <p className="mt-2 text-meta text-ink-3">{h.covenants.formula}</p>
        </Card>
      ) : null}
      <details className="text-sm">
        <summary className="cursor-pointer text-meta font-medium text-brand-700">{t("buy.assumptions")}</summary>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-meta text-ink-2">
          {h.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
