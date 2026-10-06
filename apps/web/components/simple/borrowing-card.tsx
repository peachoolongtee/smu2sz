"use client";

import { SectionLink } from "@/components/home/today-card";
import { Badge, Card, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { planFunding } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { MenuRow } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

type Availability = "ready" | "approval" | "apply" | "unavailable";

const availTone: Record<Availability, Tone> = { ready: "ok", approval: "warn", apply: "info", unavailable: "neutral" };
const availKey: Record<Availability, DictKey> = {
  ready: "simple.borrow.ready",
  approval: "simple.borrow.approval",
  apply: "simple.borrow.apply",
  unavailable: "simple.borrow.unavailable",
};

function availability(r: MenuRow): Availability {
  if (r.admissible) return r.needs_owner_approval ? "approval" : "ready";
  return r.facility.status === "NOT_APPLIED" || r.facility.status === "PENDING" ? "apply" : "unavailable";
}

/**
 * The owner overview's borrowing options: the Debt Desk menu from POST /router/plan (a plan only; nothing is drawn),
 * one line per source and a plain explanation behind each. The full comparison stays on Borrowing options.
 */
export function SimpleBorrowingCard() {
  const { t } = useI18n();
  const res = useAsync(() => planFunding(), []);
  const view = res.data;
  const plan = view?.committed;
  const inPlan = new Set(plan?.actions.map((a) => a.facility_id) ?? []);
  const order: Availability[] = ["ready", "approval", "apply", "unavailable"];
  const rows = view ? [...view.menu].sort((a, b) => order.indexOf(availability(a)) - order.indexOf(availability(b))) : [];

  return (
    <Card id="simple-borrow" title={t("simple.borrow.title")} subtitle={t("simple.borrow.sub")} actions={<SectionLink href="/funding">{t("simple.borrow.more")}</SectionLink>}>
      {res.error ? (
        <ErrorState error={res.error} onRetry={res.reload} />
      ) : !view || !plan ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-3">
          <p
            className={`rounded-lg border px-3.5 py-2.5 text-sm font-medium ${
              plan.actions.length ? "border-warn-line bg-warn-bg text-warn-fg" : "border-ok-line bg-ok-bg text-ok-fg"
            }`}
            data-testid="simple-borrow-headline"
          >
            {plan.actions.length ? t("simple.borrow.need", { need: plan.need_display, cost: plan.total_cost_display }) : t("simple.borrow.noNeed")}
          </p>
          <ul className="space-y-2" data-testid="simple-borrow-list">
            {rows.map((r) => (
              <Option key={r.facility.id} r={r} inPlan={inPlan.has(r.facility.id)} />
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Option({ r, inPlan }: { r: MenuRow; inPlan: boolean }) {
  const { t } = useI18n();
  const f = r.facility;
  const av = availability(r);
  const kind = f.kind;
  const hasRate = r.cost_display && r.cost_display !== "—";

  return (
    <li>
      <details className="group rounded-lg border border-line open:border-line-strong" data-testid={`simple-borrow-${f.id}`}>
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5 hover:bg-subtle [&::-webkit-details-marker]:hidden">
          <span className="min-w-0 flex-1 basis-56">
            <span className="block text-sm font-medium text-ink">{f.name}</span>
            <span className="block text-xs text-ink-2">
              {[hasRate ? t("simple.borrow.rate", { rate: r.cost_display }) : null, t("simple.borrow.speed", { ttc: r.time_to_cash_display })]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </span>
          {inPlan ? <Badge tone="brand">{t("simple.borrow.inPlan")}</Badge> : null}
          <Badge tone={availTone[av]}>{t(availKey[av])}</Badge>
          <span aria-hidden className="text-ink-3 transition-transform group-open:rotate-90">
            ›
          </span>
        </summary>
        <div className="space-y-2 border-t border-line px-3 py-3 text-sm">
          <dl className="grid gap-2 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("simple.borrow.what")}</dt>
              <dd className="mt-0.5 text-ink">{t(`simple.kind.${kind}.what` as DictKey)}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("simple.borrow.good")}</dt>
              <dd className="mt-0.5 text-ink">{t(`simple.kind.${kind}.good` as DictKey)}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("simple.borrow.watch")}</dt>
              <dd className="mt-0.5 text-ink">{t(`simple.kind.${kind}.watch` as DictKey)}</dd>
            </div>
          </dl>
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
            <span>
              {t("simple.borrow.limit")}: <span className="font-medium tabular-nums text-ink">{f.limit_display}</span>
            </span>
            <span>
              {t("simple.borrow.used")}: <span className="font-medium tabular-nums text-ink">{f.drawn_display}</span>
            </span>
            {f.collateral ? <span className="font-medium text-warn-fg">{t("simple.borrow.collateral")}</span> : null}
            {f.personal_guarantee ? <span className="font-medium text-warn-fg">{t("simple.borrow.guarantee")}</span> : null}
          </p>
          <p className="break-words text-xs text-ink-3">
            {t("simple.borrow.note")}: {r.reason}
          </p>
        </div>
      </details>
    </li>
  );
}
