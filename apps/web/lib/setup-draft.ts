"use client";

import { createStore } from "./create-store";
import { getSetupStatus } from "./api";
import { useI18n } from "./i18n";
import { useAsync } from "./use-async";
import type { SetupBill, SetupBorrow, SetupCustomer, SetupDraft, SetupInvoice, SetupLoan, SetupStatus } from "./types";

/**
 * The setup draft (ADR-0014): what the owner has typed so far, kept in this browser so "Save and finish later" can come back to it.
 * A per-browser convenience only: nothing here is the books, and the server checks every entry again when the owner reviews and opens.
 */

/** Today in the browser's calendar, as the date input takes it. */
export function todayIso(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function emptyDraft(): SetupDraft {
  return {
    business: { company_name: "", what_you_sell: "", start_date: "", cash: "", monthly_sales: "", monthly_costs: "" },
    borrowing: [],
    loans: [],
    customers: [],
    bills: [],
    limits: { min_cash: "", max_apr_pct: "15", concession_cap: "5,000", approval_above: "100,000", valid_days: 90, min_dscr: "1.25", max_leverage: "3" },
  };
}

export const blankBorrow = (kind: SetupBorrow["kind"] = "CREDIT_LINE"): SetupBorrow => ({
  name: "", kind, limit: "", drawn: "", rate_pct: "", fee_pct: "", advance_pct: kind === "INVOICE_FINANCING" ? "80" : "",
  lead_time_days: kind === "INVOICE_FINANCING" ? 3 : 0, agreed: kind !== "LOAN_TO_APPLY", clean_down_days: null,
  term_months: kind === "LOAN_TO_APPLY" ? 12 : null, document_id: null,
});

export const blankLoan = (): SetupLoan => ({ label: "", owed: "", repayment: "", every: "MONTHLY", next_payment_date: "", rate_pct: "" });

export const blankInvoice = (terms: number | null = null): SetupInvoice => ({
  sent_on: "", amount: "", terms_days: terms, paid: "", financed_amount: "", financed_by: null,
});

export const blankCustomer = (): SetupCustomer => ({ name: "", contract: null, invoices: [] });

export const blankBill = (label = "", kind: SetupBill["kind"] = "OTHER", repeats: SetupBill["repeats"] = "MONTHLY"): SetupBill => ({
  label, kind, amount: "", next_date: "", repeats, until: "",
});

const draftStore = createStore<{ draft: SetupDraft; touched: boolean }>(
  { draft: emptyDraft(), touched: false },
  { storage: "local", key: "tl-setup-draft" },
);

export function useSetupDraft(): { draft: SetupDraft; touched: boolean } {
  return draftStore.useValue();
}

/** Change the draft with a function of the draft (the page's every edit). */
export function updateDraft(fn: (d: SetupDraft) => SetupDraft): void {
  draftStore.set((s) => ({ draft: fn(s.draft), touched: true }));
}

/** Fill the start date once, on the first visit to the setup (today in the owner's calendar). */
export function ensureStartDate(): void {
  const s = draftStore.get();
  if (!s.draft.business.start_date) draftStore.set({ draft: { ...s.draft, business: { ...s.draft.business, start_date: todayIso() } }, touched: s.touched });
}

export function clearDraft(): void {
  draftStore.set({ draft: emptyDraft(), touched: false });
}

/** Which books the server holds now (blank, demo or the owner's own). Undefined while loading, or when the server cannot say. */
export function useSetupStatus(): { status: SetupStatus | undefined; reload: () => void } {
  const { lang } = useI18n();
  const read = useAsync(() => getSetupStatus(lang), [lang]);
  return { status: read.data, reload: read.reload };
}
