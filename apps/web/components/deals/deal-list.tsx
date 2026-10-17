"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRightIcon } from "@/components/icons";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { dealRecordId } from "@/lib/decision";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";
import type { DealView, DecisionSummary, NegotiationView, OfferView, StateTone, VerdictView } from "@/lib/types";
import { whenText } from "@/lib/when";

/** Which filter a deal falls under. */
export type DealGroup = "needs" | "waiting" | "agreed" | "closed" | "other";

/** One deal on the list: one buyer, where it stands and where opening it leads. Every word is the server's, the inbox's or the dictionary's. */
export interface DealListRow {
  key: string;
  buyerId: string;
  name: string;
  /** Where the latest word came from and when ("WeChat · today, 11:30"). */
  meta: string | null;
  line: string;
  /** The line is the buyer's own words, in quotes. */
  quoted: boolean;
  pill: { text: string; tone: StateTone };
  /** A figure the deal carries (what it would cost, what it is worth), with its tone. */
  figure: { text: string; tone: StateTone } | null;
  group: DealGroup;
  href: string;
}

/** Home's pill fills (StatusPill): amber for what needs the owner, lavender for what waits on someone else, green for what is agreed; the one risk red for what was set aside. */
const PILL: Record<StateTone, string> = {
  ok: "bg-f-green text-f-green-ink",
  warn: "bg-f-amber text-f-amber-ink",
  bad: "bg-bad-bg text-f-risk",
  info: "bg-f-purple-soft text-f-purple-ink",
  neutral: "bg-subtle text-ink-2",
};
const FIGURE: Record<StateTone, string> = { ok: "text-f-green-ink", warn: "text-f-amber-ink", bad: "text-f-risk", info: "text-f-purple-ink", neutral: "text-ink" };
/** The avatar's tint, by the row's place on the list: decoration only (Home's soft fills), never a status. */
const AVATAR = ["bg-f-purple-soft text-f-purple-ink", "bg-f-green text-f-green-ink", "bg-f-amber text-f-amber-ink", "bg-subtle text-ink"];
/** The groups in the order the owner reads them: what needs them first. */
const ORDER: DealGroup[] = ["needs", "waiting", "agreed", "other", "closed"];

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter((w) => /^[A-Za-z一-鿿]/.test(w))
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("") || name.slice(0, 1);

/**
 * Sorts every buyer into one row: an open offer (the deals read says whether the reply has gone out), else the latest offer's record (agreed,
 * no deal, ...), else a message not yet read, else the contract on file, else nothing set up. Unknown senders are set aside. The page decides
 * nothing: the words are the server's record and read, the inbox's message, or the dictionary's labels for those states.
 */
