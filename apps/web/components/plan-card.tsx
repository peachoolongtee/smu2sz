"use client";

import { useI18n } from "@/lib/i18n";
import type { Displayed, FundingPlan } from "@/lib/types";import { CodeBadge } from "./badges";
import { Badge, Card, Formula, TableWrap, tableCls, tdCls, thCls } from "./ui";

/** A funding plan exactly as the router returned it: actions, priced cost lines with formulas, rejected candidates. */
export function PlanCard({
  plan,
  id,
  highlight = false,
  leadTimes,
}: {
  plan: Displayed<FundingPlan>;
  id: string;
  highlight?: boolean;
  /** Each facility's lead time in days (from the funding menu or the books). The landing day of a draw or advance is its request day plus this. */
  leadTimes?: Record<string, number>;
}) {
  const { t, te } = useI18n();
  /** The day the cash lands: only for funding that brings cash in (draw, invoice advance) on a facility whose lead time is known. */
  const landing = (a: FundingPlan["actions"][number]): number | null => {
    if (a.kind !== "DRAW" && a.kind !== "FINANCE_INVOICE") return null;
    const lead = leadTimes?.[a.facility_id];
    return lead === undefined ? null : a.day + lead;
  };
  return (
    <Card
      id={id}
      title={plan.label || t("plan.title")}
      subtitle={t("plan.need", { need: plan.need_display })}
      tone={highlight ? "brand" : undefined}
      actions={
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={plan.basis === "COMMITTED" ? "ok" : "warn"}>{te("basis", plan.basis)}</Badge>
          <Badge tone={plan.admissible ? "ok" : "bad"}>{plan.admissible ? t("plan.admissible") : t("plan.notAdmissible")}</Badge>
        </div>
      }
    >
      <div className="space-y-4">
        <TableWrap label={t("plan.actions")}>
          <table className={tableCls}>
            <caption className="sr-only">{t("plan.actions")}</caption>
            <thead>
              <tr>
                <th scope="col" className={thCls}>{t("plan.action")}</th>
                <th scope="col" className={thCls}>{t("plan.facility")}</th>
                <th scope="col" className={thCls}>{t("plan.requested")}</th>
                <th scope="col" className={thCls}>{t("plan.lands")}</th>
                <th scope="col" className={`${thCls} text-right`}>{t("common.amount")}</th>
                <th scope="col" className={thCls}>{t("plan.repay")}</th>
              </tr>
            </thead>
            <tbody>
              {plan.actions.map((a, i) => (
                <tr key={i}>
                  <td className={`${tdCls} font-medium`}>{te("action", a.kind)}</td>
                  <td className={`${tdCls} font-mono text-xs`}>
                    {a.facility_id}
                    {a.receivable_id ? ` · ${a.receivable_id}` : ""}
                  </td>
                  <td className={`${tdCls} tabular-nums`}>{t("common.dayN", { n: a.day })}</td>
                  <td className={`${tdCls} tabular-nums`} data-testid="plan-lands">
                    {landing(a) !== null ? t("common.dayN", { n: landing(a) ?? 0 }) : t("common.none")}
                  </td>
                  <td className={`${tdCls} text-right tabular-nums`}>{a.amount_display}</td>
                  <td className={`${tdCls} tabular-nums`}>{a.repay_day !== null ? t("common.dayN", { n: a.repay_day }) : t("common.none")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>

        <div>
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("plan.costs")}</h3>
          <ul className="divide-y divide-line rounded-lg border border-line">
            {plan.costs.map((c) => (
              <li key={c.label} className="space-y-1.5 px-3 py-2">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm">{c.label}</span>
                  <span className="font-medium tabular-nums">{c.display}</span>
                </div>
                <Formula>{c.formula}</Formula>
              </li>
            ))}
            <li className="flex items-baseline justify-between gap-3 bg-subtle px-3 py-2 font-semibold">
              <span>{t("plan.total")}</span>
              <span className="text-lg tabular-nums" data-testid="plan-total">
                {plan.total_cost_display}
              </span>
            </li>
          </ul>
        </div>

        {plan.violations.length ? (
          <ul className="space-y-2">
            {plan.violations.map((v) => (
              <li key={v.code} className="rounded-lg border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg">
                <CodeBadge code={v.code} tone="warn" /> <span className="ml-1">{v.message}</span>
                {v.cure_note ? <p className="mt-1 text-xs">{v.cure_note}</p> : null}
              </li>
            ))}
          </ul>
        ) : null}

        {plan.rejected.length ? (
          <div>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("plan.rejected")}</h3>
            <ul className="space-y-2">
              {plan.rejected.map((r) => (
                <li key={r.label} className="rounded-lg border border-line px-3 py-2 text-sm">
                  <p className="font-medium">{r.label}</p>
                  <p className="text-ink-2">{r.note}</p>
                  {r.reasons.length ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {r.reasons.map((c) => (
                        <CodeBadge key={c} code={c} tone="bad" />
                      ))}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
