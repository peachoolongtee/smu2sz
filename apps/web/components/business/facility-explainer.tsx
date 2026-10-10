"use client";

import { Badge, type Tone } from "@/components/ui";
import { FoldChevron } from "@/components/business/kit";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { MenuRow } from "@/lib/types";

type Availability = "ready" | "approval" | "apply" | "unavailable";

const availTone: Record<Availability, Tone> = { ready: "ok", approval: "warn", apply: "info", unavailable: "neutral" };
const availKey: Record<Availability, DictKey> = {
  ready: "biz.facility.ready",
  approval: "biz.facility.approval",
  apply: "biz.facility.apply",
  unavailable: "biz.facility.unavailable",
};

function availability(r: MenuRow): Availability {
  if (r.admissible) return r.needs_owner_approval ? "approval" : "ready";
  return r.facility.status === "NOT_APPLIED" || r.facility.status === "PENDING" ? "apply" : "unavailable";
}

/**
 * Each funding source in plain words (how it works, what it is good for, what to watch), with the router's reading of
 * whether it can be used now. Ported from the `test/ui-ux` borrowing card; the figures are the server's `*_display`.
 */
export function FacilityExplainer({ menu, inPlan }: { menu: MenuRow[]; inPlan: Set<string> }) {
  const { t } = useI18n();
  const order: Availability[] = ["ready", "approval", "apply", "unavailable"];
  const rows = [...menu].sort((a, b) => order.indexOf(availability(a)) - order.indexOf(availability(b)));
  return (
    <ul className="space-y-2" data-testid="facility-explainer">
      {rows.map((r) => {
        const f = r.facility;
        const av = availability(r);
        const hasRate = r.cost_display && r.cost_display !== "—";
        return (
          <li key={f.id}>
            <details className="group rounded-tile border border-line open:border-line-strong" data-testid={`facility-${f.id}`}>
              <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5 hover:bg-subtle [&::-webkit-details-marker]:hidden">
                <span className="min-w-0 flex-1 basis-56">
                  <span className="block text-sm font-medium text-ink">{f.name}</span>
                  <span className="block text-xs text-ink-2">
                    {[hasRate ? t("biz.facility.rate", { rate: r.cost_display }) : null, t("biz.facility.speed", { ttc: r.time_to_cash_display })].filter(Boolean).join(" · ")}
                  </span>
                </span>
                {inPlan.has(f.id) ? <Badge tone="brand">{t("biz.facility.inPlan")}</Badge> : null}
                <Badge tone={availTone[av]}>{t(availKey[av])}</Badge>
                <FoldChevron />
              </summary>
              <div className="space-y-2 border-t border-line px-3 py-3 text-sm">
                <dl className="grid gap-2 sm:grid-cols-3">
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.facility.what")}</dt>
                    <dd className="mt-0.5 text-ink">{t(`biz.kind.${f.kind}.what` as DictKey)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.facility.good")}</dt>
                    <dd className="mt-0.5 text-ink">{t(`biz.kind.${f.kind}.good` as DictKey)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.facility.watch")}</dt>
                    <dd className="mt-0.5 text-ink">{t(`biz.kind.${f.kind}.watch` as DictKey)}</dd>
                  </div>
                </dl>
                <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
                  <span>{t("fund.limit")}: <span className="font-medium tabular-nums text-ink">{f.limit_display}</span></span>
                  <span>{t("biz.drawn")}: <span className="font-medium tabular-nums text-ink">{f.drawn_display}</span></span>
                  {f.collateral ? <span className="font-medium text-warn-fg">{t("biz.facility.collateral")}</span> : null}
                  {f.personal_guarantee ? <span className="font-medium text-warn-fg">{t("biz.facility.guarantee")}</span> : null}
                </p>
                <p className="break-words text-xs text-ink-3">{r.reason}</p>
              </div>
            </details>
          </li>
        );
      })}
    </ul>
  );
}
