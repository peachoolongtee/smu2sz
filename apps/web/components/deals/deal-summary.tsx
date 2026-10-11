"use client";

import Link from "next/link";
import { CardLink, ContractCard, DealHeading, Pill } from "@/components/documents";
import { useI18n } from "@/lib/i18n";
import type { DealTone, DealView, StageState } from "@/lib/types";

/** Agreed by both parties: a confirmed contract and the "Terms negotiated" stage done (the server's accepted commitment). */
export function isAgreed(d: DealView): boolean {
  return d.has_contract && Boolean(d.stages?.some((s) => s.key === "negotiated" && s.state === "done"));
}

/**
 * The deal summary, after the negotiation (brief 03, on Deals): for each buyer whose deal both parties have agreed, the
 * contract the owner confirmed beside the live books. It reads top to bottom as the owner asks: what do I do (the next step,
 * first), where is the deal (the stages), what did we sign (each term with its clause as a link into the document), what has
 * changed (the differences as Contract → Now, the rest in one line, then who did what), the money, what we owe them and the
 * check. The page passes GET /deals; every amount, date and sentence here is a server string. Nothing shows before a deal is agreed.
 */
export function AgreedDeals({ deals }: { deals: DealView[] }) {
  const { t } = useI18n();
  const agreed = deals.filter(isAgreed);
  if (!agreed.length) return null;
  return (
    <ContractCard id="deal-summary" title={t("deals.summary.title")} aside={<CardLink href="/documents">{t("deals.summary.documents")} →</CardLink>}>
      <p className="mb-3 text-sm text-ink-3">{t("deals.summary.sub")}</p>
      <div className="space-y-3">
        {agreed.map((d) => (
          <DealSummary key={d.counterparty_id} deal={d} />
        ))}
      </div>
    </ContractCard>
  );
}

const DOT: Record<StageState, string> = {
  done: "border-brand-600 bg-brand-600",
  now: "border-brand-600 bg-brand-50 ring-3 ring-brand-50",
  todo: "border-line-strong bg-surface",
  skipped: "border-dashed border-line-strong bg-subtle",
  pending: "border-warn-fg bg-warn-bg",
  missed: "border-bad-fg bg-bad-bg",
};
const NOW_BAD = "border-bad-fg bg-bad-bg ring-3 ring-bad-bg";
const NEXT: Record<DealTone, string> = {
  bad: "border-bad-line bg-bad-bg text-bad-fg",
  warn: "border-warn-line bg-warn-bg text-warn-fg",
  ok: "border-ok-line bg-ok-bg text-ok-fg",
  info: "border-info-line bg-info-bg text-info-fg",
  mute: "border-line bg-subtle text-ink-3",
};
const TICK: Record<"ok" | "warn" | "info" | "todo", { cls: string; glyph: string }> = {
  ok: { cls: "bg-ok-bg text-ok-fg", glyph: "✓" },
  warn: { cls: "bg-warn-bg text-warn-fg", glyph: "!" },
  info: { cls: "border border-line-strong bg-subtle text-ink-3", glyph: "·" },
  todo: { cls: "border border-line-strong bg-subtle text-ink-3", glyph: "·" },
};
/** Who did it, by the hue of their part of the product (never a status). */
const ACTOR: Record<"BUYER" | "AGENT" | "OWNER" | "BANK", string> = {
  BUYER: "bg-sec-deals-bg text-sec-deals-fg",
  AGENT: "bg-brand-50 text-brand-700",
  OWNER: "bg-sec-recv-bg text-sec-recv-fg",
  BANK: "bg-sec-cash-bg text-sec-cash-fg",
};
const TH = "whitespace-nowrap border-b border-line px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.05em] text-ink-3";
const TD = "border-b border-line p-2 align-top tabular-nums";
const BUTTON = "inline-flex items-center rounded-lg border px-3 py-1.5 text-[13px] font-semibold";

function Tick({ kind }: { kind: keyof typeof TICK }) {
  return (
    <span aria-hidden className={`inline-grid size-[18px] flex-none place-items-center rounded-full text-[11px] font-bold ${TICK[kind].cls}`}>
      {TICK[kind].glyph}
    </span>
  );
}

/** "§5–6" from the clauses the obligations quote (5.1, 5.2, 6.1(a) …); null when none of them is numbered. */
function clauseRange(clauses: (string | null)[]): string | null {
  const nums = clauses.map((c) => (c ? /^(\d+)/.exec(c)?.[1] : undefined)).filter((n): n is string => Boolean(n)).map(Number);
  if (!nums.length) return null;
  const lo = Math.min(...nums);
  const hi = Math.max(...nums);
  return lo === hi ? `§${lo}` : `§${lo}–${hi}`;
}

