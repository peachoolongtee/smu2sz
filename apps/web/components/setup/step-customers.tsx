"use client";

import { useState } from "react";
import { Badge, Callout, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getSetupDocuments } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { blankCustomer, blankInvoice, updateDraft } from "@/lib/setup-draft";
import type { SetupContract, SetupCustomer, SetupDocument, SetupDraft, SetupInvoice } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { DocPicker } from "./doc-picker";
import { AddButton, DateInput, Field, IntInput, type Issues, MoneyInput, RemoveButton, Select, TextInput } from "./fields";
import { StepHeading } from "./steps";

/**
 * Step 3: who owes you, and where each contract stands today. A customer's repeating contract (typed, or filled from a confirmed or
 * uploaded contract) makes the future invoices; the table holds the invoices already sent and not fully paid. Where a row came from a
 * contract, the server says where the contract stands (invoice n of N) for the start date; the page draws that and computes nothing.
 */
export function StepCustomers({ draft, issues, initialPick = false }: { draft: SetupDraft; issues: Issues; initialPick?: boolean }) {
  const { t, lang } = useI18n();
  const [sel, setSel] = useState(0);
  const [picking, setPicking] = useState(initialPick);
  const start = draft.business.start_date;
  const docs = useAsync(() => getSetupDocuments(start, lang), [start, lang, picking]);
  const at = Math.min(sel, Math.max(draft.customers.length - 1, 0));
  const cu = draft.customers[at];

  const setCustomer = (patch: Partial<SetupCustomer>) => updateDraft((d) => ({ ...d, customers: d.customers.map((c, j) => (j === at ? { ...c, ...patch } : c)) }));
  const add = (c: SetupCustomer) => {
    updateDraft((d) => ({ ...d, customers: [...d.customers, c] }));
    setSel(draft.customers.length);
  };
  const use = (doc: SetupDocument) => {
    const row = doc.row ?? {};
    add({ name: row.name ?? "", contract: (row.contract as SetupContract | null) ?? null, invoices: (row.invoices as SetupInvoice[] | undefined) ?? [] });
    setPicking(false);
  };
  const remove = () => {
    updateDraft((d) => ({ ...d, customers: d.customers.filter((_, j) => j !== at) }));
    setSel(Math.max(at - 1, 0));
  };
  const counted = (n: number) => t("setup.s3.openCount", { n });

  return (
    <div className="space-y-6">
      <StepHeading title={t("setup.s3.title")} sub={t("setup.s3.sub")} />
      <div className="flex flex-wrap items-center gap-3">
        <span className="grow" />
        <button type="button" onClick={() => setPicking((p) => !p)} className="motion-press inline-flex min-h-10 items-center rounded-control border border-line-ui px-4 text-sm font-semibold text-ink hover:bg-subtle" data-testid="setup-fill-contract">
          {t("setup.s3.fillContract")}
        </button>
        <AddButton onClick={() => add(blankCustomer())} testId="setup-add-customer">
          {t("setup.s3.addCustomer")}
        </AddButton>
      </div>
      {picking ? <DocPicker kind="BUYER_CONTRACT" startDate={start} onUse={use} onClose={() => setPicking(false)} /> : null}
      {draft.customers.length === 0 ? (
        <p className="rounded-card border border-dashed border-line-strong px-4 py-8 text-center text-sm text-ink-2">{t("setup.s3.empty")}</p>
      ) : (
        <div className="flex flex-wrap items-start gap-5">
          <nav aria-label={t("setup.s3.customers")} className="flex w-full flex-col gap-2 sm:w-56">
            <p className="text-meta font-semibold uppercase tracking-wide text-ink-3">{t("setup.s3.customers")}</p>
            {draft.customers.map((c, i) => {
              const bad = Object.keys(issues).some((k) => k.startsWith(`customers[${i}]`));
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => setSel(i)}
                  aria-current={i === at ? "true" : undefined}
                  className={`motion-press rounded-tile border px-3 py-2.5 text-left text-sm ${i === at ? "border-brand-600 bg-brand-50" : "border-line-ui bg-surface hover:bg-subtle"} ${bad ? "ring-1 ring-bad-solid" : ""}`}
                >
                  <span className="block font-semibold text-ink">{c.name || t("setup.s3.unnamed")}</span>
                  <span className="block text-meta text-ink-3">{counted(c.invoices.length)}</span>
                </button>
              );
            })}
          </nav>
          {cu ? <CustomerEditor key={at} index={at} cu={cu} draft={draft} issues={issues} docs={docs.data ?? []} onChange={setCustomer} onRemove={remove} /> : null}
        </div>
      )}
      <p className="text-meta text-ink-3">{t("setup.s3.foot")}</p>
    </div>
  );
}

