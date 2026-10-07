"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { BizCard, Disclosure, pillPrimary, pillSecondary } from "@/components/business/kit";
import type { useFixAlert } from "@/components/home/fix-alert";
import { SparkIcon } from "@/components/icons";
import { approvalHref } from "@/components/operation-result";
import { Button, Formula } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { localNames } from "@/lib/business-words";
import type { AlertItem, HomeNextAction } from "@/lib/types";

/**
 * Level 2: the best next action, in the server's words, reduced to what the owner decides on: what it is, what it costs,
 * when the money arrives, and who decides. Everything else (what you receive, the cost of each leg, the lowest cash
 * after, what happens if nothing is done, why this plan, the calculation) waits behind "Details". "Run" asks once, then
 * submits the same bound request as the alerts page (state version and suggestions as shown); above the owner's limit the
 * server only queues it. The answer is rendered by the page.
 */
export function NextActionBlock({ a, stateVersion, fixer }: { a: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert> }) {
  const { t, lang } = useI18n();
  const pathname = usePathname();
  // The alerts route takes the alert as shown; the home's next action carries the same suggestions and version.
  const asAlert = { id: a.alert_id, suggested: a.suggestions } as unknown as AlertItem;
  const waiting = a.pending_approval_id;
  // Running a plan moves money: the first press shows what will happen, the second runs exactly the plan shown.
  const [confirming, setConfirming] = useState(false);
  const costTotal = a.cost_total_display ?? a.cost_display;

  return (
    <BizCard className="p-5 lg:p-6" testId="home-next-action" labelledBy="home-action-title">
      <div data-alert={a.alert_id} className="flex items-start gap-3.5">
        <span aria-hidden className="grid size-12 shrink-0 place-items-center rounded-2xl bg-linear-to-br from-blue-500 to-violet-600 text-white shadow-lg shadow-blue-500/30">
          <SparkIcon width={22} height={22} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink-3">{t("biz.recommended.short")}</p>
          <h2 id="home-action-title" className="text-xl font-semibold leading-snug tracking-tight text-ink" data-testid="next-action-title">
            {a.outcome_title}
          </h2>
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-ink-2" data-testid="next-action-components">
            {a.components.map((c, i) => (
              <li key={i}>
                <span className="figure font-semibold text-ink">{c.amount_short}</span> {localNames(c.what, lang)}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* The three things the owner decides on. */}
      <dl className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-3">
        {costTotal ? (
          <div className="rounded-2xl bg-linear-to-br from-brand-50 to-surface px-4 py-3 ring-1 ring-brand-100">
            <dt className="text-sm text-ink-3">{t("biz.costTotal")}</dt>
            <dd className="figure text-lg font-semibold text-ink" data-testid="next-action-cost">
              {costTotal}
              {a.rate_text ? (
                <span className="ml-1.5 text-sm font-normal text-ink-3">{a.cost_days ? t("biz.costRate", { rate: a.rate_text, days: a.cost_days }) : t("biz.costRateOnly", { rate: a.rate_text })}</span>
              ) : null}
            </dd>
          </div>
        ) : null}
        {a.lands_day !== null ? (
          <div className="rounded-2xl bg-linear-to-br from-teal-50 to-surface px-4 py-3 ring-1 ring-teal-100">
            <dt className="text-sm text-ink-3">{t("biz.fundsAvailable")}</dt>
            <dd className="text-lg font-semibold text-ink" data-testid="next-action-lands">
              {a.lands_when ?? ""}
            </dd>
          </div>
        ) : null}
        <div className={`rounded-2xl px-4 py-3 ring-1 ${a.needs_owner ? "bg-linear-to-br from-warn-bg to-surface ring-warn-line/60" : "bg-linear-to-br from-ok-bg to-surface ring-ok-line/60"}`}>
          <dt className="text-sm text-ink-3">{t("biz.authority")}</dt>
          {a.needs_owner ? (
            <dd className="font-semibold text-warn-fg" data-testid="next-action-needs-owner">
              {t("biz.needsYou")}
              {a.needs_owner_reason ? <span className="block text-sm font-normal">{a.needs_owner_reason}</span> : null}
            </dd>
          ) : (
            <dd className="font-semibold text-ok-fg" data-testid="next-action-within-limits">
              {a.authority_text || t("biz.agentAlone")}
            </dd>
          )}
        </div>
      </dl>

      {confirming && !waiting ? (
        <div className="mt-5 rounded-2xl bg-brand-50 p-4 [animation:biz-reveal_200ms_var(--ease-out)]" role="group" aria-labelledby={`confirm-${a.alert_id}-title`} data-testid={`fix-confirm-${a.alert_id}`}>
          <p id={`confirm-${a.alert_id}-title`} className="font-semibold text-ink">
            {t("biz.confirm.title")}
          </p>
          <p className="mt-0.5 text-sm text-ink-2">
            {a.needs_owner ? t("biz.confirm.bodyQueue") : t("biz.confirm.body", { what: t("biz.confirm.what"), amount: a.receive_display ?? "", cost: costTotal ?? "" })}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="primary" loading={fixer.busyId === a.alert_id} disabled={fixer.busyId !== null} onClick={() => void fixer.fix(asAlert, stateVersion).then(() => setConfirming(false))} data-testid={`fix-${a.alert_id}`}>
              {a.needs_owner ? t("biz.confirm.goQueue") : t("biz.confirm.go")}
            </Button>
            <Button variant="secondary" disabled={fixer.busyId !== null} onClick={() => setConfirming(false)} data-testid={`fix-cancel-${a.alert_id}`}>
              {t("biz.confirm.cancel")}
            </Button>
          </div>
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {waiting ? (
          <div className="contents" role="status" data-testid={`alert-waiting-${a.alert_id}`}>
            <Link href={approvalHref(waiting)} className={pillPrimary} data-testid={`alert-approval-link-${a.alert_id}`}>
              {t("alerts.waiting.open")}
            </Link>
            <span className="order-last basis-full text-sm text-warn-fg">
              <span className="font-semibold">{t("alerts.waiting", { id: waiting })}</span> {t("alerts.waiting.body")}
            </span>
          </div>
        ) : confirming ? null : (
          <Button variant="primary" onClick={() => setConfirming(true)} data-testid={`fix-open-${a.alert_id}`}>
            {a.needs_owner ? t("biz.queueForMe") : t("biz.runPlan")}
          </Button>
        )}
        {pathname === "/cash" ? null : (
          <Link href="/cash#cash-options" className={pillSecondary} data-testid="next-action-alternatives">
            {t("biz.compare")}
          </Link>
        )}
      </div>

      <Disclosure summary={t("biz.details.plan")} className="mt-4 border-t border-line pt-2" testId="next-action-details">
        <div className="space-y-4 text-sm">
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {a.receive_display ? (
              <div>
                <dt className="text-ink-3">{t("biz.receive")}</dt>
                <dd className="figure font-semibold text-ink" data-testid="next-action-receive">
                  {a.receive_display}
                </dd>
              </div>
            ) : null}
            {a.after_lowest_short ? (
              <div>
                <dt className="text-ink-3">{t("biz.lowestAfter")}</dt>
                <dd className="figure font-semibold text-ink" data-testid="next-action-after-lowest">
                  {a.after_lowest_short}
                </dd>
              </div>
            ) : null}
            <div>
              <dt className="text-ink-3">{t("biz.ifNothing")}</dt>
              <dd className="text-ink" data-testid="next-action-if-nothing">
                {a.if_nothing}
              </dd>
            </div>
            <div>
              <dt className="text-ink-3">{t("biz.after")}</dt>
              <dd className="text-ink" data-testid="next-action-after">
                {a.after}
              </dd>
            </div>
          </dl>
          {a.cost_breakdown.length > 1 ? (
            <div>
              <p className="text-ink-3">{t("biz.costTotal")}</p>
              <ul className="mt-1 divide-y divide-line rounded-2xl bg-subtle px-4" data-testid="next-action-cost-breakdown">
                {a.cost_breakdown.map((c, i) => (
                  <li key={i} className="flex items-baseline justify-between gap-3 py-2">
                    <span className="min-w-0 text-ink-2">{localNames(c.label.replace(/:\s*$/, ""), lang)}</span>
                    <span className="figure shrink-0 font-semibold text-ink">{c.display ?? ""}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {a.cheaper_option ? (
            <p className="text-ink-2" data-testid="next-action-cheaper">
              {t("biz.cheaper", { cost: a.cheaper_option.cost_total_display, n: a.cheaper_option.approvals })}
            </p>
          ) : null}
          <div data-testid="next-action-why">
            <p className="font-semibold text-ink">{t("biz.why")}</p>
            <p className="mt-1 text-ink">{a.why}</p>
            <p className="mt-1 text-ink-2">{a.detail}</p>
          </div>
          <div className="space-y-2" data-testid="next-action-calc">
            <p className="font-semibold text-ink">{t("biz.calculation")}</p>
            <p className="text-ink-2" data-testid="next-action-operation">
              {localNames(a.title, lang)}
            </p>
            {a.cost_basis ? (
              <p className="text-xs text-ink-3" data-testid="next-action-cost-basis">
                {a.cost_basis}
              </p>
            ) : null}
            {a.formula ? <Formula>{a.formula}</Formula> : null}
            <ul className="space-y-1">
              {a.legs.map((leg) => (
                <li key={leg.index} className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl bg-subtle px-3 py-2">
                  <span>{localNames(leg.label, lang)}</span>
                  <span className="text-xs text-ink-3">
                    {leg.cost_display ? t("alerts.cost", { cost: leg.cost_display }) : t("biz.noStatedCost")}
                    {leg.lands_day !== null ? ` · ${t("biz.landsShort", { when: leg.lands_when ?? "" })}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Disclosure>
    </BizCard>
  );
}
