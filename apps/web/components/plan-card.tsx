"use client";

import { useI18n } from "@/lib/i18n";
import type { Displayed, FundingPlan } from "@/lib/types";
import { useBusinessToday } from "@/lib/use-business-today";
import { whenText } from "@/lib/when";
import { PlainCode } from "./badges";
import { PlanNotes } from "./plan-notes";
import { Badge, Card, Formula, TableWrap, tableCls, tdCls, thCls } from "./ui";

/**
 * A funding plan exactly as the router returned it: actions, priced cost lines with formulas, rejected candidates. The Demo
 * views say "Day N"; on a Business page every day is a distance from today (`whenText`) and every sentence the API wrote
 * a `*_when` twin for is shown in those words, the raw sentence being the audit level.
 */
export function PlanCard({
  plan,
  id,
  highlight = false,
  leadTimes,
  today: todayProp,
}: {
  plan: Displayed<FundingPlan>;
  id: string;
  highlight?: boolean;
  /** Each facility's lead time in days (from the funding menu or the books). The landing day of a draw or advance is its request day plus this. */
  leadTimes?: Record<string, number>;
  /** The simulated clock, when the page has read it; on a Business page without it the card reads the clock itself. */
  today?: number;
}) {
  const { t, te } = useI18n();
  const { business, today } = useBusinessToday(todayProp);
  /** "Day 37" in Demo; "in 3 days" on a Business page once the clock is known. */
  const dayText = (day: number): string => (today === null ? t("common.dayN", { n: day }) : whenText(day, today, t));
  /** The server's Business twin of a sentence when there is one and this is a Business page, else the sentence itself. */
  const said = (raw: string | undefined, when: string | null | undefined): string | undefined => (business && when ? when : raw);
  /** The day the cash lands: the API's `lands_day`. Only when the field is absent (an older answer) is it derived: request day plus the facility's lead time, for a draw or advance. */
  const landing = (a: FundingPlan["actions"][number]): number | null => {
    if (a.lands_day !== undefined) return a.lands_day;
    if (a.kind !== "DRAW" && a.kind !== "FINANCE_INVOICE") return null;
    const lead = leadTimes?.[a.facility_id];
    return lead === undefined ? null : a.day + lead;
  };
  /** The day a leg waits for its invoice: only an invoice advance whose eligibility day is after its request day. */
  const waitsUntil = (a: FundingPlan["actions"][number]): number | null =>
    a.kind === "FINANCE_INVOICE" && a.available_from_day !== undefined && a.available_from_day !== null && a.available_from_day > a.day ? a.available_from_day : null;
  const anyWaits = plan.actions.some((a) => waitsUntil(a) !== null);
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
        <PlanNotes
          needsApproval={plan.needs_owner_approval}
          approvalReason={said(plan.approval_reason, plan.approval_reason_when)}
          executableNow={plan.executable_now}
          notExecutableReason={said(plan.not_executable_reason, plan.not_executable_reason_when)}
        />
        <TableWrap label={t("plan.actions")}>
          <table className={tableCls}>
            <caption className="sr-only">{t("plan.actions")}</caption>
            <thead>
              <tr>
                <th scope="col" className={thCls}>{t("plan.action")}</th>
                <th scope="col" className={thCls}>{t("plan.facility")}</th>
                <th scope="col" className={thCls}>{anyWaits ? t("plan.requestedOrFrom") : t("plan.requested")}</th>
                <th scope="col" className={thCls}>{t("plan.lands")}</th>
                <th scope="col" className={`${thCls} text-right`}>{t("common.amount")}</th>
                <th scope="col" className={thCls}>{t("plan.repay")}</th>
              </tr>
            </thead>
            <tbody>
              {plan.actions.map((a, i) => (
                <tr key={i}>
                  <td className={`${tdCls} font-medium`}>{te("action", a.kind)}</td>
                  <td className={`${tdCls} font-mono text-meta`}>
                    {a.facility_id}
                    {a.receivable_id ? ` · ${a.receivable_id}` : ""}
                  </td>
                  <td className={`${tdCls} tabular-nums`} data-testid="plan-available-from">
                    {waitsUntil(a) !== null ? dayText(waitsUntil(a) ?? a.day) : a.kind === "EARLY_PAY" && plan.executable_now === false ? t("plan.needsBuyer") : dayText(a.day)}

                  </td>
                  <td className={`${tdCls} tabular-nums`} data-testid="plan-lands">
                    {landing(a) !== null ? dayText(landing(a) ?? 0) : t("common.none")}
                  </td>
                  <td className={`${tdCls} text-right tabular-nums`}>{a.amount_display}</td>
                  <td className={`${tdCls} tabular-nums`}>{a.repay_day !== null ? dayText(a.repay_day) : t("common.none")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>

        <div>
          <h3 className="mb-1.5 text-meta font-semibold uppercase tracking-wide text-ink-3">{t("plan.costs")}</h3>
          <ul className="divide-y divide-line rounded-tile border border-line">
            {plan.costs.map((c) => (
              <li key={c.label} className="space-y-1.5 px-3 py-2">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm">{said(c.label, c.label_when)}</span>
                  <span className="font-medium tabular-nums">{c.display}</span>
                </div>
                <Formula>{c.formula}</Formula>
                <PlanNotes
                  needsApproval={c.needs_owner_approval}
                  approvalReason={said(c.approval_reason, c.approval_reason_when)}
                  executableNow={c.executable_now}
                  notExecutableReason={said(c.not_executable_reason, c.not_executable_reason_when)}
                />
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
              <li key={v.code} className="rounded-tile border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg">
                <PlainCode code={v.code} tone="warn" /> <span className="ml-1">{said(v.message, v.message_when)}</span>
                {v.cure_note ? <p className="mt-1 text-supporting">{said(v.cure_note, v.cure_note_when)}</p> : null}
              </li>
            ))}
          </ul>
        ) : null}

        {plan.rejected.length ? (
          <div>
            <h3 className="mb-1.5 text-meta font-semibold uppercase tracking-wide text-ink-3">{t("plan.rejected")}</h3>
            <ul className="space-y-2">
              {plan.rejected.map((r) => (
                <li key={r.label} className="rounded-tile border border-line px-3 py-2 text-sm">
                  <p className="font-medium">{r.label}</p>
                  <p className="text-ink-2">{said(r.note, r.note_when)}</p>
                  {r.reasons.length ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {r.reasons.map((c) => (
                        <PlainCode key={c} code={c} tone="bad" />
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
