"use client";

import { Disclosure } from "@/components/business/kit";
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
  legs?: { name_display?: string | null; cost_display?: string | null; amount_fen?: number | null }[];
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

/** The row's grid: radio, the plan, [cost cell]. Under the small breakpoint the cost cell drops to a second line so the name keeps the width. */
const rowGrid = "grid min-h-12 grid-cols-[1.5rem_minmax(0,1fr)] items-start gap-x-3 gap-y-2 px-2 py-3 sm:grid-cols-[1.5rem_minmax(0,1fr)_9.5rem]";

/** Whether the row is the recommended plan: the server's `role`, else (an older recording) the selected row when the home's next step came from the router. */
export function isRecommendedRow(c: ComparisonRow, recommendedKey: string | null): boolean {
  const o = c as Option;
  return o.role ? o.role === "recommended" : Boolean(o.selected) && recommendedKey === (o.key ?? null);
}

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

/** A row's identity for the radio group: the router's key, else its label. */
export const rowKey = (c: ComparisonRow): string => c.key ?? c.label;

const ROLE_KEY: Record<ComparisonGroup, DictKey> = {
  RECOMMENDED: "biz.option.recommended",
  ALTERNATIVE: "biz.cash.role.alternative",
  CONDITIONAL_ON_BUYER: "biz.cash.role.buyer",
  INSUFFICIENT: "biz.cash.role.insufficient",
  NOT_AVAILABLE_YET: "biz.cash.role.unavailable",
  BLOCKED: "biz.cash.role.blocked",
};

/**
 * One option as a row of the radio group: the name and its role, the legs, when the money arrives, the cost against the dearest row,
 * and what the plan covers against what it leaves open. Choosing the row draws its cash line on the picture. What decides the row's place
 * (the server's note, what stops it from running) is one tap away under its own fold. The numeral is the server's `rank`, drawn only when
 * there is one. Nothing here sorts, ranks or adds up for display: the bars are sized by `*_fen` (plotting) and every word is the server's.
 */
