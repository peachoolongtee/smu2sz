import {
  borrowerFile,
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
  recordNegotiation,
  recordOffer,
  recordVerdict,
} from "./demo-store";
import { SAMPLES, type SampleId } from "./samples";

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
  const offer = await submitOffer({ counterparty_id: s.counterparty_id, documents: s.documents });
  recordOffer(offer);
  return offer.offer.offer_id;
}

export async function evaluate(offerId: string): Promise<void> {
  recordVerdict(await evaluateOffer(offerId));
}

const noop = async () => {};

/** The machine from docs/DEMO_FLOW.md Scene 3. The request is a typed input; the API does all the maths. */
export async function runCapex(): Promise<void> {
  recordCapex(await capexEvaluate({ label: "\u00a5600k machine", price_fen: 60000000 }));
}

export async function runBorrowerFile(): Promise<void> {
  recordBorrowerFile(await borrowerFile({ facility_id: "FAC-ETL", amount_fen: 60000000 }));
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
  { id: "funding", scene: "s1", route: "/funding", run: async () => void (await planFunding()) },
  { id: "verdict", scene: "s1", route: "/verdict", run: noop },
  {
    id: "negotiate",
    scene: "s1",
    route: "/verdict",
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
      recordNegotiation(await negotiate(id, { buyer_profile: "hard_line" }));
    },
  },
  { id: "router", scene: "s2", route: "/funding", run: async () => void (await planFunding()) },
  { id: "ledger2", scene: "s2", route: "/ledger", run: async () => bump() },
  {
    id: "reworded",
    scene: "s2",
    route: "/verdict",
    run: async () => {
      const id = await submitSample("EX01B");
      await evaluate(id);
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
