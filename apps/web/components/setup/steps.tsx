"use client";

import { useState } from "react";
import { Disclosure } from "@/components/business/kit";
import { TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { DictKey } from "@/lib/dictionary";
import { blankBill, blankBorrow, blankLoan, updateDraft } from "@/lib/setup-draft";
import type { SetupBill, SetupBorrow, SetupDocument, SetupDraft, SetupLoan } from "@/lib/types";
import { DocPicker } from "./doc-picker";
import { AddButton, DateInput, Field, IntInput, type Issues, MoneyInput, RemoveButton, Select, TextInput } from "./fields";

/** The setup's steps 1, 2, 4 and 5 (step 3, customers, and step 6, review, have their own files). Every edit goes straight into the draft. */

export function StepHeading({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="space-y-1.5">
      <h2 className="type-headline text-balance text-ink">{title}</h2>
      <p className="max-w-[64ch] text-pretty text-sm text-ink-2">{sub}</p>
    </div>
  );
}

// ---------------------------------------------------------------- step 1

export function StepBusiness({ draft, issues }: { draft: SetupDraft; issues: Issues }) {
  const { t } = useI18n();
  const b = draft.business;
  const set = (k: keyof SetupDraft["business"]) => (v: string) => updateDraft((d) => ({ ...d, business: { ...d.business, [k]: v } }));
  return (
    <div className="space-y-6">
      <StepHeading title={t("setup.s1.title")} sub={t("setup.s1.sub")} />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label={t("setup.s1.company")} issue={issues["business.company_name"]}>
          <TextInput value={b.company_name} onChange={set("company_name")} placeholder={t("setup.s1.company.ph")} invalid={!!issues["business.company_name"]} testId="setup-company" />
        </Field>
        <Field label={t("setup.s1.sells")}>
          <TextInput value={b.what_you_sell} onChange={set("what_you_sell")} placeholder={t("setup.s1.sells.ph")} />
        </Field>
        <Field label={t("setup.s1.start")} hint={t("setup.s1.start.hint")} issue={issues["business.start_date"]}>
          <DateInput value={b.start_date} onChange={set("start_date")} invalid={!!issues["business.start_date"]} testId="setup-start" />
        </Field>
        <Field label={t("setup.s1.cash")} hint={t("setup.s1.cash.hint")} issue={issues["business.cash"]}>
          <MoneyInput value={b.cash} onChange={set("cash")} placeholder={t("setup.money.ph")} invalid={!!issues["business.cash"]} testId="setup-cash" />
        </Field>
      </div>
      <section className="space-y-4 rounded-card border border-line bg-surface p-5">
        <div className="space-y-1">
          <h3 className="text-sm font-bold text-ink">{t("setup.s1.earn.title")}</h3>
          <p className="text-sm text-ink-2">{t("setup.s1.earn.sub")}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("setup.s1.sales")} issue={issues["business.monthly_sales"]}>
            <MoneyInput value={b.monthly_sales} onChange={set("monthly_sales")} placeholder="¥" invalid={!!issues["business.monthly_sales"]} testId="setup-sales" />
          </Field>
          <Field label={t("setup.s1.costs")} issue={issues["business.monthly_costs"]}>
            <MoneyInput value={b.monthly_costs} onChange={set("monthly_costs")} placeholder="¥" invalid={!!issues["business.monthly_costs"]} testId="setup-costs" />
          </Field>
        </div>
      </section>
      <p className="text-meta text-ink-3">{t("setup.s1.foot")}</p>
    </div>
  );
}

// ---------------------------------------------------------------- step 2

const KINDS: SetupBorrow["kind"][] = ["CREDIT_LINE", "INVOICE_FINANCING", "LOAN_TO_APPLY"];

