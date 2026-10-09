/**
 * Mock POST /nl. A handful of scripted conversations, each reply recorded from the real API
 * (`mocks/nl_script.json`, LLM_MODE=cache, golden_sme books at day 0). Matching is a short list of regular
 * expressions plus one piece of state per session (what is waiting for "go ahead"), which is enough to
 * replay the demo conversations: evaluate, confirm, correct, clarify, refuse, and the FastCapital message.
 * Nothing here computes money; every amount is inside a recorded string.
 */

import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import type { NlRequest, NlResponse } from "../types";
import approveChat from "../../mocks/home_approve_chat.json";
import page from "../../mocks/nl_page.json";
import script from "../../mocks/nl_script.json";
import { appendRecorded, decideApproval, ensureHomeApproval, getApprovals } from "./handlers";
import { markDealAgreed } from "./documents";
import { markFunded, mockOpenerAnswer, openerWaiting, readPoint } from "./home";

type Key = keyof typeof script;
type Recorded = Omit<NlResponse, "session_id">;

interface Session {
  turn: number;
  /** The scripted reply whose plan is waiting for the owner's confirmation. */
  pending: Key | null;
  clarifying: boolean;
  /** Language of the last reply, so a bare "1" answering a Chinese question stays Chinese. */
  zh: boolean;
}

const sessions = new Map<string, Session>();

const CJK = /[㐀-鿿]/;
const CONFIRM = /^\s*(go ahead|yes|proceed|do it|send the counters|approve|执行|确认|好的?|是)\s*[.!。]*\s*$/i;
const CANCEL = /^\s*(cancel|no|stop|取消|算了|不要)\s*[.!。]*\s*$/i;

/**
 * The questions the Business pages suggest, replayed from what the real API answered (mocks/nl_page.json; the match is the
 * server's closed grammar, in miniature). The deal questions are about the deal the page evaluated, so they need the page's
 * context to name an offer, as the server does; the others are read from the books at the point of the story the mock is at.
 */
