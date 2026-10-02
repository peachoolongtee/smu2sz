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
import type { AlertActResult, AlertsView, ClockView, NlOpenerResponse, NlResponse } from "../types";
import act from "../../mocks/home_act.json";
import alertsAfter from "../../mocks/home_alerts_after.json";
import alertsDay34 from "../../mocks/home_alerts_day34.json";
import goAhead from "../../mocks/home_goahead.json";
import openerAfter from "../../mocks/home_opener_after_approve.json";
import openerDay34 from "../../mocks/home_opener_day34.json";
import openerDay34Zh from "../../mocks/home_opener_day34_zh.json";
import openerPending from "../../mocks/home_opener_pending.json";
import openerQuiet from "../../mocks/home_opener_quiet.json";
import openerQuietZh from "../../mocks/home_opener_quiet_zh.json";
import stateAfterApprove from "../../mocks/home_state_after_approve.json";
import stateDay34 from "../../mocks/home_state_day34.json";
import stateAfterFund from "../../mocks/state_after_fund.json";

/** The day the recording was taken on. */
export const NEWS_DAY = 34;
const KEY = "tl-mock-home-v2";

export type CureStage = "open" | "pending" | "approved";

interface HomeState {
  day: number;
  /** Where the reserve alert's cure stands. */
  stage: CureStage;
  /** The day-0 funding plan ("Fund the cash gap", then "go ahead") has run. */
  funded: boolean;
}

let memory: HomeState | null = null;

const fresh = (): HomeState => ({ day: 0, stage: "open", funded: false });

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

export function mockAlerts(): AlertsView | null {
  const s = load();
  if (s.day < NEWS_DAY) return null;
  const view = clone<AlertsView>(s.stage === "approved" ? alertsAfter : alertsDay34);
  return { ...view, day: s.day };
}

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
export function mockAct(id: string): AlertActResult {
  requireOwner();
  if (!newsIsOpen() || !id.startsWith("ALERT-RESERVE")) {
    throw new ApiError(409, "This alert suggests nothing the agent may execute.");
  }
  queueCure();
  return { ...clone<AlertActResult>(act), alert_id: id, day: load().day };
}
