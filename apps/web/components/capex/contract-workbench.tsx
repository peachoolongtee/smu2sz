"use client";

import Link from "next/link";
import { type ReactNode, useState } from "react";
import { FoldCard } from "@/components/business/surface";
import { cardTitle } from "@/components/home/v2/home-cards";
import { Button, ErrorState, inputClass, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import { commitContract, evaluateContract } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { BuySideEvaluationView, BuyTimeline, PaymentScheduleView, PurchaseCommitResult, PurchaseRow } from "@/lib/types";

const FIELDS = ["signing_day", "delivery_day", "acceptance_day"] as const;
type Field = (typeof FIELDS)[number];
const FIELD_LABEL: Record<Field, DictKey> = {
  signing_day: "buy.timeline.signing_day",
  delivery_day: "buy.timeline.delivery_day",
  acceptance_day: "buy.timeline.acceptance_day",
};

/** A card of the workbench, in Home's card language: the title, an optional quiet line under it, then the content. */
function Panel({ id, title, sub, pill, children, testId }: { id?: string; title: string; sub?: string; pill?: ReactNode; children: ReactNode; testId?: string }) {
  return (
    <section id={id} className="motion-reveal f-card p-4 sm:p-5" data-testid={testId}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className={cardTitle}>{title}</h3>
          {sub ? <p className="mt-1 text-supporting text-ink-3">{sub}</p> : null}
        </div>
        {pill}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Mini({ label, value, hint, bad }: { label: string; value: string; hint?: string; bad?: boolean }) {
  return (
    <div className="rounded-[14px] bg-subtle px-3 py-2">
      <dt className="text-supporting text-ink-3">{label}</dt>
      <dd className={`font-display text-lg font-bold tabular-nums ${bad ? "text-bad-fg" : "text-ink"}`}>{value}</dd>
      {hint ? <dd className="text-supporting text-ink-3">{hint}</dd> : null}
    </div>
  );
}

/**
 * One capex contract on the owner's timeline (ADR-0013): the timeline, then the server's payment schedule, the vendor's early-payment discount, the financing screen on it and the
 * commitment (POST /capex/contracts/{id}/evaluate and /commit). Shared by Capex and the contract's own page. Every figure and sentence is the server's.
 */
export function ContractWorkbench({ id, row, onCommitted }: { id: string; row: PurchaseRow | undefined; onCommitted?: () => void }) {
  const { t } = useI18n();
  const [days, setDays] = useState<Record<Field, string>>({ signing_day: "20", delivery_day: "60", acceptance_day: "80" });
  const [uplift, setUplift] = useState("22000");
  const [ev, setEv] = useState<BuySideEvaluationView | null>(null);
  const [early, setEarly] = useState(false);
  const [busy, setBusy] = useState<"evaluate" | "commit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [committed, setCommitted] = useState<PurchaseCommitResult | null>(null);

  const timeline = (): BuyTimeline =>
    Object.fromEntries(FIELDS.map((f) => [f, days[f].trim() === "" ? null : Number.parseInt(days[f], 10)])) as BuyTimeline;

  async function evaluate() {
    setBusy("evaluate");
    setError(null);
    setCommitted(null);
    try {
      // The owner types whole yuan a month; the request carries fen (an exact integer: the page parses an entry, it formats no money).
      const yuan = Number.parseInt(uplift, 10);
      const view = await evaluateContract(id, timeline(), Number.isFinite(yuan) ? { monthly_uplift_fen: yuan * 100 } : {});
      setEv(view);
      setEarly(Boolean(view.early_pay?.take));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function commit() {
    if (!ev) return;
    const schedule = early ? ev.early_pay_schedule : ev.schedule.schedule;
    if (!schedule) return;
    setBusy("commit");
    setError(null);
    try {
      setCommitted(await commitContract(id, timeline(), schedule.schedule_hash, early));
      onCommitted?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const evaluation = early ? ev?.early_pay_evaluation : ev?.evaluation;
  const schedule: PaymentScheduleView | null | undefined = early ? ev?.early_pay_schedule : ev?.schedule.schedule;
  const canCommit = Boolean(ev?.reading_confirmed && schedule && row && row.stage === "READY" && !committed);
  const assumptions = [...(schedule?.assumptions ?? []), ...(evaluation?.assumptions ?? [])];

  return (
    <div className="space-y-4" data-testid="contract-workbench">
      {error ? <ErrorState error={error} /> : null}

      <Panel id="timeline" title={t("buy.timeline.title")} sub={t("buy.timeline.sub")}>
        <div className="grid gap-3 sm:grid-cols-4">
          {FIELDS.map((f) => (
            <label key={f} className="grid gap-1 text-supporting text-ink-3">
              {t(FIELD_LABEL[f])}
              <input
                className={inputClass}
                inputMode="numeric"
                value={days[f]}
                onChange={(e) => setDays({ ...days, [f]: e.target.value.replace(/[^0-9]/g, "") })}
                data-testid={`timeline-${f}`}
              />
            </label>
          ))}
          <label className="grid gap-1 text-supporting text-ink-3">
            {t("buy.timeline.uplift")}
            <input className={inputClass} inputMode="numeric" value={uplift} onChange={(e) => setUplift(e.target.value.replace(/[^0-9]/g, ""))} data-testid="timeline-uplift" />
          </label>
        </div>
        <p className="mt-2 text-supporting text-ink-3">{t("buy.timeline.note")}</p>
        <div className="mt-3">
          <Button variant="primary" loading={busy === "evaluate"} onClick={() => void evaluate()} data-testid="buy-evaluate">
            {t("buy.evaluate")}
          </Button>
        </div>
      </Panel>

      {ev ? (
        <>
          <section className={`motion-reveal f-card p-4 sm:p-5 ${evaluation?.selected_id ? "" : "shadow-[inset_3px_0_0_var(--color-warn-fg)]"}`}>
            <p className="text-pretty text-base text-ink" data-testid="buy-summary">{ev.summary}</p>
            {!ev.reading_confirmed ? <p className="mt-1 text-supporting font-medium text-warn-fg">{t("buy.unconfirmed")}</p> : null}
          </section>

          {!ev.schedule.derivable ? (
            <Panel title={t("buy.schedule.none")}>
              <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2" data-testid="buy-reasons">
                {ev.schedule.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </Panel>
          ) : null}

          {schedule ? (
            <Panel id="schedule" title={t("buy.schedule.title")} sub={t("buy.schedule.sub", { total: schedule.price_display })}>
              <TableWrap label={t("buy.schedule.title")}>
                <table className={tableCls} data-testid="buy-schedule">
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("buy.schedule.day")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("buy.schedule.amount")}</th>
                      <th scope="col" className={thCls}>{t("buy.schedule.what")}</th>
                      <th scope="col" className={thCls}>{t("buy.schedule.basis")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schedule.payments.map((x) => (
                      <tr key={x.n}>
                        <td className={`${tdCls} tabular-nums`}>{x.day}</td>
                        <td className={`${tdCls} whitespace-nowrap text-right font-medium tabular-nums`}>{x.amount_display}</td>
                        <td className={tdCls}>
                          {x.label}
                          {x.clause ? <span className="ml-1 text-supporting text-ink-3">§{x.clause}</span> : null}
                        </td>
                        <td className={`${tdCls} text-supporting text-ink-2`}>
                          {x.day_formula}
                          {x.owner_dated ? <StatusPill tone="neutral" className="ml-1">{t("buy.yourDay")}</StatusPill> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
              {evaluation?.beyond_horizon_fen ? (
                <p className="mt-2 text-supporting font-medium text-warn-fg" data-testid="buy-beyond">
                  {t("buy.beyond", { amount: evaluation.beyond_horizon_display ?? "", day: evaluation.horizon_end_day ?? "" })}
                </p>
              ) : null}
            </Panel>
          ) : null}

          {ev.early_pay ? (
            <Panel id="early" title={t("buy.early.title")} pill={ev.early_pay.take ? <StatusPill tone="green">{t("buy.early.worth")}</StatusPill> : null}>
              <p className="text-sm text-ink" data-testid="buy-early">{ev.early_pay.text}</p>
              <p className="mt-1 text-supporting text-ink-3">{ev.early_pay.formula}</p>
              <label className="mt-3 flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-5" checked={early} onChange={(e) => setEarly(e.target.checked)} data-testid="buy-early-take" />
                {t("buy.early.take")}
              </label>
            </Panel>
          ) : null}

          {evaluation ? (
            <Panel id="financing" title={t("buy.financing.title")} sub={t("buy.financing.sub")}>
              <dl className="mb-3 grid grid-cols-2 gap-3 lg:grid-cols-3">
                <Mini label={t("capex.npv")} value={evaluation.npv_display} bad={evaluation.npv_fen < 0} />
                <Mini label={t("capex.payback")} value={evaluation.payback_month !== null ? t("capex.paybackValue", { n: evaluation.payback_month }) : t("common.none")} />
                <Mini
                  label={t("buy.uplift.from")}
                  value={ev.uplift_start_month !== null ? t("capex.paybackValue", { n: ev.uplift_start_month }) : t("common.none")}
                  hint={ev.uplift_start_basis ?? undefined}
                />
              </dl>
              <ul className="space-y-1" data-testid="buy-structures">
                {evaluation.structures.map((s) => {
                  const selected = s.id === evaluation.selected_id;
                  return (
                    <li key={s.id} className={`rounded-[16px] px-3 py-3 ${selected ? "bg-brand-50 shadow-[inset_0_0_0_1px_var(--color-f-purple)]" : ""}`} data-testid={`buy-structure-${s.id}`}>
                      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                        <p className="flex flex-wrap items-center gap-2 font-semibold text-ink">
                          {s.label}
                          {selected ? <StatusPill tone="green">{t("capex.selected")}</StatusPill> : null}
                        </p>
                        <div className="shrink-0 text-right">
                          <p className="font-display text-base font-bold tabular-nums text-ink">{s.monthly_payment_display ?? t("common.none")}</p>
                          <p className="text-supporting tabular-nums text-ink-3">
                            {t("capex.charges")} {s.charges_total_display ?? t("common.none")}
                          </p>
                        </div>
                      </div>
                      <p className="mt-1 text-supporting text-ink-2">{s.note}</p>
                      {s.violations
                        .filter((v) => v.cure_note)
                        .map((v) => (
                          <p key={v.code} className="mt-1 text-supporting font-medium text-warn-fg">{v.cure_note}</p>
                        ))}
                    </li>
                  );
                })}
              </ul>
            </Panel>
          ) : null}

          {schedule ? (
            <Panel id="commit" title={t("buy.commit.title")} pill={<StatusPill tone="amber">{t("buy.commit.tier")}</StatusPill>}>
              <p className="text-sm text-ink-2">{t("buy.commit.body")}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button variant="primary" disabled={!canCommit} loading={busy === "commit"} onClick={() => void commit()} data-testid="buy-commit">
                  {early ? t("buy.commit.early") : t("buy.commit.plain")}
                </Button>
                {row && row.stage !== "READY" ? <span className="text-supporting text-ink-3">{t("buy.commit.notReady")}</span> : null}
              </div>
              {committed ? (
                <p className="mt-2 text-sm text-ink" data-testid="buy-committed">
                  {t("buy.commit.queued", { id: committed.approval_id ?? "" })}{" "}
                  <Link href="/approvals" className="font-medium text-brand-700 underline underline-offset-2">{t("buy.toApprovals")}</Link>
                </p>
              ) : null}
            </Panel>
          ) : null}

          {assumptions.length ? (
            <FoldCard title={t("buy.assumptions")} hint={t("buy.assumptions.hint")}>
              <ul className="list-disc space-y-1.5 pl-5 text-supporting text-ink-2">
                {assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </FoldCard>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
