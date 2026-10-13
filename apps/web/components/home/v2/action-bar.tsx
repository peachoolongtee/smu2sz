"use client";

import Link from "next/link";
import { useId } from "react";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { SegmentedBar } from "@/components/home/v2/segmented-bar";
import { AlertIcon, CheckIcon } from "@/components/icons";
import { Button, ButtonLink, textLinkClass } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { StatusPill } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { HomeNextAction, HomeV2, HomeV2Action } from "@/lib/types";

/** The facts of the recommendation: the server's `facts` (label and value); until it sends them the one sentence is the line under the title. */
function factsOf(a: HomeV2Action) {
  return a.facts?.length ? a.facts : undefined;
}

/** The plan's own confirm-and-run control (the ids `fix-open-*`, `fix-*` and `fix-cancel-*`): the card's one filled button, "Compare funding options" an outline button beside it, the confirmation under the row. */
function PlanControls({ a, run, stateVersion, fixer }: { a: HomeV2Action; run: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert> }) {
  const { t } = useI18n();
  const { primary, panel } = usePlanRun(run, stateVersion, fixer);
  return (
    <>
      <ActionGroup testId="home-attention-run" className="[&>*]:min-h-9">
        {primary}
        {a.secondary ? (
          <ButtonLink href={a.secondary.href} data-testid="next-action-alternatives">
            {t("hv2.action.compare")}
          </ButtonLink>
        ) : null}
      </ActionGroup>
      {panel ? <div className="mt-3">{panel}</div> : null}
    </>
  );
}

/**
 * "What we recommend", the mockup's middle card (`f-card`, a flex column): the title with the planned pill, the server's title, the planned amount as the figure, the consequence said whole, the cost to
 * the owner, the funding legs inline as a stacked bar in the gap, one 13 px approval line (the server's `approval_text` and `approval_needed`: the tick form, the warn form, none for null) and the
 * actions pinned to the bottom (the plan's confirm-and-run control is the page's one filled button, "Compare funding options" outlined). Quiet variant: the same card with no buttons. While a customer or a deal is selected it is the one-row band instead: the company's
 * cash and minimum reserve and an OUTLINED "Review funding plan" that returns to it. `id="home-v2-action"` is the scroll target of the worklist's alert.
 */
