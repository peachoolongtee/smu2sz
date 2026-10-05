/**
 * Mock for the owner home: the clock, the agent's opener, and "Let the agent fix this". A small fixed script
 * recorded from the real API on the demo path (`mocks/home_*.json`: deal, receipt on day 2, clock to day 34).
 * Before day 34 the opener has nothing for the owner to approve; from day 34 the opener has news and the reserve alert is actionable.
 * The cure (an advance of ¥200,000 on RI:BUYER-1:2) is above the yearly cost ceiling, so it goes through three stages, as live:
 * "open" (nothing asked), "pending" (the button or "go ahead" queued it: PENDING_APPROVAL, the alert stays open) and
 * "approved" (the owner approved it on the approval card or in the chat: it executed, the cash lands on day 37, the alert clears).
 * The state is a day counter, the stage and whether the day-0 funding plan ran. Nothing here computes money: every amount is a recorded string.
 */

import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import type { ActRequest, AlertActResult, AlertChangedDetail, AlertsView, ClockView, HomeView, NlOpenerResponse, NlResponse } from "../types";
import act from "../../mocks/home_act.json";
import actDay0 from "../../mocks/home_act_day0.json";
import summaryAfter from "../../mocks/home_summary_after.json";
import summaryAfterFund from "../../mocks/home_summary_after_fund.json";
import summaryDay0 from "../../mocks/home_summary_day0.json";
import summaryDay34 from "../../mocks/home_summary_day34.json";
import summaryPending from "../../mocks/home_summary_pending.json";
import summaryQuiet from "../../mocks/home_summary_quiet.json";
import alertsAfter from "../../mocks/home_alerts_after.json";
import alertsDay34 from "../../mocks/home_alerts_day34.json";
import alertsMandateExpired from "../../mocks/home_alerts_mandate_expired.json";
import alertsMandateWarning from "../../mocks/home_alerts_mandate_warning.json";
import goAhead from "../../mocks/home_goahead.json";
import openerAfter from "../../mocks/home_opener_after_approve.json";
import openerDay34 from "../../mocks/home_opener_day34.json";
import openerDay34Zh from "../../mocks/home_opener_day34_zh.json";
import openerPending from "../../mocks/home_opener_pending.json";
import openerQuiet from "../../mocks/home_opener_quiet.json";
import openerQuietZh from "../../mocks/home_opener_quiet_zh.json";
import reconciliationDay34 from "../../mocks/home_reconciliation_day34.json";
import stateAfterApprove from "../../mocks/home_state_after_approve.json";
import stateDay34 from "../../mocks/home_state_day34.json";
import stateAfterFund from "../../mocks/state_after_fund.json";

/** The day the recording was taken on. */
export const NEWS_DAY = 34;
const KEY = "tl-mock-home-v3";
/**
 * The mock variant of the 409 ALERT_CHANGED path. Set this sessionStorage key to "1" (the books move, the alert is still there
 * with its recorded cure) or "gone" (the books move and the alert no longer exists) just before pressing "Let the agent fix this":
 * the next act answers 409 ALERT_CHANGED, once, and the state_version the mock serves advances by one.
 */
export const MOVE_BOOKS_KEY = "tl-mock-books-moved";

export type CureStage = "open" | "pending" | "approved";

interface HomeState {
  day: number;
  /** Where the reserve alert's cure stands. */
  stage: CureStage;
  /** The day-0 funding plan ("Fund the cash gap", then "go ahead") has run. */
  funded: boolean;
  /** How many times the books moved behind the owner's back (the mock variant below): added to the recorded state_version. */
  moved: number;
}

let memory: HomeState | null = null;

const fresh = (): HomeState => ({ day: 0, stage: "open", funded: false, moved: 0 });

function load(): HomeState {
  if (memory) return memory;
  memory = fresh();
  if (typeof window !== "undefined") {
    try {
      const raw = window.sessionStorage.getItem(KEY);
      if (raw) memory = JSON.parse(raw) as HomeState;
    } catch {
      /* start from day 0 */
    }
  }
  return memory;
}

