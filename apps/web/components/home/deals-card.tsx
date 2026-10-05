"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ClauseLabel, ClauseQuote, contractsOff, DEAL_TONE } from "@/components/documents";
import { Badge, Card, ErrorState, LoadingBlock, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getDeals } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { DealTone, DealView, StageState } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { SectionLink } from "./today-card";

/**
 * Each buyer's deal: the contract the owner confirmed (every term with its clause and quote) beside the live books
 * (what changed since signing, the terms in force, the invoices and what to do next). GET /deals builds it all; every
 * amount, date and sentence here is a server string. A buyer without a confirmed contract gets a placeholder.
 */
export function DealsCard() {
  const { t } = useI18n();
  const deals = useAsync(getDeals, []);
  const list = deals.data?.deals ?? [];
  return (
    <Card id="home-deals" title={t("home.deals")} subtitle={t("home.deals.sub")} actions={<SectionLink href="/documents">{t("home.deals.open")}</SectionLink>}>
      {contractsOff(deals.error) ? (
        <p className="text-sm text-ink-3" data-testid="home-deals-off">
          {t("home.deals.off")}
        </p>
      ) : deals.error ? (
        <ErrorState error={deals.error} onRetry={deals.reload} />
      ) : !deals.data ? (
        <LoadingBlock rows={2} />
      ) : (
        <div className="space-y-4">
          {list
            .filter((d) => d.has_contract)
            .map((d) => (
              <Deal key={d.counterparty_id} deal={d} />
            ))}
          <div className="grid gap-3 sm:grid-cols-2">
            {list
              .filter((d) => !d.has_contract)
              .map((d) => (
                <div
                  key={d.counterparty_id}
                  className="rounded-lg border border-dashed border-line-strong px-3.5 py-3 text-sm"
                  data-testid={`home-deal-${d.counterparty_id}`}
                  data-has-contract="false"
                >
                  <p className="font-medium text-ink">{d.counterparty_name}</p>
                  {d.pending_documents.length ? (
                    <p className="mt-0.5 text-ink-2">
                      {t("home.deals.waiting", { id: d.pending_documents[0] })}{" "}
                      <Link href={`/documents?id=${encodeURIComponent(d.pending_documents[0])}`} className="font-medium text-brand-700 underline underline-offset-2">
                        {t("home.deals.review")}
                      </Link>
                    </p>
                  ) : (
                    <p className="mt-0.5 text-ink-3">{t("home.deals.none")}</p>
                  )}
                </div>
              ))}
            <Link href="/documents" className="rounded-lg border border-dashed border-line-strong px-3.5 py-3 text-sm hover:bg-subtle">
              <span className="block font-medium text-ink-2">{t("home.deals.add")}</span>
              <span className="mt-0.5 block text-ink-3">{t("home.deals.addHint")}</span>
            </Link>
          </div>
        </div>
      )}
    </Card>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return <h4 className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{children}</h4>;
}

const DOT: Record<StageState, string> = {
  done: "border-brand-600 bg-brand-600",
  now: "border-brand-600 bg-brand-50 ring-4 ring-brand-50",
  todo: "border-line-strong bg-surface",
  skipped: "border-dashed border-line-strong bg-subtle",
  pending: "border-warn-fg bg-warn-bg",
  missed: "border-bad-fg bg-bad-bg",
};
const NOW_BAD = "border-bad-fg bg-bad-bg ring-4 ring-bad-bg";
const NEXT: Record<DealTone, string> = {
  bad: "border-bad-line bg-bad-bg",
  warn: "border-warn-line bg-warn-bg",
  ok: "border-ok-line bg-ok-bg",
  info: "border-info-line bg-info-bg",
  mute: "border-line bg-subtle",
};
const CHECK: Record<"ok" | "warn" | "info", { cls: string; glyph: string }> = {
  ok: { cls: "bg-ok-bg text-ok-fg", glyph: "✓" },
  warn: { cls: "bg-warn-bg text-warn-fg", glyph: "!" },
  info: { cls: "border border-line-strong bg-subtle text-ink-3", glyph: "·" },
};
const LINK_BUTTON = "inline-flex min-h-8 items-center rounded-md border px-2.5 text-xs font-medium";

function Deal({ deal }: { deal: DealView }) {
  const { t, te } = useI18n();
  const c = deal.contract;
  const meta = [c?.title, c?.signed_display ? t("deal.signed", { date: c.signed_display }) : null, c?.term_display, c?.cadence_display].filter(Boolean).join(" · ");
  const blanks = deal.blanks ?? [];
  const next = deal.next_action;
  return (
    <article className="overflow-hidden rounded-lg border border-line" data-testid={`home-deal-${deal.counterparty_id}`} data-has-contract="true">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-subtle px-4 py-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-ink">{deal.counterparty_name}</h3>
          <p className="mt-0.5 text-xs text-ink-3">{meta}</p>
        </div>
        <div className="flex flex-wrap gap-1.5" data-testid="deal-pills">
          {deal.pills?.map((p) => (
            <Badge key={p.label} tone={DEAL_TONE[p.tone]}>
              {p.label}
            </Badge>
          ))}
        </div>
      </div>

      <ol className="grid grid-cols-5 px-1 pb-3 pt-4 sm:px-4" aria-label={t("deal.stages")} data-testid="deal-stages">
        {deal.stages?.map((s) => {
          const reached = s.state === "done" || s.state === "now";
          return (
            <li
              key={s.key}
              data-state={s.state}
              aria-current={s.state === "now" ? "step" : undefined}
              className={`relative flex flex-col items-center gap-1.5 text-center text-xs before:absolute before:-left-1/2 before:top-[7px] before:h-0.5 before:w-full first:before:hidden ${
                reached ? "before:bg-brand-600" : "before:bg-line-strong"
              } ${s.state === "now" ? (s.tone === "bad" ? "font-semibold text-bad-fg" : "font-semibold text-ink") : "text-ink-3"}`}
            >
              <span aria-hidden className={`relative z-10 size-4 rounded-full border-2 ${s.state === "now" && s.tone === "bad" ? NOW_BAD : DOT[s.state]}`} />
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
        <section className="min-w-0 p-4" data-testid="deal-contract">
          <Heading>
            {t("deal.contract")} <Badge>{t("docs.confirmedLabel")}</Badge>
          </Heading>
          <dl className="space-y-2.5">
            {deal.contract_terms?.map((term, i) => (
              <div key={`${term.field}-${i}`} className="grid gap-x-3 gap-y-0.5 sm:grid-cols-[8.5rem_minmax(0,1fr)]">
                <dt className="text-sm text-ink-3">{te("contractfield", term.field) || term.label}</dt>
                <dd className="min-w-0 text-sm font-medium text-ink">
                  {term.value_display}
                  <ClauseQuote clause={term.clause} quote={term.quote} />
                </dd>
              </div>
            ))}
            {blanks.length ? (
              <div className="grid gap-x-3 gap-y-0.5 sm:grid-cols-[8.5rem_minmax(0,1fr)]" data-testid="deal-blanks">
                <dt className="text-sm text-ink-3">{t("deal.notFound")}</dt>
                <dd className="min-w-0 text-sm">
                  <span className="flex flex-wrap gap-1">
                    {blanks.map((b) => (
                      <Badge key={b.field}>{te("contractfield", b.field) || b.label}</Badge>
                    ))}
                  </span>
                  <span className="mt-1 block border-l-2 border-line-strong pl-2 text-xs text-ink-3">{t("deal.notFoundHint")}</span>
                </dd>
              </div>
            ) : null}
          </dl>
        </section>

        <section className="min-w-0 border-t border-line p-4 md:border-l md:border-t-0">
          <Heading>{t("deal.changes")}</Heading>
          <ol className="space-y-2.5" data-testid="deal-changes">
            {deal.changes?.map((ch, i) => (
              <li key={i} className="grid grid-cols-[3.75rem_minmax(0,1fr)] gap-2.5">
                <span className="pt-0.5 font-mono text-xs text-ink-3">{ch.day === null ? "" : t("common.dayN", { n: ch.day })}</span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">{ch.label}</p>
                  <p className="break-words text-sm text-ink">{ch.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-4">
            <Heading>{t("deal.inForce")}</Heading>
            <dl className="space-y-2" data-testid="deal-in-force">
              {deal.in_force?.map((r) => (
                <div key={r.key} className="grid gap-x-3 sm:grid-cols-[8.5rem_minmax(0,1fr)]" data-vs={r.vs_contract}>
                  <dt className="text-sm text-ink-3">{r.label}</dt>
                  <dd className="min-w-0 text-sm font-medium text-ink">
                    {r.value_display}{" "}
                    {r.vs_contract === "NONE" ? null : (
                      <Badge tone={r.vs_contract === "SAME" ? "ok" : r.vs_contract === "DIFFERENT" ? "warn" : "info"}>{te("deal.vs", r.vs_contract)}</Badge>
                    )}
                    {r.vs_contract === "DIFFERENT" && r.contract_display ? (
                      <span className="mt-0.5 block text-xs font-normal text-ink-3">{t("deal.vsContract", { text: r.contract_display })}</span>
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </div>

      <section className="border-t border-line p-4">
        <Heading>{t("deal.money")}</Heading>
        {deal.invoices?.length ? (
          <TableWrap label={t("deal.invoicesLabel", { name: deal.counterparty_name })}>
            <table className={tableCls}>
              <thead>
                <tr>
                  <th className={thCls}>{t("deal.col.invoice")}</th>
                  <th className={`${thCls} text-right`}>{t("deal.col.amount")}</th>
                  <th className={thCls}>{t("deal.col.due")}</th>
                  <th className={`${thCls} text-right`}>{t("deal.col.outstanding")}</th>
                  <th className={thCls}>{t("deal.col.status")}</th>
                </tr>
              </thead>
              <tbody>
                {deal.invoices.map((inv) => (
                  <tr key={inv.id} data-testid={`deal-invoice-${inv.id}`} data-status={inv.status}>
                    <td className={tdCls}>
                      <span className="font-medium text-ink">{inv.label}</span>
                      <span className="block text-xs text-ink-3">{t("deal.issued", { n: inv.issue_day })}</span>
                    </td>
                    <td className={`${tdCls} text-right tabular-nums`}>{inv.amount_display}</td>
                    <td className={`${tdCls} whitespace-nowrap`}>{t("common.dayN", { n: inv.due_day })}</td>
                    <td className={`${tdCls} text-right tabular-nums`}>{inv.outstanding_display}</td>
                    <td className={tdCls}>
                      <Badge tone={DEAL_TONE[inv.tone]}>{inv.status_text}</Badge>
                      {inv.notes.map((n) => (
                        <span key={n} className="mt-0.5 block text-xs text-ink-3">
                          {n}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        ) : (
          <p className="text-sm text-ink-3">{t("deal.noInvoices")}</p>
        )}
        {deal.next_invoice ? (
          <p className="mt-2 text-xs text-ink-3">{t("deal.nextInvoice", { day: deal.next_invoice.day, amount: deal.next_invoice.amount_display })}</p>
        ) : null}
      </section>

      <div className="grid border-t border-line md:grid-cols-2">
        <section className="min-w-0 p-4" data-testid="deal-owed">
          <Heading>
            {t("deal.owed")} <Badge>{t("deal.owedBadge")}</Badge>
          </Heading>
          <Owed title={t("deal.deliverables")} items={deal.owed_by_us?.deliverables ?? []} />
          <div className="mt-3">
            <Owed title={t("deal.documents")} items={deal.owed_by_us?.documents ?? []} />
          </div>
        </section>
        <section className="min-w-0 border-t border-line p-4 md:border-l md:border-t-0">
          <Heading>{t("deal.checks")}</Heading>
          <ul className="space-y-1.5" data-testid="deal-checks">
            {deal.checks?.map((ch, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm" data-status={ch.status}>
                <span aria-hidden className={`inline-grid size-[18px] flex-none place-items-center rounded-full text-[11px] font-bold ${CHECK[ch.status].cls}`}>
                  {CHECK[ch.status].glyph}
                </span>
                <span className="min-w-0 text-ink">{ch.text}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {next ? (
        <div className={`flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 ${NEXT[next.tone]}`} data-testid="deal-next" data-tone={next.tone}>
          <p className="min-w-0 text-sm text-ink">
            <span className="font-semibold">{t("deal.next")}:</span> {next.text}
          </p>
          {next.actions.length ? (
            <div className="flex flex-wrap gap-2">
              {next.actions.map((a) => (
                <Link
                  key={a.key}
                  href={a.href}
                  className={`${LINK_BUTTON} ${a.primary ? "border-transparent bg-brand-600 text-white hover:bg-brand-700" : "border-line-strong bg-surface text-ink hover:bg-subtle"}`}
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

function Owed({ title, items }: { title: string; items: { text: string | null; clause: string | null; quote: string }[] }) {
  const { t } = useI18n();
  return (
    <>
      <p className="text-xs font-medium text-ink-2">{title}</p>
      {items.length ? (
        <ul className="mt-1 space-y-1">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2 text-sm text-ink">
              <span aria-hidden className="text-ink-3">
                ·
              </span>
              <span className="min-w-0">
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
        <p className="mt-1 text-sm text-ink-3">{t("deal.owedNone")}</p>
      )}
    </>
  );
}
