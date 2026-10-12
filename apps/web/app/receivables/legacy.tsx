"use client";

import { useEffect, useState } from "react";
import { PromisedAndReceived } from "@/components/receivables/history";
import { ErrorState, LoadingBlock, PageHeader, textLinkClass } from "@/components/ui";
import { getHome, getReceivablesWorth, getReconciliation, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { isOverdue, orderInvoices } from "@/lib/receivables-order";
import { daysLate } from "@/lib/when";
import { useAsync, useStrategyAsync } from "@/lib/use-async";
import { ActionBar } from "@/components/business/action-bar";
import { PartialRead, ReadWhen } from "@/components/business/freshness";
import { chaseIds, shortfallStretch } from "@/lib/chase";
import { DUE_SOON_DAYS, ReceivablesTable, type RecvFilter } from "@/components/business/receivables-table";
import { ChasePayment } from "@/components/business/chase-payment";
import { WhoPaysWhen } from "@/components/business/who-pays-when";

/** One fact of the facts row: a label, the figure and a caption, beside the next with a hairline between. */
function Fact({ label, caption, children, last = false }: { label: string; caption?: React.ReactNode; children: React.ReactNode; last?: boolean }) {
  return (
    <div className={`min-w-0 flex-1 basis-44 py-1 sm:px-5 sm:first:pl-0 ${last ? "" : "sm:border-r sm:border-line"}`}>
      <dt className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">{label}</dt>
      <dd className="mt-1 text-2xl font-extrabold tabular-nums tracking-[-0.01em] text-ink">{children}</dd>
      {caption ? <dd className="mt-0.5 text-xs text-ink-3">{caption}</dd> : null}
    </div>
  );
}

/**
 * The Receivables page as it was before map #110, kept as the fallback while the server has no GET /receivables (app/receivables/page.tsx chooses).
 *
 * Receivables, in the order the owner asks: who owes me, who is late, what should I do. The page title is the server's answer sentence
 * (`receivables.headline`, else the strategy read's top action while someone is late; never composed here), then a facts row, the one raised
 * action (Chase payment, only while someone is late), the "Who pays when" picture, the open invoices (late first), what was promised early and
 * what arrived. The last two appear only when there is something to show.
 */
export function LegacyReceivables() {
  const { t, lang } = useI18n();
  const recon = useAsync(getReconciliation, [lang]);
  const books = useAsync(getState, []);
  const home = useAsync(() => getHome(lang), [lang]);
  // The worth of collecting each invoice (strategy MVP, build-time flag): null while loading, when the server has it off, or
  // when the read fails; the page then shows the table it always had. Matched to the invoices by receivable_id.
  const worthRead = useStrategyAsync(() => getReceivablesWorth(lang), [lang]);
  const worth = worthRead.data;
  // The open invoices' filter lives here so the Overdue fact can apply Late; the picture's pressed mark highlights its row.
  const [filter, setFilter] = useState<RecvFilter>("all");
  const [picked, setPicked] = useState<string | null>(null);
  const worthOf = new Map((worth?.rows ?? []).map((w) => [w.receivable_id, w]));
  const data = recon.data;
  const r = home.data?.receivables;
  const name = (id: string | null) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id ?? "";
  // Overdue rows are pinned first, whatever the ranking says (the server's `past_due` / `overdue_text`; no date is compared here); inside each group the
  // server's own rank leads (what collecting each saves). The page counts days, the server does the money.
  const rank = new Map((worth?.rows ?? []).map((w, i) => [w.receivable_id, i]));
  const invoices = data ? orderInvoices(data.outstanding, worth?.rows ?? []) : [];
  const isLate = (o: (typeof invoices)[number]) => isOverdue(o, worthOf.get(o.receivable_id));
  const error = recon.error ?? home.error;
  // Chase payment is offered on the invoices that are late, that fall due inside the forecast's shortfall (the home read's first
  // breach to its lowest day) or whose early payment lapsed. Day numbers are compared; the handoff itself is the server's.
  const chase = chaseIds(invoices, data?.promised, shortfallStretch(home.data?.cash.first_breach_day, home.data?.cash.lowest_day));
  const lateInvoice = invoices.find(isLate);
  const someoneLate = Boolean(lateInvoice);
  // The page's answer: the server's sentence for every state when it sends one, else the strategy read's top action while someone is late;
  // otherwise the plain title stands (nothing is composed in the browser).
  const sentence = r?.headline || (someoneLate && worth?.top_action ? worth.top_action : null);
  const note = r?.headline ? (r.headline_note ?? null) : worth?.no_plan && worth.top_action_second && sentence ? worth.top_action_second : null;
  const chaseTarget = lateInvoice?.receivable_id;

  // A link such as /receivables#RI:BUYER-1:2 (from the home's remaining task) lands on that invoice once the page has loaded. The phone list and
  // the table both carry the id, one of them hidden: the visible one is scrolled to.
  const loaded = Boolean(data && r);
  useEffect(() => {
    if (!loaded || typeof window === "undefined" || !window.location.hash) return;
    const id = decodeURIComponent(window.location.hash.slice(1));
    const target = Array.from(document.querySelectorAll<HTMLElement>("[id]")).find((el) => el.id === id && el.getClientRects().length > 0);
    target?.scrollIntoView({ block: "center" });
  }, [loaded]);

  /** A pressed mark: show every invoice, then bring the visible row (table or phone list) into view and highlight it. */
  function pick(rowId: string) {
    setPicked(rowId);
    setFilter("all");
    window.setTimeout(() => {
      const el = Array.from(document.querySelectorAll<HTMLElement>("[id]")).find((x) => x.id === rowId && x.getClientRects().length > 0);
      el?.scrollIntoView({ block: "center", behavior: "auto" });
    }, 0);
  }

  return (
    <>
      {r?.headline && (r.headline_tone === "bad" || r.headline_tone === "warn") ? (
        // The server's tone as a status pill above the heading, built like Home's; the heading itself stays in the ink colour.
        <span
          className={`mb-2 inline-flex items-center gap-2 rounded-pill border px-3 py-1 text-xs font-extrabold uppercase tracking-[0.06em] ${r.headline_tone === "bad" ? "border-bad-line bg-bad-bg text-bad-fg" : "border-warn-line bg-warn-bg text-warn-fg"}`}
          data-testid="recv-status-word"
          data-tone={r.headline_tone}
        >
          <span aria-hidden className={`size-1.5 shrink-0 rounded-pill ${r.headline_tone === "bad" ? "bg-bad-solid" : "bg-warn-solid"}`} />
          {t(r.headline_tone === "bad" ? "biz.recv.pill.bad" : "biz.recv.pill.warn")}
        </span>
      ) : null}
      <PageHeader section="recv" title={sentence ?? t("nav.receivables")} subtitle={sentence ? note : t("biz.recv.subtitle")} />
      {error ? (
        <ErrorState error={error} onRetry={() => { recon.reload(); home.reload(); }} />
      ) : !data || !r ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-7">
          <section id="recv-summary" aria-label={t("biz.recv.facts")} data-testid="recv-summary">
            {/* How fresh the summary is: the report's own "when", else the home read's. */}
            <ReadWhen when={data.last_read_when ?? home.data?.cash.last_read_when} testId="recv-read-when" className="mb-2" />
            <dl className="flex flex-wrap gap-y-4 border-y border-line py-4">
              <Fact label={t("biz.recv.sum.outstanding")} caption={t("biz.recv.sum.count", { n: r.open_count })}>
                <span data-testid="recv-outstanding">{r.open_total_display}</span>
              </Fact>
              <Fact
                label={t("biz.recv.sum.overdue")}
                caption={
                  r.past_due.length ? (
                    <span className="flex flex-wrap items-center gap-x-2">
                      <span>{t("biz.recv.sum.overdue.n", { n: r.past_due.length })}</span>
                      {invoices.length ? (
                        // A tap on the Overdue fact shows the late invoices: the list below takes its Late filter and comes into view.
                        <button
                          type="button"
                          className={`${textLinkClass} -ml-2`}
                          data-testid="recv-overdue-show"
                          onClick={() => {
                            setFilter("late");
                            document.getElementById("recv-open")?.scrollIntoView({ block: "start" });
                          }}
                        >
                          {t("biz.recv.sum.overdue.show")}
                        </button>
                      ) : null}
                    </span>
                  ) : undefined
                }
              >
                <span data-testid="recv-overdue" className={r.past_due.length ? "text-bad-fg" : ""}>
                  {r.overdue_total_display}
                </span>
              </Fact>
              <Fact
                last
                label={t("biz.recv.sum.next")}
                caption={r.next_receipt ? <span data-testid="recv-next-hint">{t("biz.recv.sum.next.hint", { buyer: r.next_receipt.buyer_name, when: r.next_receipt.due_when })}</span> : undefined}
              >
                <span data-testid="recv-next-amount">{r.next_receipt ? r.next_receipt.face_display : "-"}</span>
              </Fact>
            </dl>
            {r.open_count === 0 ? <p className="mt-3 text-sm text-ink-3" data-testid="recv-none">{t("recon.outstanding.empty")}</p> : null}
          </section>

          {/* The one raised surface: only while someone is late. */}
          {someoneLate && chaseTarget ? (
            <ActionBar aria-label={t("biz.chase.button")} data-testid="recv-top-action">
              <div className="min-w-0 flex-[2_1_20rem]">
                <p className="text-xs font-extrabold uppercase tracking-[0.08em] text-brand-700">{t("biz.recommended.short")}</p>
                {worth?.top_action_second && !worth.no_plan ? (
                  <p className="mt-1 text-pretty font-display text-lg font-extrabold leading-snug text-ink" data-testid="recv-top-action-second">
                    {worth.top_action_second}
                  </p>
                ) : (
                  <p className="mt-1 text-pretty font-display text-lg font-extrabold leading-snug text-ink">
                    {name(invoices.find((o) => o.receivable_id === chaseTarget)?.counterparty_id ?? null)}
                    <span className="ml-3 text-base font-bold text-bad-fg tabular-nums">
                      {t("biz.recv.bar.overdue")} {r.overdue_total_display}
                    </span>
                    {r.past_due[0] ? <span className="ml-3 text-sm font-semibold text-ink-2">{daysLate(r.past_due[0].days_late, t)}</span> : null}
                  </p>
                )}
              </div>
              <ChasePayment top receivableId={chaseTarget} buyer={name(invoices.find((o) => o.receivable_id === chaseTarget)?.counterparty_id ?? null)} />
            </ActionBar>
          ) : null}

          <PartialRead partial={home.data?.partial} onRetry={home.reload} />

          {worthRead.error ? (
            <div data-testid="recv-worth-failed">
              <ErrorState error={t("biz.recv.worth.failed")} onRetry={worthRead.reload} />
            </div>
          ) : null}

          {invoices.length ? <WhoPaysWhen invoices={invoices} promised={data.promised} asOfDay={data.as_of_day} buyerName={name} isLate={isLate} dueSoonDays={DUE_SOON_DAYS} selected={picked} onSelect={pick} /> : null}

          {invoices.length ? <ReceivablesTable invoices={invoices} asOfDay={data.as_of_day} buyerName={name} worth={worth} worthOf={worthOf} rank={rank} chase={chase} filter={filter} onFilter={setFilter} highlight={picked} /> : null}

          <PromisedAndReceived data={data} name={name} picked={picked} />
        </div>
      )}
    </>
  );
}
