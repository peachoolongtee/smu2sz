"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import { Disclosure } from "@/components/business/kit";
import type { useFixAlert } from "@/components/home/fix-alert";
import { approvalHref } from "@/components/operation-result";
import { Button, Formula, ButtonLink, Stat } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { AlertItem, HomeNextAction } from "@/lib/types";

/**
 * Level 2: the best next step, in the server's words, reduced to what the owner decides on: what it is, what it costs,
 * when the money is available and who decides. "Details" adds, in reading order: before and after side by side (with what you
 * receive and the lowest cash after), the cost of each part, and why in one sentence; the reasoning, the formula, each part's
 * arrival and the cost's assumptions fold once more under "Show the calculation".
 * "Run" asks once, then submits the same bound request as the alerts page (state version and suggestions as shown);
 * above the owner's limit the server only queues it. The answer is rendered by the page: the block leaves once the fix
 * has run, its answer must not.
 */
export function NextActionBlock({ a, stateVersion, fixer }: { a: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert> }) {
  const { t } = useI18n();
  const pathname = usePathname();
  // The alerts route takes the alert as shown; the home's next action carries the same suggestions and version.
  const asAlert = { id: a.alert_id, suggested: a.suggestions } as unknown as AlertItem;
  const waiting = a.pending_approval_id;
  // Running a plan moves money: the first press shows what will happen, the second runs exactly the plan shown.
  const [confirming, setConfirming] = useState(false);
  const costTotal = a.cost_total_display ?? a.cost_display;
  const confirmBody = a.needs_owner
    ? t("biz.confirm.bodyQueue")
    : a.receive_display && costTotal
      ? t("biz.confirm.body", { amount: a.receive_display, cost: costTotal })
      : costTotal
        ? t("biz.confirm.bodyCost", { cost: costTotal })
        : "";

  return (
    <section aria-labelledby="home-action-title" className="rounded-card border border-line bg-surface p-4 shadow-card short:p-3" data-testid="home-next-action" data-alert={a.alert_id}>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.recommended.short")}</p>
      <h2 id="home-action-title" className="mt-1 text-balance text-xl font-semibold leading-snug text-ink" data-testid="next-action-title">
        {a.outcome_title}
      </h2>
      <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm" data-testid="next-action-components">
        {a.components.map((c, i) => (
          <li key={i} className="flex items-baseline gap-2">
            <span className="text-base font-semibold tabular-nums text-ink">{c.amount_short}</span>
            <span className="text-ink-2">{c.what}</span>
          </li>
        ))}
      </ul>

      {/* The three things the owner decides on. */}
      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {costTotal ? (
          <Stat
            label={t("biz.costTotal")}
            testId="next-action-cost"
            value={costTotal}
            caption={a.rate_text ? (a.cost_days ? t("biz.costRate", { rate: a.rate_text, days: a.cost_days }) : t("biz.costRateOnly", { rate: a.rate_text })) : undefined}
          />
        ) : null}
        {a.lands_day !== null ? <Stat label={t("biz.fundsAvailable")} testId="next-action-lands" value={a.lands_when ?? ""} /> : null}
        {a.needs_owner ? (
          <Stat className="col-span-2 sm:col-span-1" label={t("biz.authority")} tone="warn" tint testId="next-action-needs-owner" value={<span className="text-base">{t("biz.needsYou")}{a.needs_owner_reason ? <span className="block text-sm font-normal text-warn-fg max-sm:hidden" data-testid="next-action-needs-owner-reason">{a.needs_owner_reason}</span> : null}</span>} />
        ) : (
          <Stat className="col-span-2 sm:col-span-1" label={t("biz.authority")} tone="ok" tint testId="next-action-within-limits" value={<span className="text-sm">{a.authority_text || t("biz.agentAlone")}</span>} />
        )}
      </dl>

      {confirming && !waiting ? (
        <div className="mt-4 rounded-tile border border-brand-100 bg-brand-50 p-4" role="group" aria-labelledby={`confirm-${a.alert_id}-title`} data-testid={`fix-confirm-${a.alert_id}`}>
          <p id={`confirm-${a.alert_id}-title`} className="font-semibold text-ink">
            {a.needs_owner ? t("biz.confirm.titleQueue") : t("biz.confirm.title")}
          </p>
          {confirmBody ? <p className="mt-0.5 text-sm text-ink-2">{confirmBody}</p> : null}
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

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {waiting ? (
          <>
            <div className="rounded-tile border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg" role="status" data-testid={`alert-waiting-${a.alert_id}`}>
              <p className="font-semibold">{t("alerts.waiting.short")}</p>
            </div>
            {/* The one primary while the plan waits for the owner: the question to answer. */}
            <ButtonLink href={approvalHref(waiting)} variant="primary" data-testid={`alert-approval-link-${a.alert_id}`}>
              {t("biz.review")}
            </ButtonLink>
          </>
        ) : confirming ? null : (
          <Button variant="primary" onClick={() => setConfirming(true)} data-testid={`fix-open-${a.alert_id}`}>
            {a.needs_owner ? t("biz.queueForMe") : t("biz.runPlan")}
          </Button>
        )}
        {pathname === "/cash" ? null : (
          <ButtonLink href="/cash#cash-options" data-testid="next-action-alternatives">
            {t("biz.compare")}
          </ButtonLink>
        )}
      </div>

      <Disclosure summary={t("biz.details.plan")} className="mt-4 border-t border-line pt-2" testId="next-action-details">
        <div className="space-y-4 text-sm">
          {/* On a phone the reason the owner must decide waits here, so the button comes up the screen; a desktop shows it in the tile. */}
          {a.needs_owner && a.needs_owner_reason ? (
            <p className="text-warn-fg sm:hidden" data-testid="next-action-needs-owner-reason-folded">
              {a.needs_owner_reason}
            </p>
          ) : null}
          {/* Before and after, side by side: the one comparison the owner reads first. */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-tile bg-bad-bg/60 p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-bad-fg">{t("biz.ifNothing")}</p>
              <p className="mt-1 text-ink" data-testid="next-action-if-nothing">{a.if_nothing}</p>
            </div>
            <div className="rounded-tile bg-ok-bg/70 p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-ok-fg">{t("biz.afterPlan")}</p>
              <p className="mt-1 text-ink" data-testid="next-action-after">{a.after}</p>
              {a.receive_display || a.after_lowest_short ? (
                <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs">
                  {a.receive_display ? (
                    <div className="flex items-baseline gap-1.5">
                      <dt className="text-ink-3">{t("biz.receive")}</dt>
                      <dd className="font-bold tabular-nums text-ink" data-testid="next-action-receive">{a.receive_display}</dd>
                    </div>
                  ) : null}
                  {a.after_lowest_short ? (
                    <div className="flex items-baseline gap-1.5">
                      <dt className="text-ink-3">{t("biz.lowestAfter")}</dt>
                      <dd className="font-bold tabular-nums text-ink" data-testid="next-action-after-lowest">{a.after_lowest_short}</dd>
                    </div>
                  ) : null}
                </dl>
              ) : null}
            </div>
          </div>
          {/* The cost by part: the source in bold, its terms in one quiet line (the full words are its title). */}
          {a.cost_breakdown.length > 1 ? (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-ink-3">{t("biz.costTotal")}</p>
              <ul className="mt-1.5 divide-y divide-line rounded-tile border border-line px-3" data-testid="next-action-cost-breakdown">
                {a.cost_breakdown.map((c, i) => {
                  const label = c.label.replace(/:\s*$/, "");
                  const cut = label.indexOf(": ");
                  const source = cut > 0 ? label.slice(0, cut) : label;
                  const terms = cut > 0 ? label.slice(cut + 2) : null;
                  return (
                    <li key={i} className="flex items-baseline justify-between gap-3 py-2">
                      <span className="min-w-0">
                        <span className="block font-bold text-ink">{source}</span>
                        {terms ? (
                          <span className="block truncate text-xs text-ink-3" title={terms}>
                            {terms}
                          </span>
                        ) : null}
                      </span>
                      <span className="shrink-0 font-bold tabular-nums text-ink">{c.display ?? ""}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
          {a.cheaper_option ? (
            <p className="text-ink-2" data-testid="next-action-cheaper">
              {t("biz.cheaper", { cost: a.cheaper_option.cost_total_display, n: a.cheaper_option.approvals })}
            </p>
          ) : null}
          {/* Why, in one sentence; the reasoning, the formula, each part's arrival and the cost's assumptions fold under it. */}
          <div data-testid="next-action-why">
            <p className="text-xs font-bold uppercase tracking-wide text-ink-3">{t("biz.why")}</p>
            <p className="mt-1 text-ink">{a.why}</p>
            <Disclosure summary={t("biz.calculation")} className="mt-1" testId="next-action-calc-fold">
              <div className="space-y-2 text-ink-2" data-testid="next-action-calc">
                <p>{a.detail}</p>
                <p data-testid="next-action-operation">{a.title}</p>
                {a.formula ? <Formula>{a.formula}</Formula> : null}
                <ul className="space-y-1">
                  {a.legs.map((leg) => (
                    <li key={leg.index} className="flex flex-wrap items-baseline justify-between gap-2 rounded-tile border border-line px-3 py-1.5">
                      <span>{leg.label}</span>
                      <span className="text-xs text-ink-3">
                        {leg.cost_display ? t("alerts.cost", { cost: leg.cost_display }) : t("biz.noStatedCost")}
                        {leg.lands_day !== null ? ` · ${t("biz.landsShort", { when: leg.lands_when ?? "" })}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
                {a.cost_basis ? (
                  <p className="text-xs text-ink-3" data-testid="next-action-cost-basis">{a.cost_basis}</p>
                ) : null}
              </div>
            </Disclosure>
          </div>
        </div>
      </Disclosure>
    </section>
  );
}
