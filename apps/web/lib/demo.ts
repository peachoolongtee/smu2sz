import {
  actOnAlert,
  advanceClock,
  borrowerFile,
  capexApply,
  capexEvaluate,
  decideApproval,
  dealRecordId,
  demoBankReceipt,
  demoReset,
  evaluateOffer,
  getApprovals,
  getClock,
  getDecision,
  getHome,
  getLedger,
  negotiate,
  planFunding,
  submitOffer,
} from "./api";
import {
  bump,
  clearDemo,
  demoStore,
  recordBorrowerFile,
  recordCapex,
  recordCapexApplication,
  recordCure,
  recordFunding,
  recordNegotiation,
  recordOffer,
  recordVerdict,
  selectOffer,
  selectStoryOffer,
  type DemoState,
} from "./demo-store";
import { getLang, tNow } from "./i18n";
import { SAMPLES, type SampleId } from "./samples";
import type { AlertItem, ApprovalView } from "./types";

/**
 * The guided demo is the late-payment loop of docs/DEMO_FLOW.md in six scenes: the buyer asks, FLOW decides, the agreement acts on the
 * books, reality diverges (one synthetic bank event, then time passes), the owner controls the cure, and the outcome is proved.
 * Each step does its server work through lib/api.ts only, then the UI opens `route`. A step returns the sentences and figures of the
 * responses it just received (`StepFacts`); its narration is built from those and never from a figure typed into the dictionary.
 *
 * Every step is convergent: it brings the books to at least the state its scene describes, and when they are already there it only
 * reads them again. That is what lets Replay and a second Run be safe on a story that moves time.
 */
export type SceneId = "buyer" | "decision" | "agreement" | "reality" | "owner" | "proof";

export type StepId = "ask" | "decide" | "agree" | "cash" | "bank" | "time" | "queue" | "approve" | "settle" | "outcome" | "proof";

/** The sentences and figures a step was told, by name; the dictionary's `demo.done.<step>` template says where each goes. */
export type StepFactValues = Record<string, string>;

export interface DemoStep {
  id: StepId;
  scene: SceneId;
  /** The Business page that shows the result; a step whose screen depends on the books (the approval card) computes it. */
  route: string | ((demo: DemoState) => string);
  run: () => Promise<StepFactValues | void>;
  /** The owner's own click: the step's button names what is approved, and the stepper never presses it by itself. */
  owner?: boolean;
  /** A side link shown with the step (the evidence export on the last one). */
  link?: { route: string; label: "demo.link.evidence" };
}

export const stepRoute = (step: Pick<DemoStep, "route">, demo: DemoState): string => (typeof step.route === "function" ? step.route(demo) : step.route);

// ---------------------------------------------------------------- shared reads

export async function submitSample(id: SampleId): Promise<string> {
  const s = SAMPLES[id];
  const offer = await submitOffer({ fixture_id: s.fixtureId });
  recordOffer(offer, s.fixtureId);
  return offer.offer.offer_id;
}

/** Evaluates an offer and caches the verdict for the screens. Fixture offers pass their id so the owner-declared costs apply. */
export async function evaluate(offerId: string): Promise<void> {
  recordVerdict(await evaluateOffer(offerId, demoStore.get().fixtures[offerId], getLang()));
}

/**
 * The day the story lets time pass to: the second invoice (due day 32) is two days late, payroll has gone out and the reserve breach is
 * ahead. A position on the clock, not a figure; the dollars on screen all come from the responses. The same day scripts/demo_run.py reads.
 */
export const LATE_DAY = 34;
/** The cure's cash lands on its landing day and is cash the day after; used only when the approval card did not say its landing day. */
const SETTLED_FALLBACK_DAY = LATE_DAY + 4;

function storyOffer(): string {
  const id = demoStore.get().storyOfferId;
  if (!id) throw new Error(tNow("demo.err.noStory"));
  return id;
}

const dealRecord = (offerId: string) => getDecision(dealRecordId(offerId), getLang());

/** The clock moves forward to `day` (never back, never to where it already is); the books close the days and nothing is recorded as received. */
async function clockTo(day: number): Promise<number> {
  const today = (await getClock()).day;
  if (today < day) await advanceClock(day - today);
  return today;
}

