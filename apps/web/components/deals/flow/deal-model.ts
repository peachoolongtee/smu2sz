import type { PillTone } from "@/components/ui/status-pill";
import type { DealsCounts, OfferPictureView, PathTerm, PicturePath, QueueRowView } from "@/lib/types";
import { pillTone, statusCells, taskRows, type Queue, type Tier } from "./queue-model";

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
  // Round three (section 11): the Agreed tab holds the agreements in force and, after them, the closed ones; the server counts them apart (`agreements`, `closed`) and the tab says both together.
  const n = {
    needs_you: served?.needs_you ?? held.needs_you,
    waiting: served?.waiting ?? held.waiting,
    agreements: served ? (served.agreements ?? held.agreements) + (served.closed ?? 0) : held.agreements,
  };
  return { all: served?.all ?? served?.total ?? n.needs_you + n.waiting + n.agreements, ...n };
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

// ---------------------------------------------------------------- the timing diagram

export interface TimingBar {
  key: "current" | "asked" | "reply";
  /** The term in days: the bar's length only; the words beside it are the server's. */
  days: number;
  /** The server's words for the term ("45 days"); null leaves the bar unlabelled. */
  text: string | null;
}
export interface Timing {
  bars: TimingBar[];
  max: number;
  /** The server's words for the difference the buyer asks ("+15 days requested by buyer"). */
  deltaText: string | null;
}

const paymentTermsText = (p: PicturePath | null | undefined): string | null => p?.terms?.find((t) => t.key === "payment_terms" || t.key === "payment_period")?.value_text ?? null;

/**
 * Current terms, the buyer's request and FLOW's counter as bars from day 0 on one scale: the server's `terms_days` numbers, their words the server's. A path with no payment term in days has no bar,
 * and fewer than two bars is no diagram. Nothing is computed: the largest number sets the scale, and the difference is only said when the server says it.
 */
export function timingOf(picture: Pick<OfferPictureView, "current_terms_days" | "current_terms_text">, asked: PicturePath | null, reply: PicturePath | null): Timing | null {
  const bars: TimingBar[] = [];
  const num = (n: number | null | undefined): n is number => typeof n === "number" && Number.isFinite(n) && n >= 0;
  if (num(picture.current_terms_days)) bars.push({ key: "current", days: picture.current_terms_days, text: picture.current_terms_text ?? null });
  if (asked && num(asked.terms_days)) bars.push({ key: "asked", days: asked.terms_days, text: asked.terms_days_text ?? paymentTermsText(asked) });
  if (reply && reply.key !== asked?.key && num(reply.terms_days)) bars.push({ key: "reply", days: reply.terms_days, text: reply.terms_days_text ?? paymentTermsText(reply) });
  if (bars.length < 2) return null;
  const max = Math.max(...bars.map((b) => b.days));
  if (!(max > 0)) return null;
  return { bars, max, deltaText: asked?.terms_delta_text ?? null };
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

/** The five views of the selected deal. Before agreement: Overview, Compare responses, Cash impact, Messages; from agreement on: Overview, Terms, Messages. */
export type DealViewKey = "overview" | "compare" | "cash" | "terms" | "messages";
export const DEAL_VIEWS: readonly DealViewKey[] = ["overview", "compare", "cash", "terms", "messages"];
/** The views that take the full width: the queue steps aside to its 72 px rail. */
export const WIDE_VIEWS: ReadonlySet<DealViewKey> = new Set<DealViewKey>(["compare", "cash"]);
/** The addresses of round two that opened sections under the page; they all land on Compare responses. */
const LEGACY_KEYS = ["investigate", "compare", "chart", "show"] as const;

/** The view the address names: `view=`, else (an old link with `investigate`, `compare`, `chart` or `show`) Compare responses, else Overview. `legacy` is true when the address still carries a retired key. */
export function viewOf(params: { get(name: string): string | null }): { view: DealViewKey; legacy: boolean } {
  const raw = params.get("view");
  const legacy = LEGACY_KEYS.some((k) => params.get(k) !== null);
  if (raw && (DEAL_VIEWS as readonly string[]).includes(raw)) return { view: raw as DealViewKey, legacy };
  return { view: legacy ? "compare" : "overview", legacy };
}
export const LEGACY_VIEW_KEYS: readonly string[] = LEGACY_KEYS;

/** The tabs a deal has: before agreement the comparison and the cash; from agreement on the terms (the Overview is the tracker). A deal with nothing to draw has neither comparison tab. */
export function tabsOf(opts: { agreed: boolean; analysis: boolean }): DealViewKey[] {
  if (opts.agreed) return ["overview", "terms", "messages"];
  return opts.analysis ? ["overview", "compare", "cash", "messages"] : ["overview", "messages"];
}

/** A view the deal has, else the Overview. */
export const viewIn = (view: DealViewKey, tabs: DealViewKey[]): DealViewKey => (tabs.includes(view) ? view : "overview");

// ---------------------------------------------------------------- the comparison's rows and the outcome plot (round three, sections 1 and 5)

export type CompareRowKey = "terms" | "economic" | "cash" | "authority" | "status";
export const COMPARE_ROWS: readonly CompareRowKey[] = ["terms", "economic", "cash", "authority", "status"];

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
 * The comparison as one model: for each of the five default rows, one cell per path. Every cell is a server word (`economic_headline_text`, `lowest_short`, `reserve_state_text`, `authority_short_text`,
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
      if (key === "cash") return { value: p.lowest_short, sub: p.lowest_when, note: p.reserve_state_text ?? p.band_text, bad: p.first_breach_when !== null };
      if (key === "authority") return { ...empty, value: p.authority_short_text ?? null };
      return { ...empty, value: p.buyer_status_text ?? null };
    }),
  }));
}