function CustomerEditor({ index, cu, draft, issues, docs, onChange, onRemove }: { index: number; cu: SetupCustomer; draft: SetupDraft; issues: Issues; docs: SetupDocument[]; onChange: (p: Partial<SetupCustomer>) => void; onRemove: () => void }) {
  const { t } = useI18n();
  const p = `customers[${index}]`;
  const is = (k: string) => issues[`${p}.${k}`];
  const k = cu.contract;
  const doc = k?.document_id ? docs.find((d) => d.document_id === k.document_id) : undefined;
  const progress = doc?.progress ?? null;
  const setContract = (patch: Partial<SetupContract>) => onChange({ contract: { ...(k as SetupContract), ...patch } });
  const setInvoice = (i: number, patch: Partial<SetupInvoice>) => onChange({ invoices: cu.invoices.map((inv, j) => (j === i ? { ...inv, ...patch } : inv)) });
  const financers = draft.borrowing.map((b, i) => ({ b, i })).filter(({ b }) => b.kind === "INVOICE_FINANCING");

  return (
    <div className="min-w-0 flex-[999_1_480px] space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("setup.s3.customerName")} issue={is("name")} className="min-w-56 flex-1">
          <TextInput value={cu.name} onChange={(v) => onChange({ name: v })} invalid={!!is("name")} testId="setup-customer-name" />
        </Field>
        <button type="button" onClick={onRemove} className="motion-press min-h-10 rounded-control px-3 text-sm font-medium text-ink-2 hover:bg-subtle hover:text-bad">
          {t("setup.s3.removeCustomer")}
        </button>
      </div>

      <section className="space-y-4 rounded-card border border-line bg-surface p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-bold text-ink">{t("setup.s3.contract")}</h3>
          {k?.document_id ? <Badge tone="ok">{doc?.title ?? t("setup.s3.fromDocs")}</Badge> : null}
          <span className="grow" />
          {k ? (
            <button type="button" onClick={() => onChange({ contract: null })} className="text-meta font-medium text-ink-2 underline underline-offset-2 hover:text-bad">
              {t("setup.s3.removeContract")}
            </button>
          ) : null}
        </div>
        {!k ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-ink-2">{t("setup.s3.noContract")}</p>
            <AddButton onClick={() => onChange({ contract: { amount: "", every_days: 30, terms_days: null, next_invoice_date: "", document_id: null } })} testId="setup-add-contract">
              {t("setup.s3.addContract")}
            </AddButton>
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Field label={t("setup.s3.amount")} issue={is("contract.amount")}>
                <MoneyInput value={k.amount} onChange={(v) => setContract({ amount: v })} placeholder="¥" invalid={!!is("contract.amount")} />
              </Field>
              <Field label={t("setup.s3.every")} issue={is("contract.every_days")}>
                <IntInput value={k.every_days} onChange={(v) => setContract({ every_days: v })} invalid={!!is("contract.every_days")} />
              </Field>
              <Field label={t("setup.s3.terms")} issue={is("contract.terms_days")}>
                <IntInput value={k.terms_days} onChange={(v) => setContract({ terms_days: v })} invalid={!!is("contract.terms_days")} />
              </Field>
              <Field label={t("setup.s3.nextInvoice")} issue={is("contract.next_invoice_date")}>
                <DateInput value={k.next_invoice_date} onChange={(v) => setContract({ next_invoice_date: v })} invalid={!!is("contract.next_invoice_date")} />
              </Field>
            </div>
            {doc?.facts?.length ? <p className="text-meta text-ink-3">{doc.facts.join(" · ")}</p> : null}
            {progress ? (
              <div className="space-y-2" data-testid="setup-progress">
                <p className="text-sm font-semibold text-ink-2">{progress.text}</p>
                <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${progress.slots.length}, minmax(0, 1fr))` }} aria-hidden>
                  {progress.slots.map((s, i) => (
                    <span key={i} className={`h-5 rounded-[4px] ${s === "sent" ? "bg-ink" : "border-2 border-dashed border-line-strong"}`} />
                  ))}
                </div>
                <p className="flex flex-wrap gap-4 text-meta text-ink-3">
                  <span>■ {t("setup.s3.legend.sent")}</span>
                  <span>┅ {t("setup.s3.legend.future")}</span>
                </p>
                {progress.earlier_paid_text ? <p className="text-meta text-ink-3">{progress.earlier_paid_text}</p> : null}
              </div>
            ) : null}
          </>
        )}
      </section>

      <section className="space-y-3">
        {progress?.assumed_text && cu.invoices.length ? (
          <div data-testid="setup-assumed">
            <Callout tone="warn">{progress.assumed_text}</Callout>
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-sm font-bold text-ink">{t("setup.s3.invoices")}</h3>
          <span className="grow" />
          <AddButton onClick={() => onChange({ invoices: [...cu.invoices, blankInvoice(k?.terms_days ?? null)] })} testId="setup-add-invoice">
            {t("setup.s3.addInvoice")}
          </AddButton>
        </div>
        {cu.invoices.length === 0 ? (
          <p className="text-sm text-ink-3">{t("setup.s3.noInvoices")}</p>
        ) : (
          <TableWrap label={t("setup.s3.invoices")}>
            <table className={`${tableCls} min-w-[860px]`}>
              <thead>
                <tr>
                  {(["sent", "amount", "terms", "paid", "financed", "financedBy"] as const).map((c) => (
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
                {cu.invoices.map((inv, i) => {
                  const q = `invoices[${i}]`;
                  return (
                    <tr key={i}>
                      <td className={tdCls}>
                        <DateInput value={inv.sent_on} onChange={(v) => setInvoice(i, { sent_on: v })} label={t("setup.col.sent")} invalid={!!is(`${q}.sent_on`)} />
                      </td>
                      <td className={tdCls}>
                        <MoneyInput value={inv.amount} onChange={(v) => setInvoice(i, { amount: v })} label={t("setup.col.amount")} placeholder="¥" invalid={!!is(`${q}.amount`)} />
                      </td>
                      <td className={tdCls}>
                        <IntInput value={inv.terms_days} onChange={(v) => setInvoice(i, { terms_days: v })} label={t("setup.col.terms")} placeholder={k?.terms_days != null ? String(k.terms_days) : ""} invalid={!!is(`${q}.terms_days`)} />
                      </td>
                      <td className={tdCls}>
                        <MoneyInput value={inv.paid} onChange={(v) => setInvoice(i, { paid: v })} label={t("setup.col.paid")} placeholder="¥ 0" invalid={!!is(`${q}.paid`)} />
                      </td>
                      <td className={tdCls}>
                        <MoneyInput value={inv.financed_amount} onChange={(v) => setInvoice(i, { financed_amount: v })} label={t("setup.col.financed")} placeholder="¥ 0" invalid={!!is(`${q}.financed_amount`)} />
                      </td>
                      <td className={tdCls}>
                        <Select
                          value={inv.financed_by === null ? "" : String(inv.financed_by)}
                          onChange={(v) => setInvoice(i, { financed_by: v === "" ? null : Number(v) })}
                          options={[{ value: "", label: t("setup.s3.notFinanced") }, ...financers.map(({ b, i: n }) => ({ value: String(n), label: b.name || t("setup.kind.INVOICE_FINANCING") }))]}
                          label={t("setup.col.financedBy")}
                          invalid={!!is(`${q}.financed_by`)}
                        />
                      </td>
                      <td className={tdCls}>
                        <RemoveButton onClick={() => onChange({ invoices: cu.invoices.filter((_, j) => j !== i) })} label={t("setup.remove")} />
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
