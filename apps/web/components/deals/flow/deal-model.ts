import type { PillTone } from "@/components/ui/status-pill";
import type { DealsCounts, HomeSeriesPoint, PathTerm, PicturePath, PictureAxis, QueueRowView } from "@/lib/types";
import { pillTone, rowTarget, statusCells, taskRows, type Queue, type Tier } from "./queue-model";

/**
 * The model of Deals round two (docs/design/flow-mockup-2026-10-13/04_slice_b_round_two.md, sections 1 and 2): which rows the queue lists (negotiations only), the lifecycle pill, the sort and
 * the grouping, the commercial terms table's rows, the timing diagram's bars and the cost table's rows. Pure functions over the server's reads. Nothing here is a word, a figure or a date:
 * it files, orders and aligns what the server wrote, and a field the server did not send leaves its row, bar or cell out.
 */

// ---------------------------------------------------------------- the queue

/** The rows of the Deals queue are negotiations: a decision, the buyer's reply, an agreement. An approval, a collection, a setup task, a settlement and a promise are other pages' (Approvals, Receivables, Agreements). */
export const NEGOTIATION_KINDS: ReadonlySet<string> = new Set(["DECISION", "BUYER_REPLY", "AGREEMENT"]);
export const isNegotiation = (row: Pick<QueueRowView, "kind">): boolean => NEGOTIATION_KINDS.has(row.kind);

export type DealTier = Exclude<Tier, "customers">;
export type DealTab = "all" | DealTier;
export const DEAL_TABS: DealTab[] = ["all", "needs_you", "waiting", "agreements"];
export interface DealRow {
  tier: DealTier;
  row: QueueRowView;
}

/** A tab from the address: the four the page has; anything else (including the retired Customers tab) is null. */
export function dealTabOf(raw: string | null): DealTab | null {
  return raw && (DEAL_TABS as string[]).includes(raw) ? (raw as DealTab) : null;
}

/** The negotiations of the queue, in tier order (what the server filed first stays first); the Agreements tab also holds the promised payments under the agreements, as the server's `queue.deals.agreements` counts them. */
export const negotiationRows = (q: Queue): DealRow[] => taskRows(q).filter((x) => isNegotiation(x.row) || (x.tier === "agreements" && x.row.kind === "PROMISE"));

/** The tab counts: the server's `queue.deals` when it sends them (negotiations only), else the negotiation rows held (a count of lines). */
export function dealTabCounts(q: Queue): Record<DealTab, number> {
  const rows = negotiationRows(q);
  const held = { needs_you: rows.filter((x) => x.tier === "needs_you").length, waiting: rows.filter((x) => x.tier === "waiting").length, agreements: rows.filter((x) => x.tier === "agreements").length };
  const served: DealsCounts | null = q.deals ? ("counts" in q.deals && q.deals.counts ? q.deals.counts : (q.deals as DealsCounts)) : null;
  // Round three (section 11): the Agreed tab counts the deals in force, as the server counts them (`awaiting_payment` + `payment_late`: deals, not rows; a promised payment is a row of its deal);
  // the closed ones are counted apart (`closed`, the Closed group's own count). The browser counts no rows when the server sends these.
  const byGroup = served && (served.awaiting_payment !== undefined || served.payment_late !== undefined);
  const inForce = byGroup ? (served?.awaiting_payment ?? 0) + (served?.payment_late ?? 0) : null;
  const n = {
    needs_you: served?.needs_you ?? held.needs_you,
    waiting: served?.waiting ?? held.waiting,
    agreements: inForce ?? (served ? (served.agreements ?? held.agreements) + (served.closed ?? 0) : held.agreements),
  };
  return { all: served?.all ?? served?.total ?? n.needs_you + n.waiting + n.agreements + (byGroup ? (served?.closed ?? 0) : 0), ...n };
}

// ---------------------------------------------------------------- the lifecycle pill

