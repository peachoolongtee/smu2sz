"use client";

import { useEffect } from "react";
import { ReceiptFacts } from "@/components/receipt-facts";
import { Badge, Card, ErrorState, LoadingBlock, PageHeader, Stat } from "@/components/ui";
import { getHome, getReceivablesWorth, getReconciliation, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";
import { useAsync, useStrategyAsync } from "@/lib/use-async";
import { Disclosure } from "@/components/business/kit";
import { chaseIds, shortfallStretch } from "@/lib/chase";
import { ReceivablesTable } from "@/components/business/receivables-table";

/**
 * Receivables, in the order the owner asks: who owes me and how much (the summary, from the home read), when and who is
 * late (the invoices, late first), what was promised early and what arrived. The last two appear only when there is
 * something to show. Names from the books; ids beside them.
 */
export default function ReceivablesPage() {
  const { t, te, lang } = useI18n();
  const recon = useAsync(getReconciliation, []);
  const books = useAsync(getState, []);
  const home = useAsync(() => getHome(lang), [lang]);
  // The worth of collecting each invoice (strategy MVP, build-time flag): null while loading, when the server has it off, or
  // when the read fails; the page then shows the table it always had. Matched to the invoices by receivable_id.
  const worthRead = useStrategyAsync(() => getReceivablesWorth(lang), [lang]);
  const worth = worthRead.data;
  const worthOf = new Map((worth?.rows ?? []).map((w) => [w.receivable_id, w]));
  const data = recon.data;
  const r = home.data?.receivables;
  const name = (id: string | null) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id ?? "";
  // Late rows first, then by due day; the page counts days, the server does the money.
  // With the worth loaded the server's own rank leads (what collecting each saves), the rest keep the late-first order.
  const rank = new Map((worth?.rows ?? []).map((w, i) => [w.receivable_id, i]));
  const invoices = data
    ? [...data.outstanding].sort((a, b) => (rank.get(a.receivable_id) ?? rank.size) - (rank.get(b.receivable_id) ?? rank.size) || Number(b.past_due) - Number(a.past_due) || a.due_day - b.due_day)
    : [];
  const error = recon.error ?? home.error;
  // Chase payment is offered on the invoices that are late, that fall due inside the forecast's shortfall (the home read's first
  // breach to its lowest day) or whose early payment lapsed. Day numbers are compared; the handoff itself is the server's.
  const chase = chaseIds(invoices, data?.promised, shortfallStretch(home.data?.cash.first_breach_day, home.data?.cash.lowest_day));

  // A link such as /receivables#RI:BUYER-1:2 (from the home's remaining task) lands on that invoice once the page has loaded. The phone list and
  // the table both carry the id, one of them hidden: the visible one is scrolled to.
  const loaded = Boolean(data && r);
  useEffect(() => {
    if (!loaded || typeof window === "undefined" || !window.location.hash) return;
    const id = decodeURIComponent(window.location.hash.slice(1));
    const target = Array.from(document.querySelectorAll<HTMLElement>("[id]")).find((el) => el.id === id && el.getClientRects().length > 0);
    target?.scrollIntoView({ block: "center" });
  }, [loaded]);

  return (
    <>
      <PageHeader section="recv" title={t("nav.receivables")} subtitle={t("biz.recv.subtitle")} />
      {error ? (
        <ErrorState error={error} onRetry={() => { recon.reload(); home.reload(); }} />
      ) : !data || !r ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-6">
          <section id="recv-summary" aria-label={t("nav.receivables")} data-testid="recv-summary">
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Stat className="col-span-2 sm:col-span-1" label={t("biz.recv.sum.outstanding")} value={<span data-testid="recv-outstanding">{r.open_total_display}</span>} caption={t("biz.recv.sum.count", { n: r.open_count })} />
              <Stat
                label={t("biz.recv.sum.overdue")}
                value={<span data-testid="recv-overdue">{r.overdue_total_display}</span>}
                caption={r.past_due.length ? t("biz.recv.sum.overdue.n", { n: r.past_due.length }) : undefined}
                tone={r.past_due.length ? "bad" : "neutral"}
              />
              <Stat
                label={t("biz.recv.sum.next")}
                value={<span data-testid="recv-next-amount">{r.next_receipt ? r.next_receipt.face_display : "-"}</span>}
                caption={r.next_receipt ? <span data-testid="recv-next-hint">{t("biz.recv.sum.next.hint", { buyer: r.next_receipt.buyer_name, when: r.next_receipt.due_when })}</span> : undefined}
              />
            </dl>
            {r.open_count === 0 ? <p className="mt-3 text-sm text-ink-3" data-testid="recv-none">{t("recon.outstanding.empty")}</p> : null}
          </section>

          {worthRead.error ? (
            <div data-testid="recv-worth-failed">
              <ErrorState error={t("biz.recv.worth.failed")} onRetry={worthRead.reload} />
            </div>
          ) : null}

          {invoices.length ? <ReceivablesTable invoices={invoices} asOfDay={data.as_of_day} buyerName={name} worth={worth} worthOf={worthOf} rank={rank} chase={chase} /> : null}

          {data.promised?.length ? (
            <Card id="recv-promised" title={t("biz.recv.promised")} subtitle={t("biz.recv.promised.sub")} actions={data.lapsed_promises ? <Badge tone="bad">{`${t("recon.lapsed")}: ${data.lapsed_promises}`}</Badge> : undefined}>
              <ul className="motion-rise space-y-2">
                {data.promised.map((p) => (
                  <li key={`${p.commitment_id}:${p.obligation_id}:${p.receivable_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-tile border border-line px-3 py-2 text-sm" data-testid={`promised-${p.receivable_id}`} data-status={p.status}>
                    <span>
                      <span className="font-medium text-ink">{name(p.counterparty_id)}</span>
                      <span className="block text-xs text-ink-2">{p.detail_when ?? p.detail}</span>
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="font-semibold tabular-nums">{p.expected_display}</span>
                      <Badge tone={p.status === "RECEIVED" ? "ok" : p.status === "AWAITED" ? "info" : "bad"}>{te("promstatus", p.status)}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {data.receipts.length ? (
            <Card id="recv-receipts" title={t("biz.recv.receipts")} subtitle={t("biz.recv.receipts.sub", { matched: data.matched, flagged: data.flagged })}>
              <ul className="space-y-2">
                {data.receipts.map((x) => (
                  <li key={x.entry_hash} className={`rounded-tile border px-3 py-2 text-sm ${x.flagged ? "border-bad-line bg-bad-bg/40" : "border-line"}`} data-testid={`receipt-${x.op_id}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-ink">{name(x.counterparty_id)}</span>
                      <span className="flex items-center gap-2">
                        <span className="font-semibold tabular-nums">{x.received_display}</span>
                        <Badge tone={x.flagged ? "bad" : "ok"}>{te("recstatus", x.status)}</Badge>
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-2">
                      {x.day !== null ? `${whenText(x.day, data.as_of_day, t)} · ` : ""}
                      {x.detail_when ?? x.detail}
                    </p>
                    <ReceiptFacts facts={x} testId={`receipt-facts-${x.op_id}`} />
                    {/* The record ids (invoice, bank reference) are the audit level. */}
                    <Disclosure className="mt-1" testId={`receipt-audit-${x.op_id}`} summary={t("biz.auditDetails")}>
                      <p className="mt-1 text-xs text-ink-3">
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
            </Card>
          ) : null}
        </div>
      )}
    </>
  );
}