function Row({ c, name, recommended, chosen, maxTotal, onChoose }: { c: Option; name: string; recommended: boolean; chosen: boolean; maxTotal: number; onChoose: () => void }) {
  const { t } = useI18n();
  const status = roleOf(c);
  const group = groupOf(c);
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
  const hasLine = Boolean(c.series?.length);
  const id = rowKey(c);
  // The bars: plotting only. Cost against the dearest row; covered (the legs' amounts) against uncovered (the gap that remains).
  const costPct = maxTotal > 0 && c.total_fen > 0 ? Math.max((c.total_fen / maxTotal) * 100, 3) : 0;
  const coveredFen = (c.legs ?? []).reduce((sum, l) => sum + (l.amount_fen && l.amount_fen > 0 ? l.amount_fen : 0), 0);
  const gapFen = c.remaining_gap_fen && c.remaining_gap_fen > 0 ? c.remaining_gap_fen : 0;
  return (
    <li data-testid={`cash-option-${c.selected || recommended ? "selected" : "other"}`} data-key={c.key ?? ""} data-status={status} data-group={group} data-chosen={chosen ? "yes" : "no"}>
      <label className={`${rowGrid} cursor-pointer rounded-tile hover:bg-subtle ${chosen ? "bg-brand-50/70" : ""}`}>
        <input type="radio" name="cash-option" value={id} checked={chosen} onChange={onChoose} className="peer sr-only" data-testid={`option-${id}`} />
        <span aria-hidden className="mt-0.5 grid size-5 place-items-center rounded-pill border-2 border-line-ui bg-surface peer-checked:border-brand-600 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus [&>span]:scale-0 peer-checked:[&>span]:scale-100">
          <span className="size-2.5 rounded-pill bg-brand-600 transition-transform" />
        </span>
        <span className="min-w-0 space-y-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {ranked ? <span className="text-xs font-semibold tabular-nums text-ink-3">{t("biz.option.rank", { n: c.rank as number })}</span> : null}
            <span className={`text-sm ${c.selected || recommended ? "font-semibold" : "font-medium"} text-ink`}>{name}</span>
            <Badge tone={recommended ? "brand" : "neutral"} dot={false}>{t(ROLE_KEY[group])}</Badge>
            {chosen && hasLine ? <span className="text-xs font-semibold text-brand-700">{t("biz.cash.opt.onChart")}</span> : null}
          </span>
          {legs || reason ? (
            <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2" data-testid="cash-option-legs">
              {legs ? <span className="tabular-nums">{legs}</span> : null}
              {reason ? <Chip wrap>{reason}</Chip> : null}
            </span>
          ) : null}
          {c.arrival_text ? (
            <span className="block text-sm text-ink" data-testid="cash-option-arrival">
              {c.arrival_text}
            </span>
          ) : null}
          {coveredFen > 0 || gapFen > 0 ? (
            <span className="block">
              <span aria-hidden className="flex h-1.5 max-w-xs gap-[3px]" data-testid="cash-option-coverage" data-covered={coveredFen} data-gap={gapFen}>
                {coveredFen > 0 ? <span className="rounded-[3px] bg-ok-solid" style={{ flex: `${coveredFen} 1 0` }} /> : null}
                {gapFen > 0 ? <span className="rounded-[3px] bg-bad-solid" style={{ flex: `${gapFen} 1 0` }} /> : null}
              </span>
              <span className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-ink-2">
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden className="size-2 rounded-[2px] bg-ok-solid" />
                  {t("biz.cash.opt.covered")}
                </span>
                {gapFen > 0 ? (
                  <span className="inline-flex items-center gap-1.5 font-semibold text-bad-fg">
                    <span aria-hidden className="size-2 rounded-[2px] bg-bad-solid" />
                    {t("biz.cash.opt.uncovered")} {c.uncovered_display ?? c.remaining_gap_display ?? ""}
                  </span>
                ) : null}
              </span>
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
            <span className="block text-sm text-ink" data-testid="cash-option-consent">
              {c.consent_text}
            </span>
          ) : null}
          {c.basis_text ? (
            <span className="block text-xs text-ink-3" data-testid="cash-option-basis">
              {c.basis_text}
            </span>
          ) : null}
          {/* A plan the server could not project has no line: it says why, and the picture stays on the baseline. */}
          {!hasLine ? (
            <span className="block text-xs text-ink-3" data-testid="cash-option-series-note">
              {c.series_note ?? t("biz.cash.opt.noLine")}
            </span>
          ) : null}
        </span>
        <span className="col-span-2 col-start-2 min-w-0 sm:col-span-1 sm:col-start-3 sm:row-start-1">
          <span className="block text-xs font-medium text-ink-3">{t("biz.cash.opt.cost")}</span>
          <span className="block text-base font-bold tabular-nums text-ink" data-testid="cash-option-total">{total}</span>
          <span aria-hidden className="mt-1 block h-1.5 w-full rounded-pill bg-subtle" data-testid="cash-option-cost-bar" data-pct={Math.round(costPct)}>
            <span className="block h-full rounded-pill bg-brand-600" style={{ width: `${costPct}%` }} />
          </span>
        </span>
      </label>
      {hasMore ? (
        <Disclosure testId="cash-option-details" className="pl-9" summary={t("biz.cash.opt.why")}>
          <div className="space-y-1.5 pb-3 text-xs text-ink-2" data-testid="cash-option-why">
            {why ? <p data-testid={status === "unavailable" || status === "blocked" ? "cash-option-unavailable-note" : status === "alternative" ? "cash-option-alternative-note" : undefined}>{why}</p> : null}
            {notes}
          </div>
        </Disclosure>
      ) : null}
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
 * (`orderText`) says how the list is ordered. The rows are a radio group: the chosen one is drawn on the cash picture. The component
 * sorts nothing and ranks nothing itself.
 */
export function FundingOptions({
  rows,
  menu,
  recommendedKey,
  orderText,
  chosenKey,
  onChoose,
}: {
  rows: ComparisonRow[];
  menu: MenuRow[];
  recommendedKey: string | null;
  orderText?: string | null;
  chosenKey: string | null;
  onChoose: (key: string) => void;
}) {
  const { t } = useI18n();
  const options = rows as Option[];
  // The badge follows the server's role; an older recording marks the router's pick only when the home's next step came from it.
  const isRecommended = (c: Option) => isRecommendedRow(c, recommendedKey);
  const fallbackHeading = (g: ComparisonGroup) => (g === "RECOMMENDED" || g === "ALTERNATIVE" ? t("biz.cash.options.full") : t("biz.cash.options.rest"));
  const maxTotal = options.reduce((m, c) => Math.max(m, c.total_fen > 0 ? c.total_fen : 0), 0);
  return (
    <div className="space-y-4" data-testid="cash-options-list" role="radiogroup" aria-label={t("biz.cash.opt.group")}>
      {orderText ? (
        <p className="text-xs text-ink-2" data-testid="cash-options-order">
          {orderText}
        </p>
      ) : null}
      {chunks(options).map((g) => (
        <div key={`${g.group}-${g.rows[0].key ?? g.rows[0].label}`} data-testid={`cash-options-${g.group}`} data-group={g.group}>
          <h3 className="border-b border-line px-2 pb-1.5 text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">{g.heading ?? fallbackHeading(g.group)}</h3>
          <ul className="motion-rise divide-y divide-line">
            {g.rows.map((c) => (
              <Row key={rowKey(c)} c={c} name={optionName(c, menu, t)} recommended={isRecommended(c)} chosen={chosenKey === rowKey(c)} maxTotal={maxTotal} onChoose={() => onChoose(rowKey(c))} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
