"use client";

import { useId, useState } from "react";
import { Button, ErrorState } from "@/components/ui";
import { getState } from "@/lib/api";
import { CAPEX_REQUEST, runCapex } from "@/lib/demo";
import { useI18n } from "@/lib/i18n";
import type { CapexStructure } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/**
 * Whole yuan with up to two decimals ("600,000", "¥22000.50") to integer fen, by string handling only: this converts
 * the owner's entry for the API, it never does arithmetic on money the server reported. Null when it is not a number.
 */
export function yuanToFen(text: string): number | null {
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(text.replace(/[¥,\s]/g, ""));
  if (!m) return null;
  const fen = Number(`${m[1]}${(m[2] ?? "").padEnd(2, "0")}`);
  return Number.isSafeInteger(fen) && fen > 0 ? fen : null;
}

/** The owner's purchase question: what, the price, the extra cash it brings each month, from when and for how long. */
export function CapexForm() {
  const { t } = useI18n();
  const [label, setLabel] = useState(CAPEX_REQUEST.label);
  const [price, setPrice] = useState("600,000");
  const [uplift, setUplift] = useState("22,000");
  const [start, setStart] = useState("4");
  const [life, setLife] = useState("60");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ids = { label: useId(), price: useId(), uplift: useId(), start: useId(), life: useId() };

  const priceFen = yuanToFen(price);
  const upliftFen = yuanToFen(uplift);
  const startN = Number(start);
  const lifeN = Number(life);
  const valid =
    label.trim() !== "" &&
    priceFen !== null &&
    upliftFen !== null &&
    Number.isInteger(startN) &&
    Number.isInteger(lifeN) &&
    startN >= 1 &&
    lifeN >= startN &&
    lifeN <= 600;

  async function check() {
    if (!valid || priceFen === null || upliftFen === null) return;
    setBusy(true);
    setError(null);
    try {
      await runCapex({ label: label.trim(), price_fen: priceFen, monthly_uplift_fen: upliftFen, uplift_start_month: startN, life_months: lifeN });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const field = "min-h-9 w-full rounded-md border border-line-strong bg-surface px-2.5 text-sm";
  const lbl = "mb-1 block text-xs font-medium text-ink-2";
  return (
    <form
      className="space-y-3"
      data-testid="capex-form"
      onSubmit={(e) => {
        e.preventDefault();
        void check();
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="sm:col-span-2 lg:col-span-1">
          <label htmlFor={ids.label} className={lbl}>{t("capexForm.label")}</label>
          <input id={ids.label} className={field} value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>
        <div>
          <label htmlFor={ids.price} className={lbl}>{t("capexForm.price")}</label>
          <input id={ids.price} className={field} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} data-testid="capex-price" />
        </div>
        <div>
          <label htmlFor={ids.uplift} className={lbl}>{t("capexForm.uplift")}</label>
          <input id={ids.uplift} className={field} inputMode="decimal" value={uplift} onChange={(e) => setUplift(e.target.value)} />
        </div>
        <div>
          <label htmlFor={ids.start} className={lbl}>{t("capexForm.start")}</label>
          <input id={ids.start} className={field} inputMode="numeric" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div>
          <label htmlFor={ids.life} className={lbl}>{t("capexForm.life")}</label>
          <input id={ids.life} className={field} inputMode="numeric" value={life} onChange={(e) => setLife(e.target.value)} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" loading={busy} disabled={!valid} data-testid="capex-check">
          {t("capexForm.check")}
        </Button>
        <span className="text-xs text-ink-3">{valid ? t("capexForm.hint") : t("capexForm.invalid")}</span>
      </div>
      {error ? <ErrorState error={error} /> : null}
    </form>
  );
}

/** Lender company names by facility id, from the books' facilities and the counterparty registry. */
export function useLenders(): (facilityId: string | null | undefined) => string | null {
  const state = useAsync(getState, []);
  return (facilityId) => {
    if (!state.data || !facilityId) return null;
    const fac = state.data.state.facilities.find((f) => f.id === facilityId);
    if (!fac) return null;
    return state.data.state.counterparties.find((c) => c.id === fac.lender_id)?.name ?? fac.lender_id;
  };
}

/** Who would lend for a structure: the lender's name, or "your cash + the bank credit line" for the cash structure. */
export function lenderOf(s: CapexStructure, lender: ReturnType<typeof useLenders>, cashLabel: string): string {
  return s.kind === "CASH_LINE" ? cashLabel : (lender(s.facility_id) ?? s.facility_id ?? "");
}
