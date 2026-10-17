"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Avatar, toneFor } from "@/components/business/kit";
import { FoldCard } from "@/components/business/surface";
import { ContractWorkbench } from "@/components/capex/contract-workbench";
import { HealthFigures } from "@/components/capex/health-figures";
import { QuickCheck } from "@/components/capex/quick-check";
import { contractsOff } from "@/components/documents";
import { cardTitle } from "@/components/home/v2/home-cards";
import { ChevronRightIcon } from "@/components/icons";
import { Button, ErrorState, LoadingBlock, PageHeader, textLinkClass } from "@/components/ui";
import { StatusPill, type PillTone } from "@/components/ui/status-pill";
import { getCapexContractFixtures, getClock, getFinanceHealth, getPurchases, submitDocument } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { PurchaseRow, PurchaseStage } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

// The pill says who acts (Home's rule): amber when the owner has the next step, green when it is done and on the books, quiet when nothing is left to do.
const STAGE: Record<PurchaseStage, { key: DictKey; tone: PillTone }> = {
  REVIEW: { key: "buy.stage.REVIEW", tone: "amber" },
  READY: { key: "buy.stage.READY", tone: "amber" },
  AWAITING_APPROVAL: { key: "buy.stage.AWAITING_APPROVAL", tone: "amber" },
  COMMITTED: { key: "buy.stage.COMMITTED", tone: "green" },
  PAID: { key: "buy.stage.PAID", tone: "neutral" },
  REJECTED: { key: "buy.stage.REJECTED", tone: "neutral" },
};

export default function Page() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <CapexPage />
    </Suspense>
  );
}

/**
 * Capex, the buy side's one page (ADR-0013): the company's health in four figures, every vendor contract with where it stands, and the picked one worked through on the owner's
 * timeline (schedule, early payment, financing, commitment). The capex screen without a contract (the demo's ¥600k machine) stays below, as a quick check. With the buy side
 * switched off on the server (FEATURE_CAPEX_CONTRACTS), only the quick check is drawn, as before.
 */
function CapexPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const picked = useSearchParams().get("purchase");
  // Days are said as distances from the simulated today ("computed today", "generated 3 days ago").
  const clock = useAsync(getClock, []);
  const today = clock.data?.day ?? 0;
  const list = useAsync(() => getPurchases(lang), [lang]);
  const health = useAsync(() => getFinanceHealth(null), []);
  const off = Boolean(list.error && contractsOff(list.error));
  const purchases = (list.data?.purchases ?? []).filter((p) => p.stage !== "REJECTED");
  // Opened from Deals or picked here, a purchase stays open whatever its stage becomes (committing it moves it to the owner's approval, and the page says so in place).
  const selected = picked ? purchases.find((p) => p.document_id === picked) : undefined;
  const bench = useRef<HTMLDivElement>(null);

  // A purchase opened from Deals (`?purchase=`) or picked here brings its workbench into view.
  const selectedId = selected?.document_id ?? null;
  useEffect(() => {
    if (selectedId) bench.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [selectedId]);

  function pick(id: string | null) {
    router.replace(id ? `${pathname}?purchase=${encodeURIComponent(id)}` : pathname, { scroll: false });
  }

  return (
    <div className="flow-f min-w-0">
      <PageHeader section="capex" title={t("capex.title")} subtitle={off ? t("capex.subtitle") : t("capex.hub.subtitle")} />
      <div className="space-y-4">
        {off ? null : (
          <>
            {health.error && !contractsOff(health.error) ? <ErrorState error={health.error} onRetry={health.reload} /> : null}
            {health.data ? (
              <div>
                <HealthFigures h={health.data} testId="capex-health" />
                <Link href="/finance" className={`${textLinkClass} mt-2 inline-flex items-center gap-1 text-sm`} data-testid="capex-to-finance">
                  {t("buy.toFinance")}
                  <ChevronRightIcon />
                </Link>
              </div>
            ) : health.error ? null : (
              <LoadingBlock rows={2} />
            )}

            {list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : null}
            <Purchases rows={list.data ? purchases : null} selectedId={selectedId} onPick={pick} onRead={list.reload} />

            {selected ? (
              <section ref={bench} id="capex-bench" aria-labelledby="capex-bench-title" className="scroll-mt-24 space-y-4" data-testid={`capex-bench-${selected.document_id}`}>
                <div className="flex flex-wrap items-end justify-between gap-2 pt-2">
                  <div className="min-w-0">
                    <h2 id="capex-bench-title" className="font-display text-xl font-bold tracking-[-0.01em] text-ink">{selected.title}</h2>
                    <p className="mt-0.5 text-supporting text-ink-3">
                      {selected.vendor_name}
                      {selected.price_display ? ` · ${selected.price_display}` : ""}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => pick(null)} data-testid="capex-bench-close">
                    {t("capex.hub.close")}
                  </Button>
                </div>
                <ContractWorkbench key={selected.document_id} id={selected.document_id} row={selected} onCommitted={list.reload} />
              </section>
            ) : null}
          </>
        )}

        {off ? (
          <QuickCheck today={today} />
        ) : (
          <FoldCard id="quick-check" testId="capex-quick" title={t("capex.quick.title")} hint={t("capex.quick.hint")} defaultOpen>
            <QuickCheck today={today} quiet />
          </FoldCard>
        )}
      </div>
    </div>
  );
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("") || "·";
}

