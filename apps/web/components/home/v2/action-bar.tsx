"use client";

import Link from "next/link";
import { useId } from "react";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { FundingComposition, FundingFact, useFunding } from "@/components/home/v2/funding-composition";
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
function PlanControls({ a, run, stateVersion, fixer, funding }: { a: HomeV2Action; run: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert>; funding?: React.ReactNode }) {
  const { t } = useI18n();
  const { primary, panel } = usePlanRun(run, stateVersion, fixer);
  return (
    <>
      <ActionGroup testId="home-attention-run">
        {primary}
        {a.secondary ? (
          <ButtonLink href={a.secondary.href} data-testid="next-action-alternatives">
            {t("hv2.action.compare")}
          </ButtonLink>
        ) : null}
        {funding}
      </ActionGroup>
      {panel ? <div className="mt-3">{panel}</div> : null}
    </>
  );
}

/**
 * "What we recommend", the mockup's middle card (`f-card`): the title with the planned pill, the server's title, the planned amount as the figure, one line of the cost to the owner with
 * its basis, and the actions (the plan's confirm-and-run control is the page's one filled button, "Compare funding options" outlined, "Funding sources" the disclosure of how the plan is
 * made up: on the pointer, on keyboard focus, on a tap and from `?funding=1`). Under the actions is one 13 px approval line bound to the server's `approval_text` and `approval_needed`
 * (the tick form, the warn form, none for null). Quiet variant: the same card with no buttons. While a customer or a deal is selected it is the one-row band instead: the company's
 * cash and minimum reserve and an OUTLINED "Review funding plan" that returns to it. `id="home-v2-action"` is the scroll target of the worklist's alert.
 */
