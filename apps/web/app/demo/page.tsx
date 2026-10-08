"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TodayCard } from "@/components/home/today-card";
import { ArrowRightIcon, ResetIcon } from "@/components/icons";
import { Badge, Button, Callout, Card, PageHeader, inputClass } from "@/components/ui";
import { goToStep, resetDemo } from "@/lib/demo-control";
import { useDemo } from "@/lib/demo-store";
import { DEMO_STEPS, SCENES, type SceneId } from "@/lib/demo";
import { useI18n } from "@/lib/i18n";

/**
 * The judge's page: the story in order, each step one click, with the clock, the scenario switch and the side doors. The one brand
 * fill on the page is the strip's Start demo / Next; every button here is a secondary pill.
 */
export default function DemoPage() {
  const { t, te } = useI18n();
  const router = useRouter();
  const demo = useDemo();
  const [scenario, setScenario] = useState<"golden_sme" | "short_facilities">("golden_sme");
  const current = demo.step;

  return (
    <>
      <PageHeader
        title={t("story.title")}
        subtitle={t("story.subtitle")}
        actions={
          <Button variant="secondary" loading={demo.busy} disabled={current >= DEMO_STEPS.length - 1} onClick={() => void goToStep(current + 1, router.push)} data-testid="story-next">
            {current < 0 ? t("demo.start") : t("demo.next")}
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
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{te("scene", scene.id)}</p>
                  <ol className="space-y-1">
                    {DEMO_STEPS.map((s, i) => ({ s, i }))
                      .filter(({ s }) => s.scene === (scene.id as SceneId))
                      .map(({ s, i }) => {
                        const done = i <= current;
                        const active = i === current;
                        return (
                          <li key={s.id} className={`flex flex-wrap items-start gap-x-3 gap-y-2 rounded-tile border px-3 py-2 ${active ? "border-brand-600 bg-brand-50" : "border-line"}`} data-testid={`story-step-${i + 1}`} data-done={done}>
                            <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-pill text-xs font-bold ${done ? "bg-brand-600 text-white" : "bg-subtle text-ink-3"}`} aria-hidden>
                              {i + 1}
                            </span>
                            <span className="min-w-0 flex-1 basis-48">
                              <span className="block text-sm font-medium text-ink">{te("demo.step", s.id)}</span>
                              <span className="block text-xs text-ink-2">{te("demo.desc", s.id)}</span>
                            </span>
                            <span className="flex shrink-0 gap-1.5 max-sm:ml-9">
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
                                    {t("story.replay")}
                                  </Button>
                                </>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  disabled={demo.busy}
                                  onClick={() => void goToStep(i, router.push, { mode: "run" })}
                                  aria-label={`${t("story.run")}, ${t("story.stepN", { n: i + 1 })}`}
                                  data-testid={`story-run-${i + 1}`}
                                >
                                  {t("story.run")}
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
              <p role="status" className="mt-3 rounded-tile border border-warn-line bg-warn-bg px-2.5 py-1.5 text-xs text-warn-fg" data-testid="story-interrupted">
                {t("demo.interrupted", { n: demo.running + 1 })}
              </p>
            ) : null}
            {demo.error ? (
              <p role="alert" className="mt-3 rounded-tile border border-bad-line bg-bad-bg px-2.5 py-1.5 text-xs text-bad-fg">
                {demo.error}
              </p>
            ) : null}
          </Card>

          <Card id="story-after" title={t("story.after")} subtitle={t("story.after.sub")}>
            <ol className="list-decimal space-y-1 pl-5 text-sm text-ink-2">
              {(["1", "2", "3", "4", "5"] as const).map((n) => (
                <li key={n}>{t(`story.after.${n}`)}</li>
              ))}
            </ol>
            <p className="mt-3 text-xs text-ink-3">{t("story.after.hint")}</p>
          </Card>
        </div>

        <div className="min-w-0 space-y-6">
          {/* The clock moves the books under a running step: a disabled fieldset locks the card's controls while a step runs. */}
          <fieldset disabled={demo.busy} className="min-w-0">
            <TodayCard onAdvanced={() => undefined} />
          </fieldset>

          <Card id="story-reset" title={t("story.books")} subtitle={t("story.books.sub")}>
            <div className="space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-ink-3">{t("story.scenario")}</span>
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
              <p className="text-xs text-ink-3">{t("story.reset.hint")}</p>
            </div>
          </Card>

          <Card id="story-doors" title={t("story.doors")} subtitle={t("story.doors.sub")}>
            <ul className="space-y-2 text-sm">
              {(
                [
                  ["/chat", "story.door.buyer"],
                  ["/security", "story.door.attack"],
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