export type Lifecycle = "counter_ready" | "owner_review" | "awaiting_buyer" | "more_info" | "agreed" | "declined" | "lapsed" | "closed";
const LIFECYCLES: ReadonlySet<string> = new Set<Lifecycle>(["counter_ready", "owner_review", "awaiting_buyer", "more_info", "agreed", "declined", "lapsed", "closed"]);
/** The server's key for "More information needed" is `more_information`. */
const ALIAS: Record<string, Lifecycle> = { more_information: "more_info" };

/** The lifecycle the server names for a negotiation (`lifecycle`, any case, spaces or dashes as underscores); null when it names none (an older server). */
export function lifecycleOf(row: Pick<QueueRowView, "lifecycle">): Lifecycle | null {
  const key = row.lifecycle?.trim().toLowerCase().replace(/[\s-]+/g, "_");
  return key ? (ALIAS[key] ?? (LIFECYCLES.has(key) ? (key as Lifecycle) : null)) : null;
}

/** The pill's tone by lifecycle: amber is the owner's turn (a counter ready, a review, a question), lavender somebody else's (waiting for the buyer), green agreed, neutral closed (declined, lapsed). */
const LIFECYCLE_TONE: Record<Lifecycle, PillTone> = { counter_ready: "amber", owner_review: "amber", more_info: "amber", awaiting_buyer: "lavender", agreed: "green", declined: "neutral", lapsed: "neutral", closed: "neutral" };

/** The record's states as a pill tone, for the selected negotiation when the queue holds no row for it. */
export function recordTone(state: string): PillTone {
  if (state === "AGREED" || state === "FULFILLED") return "green";
  if (state === "RESPONSE_READY" || state === "RECEIVED" || state === "NEEDS_CLARIFICATION" || state === "AUTHORIZATION_REQUIRED") return "amber";
  return "neutral";
}

/**
 * A row's status pill: with a lifecycle the pill is the server's lifecycle word alone (`status_text`) and its tone follows the lifecycle; an older server writes "state . who acts", the pill is the
 * state and the next step the rest, the tone the tier's. Financial risk is never in the pill (it is the severity dot beside the consequence).
 */
export function rowPill(tier: DealTier, row: QueueRowView): { tone: PillTone; text: string; next: string | null; lifecycle: Lifecycle | null } {
  const lifecycle = lifecycleOf(row);
  // An agreed deal whose payment is late carries the tracker's bad tone (it stays in Agreements, never in Needs you).
  if (lifecycle && row.after_group === "payment_late") return { tone: "bad", text: row.status_text, next: null, lifecycle };
  if (lifecycle) return { tone: LIFECYCLE_TONE[lifecycle], text: row.status_text, next: null, lifecycle };
  const { state, next } = statusCells(row);
  const tone = pillTone(tier, row);
  return { tone: tone === "bad" || tone === "warn" ? "amber" : tone === "info" ? "lavender" : "green", text: state, next, lifecycle: null };
}

// ---------------------------------------------------------------- sort and group

export type SortKey = "urgency" | "latest";
const SEVERITY: Record<string, number> = { CRITICAL: 0, CAUTION: 1, NORMAL: 2 };
const TIER: Record<DealTier, number> = { needs_you: 0, waiting: 1, agreements: 2 };

/** Is there a latest-activity day on any row? Without one the sort is not offered (the control shows it disabled). */
export const canSortLatest = (rows: DealRow[]): boolean => rows.some((x) => x.row.last_activity_day !== null && x.row.last_activity_day !== undefined);

/**
 * Urgency (default): who acts first (the owner's, then the buyer's, then agreements), then the server's severity, then the nearer deadline; latest activity: the most recent day first. Stable: rows
 * that tie keep the order the server wrote them in.
 */
