"use client";

import Link from "next/link";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { Button, ButtonLink, Card, DecisionCard, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeNextAction, HomeTone, HomeV2Action } from "@/lib/types";

const EYEBROW: Record<HomeTone, string> = { ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg", neutral: "text-ink-3" };

/** The words of the action, in the server's sentences: its eyebrow, its title, its one sentence. */
function Words({ a }: { a: HomeV2Action }) {
  return (
    <div className="min-w-0 flex-1 basis-72 space-y-1">
      <p className={`text-meta font-extrabold tracking-[0.08em] ${EYEBROW[a.tone]}`} data-testid="home-action-eyebrow">
        {a.eyebrow}
      </p>
      <h2 className="type-card-title text-pretty text-ink" data-testid="home-action-title">
        {a.title}
      </h2>
      <p className="text-pretty text-body text-ink-2" data-testid="home-action-text">
        {a.text}
      </p>
    </div>
  );
}

/** The plan's own confirm-and-run control (the same ids as the older Home): the one filled primary, "Compare" beside it, the confirmation under the row. */
function PlanControls({ a, run, stateVersion, fixer }: { a: HomeV2Action; run: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert> }) {
  const { primary, panel } = usePlanRun(run, stateVersion, fixer);
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 max-sm:w-full max-sm:[&>a]:w-full max-sm:[&>button]:w-full" data-testid="home-attention-run">
        {primary}
        {a.secondary ? (
          <ButtonLink href={a.secondary.href} data-testid="next-action-alternatives">
            {a.secondary.label}
          </ButtonLink>
        ) : null}
      </div>
      {panel ? <div className="basis-full">{panel}</div> : null}
    </>
  );
}

/**
 * The action bar: the company's one next action, in one line (eyebrow, title, one sentence) and, when the server says the plan can be run or approved from here,
 * the confirm-and-run control as the page's one filled primary with "Compare" beside it. This is the page's one `DecisionCard`. Without a control the bar has no filled
 * button: an action with only a way to look (the options) is a secondary link, and the quiet variant ("nothing needs you from the company side") is an unraised card.
 * The scroll target of the worklist's alert ("Run or compare"): `id="home-v2-action"`.
 */
export function HomeV2ActionBar({ action, nextAction, stateVersion, fixer, onBack }: { action: HomeV2Action; nextAction: HomeNextAction | null; stateVersion: number; fixer: ReturnType<typeof useFixAlert>; onBack?: () => void }) {
  const { t } = useI18n();
  // While a customer or a decision is selected the company's warning stays on the page, in its quiet variant (an unraised card, no filled button; the selection's own
  // action, if it has one, is the page's primary) with the way back to the action.
  if (onBack && action.variant === "ACTION") {
    return (
      <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="held" className="outline-none">
        <Card tone={action.tone === "bad" ? "bad" : action.tone === "warn" ? "warn" : undefined}>
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
            <div className="min-w-0 flex-1 basis-72 space-y-1">
              <p className={`text-meta font-extrabold tracking-[0.08em] ${EYEBROW[action.tone]}`}>{action.eyebrow}</p>
              <p className="type-card-title text-pretty text-ink" data-testid="home-action-title">
                {action.title}
              </p>
            </div>
            <Button onClick={onBack} className="max-sm:w-full" data-testid="home-action-back">
              {t("hv2.focus.back")}
            </Button>
          </div>
        </Card>
      </div>
    );
  }
  if (action.variant === "QUIET") {
    return (
      <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="quiet" className="outline-none">
        <Card>
          <Words a={action} />
        </Card>
      </div>
    );
  }
  const run = action.control && nextAction ? nextAction : null;
  return (
    <div id="home-v2-action" tabIndex={-1} data-testid="home-v2-action" data-variant="action" className="outline-none">
      <DecisionCard className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 p-5 max-sm:p-4" data-testid={run ? "home-next-action" : "home-attention-card"} data-alert={run?.alert_id}>
        <Words a={action} />
        {run ? (
          <PlanControls a={action} run={run} stateVersion={stateVersion} fixer={fixer} />
        ) : action.primary || action.secondary ? (
          <div className="flex flex-wrap items-center gap-2 max-sm:w-full max-sm:[&>a]:w-full">
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
          </div>
        ) : null}
      </DecisionCard>
    </div>
  );
}
