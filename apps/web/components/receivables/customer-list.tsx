"use client";

import { ListCard, type ListCardRow } from "@/components/deals/deal-list";
import { useI18n } from "@/lib/i18n";
import type { ReceivableRow, StateTone } from "@/lib/types";
import { isLate, isSoon } from "./state";

/**
 * The Receivables list: every customer, one card each, the ones who owe the most urgently first. A card says how many invoices are open and when the
 * next is due, the most urgent invoice's state in the server's words, and (for one invoice) what is owed and what it nets; a customer who owes
 * nothing says so. Nothing is added up: amounts are the rows' own display strings.
 */
export function CustomerList({ rows, customers }: { rows: ReceivableRow[]; customers: { id: string; name: string }[] }) {
  const { t } = useI18n();
  const ids = [...new Set([...rows.map((r) => r.buyer_id).filter((x): x is string => Boolean(x)), ...customers.map((c) => c.id)])];
  const cards: (ListCardRow & { rank: number })[] = ids.map((id) => {
    const mine = rows.filter((r) => r.buyer_id === id);
    const name = mine[0]?.buyer_name ?? customers.find((c) => c.id === id)?.name ?? id;
    const href = `/receivables?buyer=${encodeURIComponent(id)}`;
    if (!mine.length) {
      return { key: id, buyerId: id, name, meta: null, line: t("recv.list.none"), pill: { text: t("recv.list.pill.none"), tone: "neutral" as StateTone }, figure: null, href: `/customers/${encodeURIComponent(id)}?from=receivables`, group: "none", rank: 3 };
    }
    // The invoice that speaks for the customer: a late one, else one due soon, else the first (the server's own order).
    const lead = mine.find(isLate) ?? mine.find(isSoon) ?? mine[0];
    const tone: StateTone = isLate(lead) ? "bad" : isSoon(lead) ? "warn" : "ok";
    const one = mine.length === 1;
    return {
      key: id,
      buyerId: id,
      name,
      meta: t("recv.list.meta", { n: mine.length, when: lead.due_when ?? "" }),
      line: lead.basis_text ?? lead.invoice ?? "",
      pill: { text: lead.collection_state_text ?? t("recv.list.pill.open"), tone },
      figure: one && lead.outstanding_display ? { text: lead.outstanding_display, tone: isLate(lead) ? "bad" : "neutral" } : { text: t("recv.list.many", { n: mine.length }), tone: "neutral" },
      figureNote: one && lead.net_short ? t("recv.list.net", { net: lead.net_short }) : null,
      href,
      group: isLate(lead) ? "late" : isSoon(lead) ? "soon" : "open",
      rank: isLate(lead) ? 0 : isSoon(lead) ? 1 : 2,
    };
  });
  cards.sort((a, b) => a.rank - b.rank);
  return (
    <section aria-labelledby="recv-list-title" className="space-y-4" data-testid="recv-customer-list">
      <div>
        <h2 id="recv-list-title" className="sec-title font-display text-2xl font-bold tracking-[-0.01em] text-ink">
          {t("recv.list.title")}
        </h2>
        <p className="text-supporting text-ink-3">{t("recv.list.sub")}</p>
      </div>
      <ul className="space-y-3">
        {cards.map((c, i) => (
          <li key={c.key}>
            <ListCard row={c} index={i} label={t("recv.list.open", { name: c.name })} testId="recv-customer-row" />
          </li>
        ))}
      </ul>
    </section>
  );
}
