"use client";

import Link from "next/link";
import { Disclosure } from "@/components/business/kit";
import { StageTrack } from "@/components/deals/stage-track";
import { DealHeading } from "@/components/documents";
import { Callout, Chip, StatePill, textLinkClass, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { DealTone, DealView } from "@/lib/types";
import { whenText } from "@/lib/when";

/** Agreed by both parties: a confirmed contract and the "Terms negotiated" stage done (the server's accepted commitment). */
export function isAgreed(d: DealView): boolean {
  return d.has_contract && Boolean(d.stages?.some((s) => s.key === "negotiated" && s.state === "done"));
}

/** The server names a tone from its own five (`mute` for a quiet one); the app's pills and callouts call that `neutral`. */
const toneOf = (tone: DealTone): Tone => (tone === "mute" ? "neutral" : tone);

/** A mark that goes with each check's tone, so a check is never colour alone. */
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

/** Where a clause link lands: the confirmed contract on the documents page, that term lit up and scrolled into view. */
function clauseHref(docId: string, focus: { span?: { start: number; end: number } | null; clause?: string | null }): string {
  const q = new URLSearchParams({ id: docId });
  if (focus.span) q.set("at", `${focus.span.start}-${focus.span.end}`);
  if (focus.clause) q.set("clause", focus.clause);
  return `/documents?${q.toString()}`;
}

/** "§4.2 ↗": the clause as a link into the contract (its words are the tooltip and open in the document, not here). */
function ClauseLink({ docId, clause, span, quote }: { docId: string | null; clause: string | null; span?: { start: number; end: number } | null; quote?: string }) {
  const { t } = useI18n();
  const label = clause ? (/^\d/.test(clause) ? t("deal.clause", { n: clause }) : clause) : t("deal.seeClause");
  if (!docId) return clause ? <span className="font-mono text-xs text-ink-3">{label}</span> : null;
  return (
    <Link
      href={clauseHref(docId, { span, clause })}
      title={quote ? `“${quote}”` : undefined}
      aria-label={t("deal.openClause", { clause: label })}
      className="motion-press hit inline-flex min-h-8 shrink-0 items-center gap-0.5 whitespace-nowrap rounded-pill bg-sec-deals-bg px-2 font-mono text-xs font-semibold text-sec-deals-fg hover:underline"
    >
      {label}
      <span aria-hidden>↗</span>
    </Link>
  );
}

/**
 * The summary of one agreed deal (brief 03), inside the buyer's agreement on Deals: a headline (where it stands, in the server's pills), two to
 * four facts, and the one thing to do; the stages, the contract's terms, what changed, what is in force, the invoices, what you owe and the
 * checks are behind one fold, in the order the owner asks: where the deal is, what we signed (each term with its clause as a link into the document), what
 * changed (each difference as Contract then Now, who did what), the money, what we owe them and the check. The page passes GET /deals; every amount, date and sentence is a server string, and a day is said as a distance
 * from `today` where the server sent no `*_when` of its own.
 */
export function DealSummary({ deal, today }: { deal: DealView; today: number }) {
  const { t, te } = useI18n();
  const c = deal.contract;
  const docId = c?.record_id ?? null;
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
  const inForce = deal.in_force ?? [];
  const changed = inForce.filter((r) => r.vs_contract === "DIFFERENT" || r.vs_contract === "NOT_IN_CONTRACT" || r.vs_contract === "NOT_COMPARABLE");
  const same = inForce.filter((r) => r.vs_contract === "SAME" || r.vs_contract === "NONE");
  const checks = deal.checks ?? [];
  const flagged = checks.filter((ch) => ch.status === "warn").length;

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
            {docId ? (
              <>
                {" · "}
                <Link href={`/documents?id=${encodeURIComponent(docId)}`} className={textLinkClass} data-testid="deal-contract-link">
                  {t("deals.summary.contract")}
                </Link>
              </>
            ) : null}
            {c?.replaces_text ? <span className="block text-xs font-normal text-ink-3" data-testid="deal-replaces">{c.replaces_text}</span> : null}
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
          <StageTrack stages={stages} />

          {/* What the contract says: each term's value, and its clause as a link into the document. */}
          <section className="min-w-0" data-testid="deal-contract">
            <DealHeading>
              {t("deal.contract")} <Chip tone="ok">{t("docs.confirmedLabel")}</Chip>
            </DealHeading>
            <dl className="divide-y divide-line">
              {deal.contract_terms?.map((term, i) => (
                <div key={`${term.field}-${i}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-1.5 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto]">
                  <dt className="col-span-2 text-sm text-ink-3 sm:col-span-1">{te("contractfield", term.field) || term.label}</dt>
                  <dd className="min-w-0 font-medium text-ink">{term.value_display}</dd>
                  <dd>
                    <ClauseLink docId={docId} clause={term.clause} span={term.span} quote={term.quote} />
                  </dd>
                </div>
              ))}
            </dl>
            {blanks.length ? (
              <p className="mt-2 text-xs text-ink-3" data-testid="deal-blanks">
                {t("deal.notInContractList", { list: blanks.map((b) => te("contractfield", b.field) || b.label).join(", ") })}
                <span className="mt-1 block border-l-2 border-line-strong pl-2">{t("deal.notFoundHint")}</span>
              </p>
            ) : null}
          </section>

          {/* What changed: each difference as Contract then Now, the unchanged terms in one line, then who did what. */}
          <section className="min-w-0">
            <DealHeading>{t("deal.changes")}</DealHeading>
            <div className="space-y-2" data-testid="deal-in-force">
              {changed.map((r) => (
                <div key={r.key} className={`rounded-tile border px-3 py-2 ${r.vs_contract === "NOT_COMPARABLE" ? "border-line bg-subtle" : "border-warn-line bg-warn-bg/50"}`} data-vs={r.vs_contract}>
                  <p className="text-xs font-bold text-ink">{r.label}</p>
                  <div className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2.5 gap-y-0.5 text-sm">
                    {r.vs_contract === "DIFFERENT" && r.contract_display ? (
                      <>
                        <span className="text-ink-3">{t("deal.wasNow.contract")}</span>
                        <span className="text-ink-3 line-through decoration-ink-3/40">{r.contract_display}</span>
                      </>
                    ) : null}
                    <span className={`font-bold ${r.vs_contract === "NOT_COMPARABLE" ? "text-ink-2" : "text-warn-fg"}`}>
                      {r.vs_contract === "DIFFERENT" ? t("deal.wasNow.now") : r.vs_contract === "NOT_IN_CONTRACT" ? t("deal.newTerm") : (r.vs_contract_text ?? t("deal.vs.NOT_COMPARABLE"))}
                    </span>
                    <span className="font-semibold text-ink">{r.value_display}</span>
                  </div>
                  {r.vs_contract_note ? <p className="mt-1 text-xs text-ink-3">{r.vs_contract_note}</p> : null}
                </div>
              ))}
              {same.length ? (
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="mr-0.5 font-semibold text-ink-3">{t("deal.unchanged")}</span>
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
            <ol className="relative grid gap-2.5 before:absolute before:bottom-3 before:left-3.5 before:top-3 before:w-px before:bg-line" data-testid="deal-changes">
              {deal.changes?.map((ch, i) => (
                <li key={i} className="relative grid grid-cols-[1.75rem_minmax(0,1fr)] gap-2.5">
                  <span aria-hidden className={`z-10 grid size-7 place-items-center rounded-full text-xs font-bold ${ACTOR[ch.actor]}`}>
                    {te("deal.actor", ch.actor).slice(0, 1).toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-baseline gap-x-2 text-xs">
                      <span className="font-bold text-ink">{ch.label}</span>
                      <span className="sr-only">{te("deal.actor", ch.actor)}</span>
                      <span className="text-ink-3">{when(ch.when, ch.day)}</span>
                    </p>
                    <p className="break-words text-sm leading-snug text-ink-2">{ch.text}</p>
                  </div>
                </li>
              ))}
            </ol>
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
            <Owed title={t("deal.deliverables")} items={owed.deliverables} docId={docId} />
            <div className="mt-2.5">
              <Owed title={t("deal.documents")} items={owed.documents} docId={docId} />
            </div>
          </section>

          {/* The check in one line, then the list: the fold already hides it, so no second fold inside it. */}
          <section className="min-w-0">
            <DealHeading>{t("deal.checks")}</DealHeading>
            <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              <Tick kind={flagged ? "warn" : "ok"} />
              <span className={flagged ? "text-warn-fg" : "text-ok-fg"}>{flagged ? t("deal.checksSome", { bad: flagged, n: checks.length }) : t("deal.checksAll", { n: checks.length })}</span>
            </p>
            <ul className="mt-2 grid gap-1.5" data-testid="deal-checks">
              {checks.map((ch, i) => (
                <li key={i} className="flex items-baseline gap-2" data-status={ch.status}>
                  <Tick kind={ch.status} />
                  <span className="min-w-0 text-ink-2">{ch.text}</span>
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
              <span className="min-w-0 text-ink">
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
