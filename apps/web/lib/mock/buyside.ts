/**
 * Mock for the buy side (ADR-0013, docs/capex_handover.md). Serves mocks/buyside/*.json, recorded from the live API with
 * FEATURE_CAPEX_CONTRACTS=1 (scripts/record-mocks.mjs --buyside): the demo capex contract read and confirmed (the recording's
 * DOC-000004), screened on three timelines, committed and approved; financial health, loan eligibility and a two-project plan.
 *
 * The mock keeps one small state, the purchase's stage (ready, then awaiting the owner once committed here), in sessionStorage
 * like the documents mock. Nothing here computes money or reads a contract: a timeline other than the three recorded is answered
 * with the recording nearest to it, and the page says the figures are the recorded ones.
 */

import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import type {
  AddToMenuResult,
  BuySideEvaluationView,
  BuyTimeline,
  CapexPlansRequest,
  CapexPlansView,
  ContractFixture,
  EligibilityView,
  FinanceHealthView,
  HealthInputsRequest,
  PurchaseCommitResult,
  PurchaseRow,
  PurchasesView,
} from "../types";
import addToMenuJson from "../../mocks/buyside/add_to_menu.json";
import commitJson from "../../mocks/buyside/commit.json";
import eligibility48Json from "../../mocks/buyside/eligibility_48.json";
import eligibilityJson from "../../mocks/buyside/eligibility.json";
import evaluateDay7Json from "../../mocks/buyside/evaluate_day7.json";
import evaluateJson from "../../mocks/buyside/evaluate.json";
import evaluateNeedsJson from "../../mocks/buyside/evaluate_needs.json";
import fixturesJson from "../../mocks/buyside/fixtures.json";
import healthInputsJson from "../../mocks/buyside/health_inputs.json";
import healthJson from "../../mocks/buyside/health.json";
import plansJson from "../../mocks/buyside/plans.json";
import awaitingJson from "../../mocks/buyside/purchases_awaiting.json";
import committedJson from "../../mocks/buyside/purchases_committed.json";
import readyJson from "../../mocks/buyside/purchases_ready.json";

type Stage = "ready" | "awaiting" | "committed";
type ByLang = { en: PurchasesView; zh: PurchasesView };
const KEY = "termsledger.mock.buyside";
const RECORDINGS: Record<Stage, ByLang> = {
  ready: readyJson as unknown as ByLang,
  awaiting: awaitingJson as unknown as ByLang,
  committed: committedJson as unknown as ByLang,
};
let memory: Stage | null = null;

const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

function stage(): Stage {
  if (memory) return memory;
  memory = "ready";
  if (typeof window !== "undefined") {
    try {
      const raw = window.sessionStorage.getItem(KEY);
      if (raw === "ready" || raw === "awaiting" || raw === "committed") memory = raw;
    } catch {
      /* the in-memory stage still works */
    }
  }
  return memory;
}

function setStage(s: Stage): void {
  memory = s;
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(KEY, s);
  } catch {
    /* the in-memory stage still works */
  }
}

/** Back to the recording's starting point (the demo reset). */
export function resetBuyside(): void {
  setStage("ready");
}

/** The owner approved the recorded commitment (the approvals mock calls this). */
export function markPurchaseApproved(): void {
  setStage("committed");
}

function requireOwner(): void {
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required (401). Sign in with the owner token to use this.");
  }
}

const delay = () => new Promise((r) => setTimeout(r, 120));

export async function getPurchases(lang: "en" | "zh" = "en"): Promise<PurchasesView> {
  await delay();
  requireOwner();
  return clone(RECORDINGS[stage()][lang]);
}

export async function getPurchase(id: string, lang: "en" | "zh" = "en"): Promise<PurchaseRow> {
  const rows = (await getPurchases(lang)).purchases;
  const row = rows.find((r) => r.document_id === id);
  if (!row) throw new ApiError(404, `no capex contract ${id}`);
  return row;
}

export async function getCapexContractFixtures(): Promise<ContractFixture[]> {
  await delay();
  requireOwner();
  return clone(fixturesJson);
}

/** The recording nearest the timeline asked: the full timeline, the contract's own signing date, or none. */
export async function evaluateContract(id: string, timeline: BuyTimeline): Promise<BuySideEvaluationView> {
  await delay();
  requireOwner();
  void id;
  const recorded =
    timeline.delivery_day == null || timeline.acceptance_day == null ? evaluateNeedsJson : timeline.signing_day == null ? evaluateDay7Json : evaluateJson;
  return clone(recorded);
}

export async function commitContract(id: string, timeline: BuyTimeline, scheduleHash: string, takeEarlyPay: boolean): Promise<PurchaseCommitResult> {
  await delay();
  requireOwner();
  void id;
  void timeline;
  void takeEarlyPay;
  const recorded = clone<PurchaseCommitResult>(commitJson);
  if (scheduleHash !== recorded.schedule.schedule_hash && scheduleHash !== clone<BuySideEvaluationView>(evaluateJson).early_pay_schedule?.schedule_hash) {
    throw new ApiError(409, "the payment schedule is not the one shown; evaluate again and commit what is shown", { code: "SCHEDULE_CHANGED" });
  }
  setStage("awaiting");
  return recorded;
}

export async function getFinanceHealth(inputs: HealthInputsRequest | null = null): Promise<FinanceHealthView> {
  await delay();
  requireOwner();
  return clone(inputs ? healthInputsJson : healthJson);
}

export async function getEligibility(inputs: { months_trading?: number | null; amount_fen?: number | null } | null = null): Promise<EligibilityView> {
  await delay();
  requireOwner();
  return clone(inputs?.months_trading ? eligibility48Json : eligibilityJson);
}

export async function addProductToMenu(productId: string, amountFen: number | null = null): Promise<AddToMenuResult> {
  await delay();
  requireOwner();
  void amountFen;
  const recorded = clone<AddToMenuResult & { eligibility?: unknown }>(addToMenuJson);
  if (productId !== "PRD-BANK1-TERM-60") throw new ApiError(422, "The mock holds the recorded term loan only; use live mode for other products.");
  return recorded;
}

export async function runCapexPlans(req: CapexPlansRequest): Promise<CapexPlansView> {
  await delay();
  requireOwner();
  void req;
  return clone(plansJson);
}
