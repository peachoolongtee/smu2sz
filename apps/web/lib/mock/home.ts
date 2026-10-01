/**
 * Mock for the owner home: the clock, the agent's opener, and "Let the agent fix this". A small fixed script
 * recorded from the real API on the demo path (`mocks/home_*.json`: deal, receipt on day 2, clock to day 34).
 * Before day 34 nothing needs the owner; from day 34 the opener has news and the reserve alert is actionable,
 * until it is cured (by "go ahead" in the opener's session or by the alert's own button).
 * The only state is a day counter and one flag. Nothing here computes money: every amount is a recorded string.
 */

import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import type { AlertActResult, AlertsView, ClockView, NlOpenerResponse, NlResponse } from "../types";
import act from "../../mocks/home_act.json";
import alertsAfter from "../../mocks/home_alerts_after.json";
import alertsDay34 from "../../mocks/home_alerts_day34.json";
import goAhead from "../../mocks/home_goahead.json";
import openerAfter from "../../mocks/home_opener_after_act.json";
import openerDay34 from "../../mocks/home_opener_day34.json";
import openerDay34Zh from "../../mocks/home_opener_day34_zh.json";
import openerQuiet from "../../mocks/home_opener_quiet.json";
import openerQuietZh from "../../mocks/home_opener_quiet_zh.json";

/** The day the recording was taken on. */
export const NEWS_DAY = 34;
const KEY = "tl-mock-home-v1";

interface HomeState {
  day: number;
  /** The reserve alert's cure has been executed. */
  cured: boolean;
}

let memory: HomeState | null = null;

function load(): HomeState {
  if (memory) return memory;
  memory = { day: 0, cured: false };
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
  memory = { day: 0, cured: false };
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

/** True while the recorded reserve alert exists. */
function newsIsOpen(): boolean {
  const s = load();
  return s.day >= NEWS_DAY && !s.cured;
}

export function mockAlerts(): AlertsView | null {
  const s = load();
  if (s.day < NEWS_DAY) return null;
  const view = clone<AlertsView>(s.cured ? alertsAfter : alertsDay34);
  return { ...view, day: s.day };
}

export function mockOpener(sessionId: string | undefined, lang: "en" | "zh"): NlOpenerResponse {
  requireOwner();
  const s = load();
  const zh = lang === "zh";
  const recorded = s.day < NEWS_DAY ? (zh ? openerQuietZh : openerQuiet) : s.cured ? openerAfter : zh ? openerDay34Zh : openerDay34;
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
  markCured();
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

export function markCured(): void {
  load().cured = true;
  save();
}

/** POST /alerts/{id}/act. Only the recorded reserve alert has a cure; others answer 409 like the server. */
export function mockAct(id: string): AlertActResult {
  requireOwner();
  if (!newsIsOpen() || !id.startsWith("ALERT-RESERVE")) {
    throw new ApiError(409, "This alert suggests nothing the agent may execute.");
  }
  markCured();
  return { ...clone<AlertActResult>(act), alert_id: id, day: load().day };
}
