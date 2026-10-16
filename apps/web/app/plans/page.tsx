"use client";

import { useState } from "react";
import { contractsOff } from "@/components/documents";
import { Badge, Button, Callout, Card, EmptyState, ErrorState, inputClass, LoadingBlock, PageHeader } from "@/components/ui";
import { getPurchases, runCapexPlans } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { CapexPlansView, PlanProjectRequest, RankedPlanView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

interface Extra {
  label: string;
  price: string; // whole yuan, as typed
  uplift: string; // whole yuan a month
  optional: boolean;
}

/** Long-term plans (ADR-0013, phase 7): the permutations of purchases, start months and financing, ranked on a monthly estimate. */
export default function PlansPage() {
  const { t, lang } = useI18n();
  const purchases = useAsync(() => getPurchases(lang), [lang]);
  const [include, setInclude] = useState<Record<string, boolean>>({});
  const [extras, setExtras] = useState<Extra[]>(() => [{ label: t("plans.sample.robot"), price: "400000", uplift: "15000", optional: true }]);
  const [result, setResult] = useState<CapexPlansView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (purchases.error && contractsOff(purchases.error)) {
    return (
      <>
        <PageHeader title={t("plans.title")} subtitle={t("plans.subtitle")} />
        <EmptyState title={t("buy.off.title")} body={t("buy.off.body")} />
      </>
    );
  }
  const ready = (purchases.data?.purchases ?? []).filter((p) => p.stage === "READY");

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const projects: PlanProjectRequest[] = [
        ...ready
          .filter((p) => include[p.document_id] !== false)
          .map((p) => ({
            id: p.document_id,
            label: p.title,
            document_id: p.document_id,
            // the demo timeline the contract screen opens with: the owner adjusts it there
            timeline: { signing_day: 20, delivery_day: 60, acceptance_day: 80 },
            monthly_uplift_fen: 2_200_000,
          })),
        ...extras
          .filter((x) => x.price.trim() !== "")
          .map((x, i) => ({
            id: `project-${i + 1}`,
            label: x.label || t("plans.project", { n: i + 1 }),
            // whole yuan typed by the owner; the request carries fen (an exact integer)
            price_fen: Number.parseInt(x.price, 10) * 100,
            monthly_uplift_fen: x.uplift ? Number.parseInt(x.uplift, 10) * 100 : 0,
            uplift_start_month: 4,
            optional: x.optional,
          })),
      ];
      if (!projects.length) throw new Error(t("plans.none"));
      setResult(await runCapexPlans({ projects }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={t("plans.title")} subtitle={t("plans.subtitle")} />
      {error ? <ErrorState error={error} /> : null}
      <Card flat id="projects" title={t("plans.projects")} subtitle={t("plans.projects.sub")}>
        {!purchases.data ? <LoadingBlock rows={2} /> : null}
        <ul className="space-y-2">
          {ready.map((p) => (
            <li key={p.document_id}>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-5" checked={include[p.document_id] !== false}
                  onChange={(e) => setInclude({ ...include, [p.document_id]: e.target.checked })} data-testid={`plan-include-${p.document_id}`} />
                {p.title} · {p.price_display}
              </label>
            </li>
          ))}
        </ul>
        <div className="mt-3 space-y-2">
          {extras.map((x, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-[2fr_1fr_1fr_auto]">
              <input className={inputClass} aria-label={t("plans.extra.label")} value={x.label}
                onChange={(e) => setExtras(extras.map((y, j) => (j === i ? { ...y, label: e.target.value } : y)))} />
              <input className={inputClass} aria-label={t("plans.extra.price")} inputMode="numeric" value={x.price}
                onChange={(e) => setExtras(extras.map((y, j) => (j === i ? { ...y, price: e.target.value.replace(/[^0-9]/g, "") } : y)))} />
              <input className={inputClass} aria-label={t("plans.extra.uplift")} inputMode="numeric" value={x.uplift}
                onChange={(e) => setExtras(extras.map((y, j) => (j === i ? { ...y, uplift: e.target.value.replace(/[^0-9]/g, "") } : y)))} />
              <label className="flex items-center gap-2 text-meta">
                <input type="checkbox" className="size-5" checked={x.optional}
                  onChange={(e) => setExtras(extras.map((y, j) => (j === i ? { ...y, optional: e.target.checked } : y)))} />
                {t("plans.extra.optional")}
              </label>
            </div>
          ))}
          <p className="text-meta text-ink-3">{t("plans.extra.hint")}</p>
          <Button variant="ghost" size="sm" onClick={() => setExtras([...extras, { label: "", price: "", uplift: "", optional: true }])}>
            {t("plans.extra.add")}
          </Button>
        </div>
        <div className="mt-3">
          <Button variant="primary" loading={busy} onClick={() => void run()} data-testid="plans-run">{t("plans.run")}</Button>
        </div>
      </Card>

      {result ? (
        <div className="mt-6 space-y-6" data-testid="plans-result">
          <Callout tone="warn">
            <p>{t("plans.estimate", { n: result.combinations, ok: result.admissible_count })}</p>
          </Callout>
          {result.best.length ? (
            <ol className="space-y-3">
              {result.best.map((p) => (
                <PlanCard key={p.rank ?? 0} p={p} />
              ))}
            </ol>
          ) : (
            <EmptyState title={t("plans.noneAdmissible")} />
          )}
          {result.best_unconstrained ? (
            <Card flat title={t("plans.unconstrained")} subtitle={t("plans.unconstrained.sub")}>
              <p className="text-sm text-ink-2" data-testid="plans-unconstrained">{result.best_unconstrained.text}</p>
            </Card>
          ) : null}
          {result.daily_checks.length ? (
            <Card flat title={t("plans.daily")}>
              <ul className="space-y-1 text-sm text-ink-2" data-testid="plans-daily">
                {result.daily_checks.map((c) => (
                  <li key={c.project_id}>{c.text}</li>
                ))}
              </ul>
            </Card>
          ) : null}
          {result.never_admissible.length ? (
            <p className="text-meta text-ink-3">{t("plans.never", { list: result.never_admissible.join(", ") })}</p>
          ) : null}
          <details className="text-sm">
            <summary className="cursor-pointer text-meta font-medium text-brand-700">{t("buy.assumptions")}</summary>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-meta text-ink-2">
              {result.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </details>
        </div>
      ) : null}
    </>
  );
}

function PlanCard({ p }: { p: RankedPlanView }) {
  const { t } = useI18n();
  return (
    <li className="rounded-card border border-line p-4" data-testid={`plan-${p.rank}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-ink">{t("plans.rank", { n: p.rank ?? 0 })}</p>
        <div className="flex gap-2">
          <Badge tone="ok">{t("plans.npv", { amount: p.npv_display })}</Badge>
          <Badge tone="neutral">{t("plans.lowest", { amount: p.lowest_headroom_display, n: p.lowest_month })}</Badge>
        </div>
      </div>
      <ul className="mt-2 space-y-1 text-sm text-ink-2">
        {p.choices.map((c) => (
          <li key={c.project_id}>
            {c.included
              ? t("plans.choice", {
                  label: c.label,
                  when: c.start_offset_months === 0 ? t("plans.now") : t("plans.later", { n: c.start_offset_months }),
                  how: c.option === "CASH" ? t("plans.cash") : `${c.option_label}${c.monthly_payment_display ? ` (${c.monthly_payment_display})` : ""}`,
                })
              : t("plans.left", { label: c.label })}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-meta text-ink-3">{t("plans.charges", { amount: p.financing_charges_display })}</p>
    </li>
  );
}
