"use client";

import { demoReset } from "./api";
import { ApiError } from "./errors";
import { errorMessage } from "./error-text";
import { demoStore, reachedOf, recordFacts, resetSession, selectStoryOffer } from "./demo-store";
import { DEMO_STEPS, MORE, OwnerDecisionPending, stepRoute, type MoreId } from "./demo";
import { getLang } from "./i18n";
import { setMode } from "./mode";

/**
 * Running the guided demo from anywhere (the stepper bar and the story page share this). Each step does its server work
 * through lib/api.ts and then the caller navigates to the step's route. A 401 is reported as `"unauthorized"` so the
 * caller can resume the step once the owner has signed in; any other error is kept in the demo store for display.
 *
 * Three modes. `run` does the step's server work (and changes the books); `show` only opens the step's screen and is allowed for
 * a finished step (`target <= reached`, the highest step ever finished, which Back does not lower), so it can never reset the clock or the
 * ledger; `follow` is a Show that also moves the pointer to the step (what Next does after a Back). Replaying a finished step is `run`.
 * A step can only run when the one before the finished ones has: the story moves time, so a step never skips the steps that make it true.
 */
export type StepMode = "show" | "run" | "follow";
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
  if (mode === "show" || mode === "follow") {
    if (target > reachedOf(demoStore.get())) return "ignored";
    selectStoryOffer(); // an optional scene may have read another message: the story shows its own
    if (mode === "follow") demoStore.set((s) => ({ ...s, step: target, running: null, error: null }));
    open(stepRoute(DEMO_STEPS[target], demoStore.get()), push); // read-only: the books are not touched
    return "done";
  }
  // The first step starts the story over; every other step needs the one before it.
  if (target > reachedOf(demoStore.get()) + 1) return "ignored";
  inFlight = true;
  demoStore.set((s) => ({ ...s, busy: true, running: target, error: null }));
  try {
    selectStoryOffer();
    const step = DEMO_STEPS[target];
    const values = await step.run();
    if (values) recordFacts(step.id, { lang: getLang(), values });
    // The first step starts the story over, so the highest finished step starts over with it.
    demoStore.set((s) => ({ ...s, step: target, reached: target === 0 ? 0 : Math.max(reachedOf(s), target), busy: false, running: null }));
    open(stepRoute(step, demoStore.get()), push);
    return "done";
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      demoStore.set((s) => ({ ...s, busy: false, running: null }));
      return "unauthorized";
    }
    if (e instanceof OwnerDecisionPending) {
      // The cure still waits: the step decided nothing and is not finished. The owner's card is opened; the pointer stays where it was.
      demoStore.set((s) => ({ ...s, busy: false, running: null }));
      open(stepRoute(DEMO_STEPS[target], demoStore.get()), push);
      return "done";
    }
    demoStore.set((s) => ({ ...s, busy: false, running: null, error: errorMessage(e) }));
    return "error";
  } finally {
    inFlight = false;
  }
}

/**
 * Next: the step after the pointer. After a Back that is a step already finished, so Next only shows it (the pointer moves, nothing runs and
 * the books are not touched); only the step after the highest finished one is run.
 */
export function nextStep(push: (route: string) => void): Promise<StepOutcome> {
  const d = demoStore.get();
  const target = d.step + 1;
  return goToStep(target, push, { mode: target <= reachedOf(d) ? "follow" : "run" });
}

/** Back only moves the pointer: the books already hold the step's result. */
export function backStep(push: (route: string) => void): void {
  const step = demoStore.get().step;
  const target = step - 1;
  if (target < 0 || inFlight || demoStore.get().busy) return;
  selectStoryOffer();
  demoStore.set((s) => ({ ...s, step: target, running: null, error: null }));
  push(stepRoute(DEMO_STEPS[target], demoStore.get()));
}

/**
 * One of the optional scenes ("More to show"). It never moves the story's pointer: it runs on the books the story left and opens its
 * screen. The scene that replaces the books (the buyer who walks away) cannot leave a story half-told on books that are no longer
 * its own, so after it the story starts over from its first step.
 */
export async function goToMore(id: MoreId, push: (route: string) => void): Promise<StepOutcome> {
  const item = MORE.find((m) => m.id === id);
  if (!item) return "ignored";
  if (inFlight || demoStore.get().busy) return "busy";
  if (item.needsWalk && !demoStore.get().rewordedId) return "ignored";
  setMode("demo");
  inFlight = true;
  demoStore.set((s) => ({ ...s, busy: true, running: null, error: null }));
  try {
    if (item.run) await item.run();
    if (item.replacesBooks) {
      // The story's own state is gone with its books; what the optional scene prepared (the offers, verdicts, the answer) stays for its screens.
      demoStore.set((s) => ({ ...s, step: -1, reached: -1, storyOfferId: null, cure: null, facts: {}, busy: false }));
    } else demoStore.set((s) => ({ ...s, busy: false }));
    open(item.route, push);
    return "done";
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      demoStore.set((s) => ({ ...s, busy: false }));
      return "unauthorized";
    }
    demoStore.set((s) => ({ ...s, busy: false, error: errorMessage(e) }));
    return "error";
  } finally {
    inFlight = false;
  }
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

/**
 * The one next control of the story page. `action` is the server's: a step id to run, or `restart` (the main books reset, as the stepper always did). The books are the truth
 * about where the story stands, so a browser session that has lost its pointer (a reload, another tab) follows the server instead of refusing the step.
 */
let resumeAction: string | null = null;

/** The story control a 401 interrupted: once the owner signs in from the dialog it opened, it runs by itself (the strip calls this on sign-in). */
export async function resumeStoryAction(push: (route: string) => void): Promise<void> {
  const action = resumeAction;
  resumeAction = null;
  if (action) await runStoryAction(action, push);
}

export async function runStoryAction(action: string, push: (route: string) => void): Promise<StepOutcome> {
  const outcome = await runStoryActionOnce(action, push);
  if (outcome === "unauthorized") resumeAction = action;
  return outcome;
}

async function runStoryActionOnce(action: string, push: (route: string) => void): Promise<StepOutcome> {
  if (action === "restart") {
    await resetDemo(push);
    return "done";
  }
  const idx = DEMO_STEPS.findIndex((s) => s.id === action);
  if (idx < 0) return "ignored";
  if (idx > reachedOf(demoStore.get()) + 1) demoStore.set((s) => ({ ...s, reached: idx - 1, step: Math.max(s.step, idx - 1) }));
  return goToStep(idx, push, { mode: "run" });
}

/** `seen` for GET /demo/story: the last view step (the three that change nothing: cash, outcome, proof) this browser has shown; the server accepts it only when the books support it. */
export function seenOf(reached: number): string | null {
  return DEMO_STEPS.slice(0, reached + 1).reverse().find((s) => s.id === "cash" || s.id === "outcome" || s.id === "proof")?.id ?? null;
}
