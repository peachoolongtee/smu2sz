"use client";

import Link from "next/link";
import { useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { Disclosure } from "@/components/business/kit";
import { decisionHref } from "@/components/business/open-decisions";
import { DealStage } from "@/components/deals/deal-steps";
import { ParsedTerms } from "@/components/deals/asks";
import { AllChecks, checkCount, EngineVerdictLine } from "@/components/deals/reasons";
import { PlanCard } from "@/components/plan-card";
import { Badge, Callout, Card, Formula, StatePill, textLinkClass, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { annotationsFor, type OfferItem } from "@/lib/offer-items";
import type { AdvancedKey, DealWorkspace, Displayed, Obligation, OfferView, VerdictView } from "@/lib/types";
import { whenText } from "@/lib/when";

/**
 * The Deals workspace (wayfinder #65 Wave 3, audit section 12): one selected buyer, then the sections in the order the server gives
 * (`workspace.order`): what the buyer asks, what it costs (the immediate discount and the forward figure on their own lines), why it matters,
 * what FLOW recommends, the one priced response, the folds. Every sentence and figure here is the server's string; the page adds nothing
 * up and decides nothing (INVARIANT 13).
 */

/**
 * The compact header of the selected deal: the buyer, when the offer came, when it was checked, and one chip for where the deal stands (the
 * record's state in the server's words, its colour the server's `state_tone`; the browser never picks one) and, under the meta line, the stage
 * indicator: Received · Analysed · Response ready · Sent · Agreed, one chip each, from the same record state. No ask line (the asks card says it once).
 */
export function SelectedBuyer({ buyer, received, evaluatedWhen, state = null }: { buyer: string; received: string; evaluatedWhen: string | null; state?: { code: string; text: string; tone: Tone } | null }) {
  const { t } = useI18n();
  return (
    <section id="deal-selected" aria-labelledby="deal-selected-title" className="motion-reveal min-w-0 rounded-card border border-line bg-surface px-4 py-2 shadow-card sm:py-3">
      {/* One wrapping row: the buyer, then the state chip and the meta line. On a phone the chip and the meta line share a row (the first screen is short);
          from sm the chip sits at the right of the buyer and the meta line has its own row. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 sm:gap-y-1">
        <h2 id="deal-selected-title" className="min-w-0 text-balance text-base font-semibold text-ink max-sm:basis-full sm:flex-1">
          {buyer}
        </h2>
        {state ? (
          <span data-testid="deal-state-chip" data-state={state.code} className="sm:order-2">
            <StatePill tone={state.tone}>{state.text}</StatePill>
          </span>
        ) : null}
        <p className="min-w-0 text-xs text-ink-3 max-sm:flex-1 sm:order-3 sm:basis-full" data-testid="deal-selected-meta">
          {received}
          {evaluatedWhen ? (
            <>
              {" · "}
              <span data-testid="deal-evaluated">{t("biz.deals.evaluatedWhen", { when: evaluatedWhen })}</span>
            </>
          ) : null}
        </p>
      </div>
      {state ? <DealStage state={state.code} stateText={state.text} /> : null}
    </section>
  );
}

/** What the buyer asks, in the server's sentences (one line per obligation). */
export function WorkspaceAsks({ ws, children }: { ws: DealWorkspace; children?: React.ReactNode }) {
  return (
    <Card id="deal-ask" title={ws.buyer_asks.title}>
      <ul className="space-y-1" data-testid="deal-asks">
        {ws.buyer_asks.asks.map((a) => (
          <li key={a.obligation_id} className="text-sm font-medium text-ink sm:text-base" data-testid={`deal-ask-${a.type}`}>
            {a.text}
          </li>
        ))}
      </ul>
      {children}
    </Card>
  );
}

/**
 * What it costs: the lines the server named. The immediate discount stands on its own (it is taken off the invoice and checked against its
 * own cap); the forward lines and their total are kept apart in their own box with the limit and the server's note that the two are not
 * added. Under it, why it matters: the server's reasons, then the two cash facts of the offer as asked (`settled`: the deal has an outcome,
 * so the line says "had accepted").
 */
export function WorkspaceImpact({ ws, v, today, settled = false }: { ws: DealWorkspace; v: VerdictView; today: number; settled?: boolean }) {
  const { t } = useI18n();
  const fi = ws.financial_impact;
  const immediate = fi.lines.filter((l) => l.horizon === "IMMEDIATE");
  const forward = fi.lines.filter((l) => l.horizon === "FORWARD");
  const tr = v.trajectory ?? null;
  const breach = tr?.first_breach_day ?? null;
  const dearer = v.violations.find((x) => x.code === "DISCOUNT_ABOVE_BREAK_EVEN");
  // Forward lines that share one valuation window say it once, above them; otherwise each says its own.
  const sharedWindow = forward.length > 1 && forward.every((l) => l.window_text === forward[0].window_text) ? forward[0].window_text : null;
  const line = (l: DealWorkspace["financial_impact"]["lines"][number], shared: string | null = null) => (
    <li key={l.obligation_id} className="py-2.5 first:pt-0 last:pb-0" data-testid={`deal-impact-${l.type}`} data-horizon={l.horizon}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <span className="text-sm font-medium text-ink">{l.label}</span>
        <span className="shrink-0 text-base font-semibold tabular-nums text-ink" data-testid="deal-impact-amount">
          {l.amount_display ?? "—"}
        </span>
      </div>
      {shared === null ? <p className="mt-0.5 text-xs text-ink-3">{l.window_text}</p> : null}
    </li>
  );
  return (
    <Card id="deal-impact" title={fi.title}>
      <div className="space-y-4">
        {immediate.length ? <ul className="divide-y divide-line" data-testid="deal-impact-immediate">{immediate.map((l) => line(l))}</ul> : null}
        {forward.length ? (
          <div className="rounded-tile border border-line bg-subtle px-4 py-3" data-testid="deal-impact-forward">
            {sharedWindow ? (
              <p className="mb-2 text-xs text-ink-3" data-testid="deal-impact-window">
                {sharedWindow}
              </p>
            ) : null}
            <ul className="divide-y divide-line">{forward.map((l) => line(l, sharedWindow))}</ul>
            <div className="mt-3 border-t border-line pt-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="text-sm font-semibold text-ink">{t("biz.deals.impact.forwardTotal", { n: fi.window_months })}</span>
                <span className={`shrink-0 text-lg font-semibold tabular-nums ${fi.over_cap ? "text-bad-fg" : "text-ink"}`} data-testid="deal-impact-total">
                  {fi.forward_total_display}
                </span>
              </div>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2">
                <span data-testid="deal-impact-cap">{t("biz.deals.fact.limit", { cap: fi.cap_display })}</span>
                {fi.over_cap ? <Badge tone="bad">{t("biz.deals.impact.overCap")}</Badge> : null}
              </p>
              <p className="mt-1 text-xs text-ink-3" data-testid="deal-impact-note">
                {fi.total_note}
              </p>
            </div>
          </div>
        ) : null}

        <div data-testid="deal-why-matters">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.why.title")}</h3>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-ink" data-testid="deal-why-reasons">
            {ws.why_it_matters.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {/* The cash facts are about the offer as the buyer asked for it, not about a counter: the line says so. */}
          {tr && breach !== null ? (
            <>
              <p className="mt-3 text-sm text-ink-2" data-testid="deal-if-accept">
                {settled ? t("biz.deals.ifAccepted") : t("biz.deals.ifAccept")}
              </p>
              <dl className="mt-2 divide-y divide-line rounded-tile border border-line text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 px-3 py-2" data-testid="deal-fact-cash">
                  <dt className="text-ink-2">{t("biz.deals.fact.breach")}</dt>
                  <dd className="text-right">
                    <span className="font-semibold tabular-nums text-bad-fg">{whenText(breach, today, t)}</span>
                    {tr.first_breach_cash ? <span className="block text-xs text-ink-3">{t("biz.deals.fact.breachCash", { amount: tr.first_breach_cash.text })}</span> : null}
                  </dd>
                </div>
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 px-3 py-2" data-testid="deal-fact-worst">
                  <dt className="text-ink-2">{t("biz.deals.fact.worst")}</dt>
                  <dd className="text-right">
                    <span className="font-semibold tabular-nums text-ink">{tr.min_cash.text}</span>
                    <span className="block text-xs text-ink-3">{whenText(tr.min_cash_day, today, t)}</span>
                  </dd>
                </div>
              </dl>
            </>
          ) : null}
          {dearer ? (
            <p className="mt-3 text-sm text-ink-2" data-testid="deal-discount-dearer">
              {t("biz.deals.discountDearer", { rate: dearer.observed ?? "", limit: (dearer.limit ?? "").replace(/^<\s*/, "") })}
            </p>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

const ADVANCED_TITLE: Record<AdvancedKey, "biz.deals.parsed" | "biz.deals.original" | "biz.deals.allChecks" | "biz.calculation" | "biz.deals.engineVerdict" | "biz.deals.adv.audit"> = {
  parsed_obligations: "biz.deals.parsed",
  source_text: "biz.deals.original",
  checks: "biz.deals.allChecks",
  formula: "biz.calculation",
  engine_verdict: "biz.deals.engineVerdict",
  audit_evidence: "biz.deals.adv.audit",
};

/**
 * Everything the owner does not need to decide, under one fold, in the sections the server names (`workspace.advanced.keys`): how the agent
 * read the message, the message itself, every check, the formulas, the engine's verdict and the audit evidence. The page folds the verdict's
 * existing fields; it copies none of them.
 */
export function AdvancedDetails({ ws, v, offer, items, asks }: { ws: DealWorkspace; v: VerdictView; offer: OfferView; items: OfferItem[]; asks: Displayed<Obligation>[] }) {
  const { t, te, lang } = useI18n();
  const [active, setActive] = useState<string | null>(null);
  const keys = Object.keys(ws.advanced.keys) as AdvancedKey[];
  const body: Record<AdvancedKey, React.ReactNode> = {
    parsed_obligations: asks.length ? <ParsedTerms asks={asks} /> : null,
    source_text: (
      <div className="space-y-3">
        {offer.documents.map((doc) => (
          <AnnotatedText
            key={doc.doc_id}
            ariaLabel={t("inbox.annotated")}
            text={doc.text}
            annotations={annotationsFor(items, doc.doc_id, (i) => (i.group === "obligation" ? te("obligation", i.kind) : te("flag", i.kind)))}
            activeId={active}
            onActivate={setActive}
          />
        ))}
      </div>
    ),
    checks: <AllChecks v={v} />,
    formula: (
      <div className="space-y-4">
        {v.concession_values.length ? (
          <ul className="space-y-2">
            {v.concession_values.map((c) => (
              <li key={c.obligation_id} className="rounded-tile border border-line px-3 py-2 text-sm" data-testid="deal-calc-item">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-ink">{c.interpretation ?? c.basis}</span>
                  <span className="font-semibold tabular-nums">{c.value_display}</span>
                </div>
                <Disclosure className="mt-1.5" summary={t("common.formula")}>
                  <p className="mt-1 text-xs text-ink-3">{c.basis}</p>
                  <div className="mt-1">
                    <Formula>{c.formula}</Formula>
                  </div>
                </Disclosure>
              </li>
            ))}
          </ul>
        ) : null}
        {v.counters.map((c) => (
          <div key={c.id} className="rounded-tile border border-line px-3 py-2 text-sm">
            <p className="font-medium text-ink">{c.label}</p>
            <div className="mt-1.5">
              <Formula>{c.formula}</Formula>
            </div>
          </div>
        ))}
        {v.plan ? <PlanCard plan={v.plan} id="deal-plan" /> : null}
        <p className="text-xs text-ink-3">
          <Link href="/verdict" className={textLinkClass}>
            {t("biz.deals.fullVerdict")}
          </Link>
        </p>
      </div>
    ),
    engine_verdict: <EngineVerdictLine v={v} />,
    audit_evidence: (
      <div className="space-y-2 text-xs text-ink-2" data-testid="deal-audit-evidence">
        <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5">
          {v.decision_id ? (
            <>
              <dt>{t("biz.deals.adv.record")}</dt>
              <dd className="break-all">
                <Link href={decisionHref(v.decision_id)} className={`font-mono ${textLinkClass}`}>
                  {v.decision_id}
                </Link>
              </dd>
            </>
          ) : null}
          <dt>{t("biz.deals.adv.calcVersion")}</dt>
          <dd className="break-all font-mono">{v.calc_version}</dd>
          <dt>{t("biz.deals.adv.stateVersion")}</dt>
          <dd className="font-mono tabular-nums">{v.state_version}</dd>
          <dt>{t("biz.deals.adv.mandateVersion")}</dt>
          <dd className="font-mono tabular-nums">{v.mandate_version}</dd>
        </dl>
        {v.autonomy?.gaps.length ? (
          <Callout tone="warn" title={t("biz.deals.adv.gaps")}>
            <ul className="list-disc pl-5">
              {v.autonomy.gaps.map((g, i) => (
                <li key={g}>{(lang === "zh" && v.autonomy?.gaps_when?.[i]) || g}</li>
              ))}
            </ul>
          </Callout>
        ) : null}
      </div>
    ),
  };
  return (
    <Disclosure card testId="deal-advanced" summary={t("biz.deals.advanced")}>
      <div className="space-y-2">
        {keys
          .filter((k) => k in body && body[k] !== null)
          .map((k) => (
            <Disclosure key={k} testId={`deal-adv-${k}`} summary={k === "checks" ? t("biz.deals.allChecks", { n: checkCount(v) }) : t(ADVANCED_TITLE[k])}>
              <div className="pt-1">{body[k]}</div>
            </Disclosure>
          ))}
      </div>
    </Disclosure>
  );
}
