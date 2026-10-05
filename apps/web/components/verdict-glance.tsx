"use client";

import type { ReactNode } from "react";
import { CheckIcon, XIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";
import type { VerdictView } from "@/lib/types";

/**
 * The decision in three columns, each a few short lines: what the buyer asked for, why we can or cannot say yes,
 * and what we would offer back. Every figure is a server display string; the detail sits further down the page.
 */
export function VerdictGlance({ verdict }: { verdict: VerdictView }) {
  const { t, te } = useI18n();
  const asks = verdict.bound_obligations ?? [];
  const accept = verdict.outcome === "ACCEPT";
  const cures = verdict.violations.filter((v) => v.curable && v.cure_cost_display);

  return (
    <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-3" data-testid="verdict-glance">
      <Column title={t("glance.asked")}>
        {asks.length ? (
          asks.map((o) => (
            <li key={o.id} className="text-sm">
              <span className="font-medium text-ink">{te("obligation", o.type)}</span>
              {o.spans[0] ? <span className="block text-ink-2">&ldquo;{o.spans[0].text}&rdquo;</span> : null}
            </li>
          ))
        ) : (
          <li className="text-sm text-ink-2">{t("glance.asked.none")}</li>
        )}
      </Column>

      <Column title={verdict.violations.length ? t("glance.why.no") : t("glance.why.yes")}>
        {verdict.violations.length
          ? verdict.violations.map((v) => (
              <li key={`${v.code}-${v.day ?? v.month ?? ""}`} className="flex gap-1.5 text-sm" data-testid={`glance-${v.code}`}>
                <span className="mt-0.5 shrink-0 text-bad-fg">
                  <XIcon width={14} height={14} />
                </span>
                <span>
                  <span className="font-medium text-ink">{te("violation", v.code)}</span>
                  {v.observed && v.limit ? (
                    <span className="block text-ink-2">{v.day !== null
                        ? t("glance.vsDay", { observed: v.observed, limit: v.limit, day: v.day })
                        : t("glance.vs", { observed: v.observed, limit: v.limit })}</span>
                  ) : null}
                </span>
              </li>
            ))
          : verdict.passed_checks.map((c) => (
              <li key={c.code} className="flex gap-1.5 text-sm">
                <span className="mt-0.5 shrink-0 text-ok-fg">
                  <CheckIcon width={14} height={14} />
                </span>
                <span className="text-ink">{c.label}</span>
              </li>
            ))}
      </Column>

      <Column title={accept ? t("glance.next.accept") : t("glance.offer")}>
        {accept ? (
          <li className="text-sm text-ink-2">{t("glance.next.acceptBody")}</li>
        ) : verdict.counters.length ? (
          verdict.counters.map((c) => (
            <li key={c.id} className="text-sm">
              <span className="font-medium text-ink">
                {c.label} · {t("glance.costsUs", { cost: c.supplier_cost_display })}
              </span>
              <span className="block text-ink-2">{c.text}</span>
            </li>
          ))
        ) : (
          <li className="text-sm text-ink-2">{t("glance.offer.none")}</li>
        )}
      </Column>

      {verdict.concession_values.length || cures.length ? (
        <p className="text-xs text-ink-2 md:col-span-3" data-testid="glance-footnote">
          {verdict.concession_values.length ? t("glance.givesBuyer", { total: verdict.forward_concession_total_display }) : null}
          {verdict.concession_values.length && cures.length ? " " : null}
          {cures.map((v) => t("glance.cure", { rule: te("violation", v.code), cost: v.cure_cost_display ?? "" })).join(" ")}
        </p>
      ) : null}
    </div>
  );
}

function Column({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{title}</h3>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}
