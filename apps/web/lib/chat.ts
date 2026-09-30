"use client";

/**
 * Conversation state for the chat page and the slide-over panel (they share it, so a conversation started in
 * one continues in the other). One conversation per role: the owner's and a buyer's are different channels
 * with different sessions. The server keeps the session (pending plan, clarification); this store keeps what
 * to show and the session id. It never interprets money: replies and amounts are rendered as received.
 */

import { nl } from "./api";
import { onSignedIn } from "./auth";
import { ApiError } from "./errors";
import { createStore } from "./create-store";
import type { NlActor, NlResponse } from "./types";

export const COUNTERPARTIES = ["BUYER-1", "BUYER-2", "FASTCAPITAL"] as const;
export type CounterpartyId = (typeof COUNTERPARTIES)[number];

export type ChatMessage =
  | { id: string; from: "user"; text: string }
  | { id: string; from: "assistant"; response: NlResponse }
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

const store = createStore<ChatState>({
  role: "OWNER",
  counterpartyId: "BUYER-1",
  panelOpen: false,
  convs: { OWNER: empty(), COUNTERPARTY: empty() },
});

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

async function run(a: Attempt): Promise<void> {
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
    });
    delete failed[a.role];
    patchConv(a.role, (c) =>
      c.generation !== generation ? c : { ...c, busy: false, sessionId: response.session_id, messages: [...c.messages, { id: uid("a"), from: "assistant", response }] },
    );
  } catch (e) {
    failed[a.role] = a;
    const status = e instanceof ApiError ? e.status : 0;
    const text = e instanceof Error ? e.message : String(e);
    patchConv(a.role, (c) => (c.generation !== generation ? c : { ...c, busy: false, messages: [...c.messages, { id: uid("e"), from: "error", text, status }] }));
  }
}

/**
 * Sends one turn in the current role's conversation. `display` is what the bubble shows when it differs from
 * what is sent (a clarification option shows its label and sends its id).
 */
export async function sendMessage(text: string, display?: string): Promise<void> {
  const s = store.get();
  const conv = s.convs[s.role];
  const trimmed = text.trim();
  if (!trimmed || conv.busy) return;
  patchConv(s.role, (c) => ({ ...c, messages: [...c.messages, { id: uid("u"), from: "user", text: display ?? trimmed }] }));
  await run({ role: s.role, counterpartyId: s.counterpartyId, text: trimmed, requestId: uid("req") });
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

// After the owner signs in, resend the turn that was refused with a 401 so they do not have to retype it.
onSignedIn(() => {
  const last = store.get().convs.OWNER.messages.at(-1);
  if (last?.from === "error" && last.status === 401) void retryLast("OWNER");
});