export function sortRows(rows: DealRow[], key: SortKey): DealRow[] {
  const ordered = rows.map((x, i) => ({ x, i }));
  ordered.sort((a, b) => {
    if (key === "latest") {
      const d = (b.x.row.last_activity_day ?? -Infinity) - (a.x.row.last_activity_day ?? -Infinity);
      if (d !== 0 && !Number.isNaN(d)) return d;
    } else {
      const t = TIER[a.x.tier] - TIER[b.x.tier];
      if (t !== 0) return t;
      const s = (SEVERITY[a.x.row.severity ?? "NORMAL"] ?? 2) - (SEVERITY[b.x.row.severity ?? "NORMAL"] ?? 2);
      if (s !== 0) return s;
      const d = (a.x.row.deadline_day ?? Infinity) - (b.x.row.deadline_day ?? Infinity);
      if (d !== 0 && !Number.isNaN(d)) return d;
    }
    return a.i - b.i;
  });
  return ordered.map((o) => o.x);
}

export interface DealGroup {
  customerId: string | null;
  name: string;
  rows: DealRow[];
}

/** Rows filed by customer, the groups in the order their first row has in `rows` (so the sort decides which customer leads). A row with no customer is its own group named by its subject. */
export function groupByCustomer(rows: DealRow[], nameOf: (id: string | null, row: QueueRowView) => string): DealGroup[] {
  const groups: DealGroup[] = [];
  for (const x of rows) {
    const id = x.row.customer_id;
    const found = id ? groups.find((g) => g.customerId === id) : undefined;
    if (found) found.rows.push(x);
    else groups.push({ customerId: id, name: nameOf(id, x.row), rows: [x] });
  }
  return groups;
}

/** From this many negotiations the queue offers the table beside the compact rows. */
export const TABLE_FROM = 20;

// ---------------------------------------------------------------- the commercial terms table

export type TermScope = "existing" | "future" | "quarter" | "other";
/** The scope each term the server names belongs to: the existing invoice (early settlement), future invoices (payment terms), next quarter (the rebate). A key the browser does not know is "other" and keeps the server's order. */
const SCOPE_OF: Record<string, TermScope> = {
  early_payment: "existing",
  early_payment_discount: "existing",
  eligible_amount: "existing",
  invoice_amount: "existing",
  invoice_amount_eligible: "existing",
  payment_terms: "future",
  payment_period: "future",
  rebate_or_price: "quarter",
  rebate: "quarter",
};
const SCOPE_ORDER: TermScope[] = ["existing", "future", "quarter", "other"];
/** The server's scope keys (round three) as the scopes the table files by. */
const SCOPE_OF_KEY: Record<string, TermScope> = { existing_invoice: "existing", future_invoices: "future", next_quarter: "quarter" };

export interface TermCell {
  /** The server's value for this path; null when the path says nothing for the term. */
  text: string | null;
  /** The server's "instead of ..." words (a reply only). */
  sub: string | null;
  /** The value changes what holds today (a request) or departs from the request (a reply that says what it is instead of): drawn bold on a lavender tint (never underlined: an underline reads as a link). */
  changed: boolean;
  /** The path does not touch the term. */
  unchanged: boolean;
  /** The term is not in this path's list at all. */
  absent: boolean;
}
export interface TermRow {
  key: string;
  label: string;
  cells: TermCell[];
}
export interface TermGroup {
  scope: TermScope;
  /** The server's word for the scope ("Future invoices"); null from an older server (the dictionary names it). */
  label: string | null;
  rows: TermRow[];
}

function cellOf(term: PathTerm | undefined, kind: PicturePath["kind"]): TermCell {
  if (!term) return { text: null, sub: null, changed: false, unchanged: false, absent: true };
  const text = term.value_text?.trim() ? term.value_text : null;
  const sub = term.instead_of_text?.trim() ? term.instead_of_text : null;
  // The server's `cell_text` is the cell's one word (the value, "Not offered" or "Unchanged"); an untouched row has no value and nothing it stands instead of.
  if (!text && !sub) return { text: term.cell_text?.trim() ? term.cell_text : null, sub: null, changed: false, unchanged: true, absent: false };
  if (term.cell_text?.trim()) return { text: term.cell_text, sub, changed: kind === "asked" ? Boolean(text) : Boolean(sub), unchanged: false, absent: false };
  // The ask's values are what it changes; a reply's are changed where it says what they stand instead of.
  return { text, sub, changed: kind === "asked" ? Boolean(text) : Boolean(sub), unchanged: false, absent: false };
}

