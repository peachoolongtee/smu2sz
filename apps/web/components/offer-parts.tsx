"use client";

import { ANNOTATION_STYLE } from "@/lib/annotation-style";
import { useI18n } from "@/lib/i18n";
import type { OfferItem } from "@/lib/offer-items";
import type { Contingency } from "@/lib/types";
import { Badge, KeyValueList, type Tone } from "./ui";

const contingencyTone: Record<Contingency, Tone> = { FIRM: "ok", CONTINGENT: "warn", CLAIMED_UNEVIDENCED: "bad" };

export function NumberChip({ n }: { n: number }) {
  return (
    <span className="grid size-5 shrink-0 place-items-center rounded bg-ink text-[0.7rem] font-bold text-white" aria-label={`#${n}`}>
      {n}
    </span>
  );
}

export function KindChip({ item }: { item: OfferItem }) {
  const { te } = useI18n();
  const label = item.group === "obligation" ? te("obligation", item.kind) : te("flag", item.kind);
  return (
    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold ${ANNOTATION_STYLE[item.kind].chip}`}>
      {label}
    </span>
  );
}

export function SpanQuote({ text }: { text: string }) {
  return (
    <blockquote className="mt-2 border-l-2 border-line-strong pl-2.5 text-xs italic text-ink-2">
      &ldquo;<span className="whitespace-pre-wrap">{text}</span>&rdquo;
    </blockquote>
  );
}

/** One row of the side list: an obligation or a flag, with its span. */
export function OfferItemCard({
  item,
  active,
  onActivate,
}: {
  item: OfferItem;
  active: boolean;
  onActivate: (id: string | null) => void;
}) {
  const { t, te } = useI18n();
  let rows: { k: string; v: string }[] = [];
  let note: string | null = null;
  let tone: Tone | null = null;
  let unresolved: string[] = [];

  if (item.group === "obligation") {
    const o = item.obligation;
    if (o.rate_bp !== null) rows.push({ k: t("item.rate"), v: o.rate_display ?? "" });
    if (o.amount_fen !== null) rows.push({ k: t("item.amount"), v: o.amount_display ?? "" });
    if (o.days_delta !== null) rows.push({ k: t("item.terms"), v: t("item.termsValue", { n: `${o.days_delta > 0 ? "+" : ""}${o.days_delta}` }) });
    if (o.effective_day !== null) rows.push({ k: t("item.effective"), v: t("common.dayN", { n: o.effective_day }) });
    rows.push({
      k: t("item.base"),
      v: [te("basekind", o.base.kind), o.base.amount_fen !== null ? o.base.amount_display : null, o.base.receivable_id]
        .filter(Boolean)
        .join(" · "),
    });
    rows.push({ k: t("item.duration"), v: te("duration", o.duration.kind) });
    rows.push({ k: t("item.confidence"), v: `${Math.round(o.confidence * 100)}%` });
    unresolved = o.unresolved;
    tone = contingencyTone[o.contingency];
    note = te("contingency", o.contingency);
  } else if (item.group === "funding") {
    const c = item.claim;
    rows = [
      { k: t("item.lender"), v: c.lender_name },
      { k: t("item.amount"), v: c.amount_display ?? t("common.none") },
      { k: t("item.rate"), v: c.rate_display ?? t("common.none") },
    ];
    tone = "bad";
    note = t("item.neverMenu");
  } else if (item.group === "authority") {
    rows = [{ k: t("item.claim"), v: te("authority", item.claim.kind) }];
    tone = "bad";
    note = t("item.noAuthority");
  } else {
    rows = [{ k: t("item.requested"), v: te("datarequest", item.claim.kind) }];
    tone = "bad";
    note = t("item.refused");
  }

  return (
    <li
      onMouseEnter={() => onActivate(item.id)}
      onMouseLeave={() => onActivate(null)}
      className={`rounded-lg border bg-surface p-3 ${active ? "border-ink ring-2 ring-ink/15" : "border-line"}`}
      data-testid={`item-${item.id}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <NumberChip n={item.n} />
        <KindChip item={item} />
        {note && tone ? <Badge tone={tone}>{note}</Badge> : null}
      </div>
      <div className="mt-2">
        <KeyValueList items={rows.map((r) => ({ k: r.k, v: r.v }))} />
      </div>
      {unresolved.length ? (
        <ul className="mt-2 list-disc pl-5 text-xs text-warn-fg">
          {unresolved.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      ) : null}
      {item.spans.map((s) => (
        <SpanQuote key={`${s.doc_id}:${s.start}`} text={s.text} />
      ))}
    </li>
  );
}
