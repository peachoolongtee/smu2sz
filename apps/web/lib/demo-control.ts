"use client";

import { demoReset } from "./api";
import { ApiError } from "./errors";
import { clearDemo, demoStore } from "./demo-store";
import { DEMO_STEPS } from "./demo";
import { setMode } from "./mode";

/**
 * Running the guided demo from anywhere (the stepper bar and the story page share this). Each step does its server work
 * through lib/api.ts and then the caller navigates to the step's route. A 401 is reported as `"unauthorized"` so the
 * caller can resume the step once the owner has signed in; any other error is kept in the demo store for display.
 */
export async function goToStep(target: number, push: (route: string) => void): Promise<"done" | "unauthorized" | "busy" | "error"> {
  const last = DEMO_STEPS.length - 1;
  if (demoStore.get().busy || target < 0 || target > last) return "busy";
  setMode("demo"); // running the story is Demo mode: the stepper stays on every screen it visits
  demoStore.set((s) => ({ ...s, busy: true, error: null }));
  try {
    await DEMO_STEPS[target].run();
    demoStore.set((s) => ({ ...s, step: target, busy: false }));
    const route = DEMO_STEPS[target].route;
    push(route);
    const hash = route.split("#")[1];
    if (hash) requestAnimationFrame(() => document.getElementById(hash)?.scrollIntoView({ block: "start" }));
    return "done";
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      demoStore.set((s) => ({ ...s, busy: false }));
      return "unauthorized";
    }
    demoStore.set((s) => ({ ...s, busy: false, error: e instanceof Error ? e.message : String(e) }));
    return "error";
  }
}

/** Back only moves the pointer: the books already hold the step's result. */
export function backStep(push: (route: string) => void): void {
  const step = demoStore.get().step;
  const target = step - 1;
  if (target < 0 || demoStore.get().busy) return;
  demoStore.set((s) => ({ ...s, step: target, error: null }));
  push(DEMO_STEPS[target].route);
}

/** Reset the books (owner action) and clear the session; `scenario` picks the server fixture (golden books by default). */
export async function resetDemo(push: (route: string) => void, scenario?: string): Promise<void> {
  if (demoStore.get().busy) return;
  setMode("demo");
  demoStore.set((s) => ({ ...s, busy: true, error: null }));
  try {
    await demoReset(scenario);
    clearDemo();
    push("/demo");
  } catch (e) {
    // A 401 has opened the sign-in dialog; Reset stays a deliberate click.
    const unauthorized = e instanceof ApiError && e.status === 401;
    demoStore.set((s) => ({ ...s, busy: false, error: unauthorized ? null : e instanceof Error ? e.message : String(e) }));
  }
}
