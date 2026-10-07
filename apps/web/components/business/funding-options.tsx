"use client";

import { PlanNotes } from "@/components/plan-notes";
import { Badge } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n, type I18n } from "@/lib/i18n";
import type { ComparisonRow, ComparisonStatus, MenuRow } from "@/lib/types";
import { whenText } from "@/lib/when";

/**
 * The human name of an option: the router's pick is named by its sources ("Bank credit line + Invoice financing"),
 * the other rows by the dictionary's business names. Never "Router optimum" or "Cheapest committed plan".
 */
export function optionName(c: ComparisonRow, menu: MenuRow[], t: I18n["t"]): string {
  if (c.key === "router_optimum" && c.actions?.length) {
    const names = Array.from(new Set(c.actions.map((a) => menu.find((m) => m.facility.id === a.facility_id)?.facility.name ?? a.facility_id)));
    if (names.length) return names.join(" + ");
  }
  const key = c.key ? (`biz.option.${c.key}` as DictKey) : null;
  return key ? t(key) : c.label;
}

function statusOf(c: ComparisonRow): ComparisonStatus {
  return c.status ?? (c.total_display === "—" ? "unavailable" : c.selected ? "recommended" : "alternative");
}

function Row({ c, n, name, today, recommended }: { c: ComparisonRow; n: number | null; name: string; today: number; recommended: boolean }) {
  const { t } = useI18n();
  const status = statusOf(c);
  return (
    <li className="flex items-start justify-between gap-3 py-2.5" data-testid={`cash-option-${c.selected ? "selected" : "other"}`} data-key={c.key ?? ""} data-status={status}>
      <div className="flex min-w-0 items-start gap-3">
        <span className="mt-0.5 w-6 text-xs font-semibold tabular-nums text-ink-3">{n !== null ? t("biz.option.rank", { n }) : ""}</span>
        <div className="min-w-0">
          <p className={`text-sm ${c.selected ? "font-semibold text-ink" : "text-ink"}`}>{name}</p>
          {status === "insufficient" ? (
            <p className="text-xs text-bad-fg" data-testid="cash-option-uncovered">
              {c.shortfall_display ? t("biz.option.uncovered", { amount: c.shortfall_display, when: whenText(c.breach_day ?? 0, today, t) }) : c.note}
            </p>
          ) : status === "unavailable" ? (
            <p className="text-xs text-ink-3">{c.note}</p>
          ) : recommended ? (
            <p className="text-xs text-ink-3">{t("biz.option.cheapestFull")}</p>
          ) : status === "alternative" ? (
            <p className="text-xs text-ink-3">{t("biz.option.dearer")}</p>
          ) : null}
          {c.reason_kind === "buyer_early_pay" ? (
            <p className="mt-1 text-xs text-ink-3">{t("biz.option.needsBuyer")}</p>
          ) : (
            <PlanNotes className="mt-1" needsApproval={c.needs_owner_approval} approvalReason={c.approval_reason} executableNow={c.executable_now} notExecutableReason={c.not_executable_reason} />
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {recommended ? <Badge tone="brand">{t("biz.option.recommended")}</Badge> : null}
        {status === "insufficient" ? <Badge tone="bad">{t("biz.option.insufficient")}</Badge> : null}
        {status === "unavailable" ? <Badge tone="neutral">{t("biz.option.notPossible")}</Badge> : null}
        <span className="font-semibold tabular-nums">{c.total_display}</span>
      </div>
    </li>
  );
}

/**
 * The router's comparison in two groups that are never ranked together: plans that fully protect cash (the
 * recommended one first, then the dearer alternatives, numbered), and options that do not (insufficient, with what
 * they leave uncovered; not currently available, with why). The rows are the server's; the component only sorts them
 * by the server's status.
 */
export function FundingOptions({ rows, menu, today, recommendedKey }: { rows: ComparisonRow[]; menu: MenuRow[]; today: number; recommendedKey: string | null }) {
  const { t } = useI18n();
  const full = rows.filter((c) => ["recommended", "alternative"].includes(statusOf(c)));
  const rest = rows.filter((c) => !["recommended", "alternative"].includes(statusOf(c)));
  return (
    <div className="space-y-4" data-testid="cash-options-list">
      {full.length ? (
        <div data-testid="cash-options-full">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.cash.options.full")}</h3>
          <ol className="divide-y divide-line">
            {full.map((c, i) => (
              <Row key={c.key ?? c.label} c={c} n={i + 1} name={optionName(c, menu, t)} today={today} recommended={c.selected && recommendedKey === (c.key ?? null)} />
            ))}
          </ol>
        </div>
      ) : null}
      {rest.length ? (
        <div data-testid="cash-options-rest">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.cash.options.rest")}</h3>
          <ul className="divide-y divide-line">
            {rest.map((c) => (
              <Row key={c.key ?? c.label} c={c} n={null} name={optionName(c, menu, t)} today={today} recommended={false} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
