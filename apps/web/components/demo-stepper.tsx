"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { onSignedIn } from "@/lib/auth";
import { backStep, goToStep, resetDemo, type StepMode } from "@/lib/demo-control";
import { useDemo } from "@/lib/demo-store";
import { DEMO_STEPS, SCENES } from "@/lib/demo";
import { stepNarration } from "@/lib/demo-text";
import { useI18n } from "@/lib/i18n";
import { ArrowLeftIcon, ArrowRightIcon, ResetIcon } from "./icons";
import { Button, toggleClass } from "./ui";

/**
 * The guided story's control bar, Demo mode only: the six scenes of the late-payment loop, with reset. The step that is the owner's own
 * decision names what it approves on its button, and nothing here presses it for them.
 */
export function DemoStepper() {
  const i18n = useI18n();
  const { t, te } = i18n;
  const router = useRouter();
  const demo = useDemo();
  const step = demo.step;
  const current = step >= 0 ? DEMO_STEPS[step] : null;
  const last = DEMO_STEPS.length - 1;

  // The step a 401 interrupted: once the owner signs in from the dialog it opened, it runs by itself (as the chat resends its turn).
  const interrupted = useRef<number | null>(null);

  async function goTo(target: number, mode: StepMode = "run") {
    interrupted.current = null;
    const outcome = await goToStep(target, router.push, { mode });
    if (outcome === "unauthorized") interrupted.current = target;
  }

  useEffect(
    () =>
      onSignedIn(() => {
        const target = interrupted.current;
        if (target !== null) void goTo(target);
      }),
    // goTo only reads the demo store and the router, so the first render's copy is the one to keep.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const upcoming = DEMO_STEPS[step + 1] ?? null;
  const nextLabel = step < 0 ? t("demo.start") : upcoming?.owner ? (demo.cure?.amount ? t("demo.approve", { amount: demo.cure.amount }) : t("demo.approve.plain")) : t("demo.next");
  const narration = current ? stepNarration(i18n, current.id, demo) : "";

  return (
    <div className="border-t border-line bg-brand-50 px-4 py-2 lg:px-8" aria-label={t("demo.region")} role="region">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {/* The navy strip above the page already says DEMO on a phone, where the six scene buttons need the whole width. */}
          <span className="rounded-pill bg-brand-600 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-white max-sm:hidden">
            {t("demo.label")}
          </span>
          <ol className="flex flex-wrap items-center gap-1" aria-label={t("demo.scenes")}>
            {SCENES.map((s, n) => {
              const active = current?.scene === s.id;
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    // A scene that is already behind us is shown, never re-run; the next one starts; the ones after it wait their turn (the story moves time).
                    disabled={demo.busy || s.first > step + 1}
                    onClick={() => void goTo(s.first, s.first <= step ? "show" : "run")}
                    aria-current={active ? "step" : undefined}
                    title={t("demo.jump", { scene: te("scene", s.id) })}
                    className={toggleClass(active, "sm")}
                  >
                    {/* On a phone the six scenes are numbered pills (one row); the name is the tooltip and the accessible name. */}
                    <span aria-hidden className="sm:hidden">
                      {n + 1}
                    </span>
                    <span className="max-sm:sr-only">{te("scene.short", s.id)}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>

        <div className="min-w-0 flex-1 basis-56" aria-live="polite">
          {current ? (
            <>
              <p className="truncate text-sm font-semibold text-ink" data-testid="demo-step-title">
                <span className="mr-1.5 font-normal text-ink-3 tabular-nums">
                  {t("demo.progress", { n: step + 1, total: DEMO_STEPS.length })}
                </span>
                {te("demo.step", current.id)}
              </p>
              {/* What the server just told this step, in two lines at most; the full sentence is the tooltip and the story page's. */}
              <p className="line-clamp-2 text-xs text-ink-2" title={narration} data-testid="demo-step-narration">
                {narration}
              </p>
              {current.link ? (
                <Link href={current.link.route} className="mt-0.5 inline-block text-xs font-medium text-brand-700 underline underline-offset-2" data-testid="demo-step-link">
                  {t(current.link.label)}
                </Link>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-ink-2">{t("demo.idle")}</p>
          )}
          {/* A reload in the middle of a step leaves the books where the step stopped: say so, never unlock silently. */}
          {!demo.busy && demo.running !== null ? (
            <p className="mt-0.5 text-xs font-medium text-warn-fg" data-testid="demo-interrupted">
              {t("demo.interrupted", { n: demo.running + 1 })}
            </p>
          ) : null}
        </div>

        {/* Below sm the last 3rem of this row is Ask FLOW (chat-panel.tsx fixes it to the bar's corner). */}
        <div className="flex items-center gap-1.5 max-sm:mr-12">
          <Button size="sm" variant="ghost" onClick={() => backStep(router.push)} disabled={demo.busy || step <= 0} aria-label={t("demo.back")}>
            <ArrowLeftIcon />
            <span className="hidden sm:inline">{t("demo.back")}</span>
          </Button>
          <Button
            size="sm"
            variant="primary"
            loading={demo.busy}
            disabled={step >= last}
            onClick={() => void goTo(step + 1)}
            data-testid="demo-next"
          >
            {nextLabel}
            <ArrowRightIcon />
          </Button>
          <Button size="sm" variant="secondary" onClick={() => void resetDemo(router.push)} disabled={demo.busy} data-testid="demo-reset">
            <ResetIcon />
            {t("demo.reset")}
          </Button>
        </div>
      </div>
      {demo.error ? (
        <p role="alert" className="mt-1.5 rounded-tile max-sm:mr-12 border border-bad-line bg-bad-bg px-2.5 py-1.5 text-xs text-bad-fg">
          {demo.error}
        </p>
      ) : null}
    </div>
  );
}
