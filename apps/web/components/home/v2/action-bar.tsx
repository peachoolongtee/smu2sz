"use client";

import Link from "next/link";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { ActionGroup } from "@/components/ui/action-group";
import { FundingTimeline } from "@/components/home/v2/funding-timeline";
import { AlertIcon, CheckIcon } from "@/components/icons";
import { DecisionHighlight, HealthBand } from "@/components/ui/decision-highlight";
import { Button, ButtonLink, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeNextAction, HomeV2Action } from "@/lib/types";

/** The facts of the recommendation: the server's `facts` (label and value); until it sends them the one sentence is the line under the title. */
function factsOf(a: HomeV2Action) {
  return a.facts?.length ? a.facts : undefined;
}

/**
 * The recommendation's three facts are the server's, in its order: the cost to the owner, the funding, who approves. The cost is the hero figure; the funding is the timeline of the
 * plan's legs when the server sends them (else the sentence it already wrote); who approves is one quiet line under the actions, with a check, or in the warn tone when the owner must
 * approve. Any other set of facts keeps the plain row.
 */
function shape(a: HomeV2Action, total: string, needsOwner: boolean) {
  const f = a.facts;
  if (!f || f.length !== 3) return { facts: f };
  const [cost, funding, approval] = f;
  const legs = a.legs?.length ? a.legs : null;
  return {
    hero: { label: "", value: cost.value, key: cost.label },
    middle: legs ? <FundingTimeline legs={legs} total={total} /> : (
      <div data-testid="hv2-funding-text">
        <p className="text-supporting text-ink-3">{funding.label}</p>
        <p className="mt-1 text-supporting font-bold text-ink sm:text-sm">{funding.value}</p>
      </div>
    ),
    note: (
      <p className={`flex items-center gap-1.5 ${needsOwner ? "font-semibold text-warn-fg" : ""}`} data-testid="hv2-approval">
        {needsOwner ? <AlertIcon className="size-3.5 shrink-0 text-warn-solid" /> : <CheckIcon className="size-3.5 shrink-0 text-ok-solid" />}
        {approval.value}
      </p>
    ),
  };
}

/** The plan's own confirm-and-run control (the same ids as the older Home): the page's one filled button, "Compare funding options" an outline button beside it, the confirmation under the row. */
function PlanControls({ a, run, stateVersion, fixer }: { a: HomeV2Action; run: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert> }) {
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
      </ActionGroup>
      {panel ? <div className="mt-3">{panel}</div> : null}
    </>
  );
}

/**
 * The recommendation (`DecisionHighlight`): "FLOW recommends", the server's title, one line, the server's facts (Estimated cost, Funding, Approval) and then the plan's
 * confirm-and-run control as the page's one filled button with "Compare funding options" outlined beside it. Without a control there is no filled button: an action with only a
 * way to look (the options) is an outline button and a quiet link, and the quiet variant ("nothing needs you from the company side") is the same block with no buttons.
 * While a customer or a deal is selected it is the health band instead: one row, the company's sentence and cost, and an OUTLINED "Review funding plan" that returns to it.
 * `id="home-v2-action"` is the scroll target of the worklist's alert.
 */
export function HomeV2ActionBar({
  action,
  nextAction,
  stateVersion,
  fixer,
  line,
  fundingTotal,
  onBack,
}: {
  action: HomeV2Action;
  nextAction: HomeNextAction | null;
  stateVersion: number;
  fixer: ReturnType<typeof useFixAlert>;
  /** The Home read's note under its headline (the server's sentence about the cash), the recommendation's one line. */
  line?: string | null;
  /** The funding plan's total, the timeline's right end (the strip's own funding figure). */
  fundingTotal?: string;
  onBack?: () => void;
}) {
  const { t } = useI18n();
  if (onBack && action.variant === "ACTION") {
    return (
      <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="held" className="outline-none">
        <HealthBand label={t("hv2.band.label")} sentence={action.title} fact={action.facts?.[0] ?? null} testId="hv2-band">
          <Button onClick={onBack} data-testid="home-action-back">
            {t("hv2.band.review")}
          </Button>
        </HealthBand>
      </div>
    );
  }
  if (action.variant === "QUIET") {
    return (
      <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="quiet" className="outline-none">
        <DecisionHighlight eyebrow={action.eyebrow} title={action.title} line={action.text} testId="hv2-action" labelId="hv2-action-title" />
      </div>
    );
  }
  const run = action.control && nextAction ? nextAction : null;
  const facts = factsOf(action);
  const shaped = shape(action, fundingTotal ?? "", Boolean(nextAction?.needs_owner));
  return (
    <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="action" className="outline-none">
      <div data-testid={run ? "home-next-action" : "home-attention-card"} data-alert={run?.alert_id}>
        <DecisionHighlight eyebrow={run ? t("hv2.action.eyebrow") : action.eyebrow} title={action.title} line={facts ? line : action.text} facts={shaped.facts} hero={shaped.hero ? { label: t("hv2.action.cost"), value: shaped.hero.value } : undefined} middle={shaped.middle} stackMiddle={Boolean(action.legs?.length)} note={shaped.note} testId="hv2-action" labelId="hv2-action-title">
          {run ? (
            <PlanControls a={action} run={run} stateVersion={stateVersion} fixer={fixer} />
          ) : action.primary || action.secondary ? (
            <ActionGroup>
              {action.primary ? (
                <ButtonLink href={action.primary.href} data-testid="home-action-primary">
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
        </DecisionHighlight>
      </div>
    </div>
  );
}
