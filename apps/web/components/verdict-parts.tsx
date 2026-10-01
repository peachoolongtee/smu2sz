"use client";

import { useI18n } from "@/lib/i18n";
import { AnnualisedLine } from "@/components/annualised";
import type { AnnualisedLeg, Displayed, CounterProposal, OperationView, Violation } from "@/lib/types";
import { CodeBadge, OpStatusBadge, TierBadge } from "./badges";
import { SpanQuote } from "./offer-parts";
import { Badge, Formula, Hash } from "./ui";

/** One violation with its formula and inputs shown verbatim from the server. */
export function ViolationCard({ v }: { v: Displayed<Violation> }) {
  const { t, te } = useI18n();
  const inputs = Object.entries(v.inputs);
  return (
    <li className="min-w-0 rounded-lg border border-bad-line bg-surface p-4" data-testid={`violation-${v.code}`}>
      <div className="flex flex-wrap items-center gap-2">
        <CodeBadge code={v.code} tone="bad" />
        {v.day !== null ? <Badge tone="bad">{t("common.dayN", { n: v.day })}</Badge> : null}
        {v.month !== null ? <Badge>{t("common.monthN", { n: v.month })}</Badge> : null}
        {v.curable === true ? <Badge tone="warn">{t("verdict.curable")}</Badge> : null}
        {v.curable === false ? <Badge>{t("verdict.notCurable")}</Badge> : null}
      </div>
      <p className="mt-2 text-sm font-medium">{v.message}</p>
      <p className="text-xs text-ink-3">{te("violation", v.code)}</p>

      {v.observed || v.limit ? (
        <dl className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <dt className="text-xs text-ink-3">{t("verdict.observed")}</dt>
            <dd className="text-lg font-semibold tabular-nums text-bad-fg">{v.observed ?? t("common.none")}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-3">{t("verdict.limit")}</dt>
            <dd className="text-lg font-semibold tabular-nums">{v.limit ?? t("common.none")}</dd>
          </div>
        </dl>
      ) : null}

      {v.formula ? (
        <div className="mt-3">
          <p className="mb-1 text-xs font-semibold text-ink-3">{t("common.formula")}</p>
          <Formula>{v.formula}</Formula>
        </div>
      ) : null}

      {inputs.length ? (
        <div className="mt-3">
          <p className="mb-1 text-xs font-semibold text-ink-3">{t("verdict.inputs")}</p>
          <dl className="grid grid-cols-[minmax(0,max-content)_minmax(0,1fr)] gap-x-4 gap-y-1 rounded-md border border-line bg-subtle px-3 py-2 font-mono text-xs">
            {inputs.map(([k, val]) => (
              <div key={k} className="contents">
                <dt className="text-ink-3">{k}</dt>
                <dd className="min-w-0 break-words text-ink">{val}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      {v.curable && v.cure_cost_display ? (
        <div className="mt-3 rounded-md border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg">
          <p className="font-semibold">{t("verdict.cureCost", { cost: v.cure_cost_display })}</p>
          {v.cure_note ? <p className="mt-0.5 text-xs">{v.cure_note}</p> : null}
        </div>
      ) : null}

      {v.spans.map((s) => (
        <SpanQuote key={`${s.doc_id}:${s.start}`} text={s.text} />
      ))}
    </li>
  );
}

export function CounterCard({ c, legs = [] }: { c: Displayed<CounterProposal>; legs?: AnnualisedLeg[] }) {
  const { t } = useI18n();
  return (
    <li className="flex min-w-0 flex-col rounded-lg border border-warn-line bg-surface p-4" data-testid={`counter-${c.id}`}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-base font-semibold">{c.label}</h3>
        <div className="text-right">
          <p className="text-xs text-ink-3">{t("verdict.counter.cost")}</p>
          <p className="text-lg font-semibold tabular-nums">{c.supplier_cost_display}</p>
        </div>
      </div>
      <blockquote className="mt-3 rounded-md border-l-4 border-warn-line bg-warn-bg/60 px-3 py-2 text-sm">{c.text}</blockquote>
      <p className="mt-3 text-sm text-ink-2">{c.rationale}</p>
      {legs.map((l) => (
        <div key={l.obligation_id} className="mt-3">
          <AnnualisedLine leg={l} />
        </div>
      ))}
      <div className="mt-3">
        <p className="mb-1 text-xs font-semibold text-ink-3">{t("verdict.counter.priced")}</p>
        <Formula>{c.formula}</Formula>
      </div>
    </li>
  );
}

export function OperationsList({ ops }: { ops: OperationView[] }) {
  const { t, te } = useI18n();
  if (!ops.length) return <p className="text-sm text-ink-2">{t("ledger.ops.empty")}</p>;
  return (
    <ul className="divide-y divide-line rounded-lg border border-line">
      {ops.map((o) => (
        <li key={o.op_id} className="space-y-1 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-ink-3">#{o.seq}</span>
            <span className="text-sm font-medium">{te("opkind", o.kind)}</span>
            <TierBadge tier={o.tier} />
            <OpStatusBadge status={o.status} />
          </div>
          <p className="text-sm text-ink-2">{o.summary}</p>
          <p className="flex flex-wrap items-center gap-1 text-xs text-ink-3">
            {t("ledger.hash")}: <Hash value={o.entry_hash} />
          </p>
        </li>
      ))}
    </ul>
  );
}