const DEAL_READS: [RegExp, keyof typeof page.deals][] = [
  [/original terms|原始条款/i, "original"],
  [/option\s+[a-d]\b|方案\s?[a-d]/i, "option"],
  [/why.*counter|为什么要还价/i, "explain"],
];
const POINT_READS: [RegExp, keyof typeof page.day0][] = [
  [/what changed|what['’]s new|since my last visit|有什么变化/i, "changes"],
  [/waiting for|在等什么/i, "waiting"],
  [/when does the money arrive|什么时候到账/i, "arrival"],
  [/what is overdue|chase first|先催|逾期/i, "overdue"],
  [/payment is late|款项延迟/i, "late"],
  [/choose this plan|选这个方案/i, "plan"],
];

function pageRead(req: NlRequest): Recorded | null {
  if (req.actor !== "OWNER") return null;
  const q = req.text.trim();
  const echo = req.context?.offer_id ? (page.deals.explain.context_echo as NlResponse["context_echo"]) : null;
  const deal = req.context?.offer_id ? DEAL_READS.find(([re]) => re.test(q)) : undefined;
  const recorded = deal ? page.deals[deal[1]] : (() => {
    const hit = POINT_READS.find(([re]) => re.test(q));
    return hit ? page[readPoint()][hit[1]] : null;
  })();
  return recorded ? ({ ...(JSON.parse(JSON.stringify(recorded)) as Recorded), context_echo: echo }) : null;
}

function pick(req: NlRequest, s: Session): Key | null {
  const q = req.text.trim();
  if (req.actor === "COUNTERPARTY") {
    if (req.counterparty_id === "FASTCAPITAL" || /fastcapital/i.test(q)) return "fastcapital";
    if (/忽略|ignore your/i.test(q)) return CJK.test(q) ? "buyer_injection_zh" : null;
    if (/reserve|credit line limit|payment terms|储备|授信/i.test(q)) return CJK.test(q) ? "buyer_extraction_zh" : "buyer_extraction";
    if (/rebate|agreed last month/i.test(q)) return "buyer_rebate";
    if (/early|1\.5\s?%|pay this one/i.test(q)) return "buyer_ex02";
    return null;
  }
  if (s.clarifying) {
    if (/^1$|status|cash status/i.test(q)) return "status";
    if (/^2$|fund|gap/i.test(q)) return "fund_gap";
    if (/^3$|early|paid/i.test(q)) return "goal";
  }
  if (s.pending && CANCEL.test(q)) return "cancel";
  if (s.pending && CONFIRM.test(q)) return s.pending === "evaluate_ex01" ? "negotiate_ex01" : s.pending === "fund_gap" ? "fund_gap_go" : "goal_go";
  if (s.pending === "goal") {
    if (/invoice financing|发票融资/i.test(q)) return "amend_fin";
    if (/0\.8\s?%/.test(q)) return "amend_08";
    if (/\b1\s?%/.test(q)) return "amend_1_refused";
  }
  if (/\bex01\b/i.test(q)) return "evaluate_ex01";
  if (/why|explain|为什么|为何|解释/i.test(q)) return CJK.test(q) ? "explain_zh" : "explain_en";
  if (/get paid early|paid early|提前收款/i.test(q)) return "goal";
  if (/sort out|figure out our cash|资金问题/i.test(q)) return "clarify_cash";
  if (/fund|gap|缺口|补足/i.test(q)) return "fund_gap";
  if (/status|cash position|where we stand|状态|现金/i.test(q)) return "status";
  if (/guarantee|pledge|equity|mandate|抵押|担保|股权/i.test(q)) return "tier3";
  if (/approve|批准/i.test(q)) return "approve_none";
  if (/flight|joke|weather|笑话/i.test(q)) return "out_of_scope";
  return null;
}

function fallback(req: NlRequest): Recorded {
  const zh = CJK.test(req.text);
  const counterparty = req.actor === "COUNTERPARTY";
  return {
    turn: 0,
    reply: zh
      ? "模拟模式只重放几段录制好的对话。可以试试：评估 EX01、状态、补足资金缺口。连接真实 API 后可以自由提问。"
      : counterparty
        ? "Mock mode replays only a few recorded buyer messages. Try the suggested prompts, or switch to live mode."
        : "Mock mode replays only a few recorded conversations. Try: Evaluate EX01, status, fund the cash gap. Switch to live mode for free-form requests.",
    intent: counterparty ? "COUNTERPARTY_MESSAGE" : "OUT_OF_SCOPE",
    lang: zh ? "zh" : "en",
    plan: [],
    verdict: null,
    operations: [],
    clarification: null,
    awaiting_confirmation: false,
    amended: false,
    replayed: false,
    negotiation: null,
    security_events: [],
    parse_source: "mock",
    trace_id: "mock",
  };
}

export async function mockNl(req: NlRequest): Promise<NlResponse> {
  // The real gate: owner turns need a token, counterparty turns are open. Any non-empty token passes in mock mode.
  if (req.actor === "OWNER" && !getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required (401). Sign in with the owner token to use this.", undefined, "owner_required");
  }
  const sid = req.session_id ?? "mock-session";
  const s = sessions.get(sid) ?? { turn: 0, pending: null, clarifying: false, zh: false };
  // The agent's opener left a cure waiting in this session: "go ahead" runs it (recorded), "cancel" drops it.
  if (req.actor === "OWNER" && openerWaiting(sid) && (CONFIRM.test(req.text) || CANCEL.test(req.text))) {
    const confirm = CONFIRM.test(req.text);
    const ran = mockOpenerAnswer(sid, confirm);
    const recorded: Recorded = ran ?? (JSON.parse(JSON.stringify(script.cancel)) as Recorded);
    if (ran) {
      // As live: "go ahead" queues the cure (PENDING_APPROVAL) once; the same turn again changes nothing.
      const first = !(await getApprovals()).some((a) => a.op_id?.startsWith("alert:"));
      ensureHomeApproval();
      if (first) for (const o of ran.operations) appendRecorded({ kind: o.kind, status: o.status, tier: o.tier, message: o.message, day: 34 });
    }
    s.turn += 1;
    s.pending = null;
    s.clarifying = false;
    sessions.set(sid, s);
    return { ...recorded, session_id: sid, turn: s.turn, trace_id: `${sid}:${s.turn}` };
  }
  // "approve APR-…" while the day-34 cure waits: the owner's exact decision runs it (recorded). Any other mention changes nothing.
  const approveId = req.actor === "OWNER" ? /^\s*approve\s+(APR-[A-Z0-9]+)\s*[.!]?\s*$/i.exec(req.text)?.[1].toUpperCase() : undefined;
  if (approveId) {
    const held = (await getApprovals()).find((a) => a.id === approveId && a.status === "PENDING" && a.op_id?.startsWith("alert:"));
    if (held) {
      await decideApproval(held.id, "APPROVE");
      s.turn += 1;
      s.pending = null;
      s.clarifying = false;
      sessions.set(sid, s);
      return { ...(JSON.parse(JSON.stringify(approveChat)) as Recorded), session_id: sid, turn: s.turn, trace_id: `${sid}:${s.turn}` };
    }
  }
  const asked = pageRead(req);
  if (asked) {
    s.turn += 1;
    s.pending = null;
    s.clarifying = false;
    sessions.set(sid, s);
    return { ...asked, session_id: sid, turn: s.turn, trace_id: `${sid}:${s.turn}` };
  }
  const base = pick(req, s);
  // A Chinese request replays the Chinese recording of the same scenario when there is one.
  const zh = CJK.test(req.text) || (/^\d$/.test(req.text.trim()) && s.zh);
  const zhKey = base && !base.endsWith("_zh") ? (`${base}_zh` as Key) : null;
  const key = zh && zhKey && zhKey in script ? zhKey : base;
  const recorded = key ? (JSON.parse(JSON.stringify(script[key])) as Recorded) : fallback(req);
  s.turn += 1;
  s.zh = recorded.lang === "zh";
  s.clarifying = recorded.clarification !== null;
  const family = base?.startsWith("goal") || base?.startsWith("amend") ? "goal" : base;
  s.pending = recorded.awaiting_confirmation ? (family as Key) : null;
  sessions.set(sid, s);
  // The day-0 plan ran: the books now hold the draw as cash and the advance as funding in transit.
  if (key?.startsWith("fund_gap_go")) markFunded();
  // "go ahead" on EX01 agreed the deal with the buyer (recorded): the deal summary shows on Deals from now on, as live.
  if (key?.startsWith("negotiate_ex01")) markDealAgreed();
  // As live: a buyer's turn carries only the reply (the recorded buyer turns already have a null verdict; this stays as a guard).
  if (req.actor === "COUNTERPARTY") return { ...recorded, verdict: null, operations: [], security_events: [], session_id: sid, turn: s.turn, trace_id: `${sid}:${s.turn}` };
  return { ...recorded, session_id: sid, turn: s.turn, trace_id: `${sid}:${s.turn}` };
}
