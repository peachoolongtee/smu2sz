"use client";

/**
 * Conversation state for the chat page and the slide-over panel (they share it, so a conversation started in
 * one continues in the other). One conversation per role: the owner's and a buyer's are different channels
 * with different sessions. The server keeps the session (pending plan, clarification); this store keeps what
 * to show and the session id. It never interprets money: replies and amounts are rendered as received.
 *
 * A reset is a fresh conversation everywhere (owner report, 17 Oct): "New conversation" drops the transcript, the session id, the draft
 * and the failed turn here and ends the session on the server (POST /nl/session/reset); replaced books (a demo reset, the story's
 * restore, Set up your books; lib/books-epoch.ts) drop both conversations in every tab, the server having ended every session itself;
 * signing out ends the owner's session with the token that is going and drops both conversations and the draft.
 */

import { endNlSession, nl, nlOpener } from "./api";
import { getOwnerToken, onSignedIn, onSignedOut, onSigningOut } from "./auth";
import { booksEpoch, onBooksReplaced } from "./books-epoch";
import { getLang } from "./i18n";
import { getMode, shellFor } from "./mode";
import { nlContext } from "./chat-context";
import { currentScope, toNlScope } from "./chat-scope-model";
import type { ScopeKind } from "./selection";
import { ApiError } from "./errors";
import { errorMessage } from "./error-text";
import { createStore } from "./create-store";
import type { NlActor, NlResponse } from "./types";

export const COUNTERPARTIES = ["BUYER-1", "BUYER-2", "FASTCAPITAL"] as const;
export type CounterpartyId = (typeof COUNTERPARTIES)[number];

export type ChatMessage =
  | { id: string; from: "user"; text: string }
  /** `restored`: read back from the browser after a refresh; its buttons are history, and a pending plan or approval lives on the Approvals page. */
  | { id: string; from: "assistant"; response: NlResponse; restored?: boolean; asked?: { kind: ScopeKind } }
  | { id: string; from: "error"; text: string; status: number };

interface Conversation {
  /** Null until the first turn; then the id the server answered with. */
  sessionId: string | null;
  messages: ChatMessage[];
  busy: boolean;
  /** Bumped by "New conversation" so a late answer to the old one is dropped. */
  generation: number;
  /** FLOW's opener (POST /nl/opener) was asked for this conversation: it is asked once per conversation, never twice. */
  openerTried?: boolean;
}

interface ChatState {
  role: NlActor;
  counterpartyId: CounterpartyId;
  panelOpen: boolean;
  convs: Record<NlActor, Conversation>;
  /** The books marker (lib/books-epoch.ts) this conversation was held under: a different one on load means the books were replaced since. */
  booksEpoch: string | null;
}

const empty = (generation = 0): Conversation => ({ sessionId: null, messages: [], busy: false, generation, openerTried: false });

/** How many turns a refresh brings back (the server keeps the session; this is what the panel shows again). */
const KEEP_TURNS = 12;

/**
 * The owner's conversation survives a refresh in this tab (sessionStorage `tl-chat-session`): the session id, so the next turn
 * continues the same server session, and the last turns, marked `restored`. The buyer's role-play, the open panel, a turn in
 * flight and errors are not kept. It goes with the sign-out (below).
 */
const store = createStore<ChatState>(
  {
    role: "OWNER",
    counterpartyId: "BUYER-1",
    panelOpen: false,
    convs: { OWNER: empty(), COUNTERPARTY: empty() },
    booksEpoch: null,
  },
  {
    storage: "session",
    key: "tl-chat-session",
    sanitize: (s) => ({
      ...s,
      role: "OWNER",
      panelOpen: false,
      convs: {
        OWNER: {
          sessionId: s.convs.OWNER.sessionId,
          busy: false,
          generation: 0,
          openerTried: s.convs.OWNER.openerTried ?? false,
          messages: s.convs.OWNER.messages
            .filter((m) => m.from !== "error")
            .slice(-KEEP_TURNS)
            .map((m): ChatMessage => (m.from === "assistant" ? { ...m, restored: true } : m)),
        },
        COUNTERPARTY: empty(),
      },
    }),
  },
);

