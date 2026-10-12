"use client";

import Link from "next/link";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { ActionGroup } from "@/components/ui/action-group";
import { DecisionHighlight, HealthBand } from "@/components/ui/decision-highlight";
import { Button, ButtonLink, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeNextAction, HomeV2Action } from "@/lib/types";

/** The facts of the recommendation: the server's `facts` (label and value); until it sends them the one sentence is the line under the title. */
function factsOf(a: HomeV2Action) {
  return a.facts?.length ? a.facts : undefined;
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
  onBack,
}: {
  action: HomeV2Action;
  nextAction: HomeNextAction | null;
  stateVersion: number;
  fixer: ReturnType<typeof useFixAlert>;
  /** The Home read's note under its headline (the server's sentence about the cash), the recommendation's one line. */
  line?: string | null;
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
  return (
    <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="action" className="outline-none">
      <div data-testid={run ? "home-next-action" : "home-attention-card"} data-alert={run?.alert_id}>
        <DecisionHighlight eyebrow={run ? t("hv2.action.eyebrow") : action.eyebrow} title={action.title} line={facts ? line : action.text} facts={facts} testId="hv2-action" labelId="hv2-action-title">
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
