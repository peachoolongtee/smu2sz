"use client";

import { ChevronRightIcon } from "@/components/icons";
import { PlanNotes } from "@/components/plan-notes";
import { Badge } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n, type I18n } from "@/lib/i18n";
import { statusOf } from "@/lib/presentation-fallbacks";
import type { ComparisonRow, MenuRow } from "@/lib/types";
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

/**
 * One option as a row that opens: the name, its status and its total on one line; what it leaves uncovered stays on the
 * line (it is the fact that decides), and why it ranks where it does (the server's note, the buyer it needs, what stops it
 * from running) is one tap away. A row with nothing more to say is a plain row.
 */
function Row({ c, n, name, today, recommended }: { c: ComparisonRow; n: number | null; name: string; today: number; recommended: boolean }) {
  const { t } = useI18n();
  const status = statusOf(c);
  const needsBuyer = c.reason_kind === "buyer_early_pay";
  const why =
    status === "insufficient" ? null : status === "unavailable" || status === "blocked" ? (c.note_when ?? c.note) : recommended && c.executable_now !== false ? t("biz.option.recommendedWhy") : status === "alternative" ? (c.note_when ?? c.note) : null;
  const notes = needsBuyer ? null : (
    <PlanNotes needsApproval={c.needs_owner_approval} approvalReason={c.approval_reason} executableNow={c.executable_now} notExecutableReason={c.not_executable_reason_when ?? c.not_executable_reason} />
  );
  const hasMore = Boolean(why) || needsBuyer || Boolean(c.needs_owner_approval) || c.executable_now === false;
  const head = (
    <>
      <span className="mt-0.5 w-6 shrink-0 text-xs font-semibold tabular-nums text-ink-3">{n !== null ? t("biz.option.rank", { n }) : ""}</span>
      <span className="min-w-0 flex-1">
        <span className={`block text-sm ${c.selected ? "font-semibold text-ink" : "text-ink"}`}>{name}</span>
        {status === "insufficient" ? (
          <span className="block text-xs text-bad-fg" data-testid="cash-option-uncovered">
            {c.shortfall_display ? t("biz.option.uncovered", { amount: c.shortfall_display, when: whenText(c.breach_day ?? 0, today, t) }) : c.note}
          </span>
        ) : null}
      </span>
      <span className="flex shrink-0 items-center gap-2">
        {recommended ? <Badge tone="brand">{t("biz.option.recommended")}</Badge> : null}
        {status === "insufficient" ? <Badge tone="bad">{t("biz.option.insufficient")}</Badge> : null}
        {status === "unavailable" ? <Badge tone="neutral">{t("biz.option.notPossible")}</Badge> : null}
        {status === "blocked" ? <Badge tone="bad">{t("biz.option.blocked")}</Badge> : null}
        <span className="text-sm font-semibold tabular-nums">{c.total_display}</span>
        {hasMore ? <ChevronRightIcon className="shrink-0 text-ink-3 transition-transform group-open:rotate-90" /> : <span className="w-4 shrink-0" aria-hidden />}
      </span>
    </>
  );
  return (
    <li data-testid={`cash-option-${c.selected ? "selected" : "other"}`} data-key={c.key ?? ""} data-status={status}>
      {hasMore ? (
        <details className="group" data-testid="cash-option-details">
          <summary className="flex min-h-12 cursor-pointer list-none items-start gap-3 py-2.5 [&::-webkit-details-marker]:hidden">{head}</summary>
          <div className="space-y-1.5 pb-3 pl-9 text-xs text-ink-2" data-testid="cash-option-why">
            {why ? <p data-testid={status === "unavailable" || status === "blocked" ? "cash-option-unavailable-note" : status === "alternative" ? "cash-option-alternative-note" : undefined}>{why}</p> : null}
            {needsBuyer ? <p>{t("biz.option.needsBuyer")}</p> : null}
            {notes}
          </div>
        </details>
      ) : (
        <div className="flex min-h-12 items-start gap-3 py-2.5">{head}</div>
      )}
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
  // The recommended plan is #1; the dearer alternatives follow by ascending total (ordering only, no arithmetic).
  const full = rows
    .filter((c) => ["recommended", "alternative"].includes(statusOf(c)))
    .sort((a, b) => Number(statusOf(b) === "recommended") - Number(statusOf(a) === "recommended") || a.total_fen - b.total_fen);
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