/** The terms of the paths side by side, grouped by scope, one row per term the server names (in the first path that has it; the label is the server's). Paths are the table's columns in the order given. */
export function termsGroups(paths: PicturePath[]): TermGroup[] {
  const order: { key: string; label: string; scope: TermScope; scopeLabel: string | null }[] = [];
  for (const p of paths) for (const t of p.terms ?? []) if (!order.some((o) => o.key === t.key)) order.push({ key: t.key, label: t.label, scope: (t.scope ? SCOPE_OF_KEY[t.scope] : undefined) ?? SCOPE_OF[t.key] ?? "other", scopeLabel: t.scope_label ?? null });
  const groups: TermGroup[] = [];
  for (const scope of SCOPE_ORDER) {
    const rows = order
      .filter((o) => o.scope === scope)
      .map((o) => ({ key: o.key, label: o.label, cells: paths.map((p) => cellOf(p.terms?.find((t) => t.key === o.key), p.kind)) }))
      // A term no path says anything for, and none says it leaves alone, is nothing to show.
      .filter((r) => r.cells.some((c) => c.text || c.sub || c.unchanged));
    if (rows.length) groups.push({ scope, label: order.find((o) => o.scope === scope && o.scopeLabel)?.scopeLabel ?? null, rows });
  }
  return groups;
}

// ---------------------------------------------------------------- the cost table

/** A path's cost as one headline and the words that say what it covers: the forward cost with its two-part note when it has both a forward and a one-off part, else its total. */
export function costHeadline(p: PicturePath): { display: string | null; basis: string | null } {
  // The server's own total row, when the path carries its cost as rows: the figure and the basis words it states for that total.
  const total = p.cost_rows?.find((r) => r.key === "total" && r.amount_display);
  if (total) return { display: total.amount_display, basis: total.basis_text || null };
  if (p.cost_forward_display && p.cost_once_display) return { display: p.cost_forward_display, basis: p.cost_note || null };
  return { display: p.cost_total_display ?? p.cost_once_display ?? p.cost_display ?? null, basis: p.cost_basis_text ?? p.cost_note ?? null };
}

export interface CostCell {
  display: string;
  basis: string | null;
  /** The server's word on the figure ("if the plan runs; it cannot run today"). */
  note?: string | null;
}
export interface CostRow {
  key: string;
  label: string;
  cells: (CostCell | null)[];
}

/** The cost components of the paths side by side, one row per component (matched by the server's `key`, else its label), in the order the paths name them. A path without the component has no cell. */
export function costRows(paths: PicturePath[]): CostRow[] {
  const rows: CostRow[] = [];
  paths.forEach((p, i) => {
    // The server's rows (`cost_rows`, the total apart) else its older components; a component with no amount for a path is that path's missing cell.
    const parts = p.cost_rows?.length ? p.cost_rows.filter((r) => r.key !== "total").map((r) => ({ key: r.key, label: r.label, display: r.amount_display, basis_text: r.basis_text, note: r.note })) : (p.cost_components ?? []);
    for (const c of parts) {
      if (!c.display) continue;
      const key = c.key ?? c.label;
      let row = rows.find((r) => r.key === key);
      if (!row) {
        row = { key, label: c.label, cells: paths.map(() => null) };
        rows.push(row);
      }
      row.cells[i] = { display: c.display, basis: c.basis_text ?? null, note: "note" in c ? (c.note ?? null) : null };
    }
  });
  return rows;
}

// ---------------------------------------------------------------- the selected negotiation's pill

/**
 * The pill at the head of the workspace: the queue row's lifecycle word when the server names one for it (the same word as the queue's pill, so the two never disagree), else the record's own state
 * word with a tone from its state.
 */
export function paneStatus(row: QueueRowView | null, stateText: string | null | undefined, stateCode: string): { tone: PillTone; text: string } {
  if (row && lifecycleOf(row) && row.status_text) return { tone: rowPill("needs_you", row).tone, text: row.status_text };
  return { tone: recordTone(stateCode), text: stateText ?? row?.status_text ?? "" };
}

