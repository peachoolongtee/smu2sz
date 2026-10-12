"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { TodayCard } from "@/components/home/today-card";
import { ArrowRightIcon, ResetIcon } from "@/components/icons";
import { Disclosure } from "@/components/business/kit";
import { Badge, Button, Callout, Card, PageHeader, inputClass } from "@/components/ui";
import { goToMore, goToStep, nextStep, resetDemo } from "@/lib/demo-control";
import { reachedOf, useDemo } from "@/lib/demo-store";
import { DEMO_STEPS, ENGINE_PAGES, MORE, SCENES, stepRoute, type SceneId } from "@/lib/demo";
import { stepNarration } from "@/lib/demo-text";
import { useI18n } from "@/lib/i18n";
import { useCureWaiting } from "@/lib/use-cure-waiting";
import { useNarrow } from "@/lib/use-narrow";

/**
 * One of the page's three side cards. On a desktop it is a card; on a phone it is one closed fold with the card's title (the story is the
 * page, these are tools for after it), so the page stays short. Its parts keep their ids and test ids; a fold only hides them until it is opened.
 */
function SideCard({ id, title, subtitle, narrow, children }: { id: string; title: string; subtitle: string; narrow: boolean; children: ReactNode }) {
  if (!narrow) {
    return (
      <Card id={id} title={title} subtitle={subtitle}>
        {children}
      </Card>
    );
  }
  return (
    <div id={id} className="scroll-mt-20">
      <Disclosure card testId={`story-fold-${id}`} summary={title}>
        {subtitle ? <p className="mb-3 text-meta text-ink-3">{subtitle}</p> : null}
        {children}
      </Disclosure>
    </div>
  );
}

/**
 * The judge's page: the late-payment loop in six scenes, each step one click, with the clock, the scenario switch, the optional scenes
 * and the side doors. The one brand fill on the page is the strip's Start demo / Next; every button here is a secondary pill.
 */