export function useDealRows({
  deals,
  records,
  offers,
  negotiations,
  verdicts,
  readDocIds,
  known,
  nameOf,
  today,
}: {
  deals: DealView[];
  records: DecisionSummary[];
  offers: OfferView[];
  /** The buyer's answer to a counter the owner sent, by offer: what it said decides the line ("accepted Option A", "turned it down"). */
  negotiations: Record<string, NegotiationView>;
  verdicts: Record<string, VerdictView>;
  readDocIds: string[];
  known: Set<string> | null;
  nameOf: (id: string) => string;
  today: number;
}): DealListRow[] {
  const { t, te } = useI18n();
  const buyers = new Set<string>([...deals.map((d) => d.counterparty_id), ...offers.map((o) => o.offer.counterparty_id), ...INBOX.map((m) => m.counterparty_id)]);
  const metaOf = (m: InboxMessage | undefined) => (m ? `${te("inbox.source", m.source)} · ${t("inbox.at", { when: whenText(m.document.received_day, today, t), time: m.time })}` : null);
  const rows: DealListRow[] = [];
  for (const id of buyers) {
    const deal = deals.find((d) => d.counterparty_id === id) ?? null;
    const name = deal?.counterparty_name ?? INBOX.find((m) => m.counterparty_id === id)?.company ?? nameOf(id);
    const messages = INBOX.filter((m) => m.counterparty_id === id);
    const latestMessage = messages[0];
    const unread = messages.find((m) => !readDocIds.includes(m.document.doc_id));
    const mine = offers.filter((o) => o.offer.counterparty_id === id);
    const latestOffer = mine[mine.length - 1] ?? null;
    const record = latestOffer ? (records.find((r) => r.id === dealRecordId(latestOffer.offer.offer_id)) ?? null) : null;
    const offerMeta = latestOffer ? `${te("channel", latestOffer.documents[0]?.channel ?? "chat")} · ${record?.updated_when ?? whenText(latestOffer.offer.received_day, today, t)}` : null;
    const open = deal?.open_offer ?? null;
    // A deal opens on its customer: every deal with that buyer, the next one to act on outlined; nothing is selected for the owner.
    const base = { key: id, buyerId: id, name, href: `/deals?customer=${encodeURIComponent(id)}` };

    if (known && !known.has(id)) {
      // A sender the books do not know: set aside, never a deal. Its message is on the Security page.
      rows.push({ ...base, meta: metaOf(latestMessage), line: t("deals.list.line.setAside"), quoted: false, pill: { text: t("deals.list.pill.setAside"), tone: "bad" }, figure: null, group: "closed", href: "/trust" });
    } else if (open) {
      const sent = open.stages.some((s) => s.key === "sent" && s.state === "now");
      rows.push(
        sent
          ? { ...base, meta: offerMeta ?? metaOf(latestMessage), line: t("deals.list.line.waiting"), quoted: false, pill: { text: t("deals.list.pill.waiting"), tone: "info" }, figure: null, group: "waiting" }
          : {
              ...base,
              meta: offerMeta ?? metaOf(latestMessage),
              line: open.headline_short ?? open.read_text ?? open.asks_text,
              quoted: false,
              pill: { text: t("deals.list.pill.needs"), tone: "warn" },
              figure: open.cost_display ? { text: [open.cost_display, open.cost_window_text].filter(Boolean).join(" "), tone: open.over_limit ? "bad" : "neutral" } : null,
              group: "needs",
            },
      );
    } else if (record) {
      const tone = record.state_tone ?? "neutral";
      const group: DealGroup = ["AGREED", "FULFILLED", "SETTLED", "EXECUTED", "SETTLEMENT_PENDING", "PARTIALLY_EXECUTED"].includes(record.state)
        ? "agreed"
        : record.terminal
          ? "closed"
          : record.waiting_for?.code === "OWNER_RESPONSE" || record.waiting_for?.code === "OWNER_APPROVAL"
            ? "needs"
            : "other";
      // The buyer's answer, when there was one: the counter it accepted by its label, or that it turned the counter down.
      const neg = latestOffer ? (negotiations[latestOffer.offer.offer_id] ?? null) : null;
      const accepted = neg?.accepted_counter_id ? (verdicts[latestOffer!.offer.offer_id]?.counters.find((c) => c.id === neg.accepted_counter_id)?.label ?? null) : null;
      const line = neg ? (neg.outcome === "DEAL" ? (accepted ? t("deals.list.line.accepted", { option: accepted }) : t("deals.list.line.agreed")) : t("deals.list.line.refused")) : record.headline;
      rows.push({
        ...base,
        meta: offerMeta,
        line,
        quoted: false,
        pill: { text: record.state_text, tone },
        figure: record.amount_display ? { text: record.amount_display, tone: group === "agreed" ? "ok" : "neutral" } : null,
        group,
      });
    } else if (unread) {
      rows.push({ ...base, meta: metaOf(unread), line: unread.document.text, quoted: true, pill: { text: t("deals.list.pill.new"), tone: "info" }, figure: null, group: "needs" });
    } else if (deal?.has_contract) {
      const contract = deal.contract;
      rows.push({
        ...base,
        meta: contract?.confirmed_when ? t("deals.list.meta.confirmed", { when: contract.confirmed_when }) : null,
        line: contract ? t("deals.list.line.terms", { title: contract.title }) : (deal.label ?? t("deals.list.pill.terms")),
        quoted: false,
        pill: { text: t("deals.list.pill.terms"), tone: "ok" },
        figure: deal.next_invoice ? { text: t("deals.list.next", { amount: deal.next_invoice.amount_display, when: deal.next_invoice.when ?? whenText(deal.next_invoice.day, today, t) }), tone: "neutral" } : null,
        group: "agreed",
        href: `/customers/${encodeURIComponent(id)}?from=deals`,
      });
    } else {
      rows.push({ ...base, meta: null, line: t("deals.list.line.setup"), quoted: false, pill: { text: t("deals.list.pill.setup"), tone: "neutral" }, figure: null, group: "other", href: `/customers/${encodeURIComponent(id)}?from=deals` });
    }
  }
  return rows.sort((a, b) => ORDER.indexOf(a.group) - ORDER.indexOf(b.group));
}

type Filter = "all" | "needs" | "waiting" | "agreed" | "closed";

/**
 * The Deals list: every deal the owner has, one card each (who, where the last word came from and when, where it stands, a pill and a figure), with
 * a filter by what it needs. A card opens the deal in full.
 */
