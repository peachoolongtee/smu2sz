"use client";

import { Disclosure, FoldChevron } from "@/components/business/kit";
import { PlanNotes } from "@/components/plan-notes";
import { Badge, Chip } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n, type I18n } from "@/lib/i18n";
import { statusOf } from "@/lib/presentation-fallbacks";
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

/**
 * What the server adds to a comparison row (Wave 8): its `role` (recommended, alternative, insufficient, unavailable), the short
 * reason an alternative is not the pick (`role_reason`: "needs 2 approvals") and the plan's legs, each named with its cost
 * (`legs[].name_display`, `cost_display`). Every field is optional: an older recording has none and the row reads as it always did.
 */
type RoleFields = {
  role?: "recommended" | "alternative" | "insufficient" | "unavailable";
  role_reason?: string | null;
  legs?: { name_display?: string | null; cost_display?: string | null }[];
};
type Option = ComparisonRow & RoleFields;

/** The row's status: the server's `role` when it sent one, else `status`, else the router's own result. */
function roleOf(c: Option): ComparisonStatus {
  return c.role ?? statusOf(c);
}

/**
 * The plan's total as the server wrote it, without the sum that leads to it: "¥841.64 + ¥2,272.29 = ¥3,113.93" reads as its last
 * term when the legs are named beside it. Text only; nothing is added up here.
 */
function totalOnly(display: string): string {
  const i = display.lastIndexOf("=");
  return i === -1 ? display : display.slice(i + 1).trim();
}

/** "Credit line ¥841.64 · Invoice financing ¥2,272.29": the named legs, the server's strings. */
function legsLine(c: Option): string | null {
  const legs = (c.legs ?? []).filter((l) => l.name_display && l.cost_display);
  return legs.length > 1 ? legs.map((l) => `${l.name_display} ${l.cost_display}`).join(" · ") : null;
}

/** The row's grid: rank, name, [cost cell], chevron. Under the small breakpoint the cost cell drops to a second line so the name keeps the width. */
const rowGrid = "grid min-h-12 grid-cols-[1.5rem_minmax(0,1fr)_1rem] items-start gap-x-3 gap-y-1 py-2.5 sm:grid-cols-[1.5rem_minmax(0,1fr)_auto_1rem]";

/**
 * One option as a row that opens: the name, its status and its total on one line; what it leaves uncovered stays on the
 * line (it is the fact that decides), and why it ranks where it does (the server's note, the buyer it needs, what stops it
 * from running) is one tap away. A row with nothing more to say is a plain row. The recommended row wears the brand
 * "Recommended" badge; an alternative says in a neutral chip why it is not the pick; named legs sit under the name and the
 * total is the one bold figure.
 */