/** The queue row of the cure the story queued (an alert's cure is named `alert:<alert id>:...` by the executor). */
async function cureRow(): Promise<ApprovalView | null> {
  const cure = demoStore.get().cure;
  const rows = await getApprovals();
  if (cure) return rows.find((a) => a.id === cure.approvalId) ?? null;
  return [...rows].reverse().find((a) => Boolean(a.op_id?.startsWith("alert:"))) ?? null;
}

// ---------------------------------------------------------------- the six scenes

export const DEMO_STEPS: DemoStep[] = [
  // 1. Buyer asks: the books are reset, the buyer's message arrives and is read.
  {
    id: "ask",
    scene: "buyer",
    route: "/deals",
    run: async () => {
      await demoReset();
      clearDemo();
      const id = await submitSample("EX01");
      demoStore.set((s) => ({ ...s, storyOfferId: id }));
      const record = await dealRecord(id);
      return { headline: record.headline, task: record.remaining_task?.text ?? "" };
    },
  },
  // 2. Decision: what the offer costs and the one response FLOW recommends.
  {
    id: "decide",
    scene: "decision",
    route: "/deals",
    run: async () => {
      const id = storyOffer();
      // Once the answer is sent the books have moved: a replay shows the verdict the owner decided on, it does not rewrite it.
      if (!demoStore.get().negotiations[id]) {
        await evaluate(id);
        // The Debt Desk's view at decision time: once the plan executes the books change and a re-plan is empty, so Cash keeps this as the history.
        recordFunding(await planFunding());
      }
      const w = demoStore.get().verdicts[id]?.workspace;
      return { action: w?.recommends?.text ?? "", why: w?.why_it_matters?.text ?? "", scope: w?.priced_response?.send_scope ?? "" };
    },
  },
  // 3. Agreement and action: the recommended counter is sent bound to what was shown; the books change.
  {
    id: "agree",
    scene: "agreement",
    route: "/deals#commitments",
    run: async () => {
      const id = storyOffer();
      const d = demoStore.get();
      if (!d.negotiations[id]) {
        const v = d.verdicts[id];
        if (!v) throw new Error(tNow("demo.err.noVerdict"));
        // Exactly the send Deals offers: the recommended counter with the verdict id and books version the owner was shown.
        const priced = v.workspace?.priced_response;
        const counterId = priced?.counter_id ?? v.counters[0]?.id;
        if (!counterId) throw new Error(tNow("demo.err.noCounter"));
        recordNegotiation(await negotiate(id, { buyer_profile: "cooperative", verdict_id: priced?.verdict_id ?? v.id, counter_id: counterId, state_version: priced?.state_version ?? v.state_version }));
      }
      const record = await dealRecord(id);
      return { state: record.state_text, task: record.remaining_task?.text ?? "" };
    },
  },
  {
    id: "cash",
    scene: "agreement",
    route: "/cash",
    run: async () => {
      const home = await getHome(getLang());
      const negotiation = demoStore.get().negotiations[storyOffer()];
      return { summary: negotiation?.execution?.summary_text ?? "", cash: home.cash.cash_short, transit: home.cash.in_transit?.lots[0]?.headline ?? "" };
    },
  },
  // 4. Reality diverges: the buyer's early payment arrives from the (synthetic) bank, then time passes and the later payment does not.
  {
    id: "bank",
    scene: "reality",
    route: "/receivables",
    run: async () => {
      const id = storyOffer();
      let record = await dealRecord(id);
      const awaited = record.promises.find((p) => p.status === "AWAITED");
      let reference = "";
      if (awaited) {
        // The receipt is dated to the day the buyer promised to pay by. The clock moving there records nothing; the one receipt below does.
        if (typeof awaited.promised_day === "number") await clockTo(awaited.promised_day);
        reference = (await demoBankReceipt()).bank_reference;
        bump();
        record = await dealRecord(id);
      } else if (!record.promises.some((p) => p.status === "RECEIVED")) {
        throw new Error(tNow("demo.err.noPromise"));
      }
      return { reference, state: record.state_text, task: record.remaining_task?.text ?? "" };
    },
  },
  {
    id: "time",
    scene: "reality",
    route: "/",
    run: async () => {
      const from = await clockTo(LATE_DAY);
      bump();
      const home = await getHome(getLang());
      return { days: String(Math.max(LATE_DAY - from, 0)), headline: home.headline, note: home.note };
    },
  },
  // 5. Owner control: the cure is priced above the autonomous ceiling, so it waits for the owner, who decides.
  {
    id: "queue",
    scene: "owner",
    route: (demo) => (demo.cure ? `/approvals#approval-${demo.cure.approvalId}` : "/approvals"),
    run: async () => {
      let row = await cureRow();
      if (!row) {
        // Exactly what the Home button sends: the alert as the home showed it, the books version the home read.
        const home = await getHome(getLang());
        const next = home.next_action;
        if (!next) throw new Error(tNow("demo.err.noCure"));
        await actOnAlert({ id: next.alert_id, suggested: next.suggestions } as unknown as AlertItem, home.state_version);
        row = await cureRow();
      }
      if (!row) throw new Error(tNow("demo.err.cureNotQueued"));
      recordCure({ approvalId: row.id, decisionId: row.decision_id ?? null, amount: row.amount_display ?? "", landsDay: row.presentation?.lands_day ?? null });
      return { headline: row.presentation?.headline ?? "", reason: row.presentation?.reason ?? "" };
    },
  },
  {
    id: "approve",
    scene: "owner",
    route: (demo) => (demo.cure ? `/approvals#approval-${demo.cure.approvalId}` : "/approvals"),
    owner: true,
    run: async () => {
      const row = await cureRow();
      if (!row) throw new Error(tNow("demo.err.cureNotQueued"));
      // A second Run after the decision is a Show: an approved cure is never approved again, and a declined one is not approved for the owner.
      if (row.status === "REJECTED") throw new Error(tNow("demo.err.declined"));
      const decided = row.status === "PENDING" ? await decideApproval(row.id, "APPROVE") : row;
      bump();
      return { result: decided.execution?.summary_text ?? "" };
    },
  },
  {
    id: "settle",
    scene: "owner",
    route: "/cash",
    run: async () => {
      const landsDay = demoStore.get().cure?.landsDay;
      const target = (landsDay ?? SETTLED_FALLBACK_DAY - 1) + 1;
      const from = await clockTo(target);
      bump();
      const home = await getHome(getLang());
      return { days: String(Math.max(target - from, 0)), cash: home.cash.cash_short, headline: home.headline };
    },
  },
  // 6. Outcome and proof: where the books stand, and the record that shows how they got there.
  {
    id: "outcome",
    scene: "proof",
    route: "/",
    run: async () => {
      const d = demoStore.get();
      const [home, deal, cure] = await Promise.all([getHome(getLang()), dealRecord(storyOffer()), d.cure?.decisionId ? getDecision(d.cure.decisionId, getLang()) : Promise.resolve(null)]);
      return { headline: home.headline, note: home.note, deal: deal.state_text, cure: cure?.state_text ?? "", remaining: home.remaining_task ?? "" };
    },
  },
  {
    id: "proof",
    scene: "proof",
    route: "/activity",
    link: { route: "/evidence", label: "demo.link.evidence" },
    run: async () => {
      const ledger = await getLedger();
      return { entries: String(ledger.chain_length), chain: tNow(ledger.chain_valid ? "biz.activity.chainOk" : "biz.activity.chainBroken") };
    },
  },
];

