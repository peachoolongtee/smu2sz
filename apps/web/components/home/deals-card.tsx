"use client";

import Link from "next/link";
import { CardLink, ClauseLabel, ClauseQuote, ContractCard, contractsOff, DealHeading, Pill } from "@/components/documents";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { getDeals } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { DealTone, DealView, StageState } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/**
 * Each buyer's deal, laid out as the brief-03 prototype: the contract the owner confirmed (every term with its clause and
 * quote) beside the live books (what changed since signing, the terms in force, the invoices, what each side owes and what to
 * do next). GET /deals builds it all; every amount, date and sentence here is a server string. A buyer without a confirmed
 * contract gets a placeholder.
 */
export function DealsCard() {
  const { t } = useI18n();
  const deals = useAsync(getDeals, []);
  const list = deals.data?.deals ?? [];
  return (
    <ContractCard id="home-deals" title={t("home.deals")} aside={<CardLink href="/documents">{t("home.deals.open")} →</CardLink>}>
      {contractsOff(deals.error) ? (
        <p className="text-sm text-ink-3" data-testid="home-deals-off">
          {t("home.deals.off")}
        </p>
      ) : deals.error ? (
        <ErrorState error={deals.error} onRetry={deals.reload} />
      ) : !deals.data ? (
        <LoadingBlock rows={2} />
      ) : (
        <div className="space-y-3">
          {list
            .filter((d) => d.has_contract)
            .map((d) => (
              <Deal key={d.counterparty_id} deal={d} />
            ))}
          <div className="grid gap-3 md:grid-cols-2">
            {list
              .filter((d) => !d.has_contract)
              .map((d) => (
                <div
                  key={d.counterparty_id}
                  className="grid gap-1 rounded-(--radius-card) border border-dashed border-line-strong px-3.5 py-3 text-ink-3"
                  data-testid={`home-deal-${d.counterparty_id}`}
                  data-has-contract="false"
                >
                  <b className="font-semibold text-ink-2">{d.counterparty_name}</b>
                  {d.pending_documents.length ? (
                    <span>
                      {t("home.deals.waiting", { id: d.pending_documents[0] })}{" "}
                      <Link href={`/documents?id=${encodeURIComponent(d.pending_documents[0])}`} className="font-medium text-brand-600 hover:underline">
                        {t("home.deals.review")}
                      </Link>
                    </span>
                  ) : (
                    <span>{t("home.deals.none")}</span>
                  )}
                </div>
              ))}
            <Link href="/documents" className="grid gap-1 rounded-(--radius-card) border border-dashed border-line-strong px-3.5 py-3 text-ink-3 hover:bg-subtle">
              <b className="font-semibold text-ink-2">{t("home.deals.add")}</b>
              <span>{t("home.deals.addHint")}</span>
            </Link>
          </div>
        </div>
      )}
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
/** The prototype's term row: a 140px label beside the value, one column on a phone. */
const TERM = "grid items-baseline gap-x-3 gap-y-0.5 sm:grid-cols-[140px_minmax(0,1fr)]";
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

function Deal({ deal }: { deal: DealView }) {
  const { t, te } = useI18n();
  const c = deal.contract;
  const meta = [c?.title, c?.signed_display ? t("deal.signed", { date: c.signed_display }) : null, c?.term_display, c?.cadence_display].filter(Boolean).join(" · ");
  const blanks = deal.blanks ?? [];
  const owed = deal.owed_by_us ?? { display_only: true, deliverables: [], documents: [] };
  const range = clauseRange([...owed.deliverables, ...owed.documents].map((o) => o.clause));
  const next = deal.next_action;
  return (
    <article className="overflow-hidden rounded-(--radius-card) border border-line" data-testid={`home-deal-${deal.counterparty_id}`} data-has-contract="true">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2.5 border-b border-line bg-subtle px-4 py-3.5">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-ink">{deal.counterparty_name}</h3>
          <p className="text-[12.5px] text-ink-3">{meta}</p>
        </div>
        <div className="flex flex-wrap gap-1.5" data-testid="deal-pills">
          {deal.pills?.map((p) => (
            <Pill key={p.label} tone={p.tone}>
              {p.label}
            </Pill>
          ))}
        </div>
      </div>

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
        <section className="min-w-0 px-4 py-3.5" data-testid="deal-contract">
          <DealHeading>
            {t("deal.contract")} <Pill>{t("docs.confirmedLabel")}</Pill>
          </DealHeading>
          <dl className="grid gap-2">
            {deal.contract_terms?.map((term, i) => (
              <div key={`${term.field}-${i}`} className={TERM}>
                <dt className="text-[13px] text-ink-3">{te("contractfield", term.field) || term.label}</dt>
                <dd className="min-w-0 font-medium text-ink">
                  {term.value_display}
                  <ClauseQuote clause={term.clause} quote={term.quote} />
                </dd>
              </div>
            ))}
            {blanks.length ? (
              <div className={TERM} data-testid="deal-blanks">
                <dt className="text-[13px] text-ink-3">{t("deal.notFound")}</dt>
                <dd className="min-w-0 font-medium">
                  <span className="flex flex-wrap gap-1">
                    {blanks.map((b) => (
                      <Pill key={b.field}>{te("contractfield", b.field) || b.label}</Pill>
                    ))}
                  </span>
                  <span className="mt-[3px] block border-l-2 border-line-strong pl-2 text-xs font-normal text-ink-3">{t("deal.notFoundHint")}</span>
                </dd>
              </div>
            ) : null}
          </dl>
        </section>

        <section className="min-w-0 border-t border-line px-4 py-3.5 md:border-l md:border-t-0">
          <DealHeading>{t("deal.changes")}</DealHeading>
          <ol className="grid gap-2.5" data-testid="deal-changes">
            {deal.changes?.map((ch, i) => (
              <li key={i} className="grid grid-cols-[56px_minmax(0,1fr)] gap-2.5">
                <span className="pt-px font-mono text-xs text-ink-3">{ch.day === null ? "" : t("deal.dayShort", { n: ch.day })}</span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.04em] text-ink-3">{ch.label}</p>
                  <p className="break-words text-ink">{ch.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <DealHeading className="mt-3.5">{t("deal.inForce")}</DealHeading>
          <dl className="grid gap-2" data-testid="deal-in-force">
            {deal.in_force?.map((r) => (
              <div key={r.key} className={TERM} data-vs={r.vs_contract}>
                <dt className="text-[13px] text-ink-3">{r.label}</dt>
                <dd className="min-w-0 font-medium text-ink">
                  {r.value_display}{" "}
                  {r.vs_contract === "NONE" ? null : (
                    <Pill tone={r.vs_contract === "SAME" ? "ok" : r.vs_contract === "DIFFERENT" ? "warn" : "info"}>{te("deal.vs", r.vs_contract)}</Pill>
                  )}
                  {r.vs_contract === "DIFFERENT" && r.contract_display ? (
                    <span className="mt-[3px] block text-xs font-normal text-ink-3">{t("deal.vsContract", { text: r.contract_display })}</span>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <section className="border-t border-line px-4 py-3.5">
        <DealHeading>{t("deal.money")}</DealHeading>
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
          <Owed title={t("deal.deliverables")} items={owed.deliverables} />
          <div className="mt-2.5">
            <Owed title={t("deal.documents")} items={owed.documents} />
          </div>
        </section>
        <section className="min-w-0 border-t border-line px-4 py-3.5 md:border-l md:border-t-0">
          <DealHeading>{t("deal.checks")}</DealHeading>
          <ul className="grid gap-1.5" data-testid="deal-checks">
            {deal.checks?.map((ch, i) => (
              <li key={i} className="flex items-baseline gap-2" data-status={ch.status}>
                <Tick kind={ch.status} />
                <span className="min-w-0 text-ink">{ch.text}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {next ? (
        <div className={`flex flex-wrap items-center justify-between gap-x-3.5 gap-y-2.5 border-t px-4 py-3 ${NEXT[next.tone]}`} data-testid="deal-next" data-tone={next.tone}>
          {/* The text wraps beside the buttons, as in the prototype; on a narrow screen the buttons drop below it. */}
          <div className="min-w-0 flex-[1_1_28rem]">
            <b>{t("deal.next")}:</b> <p className="text-ink">{next.text}</p>
          </div>
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
    </article>
  );
}

/** What the supplier owes, listed from the contract with its clause; shown, never tracked (brief 03, Q1). */
function Owed({ title, items }: { title: string; items: { text: string | null; clause: string | null; quote: string }[] }) {
  const { t } = useI18n();
  return (
    <>
      <p className="mb-1 text-xs font-medium text-ink-2">{title}</p>
      {items.length ? (
        <ul className="grid gap-1.5">
          {items.map((it, i) => (
            <li key={i} className="flex items-baseline gap-2">
              <Tick kind="todo" />
              <span className="min-w-0 text-ink">
                {it.text ?? it.quote}
                {it.clause ? (
                  <span className="ml-1">
                    <ClauseLabel clause={it.clause} />
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
