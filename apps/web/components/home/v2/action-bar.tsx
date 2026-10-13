"use client";

import Link from "next/link";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { ActionGroup } from "@/components/ui/action-group";
import { FundingComposition, FundingFact, useFunding } from "@/components/home/v2/funding-composition";
import { AlertIcon, CheckIcon } from "@/components/icons";
import { DecisionHighlight, HealthBand } from "@/components/ui/decision-highlight";
import { Button, ButtonLink, textLinkClass } from "@/components/ui";
import { useId } from "react";
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
 * The recommendation (`DecisionHighlight`): "What we recommend", the server's title, one line, the cost and the funding facts and then the plan's
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
  fundingOpen,
  onFunding,
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
  /** `?funding=1`: the funding composition is open (and stays open); pressing the funding fact writes it. */
  fundingOpen?: boolean;
  onFunding?: (on: boolean) => void;
  onBack?: () => void;
}) {
  const { t } = useI18n();
  const uid = useId();
  const funding = useFunding(Boolean(fundingOpen), onFunding ?? (() => undefined));
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
  // The card is compact: the title, one line that reconciles with the strip (the server's `consequence_text`; until it sends it, the Home read's note), the three facts in one row
  // (the cost to the owner as the hero figure, the funding timing) and the actions. The funding timing carries the composition of the plan (hover or focus, a tap, `?funding=1`).
  // Who approves is one 13 px line under the actions, in both forms: the check glyph and the server's sentence in the quiet ink, or the warn glyph and the sentence in the warn tone when the owner must approve.
  const three = facts?.length === 3 ? facts : null;
  const legs = action.legs?.length ? action.legs : null;
  const needsOwner = Boolean(nextAction?.needs_owner);
  return (
    <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="action" className="outline-none">
      <div data-testid={run ? "home-next-action" : "home-attention-card"} data-alert={run?.alert_id}>
        <DecisionHighlight
          eyebrow={run ? t("hv2.action.eyebrow") : action.eyebrow}
          title={action.title}
          line={action.consequence_text ?? (facts ? line : action.text)}
          facts={three ? undefined : facts}
          hero={three ? { label: t("hv2.action.cost"), value: three[0].value, basis: action.cost_basis_text ?? null } : undefined}
          middle={
            three ? (
              <FundingFact label={three[1].label} value={three[1].value} open={funding.open} id={`${uid}-fact`} controls={`${uid}-comp`} toggle={funding.toggle} pointer={funding.pointer} focus={funding.focus} hasLegs={Boolean(legs)} />
            ) : undefined
          }
          below={three && legs && funding.open ? <FundingComposition legs={legs} total={fundingTotal ?? ""} id={`${uid}-comp`} labelledBy={`${uid}-fact`} basis={action.cost_basis_text} pointer={funding.pointer} /> : undefined}
          note={
            three ? (
              <p className={`flex items-center gap-1.5 ${needsOwner ? "font-semibold text-warn-fg" : ""}`} data-testid="hv2-approval" data-needs-owner={needsOwner}>
                {needsOwner ? <AlertIcon className="size-3.5 shrink-0 text-warn-solid" /> : <CheckIcon className="size-3.5 shrink-0 text-ok-solid" />}
                {three[2].value}
              </p>
            ) : undefined
          }
          testId="hv2-action"
          labelId="hv2-action-title"
        >
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
