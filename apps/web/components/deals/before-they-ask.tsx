"use client";

import { Button, Card, Chip, LoadingBlock, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { Disclosure } from "@/components/business/kit";
import { getEnvelope } from "@/lib/api";
import { STRATEGY_MVP } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import type { EnvelopeLeverView, EnvelopePackageView, EnvelopeView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/** The eyebrow and the small headings inside the details: the same quiet label the response cards use. */
const labelCls = "text-xs font-semibold uppercase tracking-wide text-ink-3";

function LeverTable({ levers }: { levers: EnvelopeLeverView[] }) {
  const { t } = useI18n();
  return (
    <div data-testid="envelope-levers">
      <h3 className={labelCls}>{t("biz.strategy.envelope.levers")}</h3>
      {/* On a phone each lever is a list item; the table needs the width of a larger screen. */}
      <ul className="mt-2 divide-y divide-line sm:hidden" data-testid="envelope-levers-list">
        {levers.map((l) => (
          <li key={l.key} className="py-2.5 text-sm" data-testid={`envelope-lever-list-${l.key}`}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 text-ink">{l.label}</span>
              <span className="shrink-0 text-right font-semibold tabular-nums text-ink">{l.maximum_display}</span>
            </div>
            {l.wall_words ? (
              <p className="mt-1 text-xs text-ink-2">
                {t("biz.strategy.envelope.col.wall")}: {l.wall_words}
              </p>
            ) : null}
            <p className="mt-0.5 text-xs text-ink-2">
              {t("biz.strategy.envelope.col.next")}: {l.next_step_sentence}
            </p>
          </li>
        ))}
      </ul>
      <div className="mt-2 hidden sm:block">
        <TableWrap label={t("biz.strategy.envelope.levers.label")}>
          <table className={tableCls}>
            <thead>
              <tr>
                <th scope="col" className={thCls}>
                  {t("biz.strategy.envelope.col.lever")}
                </th>
                <th scope="col" className={thCls}>
                  {t("biz.strategy.envelope.col.max")}
                </th>
                <th scope="col" className={thCls}>
                  {t("biz.strategy.envelope.col.wall")}
                </th>
                <th scope="col" className={thCls}>
                  {t("biz.strategy.envelope.col.next")}
                </th>
              </tr>
            </thead>
            <tbody>
              {levers.map((l) => (
                <tr key={l.key} data-testid={`envelope-lever-${l.key}`}>
                  <th scope="row" className={`${tdCls} font-normal text-ink`}>
                    {l.label}
                  </th>
                  <td className={`${tdCls} font-semibold tabular-nums text-ink`}>{l.maximum_display}</td>
                  <td className={`${tdCls} text-ink-2`}>{l.wall_words ?? "-"}</td>
                  <td className={`${tdCls} text-ink-2`}>{l.next_step_sentence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </div>
    </div>
  );
}

function Packages({ packages, unlisted }: { packages: EnvelopePackageView[]; unlisted: string[] }) {
  const { t } = useI18n();
  return (
    <div className="mt-4">
      <h3 className={labelCls}>{t("biz.strategy.envelope.packages")}</h3>
      <p className="mt-1 text-xs text-ink-3">{t("biz.strategy.envelope.packages.sub")}</p>
      <ul className="mt-2 divide-y divide-line" data-testid="envelope-packages">
        {packages.map((p, i) => (
          <li key={i} className="py-2 text-sm text-ink" data-testid="envelope-package">
            {p.summary}
            {p.flags.length ? <span className="text-ink-2">{` · ${p.flags.join(", ")}`}</span> : null}
          </li>
        ))}
      </ul>
      {unlisted.map((sentence, i) => (
        <p key={i} className="mt-2 text-xs text-ink-2" data-testid="envelope-unlisted">
          {sentence}
        </p>
      ))}
    </div>
  );
}

/** The zone has four narrow columns, so its headings may wrap. */
const zoneTh = thCls.replace("whitespace-nowrap", "align-bottom");

function Zone({ zone }: { zone: EnvelopeView["zone"] }) {
  const { t } = useI18n();
  return (
    <Disclosure className="mt-4" testId="envelope-zone" summary={t("biz.strategy.envelope.zone")}>
      <TableWrap label={t("biz.strategy.envelope.zone.label")}>
        <table className={`${tableCls} text-xs`}>
          <thead>
            <tr>
              <th scope="col" className={zoneTh}>
                {t("biz.strategy.envelope.zone.terms")}
              </th>
              <th scope="col" className={zoneTh}>
                {t("biz.strategy.envelope.zone.min")}
              </th>
              <th scope="col" className={zoneTh}>
                {t("biz.strategy.envelope.zone.counter")}
              </th>
              <th scope="col" className={zoneTh}>
                {t("biz.strategy.envelope.zone.cost")}
              </th>
            </tr>
          </thead>
          <tbody>
            {zone.map((z) => (
              <tr key={z.terms_days} data-testid="envelope-zone-row">
                <th scope="row" className={`${tdCls} font-normal text-ink`}>
                  {z.terms_words}
                </th>
                <td className={`${tdCls} tabular-nums text-ink`}>{z.lowest_price_words}</td>
                <td className={`${tdCls} tabular-nums text-ink-2`}>{z.min_price_bp === null ? "—" : (z.rule_price_display ?? "-")}</td>
                <td className={`${tdCls} tabular-nums text-ink-2`}>{z.cost_per_invoice_display ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </Disclosure>
  );
}

/**
 * "Before they ask" on Deals (behind STRATEGY_MVP): what the owner can live with for this buyer, in the server's words, before the
 * buyer asks. The card sends nothing: its two secondary buttons only open the response card's Option A and Option B (the page's one
 * filled action stays "Send this counter"). Loading takes several seconds on a cold server, so the card holds its place with a
 * caption; an unreachable server says so in one line; a buyer the server has no envelope for (feature off) mounts nothing.
 * Business mode shows the sentences and the details; Demo mode adds how long the server took.
 */
export function BeforeTheyAsk({ buyerId, optionCount, onOpenOption }: { buyerId: string; optionCount: number; onOpenOption: (index: number) => void }) {
  const { t, lang } = useI18n();
  const mode = useMode();
  // The first answer for a set of books is the slow one; every later read is cached on the server.
  const envelope = useAsync(async () => (STRATEGY_MVP ? await getEnvelope(buyerId, lang, true) : null), [buyerId, lang]);
  const e = envelope.data;
  const eyebrow = <span className={labelCls}>{t("biz.strategy.envelope.eyebrow")}</span>;

  if (envelope.error) {
    return (
      <Card id="deal-envelope" title={eyebrow}>
        <div className="flex flex-wrap items-center justify-between gap-3" data-testid="envelope-error">
          <p role="alert" className="text-sm text-ink-2">
            {t("biz.strategy.envelope.error")}
          </p>
          <Button size="sm" onClick={envelope.reload}>
            {t("common.retry")}
          </Button>
        </div>
      </Card>
    );
  }
  if (envelope.loading && !e) {
    // The skeleton is about the height of the answer, so the response card below does not jump when it lands.
    return (
      <Card id="deal-envelope" title={eyebrow}>
        <div data-testid="envelope-loading" aria-busy="true">
          <p aria-hidden className="mb-3 text-sm text-ink-2">
            {t("biz.strategy.envelope.loading")}
          </p>
          <LoadingBlock rows={4} label={t("biz.strategy.envelope.loading")} />
        </div>
      </Card>
    );
  }
  if (!e) return null;

  if (e.refused) {
    return (
      <Card id="deal-envelope" title={eyebrow} actions={<Chip title={t("biz.strategy.envelope.hypothetical.title")}>{t("biz.strategy.envelope.hypothetical")}</Chip>}>
        <p className="text-sm text-ink-2" data-testid="envelope-refused">
          {e.refused}
        </p>
      </Card>
    );
  }

  return (
    <Card id="deal-envelope" title={eyebrow} actions={<Chip title={t("biz.strategy.envelope.hypothetical.title")}>{t("biz.strategy.envelope.hypothetical")}</Chip>}>
      <p className="text-base font-semibold text-ink" data-testid="envelope-primary">
        {e.primary}
      </p>
      <p className="mt-1 text-xs text-ink-3" data-testid="envelope-caption">
        {t("biz.strategy.envelope.caption")}
      </p>
      <p className="mt-1 text-sm text-ink-2" data-testid="envelope-reason">
        {e.reason}
      </p>
      <p className="mt-1 text-sm text-ink-2" data-testid="envelope-money">
        {e.money}
      </p>
      {optionCount > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={() => onOpenOption(0)} data-testid="envelope-open-a">
            {t("biz.strategy.envelope.openA")}
          </Button>
          {optionCount > 1 ? (
            <Button onClick={() => onOpenOption(1)} data-testid="envelope-open-b">
              {t("biz.strategy.envelope.openB")}
            </Button>
          ) : null}
        </div>
      ) : null}
      <Disclosure className="mt-3" testId="envelope-details" summary={t("biz.strategy.envelope.details")}>
        <LeverTable levers={e.levers} />
        {e.packages.length ? <Packages packages={e.packages} unlisted={e.unlisted_counters} /> : null}
        {e.zone.length ? <Zone zone={e.zone} /> : null}
      </Disclosure>
      {mode === "demo" && e.computed_in_seconds > 0 ? (
        <p className="mt-2 text-xs text-ink-3" data-testid="envelope-computed">
          {t("biz.strategy.envelope.computed", { s: e.computed_in_seconds.toFixed(1) })}
        </p>
      ) : null}
    </Card>
  );
}
