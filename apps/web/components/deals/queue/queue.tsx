"use client";

import type { ReactNode } from "react";
import { dealRecordId } from "@/lib/decision";
import { useI18n } from "@/lib/i18n";
import type { DictKey } from "@/lib/dictionary";
import type { Tone } from "@/components/ui";
import type { DealTone, DealView } from "@/lib/types";
import { contextQuery, queueRows, type QueueRow, type QueueTab, QUEUE_TABS } from "./model";
import { QueueList, QueueTabs, type ListItem } from "./queue-list";

/** The in-force line of a customer's contract in the server's words: payment terms and rebates, each as the read labels them. */
function termsInForce(deal: DealView): string {
  return (deal.in_force ?? [])
    .filter((i) => i.key === "payment_terms" || i.key === "rebate")
    .map((i) => `${i.label}: ${i.value_display}`)
    .join(", ");
}

const STATUS_TONE = { needs: "warn", wait: "info", agreed: "ok", setup: "neutral" } as const;
const toneOf = (tone: DealTone): Tone => (tone === "mute" ? "neutral" : tone);

/**
 * The queue's tiles and list. It files the deals read into four tabs and lays each line out; every word is the read's (the request, its cost and window, FLOW's short verdict, the
 * contract reference and the terms in force, the status) or the dictionary's for a line the server has no word for (a customer still to set up). Nothing is composed from
 * the verdict here: an open deal's recommendation is its `headline_short` whether or not it is the selected one. A line selects with `onSelect`; the selected line is
 * `selectedKey` (an open deal's, or an agreed or setup line the owner opened), and when it is the open deal and its record is read, its status is the record's own word.
 */
export function QueueHead({
  deals,
  tab,
  onTab,
  selectedOfferId,
  selectedKey,
  onSelect,
  pick,
  state,
}: {
  deals: DealView[];
  tab: QueueTab;
  onTab: (t: QueueTab) => void;
  selectedOfferId: string | null;
  /** A line without an open deal that the owner opened (agreed, setup). */
  selectedKey: string | null;
  onSelect: (row: QueueRow) => void;
  /** The picked path's key, carried by every customer link. */
  pick: string | null;
  /** Where the selected open deal stands, in the record's words: shown as its line's status. */
  state: { code: string; text: string; tone: Tone } | null;
}) {
  const { t } = useI18n();
  const rows = queueRows(deals);
  const counts = Object.fromEntries(QUEUE_TABS.map((k) => [k, rows.filter((r) => r.tab === k).length])) as Record<QueueTab, number>;
  const href = (r: QueueRow) => {
    const id = r.deal.counterparty_id;
    const decision = r.offerId ? dealRecordId(r.offerId) : selectedOfferId ? dealRecordId(selectedOfferId) : null;
    return `/customers/${encodeURIComponent(id)}?${contextQuery({ customer: id, decision, path: pick })}`;
  };
  const item = (r: QueueRow): ListItem & { select: () => void } => {
    const open = r.deal.open_offer ?? null;
    const selected = r.offerId ? r.offerId === selectedOfferId : r.key === selectedKey;
    const base = { key: r.key, customer: r.deal.counterparty_name, customerHref: href(r), selected, select: () => onSelect(r), statusTone: STATUS_TONE[r.tab] as Tone, statusState: null as string | null };
    if (r.tab === "needs" || r.tab === "wait") {
      const stage = open?.stages.find((s) => s.state === "now");
      // The status is the record's word on the selected line, else the server's own for the line (the pill's words, or the stage the deal is at).
      const word = selected && state ? state.text : r.tab === "needs" ? (r.deal.needs_you_text ?? open?.action_text ?? "") : (stage?.label ?? "");
      return {
        ...base,
        request: open?.asks_text ?? "",
        cost: open?.cost_display ? `${open.cost_display}${open.cost_window_text ? ` ${open.cost_window_text}` : ""}` : "",
        costTone: open?.over_limit ? "bad" : "neutral",
        recommends: open?.headline_short ?? open?.read_text ?? open?.action_text ?? "",
        status: word,
        statusTone: selected && state ? state.tone : base.statusTone,
        statusState: selected && state ? state.code : null,
      };
    }
    if (r.tab === "agreed") {
      const ref = r.deal.contract?.reference;
      const terms = termsInForce(r.deal);
      const text = [terms ? t("dq.agreed.request", { terms }) : (r.deal.contract?.title ?? ""), ref ? t("dq.agreed.ref", { ref }) : ""].filter(Boolean).join(" · ");
      const pill = r.deal.pills?.[0];
      return { ...base, request: text, cost: "", costTone: "neutral", recommends: r.deal.open_offer ? t("dq.rec.nothingChange") : t("dq.rec.nothing"), status: pill?.label ?? r.deal.label ?? "", statusTone: pill ? toneOf(pill.tone) : base.statusTone };
    }
    return { ...base, request: t("dq.setup.request"), cost: "", costTone: "neutral", recommends: t("dq.rec.setup"), status: t("dq.status.setup") };
  };
  const shown = rows.filter((r) => r.tab === tab).map(item);
  return (
    <>
      <QueueTabs counts={counts} tab={tab} onTab={onTab} />
      <QueueList tab={tab} items={shown} emptyText={t(`dq.empty.${tab}` as DictKey)} />
    </>
  );
}

/**
 * The detail and its aside side by side from `lg` (the detail first); below it the aside follows the detail. A selection replaces the detail at one quick fade (`motion-select`,
 * `--dur`; what is inside does not reveal again). The polite announcement sits outside the keyed section, so a new selection changes its text and is said once.
 */
export function QueueBody({ detail, aside, offerKey, announce }: { detail: ReactNode; aside: ReactNode; offerKey: string; announce: string }) {
  return (
    <>
      <p role="status" aria-live="polite" className="sr-only" data-testid="queue-announce">
        {announce}
      </p>
      <section key={offerKey} className={`motion-select grid gap-x-7 gap-y-6 card-standard max-sm:rounded-none max-sm:border-0 max-sm:bg-transparent max-sm:p-0 sm:p-6 short:p-4 ${aside ? "lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]" : ""}`} data-testid="queue-body">
        {detail}
        {aside}
      </section>
    </>
  );
}
