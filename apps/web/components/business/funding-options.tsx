"use client";

import { Disclosure, FoldChevron } from "@/components/business/kit";
import { PlanNotes } from "@/components/plan-notes";
import { Badge, Chip } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n, type I18n } from "@/lib/i18n";
import { statusOf } from "@/lib/presentation-fallbacks";
import type { ComparisonGroup, ComparisonRow, ComparisonStatus, MenuRow } from "@/lib/types";

/**
 * The human name of an option: the router's pick is named by its sources ("Bank credit line + Invoice financing"),
 * the other rows by the dictionary's business names. Never "Router optimum" or "Cheapest committed plan". The recommended row is
 * titled with the server's `name_display` (its sources joined) when it sends one; "Recommended plan" is only the fallback.
 */
export function optionName(c: ComparisonRow, menu: MenuRow[], t: I18n["t"]): string {
  if (c.key === "router_optimum" && c.actions?.length) {
    const names = Array.from(new Set(c.actions.map((a) => menu.find((m) => m.facility.id === a.facility_id)?.facility.name ?? a.facility_id)));
    if (names.length) return names.join(" + ");
  }
  if (c.role === "recommended" && c.name_display) return c.name_display;
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

/** The server's group for a row; a recording without one is grouped by the row's role, as it always was. */
function groupOf(c: Option): ComparisonGroup {
  if (c.group) return c.group;
  const status = roleOf(c);
  if (status === "recommended") return "RECOMMENDED";
  if (status === "alternative") return c.reason_kind === "buyer_early_pay" ? "CONDITIONAL_ON_BUYER" : "ALTERNATIVE";
  if (status === "insufficient") return "INSUFFICIENT";
  if (status === "unavailable") return "NOT_AVAILABLE_YET";
  return "BLOCKED";
}

/**
 * One option as a row that opens: the name and its total on one line; what it costs to get there, when the money arrives, what it leaves
 * uncovered and what the cost assumes stay on the row (they are the facts that decide), and why it is where it is (the server's note, what
 * stops it from running) is one tap away. The numeral is the server's `rank` and is drawn only when there is one: an option that depends on
 * the buyer, leaves a gap or is not available yet is never ranked against the plans that can run now. Nothing here sorts or adds up.
 */
function Row({ c, name, recommended }: { c: Option; name: string; recommended: boolean }) {
  const { t } = useI18n();
  const status = roleOf(c);
  const needsBuyer = c.reason_kind === "buyer_early_pay" || c.group === "CONDITIONAL_ON_BUYER";
  const why =
    status === "insufficient" ? null : status === "unavailable" || status === "blocked" ? (c.note_when ?? c.note) : recommended && c.executable_now !== false ? t("biz.option.recommendedWhy") : status === "alternative" && !needsBuyer ? (c.note_when ?? c.note) : null;
  const notes = needsBuyer ? null : (
    <PlanNotes needsApproval={c.needs_owner_approval} approvalReason={c.approval_reason_when ?? c.approval_reason} executableNow={c.executable_now} notExecutableReason={c.not_executable_reason_when ?? c.not_executable_reason} />
  );
  const hasMore = Boolean(why) || (!needsBuyer && (Boolean(c.needs_owner_approval) || c.executable_now === false));
  const legs = legsLine(c);
  const total = legs ? totalOnly(c.total_display) : c.total_display;
  const reason = status === "alternative" && !needsBuyer && c.role_reason ? c.role_reason : null;
  const ranked = c.rank !== null && c.rank !== undefined;
  const insufficient = status === "insufficient";
  const head = (
    <>
      <span className="mt-0.5 text-xs font-semibold tabular-nums text-ink-3">{ranked ? t("biz.option.rank", { n: c.rank as number }) : ""}</span>
      <span className="min-w-0">
        <span className={`block text-sm ${c.selected || recommended ? "font-semibold text-ink" : "text-ink"}`}>{name}</span>
        {legs || reason ? (
          <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2" data-testid="cash-option-legs">
            {legs ? <span className="tabular-nums">{legs}</span> : null}
            {reason ? <Chip wrap>{reason}</Chip> : null}
          </span>
        ) : null}
        {c.arrival_text ? (
          <span className="mt-0.5 block text-sm text-ink" data-testid="cash-option-arrival">
            {c.arrival_text}
          </span>
        ) : null}
        {/* An insufficient plan says what it leaves uncovered in the server's sentence (and when cash falls short); the others say whether a gap remains. */}
        {insufficient && (c.role_reason || c.remaining_gap_text) ? (
          <span className="block text-sm text-bad-fg" data-testid="cash-option-uncovered">
            {c.role_reason ?? c.remaining_gap_text}
          </span>
        ) : c.remaining_gap_text ? (
          <span className="block text-sm text-ink" data-testid="cash-option-gap">
            {c.remaining_gap_text}
          </span>
        ) : null}
        {c.consent_text ? (
          <span className="mt-0.5 block text-sm text-ink" data-testid="cash-option-consent">
            {c.consent_text}
          </span>
        ) : null}
        {c.basis_text ? (
          <span className="block text-xs text-ink-3" data-testid="cash-option-basis">
            {c.basis_text}
          </span>
        ) : null}
      </span>
      {/* Narrow: the badge and the cost sit on a second line, right-aligned; wide: beside the name. */}
      <span className="col-span-2 col-start-2 row-start-2 flex flex-wrap items-center justify-end gap-2 sm:col-span-1 sm:col-start-3 sm:row-start-1 sm:flex-nowrap">
        {recommended ? <Badge tone="brand">{t("biz.option.recommended")}</Badge> : null}
        <span className="text-sm font-semibold tabular-nums" data-testid="cash-option-total">{total}</span>
      </span>
      {hasMore ? <FoldChevron className="col-start-3 row-start-1 mt-0.5 sm:col-start-4" /> : <span className="col-start-3 row-start-1 w-4 sm:col-start-4" aria-hidden />}
    </>
  );
  return (
    <li data-testid={`cash-option-${c.selected || recommended ? "selected" : "other"}`} data-key={c.key ?? ""} data-status={status} data-group={groupOf(c)}>
      {hasMore ? (
        <Disclosure bare flush testId="cash-option-details" summaryClass={`${rowGrid} cursor-pointer list-none [&::-webkit-details-marker]:hidden`} summary={head}>
          <div className="space-y-1.5 pb-3 pl-9 text-xs text-ink-2" data-testid="cash-option-why">
            {why ? <p data-testid={status === "unavailable" || status === "blocked" ? "cash-option-unavailable-note" : status === "alternative" ? "cash-option-alternative-note" : undefined}>{why}</p> : null}
            {notes}
          </div>
        </Disclosure>
      ) : (
        <div className={rowGrid}>{head}</div>
      )}
    </li>
  );
}

/** The consecutive rows that share a group, in the order the server sent them. */
function chunks(rows: Option[]): { group: ComparisonGroup; heading: string | undefined; rows: Option[] }[] {
  const out: { group: ComparisonGroup; heading: string | undefined; rows: Option[] }[] = [];
  for (const r of rows) {
    const g = groupOf(r);
    const last = out[out.length - 1];
    if (last && last.group === g) last.rows.push(r);
    else out.push({ group: g, heading: r.group_text, rows: [r] });
  }
  return out;
}

/**
 * The router's comparison, grouped the way the server grouped it and in the order it sent: the recommended plan, the other plans that
 * can run now (numbered by the server's `rank`, cheapest first), then the options that depend on the buyer, leave a gap, are not available
 * yet or break a limit, which carry no numeral. Each group's heading is the server's `group_text`, and the one sentence above the groups
 * (`orderText`) says how the list is ordered. The component sorts nothing and ranks nothing itself.
 */
export function FundingOptions({ rows, menu, recommendedKey, orderText }: { rows: ComparisonRow[]; menu: MenuRow[]; recommendedKey: string | null; orderText?: string | null }) {
  const { t } = useI18n();
  const options = rows as Option[];
  // The badge follows the server's role; an older recording marks the router's pick only when the home's next step came from it.
  const isRecommended = (c: Option) => (c.role ? c.role === "recommended" : c.selected && recommendedKey === (c.key ?? null));
  const fallbackHeading = (g: ComparisonGroup) => (g === "RECOMMENDED" || g === "ALTERNATIVE" ? t("biz.cash.options.full") : t("biz.cash.options.rest"));
  return (
    <div className="space-y-4" data-testid="cash-options-list">
      {orderText ? (
        <p className="text-xs text-ink-2" data-testid="cash-options-order">
          {orderText}
        </p>
      ) : null}
      {chunks(options).map((g) => (
        <div key={`${g.group}-${g.rows[0].key ?? g.rows[0].label}`} data-testid={`cash-options-${g.group}`} data-group={g.group}>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{g.heading ?? fallbackHeading(g.group)}</h3>
          <ul className="motion-rise divide-y divide-line">
            {g.rows.map((c) => (
              <Row key={c.key ?? c.label} c={c} name={optionName(c, menu, t)} recommended={isRecommended(c)} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