/** Where a purchase's next step is done when it is not done here: the reading to review, or the approval to give. */
function elsewhere(p: PurchaseRow): string | null {
  if (p.stage === "REVIEW") return `/documents?id=${encodeURIComponent(p.document_id)}`;
  if (p.stage === "AWAITING_APPROVAL") return "/approvals";
  return null;
}

/** Every vendor contract as one row (the vendor, the server's next step, the price and the stage); a row worked on this page opens its workbench below, the others link out. */
function Purchases({ rows, selectedId, onPick, onRead }: { rows: PurchaseRow[] | null; selectedId: string | null; onPick: (id: string | null) => void; onRead: () => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function readSample() {
    setBusy(true);
    setError(null);
    try {
      const fixtures = await getCapexContractFixtures();
      if (!fixtures.length) throw new Error(t("buy.noSample"));
      await submitDocument({ fixture_id: fixtures[0].id });
      onRead();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="capex-purchases-title" className="motion-reveal f-card p-4 sm:p-5" data-testid="capex-purchases">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <div className="min-w-0">
          <h2 id="capex-purchases-title" className={cardTitle}>{t("capex.hub.purchases")}</h2>
          <p className="mt-1 text-supporting text-ink-3">{t("capex.hub.purchases.sub")}</p>
        </div>
        <Link href="/buy" className={`${textLinkClass} inline-flex items-center gap-1 text-sm`} data-testid="capex-purchases-all">
          {t("deals.buying.all")}
          <ChevronRightIcon />
        </Link>
      </div>
      {error ? <ErrorState error={error} /> : null}
      {rows === null ? (
        <div className="mt-3">
          <LoadingBlock rows={2} />
        </div>
      ) : rows.length === 0 ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3" data-testid="capex-purchases-empty">
          <p className="text-sm text-ink-2">{t("buy.empty.body")}</p>
          <Button variant="secondary" size="sm" loading={busy} onClick={() => void readSample()} data-testid="capex-read-sample">
            {t("buy.read.sample")}
          </Button>
        </div>
      ) : (
        <ul className="mt-3 space-y-1.5" data-testid="capex-purchase-rows">
          {rows.map((p) => {
            const stage = STAGE[p.stage];
            const href = elsewhere(p);
            const current = p.document_id === selectedId;
            const body = (
              <>
                <Avatar tone={toneFor(p.vendor_name)}>{initials(p.vendor_name)}</Avatar>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold text-ink">{p.title}</span>
                  <span className="mt-0.5 block text-supporting text-ink-3">{p.next_action}</span>
                </span>
                <span className="shrink-0 text-right">
                  {p.price_display ? <span className="block font-display text-base font-bold tabular-nums text-ink">{p.price_display}</span> : null}
                  <StatusPill tone={stage.tone} className="mt-1">{t(stage.key)}</StatusPill>
                </span>
                <ChevronRightIcon aria-hidden className={`shrink-0 text-ink-3 transition-transform duration-(--dur-fast) ${current ? "rotate-90" : ""}`} />
              </>
            );
            const cls = "flow-row flow-row-light flex w-full items-center gap-3 px-3 py-3 text-left";
            return (
              <li key={p.document_id}>
                {href ? (
                  <Link href={href} className={cls} data-testid={`capex-purchase-${p.document_id}`}>
                    {body}
                  </Link>
                ) : (
                  <button
                    type="button"
                    className={cls}
                    aria-current={current || undefined}
                    aria-expanded={current}
                    aria-controls={current ? "capex-bench" : undefined}
                    onClick={() => onPick(current ? null : p.document_id)}
                    data-testid={`capex-purchase-${p.document_id}`}
                  >
                    {body}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-line pt-3 text-sm">
        <Link href="/plans" className={`${textLinkClass} inline-flex items-center gap-1`} data-testid="capex-to-plans">
          {t("buy.toPlans")}
          <ChevronRightIcon />
        </Link>
      </div>
    </section>
  );
}