export function HomeV2ActionBar({
  action,
  kpis,
  nextAction,
  stateVersion,
  fixer,
  line: lineProp,
  fundingTotal,
  onBack,
}: {
  action: HomeV2Action;
  kpis: HomeV2["kpis"];
  nextAction: HomeNextAction | null;
  stateVersion: number;
  fixer: ReturnType<typeof useFixAlert>;
  /** The Home read's note under its headline (the server's sentence about the cash), the recommendation's one line. */
  line?: string | null;
  /** The funding plan's total (the strip's own funding figure). */
  fundingTotal?: string;
  onBack?: () => void;
}) {
  const { t } = useI18n();
  const uid = useId();
  const planned = kpis.funding.state === "PROPOSED";
  // The planned or arranged amount is the figure only when the action carries one: with no funding (state NONE: a facility application, say) the server's word for it ("None") is not an amount, and the title already says what is asked.
  const amount = kpis.funding.state !== "NONE" && kpis.funding.value_display ? kpis.funding.value_display : null;
  if (onBack && action.variant === "ACTION") {
    const cash = kpis.cash_available;
    return (
      <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="held" className="outline-none">
        <section aria-label={t("hv2.band.label")} data-testid="hv2-band" className="motion-reveal f-card flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2.5">
          <p className="min-w-0 text-sm text-ink-3">
            <span className="text-ink">
              {t("hv2.band.cash")} <b className="font-bold tabular-nums">{cash.value_display}</b>
            </span>
            <span className="ml-4">
              {t("hv2.band.reserve")} <span className="tabular-nums">{cash.buffer.min_display}</span>
            </span>
            <span className="sr-only" data-testid="home-action-title">
              {action.title}
            </span>
          </p>
          <Button onClick={onBack} data-testid="home-action-back">
            {kpis.funding.state !== "NONE" && kpis.funding.value_display ? t("hv2.band.reviewAmount", { amount: kpis.funding.value_display }) : t("hv2.band.review")}
          </Button>
        </section>
      </div>
    );
  }
  const quiet = action.variant === "QUIET";
  const run = !quiet && action.control && nextAction ? nextAction : null;
  const facts = factsOf(action);
  const cost = facts?.length === 3 ? facts[0] : null;
  const legs = action.legs?.length ? action.legs : null;
  // The approval line is the server's two fields: `approval_text` (null: no line) and `approval_needed` (true: the warn form, false: the tick form).
  const approvalText = action.approval_text ?? null;
  const needsOwner = approvalText !== null && action.approval_needed === true;
  const titleId = `${uid}-title`;
  const line = action.consequence_text ?? (facts ? lineProp : action.text);
  const total = fundingTotal && kpis.funding.state !== "NONE" ? fundingTotal : undefined;
  return (
    <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant={quiet ? "quiet" : "action"} className="h-full outline-none">
      <div data-testid={run ? "home-next-action" : quiet ? undefined : "home-attention-card"} data-alert={run?.alert_id} className="h-full">
        <section aria-labelledby={titleId} data-testid="hv2-action" className="motion-reveal f-card flex h-full min-w-0 flex-col p-4">
          <div className="flex items-start justify-between gap-3">
            <h2 id={titleId} className="font-display text-[16px] font-bold leading-tight tracking-[-0.01em] text-ink" data-testid="home-action-eyebrow">
              {quiet ? action.eyebrow : t("hv2.action.eyebrow")}
            </h2>
            {planned && !quiet ? (
              <StatusPill tone="lavender" testId="hv2-plan-pill" className="!min-h-5 py-0">
                {t("home.hy.planned")}
              </StatusPill>
            ) : null}
          </div>
          <p className="mt-1 line-clamp-1 text-pretty font-display text-[16px] font-semibold leading-snug tracking-[-0.01em] text-ink sm:text-[18px]" data-testid="home-action-title">
            {action.title}
          </p>
          {/* The planned amount is the figure, with the cost to the owner (the bold fact) at its right on the same line. */}
          {amount || cost?.value ? (
            <div className="mt-0.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
              {amount ? (
                <p className="font-display text-[32px] font-bold leading-none tracking-[-0.03em] tabular-nums text-ink sm:text-[36px]" data-testid="home-kpi-funding-value">
                  <span data-testid="hv2-plan-amount">{amount}</span>
                </p>
              ) : null}
              {cost?.value ? (
                <p className="text-sm text-ink" data-testid="hv2-action-facts">
                  <span className="text-ink-3">{t("hv2.action.cost")}</span>{" "}
                  <b className="font-bold tabular-nums" title={action.cost_basis_text ?? undefined} data-testid="hv2-hero-value">
                    {cost.value}
                  </b>
                </p>
              ) : null}
            </div>
          ) : null}
          {amount && kpis.funding.state === "ARRANGED" && kpis.funding.status_text ? (
            <p className="mt-1 text-sm font-medium text-ink-2" data-testid="home-kpi-funding-status">
              {kpis.funding.status_text}
            </p>
          ) : null}
          {/* The consequence is said whole (two lines at most in practice), never cut. */}
          {line ? (
            <p className="mt-1.5 max-w-3xl text-pretty text-sm text-ink-3 max-sm:hidden" data-testid="home-action-text">
              {line}
            </p>
          ) : null}
          {/* The gap between the facts and the buttons is the plan, inline: the legs as one thin stacked bar (widths from the legs' amounts, the server's labels, amounts, `lands_when` and shares, the total at the
              right end); a single leg is one full bar; with no legs the server's cost basis alone. Hover or focus on a segment opens the leg's own card. */}
          <div className="my-auto py-0.5" data-testid="hv2-funding-row">
            {legs ? (
              <SegmentedBar
                testId="hv2-funding"
                total={total}
                segments={legs.map((l) => ({
                  label: l.label,
                  amount_display: l.amount_display,
                  share_text: l.share_text ?? null,
                  meta: l.lands_when,
                  weight: l.amount_fen && l.amount_fen > 0 ? l.amount_fen : legs.every((x) => !x.amount_fen) ? 1 : null,
                  detail: (
                    <span className="block space-y-0.5" data-testid="hv2-leg-card">
                      <b className="block font-semibold">{l.label}</b>
                      <span className="block tabular-nums">
                        {l.amount_display} · {l.lands_when}
                      </span>
                      <span className="block text-ink-2">{l.state_text}</span>
                      {l.cost_display ? (
                        <span className="block text-ink-2">
                          {t("hv2.leg.cost")} {l.cost_display}
                          {l.repaid_when ? ` · ${t("hv2.leg.repaid")} ${l.repaid_when}` : ""}
                        </span>
                      ) : null}
                      {l.authority_text ? <span className="block text-ink-2">{l.authority_text}</span> : null}
                    </span>
                  ),
                }))}
              />
            ) : action.cost_basis_text ? (
              <p className="text-supporting text-ink-3" data-testid="hv2-cost-basis">
                {action.cost_basis_text}
              </p>
            ) : null}
          </div>
          {approvalText ? (
            <p className={`mb-1.5 flex items-center gap-1.5 text-supporting ${needsOwner ? "font-semibold text-warn-fg" : "text-ink-2"}`} data-testid="hv2-approval" data-needs-owner={needsOwner}>
              {needsOwner ? <AlertIcon className="size-3.5 shrink-0 text-warn-solid" /> : <CheckIcon className="size-3.5 shrink-0 text-ok-solid" />}
              {approvalText}
            </p>
          ) : null}
          {!quiet ? (
            <div className="mt-auto" data-testid="hv2-action-buttons">
              {run ? (
                <PlanControls a={action} run={run} stateVersion={stateVersion} fixer={fixer} />
              ) : action.primary || action.secondary ? (
                <ActionGroup>
                  {action.primary ? (
                    <ButtonLink href={action.primary.href} variant="primary" data-testid="home-action-primary">
                      {action.primary.label}
                    </ButtonLink>
                  ) : null}
                  {action.secondary ? (
                    <Link href={action.secondary.href} className={`${textLinkClass} text-sm font-bold`} data-testid="home-action-secondary">
                      {action.secondary.label}
                    </Link>
                  ) : null}
                </ActionGroup>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