/** Where a clause link lands: the confirmed contract on the documents page, that term lit up and scrolled into view. */
function clauseHref(docId: string, focus: { span?: { start: number; end: number } | null; clause?: string | null }): string {
  const q = new URLSearchParams({ id: docId });
  if (focus.span) q.set("at", `${focus.span.start}-${focus.span.end}`);
  if (focus.clause) q.set("clause", focus.clause);
  return `/documents?${q.toString()}`;
}

/** "§4.2 ↗": the clause as a link into the contract (its words are the tooltip), in place of the quote printed under every term. */
function ClauseLink({ docId, clause, span, quote }: { docId: string | null; clause: string | null; span?: { start: number; end: number } | null; quote?: string }) {
  const { t } = useI18n();
  const label = clause ? (/^\d/.test(clause) ? t("deal.clause", { n: clause }) : clause) : t("deal.seeClause");
  if (!docId) return clause ? <span className="font-mono text-[11px] text-ink-3">{label}</span> : null;
  return (
    <Link
      href={clauseHref(docId, { span, clause })}
      title={quote ? `“${quote}”` : undefined}
      aria-label={t("deal.openClause", { clause: label })}
      className="inline-flex min-h-6 shrink-0 items-center gap-0.5 whitespace-nowrap rounded-md bg-sec-deals-bg px-1.5 font-mono text-[11px] font-semibold text-sec-deals-fg hover:underline"
    >
      {label}
      <span aria-hidden>↗</span>
    </Link>
  );
}

