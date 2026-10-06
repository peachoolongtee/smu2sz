"use client";

import Link from "next/link";
import { useEffect } from "react";
import { SimpleAgreementsCard } from "@/components/simple/agreements-card";
import { SimpleBorrowingCard } from "@/components/simple/borrowing-card";
import { SimpleBuyersCard } from "@/components/simple/buyers-card";
import { SimpleCashCard } from "@/components/simple/cash-card";
import { Badge, PageHeader } from "@/components/ui";
import { getClock } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * The owner overview: buyers, cash, agreements and borrowing options, with fewer numbers than the full home (`/`).
 * It reads and writes only through lib/api.ts and the shared demo session, so a deal made here is the same commitment,
 * terms hash and ledger entry the full overview, Our decision and the ledger show; every card refetches on `bump()`.
 */
export default function SimpleOverviewPage() {
  const { t } = useI18n();
  const clock = useAsync(getClock, []);

  // A card refused for want of the owner token refetches once the owner has signed in.
  useEffect(() => onSignedIn(() => bump()), []);

  return (
    <>
      <PageHeader
        title={t("simple.title")}
        subtitle={t("simple.subtitle")}
        actions={
          <>
            {clock.data ? <Badge tone="info" className="px-3 py-1 text-sm">{t("home.dayBadge", { n: clock.data.day })}</Badge> : null}
            <Link href="/" className="text-sm font-medium text-brand-700 underline underline-offset-2" data-testid="simple-to-full">
              {t("simple.toFull")}
            </Link>
          </>
        }
      />
      <div className="space-y-6">
        <SimpleCashCard />
        <SimpleBuyersCard />
        <SimpleAgreementsCard />
        <SimpleBorrowingCard />
      </div>
    </>
  );
}