export const SCENES: { id: SceneId; first: number }[] = (["buyer", "decision", "agreement", "reality", "owner", "proof"] as SceneId[]).map((id) => ({
  id,
  first: DEMO_STEPS.findIndex((s) => s.scene === id),
}));

// ---------------------------------------------------------------- more to show (not part of Next)

/** The machine from docs/DEMO_FLOW.md Scene 3. The request is a typed input; the API does all the maths. */
const CAPEX_REQUEST = { label: "¥600k machine", price_fen: 60000000 };

/** Evaluating writes nothing: no operation, no approval. */
export async function runCapex(): Promise<void> {
  recordCapex(await capexEvaluate(CAPEX_REQUEST));
}

/**
 * The owner's explicit application for the structure the evaluation selected: POST /capex/apply queues one Tier-2
 * application, which then waits for the owner in Approvals. Nothing is applied for until the owner approves it. The
 * server refuses (409) when the books moved since the evaluation, and for any structure that is not the selected one.
 */
export async function runCapexApply(): Promise<void> {
  const capex = demoStore.get().capex ?? (await capexEvaluate(CAPEX_REQUEST));
  const selected = capex.structures.find((s) => s.id === capex.selected_id);
  if (!selected || selected.hypothetical || !selected.facility_id) {
    throw new Error("No financing structure is selected, so there is nothing to apply for.");
  }
  recordCapexApplication(
    await capexApply({
      facility_id: selected.facility_id,
      amount_fen: capex.request.price_fen,
      state_version: capex.state_version,
    }),
  );
}

