"use client";

import Link from "next/link";
import { useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { Disclosure } from "@/components/business/kit";
import { CustomerName } from "@/components/customer-link";
import { decisionHref } from "@/components/business/open-decisions";
import { DealStage } from "@/components/deals/deal-steps";
import { ParsedTerms } from "@/components/deals/asks";
import { AllChecks, checkCount, EngineVerdictLine } from "@/components/deals/reasons";
import { StageTrack } from "@/components/deals/stage-track";
import { PlanCard } from "@/components/plan-card";
import { Badge, Callout, Card, Formula, StatePill, textLinkClass, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { annotationsFor, type OfferItem } from "@/lib/offer-items";
import type { AdvancedKey, DealWorkspace, Displayed, Obligation, OfferView, OpenOffer, VerdictView } from "@/lib/types";
import { whenText } from "@/lib/when";

/**
 * The Deals workspace in the A1 pattern: the verdict is the heading (deal-heading.tsx), then who and where, what they ask with what each ask
 * costs, why it matters, the reply and the folds. Every sentence and figure here is the server's string; the page adds nothing up and decides
 * nothing (INVARIANT 13). The bars only size a mark by the server's `*_fen` against the largest; they print no figure of their own.
 */

/**
 * Who and where, unboxed: the buyer, when the offer came and when it was checked as one quiet line, the record's state chip, and the offer's five
 * stages. An open offer carries the server's own five stages (the shared `StageTrack`); a deal past that point (sent, agreed, closed) keeps the
 * record's chips (`DealStage`), which end in the record's own words.
 */
export function SelectedBuyer({
  buyer,
  buyerId,
  received,
  evaluatedWhen,
  state = null,
  open = null,
}: {
  buyer: string;
  /** The buyer's id, so the name is the link to their overview. */
  buyerId?: string;
  received: string;
  evaluatedWhen: string | null;
  state?: { code: string; text: string; tone: Tone } | null;
  open?: OpenOffer | null;
}) {
  const { t } = useI18n();
  return (
    <section id="deal-selected" aria-label={buyer} className="motion-reveal min-w-0 space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className="min-w-0 text-sm text-ink-3" data-testid="deal-selected-meta">
          <strong className="font-extrabold text-ink">
            {buyerId ? (
              <CustomerName id={buyerId} testId="deal-selected-customer">
                {buyer}
              </CustomerName>
            ) : (
              buyer
            )}
          </strong>
          {" · "}
          {received}
          {evaluatedWhen ? (
            <>
              {" · "}
              <span data-testid="deal-evaluated">{t("biz.deals.evaluatedWhen", { when: evaluatedWhen })}</span>
            </>
          ) : null}
        </p>
        {state ? (
          <span data-testid="deal-state-chip" data-state={state.code}>
            <StatePill tone={state.tone}>{state.text}</StatePill>
          </span>
        ) : null}
      </div>
      {open?.stages.length ? (
        <div className="max-w-3xl">
          <StageTrack stages={open.stages} testId="deal-stage" />
        </div>
      ) : state ? (
        <DealStage state={state.code} stateText={state.text} />
      ) : null}
    </section>
  );
}

/** A bar sized by `part` against `whole` (both the server's `*_fen`): plotting only, never a figure. `limit` marks a second value on the same scale. */
function Bar({ part, whole, tone = "brand", limit }: { part: number | null; whole: number; /** `brand` is the ask's own colour, `soft` its lighter step (a one-off line), `bad` only while the ongoing total is over the signed limit. */ tone?: "brand" | "soft" | "bad"; limit?: number }) {
  const w = part !== null && whole > 0 ? Math.max(0, Math.min(100, (part / whole) * 100)) : 0;
  return (
    <div aria-hidden className="relative h-2.5 w-full rounded-pill bg-subtle">
      <div className={`motion-grow h-full rounded-pill ${tone === "bad" ? "bg-bad-solid" : tone === "soft" ? "bg-brand-300" : "bg-brand-600"}`} style={{ width: `${w}%` }} />
      {limit !== undefined && whole > 0 ? <span className="absolute -bottom-1 -top-1 w-0.5 bg-ink" style={{ left: `${Math.min(100, (limit / whole) * 100)}%` }} /> : null}
    </div>
  );
}

/**
 * What they ask, and what each costs you: one row per ask in the server's words with a bar sized by the line's `amount_fen` against the largest
 * line, its display amount and its window words; the ongoing lines then carry their total against the signed limit as one bar with the limit
 * marked, and the server's note that the immediate discount and the ongoing total are not added.
 */
export function WorkspaceAsksCost({ ws, v, children, folded = false }: { ws: DealWorkspace; v: VerdictView | null; children?: React.ReactNode; /** Behind a fold, closed: the paths' columns already say what each path costs, so the asks are the detail beneath them. */ folded?: boolean }) {
  const { t } = useI18n();
  const fi = ws.financial_impact;
  const lineOf = (id: string) => fi.lines.find((l) => l.obligation_id === id);
  const largest = Math.max(0, ...fi.lines.map((l) => l.amount_fen ?? 0));
  const rows = ws.buyer_asks.asks.map((a) => ({ a, l: lineOf(a.obligation_id) }));
  const immediate = rows.filter((r) => r.l?.horizon === "IMMEDIATE");
  const forward = rows.filter((r) => r.l?.horizon === "FORWARD");
  const other = rows.filter((r) => !r.l);
  const sharedWindow = forward.length > 1 && forward.every((r) => r.l?.window_text === forward[0].l?.window_text) ? (forward[0].l?.window_text ?? null) : null;
  const cap = v?.forward_concession?.cap_fen;
  const totalFen = v?.forward_concession?.total_fen ?? fi.forward_total_fen;
  const scale = Math.max(totalFen, cap ?? 0);
  const row = ({ a, l }: (typeof rows)[number], shared: string | null = null) => (
    <li key={a.obligation_id} className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line py-3 first:border-t-0 first:pt-1" data-testid={l ? `deal-impact-${a.type}` : undefined} data-horizon={l?.horizon}>
      <div className="min-w-0 flex-[2_1_18rem]">
        <p className="text-xs font-semibold text-ink-3" data-testid={`deal-ask-label-${a.type}`}>
          {a.label}
        </p>
        <p className="text-sm font-medium text-ink sm:text-base" data-testid={`deal-ask-${a.type}`}>
          {a.text}
        </p>
      </div>
      {l ? (
        <div className="min-w-0 flex-[1_1_13rem]">
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <Bar part={l.amount_fen} whole={largest} tone={l.horizon === "FORWARD" ? (fi.over_cap ? "bad" : "brand") : "soft"} />
            </div>
            <p className="shrink-0 text-base font-extrabold tabular-nums text-ink" data-testid="deal-impact-amount">
              {l.amount_display ?? "—"}
            </p>
          </div>
          {shared === null ? <p className="mt-1 text-pretty text-xs text-ink-3">{l.window_text}</p> : null}
        </div>
      ) : null}
    </li>
  );
  const body = (
    <div data-testid="deal-asks">
      {immediate.length ? (
        <ul data-testid="deal-impact-immediate">
          {immediate.map((r) => row(r))}
        </ul>
      ) : null}
      {other.length ? <ul>{other.map((r) => row(r))}</ul> : null}
      {forward.length ? (
        <div id="deal-impact" data-testid="deal-impact-forward" className="border-b border-line">
          {/* The window the ongoing lines share is the quiet caption of that group, attached to its first row. */}
          <div className={immediate.length ? "mt-3 border-t border-line" : ""}>
            {sharedWindow ? (
              <p className="pt-2 text-xs font-medium text-ink-3" data-testid="deal-impact-window">
                {sharedWindow}
              </p>
            ) : null}
            <ul>{forward.map((r) => row(r, sharedWindow))}</ul>
          </div>
          <div className="border-t border-line py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
              <span className="text-sm font-extrabold text-ink">{t("biz.deals.impact.forwardTotal", { n: fi.window_months })}</span>
              <span className={`shrink-0 text-lg font-extrabold tabular-nums ${fi.over_cap ? "text-bad-fg" : "text-ink"}`} data-testid="deal-impact-total">
                {fi.forward_total_display}
              </span>
            </div>
            <div className="my-2">
              <Bar part={totalFen} whole={scale} tone={fi.over_cap ? "bad" : "brand"} limit={cap} />
            </div>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2">
              <span data-testid="deal-impact-cap">{t("biz.deals.fact.limit", { cap: fi.cap_display })}</span>
              {fi.over_cap ? <Badge tone="bad">{t("biz.deals.impact.overCap")}</Badge> : null}
            </p>
            <p className="mt-1 text-xs text-ink-3" data-testid="deal-impact-note">
              {fi.total_note}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
  if (folded) {
    return (
      <div id="deal-ask" className="border-t border-line pt-1">
        <Disclosure testId="deal-ask-fold" summary={t("biz.deals.askCost")}>
          <div className="pt-1">{body}</div>
        </Disclosure>
        {children}
      </div>
    );
  }
  return (
    <Card flat id="deal-ask" title={t("biz.deals.askCost")}>
      {body}
      {children}
    </Card>
  );
}

/**
 * Why it matters, unboxed: the server's reasons, then the two cash facts of the offer as asked (`settled`: the deal has an outcome, so the line
 * says "had accepted"). The page folds it (`folded`); the cash facts stay here as well as in the picture's columns, so the fact is never lost.
 */
export function WorkspaceWhy({ ws, v, today, settled = false, facts = true, folded = false }: { ws: DealWorkspace; v: VerdictView; today: number; settled?: boolean; facts?: boolean; /** Behind a fold, closed (the page's order puts the price and the picture first); the fold's name is the section's. */ folded?: boolean }) {
  const { t } = useI18n();
  const tr = v.trajectory ?? null;
  const breach = tr?.first_breach_day ?? null;
  const dearer = v.violations.find((x) => x.code === "DISCOUNT_ABOVE_BREAK_EVEN");
  const body = (
    <div data-testid="deal-why-matters">
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink" data-testid="deal-why-reasons">
        {ws.why_it_matters.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      {/* The cash facts are about the offer as the buyer asked for it, not about a counter: the line says so. */}
      {facts && tr && breach !== null ? (
        <>
          <p className="mt-3 text-sm text-ink-2" data-testid="deal-if-accept">
            {settled ? t("biz.deals.ifAccepted") : t("biz.deals.ifAccept")}
          </p>
          <dl className="mt-1 divide-y divide-line border-y border-line text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-2" data-testid="deal-fact-cash">
              <dt className="text-ink-2">{t("biz.deals.fact.breach")}</dt>
              <dd className="text-right">
                <span className="font-semibold tabular-nums text-bad-fg">{whenText(breach, today, t)}</span>
                {tr.first_breach_cash ? <span className="block text-xs text-ink-3">{t("biz.deals.fact.breachCash", { amount: tr.first_breach_cash.text })}</span> : null}
              </dd>
            </div>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-2" data-testid="deal-fact-worst">
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
  );
  if (folded) {
    return (
      <div id="deal-why" className="border-t border-line pt-1">
        <Disclosure testId="deal-why-fold" summary={t("biz.deals.why.title")}>
          <div className="pt-1">{body}</div>
        </Disclosure>
      </div>
    );
  }
  return (
    <Card flat id="deal-why" title={t("biz.deals.why.title")}>
      {body}
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
export function AdvancedDetails({ ws, v, offer, items, asks, only }: { ws: DealWorkspace; v: VerdictView; offer: OfferView; items: OfferItem[]; asks: Displayed<Obligation>[]; /** Only these sections, each its own fold, without the "Advanced details" fold around them (the decision queue's evidence: the buyer's message and the calculations). */ only?: AdvancedKey[] }) {
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
  if (only) {
    const title: Partial<Record<AdvancedKey, string>> = { source_text: t("dq.link.message"), formula: t("dq.link.calcs") };
    return (
      <div className="space-y-2" data-testid="queue-evidence">
        {keys
          .filter((k) => only.includes(k) && k in body && body[k] !== null)
          .map((k) => (
            <Disclosure key={k} testId={`deal-adv-${k}`} summary={title[k] ?? t(ADVANCED_TITLE[k])}>
              <div className="pt-1">{body[k]}</div>
            </Disclosure>
          ))}
      </div>
    );
  }
  return (
    <Disclosure className="border-t border-line pt-1" testId="deal-advanced" summary={t("biz.deals.advanced")}>
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
