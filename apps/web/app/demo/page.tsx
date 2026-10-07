"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { TodayCard } from "@/components/home/today-card";
import { ResetIcon } from "@/components/icons";
import { Badge, Button, Callout, Card, PageHeader } from "@/components/ui";
import { goToStep, resetDemo } from "@/lib/demo-control";
import { useDemo } from "@/lib/demo-store";
import { DEMO_STEPS, SCENES, type SceneId } from "@/lib/demo";
import { useI18n } from "@/lib/i18n";

/** The judge's page: the story in order, each step one click, with the clock, the scenario switch and the side doors. */
export default function DemoPage() {
  const { t, te } = useI18n();
  const router = useRouter();
  const demo = useDemo();
  const [scenario, setScenario] = useState<"golden_sme" | "short_facilities">("golden_sme");
  const current = demo.step;

  return (
    <>
      {/* The story bar above carries Start demo and Next; the page does not repeat it. */}
      <PageHeader title={t("story.title")} subtitle={t("story.subtitle")} />

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
                          <li key={s.id} className={`flex items-start gap-3 rounded-md border px-3 py-2 ${active ? "border-brand-600 bg-brand-50" : "border-line"}`} data-testid={`story-step-${i + 1}`} data-done={done}>
                            <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-xs font-bold ${done ? "bg-brand-600 text-white" : "bg-subtle text-ink-3"}`} aria-hidden>
                              {i + 1}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block text-sm font-medium text-ink">{te("demo.step", s.id)}</span>
                              <span className="block text-xs text-ink-2">{te("demo.desc", s.id)}</span>
                            </span>
                            <Button size="sm" variant={active ? "primary" : "secondary"} disabled={demo.busy} onClick={() => void goToStep(i, router.push)}>
                              {done ? t("story.show") : t("story.run")}
                            </Button>
                          </li>
                        );
                      })}
                  </ol>
                </li>
              ))}
            </ol>
            {demo.error ? (
              <p role="alert" className="mt-3 rounded-md border border-bad-line bg-bad-bg px-2.5 py-1.5 text-xs text-bad-fg">
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
          <TodayCard onAdvanced={() => undefined} />

          <Card id="story-reset" title={t("story.books")} subtitle={t("story.books.sub")}>
            <div className="space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium text-ink-3">{t("story.scenario")}</span>
                <select
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value as "golden_sme" | "short_facilities")}
                  className="min-h-10 w-full rounded-md border border-line-strong bg-surface px-2 text-sm"
                  data-testid="story-scenario"
                >
                  <option value="golden_sme">{t("story.scenario.golden")}</option>
                  <option value="short_facilities">{t("story.scenario.short")}</option>
                </select>
              </label>
              <Button variant="secondary" loading={demo.busy} onClick={() => void resetDemo(router.push, scenario === "golden_sme" ? undefined : scenario)} data-testid="story-reset">
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