/** The half-typed message (sessionStorage `tl-chat-draft`), kept across a refresh and shared by the panel and the chat page. */
const draftStore = createStore<{ text: string }>({ text: "" }, { storage: "session", key: "tl-chat-draft" });

export const useDraft = (): string => draftStore.useValue().text;

export function setDraft(text: string): void {
  draftStore.set({ text });
}

export const useChat = store.useValue;

let counter = 0;
const uid = (p: string) => `${p}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

/** Session ids match the API's ^[A-Za-z0-9_.:-]{1,64}$. */
function newSessionId(): string {
  const r = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36);
  return `web-${r}`;
}

function patchConv(role: NlActor, fn: (c: Conversation) => Conversation): void {
  store.set((s) => ({ ...s, convs: { ...s.convs, [role]: fn(s.convs[role]) } }));
}

/** Whether the page the owner is on shows the Business shell: its chat then asks for the owner's wording (no ids, no tier words). */
function onBusinessShell(): boolean {
  return typeof window !== "undefined" && shellFor(window.location.pathname, getMode()) === "business";
}

interface Attempt {
  role: NlActor;
  counterpartyId: CounterpartyId;
  text: string;
  requestId: string;
}

/** The last failed attempt per role, kept so Retry resends the same text under the same request_id (replay-safe). */
const failed: Partial<Record<NlActor, Attempt>> = {};

async function run(a: Attempt): Promise<NlResponse | null> {
  const conv = store.get().convs[a.role];
  const sessionId = conv.sessionId ?? newSessionId();
  const generation = conv.generation;
  patchConv(a.role, (c) => ({ ...c, sessionId, busy: true }));
  // What the question is about: the scope shown before it was asked (the address, as the owner narrowed it), and nothing from an earlier page.
  const scope = a.role === "OWNER" ? currentScope() : null;
  const started = typeof performance !== "undefined" ? performance.now() : 0;
  try {
    const response = await nl({
      session_id: sessionId,
      actor: a.role,
      counterparty_id: a.role === "COUNTERPARTY" ? a.counterpartyId : undefined,
      text: a.text,
      lang: getLang(),
      request_id: a.requestId,
      // The owner's page (the route and the last visit) and the scope itself. A buyer's turn names none.
      context: scope ? nlContext() : undefined,
      scope: scope ? toNlScope(scope) : undefined,
    }, { business: a.role === "OWNER" && onBusinessShell() });
    logDuration(a, scope?.kind ?? null, started, "answered");
    delete failed[a.role];
    patchConv(a.role, (c) =>
      c.generation !== generation ? c : { ...c, busy: false, sessionId: response.session_id, messages: [...c.messages, { id: uid("a"), from: "assistant", response, ...(scope ? { asked: { kind: scope.kind } } : {}) }] },
    );
    return response;
  } catch (e) {
    logDuration(a, scope?.kind ?? null, started, "failed");
    failed[a.role] = a;
    const status = e instanceof ApiError ? e.status : 0;
    const text = errorMessage(e);
    patchConv(a.role, (c) => (c.generation !== generation ? c : { ...c, busy: false, messages: [...c.messages, { id: uid("e"), from: "error", text, status }] }));
    return null;
  }
}

/**
 * How long a turn took, in the console, in development only (ticket #130: the six-customer question timed out once in the audit, UX35, and is to be measured before anything is
 * diagnosed). The request id and the scope's kind say which turn it was; no text, no figure.
 */
function logDuration(a: Attempt, kind: string | null, started: number, outcome: "answered" | "failed"): void {
  if (process.env.NODE_ENV === "production" || typeof performance === "undefined") return;
  console.info(`[ask-flow] ${outcome} in ${Math.round(performance.now() - started)} ms (request ${a.requestId}, scope ${kind ?? "none"})`);
}

/**
 * Sends one turn in the current role's conversation. `display` is what the bubble shows when it differs from
 * what is sent (a clarification option shows its label and sends its id).
 */
export async function sendMessage(text: string, display?: string, role: NlActor = store.get().role): Promise<void> {
  await sendTurn(role, text, display);
}

async function sendTurn(role: NlActor, text: string, display?: string): Promise<NlResponse | null> {
  const s = store.get();
  const conv = s.convs[role];
  const trimmed = text.trim();
  if (!trimmed || conv.busy) return null;
  patchConv(role, (c) => ({ ...c, messages: [...c.messages, { id: uid("u"), from: "user", text: display ?? trimmed }] }));
  return run({ role, counterpartyId: s.counterpartyId, text: trimmed, requestId: uid("req") });
}

/** The owner's session id, created on first use. The home page opens its opener in this session, so "go ahead" lands in the same conversation as the chat panel. */
export function ensureOwnerSession(): string {
  const existing = store.get().convs.OWNER.sessionId;
  if (existing) return existing;
  const sessionId = newSessionId();
  patchConv("OWNER", (c) => ({ ...c, sessionId }));
  return sessionId;
}

/** Shows the agent's opener as an assistant turn in the owner's conversation (a newer opener replaces an older one that nobody answered). */
export function appendOwnerOpener(response: NlResponse): void {
  patchConv("OWNER", (c) => {
    const last = c.messages.at(-1);
    const rest = last?.from === "assistant" && last.response.parse_source === "opener" ? c.messages.slice(0, -1) : c.messages;
    return { ...c, sessionId: response.session_id, messages: [...rest, { id: uid("a"), from: "assistant", response }] };
  });
}

/** Sends one owner turn whatever channel the chat panel is showing, and returns the answer (null if it failed or a turn was in flight). */
export function sendOwnerTurn(text: string, display?: string): Promise<NlResponse | null> {
  return sendTurn("OWNER", text, display);
}

/** Resends the last failed turn (same request_id). The error bubble is replaced by the answer. */
export async function retryLast(role: NlActor = store.get().role): Promise<void> {
  const a = failed[role];
  if (!a || store.get().convs[role].busy) return;
  patchConv(role, (c) => ({ ...c, messages: c.messages.filter((m) => m.from !== "error") }));
  await run(a);
}

/** Ends a session on the server, quietly: the browser has already let go of the id, so a failure leaves only the server's expiry. */
function endOnServer(sessionId: string | null, role: NlActor, counterpartyId: CounterpartyId, token: string | null = getOwnerToken()): void {
  if (!sessionId) return;
  void endNlSession(sessionId, role, role === "COUNTERPARTY" ? counterpartyId : undefined, role === "OWNER" ? token : undefined).catch(() => undefined);
}

/**
 * "New conversation" in the channel on screen (`role`: the Business shell shows the owner's whatever role a Demo visit left behind): the
 * transcript, the session id, the failed turn and the draft go, a late answer to the old conversation is dropped, and the server ends the
 * session, so nothing it held (a pending plan, the last offer, a clarification) can be confirmed or referred to again.
 */
export function newConversation(role: NlActor = store.get().role): void {
  const s = store.get();
  const old = s.convs[role].sessionId;
  delete failed[role];
  patchConv(role, (c) => empty(c.generation + 1));
  setDraft("");
  endOnServer(old, role, s.counterpartyId);
}

/** Both conversations and the draft go (the books were replaced, or the owner signed out). */
function startOver(): void {
  delete failed.OWNER;
  delete failed.COUNTERPARTY;
  store.set((s) => ({
    ...s,
    booksEpoch: booksEpoch(),
    convs: { OWNER: empty(s.convs.OWNER.generation + 1), COUNTERPARTY: empty(s.convs.COUNTERPARTY.generation + 1) },
  }));
  setDraft("");
}

export function setRole(role: NlActor): void {
  store.set((s) => ({ ...s, role }));
}

/** A different buyer is a different counterparty on the server, so it starts a fresh conversation. */
export function setCounterparty(id: CounterpartyId): void {
  const s = store.get();
  if (s.counterpartyId === id) return;
  endOnServer(s.convs.COUNTERPARTY.sessionId, "COUNTERPARTY", s.counterpartyId);
  delete failed.COUNTERPARTY;
  store.set((s) => ({
    ...s,
    counterpartyId: id,
    convs: { ...s.convs, COUNTERPARTY: empty(s.convs.COUNTERPARTY.generation + 1) },
  }));
}

export function setPanelOpen(panelOpen: boolean): void {
  store.set((s) => ({ ...s, panelOpen }));
}

/**
 * FLOW speaks first (lead, 17 Oct): when the side panel or the Ask FLOW page opens on the owner's EMPTY conversation, ask POST /nl/opener once
 * and, if something needs the owner (`has_news`), show its answer as FLOW's first message (its pending cure waits in the same session for
 * "go ahead", exactly as before). Nothing needs the owner, a failure, or a conversation that started meanwhile: nothing is shown and the
 * empty state stays. Never for a buyer, never signed out (the opener is owner only), never twice in one conversation; "New conversation"
 * starts a fresh one, where it may run again. While it is asked the conversation is busy, so a question typed meanwhile waits behind it.
 */
export async function startOpener(lang: "en" | "zh"): Promise<void> {
  const conv = store.get().convs.OWNER;
  if (conv.openerTried || conv.busy || conv.messages.length > 0 || !getOwnerToken()) return;
  const sessionId = conv.sessionId ?? newSessionId();
  const generation = conv.generation;
  patchConv("OWNER", (c) => ({ ...c, sessionId, openerTried: true, busy: true }));
  try {
    const r = await nlOpener(sessionId, lang);
    patchConv("OWNER", (c) =>
      c.generation !== generation
        ? c
        : { ...c, busy: false, sessionId: r.session_id, messages: r.has_news && c.messages.length === 0 ? [{ id: uid("a"), from: "assistant", response: r }] : c.messages },
    );
  } catch {
    patchConv("OWNER", (c) => (c.generation !== generation ? c : { ...c, busy: false }));
  }
}

/** "Back to the side panel": the panel opens once the page it returns to is shown (components/chat/chat-panel.tsx reads it on the route change). */
let panelOnArrival = false;

export function openPanelOnArrival(): void {
  panelOnArrival = true;
}

export function takePanelOnArrival(): boolean {
  const wanted = panelOnArrival;
  panelOnArrival = false;
  return wanted;
}

/** Where "Back to the side panel" on the Ask FLOW page returns to: the page Expand was pressed on (this tab only). */
const RETURN_KEY = "tl-ask-return";

export function setAskReturn(path: string): void {
  try {
    window.sessionStorage.setItem(RETURN_KEY, path);
  } catch {
    /* storage unavailable: the way back is Home */
  }
}

export function askReturn(): string {
  try {
    const p = window.sessionStorage.getItem(RETURN_KEY);
    return p && p.startsWith("/") && !p.startsWith("//") && !p.startsWith("/ask") ? p : "/";
  } catch {
    return "/";
  }
}

// Signing out ends the owner's session on the server with the token that is going, then takes both conversations and the draft out of the browser.
onSigningOut((token) => endOnServer(store.get().convs.OWNER.sessionId, "OWNER", store.get().counterpartyId, token));
onSignedOut(startOver);

// Replaced books start the conversation over, in this tab and in every other one; a tab reloaded after another tab replaced them too.
onBooksReplaced(startOver);
if (typeof window !== "undefined" && store.get().booksEpoch !== booksEpoch()) startOver();

// After the owner signs in, resend the turn that was refused with a 401 so they do not have to retype it.
onSignedIn(() => {
  const last = store.get().convs.OWNER.messages.at(-1);
  if (last?.from === "error" && last.status === 401) void retryLast("OWNER");
});
