"use client";

import { getDemoStory } from "./api";
import { changeBooks, isGuardError, resetTo, type Books } from "./books-guard";
import { ApiError } from "./errors";
import { errorMessage } from "./error-text";
import { demoStore, reachedOf, recordFacts, selectStoryOffer } from "./demo-store";
import { DEMO_STEPS, MORE, OwnerDecisionPending, stepRoute, withBooksGuard, type MoreId } from "./demo";
import { requestSignIn } from "./auth";
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
    if (isGuardError(e)) {
      // A refused reset changed nothing: the story stays where it was, and the guard (lib/books-guard.ts) says what to do.
      demoStore.set((s) => ({ ...s, busy: false, running: null }));
      throw e;
    }
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
export async function goToMore(id: MoreId, push: (route: string) => void, books: Books): Promise<StepOutcome> {
  const item = MORE.find((m) => m.id === id);
  if (!item?.replacesBooks) return runMore(id, push);
  // An optional scene that replaces the books resets them: the same guard as every other reset.
  let outcome = "done" as StepOutcome;
  await changeBooks(books, (guard) =>
    withBooksGuard(guard, async () => {
      outcome = await runMore(id, push);
    }),
  );
  return outcome;
}

async function runMore(id: MoreId, push: (route: string) => void): Promise<StepOutcome> {
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
    if (isGuardError(e)) {
      demoStore.set((s) => ({ ...s, busy: false }));
      throw e;
    }
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


/**
 * The one next control of the story page. `action` is the server's: a step id to run, or `restart` (the main books reset, as the stepper always did). The books are the truth
 * about where the story stands, so a browser session that has lost its pointer (a reload, another tab) follows the server instead of refusing the step.
 */
let resumeAction: { action: string; books: Books } | null = null;

/** The story control a 401 interrupted: once the owner signs in from the dialog it opened, it runs by itself (the strip calls this on sign-in). */
export async function resumeStoryAction(push: (route: string) => void): Promise<void> {
  const r = resumeAction;
  resumeAction = null;
  if (r) await runStoryAction(r.action, push, r.books);
}

/**
 * The one next control of the story page and of the strip. `action` is the server's: a step id to run, or `restart` (the main books reset, as the stepper always did). `books` is
 * the `books` block of the story read the caller is showing: the first step and `restart` replace the books, so they go through the guard (lib/books-guard.ts): the dialog first when
 * work would be lost, `from_scenario` always, `confirm_loss=1` only from the dialog's confirm. The books are the truth about where the story stands, so a browser session that has
 * lost its pointer (a reload, another tab) follows the server instead of refusing the step.
 */
export async function runStoryAction(action: string, push: (route: string) => void, books: Books): Promise<StepOutcome> {
  let outcome = "done" as StepOutcome;
  if (action === "restart") {
    await changeBooks(books, resetTo(undefined, push));
    return outcome;
  }
  let idx = DEMO_STEPS.findIndex((s) => s.id === action);
  if (idx < 0) return "ignored";
  // The books are mid-story but this browser has lost its place (another tab, a new session): there is no story offer to go on from, so the story starts over from scene one, and
  // starting over resets the books, which is asked first like every reset.
  if (idx > 0 && !demoStore.get().storyOfferId) idx = 0;
  if (idx > reachedOf(demoStore.get()) + 1) demoStore.set((s) => ({ ...s, reached: idx - 1, step: Math.max(s.step, idx - 1) }));
  const run = async () => {
    outcome = await goToStep(idx, push, { mode: "run" });
  };
  // The first step starts the story over on fresh books: it is the one step that resets.
  if (idx === 0) await changeBooks(books, (guard) => withBooksGuard(guard, run));
  else await run();
  if (outcome === "unauthorized") resumeAction = { action, books };
  return outcome;
}

/**
 * Whether the story's one next control waits instead of taking a press: while a step runs (`busy`), and while the story read is not
 * settled for the books as they stand (`storyLoading`). After a step, `useAsync` keeps the read from before it until GET /demo/story
 * answers again, and that read's action is the step just run: a press in that moment ran it a second time and left the story one step
 * behind (the round-nine walk stopped at the cure, one press short of the owner's approval).
 */
export function storyControlWaits(busy: boolean, storyLoading: boolean): boolean {
  return busy || storyLoading;
}

/** `seen` for GET /demo/story: the last view step (the three that change nothing: cash, outcome, proof) this browser has shown; the server accepts it only when the books support it. */
export function seenOf(reached: number): string | null {
  return DEMO_STEPS.slice(0, reached + 1).reverse().find((s) => s.id === "cash" || s.id === "outcome" || s.id === "proof")?.id ?? null;
}

let startPending = false;

/**
 * The story's start for a visitor who is not signed in: nothing reads the owner's story by itself, so the control says "Start demo" and a click asks for the sign-in; once the owner
 * has signed in the story is read and its one next control runs (`resumeStart`, called on sign-in).
 */
export function requestStart(): void {
  startPending = true;
  requestSignIn("required");
}

export async function resumeStart(lang: "en" | "zh", push: (route: string) => void): Promise<void> {
  if (!startPending) return;
  startPending = false;
  const view = await getDemoStory(lang, seenOf(reachedOf(demoStore.get())));
  if (view.next.href) push(view.next.href);
  else await runStoryAction(view.next.action ?? "", push, view.books);
}
