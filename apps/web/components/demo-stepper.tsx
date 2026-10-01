"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { demoReset } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { ApiError } from "@/lib/errors";
import { clearDemo, demoStore, useDemo } from "@/lib/demo-store";
import { DEMO_STEPS, SCENES } from "@/lib/demo";
import { useI18n } from "@/lib/i18n";
import { ArrowLeftIcon, ArrowRightIcon, ResetIcon } from "./icons";
import { Button } from "./ui";

/** Global "Demo" stepper: Scene 1 -> Scene 2 -> Scene 3 -> Security, with reset. */
export function DemoStepper() {
  const { t, te } = useI18n();
  const router = useRouter();
  const demo = useDemo();
  const step = demo.step;
  const current = step >= 0 ? DEMO_STEPS[step] : null;
  const last = DEMO_STEPS.length - 1;

  // The step a 401 interrupted: once the owner signs in from the dialog it opened, it runs by itself (as the chat resends its turn).
  const interrupted = useRef<number | null>(null);

  async function goTo(target: number) {
    if (demoStore.get().busy || target < 0 || target > last) return;
    interrupted.current = null;
    demoStore.set((s) => ({ ...s, busy: true, error: null }));
    try {
      await DEMO_STEPS[target].run();
      demoStore.set((s) => ({ ...s, step: target, busy: false }));
      const route = DEMO_STEPS[target].route;
      router.push(route);
      const hash = route.split("#")[1];
      if (hash) requestAnimationFrame(() => document.getElementById(hash)?.scrollIntoView({ block: "start" }));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        interrupted.current = target;
        demoStore.set((s) => ({ ...s, busy: false }));
        return;
      }
      demoStore.set((s) => ({ ...s, busy: false, error: e instanceof Error ? e.message : String(e) }));
    }
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

  function back() {
    const target = step - 1;
    if (target < 0 || demoStore.get().busy) return;
    demoStore.set((s) => ({ ...s, step: target, error: null }));
    router.push(DEMO_STEPS[target].route);
  }

  async function reset() {
    if (demoStore.get().busy) return;
    demoStore.set((s) => ({ ...s, busy: true, error: null }));
    try {
      await demoReset();
      clearDemo();
      router.push("/mandate");
    } catch (e) {
      // A 401 has opened the sign-in dialog; Reset stays a deliberate click.
      const unauthorized = e instanceof ApiError && e.status === 401;
      demoStore.set((s) => ({ ...s, busy: false, error: unauthorized ? null : e instanceof Error ? e.message : String(e) }));
    }
  }

  const nextLabel = step < 0 ? t("demo.start") : t("demo.next");

  return (
    <div className="border-t border-line bg-brand-50 px-4 py-2 lg:px-8" aria-label={t("demo.region")} role="region">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="rounded bg-brand-600 px-1.5 py-0.5 text-[0.7rem] font-bold uppercase tracking-wide text-white">
            {t("demo.label")}
          </span>
          <ol className="flex items-center gap-1" aria-label={t("demo.scenes")}>
            {SCENES.map((s) => {
              const active = current?.scene === s.id;
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    disabled={demo.busy}
                    onClick={() => void goTo(s.first)}
                    aria-current={active ? "step" : undefined}
                    title={t("demo.jump", { scene: te("scene", s.id) })}
                    className={`min-h-8 whitespace-nowrap rounded-md border px-2 text-xs font-medium disabled:opacity-50 ${
                      active
                        ? "border-brand-600 bg-brand-600 text-white"
                        : "border-line-strong bg-surface text-ink-2 hover:bg-subtle"
                    }`}
                  >
                    {te("scene.short", s.id)}
                  </button>
                </li>
              );
            })}
          </ol>
        </div>

        <div className="min-w-0 flex-1 basis-56" aria-live="polite">
          {current ? (
            <>
              <p className="truncate text-sm font-semibold text-ink">
                <span className="mr-1.5 font-normal text-ink-3 tabular-nums">
                  {t("demo.progress", { n: step + 1, total: DEMO_STEPS.length })}
                </span>
                {te("demo.step", current.id)}
              </p>
              <p className="truncate text-xs text-ink-2">{te("demo.desc", current.id)}</p>
            </>
          ) : (
            <p className="text-sm text-ink-2">{t("demo.idle")}</p>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="ghost" onClick={back} disabled={demo.busy || step <= 0} aria-label={t("demo.back")}>
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
          <Button size="sm" variant="secondary" onClick={() => void reset()} disabled={demo.busy} data-testid="demo-reset">
            <ResetIcon />
            {t("demo.reset")}
          </Button>
        </div>
      </div>
      {demo.error ? (
        <p role="alert" className="mt-1.5 rounded-md border border-bad-line bg-bad-bg px-2.5 py-1.5 text-xs text-bad-fg">
          {demo.error}
        </p>
      ) : null}
    </div>
  );
}
