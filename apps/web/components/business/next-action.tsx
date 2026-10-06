"use client";

import Link from "next/link";
import type { useFixAlert } from "@/components/home/fix-alert";
import { approvalHref } from "@/components/operation-result";
import { Button, Formula, KeyValueList } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { AlertItem, HomeNextAction } from "@/lib/types";

/**
 * Level 2: the best next action, in the server's words. "Go ahead" submits the same bound request as the alerts page
 * (state version and suggestions as shown); when the cost is above the owner's limit the server only queues it. The answer
 * is rendered by the page (the action leaves the page once it has run, its answer must not).
 */
export function NextActionBlock({ a, stateVersion, fixer }: { a: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert> }) {
  const { t } = useI18n();
  // The alerts route takes the alert as shown; the home's next action carries the same suggestions and version.
  const asAlert = { id: a.alert_id, suggested: a.suggestions } as unknown as AlertItem;
  const waiting = a.pending_approval_id;

  const rows: { k: string; v: React.ReactNode }[] = [];
  if (a.receive_display) rows.push({ k: t("biz.receive"), v: a.receive_display });
  const costTotal = a.cost_total_display ?? a.cost_display;
  if (costTotal) {
    rows.push({
      k: t("biz.costTotal"),
      v: (
        <span data-testid="next-action-cost">
          {costTotal}
          {a.rate_text && a.cost_days ? <span className="ml-1 font-normal text-ink-3">{t("biz.costRate", { rate: a.rate_text, days: a.cost_days })}</span> : null}
          {a.rate_text && !a.cost_days ? <span className="ml-1 font-normal text-ink-3">{t("biz.costRateOnly", { rate: a.rate_text })}</span> : null}
          {a.cost_breakdown.length > 1 ? (
            <span className="mt-1 block text-xs font-normal text-ink-2" data-testid="next-action-cost-breakdown">
              {a.cost_breakdown.map((c) => `${c.label}: ${c.display ?? ""}`).join(" · ")}
            </span>
          ) : null}
          {a.cost_basis ? (
            <span className="mt-0.5 block text-xs font-normal text-ink-3" data-testid="next-action-cost-basis">
              {a.cost_basis}
            </span>
          ) : null}
        </span>
      ),
    });
  }
  if (a.lands_day !== null) rows.push({ k: t("biz.lands"), v: <span data-testid="next-action-lands">{a.lands_when ?? ""}</span> });
  rows.push({
    k: t("biz.authority"),
    v: a.needs_owner ? (
      <span className="text-warn-fg" data-testid="next-action-needs-owner">
        {t("biz.needsYou")}
        {a.needs_owner_reason ? <span className="block text-xs font-normal">{a.needs_owner_reason}</span> : null}
      </span>
    ) : (
      <span className="text-ok-fg" data-testid="next-action-within-limits">{a.authority_text || t("biz.agentAlone")}</span>
    ),
  });

  return (
    <section aria-labelledby="home-action-title" className="rounded-(--radius-card) border border-line bg-surface p-5 shadow-(--shadow-card) lg:p-6" data-testid="home-next-action" data-alert={a.alert_id}>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.nextAction")}</p>
      <h2 id="home-action-title" className="mt-1.5 text-lg font-semibold leading-snug text-ink" data-testid="next-action-title">
        {a.title}
      </h2>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <KeyValueList items={rows} />
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-xs font-medium text-ink-3">{t("biz.ifNothing")}</dt>
            <dd className="text-ink" data-testid="next-action-if-nothing">
              {a.if_nothing}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-ink-3">{t("biz.after")}</dt>
            <dd className="text-ink" data-testid="next-action-after">
              {a.after}
            </dd>
          </div>
        </dl>
      </div>
      {a.cheaper_option ? (
        <p className="mt-2 text-xs text-ink-2" data-testid="next-action-cheaper">
          {t("biz.cheaper", { cost: a.cheaper_option.cost_total_display, n: a.cheaper_option.approvals })}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {waiting ? (
          <div className="rounded-md border border-warn-line bg-warn-bg px-3 py-2 text-xs text-warn-fg" role="status" data-testid={`alert-waiting-${a.alert_id}`}>
            <p className="font-semibold">{t("alerts.waiting", { id: waiting })}</p>
            <p className="mt-0.5">{t("alerts.waiting.body")}</p>
            <Link href={approvalHref(waiting)} className="mt-1 inline-block font-medium underline underline-offset-2" data-testid={`alert-approval-link-${a.alert_id}`}>
              {t("alerts.waiting.open")}
            </Link>
          </div>
        ) : (
          <Button variant="primary" loading={fixer.busyId === a.alert_id} disabled={fixer.busyId !== null} onClick={() => void fixer.fix(asAlert, stateVersion)} data-testid={`fix-${a.alert_id}`}>
            {a.needs_owner ? t("biz.queueForMe") : t("biz.goAhead")}
          </Button>
        )}
        <Link href="/cash" className="inline-flex min-h-10 items-center rounded-md border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-subtle" data-testid="next-action-alternatives">
          {t("biz.alternatives")}
        </Link>
      </div>

      <div className="mt-4 space-y-2 border-t border-line pt-3">
        <details data-testid="next-action-why">
          <summary className="cursor-pointer text-sm font-medium text-brand-700">{t("biz.why")}</summary>
          <p className="mt-2 text-sm text-ink">{a.why}</p>
          <p className="mt-1 text-sm text-ink-2">{a.detail}</p>
        </details>
        <details data-testid="next-action-calc">
          <summary className="cursor-pointer text-sm font-medium text-brand-700">{t("biz.calculation")}</summary>
          <div className="mt-2 space-y-2">
            {a.formula ? <Formula>{a.formula}</Formula> : null}
            <ul className="space-y-1 text-sm">
              {a.legs.map((leg) => (
                <li key={leg.index} className="flex flex-wrap items-baseline justify-between gap-2 rounded-md border border-line px-3 py-1.5">
                  <span>{leg.label}</span>
                  <span className="text-xs text-ink-3">
                    {leg.cost_display ? t("alerts.cost", { cost: leg.cost_display }) : t("biz.noStatedCost")}
                    {leg.lands_day !== null ? ` · ${t("biz.landsShort", { when: leg.lands_when ?? "" })}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </details>
      </div>
    </section>
  );
}
