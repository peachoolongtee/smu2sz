"use client";

import { ReceiptFacts } from "@/components/receipt-facts";
import { Badge } from "@/components/ui";
import { Disclosure } from "@/components/business/kit";
import { useI18n } from "@/lib/i18n";
import type { ReconciliationView } from "@/lib/types";
import { whenText } from "@/lib/when";

/**
 * What was promised early and what arrived: the two sections the Receivables page has always had under its invoices (from the reconciliation read),
 * each only when there is something to show. Shared by the page of before and Receivables in three layers, which keeps them below its own sections.
 * `name` turns a buyer id into the buyer's name; `picked` is a row the page pointed at (it takes a quiet tint).
 */
export function PromisedAndReceived({ data, name, picked = null }: { data: ReconciliationView; name: (id: string | null) => string; picked?: string | null }) {
  const { t, te } = useI18n();
  return (
    <>
    {data.promised?.length ? (
      <section id="recv-promised" aria-labelledby="recv-promised-title">
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 border-b border-line-strong pb-2">
          <div>
            <h2 id="recv-promised-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
              {t("biz.recv.promised")}
            </h2>
            <p className="text-sm text-ink-3">{t("biz.recv.promised.sub")}</p>
          </div>
          {data.lapsed_promises ? <Badge tone="bad">{`${t("recon.lapsed")}: ${data.lapsed_promises}`}</Badge> : null}
        </div>
        <ul className="motion-rise divide-y divide-line">
          {data.promised.map((p) => (
            <li
              key={`${p.commitment_id}:${p.obligation_id}:${p.receivable_id}`}
              id={`promised-${p.receivable_id}`}
              className={`flex scroll-mt-20 flex-wrap items-center justify-between gap-2 py-3 text-sm ${picked === `promised-${p.receivable_id}` ? "-mx-2 rounded-tile bg-brand-50 px-2" : ""}`}
              data-testid={`promised-${p.receivable_id}`}
              data-status={p.status}
            >
              <span className="min-w-0">
                <span className="font-medium text-ink">{name(p.counterparty_id)}</span>
                <span className="block text-sm text-ink-2">{p.detail_when ?? p.detail}</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="font-semibold tabular-nums">{p.expected_display}</span>
                <Badge tone={p.status === "RECEIVED" ? "ok" : p.status === "AWAITED" ? "info" : "bad"}>{te("promstatus", p.status)}</Badge>
              </span>
            </li>
          ))}
        </ul>
      </section>
    ) : null}

    {data.receipts.length ? (
      <section id="recv-receipts" aria-labelledby="recv-receipts-title">
        <div className="mb-1 border-b border-line-strong pb-2">
          <h2 id="recv-receipts-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
            {t("biz.recv.receipts")}
          </h2>
          <p className="text-sm text-ink-3">{t("biz.recv.receipts.sub", { matched: data.matched, flagged: data.flagged })}</p>
        </div>
        <ul className="divide-y divide-line">
          {data.receipts.map((x) => (
            <li key={x.entry_hash} className="py-3 text-sm" data-testid={`receipt-${x.op_id}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-ink">{name(x.counterparty_id)}</span>
                <span className="flex items-center gap-2">
                  <span className="font-semibold tabular-nums">{x.received_display}</span>
                  <Badge tone={x.flagged ? "bad" : "ok"}>{te("recstatus", x.status)}</Badge>
                </span>
              </div>
              {/* A part-paid invoice: a short lead and the four named facts say it once; the long sentence waits behind Audit details. */}
              {x.remaining_display ? (
                <>
                  <p className="mt-0.5 text-sm text-ink-2" data-testid={`receipt-lead-${x.op_id}`}>
                    {t("biz.recv.partPaid", { buyer: name(x.counterparty_id), when: x.day !== null ? whenText(x.day, data.as_of_day, t) : "" })}
                  </p>
                  <ReceiptFacts facts={x} testId={`receipt-facts-${x.op_id}`} windowText={x.window_state_text} />
                </>
              ) : (
                <p className="mt-0.5 text-sm text-ink-2">
                  {x.day !== null ? `${whenText(x.day, data.as_of_day, t)} · ` : ""}
                  {x.detail_when ?? x.detail}
                </p>
              )}
              {/* The record ids (invoice, bank reference) are the audit level. */}
              <Disclosure className="mt-1" testId={`receipt-audit-${x.op_id}`} summary={t("biz.auditDetails")}>
                {x.remaining_display ? <p className="mt-1 text-sm text-ink-2">{x.detail_when ?? x.detail}</p> : null}
                <p className="mt-1 text-sm text-ink-3">
                  {x.receivable_id}
                  {x.bank_reference ? (
                    <span data-testid={`receipt-ref-${x.op_id}`}>
                      {" · "}
                      {t("recon.bankRef", { ref: x.bank_reference })}
                    </span>
                  ) : null}
                </p>
              </Disclosure>
            </li>
          ))}
        </ul>
      </section>
    ) : null}
    </>
  );
}