/** A lifecycle key and the server's word for it as a pill (the customer page's negotiations carry both); an unknown or absent key is the owner's turn. */
export function lifecyclePill(lifecycle: string | null | undefined, text: string): { tone: PillTone; text: string; lifecycle: Lifecycle | null } {
  const lc = lifecycleOf({ lifecycle });
  return { tone: lc ? LIFECYCLE_TONE[lc] : "amber", text, lifecycle: lc };
}

// ---------------------------------------------------------------- the selected deal's tabs and address (round three, section 7)

/** The views of the selected deal. Before agreement: Overview (the recommendation and the choices table), Cash impact, Messages; from agreement on: Overview, Terms, Messages. `compare` is retired (the choices table replaces it): an old address that names it lands on the Overview. */
export type DealViewKey = "overview" | "compare" | "cash" | "terms" | "messages";
export const DEAL_VIEWS: readonly DealViewKey[] = ["overview", "compare", "cash", "terms", "messages"];
/** The addresses of round two that opened sections under the page; they all land on the Overview now (the choices table replaced Compare responses). */
const LEGACY_KEYS = ["investigate", "compare", "chart", "show"] as const;

/** The view the address names: `view=`, else else Overview (an old link with `investigate`, `compare`, `chart` or `show` has its key dropped and lands there). `legacy` is true when the address still carries a retired key. */
export function viewOf(params: { get(name: string): string | null }): { view: DealViewKey; legacy: boolean } {
  const raw = params.get("view");
  const legacy = LEGACY_KEYS.some((k) => params.get(k) !== null);
  if (raw && (DEAL_VIEWS as readonly string[]).includes(raw)) return { view: raw as DealViewKey, legacy };
  return { view: "overview", legacy };
}
export const LEGACY_VIEW_KEYS: readonly string[] = LEGACY_KEYS;

/** The sections a deal has: before agreement the cash impact; from agreement on the terms (the Overview is the tracker). A deal with nothing to draw has no cash section. */
export function tabsOf(opts: { agreed: boolean; analysis: boolean }): DealViewKey[] {
  if (opts.agreed) return ["overview", "terms", "messages"];
  return opts.analysis ? ["overview", "cash", "messages"] : ["overview", "messages"];
}

/** A view the deal has, else the Overview. */
export const viewIn = (view: DealViewKey, tabs: DealViewKey[]): DealViewKey => (tabs.includes(view) ? view : "overview");

// ---------------------------------------------------------------- the comparison's rows and the outcome plot (round three, sections 1 and 5)

// One place per fact (round three, review of the preview): the comparison's columns carry the commercial terms, the economic impact and the buyer status; the cash, the reserve, the financing and who may
// send each response are the outcome table's alone.
export type CompareRowKey = "terms" | "economic" | "status";
export const COMPARE_ROWS: readonly CompareRowKey[] = ["terms", "economic", "status"];

export interface CompareCellModel {
  /** The cell's main word and the words under it: each is one server field. */
  value: string | null;
  sub: string | null;
  note: string | null;
  /** The path breaches the reserve (a mark in the cell, never a verdict). */
  bad: boolean;
  /** Commercial terms only: one line per scope, the server's scope word and its `cell_text`. */
  lines?: { scope: string | null; text: string }[];
}

/**
 * The comparison as one model: for each of the three default rows, one cell per path. Every cell is a server word (`economic_headline_text` with its basis,
 * `buyer_status_text`, the terms' `cell_text`); an older server that lacks the short words leaves the cell with what it did send (the cost headline, the band). Nothing is composed or computed.
 */
export function comparisonRows(paths: PicturePath[]): { key: CompareRowKey; cells: CompareCellModel[] }[] {
  const groups = termsGroups(paths);
  return COMPARE_ROWS.map((key) => ({
    key,
    cells: paths.map((p, i): CompareCellModel => {
      const empty: CompareCellModel = { value: null, sub: null, note: null, bad: false };
      if (key === "terms") return { ...empty, lines: groups.flatMap((g) => g.rows.map((r) => ({ scope: g.label, text: r.cells[i]?.text ?? "" })).filter((l) => l.text)) };
      if (key === "economic") {
        const h = costHeadline(p);
        return { ...empty, value: p.economic_headline_text ?? h.display, sub: p.economic_basis_text ?? h.basis };
      }
      return { ...empty, value: p.buyer_status_text ?? null };
    }),
  }));
}

