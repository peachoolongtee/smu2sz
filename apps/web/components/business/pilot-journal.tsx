"use client";

import { Card, Chip, ErrorState, LoadingBlock } from "@/components/ui";
import { getPilotJournal } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useStrategyAsync } from "@/lib/use-async";
import { Disclosure } from "@/components/business/kit";

/**
 * The shadow pilot's journal (wayfinder map #58), at the foot of Activity, behind STRATEGY_MVP and in live mode only (the page
 * mounts it on `STRATEGY_MVP && API_MODE === "live"`). Read-only: it lists what the owner recorded against what FLOW said, newest
 * first, and posts nothing. Every string is the entry's own (the owner's words, the sentence FLOW displayed); the labels are the
 * dictionary's. A 403 FEATURE_DISABLED or a missing route is no data (the read resolves to null) and the section is not drawn. The
 * entry carries no money field, so nothing here formats or computes money.
 */
export function PilotJournal() {
  const { t, te } = useI18n();
  const journal = useStrategyAsync(() => getPilotJournal(), []);
  if (journal.loading) return <LoadingBlock rows={1} />;
  if (journal.error) return <ErrorState error={journal.error} onRetry={journal.reload} />;
  if (!journal.data) return null;
  const entries = journal.data.entries;
  return (
    <Card id="pilot-journal" title={t("biz.pilot.title")} subtitle={t("biz.pilot.sub")}>
      {entries.length ? (
        <ol className="divide-y divide-line" data-testid="pilot-journal-list">
          {entries.map((e) => (
            <li key={e.id} className="py-3 text-sm" data-testid={`pilot-journal-${e.id}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{te("biz.pilot.answer", e.answer)}</span>
                <Chip>{te("biz.pilot.choice", e.choice)}</Chip>
                <span className="text-xs text-ink-3">
                  {t("biz.pilot.week", { n: e.week })} · {t("biz.pilot.recorded", { date: e.recorded_on })}
                </span>
              </div>
              <dl className="mt-1 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5">
                <dt className="text-ink-3">{t("biz.pilot.flowSaid")}</dt>
                <dd className="break-words text-ink-2" data-testid="pilot-journal-said">
                  {e.flow_said}
                </dd>
                <dt className="text-ink-3">{t("biz.pilot.youDid")}</dt>
                <dd className="break-words text-ink" data-testid="pilot-journal-did">
                  {e.owner_did}
                </dd>
              </dl>
              <Disclosure className="mt-1" summary={t("biz.auditDetails")}>
                <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs text-ink-2">
                  <dt>{t("biz.pilot.sme")}</dt>
                  <dd className="break-all">{e.sme}</dd>
                  <dt>{t("biz.pilot.snapshot")}</dt>
                  <dd className="break-all font-mono">{e.snapshot_hash}</dd>
                </dl>
              </Disclosure>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-ink-3" data-testid="pilot-journal-empty">
          {t("biz.pilot.empty")}
        </p>
      )}
    </Card>
  );
}
