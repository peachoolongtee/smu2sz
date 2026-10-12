"use client";

import type { ReactNode } from "react";
import { dealRecordId } from "@/lib/decision";
import { useI18n } from "@/lib/i18n";
import type { DictKey } from "@/lib/dictionary";
import type { DealView, OpenOffer } from "@/lib/types";
import { contextQuery, queueRows, type QueueRow, type QueueTab, QUEUE_TABS } from "./model";
import { QueueList, QueueTabs, type ListItem } from "./queue-list";

/** The in-force line of a customer's contract in the server's words: payment terms and rebates, each as the read labels them. */
function termsInForce(deal: DealView): string {
  return (deal.in_force ?? [])
    .filter((i) => i.key === "payment_terms" || i.key === "rebate")
    .map((i) => `${i.label}: ${i.value_display}`)
    .join(", ");
}

const STATUS = { needs: "warn", wait: "info", agreed: "ok", setup: "neutral" } as const;

/**
 * The queue's header, tiles and list. It files the deals read into four tabs and lays each line out; the words are the read's (the request, its cost and window, the
 * contract reference and the terms in force) or the dictionary's. FLOW's recommendation for the open deal comes from the page, which has the verdict and the paths.
 */
export function QueueHead({
  deals,
  tab,
  onTab,
  selectedOfferId,
  onSelect,
  pick,
  recommendFor,
}: {
  deals: DealView[];
  tab: QueueTab;
  onTab: (t: QueueTab) => void;
  selectedOfferId: string | null;
  onSelect: (offerId: string) => void;
  /** The picked path's key, carried by every customer link. */
  pick: string | null;
  /** FLOW's words for an open request (from the verdict when it is the one on screen), else null. */
  recommendFor: (open: OpenOffer) => string | null;
}) {
  const { t } = useI18n();
  const rows = queueRows(deals);
  const counts = Object.fromEntries(QUEUE_TABS.map((k) => [k, rows.filter((r) => r.tab === k).length])) as Record<QueueTab, number>;
  const href = (r: QueueRow) => {
    const id = r.deal.counterparty_id;
    const decision = r.offerId ? dealRecordId(r.offerId) : selectedOfferId ? dealRecordId(selectedOfferId) : null;
    return `/customers/${encodeURIComponent(id)}?${contextQuery({ customer: id, decision, path: pick })}`;
  };
  const item = (r: QueueRow): ListItem => {
    const open = r.deal.open_offer ?? null;
    const base = { key: r.key, customer: r.deal.counterparty_name, customerHref: href(r), offerId: r.offerId, selected: Boolean(r.offerId && r.offerId === selectedOfferId), statusTone: STATUS[r.tab] };
    if (r.tab === "needs" || r.tab === "wait") {
      return {
        ...base,
        request: open?.asks_text ?? "",
        cost: open?.cost_display ? `${open.cost_display}${open.cost_window_text ? ` ${open.cost_window_text}` : ""}` : "",
        costTone: open?.over_limit ? "bad" : "neutral",
        recommends: (open && recommendFor(open)) ?? t("dq.rec.checking"),
        status: t(`dq.status.${r.tab}` as DictKey),
      };
    }
    if (r.tab === "agreed") {
      const ref = r.deal.contract?.reference;
      const terms = termsInForce(r.deal);
      const text = [terms ? t("dq.agreed.request", { terms }) : (r.deal.contract?.title ?? ""), ref ? t("dq.agreed.ref", { ref }) : ""].filter(Boolean).join(" · ");
      return { ...base, request: text, cost: "", costTone: "neutral", recommends: r.deal.open_offer ? t("dq.rec.nothingChange") : t("dq.rec.nothing"), status: t("dq.status.agreed") };
    }
    return { ...base, request: t("dq.setup.request"), cost: "", costTone: "neutral", recommends: t("dq.rec.setup"), status: t("dq.status.setup") };
  };
  const shown = rows.filter((r) => r.tab === tab).map(item);
  return (
    <>
      <QueueTabs counts={counts} tab={tab} onTab={onTab} />
      <QueueList tab={tab} items={shown} onSelect={onSelect} emptyText={t(`dq.empty.${tab}` as DictKey)} />
    </>
  );
}

/** The detail and its aside side by side from `lg` (the detail first); below it the aside follows the detail. The detail replaces itself in place on a selection. */
export function QueueBody({ detail, aside, offerKey }: { detail: ReactNode; aside: ReactNode; offerKey: string }) {
  return (
    <section key={offerKey} className="motion-reveal grid gap-x-7 gap-y-6 max-sm:p-0 sm:rounded-card sm:border sm:border-line sm:bg-surface sm:p-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]" data-testid="queue-body">
      {detail}
      {aside}
    </section>
  );
}