// ---------------------------------------------------------------- the cash impact charts (Deals redesign, board 3)

/** A scale from fen numbers to 0..100 (positions only), with the server's labelled ticks that fall inside it. No label here is the browser's: a tick's words are the axis's own. */
export interface CashScale {
  lo: number;
  hi: number;
  ticks: { at: number; label: string }[];
  at: (fen: number) => number;
}

/**
 * The scale the cash charts share: it spans every value drawn (and zero), widened to the server's axis ticks around it, so the labelled ticks sit on the ends. An axis the server did not send leaves the scale
 * unlabelled (the charts then say each figure in the server's words beside it).
 */
export function cashScale(values: number[], axis: PictureAxis | null | undefined): CashScale {
  const vals = values.filter((v) => Number.isFinite(v));
  const vmin = Math.min(0, ...vals);
  const vmax = Math.max(0, ...vals);
  const ticks = [...(axis?.ticks ?? [])].sort((a, b) => a.value_fen - b.value_fen);
  const lo = Math.max(vmin === 0 ? 0 : -Infinity, ...ticks.filter((t) => t.value_fen <= vmin).map((t) => t.value_fen));
  const lower = Number.isFinite(lo) ? lo : vmin;
  const above = ticks.filter((t) => t.value_fen >= vmax).map((t) => t.value_fen);
  const upper = above.length ? Math.min(...above) : vmax;
  const span = upper - lower;
  const at = (fen: number) => (span > 0 ? Math.min(100, Math.max(0, ((fen - lower) / span) * 100)) : 50);
  return { lo: lower, hi: upper, at, ticks: ticks.filter((t) => t.value_fen >= lower && t.value_fen <= upper).map((t) => ({ at: at(t.value_fen), label: t.label })) };
}

export interface LinePoint {
  /** 0..100 along the window. */
  x: number;
  fen: number;
  day: number;
  /** The server's words for the day ("in 15 days"). */
  when: string | null;
}

/** The days of a series inside the picture's window (`picture_days`; with none, all of them), as positions along it. */
export function lineWindow(series: HomeSeriesPoint[] | null | undefined, today: number, days: number): LinePoint[] {
  const inside = (series ?? []).filter((p) => p.day >= today && (days > 0 ? p.day - today <= days : true));
  const last = inside.length ? inside[inside.length - 1].day - today : 0;
  const span = days > 0 ? days : last;
  return inside.map((p) => ({ x: span > 0 ? ((p.day - today) / span) * 100 : 0, fen: p.closing_fen, day: p.day, when: p.when ?? null }));
}

/** The width a tick's label takes, estimated from its length (13 px text, about 7.5 px a character) and the gap kept between two labels: positions only, the words are the server's. */
export const TICK_CHAR_PX = 7.5;
export const TICK_GAP_PX = 10;

/** Where a tick's label sits along a row `width` px wide: from `left` to `right`, in px, and how it hangs from its day. Centred on the day, unless that would run off the row: then it hangs from the day toward the row's inside. */
export function tickExtent(xPct: number, label: string, width: number): { left: number; right: number; align: "start" | "center" | "end" } {
  const w = label.length * TICK_CHAR_PX;
  const at = (xPct / 100) * width;
  if (at - w / 2 < 0) return { left: at, right: at + w, align: "start" };
  if (at + w / 2 > width) return { left: at - w, right: at, align: "end" };
  return { left: at - w / 2, right: at + w / 2, align: "center" };
}

/**
 * The labelled days along a window of `width` px: the picture's moments inside it, each at its day with the server's own words ("today", "in 47 days"). Left to right, a label is kept only when it
 * clears the one before it by a gap, so the first day always stays and the last stays only when it fits: no two labels overprint. Without a width (not measured yet) none is drawn.
 */
