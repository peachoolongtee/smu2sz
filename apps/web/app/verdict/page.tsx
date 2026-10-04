"use client";

import Link from "next/link";
import { useState } from "react";
import { AnnualisedCard, offerLegs } from "@/components/annualised";
import { AutonomyPanel } from "@/components/autonomy-panel";
import { CheckIcon } from "@/components/icons";
import { DealSteps } from "@/components/deal-steps";
import { NextStep, nextLinkCls } from "@/components/next-step";
import { OutcomeBadge, TierBadge, outcomeHasTier } from "@/components/badges";
import { PlanCard } from "@/components/plan-card";
import {
  Badge,
  Button,
  Callout,
  Card,
  EmptyState,
  ErrorState,
  Formula,
  Hash,
  KeyValueList,
  LoadingBlock,
  PageHeader,
  Segmented,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
import { CounterCard, OperationsList, ViolationCard } from "@/components/verdict-parts";
import { getState, negotiate } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { recordNegotiation } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { BuyerProfile, NegotiationView, VerdictView } from "@/lib/types";
import { useCurrentOffer } from "@/lib/use-current";

export default function VerdictPage() {
  const { t } = useI18n();
  const cur = useCurrentOffer();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function evaluate() {
    if (!cur.offerId) return;
    setBusy(true);
    setError(null);
    try {
      await evaluateAndCache(cur.offerId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={t("verdict.title")} subtitle={t("verdict.subtitle")} />
      <DealSteps />
      {cur.error ? (
        <ErrorState error={cur.error} onRetry={cur.reload} />
      ) : cur.loading ? (
        <LoadingBlock rows={3} />
      ) : !cur.offerId ? (
        <EmptyState
          title={t("verdict.noOffer.title")}
          body={t("verdict.noOffer.body")}
          action={
            <Link href="/inbox" className="inline-flex min-h-10 items-center rounded-md bg-brand-600 px-3.5 text-sm font-medium text-white hover:bg-brand-700">
              {t("verdict.noOffer.cta")}
            </Link>
          }
        />
      ) : !cur.verdict ? (
        <div className="space-y-3">
          <EmptyState
            title={t("verdict.notEvaluated.title")}
            body={t("verdict.notEvaluated.body")}
            action={
              <Button variant="primary" loading={busy} onClick={() => void evaluate()}>
                {t("verdict.evaluate")}
              </Button>
            }
          />
          {error ? <ErrorState error={error} /> : null}
        </div>
      ) : (
        <VerdictBody
          verdict={cur.verdict}
          offerId={cur.offerId}
          negotiation={cur.negotiation}
          autonomyEligible={cur.offer?.offer.autonomy_eligible}
          autonomyNotes={cur.offer?.offer.autonomy_notes}
        />
      )}
    </>
  );
}

function VerdictBody({
  verdict,
  offerId,
  negotiation,
  autonomyEligible,
  autonomyNotes,
}: {
  verdict: VerdictView;
  offerId: string;
  negotiation: NegotiationView | null;
  autonomyEligible?: boolean;
  autonomyNotes?: string[];
}) {
  const { t, te } = useI18n();
  const canNegotiate = verdict.counters.length > 0;
  const plan = negotiation?.plan ?? verdict.plan;
  // Lead times come from the books' facilities; until they load (or if the read fails) the plan shows no landing day.
  const books = useAsync(getState, []);
  const leadTimes = books.data ? Object.fromEntries(books.data.state.facilities.map((f) => [f.id, f.lead_time_days])) : undefined;

  return (
    <div className="space-y-6">
      <Card id="outcome" tone={verdict.outcome === "REJECT" ? "bad" : verdict.outcome === "ACCEPT" ? "ok" : "warn"}>
        <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
          <div>
            <p className="mb-1 text-xs font-medium text-ink-3">{t("verdict.outcome")}</p>
            <span data-testid="outcome-badge">
              <OutcomeBadge outcome={verdict.outcome} large />
            </span>
          </div>
          <div className="min-w-0 flex-1 basis-72">
            <p className="text-lg font-semibold leading-snug text-ink" data-testid="verdict-plain">
              {te("verdict.plain", verdict.outcome)}
            </p>
            <details className="mt-2 text-xs text-ink-3">
              <summary className="cursor-pointer">{t("verdict.refs")}</summary>
              <p className="mt-1 text-sm leading-relaxed text-ink-2">{verdict.summary}</p>
              <p className="mt-1 font-mono">
                {verdict.id} &middot; {offerId} &middot; {t("verdict.versions", { m: verdict.mandate_version, s: verdict.state_version, c: verdict.calc_version })}
              </p>
            </details>
          </div>
          <div className="min-w-44">
            {outcomeHasTier(verdict.outcome) ? <p className="mb-1 text-xs font-medium text-ink-3">{t("verdict.tier")}</p> : null}
            {outcomeHasTier(verdict.outcome) ? (
              <>
                <TierBadge tier={verdict.required_tier} />
                <p className="mt-1 max-w-56 text-xs text-ink-2">{te("tier.short", verdict.required_tier)}</p>
              </>
            ) : (
              <p className="max-w-56 text-sm text-ink-2" data-testid="nothing-executed">
                {t("verdict.nothingExecuted")}
              </p>
            )}
          </div>
        </div>
      </Card>

      <VerdictNextStep verdict={verdict} negotiation={negotiation} />

      <AutonomyPanel
        outcome={verdict.outcome}
        tier={verdict.required_tier}
        summary={verdict.summary}
        passedChecks={verdict.passed_checks}
        autonomyEligible={autonomyEligible}
        autonomyNotes={autonomyNotes}
        autonomy={verdict.autonomy}
      />

      <section aria-labelledby="violations-title">
        <h2 id="violations-title" className="mb-2 text-sm font-semibold">
          {verdict.violations.length ? t("verdict.violations", { n: verdict.violations.length }) : t("verdict.why")}
        </h2>
        {verdict.violations.length ? (
          <ul className="grid gap-4 xl:grid-cols-2">
            {verdict.violations.map((v) => (
              <ViolationCard key={`${v.code}-${v.day ?? v.month ?? ""}`} v={v} />
            ))}
          </ul>
        ) : (
          <Callout tone="ok">{t("verdict.noViolations")}</Callout>
        )}
      </section>

      <section aria-labelledby="counters-title">
        <h2 id="counters-title" className="mb-2 text-sm font-semibold">
          {t("verdict.counters", { n: verdict.counters.length })}
        </h2>
        {verdict.counters.length ? (
          <ul className="grid gap-4 lg:grid-cols-2">
            {verdict.counters.map((c) => (
              <CounterCard key={c.id} c={c} legs={verdict.annualised?.filter((l) => c.obligations.some((o) => o.id === l.obligation_id))} />
            ))}
          </ul>
        ) : (
          <Callout tone="neutral">{t("verdict.noCounters")}</Callout>
        )}
      </section>

      {canNegotiate ? <NegotiationPanel offerId={offerId} negotiation={negotiation} /> : null}

      {plan ? <PlanCard plan={plan} id="verdict-plan" leadTimes={leadTimes} /> : null}

      <section aria-labelledby="working-title" className="space-y-6 border-t border-line pt-6">
        <div>
          <h2 id="working-title" className="text-sm font-semibold">{t("verdict.working")}</h2>
          <p className="mt-0.5 text-xs text-ink-3">{t("verdict.working.sub")}</p>
        </div>
        <AnnualisedCard legs={offerLegs(verdict.annualised, verdict.counters)} />

        {verdict.passed_checks.length ? (
          <Card id="passed" title={t("verdict.passed", { n: verdict.passed_checks.length })} subtitle={t("verdict.passed.sub")}>
            <ul className="divide-y divide-line">
              {verdict.passed_checks.map((c) => (
                <li key={c.code} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-2">
                  <div className="min-w-0 flex-1 basis-64">
                    <p className="flex items-center gap-1.5 text-sm font-medium">
                      <span className="text-ok-fg">
                        <CheckIcon />
                      </span>
                      {c.label}
                    </p>
                    {c.formula ? <p className="mt-0.5 font-mono text-xs text-ink-3">{c.formula}</p> : null}
                  </div>
                  <p className="text-sm tabular-nums">
                    <span className="font-semibold">{c.observed}</span>
                    <span className="text-ink-3"> &nbsp;{c.limit}</span>
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}

        {verdict.concession_values.length ? (
          <Card
            id="valuation"
            title={t("verdict.valuation")}
            subtitle={t("verdict.valuation.sub")}
            actions={<Badge tone="bad">{t("verdict.total", { total: verdict.forward_concession_total_display })}</Badge>}
          >
            <TableWrap label={t("verdict.valuation")}>
              <table className={tableCls}>
                <caption className="sr-only">{t("verdict.valuation")}</caption>
                <thead>
                  <tr>
                    <th scope="col" className={thCls}>{t("verdict.obligation")}</th>
                    <th scope="col" className={`${thCls} text-right`}>{t("verdict.value")}</th>
                    <th scope="col" className={`${thCls} text-right`}>{t("verdict.perInvoice")}</th>
                    <th scope="col" className={thCls}>{t("verdict.basis")}</th>
                  </tr>
                </thead>
                <tbody>
                  {verdict.concession_values.map((c) => (
                    <tr key={c.obligation_id}>
                      <td className={`${tdCls} font-mono text-xs`}>{c.obligation_id}</td>
                      <td className={`${tdCls} text-right font-medium tabular-nums`}>{c.value_display}</td>
                      <td className={`${tdCls} text-right tabular-nums`}>{c.per_invoice_display ?? t("common.none")}</td>
                      <td className={`${tdCls} min-w-72`}>
                        <p>{c.basis}</p>
                        <div className="mt-1.5">
                          <Formula>{c.formula}</Formula>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </Card>
        ) : null}

      </section>
    </div>
  );
}

/** What to do after reading the decision. Shown only where the next move is clear; otherwise the page speaks for itself. */
function VerdictNextStep({ verdict, negotiation }: { verdict: VerdictView; negotiation: NegotiationView | null }) {
  const { t } = useI18n();
  if (negotiation?.commitment) {
    return (
      <NextStep label={t("next.label")} action={<Link href="/#home-agreements" className={nextLinkCls} data-testid="next-home">{t("next.seeHome")}</Link>}>
        {t("next.agreed")}
      </NextStep>
    );
  }
  if (negotiation) {
    return (
      <NextStep label={t("next.label")} action={<Link href="/inbox" className={nextLinkCls}>{t("next.backToOffers")}</Link>}>
        {t("next.noDeal")}
      </NextStep>
    );
  }
  if (verdict.counters.length) {
    return (
      <NextStep label={t("next.label")} action={<a href="#counters-title" className={nextLinkCls}>{t("next.toCounters")}</a>}>
        {t("next.counter")}
      </NextStep>
    );
  }
  return null;
}

function NegotiationPanel({ offerId, negotiation }: { offerId: string; negotiation: NegotiationView | null }) {
  const { t } = useI18n();
  const [profile, setProfile] = useState<BuyerProfile>("cooperative");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      recordNegotiation(await negotiate(offerId, { buyer_profile: profile }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card id="negotiation" title={t("neg.title")} subtitle={t("neg.subtitle")}>
      {!negotiation ? (
        <div className="space-y-3">
          <Segmented
            label={t("neg.profile")}
            name="profile"
            value={profile}
            onChange={setProfile}
            options={[
              { value: "cooperative", label: t("neg.cooperative") },
              { value: "hard_line", label: t("neg.hardLine") },
            ]}
          />
          <p className="text-xs text-ink-3">{t("neg.hidden")}</p>
          <div>
            <Button variant="primary" loading={busy} onClick={() => void run()}>
              {t("neg.run")}
            </Button>
          </div>
          {error ? <ErrorState error={error} /> : null}
        </div>
      ) : (
        <div className="space-y-4" data-testid="negotiation-result">
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={negotiation.outcome === "DEAL" ? "ok" : "neutral"} className="px-3 py-1 text-sm font-bold">
              {negotiation.outcome === "DEAL" ? t("neg.deal") : t("neg.noDeal")}
            </Badge>
            <p className="min-w-0 flex-1 basis-64 text-sm">{negotiation.message}</p>
          </div>

          <ol className="space-y-2" aria-label={t("neg.rounds")}>
            {negotiation.rounds.map((r) => (
              <li key={r.round} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-line px-3 py-2 text-sm">
                <span className="font-mono text-xs text-ink-3">{t("neg.round", { n: r.round })}</span>
                <span className="font-medium">{r.counter_label ?? t("common.none")}</span>
                <Badge tone={r.buyer_response === "ACCEPT" ? "ok" : "bad"}>{r.buyer_response === "ACCEPT" ? t("neg.accepted") : t("neg.refused")}</Badge>
                <span className="text-ink-2">&ldquo;{r.buyer_text}&rdquo;</span>
              </li>
            ))}
          </ol>

          {negotiation.commitment ? (
            <div className="rounded-lg border border-ok-line bg-ok-bg/50 p-3">
              <p className="mb-2 text-sm font-semibold text-ok-fg">{t("neg.commitment")}</p>
              <KeyValueList
                items={[
                  { k: t("neg.commitment.id"), v: negotiation.commitment.id },
                  { k: t("neg.commitment.status"), v: negotiation.commitment.status },
                  { k: t("neg.commitment.nonce"), v: <span className="font-mono text-xs">{negotiation.commitment.nonce}</span> },
                  { k: t("neg.commitment.expires"), v: t("common.dayN", { n: negotiation.commitment.expires_day }) },
                  { k: t("neg.commitment.forward"), v: negotiation.commitment.forward_value_display },
                  { k: t("neg.commitment.hash"), v: <Hash value={negotiation.commitment.terms_hash} /> },
                ]}
              />
            </div>
          ) : null}

          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("neg.operations")}</p>
            <OperationsList ops={negotiation.operations} />
            <p className="mt-2 text-xs">
              {negotiation.commitment ? (
                <>
                  <Link href="/#home-agreements" className="font-medium text-brand-700 underline underline-offset-2" data-testid="neg-see-home">
                    {t("next.seeHome")}
                  </Link>
                  {" · "}
                </>
              ) : null}
              <Link href="/ledger" className="font-medium text-brand-700 underline underline-offset-2">
                {t("neg.openLedger")}
              </Link>
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