function Row({ c, n, name, today, recommended }: { c: Option; n: number | null; name: string; today: number; recommended: boolean }) {
  const { t } = useI18n();
  const status = roleOf(c);
  const needsBuyer = c.reason_kind === "buyer_early_pay";
  const why =
    status === "insufficient" ? null : status === "unavailable" || status === "blocked" ? (c.note_when ?? c.note) : recommended && c.executable_now !== false ? t("biz.option.recommendedWhy") : status === "alternative" ? (c.note_when ?? c.note) : null;
  const notes = needsBuyer ? null : (
    <PlanNotes needsApproval={c.needs_owner_approval} approvalReason={c.approval_reason_when ?? c.approval_reason} executableNow={c.executable_now} notExecutableReason={c.not_executable_reason_when ?? c.not_executable_reason} />
  );
  const hasMore = Boolean(why) || needsBuyer || Boolean(c.needs_owner_approval) || c.executable_now === false;
  const legs = legsLine(c);
  const total = legs ? totalOnly(c.total_display) : c.total_display;
  const reason = status === "alternative" && c.role_reason ? c.role_reason : null;
  const head = (
    <>
      <span className="mt-0.5 text-xs font-semibold tabular-nums text-ink-3">{n !== null ? t("biz.option.rank", { n }) : ""}</span>
      <span className="min-w-0">
        <span className={`block text-sm ${c.selected || recommended ? "font-semibold text-ink" : "text-ink"}`}>{name}</span>
        {legs || reason ? (
          <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2" data-testid="cash-option-legs">
            {legs ? <span className="tabular-nums">{legs}</span> : null}
            {reason ? <Chip>{reason}</Chip> : null}
          </span>
        ) : null}
        {status === "insufficient" ? (
          <span className="block text-xs text-bad-fg" data-testid="cash-option-uncovered">
            {c.shortfall_display ? t("biz.option.uncovered", { amount: c.shortfall_display, when: whenText(c.breach_day ?? 0, today, t) }) : c.note}
          </span>
        ) : null}
      </span>
      {/* Narrow: the badges and the cost sit on a second line, right-aligned; wide: beside the name. */}
      <span className="col-span-2 col-start-2 row-start-2 flex flex-wrap items-center justify-end gap-2 sm:col-span-1 sm:col-start-3 sm:row-start-1 sm:flex-nowrap">
        {recommended ? <Badge tone="brand">{t("biz.option.recommended")}</Badge> : null}
        {status === "insufficient" ? <Badge tone="bad">{t("biz.option.insufficient")}</Badge> : null}
        {status === "unavailable" ? <Badge tone="neutral">{t("biz.option.notPossible")}</Badge> : null}
        {status === "blocked" ? <Badge tone="bad">{t("biz.option.blocked")}</Badge> : null}
        <span className="text-sm font-semibold tabular-nums" data-testid="cash-option-total">{total}</span>
      </span>
      {hasMore ? <FoldChevron className="col-start-3 row-start-1 mt-0.5 sm:col-start-4" /> : <span className="col-start-3 row-start-1 w-4 sm:col-start-4" aria-hidden />}
    </>
  );
  return (
    <li data-testid={`cash-option-${c.selected || recommended ? "selected" : "other"}`} data-key={c.key ?? ""} data-status={status}>
      {hasMore ? (
        <Disclosure bare flush testId="cash-option-details" summaryClass={`${rowGrid} cursor-pointer list-none [&::-webkit-details-marker]:hidden`} summary={head}>
          <div className="space-y-1.5 pb-3 pl-9 text-xs text-ink-2" data-testid="cash-option-why">
            {why ? <p data-testid={status === "unavailable" || status === "blocked" ? "cash-option-unavailable-note" : status === "alternative" ? "cash-option-alternative-note" : undefined}>{why}</p> : null}
            {needsBuyer ? <p>{t("biz.option.needsBuyer")}</p> : null}
            {notes}
          </div>
        </Disclosure>
      ) : (
        <div className={rowGrid}>{head}</div>
      )}
    </li>
  );
}

/**
 * The router's comparison in two groups that are never ranked together: plans that fully protect cash (the
 * recommended one first, then the alternatives, numbered in display order) and options that do not (insufficient,
 * with what they leave uncovered; not currently available, with why). The rows are the server's; the component only sorts
 * them by the server's status, and keeps the server's own order among the alternatives when it sent a `role` (the numerals follow the display order).
 */
export function FundingOptions({ rows, menu, today, recommendedKey }: { rows: ComparisonRow[]; menu: MenuRow[]; today: number; recommendedKey: string | null }) {
  const { t } = useI18n();
  const options = rows as Option[];
  const serverRanked = options.some((c) => c.role);
  const isFull = (c: Option) => ["recommended", "alternative"].includes(roleOf(c));
  // Without the server's roles the recommended plan is #1 and the dearer alternatives follow by ascending total (ordering only, no arithmetic).
  const full = options.filter(isFull);
  // With the roles the order is the server's, but the recommended plan always leads its group (a stable sort: the alternatives keep the server's order).
  full.sort((a, b) => Number(roleOf(b) === "recommended") - Number(roleOf(a) === "recommended") || (serverRanked ? 0 : a.total_fen - b.total_fen));
  const rest = options.filter((c) => !isFull(c));
  // The badge follows the server's role; an older recording marks the router's pick only when the home's next step came from it.
  const isRecommended = (c: Option) => (c.role ? c.role === "recommended" : c.selected && recommendedKey === (c.key ?? null));
  return (
    <div className="space-y-4" data-testid="cash-options-list">
      {full.length ? (
        <div data-testid="cash-options-full">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.cash.options.full")}</h3>
          <ol className="motion-rise divide-y divide-line">
            {full.map((c, i) => (
              <Row key={c.key ?? c.label} c={c} n={i + 1} name={optionName(c, menu, t)} today={today} recommended={isRecommended(c)} />
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
