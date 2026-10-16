"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { contractsOff } from "@/components/documents";
import {
  Badge,
  Button,
  Callout,
  Card,
  EmptyState,
  ErrorState,
  inputClass,
  LoadingBlock,
  PageHeader,
  Stat,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
import { commitContract, evaluateContract, getPurchase } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { BuySideEvaluationView, BuyTimeline, PaymentScheduleView, PurchaseCommitResult } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

export default function Page() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <ContractPage />
    </Suspense>
  );
}

const FIELDS = ["signing_day", "delivery_day", "acceptance_day"] as const;
type Field = (typeof FIELDS)[number];
const FIELD_LABEL: Record<Field, DictKey> = {
  signing_day: "buy.timeline.signing_day",
  delivery_day: "buy.timeline.delivery_day",
  acceptance_day: "buy.timeline.acceptance_day",
};

/** One capex contract on the owner's timeline: its payment schedule, the financing screen on it, the vendor's early-payment discount and the commitment. */
function ContractPage() {
  const { t, lang } = useI18n();
  const id = useSearchParams().get("id") ?? "";
  const row = useAsync(() => getPurchase(id, lang), [id, lang]);
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
      row.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (row.error && contractsOff(row.error)) {
    return <EmptyState title={t("buy.off.title")} body={t("buy.off.body")} />;
  }
  const p = row.data;
  const evaluation = early ? ev?.early_pay_evaluation : ev?.evaluation;
  const schedule: PaymentScheduleView | null | undefined = early ? ev?.early_pay_schedule : ev?.schedule.schedule;
  const canCommit = Boolean(ev?.reading_confirmed && schedule && p && p.stage === "READY" && !committed);

  return (
    <>
      <PageHeader
        title={p?.title ?? t("buy.contract.title")}
        subtitle={p ? `${p.vendor_name}${p.price_display ? ` · ${p.price_display}` : ""}` : t("buy.contract.sub")}
      />
      {row.error ? <ErrorState error={row.error} onRetry={row.reload} /> : null}
      {error ? <ErrorState error={error} /> : null}

      <Card flat id="timeline" title={t("buy.timeline.title")} subtitle={t("buy.timeline.sub")}>
        <div className="grid gap-3 sm:grid-cols-4">
          {FIELDS.map((f) => (
            <label key={f} className="grid gap-1 text-meta text-ink-2">
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
          <label className="grid gap-1 text-meta text-ink-2">
            {t("buy.timeline.uplift")}
            <input className={inputClass} inputMode="numeric" value={uplift} onChange={(e) => setUplift(e.target.value.replace(/[^0-9]/g, ""))} data-testid="timeline-uplift" />
          </label>
        </div>
        <p className="mt-2 text-meta text-ink-3">{t("buy.timeline.note")}</p>
        <div className="mt-3">
          <Button variant="primary" loading={busy === "evaluate"} onClick={() => void evaluate()} data-testid="buy-evaluate">
            {t("buy.evaluate")}
          </Button>
        </div>
      </Card>

      {ev ? (
        <div className="mt-6 space-y-6">
          <Callout tone={evaluation?.selected_id ? "info" : "warn"}>
            <p data-testid="buy-summary">{ev.summary}</p>
            {!ev.reading_confirmed ? <p className="mt-1 text-meta font-medium text-warn-fg">{t("buy.unconfirmed")}</p> : null}
          </Callout>

          {!ev.schedule.derivable ? (
            <Card flat title={t("buy.schedule.none")}>
              <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2" data-testid="buy-reasons">
                {ev.schedule.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </Card>
          ) : null}

          {schedule ? (
            <Card flat id="schedule" title={t("buy.schedule.title")} subtitle={t("buy.schedule.sub", { total: schedule.price_display })}>
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
                          {x.clause ? <span className="ml-1 text-meta text-ink-3">§{x.clause}</span> : null}
                        </td>
                        <td className={`${tdCls} text-meta text-ink-2`}>
                          {x.day_formula}
                          {x.owner_dated ? <Badge tone="neutral" className="ml-1">{t("buy.yourDay")}</Badge> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
              {evaluation?.beyond_horizon_fen ? (
                <p className="mt-2 text-meta font-medium text-warn-fg" data-testid="buy-beyond">
                  {t("buy.beyond", { amount: evaluation.beyond_horizon_display ?? "", day: evaluation.horizon_end_day ?? "" })}
                </p>
              ) : null}
            </Card>
          ) : null}

          {ev.early_pay ? (
            <Card flat id="early" title={t("buy.early.title")} tone={ev.early_pay.take ? "ok" : undefined}>
              <p className="text-sm text-ink" data-testid="buy-early">{ev.early_pay.text}</p>
              <p className="mt-1 text-meta text-ink-3">{ev.early_pay.formula}</p>
              <label className="mt-3 flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-5" checked={early} onChange={(e) => setEarly(e.target.checked)} data-testid="buy-early-take" />
                {t("buy.early.take")}
              </label>
            </Card>
          ) : null}

          {evaluation ? (
            <Card flat id="financing" title={t("buy.financing.title")} subtitle={t("buy.financing.sub")}>
              <dl className="mb-3 grid grid-cols-2 gap-x-6 gap-y-1 lg:grid-cols-3">
                <Stat bare label={t("capex.npv")} value={evaluation.npv_display} tone={evaluation.npv_fen < 0 ? "bad" : "ok"} />
                <Stat bare label={t("capex.payback")} value={evaluation.payback_month !== null ? t("capex.paybackValue", { n: evaluation.payback_month }) : t("common.none")} />
                <Stat bare label={t("buy.uplift.from")} value={ev.uplift_start_month !== null ? t("capex.paybackValue", { n: ev.uplift_start_month }) : t("common.none")} hint={ev.uplift_start_basis ?? undefined} />
              </dl>
              <TableWrap label={t("buy.financing.title")}>
                <table className={tableCls} data-testid="buy-structures">
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("capex.structure")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("capex.monthly")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("capex.charges")}</th>
                      <th scope="col" className={thCls}>{t("capex.result")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evaluation.structures.map((s) => {
                      const selected = s.id === evaluation.selected_id;
                      return (
                        <tr key={s.id} className={selected ? "bg-ok-bg/60" : ""} data-testid={`buy-structure-${s.id}`}>
                          <th scope="row" className={`${tdCls} text-left font-medium`}>
                            {s.label}
                            {selected ? <Badge tone="ok" className="ml-2">{t("capex.selected")}</Badge> : null}
                          </th>
                          <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{s.monthly_payment_display ?? t("common.none")}</td>
                          <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{s.charges_total_display ?? t("common.none")}</td>
                          <td className={`${tdCls} min-w-64 text-meta text-ink-2`}>
                            {s.note}
                            {s.violations
                              .filter((v) => v.cure_note)
                              .map((v) => (
                                <p key={v.code} className="mt-1 font-medium text-warn-fg">{v.cure_note}</p>
                              ))}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TableWrap>
            </Card>
          ) : null}

          {schedule ? (
            <Card id="commit" title={t("buy.commit.title")} tone="warn">
              <p className="text-sm text-ink-2">{t("buy.commit.body")}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button variant="primary" disabled={!canCommit} loading={busy === "commit"} onClick={() => void commit()} data-testid="buy-commit">
                  {early ? t("buy.commit.early") : t("buy.commit.plain")}
                </Button>
                {p && p.stage !== "READY" ? <span className="text-meta text-ink-3">{t("buy.commit.notReady")}</span> : null}
              </div>
              {committed ? (
                <p className="mt-2 text-sm text-ink" data-testid="buy-committed">
                  {t("buy.commit.queued", { id: committed.approval_id ?? "" })}{" "}
                  <Link href="/approvals" className="font-medium text-brand-700 underline underline-offset-2">{t("buy.toApprovals")}</Link>
                </p>
              ) : null}
            </Card>
          ) : null}

          {schedule?.assumptions.length || evaluation?.assumptions?.length ? (
            <details className="text-sm">
              <summary className="cursor-pointer text-meta font-medium text-brand-700">{t("buy.assumptions")}</summary>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-meta text-ink-2">
                {[...(schedule?.assumptions ?? []), ...(evaluation?.assumptions ?? [])].map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
