"use client";

import Link from "next/link";
import { Avatar, Row, toneFor } from "@/components/business/kit";
import { ChevronRightIcon } from "@/components/icons";
import { Badge, textLinkClass } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { PurchaseRow, PurchaseStage } from "@/lib/types";

const STAGE: Record<PurchaseStage, DictKey> = {
  REVIEW: "buy.stage.REVIEW",
  READY: "buy.stage.READY",
  AWAITING_APPROVAL: "buy.stage.AWAITING_APPROVAL",
  COMMITTED: "buy.stage.COMMITTED",
  PAID: "buy.stage.PAID",
  REJECTED: "buy.stage.REJECTED",
};
const SHOWN = 3;

/** Where a purchase's one next step is done: the reading to review, the approval to give, else the contract's own page. */
function hrefOf(p: PurchaseRow): string {
  if (p.stage === "REVIEW") return `/documents?id=${encodeURIComponent(p.document_id)}`;
  if (p.stage === "AWAITING_APPROVAL") return "/approvals";
  return `/buy/contract?id=${encodeURIComponent(p.document_id)}`;
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("") || "·";
}

/**
 * The buying side on Deals (ADR-0013): the equipment the owner is buying, beside the selling work and second to it. The same card
 * as the inbox: a heading with its count and the way to the whole list, then one row per open purchase (the server's next step
 * under its title, the price on the right, the stage under it), each a link to where that step is done; with nothing bought, one
 * line and the way to read a vendor's contract.
 */
export function BuyingCard({ purchases }: { purchases: PurchaseRow[] }) {
  const { t } = useI18n();
  const open = purchases.filter((p) => p.stage !== "PAID" && p.stage !== "REJECTED");
  const shown = open.slice(0, SHOWN);
  return (
    <section className="flow-card p-4 sm:p-5" aria-labelledby="deals-buying-title" data-testid="deals-buying">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h2 id="deals-buying-title" className="flex items-center gap-2 font-display text-base font-extrabold text-ink">
          {t("deals.buying.title")}
          {open.length ? <Badge tone="neutral">{open.length}</Badge> : null}
        </h2>
        <Link href="/buy" className={`${textLinkClass} inline-flex items-center gap-1`} data-testid="deals-buying-all">
          {t("deals.buying.all")}
          <ChevronRightIcon />
        </Link>
      </div>
      {shown.length ? (
        <ul className="mt-2 divide-y divide-line" data-testid="deals-buying-rows">
          {shown.map((p) => (
            <li key={p.document_id}>
              <Row
                avatar={<Avatar tone={toneFor(p.vendor_name)}>{initials(p.vendor_name)}</Avatar>}
                title={p.title}
                sub={p.next_action}
                tone={p.stage === "AWAITING_APPROVAL" || p.stage === "REVIEW" ? "warn" : undefined}
                right={p.price_display ?? undefined}
                rightSub={t(STAGE[p.stage])}
                href={hrefOf(p)}
                testId={`deals-buying-${p.document_id}`}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-ink-2" data-testid="deals-buying-empty">
          {t("deals.buying.empty")}{" "}
          <Link href="/buy" className="font-medium text-brand-700 underline underline-offset-2">{t("deals.buying.read")}</Link>
        </p>
      )}
      {open.length > SHOWN ? (
        <p className="mt-1 text-supporting text-ink-3">{t("deals.buying.more", { n: open.length - SHOWN })}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-line pt-3 text-sm">
        <Link href="/finance" className={`${textLinkClass} inline-flex items-center gap-1`} data-testid="deals-buying-finance">
          {t("buy.toFinance")}
          <ChevronRightIcon />
        </Link>
        <Link href="/plans" className={`${textLinkClass} inline-flex items-center gap-1`} data-testid="deals-buying-plans">
          {t("buy.toPlans")}
          <ChevronRightIcon />
        </Link>
      </div>
    </section>
  );
}