export function HomeV2ActionBar({
  action,
  kpis,
  nextAction,
  stateVersion,
  fixer,
  line,
  fundingTotal,
  fundingOpen,
  onFunding,
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
  /** `?funding=1`: the funding composition is open (and stays open); pressing the toggle writes it. */
  fundingOpen?: boolean;
  onFunding?: (on: boolean) => void;
  onBack?: () => void;
}) {
  const { t } = useI18n();
  const uid = useId();
  const funding = useFunding(Boolean(fundingOpen), onFunding ?? (() => undefined));
  const planned = kpis.funding.state === "PROPOSED";
  // The planned or arranged amount is the figure only when the action carries one: with no funding (state NONE: a facility application, say) the server's word for it ("None") is not an amount, and the title already says what is asked.
  const amount = kpis.funding.state !== "NONE" && kpis.funding.value_display ? kpis.funding.value_display : null;
  if (onBack && action.variant === "ACTION") {
    const cash = kpis.cash_available;
    return (
      <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="held" className="outline-none">
        <section aria-label={t("hv2.band.label")} data-testid="hv2-band" className="motion-reveal f-card flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 py-4">
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
            {t("hv2.band.review")}
          </Button>
        </section>
      </div>
    );
  }
  const quiet = action.variant === "QUIET";
  const run = !quiet && action.control && nextAction ? nextAction : null;
  const facts = factsOf(action);
  const cost = facts?.length === 3 ? facts[0] : null;
  const fundingFact = facts?.length === 3 ? facts[1] : null;
  const legs = action.legs?.length ? action.legs : null;
  // The approval line is the server's two fields: `approval_text` (null: no line) and `approval_needed` (true: the warn form, false: the tick form).
  const approvalText = action.approval_text ?? null;
  const needsOwner = approvalText !== null && action.approval_needed === true;
  const titleId = `${uid}-title`;
  return (
    <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant={quiet ? "quiet" : "action"} className="outline-none">
      <div data-testid={run ? "home-next-action" : quiet ? undefined : "home-attention-card"} data-alert={run?.alert_id} className="h-full">
        <section aria-labelledby={titleId} data-testid="hv2-action" className="motion-reveal f-card flex h-full min-w-0 flex-col p-4 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <h2 id={titleId} className="font-display text-[20px] font-bold leading-tight tracking-[-0.01em] text-ink" data-testid="home-action-eyebrow">
              {run ? t("hv2.action.eyebrow") : quiet ? action.eyebrow : t("hv2.action.eyebrow")}
            </h2>
            {planned && !quiet ? (
              <StatusPill tone="lavender" testId="hv2-plan-pill" className="first-letter:uppercase">
                {t("home.hy.planned")}
              </StatusPill>
            ) : null}
          </div>
          <p className="mt-2.5 text-pretty font-display text-[18px] font-semibold leading-snug tracking-[-0.01em] text-ink sm:mt-4 sm:text-[21px]" data-testid="home-action-title">
            {action.title}
          </p>
          {amount ? (
            <>
              <p className="mt-2 font-display text-[36px] font-bold leading-none tracking-[-0.03em] tabular-nums text-ink sm:text-[52px]" data-testid="home-kpi-funding-value">
                <span data-testid="hv2-plan-amount">{amount}</span>
              </p>
              {kpis.funding.state === "ARRANGED" && kpis.funding.status_text ? (
                <p className="mt-1.5 text-sm font-medium text-ink-2" data-testid="home-kpi-funding-status">
                  {kpis.funding.status_text}
                </p>
              ) : null}
              {kpis.funding.hint ? (
                <p className="mt-1.5 text-supporting text-ink-3" data-testid="hv2-funding-hint">
                  {kpis.funding.hint}
                </p>
              ) : null}
            </>
          ) : null}
          {(action.consequence_text ?? (facts ? line : action.text)) ? (
            <p className="mt-3 max-w-3xl text-pretty text-sm text-ink-2 max-sm:hidden" data-testid="home-action-text">
              {action.consequence_text ?? (facts ? line : action.text)}
            </p>
          ) : null}
          {cost?.value ? (
            <div className="mt-3 border-t border-line pt-2.5 text-sm text-ink sm:mt-4 sm:pt-3" data-testid="hv2-action-facts">
              <p>
                <span className="text-ink-3">{t("hv2.action.cost")}</span>{" "}
                <b className="font-bold tabular-nums" title={action.cost_basis_text ?? undefined} data-testid="hv2-hero-value">
                  {cost.value}
                </b>
              </p>
            </div>
          ) : null}
          {!quiet ? (
            <div className="mt-3 sm:mt-4">
              {run ? (
                <PlanControls
                  a={action}
                  run={run}
                  stateVersion={stateVersion}
                  fixer={fixer}
                  funding={
                    fundingFact ? (
                      <FundingFact label={fundingFact.label} value={fundingFact.value} open={funding.open} id={`${uid}-fact`} controls={`${uid}-comp`} toggle={funding.toggle} pointer={funding.pointer} focus={funding.focus} hasLegs={Boolean(legs)} />
                    ) : null
                  }
                />
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
                  {fundingFact ? (
                    <FundingFact label={fundingFact.label} value={fundingFact.value} open={funding.open} id={`${uid}-fact`} controls={`${uid}-comp`} toggle={funding.toggle} pointer={funding.pointer} focus={funding.focus} hasLegs={Boolean(legs)} />
                  ) : null}
                </ActionGroup>
              ) : null}
            </div>
          ) : null}
          {approvalText ? (
            <p className={`mt-3 flex items-center gap-1.5 text-supporting ${needsOwner ? "font-semibold text-warn-fg" : "text-ink-2"}`} data-testid="hv2-approval" data-needs-owner={needsOwner}>
              {needsOwner ? <AlertIcon className="size-3.5 shrink-0 text-warn-solid" /> : <CheckIcon className="size-3.5 shrink-0 text-ok-solid" />}
              {approvalText}
            </p>
          ) : null}
          {legs && funding.open ? <FundingComposition legs={legs} total={fundingTotal && kpis.funding.state !== "NONE" ? fundingTotal : ""} id={`${uid}-comp`} labelledBy={`${uid}-fact`} basis={action.cost_basis_text} pointer={funding.pointer} /> : null}
        </section>
      </div>
    </div>
  );
}
