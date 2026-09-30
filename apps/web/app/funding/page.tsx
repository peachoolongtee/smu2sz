"use client";

import { useState } from "react";
import { CodeBadge, FacilityStatusBadge } from "@/components/badges";
import { CheckIcon, XIcon } from "@/components/icons";
import { PlanCard } from "@/components/plan-card";
import {
  Badge,
  Callout,
  Card,
  ErrorState,
  Formula,
  KeyValueList,
  LoadingBlock,
  PageHeader,
  Segmented,
  Stat,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
import { planFunding } from "@/lib/api";
import { useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { FundingView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

export default function FundingPage() {
  const { t } = useI18n();
  const [basis, setBasis] = useState<"COMMITTED" | "EXPECTED">("COMMITTED");
  const snapshot = useDemo().funding;
  // A decision-time snapshot (set by the demo stepper) wins over a live re-plan, which is empty once the plan has executed.
  const res = useAsync(() => (snapshot ? Promise.resolve(snapshot) : planFunding()), [Boolean(snapshot)]);

  return (
    <>
      <PageHeader
        title={t("fund.title")}
        subtitle={t("fund.subtitle")}
        actions={
          <Segmented
            label={t("fund.basis")}
            name="basis"
            value={basis}
            onChange={setBasis}
            options={[
              { value: "COMMITTED", label: t("fund.committed") },
              { value: "EXPECTED", label: t("fund.expected") },
            ]}
          />
        }
      />
      {res.error ? (
        <ErrorState error={res.error} onRetry={res.reload} />
      ) : !res.data ? (
        <LoadingBlock rows={4} />
      ) : (
        <FundingBody view={res.data} basis={basis} snapshot={Boolean(snapshot)} />
      )}
    </>
  );
}

function FundingBody({ view, basis, snapshot }: { view: FundingView; basis: "COMMITTED" | "EXPECTED"; snapshot: boolean }) {
  const { t, te } = useI18n();
  const plan = basis === "COMMITTED" ? view.committed : view.expected;
  const inPlan = new Set(plan.actions.map((a) => a.facility_id));
  const m = view.marginal;

  return (
    <div className="space-y-6">
      {snapshot ? <Callout tone="info">{t("fund.snapshot")}</Callout> : null}
      {basis === "EXPECTED" ? <Callout tone="warn" title={t("fund.expected")}>{t("fund.expected.note")}</Callout> : null}

      <Card id="menu" title={t("fund.menu")} subtitle={t("fund.menu.sub")}>
        <TableWrap label={t("fund.menu")}>
          <table className={`${tableCls} min-w-[56rem]`}>
            <caption className="sr-only">{t("fund.menu")}</caption>
            <thead>
              <tr>
                <th scope="col" className={`${thCls} sticky left-0 z-10`}>{t("fund.source")}</th>
                <th scope="col" className={thCls}>{t("fund.cost")}</th>
                <th scope="col" className={thCls}>{t("fund.ttc")}</th>
                <th scope="col" className={thCls}>{t("fund.state")}</th>
                <th scope="col" className={`${thCls} text-right`}>{t("fund.limit")}</th>
                <th scope="col" className={thCls}>{t("fund.covenant")}</th>
                <th scope="col" className={thCls}>{t("fund.admissible")}</th>
              </tr>
            </thead>
            <tbody>
              {view.menu.map((row) => {
                const selected = inPlan.has(row.facility.id);
                return (
                  <tr key={row.facility.id} className={selected ? "bg-brand-50" : ""} data-testid={`menu-${row.facility.id}`}>
                    <th scope="row" className={`${tdCls} sticky left-0 z-10 min-w-40 text-left font-medium ${selected ? "bg-brand-50" : "bg-surface"}`}>
                      {row.facility.name}
                      <span className="mt-0.5 block font-mono text-xs font-normal text-ink-3">{row.facility.id}</span>
                      {selected ? <Badge tone="brand" className="mt-1">{t("fund.inPlan")}</Badge> : null}
                    </th>
                    <td className={`${tdCls} min-w-36`}>{row.cost_display}</td>
                    <td className={`${tdCls} whitespace-nowrap tabular-nums`}>{row.time_to_cash_display}</td>
                    <td className={tdCls}>
                      <FacilityStatusBadge status={row.facility.status} />
                    </td>
                    <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{row.facility.limit_display}</td>
                    <td className={`${tdCls} min-w-44 text-xs text-ink-2`}>{row.covenant_effect}</td>
                    <td className={`${tdCls} min-w-56`}>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge tone={row.admissible ? "ok" : "bad"}>
                          {row.admissible ? <CheckIcon /> : <XIcon />}
                          {row.admissible ? t("fund.yes") : t("fund.no")}
                        </Badge>
                        {row.reason_codes.map((c) => (
                          <CodeBadge key={c} code={c} tone="bad" />
                        ))}
                      </div>
                      <p className="mt-1 text-xs text-ink-2">{row.reason}</p>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableWrap>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <PlanCard plan={plan} id="plan" highlight />

        <div className="min-w-0 space-y-6">
          <Card id="marginal" title={t("fund.marginal")} subtitle={t("fund.marginal.sub")}>
            <dl className="grid grid-cols-2 gap-3">
              <Stat label={t("fund.marginalRate")} value={m.rate_display} hint={m.facility_name} tone="brand" />
              <Stat label={t("fund.breakEven")} value={m.break_even_display} hint={t("fund.breakEven.hint")} tone="brand" />
            </dl>
            <div className="mt-3 space-y-2">
              <Formula>{m.break_even_formula}</Formula>
              <p className="text-xs text-ink-2">{m.excluded_note}</p>
            </div>
          </Card>

          <Card id="extension" title={t("fund.extension")} subtitle={t("fund.extension.sub")}>
            <KeyValueList
              items={[
                { k: t("fund.ext.receivables"), v: m.extension_extra_receivables_display },
                { k: t("fund.ext.perInvoice"), v: m.extension_per_invoice_display },
                { k: t("fund.ext.committed"), v: m.extension_committed_12m_display },
                { k: t("fund.ext.notional"), v: m.extension_notional_line_12m_display },
                { k: t("fund.ext.expected"), v: m.extension_expected_12m_display },
              ]}
            />
            <div className="mt-3">
              <Formula>{m.extension_formula}</Formula>
            </div>
          </Card>

          <Card id="compare" title={t("fund.compare")} subtitle={t("fund.compare.sub")}>
            <ul className="divide-y divide-line">
              {view.comparison.map((c) => (
                <li key={c.label} className="flex items-center justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <p className={`text-sm ${c.selected ? "font-semibold" : ""}`}>{c.label}</p>
                    <p className="text-xs text-ink-3">{c.note}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {c.selected ? <Badge tone="brand">{te("fund", "selected")}</Badge> : null}
                    <span className="font-semibold tabular-nums">{c.total_display}</span>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