export default function DemoPage() {
  const i18n = useI18n();
  const { t, te } = i18n;
  const router = useRouter();
  const demo = useDemo();
  const [scenario, setScenario] = useState<"golden_sme" | "short_facilities">("golden_sme");
  const current = demo.step;
  // On a phone the clock, the optional scenes and the books are one closed fold each: the page is the story.
  const narrow = useNarrow();
  // The highest finished step: Back lowers the pointer, not this. Steps up to here are done (Show, Replay); the one after it is the next to run.
  const reached = reachedOf(demo);
  // The owner's own step: while the cure waits, the decision is the approval card's one filled Approve. The strip's button only opens it, and the
  // step here shows where the decision stands instead of a second button.
  const cureWaiting = useCureWaiting();
  const upcomingOwner = Boolean(DEMO_STEPS[current + 1]?.owner);
  const opensApproval = upcomingOwner && cureWaiting;
  const runLabel = () => t("story.run");
  const upcoming = DEMO_STEPS[current + 1] ?? null;

  return (
    <>
      <PageHeader
        title={t("story.title")}
        subtitle={t("story.subtitle")}
        actions={
          <Button variant="secondary" loading={demo.busy} disabled={current >= DEMO_STEPS.length - 1} onClick={() => (opensApproval && upcoming ? router.push(stepRoute(upcoming, demo)) : void nextStep(router.push))} data-testid="story-next">
            {current < 0 ? t("demo.start") : opensApproval ? t("demo.openApproval") : t("demo.next")}
            <ArrowRightIcon />
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-6">
          <Card id="story" title={t("story.steps")} subtitle={t("story.steps.sub")}>
            <ol className="space-y-4">
              {SCENES.map((scene) => (
                <li key={scene.id}>
                  <p className="mb-1.5 text-meta font-semibold uppercase tracking-wide text-ink-3">{te("scene", scene.id)}</p>
                  <ol className="space-y-1">
                    {DEMO_STEPS.map((s, i) => ({ s, i }))
                      .filter(({ s }) => s.scene === (scene.id as SceneId))
                      .map(({ s, i }) => {
                        const done = i <= reached;
                        const active = i === current;
                        return (
                          <li key={s.id} className={`grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 gap-y-1 rounded-tile border px-3 py-2 sm:flex sm:flex-wrap sm:gap-y-2 ${active ? "border-brand-600 bg-brand-50" : "border-line"}`} data-testid={`story-step-${i + 1}`} data-done={done}>
                            <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-pill text-meta font-bold ${done ? "bg-brand-600 text-white" : "bg-subtle text-ink-3"}`} aria-hidden>
                              {i + 1}
                            </span>
                            {/* On a phone the button sits beside the title and the sentence (three lines; the whole sentence is the tooltip). */}
                            <span className="contents sm:block sm:min-w-0 sm:flex-1 sm:basis-48">
                              <span className="block min-w-0 text-sm font-medium text-ink">{te("demo.step", s.id)}</span>
                              <span className="block text-meta text-ink-2 max-sm:col-start-2 max-sm:row-start-2 max-sm:line-clamp-3 sm:mt-0" title={stepNarration(i18n, s.id, demo)}>
                                {stepNarration(i18n, s.id, demo)}
                              </span>
                            </span>
                            <span className="flex shrink-0 gap-1.5 max-sm:col-start-3 max-sm:row-span-2 max-sm:row-start-1">
                              {done ? (
                                <>
                                  {/* A finished step is shown, never re-run by accident: Show only opens its screen; Replay is the deliberate re-run. */}
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    disabled={demo.busy}
                                    onClick={() => void goToStep(i, router.push, { mode: "show" })}
                                    title={t("story.show.hint")}
                                    aria-label={`${t("story.show")}, ${t("story.stepN", { n: i + 1 })}`}
                                    data-testid={`story-show-${i + 1}`}
                                  >
                                    {t("story.show")}
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    disabled={demo.busy}
                                    onClick={() => void goToStep(i, router.push, { mode: "run" })}
                                    title={t(i === 0 ? "story.replay.setup" : "story.replay.hint")}
                                    aria-label={`${t("story.replay")}, ${t("story.stepN", { n: i + 1 })}. ${t(i === 0 ? "story.replay.setup" : "story.replay.hint")}`}
                                    data-testid={`story-replay-${i + 1}`}
                                  >
                                    <ResetIcon className="sm:hidden" />
                                    <span className="max-sm:sr-only">{t("story.replay")}</span>
                                  </Button>
                                </>
                              ) : s.owner && cureWaiting && i === reached + 1 ? (
                                <span className="text-meta font-medium text-warn-fg" data-testid={`story-waiting-${i + 1}`}>
                                  {t("story.waitingOwner")}
                                </span>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  // The story moves time: a step waits for the one before it.
                                  disabled={demo.busy || i > reached + 1}
                                  onClick={() => void goToStep(i, router.push, { mode: "run" })}
                                  title={i > reached + 1 ? t("story.run.wait") : undefined}
                                  aria-label={`${runLabel()}, ${t("story.stepN", { n: i + 1 })}`}
                                  data-testid={`story-run-${i + 1}`}
                                >
                                  {runLabel()}
                                </Button>
                              )}
                            </span>
                          </li>
                        );
                      })}
                  </ol>
                </li>
              ))}
            </ol>
            {!demo.busy && demo.running !== null ? (
              <p role="status" className="mt-3 rounded-tile border border-warn-line bg-warn-bg px-2.5 py-1.5 text-meta text-warn-fg" data-testid="story-interrupted">
                {t("demo.interrupted", { n: demo.running + 1 })}
              </p>
            ) : null}
            {demo.error ? (
              <p role="alert" className="mt-3 rounded-tile border border-bad-line bg-bad-bg px-2.5 py-1.5 text-meta text-bad-fg">
                {demo.error}
              </p>
            ) : null}
          </Card>

          <SideCard id="story-more" title={t("story.more")} subtitle={t("story.more.sub")} narrow={narrow}>
            <ul className="space-y-3">
              {MORE.map((m) => (
                <li key={m.id} className="flex flex-wrap items-start gap-x-3 gap-y-2" data-testid={`more-${m.id}`}>
                  <span className="min-w-0 flex-1 basis-48">
                    <span className="block text-sm font-medium text-ink">{te("more.title", m.id)}</span>
                    <span className="block text-meta text-ink-2">{te("more.desc", m.id)}</span>
                    {m.replacesBooks ? <span className="block text-meta font-medium text-warn-fg">{t("more.replaces")}</span> : null}
                    {m.needsWalk && !demo.rewordedId ? <span className="block text-meta text-ink-3">{t("more.needsWalk")}</span> : null}
                  </span>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={demo.busy || Boolean(m.needsWalk && !demo.rewordedId)}
                    onClick={() => void goToMore(m.id, router.push)}
                    aria-label={`${t("story.show")}: ${te("more.title", m.id)}`}
                    data-testid={`more-run-${m.id}`}
                  >
                    {t("story.show")}
                  </Button>
                </li>
              ))}
            </ul>
            <div className="mt-4 border-t border-line pt-3">
              <p className="mb-1.5 text-meta font-semibold uppercase tracking-wide text-ink-3">{t("more.engine")}</p>
              <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                {ENGINE_PAGES.map((p) => (
                  <li key={p.route}>
                    <Link href={p.route} className="font-medium text-brand-700 underline underline-offset-2">
                      {t(p.label)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </SideCard>
        </div>

        <div className="min-w-0 space-y-6">
          {/* The clock moves the books under a running step: a disabled fieldset locks the card's controls while a step runs. */}
          <fieldset disabled={demo.busy} className="min-w-0">
            {narrow ? (
              <SideCard id="story-today" title={t("home.today")} subtitle="" narrow>
                <TodayCard onAdvanced={() => undefined} folded />
              </SideCard>
            ) : (
              <TodayCard onAdvanced={() => undefined} />
            )}
          </fieldset>

          <SideCard id="story-reset" title={t("story.books")} subtitle={t("story.books.sub")} narrow={narrow}>
            <div className="space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block text-meta font-medium text-ink-3">{t("story.scenario")}</span>
                <select
                  value={scenario}
                  disabled={demo.busy}
                  onChange={(e) => setScenario(e.target.value as "golden_sme" | "short_facilities")}
                  className={`w-full ${inputClass}`}
                  data-testid="story-scenario"
                >
                  <option value="golden_sme">{t("story.scenario.golden")}</option>
                  <option value="short_facilities">{t("story.scenario.short")}</option>
                </select>
              </label>
              <Button variant="secondary" disabled={demo.busy} onClick={() => void resetDemo(router.push, scenario === "golden_sme" ? undefined : scenario)} data-testid="story-reset">
                <ResetIcon />
                {t("story.reset")}
              </Button>
              <p className="text-meta text-ink-3">{t("story.reset.hint")}</p>
            </div>
          </SideCard>

          <Card id="story-doors" title={t("story.doors")} subtitle={t("story.doors.sub")}>
            <ul className="space-y-2 text-sm">
              {(
                [
                  ["/chat", "story.door.buyer"],
                  ["/whatif", "story.door.whatif"],
                  ["/evidence", "story.door.evidence"],
                  ["/", "story.door.business"],
                ] as const
              ).map(([href, key]) => (
                <li key={href}>
                  <Link href={href} className="font-medium text-brand-700 underline underline-offset-2">
                    {t(key)}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>

          <Callout tone="info">
            <Badge tone="info" className="mb-1">
              {t("story.simulation")}
            </Badge>
            <p>{t("common.synthetic")}</p>
          </Callout>
        </div>
      </div>
    </>
  );
}
