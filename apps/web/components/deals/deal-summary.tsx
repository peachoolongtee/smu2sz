"use client";

import Link from "next/link";
import { Disclosure } from "@/components/business/kit";
import { ClauseLabel, ClauseQuote, DealHeading } from "@/components/documents";
import { Callout, Chip, StatePill, textLinkClass, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { DealTone, DealView, StageState } from "@/lib/types";
import { whenText } from "@/lib/when";

/** Agreed by both parties: a confirmed contract and the "Terms negotiated" stage done (the server's accepted commitment). */
export function isAgreed(d: DealView): boolean {
  return d.has_contract && Boolean(d.stages?.some((s) => s.key === "negotiated" && s.state === "done"));
}

/** The server names a tone from its own five (`mute` for a quiet one); the app's pills and callouts call that `neutral`. */
const toneOf = (tone: DealTone): Tone => (tone === "mute" ? "neutral" : tone);

const DOT: Record<StageState, string> = {
  done: "border-brand-600 bg-brand-600",
  now: "border-brand-600 bg-brand-50 ring-3 ring-brand-50",
  todo: "border-line-strong bg-surface",
  skipped: "border-dashed border-line-strong bg-subtle",
  pending: "border-warn-fg bg-warn-bg",
  missed: "border-bad-fg bg-bad-bg",
};
const NOW_BAD = "border-bad-fg bg-bad-bg ring-3 ring-bad-bg";
/** A mark that goes with each check's tone, so a check is never colour alone. */
const TICK: Record<"ok" | "warn" | "info" | "todo", { cls: string; glyph: string }> = {
  ok: { cls: "bg-ok-bg text-ok-fg", glyph: "✓" },
  warn: { cls: "bg-warn-bg text-warn-fg", glyph: "!" },
  info: { cls: "border border-line-strong bg-subtle text-ink-3", glyph: "·" },
  todo: { cls: "border border-line-strong bg-subtle text-ink-3", glyph: "·" },
};
/** A term row: a label beside its value, one column on a phone. */
const TERM = "grid items-baseline gap-x-3 gap-y-0.5 sm:grid-cols-[9rem_minmax(0,1fr)]";
const TH = "whitespace-nowrap border-b border-line px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wider text-ink-3";
const TD = "border-b border-line p-2 align-top tabular-nums";

function Tick({ kind }: { kind: keyof typeof TICK }) {
  return (
    <span aria-hidden className={`inline-grid size-5 flex-none place-items-center rounded-pill text-xs font-bold ${TICK[kind].cls}`}>
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

/**
 * The summary of one agreed deal (brief 03), inside the buyer's agreement on Deals: a headline (where it stands, in the server's pills), two to
 * four facts, and the one thing to do; the stages, the contract's terms, what changed, what is in force, the invoices, what you owe and the
 * checks are behind one fold. The page passes GET /deals; every amount, date and sentence is a server string, and a day is said as a distance
 * from `today` where the server sent no `*_when` of its own.
 */
export function DealSummary({ deal, today }: { deal: DealView; today: number }) {
  const { t, te } = useI18n();
  const c = deal.contract;
  const meta = [c?.title, c?.signed_display ? t("deal.signed", { date: c.signed_display }) : null, c?.term_display, c?.cadence_display].filter(Boolean).join(" · ");
  const blanks = deal.blanks ?? [];
  const owed = deal.owed_by_us ?? { display_only: true, deliverables: [], documents: [] };
  const range = clauseRange([...owed.deliverables, ...owed.documents].map((o) => o.clause));
  const next = deal.next_action;
  const when = (server: string | null | undefined, day: number | null | undefined) => server || (day === null || day === undefined ? "" : whenText(day, today, t));
  // The stage the deal is at: the one in progress, else the last one done.
  const stages = deal.stages ?? [];
  const here = stages.find((s) => s.state === "now") ?? [...stages].reverse().find((s) => s.state === "done") ?? null;
  const lead = next ? (next.actions.find((a) => a.primary) ?? next.actions[0] ?? null) : null;
  const others = next ? next.actions.filter((a) => a !== lead) : [];

  return (
    <div className="mt-3 border-t border-line pt-3" data-testid={`deal-summary-${deal.counterparty_id}`}>
      {deal.pills?.length ? (
        <div className="flex flex-wrap gap-1.5" data-testid="deal-pills">
          {deal.pills.map((p) => (
            <StatePill key={p.label} tone={toneOf(p.tone)}>
              {p.label}
            </StatePill>
          ))}
        </div>
      ) : null}

      <dl className="mt-2 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-3" data-testid="deal-facts">
        {here ? (
          <div>
            <dt className="text-xs text-ink-3">{t("deal.facts.stage")}</dt>
            <dd className="font-medium text-ink" data-testid="deal-stage-now">
              {te("dealstage", here.key) || here.label} <span className="text-xs font-normal text-ink-3">· {te("dealstate", here.state)}</span>
            </dd>
          </div>
        ) : null}
        <div className="min-w-0">
          <dt className="text-xs text-ink-3">{t("deal.facts.contract")}</dt>
          <dd className="break-words font-medium text-ink">
            {meta}
            {c?.record_id ? (
              <>
                {" · "}
                <Link href={`/documents?id=${encodeURIComponent(c.record_id)}`} className={textLinkClass} data-testid="deal-contract-link">
                  {t("deals.summary.contract")}
                </Link>
              </>
            ) : null}
          </dd>
        </div>
        {deal.next_invoice ? (
          <div>
            <dt className="text-xs text-ink-3">{t("deal.facts.invoice")}</dt>
            <dd className="font-medium tabular-nums text-ink" data-testid="deal-next-invoice">
              {[when(deal.next_invoice.when, deal.next_invoice.day), deal.next_invoice.amount_display].filter(Boolean).join(" · ")}
            </dd>
          </div>
        ) : null}
      </dl>

      {next ? (
        <div className="mt-3" data-testid="deal-next" data-tone={next.tone}>
          <Callout tone={toneOf(next.tone)} title={t("deal.next")}>
            <p className="text-ink">{next.text}</p>
            {lead ? (
              <Link href={lead.href} className={`${textLinkClass} -ml-2 mt-1`}>
                {lead.label}
              </Link>
            ) : null}
          </Callout>
        </div>
      ) : null}

      <Disclosure className="mt-2" summary={t("deal.fold")} testId={`deal-details-${deal.counterparty_id}`}>
        <div className="space-y-5 text-sm">
          {stages.length ? (
            <ol className="grid grid-cols-5" aria-label={t("deal.stages")} data-testid="deal-stages">
              {stages.map((s) => {
                const reached = s.state === "done" || s.state === "now";
                const late = s.state === "now" && s.tone === "bad";
                return (
                  <li
                    key={s.key}
                    data-state={s.state}
                    aria-current={s.state === "now" ? "step" : undefined}
                    className={`relative grid justify-items-center gap-1 text-center text-xs before:absolute before:-left-1/2 before:top-1.75 before:h-0.5 before:w-full first:before:hidden ${
                      reached ? "before:bg-brand-600" : "before:bg-line-strong"
                    } ${late ? "font-semibold text-bad-fg" : s.state === "now" ? "font-semibold text-ink" : "text-ink-3"}`}
                  >
                    <span aria-hidden className={`relative z-10 size-4 rounded-pill border-2 ${late ? NOW_BAD : DOT[s.state]}`} />
                    <span>{te("dealstage", s.key) || s.label}</span>
                    {/* The state in words as well as in the dot's colour. */}
                    <span className="font-normal" data-testid="deal-stage-state">
                      {te("dealstate", s.state)}
                    </span>
                    <small className="hidden text-xs font-normal text-ink-3 sm:block">{s.note}</small>
                  </li>
                );
              })}
            </ol>
          ) : null}

          <section className="min-w-0" data-testid="deal-contract">
            <DealHeading>
              {t("deal.contract")} <Chip tone="ok">{t("docs.confirmedLabel")}</Chip>
            </DealHeading>
            <dl className="grid gap-2">
              {deal.contract_terms?.map((term, i) => (
                <div key={`${term.field}-${i}`} className={TERM}>
                  <dt className="text-sm text-ink-3">{te("contractfield", term.field) || term.label}</dt>
                  <dd className="min-w-0 font-medium text-ink">
                    {term.value_display}
                    <ClauseQuote clause={term.clause} quote={term.quote} />
                  </dd>
                </div>
              ))}
              {blanks.length ? (
                <div className={TERM} data-testid="deal-blanks">
                  <dt className="text-sm text-ink-3">{t("deal.notFound")}</dt>
                  <dd className="min-w-0 font-medium">
                    <span className="flex flex-wrap gap-1">
                      {blanks.map((b) => (
                        <Chip key={b.field}>{te("contractfield", b.field) || b.label}</Chip>
                      ))}
                    </span>
                    <span className="mt-1 block border-l-2 border-line-strong pl-2 text-xs font-normal text-ink-3">{t("deal.notFoundHint")}</span>
                  </dd>
                </div>
              ) : null}
            </dl>
          </section>

          <section className="min-w-0">
            <DealHeading>{t("deal.changes")}</DealHeading>
            <ol className="grid gap-2.5" data-testid="deal-changes">
              {deal.changes?.map((ch, i) => (
                <li key={i} className="grid gap-x-2.5 sm:grid-cols-[6rem_minmax(0,1fr)]">
                  <span className="pt-px text-xs text-ink-3">{when(ch.when, ch.day)}</span>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">{ch.label}</p>
                    <p className="break-words text-ink">{ch.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="min-w-0">
            <DealHeading>{t("deal.inForce")}</DealHeading>
            <dl className="grid gap-2" data-testid="deal-in-force">
              {deal.in_force?.map((r) => (
                <div key={r.key} className={TERM} data-vs={r.vs_contract}>
                  <dt className="text-sm text-ink-3">{r.label}</dt>
                  <dd className="min-w-0 font-medium text-ink">
                    {r.value_display}{" "}
                    {r.vs_contract === "NONE" ? null : (
                      <StatePill tone={r.vs_contract === "SAME" ? "ok" : r.vs_contract === "DIFFERENT" ? "warn" : "info"}>{te("deal.vs", r.vs_contract)}</StatePill>
                    )}
                    {r.vs_contract === "DIFFERENT" && r.contract_display ? (
                      <span className="mt-1 block text-xs font-normal text-ink-3">{t("deal.vsContract", { text: r.contract_display })}</span>
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="min-w-0">
            <DealHeading>{t("deals.summary.money")}</DealHeading>
            {deal.invoices?.length ? (
              <div role="region" aria-label={t("deal.invoicesLabel", { name: deal.counterparty_name })} tabIndex={0} className="overflow-x-auto">
                <table className="w-full border-collapse text-sm [&_tbody_tr:last-child_td]:border-b-0">
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
                          <span className="block text-xs text-ink-3">{t("deal.issued", { when: when(inv.issue_when, inv.issue_day) })}</span>
                        </td>
                        <td className={`${TD} text-right`}>{inv.amount_display}</td>
                        <td className={`${TD} whitespace-nowrap`}>{when(inv.due_when, inv.due_day)}</td>
                        <td className={`${TD} text-right`}>{inv.outstanding_display}</td>
                        <td className={TD}>
                          <StatePill tone={toneOf(inv.tone)} wrap={false}>
                            {inv.status_text}
                          </StatePill>
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
          </section>

          <section className="min-w-0" data-testid="deal-owed">
            <DealHeading>
              {t("deal.owed")} <Chip>{range ? t("deal.owedFrom", { range }) : t("deal.owedBadge")}</Chip>
            </DealHeading>
            <Owed title={t("deal.deliverables")} items={owed.deliverables} />
            <div className="mt-2.5">
              <Owed title={t("deal.documents")} items={owed.documents} />
            </div>
          </section>

          <section className="min-w-0">
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

          {others.length ? (
            <section className="min-w-0">
              <DealHeading>{t("deal.moreActions")}</DealHeading>
              <div className="-ml-2 flex flex-wrap gap-1">
                {others.map((a) => (
                  <Link key={a.key} href={a.href} className={textLinkClass}>
                    {a.label}
                  </Link>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      </Disclosure>
    </div>
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