/**
 * The borrower file for the financing structure the capex evaluation selected (prepared for the owner, never sent).
 * Generating it is read-only: nothing is queued and nothing waits for approval; the provenance is in the file.
 * No selected structure (the project is not worth doing, or nothing passes) means no file: there is no facility to
 * borrow on, and an illustration at another term is never one. The server defaults the spend day of an equipment
 * purchase to the day the proceeds land and says so in the file.
 */
export async function runBorrowerFile(): Promise<void> {
  const capex = demoStore.get().capex ?? (await capexEvaluate(CAPEX_REQUEST));
  const selected = capex.structures.find((s) => s.id === capex.selected_id);
  if (!selected || selected.hypothetical || !selected.facility_id) {
    throw new Error("No financing structure is selected, so there is no borrower file to prepare.");
  }
  recordBorrowerFile(
    await borrowerFile({
      facility_id: selected.facility_id,
      amount_fen: capex.request.price_fen,
      use_of_proceeds: "Purchase of production equipment",
    }),
  );
}

export async function runSecurityScene(): Promise<void> {
  const id = await submitSample("SEC");
  await evaluate(id);
}

/**
 * Another buyer who refuses every counter, on fresh books: the gap is funded anyway, and the same economics in other words (EX01B) are
 * evaluated on the same books as EX01 before anything executes. It replaces the books, so the story starts over afterwards.
 */
export async function runWalkAway(): Promise<void> {
  await demoReset();
  clearDemo();
  const id = await submitSample("EX01");
  await evaluate(id);
  // The Debt Desk's view at decision time: once the plan executes the books change and a re-plan is empty.
  recordFunding(await planFunding());
  const reworded = await submitSample("EX01B");
  await evaluate(reworded);
  selectOffer(id, reworded);
  recordNegotiation(await negotiate(id, { buyer_profile: "hard_line" }));
}

export type MoreId = "walk" | "reworded" | "capex" | "security";

export interface MoreItem {
  id: MoreId;
  route: string;
  /** Runs on the books the story left; `null` only opens a screen. */
  run: (() => Promise<void>) | null;
  /** The item needs fresh books (it resets them), so the story's pointer starts over after it. */
  replacesBooks?: boolean;
  /** The item needs the walk-away scene to have run first (it shows what that scene prepared). */
  needsWalk?: boolean;
}

export const MORE: MoreItem[] = [
  { id: "walk", route: "/verdict", run: runWalkAway, replacesBooks: true },
  { id: "reworded", route: "/verdict", run: async () => void (demoStore.get().rewordedId && selectOffer(demoStore.get().rewordedId as string)), needsWalk: true },
  // The evaluation and the read-only borrower file; applying stays the owner's click on the Capex page.
  {
    id: "capex",
    route: "/capex",
    run: async () => {
      await runCapex();
      // The file is for the structure the evaluation selected; with none (not worth doing, or nothing passes) there is no file to prepare.
      const capex = demoStore.get().capex;
      const selected = capex?.structures.find((x) => x.id === capex.selected_id);
      if (selected && !selected.hypothetical && selected.facility_id) await runBorrowerFile();
    },
  },
  // The probe is read on its own offer; the story's offer is the current one again afterwards.
  {
    id: "security",
    route: "/security",
    run: async () => {
      await runSecurityScene();
    },
  },
];

/** The screens of the engine under the story, opened as they are; they read the books as they stand. */
export const ENGINE_PAGES: { route: string; label: "demo.engine.mandate" | "demo.engine.trajectory" | "demo.engine.funding" | "demo.engine.verdict" | "demo.engine.ledger" | "demo.engine.evidence" }[] = [
  { route: "/mandate", label: "demo.engine.mandate" },
  { route: "/trajectory", label: "demo.engine.trajectory" },
  { route: "/funding", label: "demo.engine.funding" },
  { route: "/verdict", label: "demo.engine.verdict" },
  { route: "/ledger", label: "demo.engine.ledger" },
  { route: "/evidence", label: "demo.engine.evidence" },
];

/** After an optional scene the story's own message is the current one again, so Deals and the verdict keep telling the story. */
export function returnToStory(): void {
  selectStoryOffer();
}
