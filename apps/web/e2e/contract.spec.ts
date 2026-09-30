import { expect, test } from "@playwright/test";
import { setOwnerToken } from "../lib/auth";
import { live } from "../lib/live";
import type { VerdictView } from "../lib/types";

/**
 * Contract tests for the live adapters, run in Node against the real API (live project only). They call the
 * same `live` client the browser uses, so a change in a server response shape fails here with a readable diff
 * instead of as a blank screen.
 */

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  setOwnerToken("demo-owner-token"); // the adapters read the token the sign-in dialog would have stored
  await live.demoReset();
});

test("trajectory adapter: the position today, then the offer applied", async () => {
  const today = await live.getTrajectory("CONSERVATIVE");
  expect(today.floor.min_cash_display).toBe("¥300,000.00");
  expect(today.trajectory.days).toHaveLength(121);
  expect(today.trajectory.horizon_days).toBe(120);
  expect(today.trajectory.months[0].ebitda_display).toBe("¥90,000.00");
  expect(today.cured_trajectory).toBeNull();
  expect(today.forward_concession.parts).toEqual([]);

  const offer = await live.submitOffer({ fixture_id: "EX01_PACKAGE" });
  const verdict: VerdictView = await live.evaluateOffer(offer.offer.offer_id, "EX01_PACKAGE");
  expect(verdict.outcome).toBe("REJECT");

  const view = await live.getTrajectory("CONSERVATIVE", verdict);
  expect(view.trajectory.min_cash_display).toBe("¥254,960.00");
  expect(view.trajectory.min_cash_day).toBe(47);
  expect(view.trajectory.first_breach_day).toBe(47);
  expect(view.shortfall_display).toBe("¥45,040.00");
  expect(view.forward_concession).toMatchObject({ total_display: "¥26,455.62", cap_display: "¥5,000.00", over_cap: true });
  expect(view.forward_concession.parts.map((p) => p.value_display)).toEqual(["¥22,455.62", "¥4,000.00"]);
  expect(view.trajectory.months[0]).toMatchObject({ dscr: { text: "2.00" }, leverage: { text: "1.39" } });
  // The pro forma 1.92x / 1.72x (extension funded) live in the verdict's own checks, not in the month table.
  expect(verdict.summary).toContain("DSCR_MIN 1.92x");
  expect(view.covenant_limits).toEqual({ min_dscr_display: "1.25×", max_leverage_display: "2.50×" });
  // Integer fen rides along for chart axes only.
  expect(view.trajectory.days[47].closing_fen).toBe(25496000);
  expect(view.trajectory.days[47].closing_display).toBe("¥254,960.00");
});

test("funding, negotiation and ledger adapters keep the golden numbers and fill the operation fields", async () => {
  const plan = await live.planFunding({});
  expect(plan.committed.total_cost_display).toBe("¥2,712.94");
  expect(plan.marginal.rate_display).toBe("10.8417%");

  await live.demoReset();
  const offer = await live.submitOffer({ fixture_id: "EX01_PACKAGE" });
  await live.evaluateOffer(offer.offer.offer_id, "EX01_PACKAGE");
  const neg = await live.negotiate(offer.offer.offer_id, { buyer_profile: "hard_line" });
  expect(neg.outcome).toBe("NO_DEAL");
  expect(neg.plan?.total_cost_display).toBe("¥2,712.94");
  for (const op of neg.operations) {
    expect(op.summary).not.toBe("");
    expect(op.day).toBe(0);
  }
  const ledger = await live.getLedger();
  expect(ledger.chain_valid).toBe(true);
  expect(ledger.operations.map((o) => o.kind)).toEqual(["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]);
});

test("approvals adapter: capex and borrower file queue as Tier 2, and the owner token decides", async () => {
  await live.demoReset();
  const capex = await live.capexEvaluate({ label: "machine", price_fen: 60000000 });
  expect(capex.npv_display).toBe("¥380,885.77");
  const selected = capex.structures.find((s) => s.id === capex.selected_id);
  expect(selected?.facility_id).toBe("FAC-ETL");

  const file = await live.borrowerFile({ facility_id: "FAC-ETL", amount_fen: 60000000, use_of_proceeds: "Purchase of production equipment" });
  expect(file.status).toBe("PREPARED_NOT_SENT");
  expect(file.downloads?.html).toBe(`/borrower-file/${file.file_id}.html`);
  expect(file.downloads?.docx).toBe(`/borrower-file/${file.file_id}.docx`);

  const queue = await live.getApprovals();
  expect(queue.map((a) => [a.tier, a.status])).toEqual([
    ["TIER_2", "PENDING"],
    ["TIER_2", "PENDING"],
  ]);
  expect(queue[0].subject).toMatch(/FAC-ETL/);

  const decided = await live.decideApproval(queue[0].id, "APPROVE");
  expect(decided.status).toBe("APPROVED");
  const rejected = await live.decideApproval(queue[1].id, "REJECT");
  expect(rejected.status).toBe("REJECTED");
});

test("alerts and reconciliation adapters", async () => {
  await live.demoReset();
  const alerts = await live.getAlerts();
  expect(alerts.counts.CRITICAL).toBe(1);
  expect(alerts.alerts[0]).toMatchObject({ day: 12, committed_cure: true, amount_display: "¥240,000.00" });
  expect(alerts.alerts[0].suggested.every((s) => s.executes_automatically === false)).toBe(true);

  const recon = await live.getReconciliation();
  expect(recon.outstanding[0]).toMatchObject({ receivable_id: "RCV-A", face_display: "¥420,000.00" });
  expect(recon.chain_valid).toBe(true);
});

test("/nl degrades gracefully when the route does not exist yet", async () => {
  const res = await live.nl({ actor: "OWNER", text: "Can we buy the ¥600k machine?" });
  // Either the server already has /nl (a real reply with a session) or the adapter reports it as unavailable.
  if (res.intent === "NL_UNAVAILABLE") {
    expect(res.operations).toEqual([]);
    expect(res.reply).toMatch(/not available/i);
  } else {
    expect(res.session_id).toBeTruthy();
    expect(typeof res.reply).toBe("string");
  }
});
