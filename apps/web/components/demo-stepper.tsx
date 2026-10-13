"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { onSignedIn } from "@/lib/auth";
import { getDemoStory } from "@/lib/api";
import { resumeStoryAction, runStoryAction, seenOf } from "@/lib/demo-control";
import { DEMO_STEPS } from "@/lib/demo";
import { reachedOf, useDemo } from "@/lib/demo-store";
import { stepNarration } from "@/lib/demo-text";
import { useI18n } from "@/lib/i18n";
import type { DemoStoryView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { ArrowRightIcon } from "./icons";
import { Button, ButtonLink } from "./ui";

/**
 * The story's strip on every other page, Demo mode only. It holds no pointer of its own: where the story stands (the progress words, the current scene, each scene chip's state)
 * and its one forward control are the server's (`GET /demo/story`), the same read and the same `runStoryAction` as the story page. The owner's step is a link to the approval,
 * never a button that decides. A quiet link goes back to the story page. The narration of what the last step did is the responses' own words, shown only for a step whose
 * sentence holds no count (the proof step's entry count is left to the pages that list the entries).
 */
export function DemoStepper() {
  const i18n = useI18n();
  const { t, lang } = i18n;
  const router = useRouter();
  const pathname = usePathname();
  const demo = useDemo();
  const reached = reachedOf(demo);
  const story = useAsync(() => getDemoStory(lang, seenOf(reached)), [lang, reached]);
  const view = story.data;

  // The step a 401 interrupted runs by itself once the owner signs in from the dialog it opened.
  useEffect(() => onSignedIn(() => void resumeStoryAction(router.push)), [router.push]);
  const press = (action: string, books: DemoStoryView["books"]) => void runStoryAction(action, router.push, books);

  // The story page is the story: it carries its own one next control, so the strip is not drawn there.
  if (pathname === "/demo") return null;

  const lastRun = reached >= 0 ? DEMO_STEPS[reached] : null;
  const narration = lastRun && lastRun.id !== "proof" ? stepNarration(i18n, lastRun.id, demo) : "";

  return (
    <div className="border-t border-line bg-brand-50 px-4 py-2 lg:px-8" aria-label={t("demo.region")} role="region">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {/* The navy strip above the page already says DEMO on a phone, where the six scene chips need the whole width. */}
          <span className="rounded-pill bg-brand-600 px-2 py-0.5 text-meta font-bold uppercase tracking-wide text-white max-sm:hidden">{t("demo.label")}</span>
          <ol className="flex flex-wrap items-center gap-1" aria-label={t("demo.scenes")}>
            {(view?.scenes ?? []).map((s) => (
              <li
                key={s.id}
                data-testid={`demo-chip-${s.id}`}
                data-state={s.state}
                aria-current={s.state === "current" ? "step" : undefined}
                title={`${s.label}: ${s.state_text}`}
                className={`inline-flex min-h-8 items-center rounded-pill border px-3 text-meta font-semibold ${s.state === "current" ? "border-brand-600 bg-brand-50 text-brand-700" : s.state === "done" ? "border-line bg-surface text-ink" : "border-line bg-subtle text-ink-3"}`}
              >
                <span aria-hidden className="sm:hidden">
                  {s.n}
                </span>
                <span className="max-sm:sr-only">{s.label}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="min-w-0 flex-1 basis-56" aria-live="polite">
          {view ? (
            <>
              <p className="truncate text-sm font-semibold text-ink" data-testid="demo-step-title">
                <span className="mr-1.5 font-normal text-ink-3 tabular-nums" data-testid="demo-progress">
                  {view.progress_text}
                </span>
                {view.current?.title_text ?? ""}
              </p>
              {narration ? (
                <p className="line-clamp-2 text-meta text-ink-2" title={narration} data-testid="demo-step-narration">
                  {narration}
                </p>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-ink-2">{t("demo.idle")}</p>
          )}
          {/* A reload in the middle of a step leaves the books where the step stopped: say so, never unlock silently. */}
          {!demo.busy && demo.running !== null ? (
            <p className="mt-0.5 text-meta font-medium text-warn-fg" data-testid="demo-interrupted">
              {t("demo.interrupted", { n: demo.running + 1 })}
            </p>
          ) : null}
        </div>

        {/* Below sm the last 3rem of this row is Ask FLOW (chat-panel.tsx fixes it to the bar's corner). */}
        <div className="flex items-center gap-1.5 max-sm:mr-12">
          <Link href="/demo" className="motion-press hit inline-flex min-h-8 items-center rounded-pill px-2 text-sm font-medium text-brand-700 underline underline-offset-2 hover:bg-brand-50 touch:min-h-11" data-testid="demo-story-link">
            {t("trust.back.demo")}
          </Link>
          {view ? (
            view.next.href ? (
              <ButtonLink href={view.next.href} size="sm" variant="primary" data-testid="demo-next" data-owner={view.next.owner ? "true" : undefined}>
                {view.next.label}
                <ArrowRightIcon />
              </ButtonLink>
            ) : (
              <Button size="sm" variant="primary" loading={demo.busy} onClick={() => press(view.next.action ?? "", view.books)} data-testid="demo-next">
                {view.next.label}
                <ArrowRightIcon />
              </Button>
            )
          ) : null}
        </div>
      </div>
      {demo.error ? (
        <p role="alert" className="mt-1.5 rounded-tile max-sm:mr-12 border border-bad-line bg-bad-bg px-2.5 py-1.5 text-meta text-bad-fg">
          {demo.error}
        </p>
      ) : null}
    </div>
  );
}