function save(): void {
  if (typeof window === "undefined" || !memory) return;
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    /* the in-memory state still works */
  }
}

/** Sessions whose opener left a cure waiting for "go ahead" (the server keeps this in the session). */
const waiting = new Set<string>();

const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

function requireOwner(): void {
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required (401). Sign in with the owner token to use this.");
  }
}

export function resetHome(): void {
  memory = fresh();
  save();
}

export function mockClock(): ClockView {
  return { day: load().day, message: null };
}

export function mockAdvance(days: number): ClockView {
  requireOwner();
  const s = load();
  const from = s.day;
  s.day += Math.max(1, Math.floor(days));
  save();
  return { day: s.day, message: `Clock moved from day ${from} to day ${s.day}` };
}

/** True while the recorded reserve alert exists (until the owner approves its cure). */
function newsIsOpen(): boolean {
  const s = load();
  return s.day >= NEWS_DAY && s.stage !== "approved";
}

/** The mandate's last day is 90: the alerts warn 14 days ahead (from day 76) and turn CRITICAL once it has passed. These two recordings were taken at day 80 and day 95. */
export const MANDATE_WARN_FROM_DAY = 76;
export const MANDATE_LAST_DAY = 90;

export function mockAlerts(): AlertsView | null {
  const s = load();
  if (s.day < NEWS_DAY) return null;
  const recorded =
    s.day > MANDATE_LAST_DAY ? alertsMandateExpired : s.day >= MANDATE_WARN_FROM_DAY ? alertsMandateWarning : s.stage === "approved" ? alertsAfter : alertsDay34;
  const view = clone<AlertsView>(recorded);
  return { ...view, day: s.day, state_version: view.state_version + s.moved };
}

/** GET /reconciliation once the day-2 bank receipt has been recorded (the home path reaches day 34 with it); null before. */
export function mockReconciliation(): unknown {
  return load().day >= NEWS_DAY ? clone(reconciliationDay34) : null;
}

const sameSuggestions = (a: ActRequest["suggestions"], b: ActRequest["suggestions"]): boolean =>
  a.length === b.length &&
  a.every(
    (x, i) =>
      x.operation_kind === b[i].operation_kind && x.facility_id === b[i].facility_id && x.receivable_id === b[i].receivable_id && x.amount_fen === b[i].amount_fen,
  );

export function mockOpener(sessionId: string | undefined, lang: "en" | "zh"): NlOpenerResponse {
  requireOwner();
  const s = load();
  const zh = lang === "zh";
  const recorded =
    s.day < NEWS_DAY
      ? zh
        ? openerQuietZh
        : openerQuiet
      : s.stage === "approved"
        ? openerAfter
        : s.stage === "pending"
          ? openerPending
          : zh
            ? openerDay34Zh
            : openerDay34;
  const sid = sessionId ?? "mock-session";
  waiting.delete(sid);
  if (recorded.awaiting_confirmation) waiting.add(sid);
  return { ...clone<NlOpenerResponse>(recorded), session_id: sid, trace_id: `${sid}:opener` };
}

/** The opener's own reply to "go ahead" / "cancel" in its session, or null when that session has no opener waiting. */
export function mockOpenerAnswer(sid: string, confirm: boolean): NlResponse | null {
  if (!waiting.has(sid)) return null;
  waiting.delete(sid);
  if (!confirm) return null;
  if (!newsIsOpen()) return null;
  queueCure();
  return { ...clone<NlResponse>(goAhead), session_id: sid, trace_id: `${sid}:go-ahead` };
}

/** True when the session's opener cure is waiting for an answer. */
export function openerWaiting(sid: string): boolean {
  return waiting.has(sid);
}

/** True when the opener's cure is waiting for "go ahead" (the day-34 reserve alert is open). */
export function openerHasCure(): boolean {
  return newsIsOpen();
}