export function DealList({ rows }: { rows: DealListRow[] }) {
  const { t, te } = useI18n();
  const [filter, setFilter] = useState<Filter>("all");
  const count = (f: Filter) => (f === "all" ? rows.length : rows.filter((r) => r.group === f).length);
  const shown = filter === "all" ? rows : rows.filter((r) => r.group === filter);
  const filters: Filter[] = ["all", "needs", "waiting", "agreed", "closed"];
  return (
    <section aria-labelledby="deal-list-title" className="space-y-4" data-testid="deal-list">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="deal-list-title" className="sec-title font-display text-2xl font-bold tracking-[-0.01em] text-ink">
            {t("deals.list.title")}
          </h2>
          <p className="text-supporting text-ink-3">{t("deals.list.sub")}</p>
        </div>
        <SegmentedTabs
          compact
          scroll
          label={t("deals.list.filter")}
          value={filter}
          onChange={setFilter}
          testId="deal-list-filter"
          tabs={filters.map((f) => ({ value: f, label: te("deals.list.filter", f), badge: f === "all" ? null : count(f) || null, badgeTone: f === "needs" ? ("alert" as const) : undefined, disabled: f !== "all" && count(f) === 0, testId: `deal-list-filter-${f}` }))}
        />
      </div>
      {shown.length ? (
        <ul className="space-y-3">
          {shown.map((r, i) => (
            <li key={r.key}>
              <ListCard row={r} index={i} label={t("deals.list.open", { name: r.name })} quote={r.quoted ? t("deals.list.quote", { text: r.line }) : null} testId="deal-list-row" />
            </li>
          ))}
        </ul>
      ) : (
        <p className="card-flat text-sm text-ink-3" data-testid="deal-list-empty">
          {rows.length ? t("deals.list.none") : t("deals.list.empty")}
        </p>
      )}
    </section>
  );
}

/** The card's own fields: the deal list's and the receivables list's rows both fit it. */
export type ListCardRow = Pick<DealListRow, "key" | "buyerId" | "name" | "meta" | "line" | "pill" | "figure" | "href"> & { group?: string; figureNote?: string | null };

/**
 * One row of a Business list, as a card in Home's look: an avatar with the initials, the name with where the last word came from and when, one line, the pill and a figure on
 * the right (under the line on a phone), and a chevron. The whole card is the link.
 */
export function ListCard({ row: r, index, label, quote, testId }: { row: ListCardRow; index: number; label: string; quote?: string | null; testId: string }) {
  return (
    <Link
      href={r.href}
      aria-label={label}
      className="motion-press group flex items-center gap-4 rounded-[var(--radius-f-card)] bg-panel p-4 shadow-(--shadow-f) outline outline-2 -outline-offset-2 outline-transparent transition-[box-shadow,outline-color] hover:shadow-(--shadow-lift) hover:outline-brand-600 focus-visible:shadow-(--shadow-lift) focus-visible:outline-brand-600 sm:gap-5 sm:p-5"
      data-testid={testId}
      data-buyer={r.buyerId}
      data-group={r.group}
    >
      <span aria-hidden className={`grid size-12 shrink-0 place-items-center rounded-[14px] font-display text-base font-bold ${AVATAR[index % AVATAR.length]}`}>
        {initials(r.name)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="font-display text-base font-bold text-ink sm:text-lg">{r.name}</span>
          {r.meta ? <span className="text-supporting text-ink-3">{r.meta}</span> : null}
        </span>
        <span className="mt-1 line-clamp-2 block text-sm text-ink-2" data-testid={`${testId}-line`}>
          {quote ?? r.line}
        </span>
        {/* On a phone the pill and the figure sit under the line. */}
        <span className="mt-2 flex flex-wrap items-center gap-2 sm:hidden">
          <Pill pill={r.pill} />
          {r.figure ? <span className={`text-supporting font-bold tabular-nums ${FIGURE[r.figure.tone]}`}>{r.figure.text}</span> : null}
        </span>
      </span>
      <span className="hidden shrink-0 flex-col items-end gap-1.5 sm:flex">
        <Pill pill={r.pill} />
        {r.figure ? (
          <span className={`max-w-[240px] text-right font-display text-base font-bold tabular-nums ${FIGURE[r.figure.tone]}`} data-testid={`${testId}-figure`}>
            {r.figure.text}
          </span>
        ) : null}
        {r.figureNote ? <span className="text-supporting text-ink-3">{r.figureNote}</span> : null}
      </span>
      <ChevronRightIcon aria-hidden width={16} height={16} className="shrink-0 text-ink-3 transition-transform duration-(--dur-fast) group-hover:translate-x-0.5" />
    </Link>
  );
}

/** Home's status pill (StatusPill's shape), with the risk red for what was set aside. */
function Pill({ pill }: { pill: DealListRow["pill"] }) {
  return (
    <span className={`inline-flex min-h-7 items-center whitespace-nowrap rounded-pill px-3 py-0.5 text-supporting font-medium leading-snug ${PILL[pill.tone]}`} data-testid="deal-list-pill" data-tone={pill.tone}>
      <span className="first-letter:uppercase">{pill.text}</span>
    </span>
  );
}
