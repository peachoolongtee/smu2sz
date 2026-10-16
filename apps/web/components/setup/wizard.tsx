"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BankIcon } from "@/components/icons";
import { Button, ButtonLink, Callout, PageHeader } from "@/components/ui";
import { previewSetup } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { ensureStartDate, useSetupDraft, useSetupStatus } from "@/lib/setup-draft";
import type { SetupIssue } from "@/lib/types";
import type { Issues } from "./fields";
import { StepCustomers } from "./step-customers";
import { StepReview } from "./step-review";
import { StepBills, StepBusiness, StepFunding, StepLimits } from "./steps";
import { SetupWelcome } from "./welcome";

const STEPS = [1, 2, 3, 4, 5, 6] as const;

/**
 * Set up your books (ADR-0013): the welcome (no `step`), then six steps in the URL (`/setup?step=3`). "Next" asks the server to check
 * the draft and moves on only when the step it leaves has nothing to fix; the review checks everything again. The draft lives in this
 * browser until the owner signs and opens the books.
 */
export function SetupWizard() {
  const { t, lang } = useI18n();
  const params = useSearchParams();
  const router = useRouter();
  const { draft } = useSetupDraft();
  const { status } = useSetupStatus();
  const raw = Number(params.get("step"));
  const step = STEPS.includes(raw as (typeof STEPS)[number]) ? raw : 0;
  const [issues, setIssues] = useState<SetupIssue[]>([]);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);

  useEffect(() => {
    if (step > 0) ensureStartDate();
  }, [step]);

  const goTo = (n: number) => {
    setIssues([]);
    setCheckError(null);
    router.push(`/setup?step=${n}`);
    if (typeof window !== "undefined") window.scrollTo({ top: 0 });
  };

  async function next() {
    setChecking(true);
    setCheckError(null);
    try {
      const p = await previewSetup(draft, lang);
      const mine = p.errors.filter((e) => e.step === step);
      setIssues(mine);
      if (mine.length === 0) goTo(step + 1);
    } catch (e) {
      setCheckError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  }

  if (step === 0) return <SetupWelcome />;

  const byPath: Issues = Object.fromEntries(issues.map((i) => [i.path, i.text]));
  const name = (n: number) => t(`setup.step.${n}` as DictKey);
  return (
    <div data-testid="setup-wizard">
      <PageHeader
        section="home"
        icon={BankIcon}
        title={t("setup.title")}
        subtitle={t("setup.stepOf", { n: step })}
        actions={
          <ButtonLink href="/" size="sm" data-testid="setup-save-later">
            {t("setup.saveLater")}
          </ButtonLink>
        }
      />
      <div className="flex flex-wrap items-start gap-6">
        <nav aria-label={t("setup.steps")} className="w-full lg:w-56">
          <ol className="flex gap-1 overflow-x-auto lg:flex-col">
            {STEPS.map((n) => (
              <li key={n} className="shrink-0">
                <button
                  type="button"
                  onClick={() => goTo(n)}
                  aria-current={n === step ? "step" : undefined}
                  aria-label={n < step ? t("setup.step.done", { name: `${n} · ${name(n)}` }) : undefined}
                  className={`motion-press flex min-h-10 w-full items-center gap-2 whitespace-nowrap rounded-control px-3 text-left text-sm ${
                    n === step ? "bg-ink font-bold text-white" : n < step ? "font-medium text-ink hover:bg-subtle" : "text-ink-3 hover:bg-subtle"
                  }`}
                >
                  <span aria-hidden className="w-4 text-center">{n < step ? "✓" : n}</span>
                  {name(n)}
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <div className="min-w-0 flex-[999_1_560px] space-y-6">
          {issues.length ? (
            <Callout tone="bad" title={t("setup.fixFirst")}>
              <ul className="mt-1 list-disc space-y-1 pl-5" data-testid="setup-step-issues">
                {issues.map((i, k) => (
                  <li key={k}>{i.text}</li>
                ))}
              </ul>
            </Callout>
          ) : null}
          {checkError ? <Callout tone="bad">{checkError}</Callout> : null}
          {step === 1 ? <StepBusiness draft={draft} issues={byPath} /> : null}
          {step === 2 ? <StepFunding draft={draft} issues={byPath} /> : null}
          {step === 3 ? <StepCustomers draft={draft} issues={byPath} initialPick={params.get("pick") === "1"} /> : null}
          {step === 4 ? <StepBills draft={draft} issues={byPath} /> : null}
          {step === 5 ? <StepLimits draft={draft} issues={byPath} /> : null}
          {step === 6 ? <StepReview draft={draft} status={status} goTo={goTo} /> : null}
          <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
            <span className="grow" />
            <Button onClick={() => (step === 1 ? router.push("/setup") : goTo(step - 1))} data-testid="setup-back">
              {t("setup.back")}
            </Button>
            {step < 6 ? (
              <Button variant="primary" onClick={next} loading={checking} data-testid="setup-next">
                {checking ? t("setup.checking") : t("setup.next", { name: name(step + 1) })}
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
