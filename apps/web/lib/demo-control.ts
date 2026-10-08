"use client";

import { demoReset } from "./api";
import { ApiError } from "./errors";
import { errorMessage } from "./error-text";
import { demoStore, resetSession } from "./demo-store";
import { DEMO_STEPS } from "./demo";
import { setMode } from "./mode";

/**
 * Running the guided demo from anywhere (the stepper bar and the story page share this). Each step does its server work
 * through lib/api.ts and then the caller navigates to the step's route. A 401 is reported as `"unauthorized"` so the
 * caller can resume the step once the owner has signed in; any other error is kept in the demo store for display.
 *
 * Two modes. `run` does the step's server work (and changes the books); `show` only opens the step's screen and is allowed for
 * a completed step (`target <= step`), so it can never reset the clock or the ledger. Replaying a completed step is `run`.
 */
export type StepMode = "show" | "run";
export type StepOutcome = "done" | "unauthorized" | "busy" | "error" | "ignored";

/**
 * A second guard beside `busy` in the store: one control action at a time, whatever a step does to the store while it runs.
 * It is module state, so it also covers the instant between a click and the store's `busy` flag reaching the buttons.
 */
let inFlight = false;

function open(route: string, push: (route: string) => void): void {
  push(route);
  const hash = route.split("#")[1];
  if (hash) requestAnimationFrame(() => document.getElementById(hash)?.scrollIntoView({ block: "start" }));
}

export async function goToStep(target: number, push: (route: string) => void, opts: { mode?: StepMode } = {}): Promise<StepOutcome> {
  const mode = opts.mode ?? "run";
  const last = DEMO_STEPS.length - 1;
  if (inFlight || demoStore.get().busy) return "busy";
  if (target < 0 || target > last) return "ignored";
  setMode("demo"); // the story is Demo mode: the stepper stays on every screen it visits
  if (mode === "show") {
    if (target > demoStore.get().step) return "ignored";
    open(DEMO_STEPS[target].route, push); // read-only: the store is not touched
    return "done";
  }
  inFlight = true;
  demoStore.set((s) => ({ ...s, busy: true, running: target, error: null }));
  try {
    await DEMO_STEPS[target].run();
    demoStore.set((s) => ({ ...s, step: target, busy: false, running: null }));
    open(DEMO_STEPS[target].route, push);
    return "done";
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      demoStore.set((s) => ({ ...s, busy: false, running: null }));
      return "unauthorized";
    }
    demoStore.set((s) => ({ ...s, busy: false, running: null, error: errorMessage(e) }));
    return "error";
  } finally {
    inFlight = false;
  }
}

/** Back only moves the pointer: the books already hold the step's result. */
export function backStep(push: (route: string) => void): void {
  const step = demoStore.get().step;
  const target = step - 1;
  if (target < 0 || inFlight || demoStore.get().busy) return;
  demoStore.set((s) => ({ ...s, step: target, running: null, error: null }));
  push(DEMO_STEPS[target].route);
}

/** Reset the books (owner action) and clear the session; `scenario` picks the server fixture (golden books by default). */
export async function resetDemo(push: (route: string) => void, scenario?: string): Promise<void> {
  if (inFlight || demoStore.get().busy) return;
  inFlight = true;
  setMode("demo");
  demoStore.set((s) => ({ ...s, busy: true, running: null, error: null }));
  try {
    await demoReset(scenario);
    resetSession();
    push("/demo");
  } catch (e) {
    // A 401 has opened the sign-in dialog; Reset stays a deliberate click.
    const unauthorized = e instanceof ApiError && e.status === 401;
    demoStore.set((s) => ({ ...s, busy: false, error: unauthorized ? null : errorMessage(e) }));
  } finally {
    inFlight = false;
  }
}