export function StepFunding({ draft, issues }: { draft: SetupDraft; issues: Issues }) {
  const { t } = useI18n();
  const [picking, setPicking] = useState(false);
  const setRow = (i: number, patch: Partial<SetupBorrow>) =>
    updateDraft((d) => ({ ...d, borrowing: d.borrowing.map((r, j) => (j === i ? { ...r, ...patch } : r)) }));
  const setLoan = (i: number, patch: Partial<SetupLoan>) => updateDraft((d) => ({ ...d, loans: d.loans.map((r, j) => (j === i ? { ...r, ...patch } : r)) }));
  const removeRow = (i: number) =>
    updateDraft((d) => ({
      ...d,
      borrowing: d.borrowing.filter((_, j) => j !== i),
      // an invoice financed by the removed source, or by one after it, keeps pointing at the same source
      customers: d.customers.map((c) => ({
        ...c,
        invoices: c.invoices.map((inv) =>
          inv.financed_by === null ? inv : inv.financed_by === i ? { ...inv, financed_by: null, financed_amount: "" } : inv.financed_by > i ? { ...inv, financed_by: inv.financed_by - 1 } : inv,
        ),
      })),
    }));
  const use = (doc: SetupDocument) => {
    if (doc.row) updateDraft((d) => ({ ...d, borrowing: [...d.borrowing, { ...blankBorrow(), ...(doc.row as Partial<SetupBorrow>), document_id: doc.document_id }] }));
    setPicking(false);
  };
  const is = (p: string) => issues[p];
  return (
    <div className="space-y-7">
      <StepHeading title={t("setup.s2.title")} sub={t("setup.s2.sub")} />
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-base font-bold text-ink">{t("setup.s2.sources")}</h3>
          <span className="grow" />
          <button type="button" onClick={() => setPicking((p) => !p)} className="motion-press inline-flex min-h-10 items-center rounded-control border border-line-ui px-4 text-sm font-semibold text-ink hover:bg-subtle" data-testid="setup-fill-agreement">
            {t("setup.s2.fill")}
          </button>
          <AddButton onClick={() => updateDraft((d) => ({ ...d, borrowing: [...d.borrowing, blankBorrow()] }))} testId="setup-add-source">
            {t("setup.s2.add")}
          </AddButton>
        </div>
        {picking ? <DocPicker kind="LENDER_AGREEMENT" startDate={draft.business.start_date} onUse={use} onClose={() => setPicking(false)} /> : null}
        {draft.borrowing.length === 0 ? (
          <p className="rounded-card border border-dashed border-line-strong px-4 py-6 text-center text-sm text-ink-2">{t("setup.s2.none")}</p>
        ) : (
          <TableWrap label={t("setup.s2.sources")}>
            <table className={`${tableCls} min-w-[980px]`}>
              <thead>
                <tr>
                  {(["name", "kind", "limit", "drawn", "rate", "fee", "lead", "cleandown", "agreed"] as const).map((c) => (
                    <th key={c} className={thCls}>
                      {t(`setup.col.${c}` as DictKey)}
                    </th>
                  ))}
                  <th className={thCls}>
                    <span className="sr-only">{t("setup.remove")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {draft.borrowing.map((r, i) => {
                  const p = `borrowing[${i}]`;
                  return (
                    <tr key={i}>
                      <td className={tdCls}>
                        <TextInput value={r.name} onChange={(v) => setRow(i, { name: v })} label={t("setup.col.name")} size="lg" invalid={!!is(`${p}.name`)} />
                      </td>
                      <td className={tdCls}>
                        <Select value={r.kind} onChange={(v) => setRow(i, { ...blankBorrow(v), name: r.name, limit: r.limit, rate_pct: r.rate_pct, document_id: r.document_id })} options={KINDS.map((k) => ({ value: k, label: t(`setup.kind.${k}` as DictKey) }))} label={t("setup.col.kind")} />
                      </td>
                      <td className={tdCls}>
                        <MoneyInput value={r.limit} onChange={(v) => setRow(i, { limit: v })} label={t("setup.col.limit")} placeholder="¥" invalid={!!is(`${p}.limit`)} />
                      </td>
                      <td className={tdCls}>
                        {r.kind === "CREDIT_LINE" ? (
                          <MoneyInput value={r.drawn} onChange={(v) => setRow(i, { drawn: v })} label={t("setup.col.drawn")} placeholder="¥ 0" invalid={!!is(`${p}.drawn`)} />
                        ) : (
                          <span className="text-meta text-ink-3">{r.kind === "INVOICE_FINANCING" ? t("setup.s2.drawnIf") : "—"}</span>
                        )}
                      </td>
                      <td className={tdCls}>
                        <TextInput value={r.rate_pct} onChange={(v) => setRow(i, { rate_pct: v })} inputMode="decimal" label={t("setup.col.rate")} placeholder="%" size="sm" invalid={!!is(`${p}.rate_pct`)} />
                      </td>
                      <td className={tdCls}>
                        {r.kind === "INVOICE_FINANCING" ? (
                          <TextInput value={r.fee_pct} onChange={(v) => setRow(i, { fee_pct: v })} inputMode="decimal" label={t("setup.col.fee")} placeholder="%" size="sm" invalid={!!is(`${p}.fee_pct`)} />
                        ) : (
                          <span className="text-ink-3">—</span>
                        )}
                      </td>
                      <td className={tdCls}>
                        <IntInput value={r.lead_time_days} onChange={(v) => setRow(i, { lead_time_days: v })} label={t("setup.col.lead")} invalid={!!is(`${p}.lead_time_days`)} />
                      </td>
                      <td className={tdCls}>
                        {r.kind === "CREDIT_LINE" ? (
                          <IntInput value={r.clean_down_days} onChange={(v) => setRow(i, { clean_down_days: v })} label={t("setup.col.cleandown")} invalid={!!is(`${p}.clean_down_days`)} />
                        ) : (
                          <span className="text-ink-3">—</span>
                        )}
                      </td>
                      <td className={`${tdCls} text-center`}>
                        <input type="checkbox" checked={r.agreed} disabled={r.kind === "LOAN_TO_APPLY"} onChange={(e) => setRow(i, { agreed: e.target.checked })} aria-label={t("setup.col.agreed")} className="size-5 accent-brand-600" />
                      </td>
                      <td className={tdCls}>
                        <RemoveButton onClick={() => removeRow(i)} label={t("setup.remove")} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableWrap>
        )}
        <p className="text-meta text-ink-3">{t("setup.s2.foot")}</p>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-base font-bold text-ink">{t("setup.s2.loans")}</h3>
          <span className="grow" />
          <AddButton onClick={() => updateDraft((d) => ({ ...d, loans: [...d.loans, blankLoan()] }))} testId="setup-add-loan">
            {t("setup.s2.addLoan")}
          </AddButton>
        </div>
        {draft.loans.length === 0 ? (
          <p className="text-sm text-ink-3">{t("setup.s2.noLoans")}</p>
        ) : (
          <TableWrap label={t("setup.s2.loans")}>
            <table className={`${tableCls} min-w-[820px]`}>
              <thead>
                <tr>
                  {(["lender", "owed", "repayment", "every", "nextPay", "interest"] as const).map((c) => (
                    <th key={c} className={thCls}>
                      {t(`setup.col.${c}` as DictKey)}
                    </th>
                  ))}
                  <th className={thCls}>
                    <span className="sr-only">{t("setup.remove")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {draft.loans.map((r, i) => {
                  const p = `loans[${i}]`;
                  return (
                    <tr key={i}>
                      <td className={tdCls}>
                        <TextInput value={r.label} onChange={(v) => setLoan(i, { label: v })} label={t("setup.col.lender")} size="lg" invalid={!!is(`${p}.label`)} />
                      </td>
                      <td className={tdCls}>
                        <MoneyInput value={r.owed} onChange={(v) => setLoan(i, { owed: v })} label={t("setup.col.owed")} placeholder="¥" invalid={!!is(`${p}.owed`)} />
                      </td>
                      <td className={tdCls}>
                        <MoneyInput value={r.repayment} onChange={(v) => setLoan(i, { repayment: v })} label={t("setup.col.repayment")} placeholder="¥" invalid={!!is(`${p}.repayment`)} />
                      </td>
                      <td className={tdCls}>
                        <Select value={r.every} onChange={(v) => setLoan(i, { every: v })} options={(["MONTHLY", "QUARTERLY"] as const).map((k) => ({ value: k, label: t(`setup.every.${k}` as DictKey) }))} label={t("setup.col.every")} />
                      </td>
                      <td className={tdCls}>
                        <DateInput value={r.next_payment_date} onChange={(v) => setLoan(i, { next_payment_date: v })} label={t("setup.col.nextPay")} invalid={!!is(`${p}.next_payment_date`)} />
                      </td>
                      <td className={tdCls}>
                        <TextInput value={r.rate_pct} onChange={(v) => setLoan(i, { rate_pct: v })} inputMode="decimal" label={t("setup.col.interest")} placeholder="%" size="sm" invalid={!!is(`${p}.rate_pct`)} />
                      </td>
                      <td className={tdCls}>
                        <RemoveButton onClick={() => updateDraft((d) => ({ ...d, loans: d.loans.filter((_, j) => j !== i) }))} label={t("setup.remove")} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableWrap>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- step 4

const BILL_KINDS: SetupBill["kind"][] = ["PAYROLL", "RENT", "SUPPLIER", "TAX", "OTHER"];
const REPEATS: SetupBill["repeats"][] = ["ONCE", "MONTHLY", "QUARTERLY", "YEARLY"];
const QUICK: Record<SetupBill["kind"], SetupBill["repeats"]> = { PAYROLL: "MONTHLY", RENT: "MONTHLY", SUPPLIER: "ONCE", TAX: "QUARTERLY", OTHER: "MONTHLY" };

export function StepBills({ draft, issues }: { draft: SetupDraft; issues: Issues }) {
  const { t } = useI18n();
  const setBill = (i: number, patch: Partial<SetupBill>) => updateDraft((d) => ({ ...d, bills: d.bills.map((r, j) => (j === i ? { ...r, ...patch } : r)) }));
  const is = (p: string) => issues[p];
  return (
    <div className="space-y-6">
      <StepHeading title={t("setup.s4.title")} sub={t("setup.s4.sub")} />
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-sm text-ink-2">{t("setup.s4.quick")}</span>
        {BILL_KINDS.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => updateDraft((d) => ({ ...d, bills: [...d.bills, blankBill(k === "OTHER" ? "" : t(`setup.bill.${k}` as DictKey), k, QUICK[k])] }))}
            className="motion-press inline-flex min-h-9 items-center rounded-pill border border-line-ui px-3.5 text-sm font-medium text-ink hover:bg-subtle"
            data-testid={`setup-quick-${k}`}
          >
            + {t(`setup.bill.${k}` as DictKey)}
          </button>
        ))}
      </div>
      {draft.bills.length === 0 ? (
        <p className="rounded-card border border-dashed border-line-strong px-4 py-6 text-center text-sm text-ink-2">{t("setup.s4.none")}</p>
      ) : (
        <TableWrap label={t("setup.step.4")}>
          <table className={`${tableCls} min-w-[860px]`}>
            <thead>
              <tr>
                {(["what", "billKind", "amount", "nextOn", "repeats", "until"] as const).map((c) => (
                  <th key={c} className={thCls}>
                    {t(`setup.col.${c}` as DictKey)}
                  </th>
                ))}
                <th className={thCls}>
                  <span className="sr-only">{t("setup.remove")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {draft.bills.map((r, i) => {
                const p = `bills[${i}]`;
                return (
                  <tr key={i}>
                    <td className={tdCls}>
                      <TextInput value={r.label} onChange={(v) => setBill(i, { label: v })} label={t("setup.col.what")} size="lg" invalid={!!is(`${p}.label`)} />
                    </td>
                    <td className={tdCls}>
                      <Select value={r.kind} onChange={(v) => setBill(i, { kind: v })} options={BILL_KINDS.map((k) => ({ value: k, label: t(`setup.bill.${k}` as DictKey) }))} label={t("setup.col.billKind")} />
                    </td>
                    <td className={tdCls}>
                      <MoneyInput value={r.amount} onChange={(v) => setBill(i, { amount: v })} label={t("setup.col.amount")} placeholder="¥" invalid={!!is(`${p}.amount`)} />
                    </td>
                    <td className={tdCls}>
                      <DateInput value={r.next_date} onChange={(v) => setBill(i, { next_date: v })} label={t("setup.col.nextOn")} invalid={!!is(`${p}.next_date`)} />
                    </td>
                    <td className={tdCls}>
                      <Select value={r.repeats} onChange={(v) => setBill(i, { repeats: v })} options={REPEATS.map((k) => ({ value: k, label: t(`setup.repeats.${k}` as DictKey) }))} label={t("setup.col.repeats")} />
                    </td>
                    <td className={tdCls}>
                      {r.repeats === "ONCE" ? (
                        <span className="text-ink-3">—</span>
                      ) : (
                        <DateInput value={r.until} onChange={(v) => setBill(i, { until: v })} label={`${t("setup.col.until")} (${t("setup.s4.untilHint")})`} invalid={!!is(`${p}.until`)} />
                      )}
                    </td>
                    <td className={tdCls}>
                      <RemoveButton onClick={() => updateDraft((d) => ({ ...d, bills: d.bills.filter((_, j) => j !== i) }))} label={t("setup.remove")} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableWrap>
      )}
      <p className="text-meta text-ink-3">{t("setup.s4.foot")}</p>
    </div>
  );
}

// ---------------------------------------------------------------- step 5

function Sentence({ pre, post, issue, children }: { pre: string; post: string; issue?: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-line px-5 py-4 last:border-b-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-base text-ink">
        <span>{pre}</span>
        <span className="w-40">{children}</span>
        <span>{post}</span>
      </div>
      {issue ? <p className="mt-1.5 text-meta font-medium text-bad">{issue}</p> : null}
    </div>
  );
}

export function StepLimits({ draft, issues }: { draft: SetupDraft; issues: Issues }) {
  const { t } = useI18n();
  const l = draft.limits;
  const set = (k: keyof SetupDraft["limits"]) => (v: string) => updateDraft((d) => ({ ...d, limits: { ...d.limits, [k]: v } }));
  return (
    <div className="space-y-6">
      <StepHeading title={t("setup.s5.title")} sub={t("setup.s5.sub")} />
      <div className="rounded-card border border-line bg-surface">
        <Sentence pre={t("setup.s5.min.pre")} post={t("setup.s5.min.post")} issue={issues["limits.min_cash"]}>
          <MoneyInput value={l.min_cash} onChange={set("min_cash")} placeholder="¥ 300,000" label={t("setup.s5.min.pre")} invalid={!!issues["limits.min_cash"]} testId="setup-min-cash" />
        </Sentence>
        <Sentence pre={t("setup.s5.apr.pre")} post={t("setup.s5.apr.post")} issue={issues["limits.max_apr_pct"]}>
          <TextInput value={l.max_apr_pct} onChange={set("max_apr_pct")} inputMode="decimal" label={t("setup.s5.apr.pre")} invalid={!!issues["limits.max_apr_pct"]} />
        </Sentence>
        <Sentence pre={t("setup.s5.cap.pre")} post={t("setup.s5.cap.post")} issue={issues["limits.concession_cap"]}>
          <MoneyInput value={l.concession_cap} onChange={set("concession_cap")} label={t("setup.s5.cap.pre")} invalid={!!issues["limits.concession_cap"]} />
        </Sentence>
        <Sentence pre={t("setup.s5.above.pre")} post={t("setup.s5.above.post")} issue={issues["limits.approval_above"]}>
          <MoneyInput value={l.approval_above} onChange={set("approval_above")} label={t("setup.s5.above.pre")} invalid={!!issues["limits.approval_above"]} />
        </Sentence>
        <Sentence pre={t("setup.s5.valid.pre")} post={t("setup.s5.valid.post")} issue={issues["limits.valid_days"]}>
          <IntInput value={l.valid_days} onChange={(v) => updateDraft((d) => ({ ...d, limits: { ...d.limits, valid_days: v } }))} label={t("setup.s5.valid.pre")} invalid={!!issues["limits.valid_days"]} />
        </Sentence>
      </div>
      <Disclosure card summary={t("setup.s5.more")} defaultOpen={!!(issues["limits.min_dscr"] || issues["limits.max_leverage"])}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("setup.s5.dscr")} issue={issues["limits.min_dscr"]}>
            <TextInput value={l.min_dscr} onChange={set("min_dscr")} inputMode="decimal" invalid={!!issues["limits.min_dscr"]} />
          </Field>
          <Field label={t("setup.s5.lev")} issue={issues["limits.max_leverage"]}>
            <TextInput value={l.max_leverage} onChange={set("max_leverage")} inputMode="decimal" invalid={!!issues["limits.max_leverage"]} />
          </Field>
        </div>
      </Disclosure>
      <div className="space-y-3 rounded-card border border-dashed border-line-strong p-5">
        <p className="text-sm font-bold text-ink">{t("setup.s5.never")}</p>
        <ul className="flex flex-wrap gap-2">
          {([1, 2, 3, 4] as const).map((n) => (
            <li key={n} className="rounded-pill bg-subtle px-3 py-1.5 text-sm text-ink-2">
              {t(`setup.s5.never.${n}` as DictKey)}
            </li>
          ))}
        </ul>
      </div>
      <p className="text-meta text-ink-3">{t("setup.s5.foot")}</p>
    </div>
  );
}