export interface PlotDot {
  key: string;
  label: string;
  /** The server's words for the dot (`lowest_short`) and its day (`lowest_when`). */
  short: string;
  when: string | null;
  /** 0 to 100: where the dot sits on the scale, from `lowest_fen` against the scale's ends (positions only; no figure is drawn from it). */
  at: number;
  /** The dot is below the reserve (red); on or above it is ink. */
  below: boolean;
}
export interface Plot {
  dots: PlotDot[];
  /** Where the reserve's dashed line sits, 0 to 100. */
  reserveAt: number;
}

/**
 * The headroom dot plot's geometry (section 5): a horizontal scale from the lowest value to the highest of the responses' lowest cash and the reserve, a vertical line at `floor_fen` and one dot per
 * response at its `lowest_fen`. The browser scales positions only; every label is a server word. A response whose cash cannot be drawn (no `lowest_fen`) has no dot; with none there is no plot.
 */
export function headroomPlot(paths: PicturePath[], floorFen: number): Plot | null {
  const drawn = paths.filter((p): p is PicturePath & { lowest_fen: number } => typeof p.lowest_fen === "number" && Boolean(p.lowest_short));
  if (!drawn.length) return null;
  const values = [...drawn.map((p) => p.lowest_fen), floorFen];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo;
  // Room at each end so a dot on the scale's end is not clipped.
  const at = (v: number) => (span > 0 ? 8 + ((v - lo) / span) * 84 : 50);
  return {
    reserveAt: at(floorFen),
    dots: drawn.map((p) => ({ key: p.key, label: p.label, short: p.lowest_short as string, when: p.lowest_when, at: at(p.lowest_fen), below: p.lowest_fen < floorFen })),
  };
}

// ---------------------------------------------------------------- the chart's lines (round three, section 6)

/** The most responses the chart draws at once. */
export const MAX_LINES = 3;

/**
 * Which responses the chart draws: the address's `lines` (the paths' keys, comma separated, the first chosen first) kept to the paths that exist and to three; else the request and the recommended
 * reply (the first reply when none is recommended).
 */
export function chosenLines(paths: Pick<PicturePath, "key" | "kind" | "recommended">[], raw: string | null): string[] {
  const keys = (raw ?? "").split(",").filter((k, i, a) => k && a.indexOf(k) === i && paths.some((p) => p.key === k)).slice(0, MAX_LINES);
  if (keys.length) return keys;
  const asked = paths.find((p) => p.kind === "asked");
  const reply = paths.find((p) => p.kind === "reply" && p.recommended) ?? paths.find((p) => p.kind === "reply");
  return [asked?.key, reply?.key].filter((k): k is string => Boolean(k));
}


/** A row of the Closed group under the Agreed tab: an agreed deal that is over (its status is the tracker's state word, its consequence the close-out sentence). */
export const isClosedRow = (row: Pick<QueueRowView, "lifecycle">): boolean => lifecycleOf(row) === "closed";
