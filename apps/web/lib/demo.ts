import {
  borrowerFile,
  capexApply,
  capexEvaluate,
  demoReset,
  evaluateOffer,
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
  recordFunding,
  recordNegotiation,
  recordOffer,
  recordVerdict,
  selectOffer,
} from "./demo-store";
import { SAMPLES, type SampleId } from "./samples";
import type { CapexRequest } from "./types";

/**
 * The guided demo, in the order of docs/DEMO_FLOW.md: setup, Scene 1, Scene 2, Scene 3, Security.
 * Each step does its server work (through lib/api.ts only) and then the UI navigates to `route`.
 */
export type SceneId = "setup" | "s1" | "s2" | "s3" | "sec";

export type StepId =
  | "mandate"
  | "inbox"
  | "trajectory"
  | "funding"
  | "verdict"
  | "negotiate"
  | "ledger1"
  | "walk"
  | "router"
  | "ledger2"
  | "reworded"
  | "capex"
  | "approval"
  | "fastcapital"
  | "evidence";

export interface DemoStep {
  id: StepId;
  scene: SceneId;
  route: string;
  run: () => Promise<void>;
}

export async function submitSample(id: SampleId): Promise<string> {
  const s = SAMPLES[id];
  const offer = await submitOffer({ fixture_id: s.fixtureId });
  recordOffer(offer, s.fixtureId);
  return offer.offer.offer_id;
}

/** Evaluates an offer and caches the verdict for the screens. Fixture offers pass their id so the owner-declared costs apply. */
export async function evaluate(offerId: string): Promise<void> {
  recordVerdict(await evaluateOffer(offerId, demoStore.get().fixtures[offerId]));
}

const noop = async () => {};

/** The machine from docs/DEMO_FLOW.md Scene 3. The request is a typed input; the API does all the maths. */
export const CAPEX_REQUEST: CapexRequest = { label: "\u00a5600k machine", price_fen: 60000000 };

/** Evaluating writes nothing: no operation, no approval. The owner's own entry replaces the demo machine when given. */
export async function runCapex(req: CapexRequest = CAPEX_REQUEST): Promise<void> {
  recordCapex(await capexEvaluate(req));
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

export const DEMO_STEPS: DemoStep[] = [
  {
    id: "mandate",
    scene: "setup",
    route: "/mandate",
    run: async () => {
      await demoReset();
      clearDemo();
    },
  },
  { id: "inbox", scene: "s1", route: "/inbox", run: async () => void (await submitSample("EX01")) },
  {
    id: "trajectory",
    scene: "s1",
    route: "/trajectory",
    run: async () => {
      const id = demoStore.get().offerId;
      if (id) await evaluate(id);
    },
  },
  { id: "funding", scene: "s1", route: "/funding", run: async () => recordFunding(await planFunding()) },
  { id: "verdict", scene: "s1", route: "/verdict", run: noop },
  {
    id: "negotiate",
    scene: "s1",
    // The verdict page is already open from the step before; the hash scrolls to the negotiation card that shows this step's result.
    route: "/verdict#negotiation",
    run: async () => {
      const id = demoStore.get().offerId;
      if (id) recordNegotiation(await negotiate(id, { buyer_profile: "cooperative" }));
    },
  },
  { id: "ledger1", scene: "s1", route: "/ledger", run: async () => bump() },
  {
    id: "walk",
    scene: "s2",
    route: "/verdict",
    run: async () => {
      await demoReset();
      clearDemo();
      const id = await submitSample("EX01");
      await evaluate(id);
      // The Debt Desk's view at decision time: once the plan executes the books change and a re-plan is empty.
      recordFunding(await planFunding());
      // Wording invariance is tested on the same books as EX01, before anything executes.
      const reworded = await submitSample("EX01B");
      await evaluate(reworded);
      selectOffer(id, reworded);
      recordNegotiation(await negotiate(id, { buyer_profile: "hard_line" }));
    },
  },
  { id: "router", scene: "s2", route: "/funding", run: noop },
  { id: "ledger2", scene: "s2", route: "/ledger", run: async () => bump() },
  {
    id: "reworded",
    scene: "s2",
    route: "/verdict",
    run: async () => {
      const prepared = demoStore.get().rewordedId;
      if (prepared) return selectOffer(prepared);
      await evaluate(await submitSample("EX01B"));
    },
  },
  {
    id: "capex",
    scene: "s3",
    route: "/capex",
    run: runCapex,
  },
  {
    id: "approval",
    scene: "s3",
    route: "/approvals",
    run: async () => {
      await runCapexApply();
      await runBorrowerFile();
    },
  },
  {
    id: "fastcapital",
    scene: "sec",
    route: "/security",
    run: runSecurityScene,
  },
  { id: "evidence", scene: "sec", route: "/evidence", run: async () => bump() },
];

export const SCENES: { id: SceneId; first: number }[] = (["setup", "s1", "s2", "s3", "sec"] as SceneId[]).map((id) => ({
  id,
  first: DEMO_STEPS.findIndex((s) => s.scene === id),
}));
