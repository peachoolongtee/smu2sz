"use client";

/**
 * Conversation state for the chat page and the slide-over panel (they share it, so a conversation started in
 * one continues in the other). One conversation per role: the owner's and a buyer's are different channels
 * with different sessions. The server keeps the session (pending plan, clarification); this store keeps what
 * to show and the session id. It never interprets money: replies and amounts are rendered as received.
 */

import { nl } from "./api";
import { onSignedIn, onSignedOut } from "./auth";
import { nlContext } from "./chat-context";
import { ApiError } from "./errors";
import { errorMessage } from "./error-text";
import { createStore } from "./create-store";
import type { NlActor, NlResponse } from "./types";

export const COUNTERPARTIES = ["BUYER-1", "BUYER-2", "FASTCAPITAL"] as const;
export type CounterpartyId = (typeof COUNTERPARTIES)[number];

export type ChatMessage =
  | { id: string; from: "user"; text: string }
  /** `restored`: read back from the browser after a refresh; its buttons are history, and a pending plan or approval lives on the Approvals page. */
  | { id: string; from: "assistant"; response: NlResponse; restored?: boolean }
  | { id: string; from: "error"; text: string; status: number };

interface Conversation {
  /** Null until the first turn; then the id the server answered with. */
  sessionId: string | null;
  messages: ChatMessage[];
  busy: boolean;
  /** Bumped by "New conversation" so a late answer to the old one is dropped. */
  generation: number;
}

interface ChatState {
  role: NlActor;
  counterpartyId: CounterpartyId;
  panelOpen: boolean;
  convs: Record<NlActor, Conversation>;
}

const empty = (generation = 0): Conversation => ({ sessionId: null, messages: [], busy: false, generation });

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
  try {
    const response = await nl({
      session_id: sessionId,
      actor: a.role,
      counterparty_id: a.role === "COUNTERPARTY" ? a.counterpartyId : undefined,
      text: a.text,
      request_id: a.requestId,
      // The owner's page, as ids: the deal it evaluated, the invoice row it has open, the last visit. A buyer's turn names none.
      context: a.role === "OWNER" ? nlContext() : undefined,
    });
    delete failed[a.role];
    patchConv(a.role, (c) =>
      c.generation !== generation ? c : { ...c, busy: false, sessionId: response.session_id, messages: [...c.messages, { id: uid("a"), from: "assistant", response }] },
    );
    return response;
  } catch (e) {
    failed[a.role] = a;
    const status = e instanceof ApiError ? e.status : 0;
    const text = errorMessage(e);
    patchConv(a.role, (c) => (c.generation !== generation ? c : { ...c, busy: false, messages: [...c.messages, { id: uid("e"), from: "error", text, status }] }));
    return null;
  }
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

export function newConversation(): void {
  delete failed[store.get().role];
  patchConv(store.get().role, (c) => empty(c.generation + 1));
}

export function setRole(role: NlActor): void {
  store.set((s) => ({ ...s, role }));
}

/** A different buyer is a different counterparty on the server, so it starts a fresh conversation. */
export function setCounterparty(id: CounterpartyId): void {
  if (store.get().counterpartyId === id) return;
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

// Signing out takes the owner's conversation and draft out of the browser with the token.
onSignedOut(() => {
  delete failed.OWNER;
  patchConv("OWNER", (c) => empty(c.generation + 1));
  setDraft("");
});

// After the owner signs in, resend the turn that was refused with a 401 so they do not have to retype it.
onSignedIn(() => {
  const last = store.get().convs.OWNER.messages.at(-1);
  if (last?.from === "error" && last.status === 401) void retryLast("OWNER");
});