/** The cure was queued for the owner's approval (the button, or "go ahead"). Nothing has run. */
export function queueCure(): void {
  const s = load();
  if (s.stage === "open") s.stage = "pending";
  save();
}

/** The owner approved the queued cure: it executed and the alert is gone. */
export function markApproved(): void {
  load().stage = "approved";
  save();
}

export function cureStage(): CureStage {
  return load().stage;
}

/**
 * GET /home for this point of the story, recorded from the real API: the opening books (the fix can run alone), the quiet
 * books after the deal, the books after the day-0 plan ran (funding in transit), day 34 with the late invoice (the fix
 * needs approval), the queued fix, and the approved fix. `dealt` says whether the Scene 1 deal was made in this session.
 */
export function mockHome(dealt: boolean): HomeView {
  const s = load();
  const recorded =
    s.day >= NEWS_DAY
      ? s.stage === "approved"
        ? summaryAfter
        : s.stage === "pending"
          ? summaryPending
          : summaryDay34
      : s.funded
        ? summaryAfterFund
        : dealt
          ? summaryQuiet
          : summaryDay0;
  const view = clone<HomeView>(recorded);
  return { ...view, day: s.day, state_version: view.state_version + s.moved };
}

/** The day-0 fix (the line draw and the invoice advance) runs alone: the recorded answer, and the books are then "funded". */
export function mockActDay0(): AlertActResult {
  requireOwner();
  const s = load();
  if (s.day >= NEWS_DAY || s.funded) {
    throw new ApiError(409, "This alert suggests nothing the agent may execute.", { code: "NO_EXECUTABLE_CURE", alert_id: "ALERT-RESERVE-12" });
  }
  s.funded = true;
  save();
  return { ...clone<AlertActResult>(actDay0), day: s.day };
}

/** The day-0 funding plan ran in the chat. */
export function markFunded(): void {
  load().funded = true;
  save();
}

/** The recorded books for this point of the story: after the approved cure, at day 34, after the day-0 plan, or null for the opening books. */
export function mockStateJson(): unknown {
  const s = load();
  if (s.day >= NEWS_DAY) return s.stage === "approved" ? stateAfterApprove : stateDay34;
  return s.funded ? stateAfterFund : null;
}

/** POST /alerts/{id}/act. Only the recorded reserve alert has a cure; others answer 409 like the server. The cure waits for the owner's approval (PENDING_APPROVAL). */
export function mockAct(id: string, bound: ActRequest): AlertActResult {
  requireOwner();
  // The books move behind the owner's back (the mock variant): the version advances, and the act below is bound to the old one.
  let variant: string | null = null;
  if (typeof window !== "undefined") {
    try {
      variant = window.sessionStorage.getItem(MOVE_BOOKS_KEY);
      if (variant) window.sessionStorage.removeItem(MOVE_BOOKS_KEY);
    } catch {
      /* no storage: no variant */
    }
  }
  if (variant) {
    load().moved += 1;
    save();
  }
  const current = mockAlerts();
  const alert = current?.alerts.find((a) => a.id === id) ?? null;
  const shown = alert?.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen }));
  const version = current ? current.state_version : bound.state_version;
  if (bound.state_version !== version || (shown !== undefined && !sameSuggestions(bound.suggestions, shown))) {
    const detail: AlertChangedDetail = {
      code: "ALERT_CHANGED",
      alert_id: id,
      state_version: version,
      message: "The alert changed since you read it; nothing was run. Review the current cure.",
      alert: variant === "gone" ? null : alert,
    };
    throw new ApiError(409, detail.message, detail);
  }
  if (!newsIsOpen() || !id.startsWith("ALERT-RESERVE")) {
    throw new ApiError(409, "This alert suggests nothing the agent may execute.", { code: "NO_EXECUTABLE_CURE", alert_id: id });
  }
  queueCure();
  return { ...clone<AlertActResult>(act), alert_id: id, day: load().day };
}