export function dayTicks(moments: { day: number; when?: string | null }[] | null | undefined, today: number, days: number, width: number): { x: number; label: string; align: "start" | "center" | "end" }[] {
  if (!(days > 0) || !(width > 0)) return [];
  const kept: { x: number; label: string; right: number; align: "start" | "center" | "end" }[] = [];
  for (const m of [...(moments ?? [])].sort((a, b) => a.day - b.day)) {
    if (!m.when || m.day < today || m.day - today > days) continue;
    const x = ((m.day - today) / days) * 100;
    const e = tickExtent(x, m.when, width);
    if (kept.length && e.left < kept[kept.length - 1].right + TICK_GAP_PX) continue;
    kept.push({ x, label: m.when, right: e.right, align: e.align });
  }
  return kept.map(({ x, label, align }) => ({ x, label, align }));
}

/** A row of the Closed group under the Agreed tab: an agreed deal that is over (its status is the tracker's state word, its consequence the close-out sentence). */
export const isClosedRow = (row: Pick<QueueRowView, "lifecycle">): boolean => lifecycleOf(row) === "closed";

export type AfterGroup = "payment_late" | "awaiting_payment" | "closed";
/** The Agreements tier's groups in the server's order (payment late, awaiting payment, closed). */
export const AFTER_GROUPS: readonly AfterGroup[] = ["payment_late", "awaiting_payment", "closed"];
/** The Agreements tier's group counts as the server sends them (`queue.deals.awaiting_payment`, `payment_late`, `closed`: deals, not rows); null where it sends none (the rows are counted). */
export function afterGroupCounts(q: Queue): Partial<Record<AfterGroup, number>> | null {
  const served = q.deals ? ("counts" in q.deals && q.deals.counts ? q.deals.counts : (q.deals as DealsCounts)) : null;
  if (!served || (served.awaiting_payment === undefined && served.payment_late === undefined && served.closed === undefined)) return null;
  return { payment_late: served.payment_late ?? 0, awaiting_payment: served.awaiting_payment ?? 0, closed: served.closed ?? 0 };
}

/** The group an agreement row stands in: the server's `after_group`; an older server's closed row is the Closed group; any other row stands in none. */
export function afterGroupOf(row: Pick<QueueRowView, "lifecycle" | "after_group">): AfterGroup | null {
  if (row.after_group && (AFTER_GROUPS as readonly string[]).includes(row.after_group)) return row.after_group;
  return isClosedRow(row) ? "closed" : null;
}

// ---------------------------------------------------------------- walking the queue (the deal page's "Deal i of N" and previous / next)

export interface DealWalk {
  /** The deals the owner can walk, in the list's order, one per record. */
  total: number;
  /** 1-based position of the open deal; null when the open deal is not among them. */
  index: number | null;
  prev: { customer: string | null; decision: string; invoice: string | null } | null;
  next: { customer: string | null; decision: string; invoice: string | null } | null;
}

/**
 * The walk through the list's order: the rows the list shows (the same tab, the same urgency order), one per deal record (a promised payment and its agreement are one deal), each as the
 * address that opens it. Positions only: the browser counts what the list holds, and every word beside the numbers is the dictionary's.
 */
export function dealWalk(rows: DealRow[], decision: string | null): DealWalk {
  const seen = new Set<string>();
  const walk: { customer: string | null; decision: string; invoice: string | null }[] = [];
  for (const { row } of rows) {
    const to = rowTarget(row);
    if (to.kind !== "select" || seen.has(to.decision)) continue;
    seen.add(to.decision);
    walk.push({ customer: to.customer, decision: to.decision, invoice: to.invoice });
  }
  const at = decision ? walk.findIndex((w) => w.decision === decision) : -1;
  return { total: walk.length, index: at >= 0 ? at + 1 : null, prev: at > 0 ? walk[at - 1] : null, next: at >= 0 && at < walk.length - 1 ? walk[at + 1] : null };
}