export function DealSummary({ deal }: { deal: DealView }) {
  const { t, te } = useI18n();
  const c = deal.contract;
  const docId = c?.record_id ?? null;
  const meta = [c?.title, c?.signed_display ? t("deal.signed", { date: c.signed_display }) : null, c?.term_display, c?.cadence_display].filter(Boolean).join(" · ");
  const blanks = deal.blanks ?? [];
  const owed = deal.owed_by_us ?? { display_only: true, deliverables: [], documents: [] };
  const range = clauseRange([...owed.deliverables, ...owed.documents].map((o) => o.clause));
  const next = deal.next_action;
  const inForce = deal.in_force ?? [];
  const changed = inForce.filter((r) => r.vs_contract === "DIFFERENT" || r.vs_contract === "NOT_IN_CONTRACT");
  const same = inForce.filter((r) => r.vs_contract === "SAME" || r.vs_contract === "NONE");
  const checks = deal.checks ?? [];
  const flagged = checks.filter((ch) => ch.status === "warn").length;
  return (
    <article className="overflow-hidden rounded-(--radius-card) border border-line" data-testid={`deal-summary-${deal.counterparty_id}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2.5 border-b border-line bg-subtle px-4 py-3.5">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-ink">{deal.counterparty_name}</h3>
          <p className="text-[12.5px] text-ink-3">
            {meta}
            {docId ? (
              <>
                {" · "}
                <Link href={`/documents?id=${encodeURIComponent(docId)}`} className="font-medium text-brand-600 hover:underline" data-testid="deal-contract-link">
                  {t("deals.summary.contract")}
                </Link>
              </>
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5" data-testid="deal-pills">
          {deal.pills?.map((p) => (
            <Pill key={p.label} tone={p.tone}>
              {p.label}
            </Pill>
          ))}
        </div>
      </div>

      {/* The answer first: does this deal need me, and what do I press. */}
      {next ? (
        <div className={`flex flex-wrap items-center justify-between gap-x-3.5 gap-y-2.5 border-b px-4 py-3 ${NEXT[next.tone]}`} data-testid="deal-next" data-tone={next.tone}>
          <p className="min-w-0 flex-[1_1_28rem] text-ink">
            <b className="mr-1.5">{t("deal.next")}:</b>
            {next.text}
          </p>
          {next.actions.length ? (
            <div className="flex flex-wrap gap-2">
              {next.actions.map((a) => (
                <Link
                  key={a.key}
                  href={a.href}
                  className={`${BUTTON} ${a.primary ? "border-brand-600 bg-brand-600 text-white hover:bg-brand-700" : "border-line-strong bg-surface text-ink hover:bg-subtle"}`}
                >
                  {a.label}
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <ol className="grid grid-cols-5 px-1 pb-1.5 pt-3.5 sm:px-4" aria-label={t("deal.stages")} data-testid="deal-stages">
        {deal.stages?.map((s) => {
          const reached = s.state === "done" || s.state === "now";
          const late = s.state === "now" && s.tone === "bad";
          return (
            <li
              key={s.key}
              data-state={s.state}
              aria-current={s.state === "now" ? "step" : undefined}
              className={`relative grid justify-items-center gap-1.5 text-center text-[11px] sm:text-xs before:absolute before:-left-1/2 before:top-[7px] before:h-0.5 before:w-full first:before:hidden ${
                reached ? "before:bg-brand-600" : "before:bg-line-strong"
              } ${late ? "font-semibold text-bad-fg" : s.state === "now" ? "font-semibold text-ink" : "text-ink-3"}`}
            >
              <span aria-hidden className={`relative z-10 size-4 rounded-full border-2 ${late ? NOW_BAD : DOT[s.state]}`} />
              <span>
                {te("dealstage", s.key) || s.label}
                <span className="sr-only">: {te("dealstate", s.state)}</span>
              </span>
              <small className="hidden text-[11px] font-normal text-ink-3 sm:block">{s.note}</small>
            </li>
          );
        })}
      </ol>

      <div className="grid border-t border-line md:grid-cols-2">
        {/* What the contract says: each term's value, and its clause as a link into the document (the words open there, not here). */}
        <section className="min-w-0 px-4 py-3.5" data-testid="deal-contract">
          <DealHeading>
            {t("deal.contract")} <Pill>{t("docs.confirmedLabel")}</Pill>
          </DealHeading>
          <dl className="divide-y divide-line">
            {deal.contract_terms?.map((term, i) => (
              <div key={`${term.field}-${i}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-1.5 sm:grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)_auto]">
                <dt className="col-span-2 text-[13px] text-ink-3 sm:col-span-1">{te("contractfield", term.field) || term.label}</dt>
                <dd className="min-w-0 text-[13.5px] font-medium text-ink">{term.value_display}</dd>
                <dd>
                  <ClauseLink docId={docId} clause={term.clause} span={term.span} quote={term.quote} />
                </dd>
              </div>
            ))}
          </dl>
          {blanks.length ? (
            <p className="mt-2 text-xs text-ink-3" data-testid="deal-blanks" title={t("deal.notFoundHint")}>
              {t("deal.notInContractList", { list: blanks.map((b) => te("contractfield", b.field) || b.label).join(", ") })}
            </p>
          ) : null}
        </section>

        {/* What changed: each difference as Contract → Now, the unchanged terms in one line, then who did what. */}
        <section className="min-w-0 border-t border-line px-4 py-3.5 md:border-l md:border-t-0">
          <DealHeading>{t("deal.changes")}</DealHeading>
          <div className="space-y-2" data-testid="deal-in-force">
            {changed.map((r) => (
              <div key={r.key} className="rounded-tile border border-warn-line bg-warn-bg/50 px-3 py-2" data-vs={r.vs_contract}>
                <p className="text-xs font-bold text-ink">{r.label}</p>
                <div className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2.5 gap-y-0.5 text-[13px]">
                  {r.vs_contract === "DIFFERENT" && r.contract_display ? (
                    <>
                      <span className="text-ink-3">{t("deal.wasNow.contract")}</span>
                      <span className="text-ink-3 line-through decoration-ink-3/40">{r.contract_display}</span>
                    </>
                  ) : null}
                  <span className="font-bold text-warn-fg">{r.vs_contract === "DIFFERENT" ? t("deal.wasNow.now") : t("deal.newTerm")}</span>
                  <span className="font-semibold text-ink">{r.value_display}</span>
                </div>
              </div>
            ))}
            {same.length ? (
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="mr-0.5 font-semibold text-ink-3">{t("deal.unchanged")}:</span>
                {same.map((r) => (
                  <span key={r.key} className="inline-flex items-center gap-1 rounded-pill border border-line bg-surface px-2 py-0.5 text-ink-2" data-vs={r.vs_contract}>
                    {r.vs_contract === "SAME" ? (
                      <span aria-hidden className="text-ok-fg">
                        ✓
                      </span>
                    ) : null}
                    {r.label} <b className="font-semibold text-ink">{r.value_display}</b>
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <DealHeading className="mt-4">{t("deal.history")}</DealHeading>
          <ol className="relative grid gap-2.5 before:absolute before:bottom-3 before:left-[13px] before:top-3 before:w-px before:bg-line" data-testid="deal-changes">
            {deal.changes?.map((ch, i) => (
              <li key={i} className="relative grid grid-cols-[28px_minmax(0,1fr)] gap-2.5">
                <span aria-hidden className={`z-10 grid size-7 place-items-center rounded-full text-[11px] font-bold ${ACTOR[ch.actor]}`}>
                  {te("deal.actor", ch.actor).slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0">
                  <p className="flex flex-wrap items-baseline gap-x-2 text-xs">
                    <span className="font-bold text-ink">{ch.label}</span>
                    {ch.day === null ? null : <span className="font-mono text-ink-3">{t("deal.dayShort", { n: ch.day })}</span>}
                  </p>
                  <p className="break-words text-[13px] leading-snug text-ink-2">{ch.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <section className="border-t border-line px-4 py-3.5">
        <DealHeading>{t("deals.summary.money")}</DealHeading>
        {deal.invoices?.length ? (
          <div role="region" aria-label={t("deal.invoicesLabel", { name: deal.counterparty_name })} tabIndex={0} className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px] [&_tbody_tr:last-child_td]:border-b-0">
              <thead>
                <tr>
                  <th className={TH}>{t("deal.col.invoice")}</th>
                  <th className={`${TH} text-right`}>{t("deal.col.amount")}</th>
                  <th className={TH}>{t("deal.col.due")}</th>
                  <th className={`${TH} text-right`}>{t("deal.col.outstanding")}</th>
                  <th className={TH}>{t("deal.col.status")}</th>
                </tr>
              </thead>
              <tbody>
                {deal.invoices.map((inv) => (
                  <tr key={inv.id} data-testid={`deal-invoice-${inv.id}`} data-status={inv.status}>
                    <td className={TD}>
                      {inv.label}
                      <span className="block text-xs text-ink-3">{t("deal.issued", { n: inv.issue_day })}</span>
                    </td>
                    <td className={`${TD} text-right`}>{inv.amount_display}</td>
                    <td className={`${TD} whitespace-nowrap`}>{t("deal.dayShort", { n: inv.due_day })}</td>
                    <td className={`${TD} text-right`}>{inv.outstanding_display}</td>
                    <td className={TD}>
                      <Pill tone={inv.tone}>{inv.status_text}</Pill>
                      {inv.notes.map((n) => (
                        <span key={n} className="block text-xs text-ink-3">
                          {n}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-ink-3">{t("deal.noInvoices")}</p>
        )}
        {deal.next_invoice ? (
          <p className="mt-2 text-xs text-ink-3">{t("deal.nextInvoice", { day: deal.next_invoice.day, amount: deal.next_invoice.amount_display })}</p>
        ) : null}
      </section>

      <div className="grid border-t border-line md:grid-cols-2">
        <section className="min-w-0 px-4 py-3.5" data-testid="deal-owed">
          <DealHeading>
            {t("deal.owed")} <Pill>{range ? t("deal.owedFrom", { range }) : t("deal.owedBadge")}</Pill>
          </DealHeading>
          <Owed title={t("deal.deliverables")} items={owed.deliverables} docId={docId} />
          <div className="mt-2.5">
            <Owed title={t("deal.documents")} items={owed.documents} docId={docId} />
          </div>
        </section>
        {/* The check in one line; the list opens by itself only when something needs a look. */}
        <section className="min-w-0 border-t border-line px-4 py-3.5 md:border-l md:border-t-0">
          <DealHeading>{t("deal.checks")}</DealHeading>
          <details className="group" open={flagged > 0 || undefined}>
            <summary className="flex min-h-8 cursor-pointer list-none flex-wrap items-center gap-2 text-sm font-semibold [&::-webkit-details-marker]:hidden">
              <Tick kind={flagged ? "warn" : "ok"} />
              <span className={flagged ? "text-warn-fg" : "text-ok-fg"}>{flagged ? t("deal.checksSome", { bad: flagged, n: checks.length }) : t("deal.checksAll", { n: checks.length })}</span>
              <span className="text-xs font-medium text-brand-700 underline underline-offset-2 group-open:hidden">{t("deal.inFull")}</span>
            </summary>
            <ul className="mt-2 grid gap-1.5" data-testid="deal-checks">
              {checks.map((ch, i) => (
                <li key={i} className="flex items-baseline gap-2 text-[13px]" data-status={ch.status}>
                  <Tick kind={ch.status} />
                  <span className="min-w-0 text-ink-2">{ch.text}</span>
                </li>
              ))}
            </ul>
          </details>
        </section>
      </div>
    </article>
  );
}

/** What the supplier owes, listed from the contract with its clause as a link into it; shown, never tracked (brief 03, Q1). */
function Owed({ title, items, docId }: { title: string; items: { text: string | null; clause: string | null; quote: string }[]; docId: string | null }) {
  const { t } = useI18n();
  return (
    <>
      <p className="mb-1 text-xs font-medium text-ink-2">{title}</p>
      {items.length ? (
        <ul className="grid gap-1.5">
          {items.map((it, i) => (
            <li key={i} className="flex items-baseline gap-2">
              <Tick kind="todo" />
              <span className="min-w-0 text-[13.5px] text-ink">
                {it.text ?? it.quote}
                {it.clause ? (
                  <span className="ml-1.5">
                    <ClauseLink docId={docId} clause={it.clause} quote={it.quote} />
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-ink-3">{t("deal.owedNone")}</p>
      )}
    </>
  );
}
