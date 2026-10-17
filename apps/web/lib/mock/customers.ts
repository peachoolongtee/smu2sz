/**
 * Mock for POST /customers: the buyers the owner added by name in this session. They join the counterparties GET /state
 * answers (the recorded books do not change), so Attach deals can file a contract under one. As live: the name is required,
 * a name already on the books is a 409 CUSTOMER_EXISTS naming that customer, and a retried request (the same key) adds it once.
 * The sentence for the event is the mock's own, in the shape the server words it.
 */

import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import type { AddCustomerRequest, AddCustomerResponse, Counterparty, Customer } from "../types";

const KEY = "tl-mock-customers-v1";

interface Added {
  customer: Customer;
  short_name: string | null;
  key: string;
}

let memory: Added[] | null = null;

function load(): Added[] {
  if (memory) return memory;
  memory = [];
  if (typeof window !== "undefined") {
    try {
      const raw = window.sessionStorage.getItem(KEY);
      if (raw) memory = JSON.parse(raw) as Added[];
    } catch {
      /* start with none */
    }
  }
  return memory;
}

function save(): void {
  if (typeof window === "undefined" || !memory) return;
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    /* the in-memory list still works */
  }
}

export function resetCustomers(): void {
  memory = [];
  save();
}

/** The counterparties of the recorded books with the customers added in this session after them. */
export function withAdded(parties: Counterparty[]): Counterparty[] {
  const ids = new Set(parties.map((p) => p.id));
  return [...parties, ...load().filter((a) => !ids.has(a.customer.id)).map((a) => ({ ...a.customer }))];
}

const norm = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();

function eventText(name: string, lang: "en" | "zh"): string {
  return lang === "zh" ? `您已将${name}添加为客户。` : `You added ${name} as a customer.`;
}

export function mockAddCustomer(req: AddCustomerRequest, lang: "en" | "zh", books: Counterparty[]): AddCustomerResponse {
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required. Sign in with the owner token to use this.");
  }
  const name = req.name.trim().replace(/\s+/g, " ");
  if (!name || name.length > 120) {
    const message = lang === "zh" ? "请输入客户名称。" : "Type the customer's name.";
    throw new ApiError(422, message, { code: "INVALID_NAME", message });
  }
  const added = load();
  const replay = added.find((a) => a.key === req.idempotency_key);
  if (replay) return { customer: { ...replay.customer }, created: false, event_text: eventText(replay.customer.name, lang) };
  const parties = withAdded(books);
  const same = parties.find((p) => p.role !== "OWNER" && norm(p.name) === norm(name));
  if (same) {
    const message = lang === "zh" ? `${same.name}已在您的账本中。` : `${same.name} is already on your books.`;
    throw new ApiError(409, message, { code: "CUSTOMER_EXISTS", message, existing_id: same.id });
  }
  const n = Math.max(0, ...parties.map((p) => /^BUYER-(\d+)$/.exec(p.id)).map((m) => (m ? Number(m[1]) : 0))) + 1;
  const customer: Customer = { id: `BUYER-${n}`, name, role: "BUYER", known: true };
  added.push({ customer, short_name: req.short_name?.trim() || null, key: req.idempotency_key });
  save();
  return { customer: { ...customer }, created: true, event_text: eventText(name, lang) };
}
