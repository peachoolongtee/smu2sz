"use client";

import Link from "next/link";
import { ActionBar } from "@/components/business/action-bar";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { ButtonLink, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeAttention, HomeAttentionItem, HomeFundingLine, HomeNextAction, HomeTone } from "@/lib/types";

const FACT_TONE: Record<HomeTone, string> = { ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg", neutral: "text-ink" };

/** The plan's line under the card: its sentence, the two costs each with its own label (a leg and the whole plan), and who decides. */
function FundingLine({ line, testId = "home-funding" }: { line: HomeFundingLine; testId?: string }) {
  const { t } = useI18n();
  const costs = [
    line.cost_leg_display ? { label: line.cost_leg_label, amount: line.cost_leg_display, id: "leg" } : null,
    line.cost_total_display ? { label: line.cost_total_label, amount: line.cost_total_display, id: "total" } : null,
  ].filter((c): c is { label: string | null | undefined; amount: string; id: string } => c !== null);
  if (!line.text && !costs.length && !line.authority_text) return null;
  return (
    <div className="space-y-1 text-sm text-ink-2" data-testid={testId} data-state={line.state}>
      {line.text ? <p data-testid="home-funding-text">{line.text}</p> : null}
      {costs.length ? (
        <p data-testid="home-funding-costs">
          {costs.map((c, i) => (
            <span key={c.id} data-testid={`home-funding-cost-${c.id}`}>
              {i > 0 ? t("home.hy.sep") : null}
              {c.label ? `${c.label} ` : null}
              <strong className="font-bold tabular-nums text-ink">{c.amount}</strong>
            </span>
          ))}
        </p>
      ) : null}
      {line.authority_text ? <p data-testid="home-funding-authority">{line.authority_text}</p> : null}
    </div>
  );
}

/**
 * Section 2 of Home, what needs the owner: the one raised surface is the queue's primary item (its eyebrow in amber, the title, a row of facts, the
 * page's only filled button and a quiet second one), the plan's line beneath a hairline, and the other items as a short ordered list under the card
 * ("Also waiting"), never as more raised cards. With nothing waiting the card shrinks to the plan's line under one quiet sentence.
 */
export function AttentionCard({ attention, funding, nextAction, stateVersion, fixer }: { attention: HomeAttention; funding: HomeFundingLine | null | undefined; nextAction?: HomeNextAction | null; stateVersion: number; fixer: ReturnType<typeof useFixAlert> }) {
  const { t } = useI18n();
  const items = attention.items ?? [];
  const main: HomeAttentionItem | undefined = items.find((i) => i.key === attention.primary_key);
  const others = items.filter((i) => i !== main);
  if (!main) {
    return (
      <section aria-label={t("home.hy.attention")} className="motion-reveal space-y-2 border-y border-line-strong py-3" data-testid="home-attention" data-state="none">
        <p className="text-sm font-semibold text-ink-2" data-testid="home-attention-none">
          {attention.none_text || t("home.hy.none")}
        </p>
        {funding ? <FundingLine line={funding} /> : null}
        {others.length ? <Queue items={others} /> : null}
      </section>
    );
  }
  // The funding item is the plan the owner can run from here; so is the approval that plan is waiting in (the plan bar's waiting state).
  const runs = nextAction && (main.kind === "funding" || (main.kind === "approval" && nextAction.pending_approval_id && main.key === `approval:${nextAction.pending_approval_id}`)) ? nextAction : null;
  return (
    <section aria-label={t("home.hy.attention")} className="space-y-3" data-testid="home-attention" data-state="needs" data-kind={main.kind}>
      {/* The card that holds the plan's run control is the page's "next action" (the handle the specs and the demo know it by). */}
      <ActionBar flow data-testid={runs ? "home-next-action" : "home-attention-card"} data-alert={runs?.alert_id}>
        <div className="w-full min-w-0 space-y-2.5 sm:space-y-3">
          <p className="text-xs font-extrabold uppercase tracking-[0.08em] text-warn-fg" data-testid="home-attention-eyebrow">
            {main.eyebrow}
          </p>
          <h2 className="max-w-3xl text-pretty text-lg font-extrabold leading-snug text-ink sm:text-xl" data-testid="home-attention-title">
            {main.title}
          </h2>
          {main.facts?.length ? (
            <dl className="flex flex-wrap gap-x-8 gap-y-2" data-testid="home-attention-facts">
              {main.facts.map((f) => (
                <div key={f.label} className="min-w-0">
                  <dt className="text-xs font-semibold text-ink-3">{f.label}</dt>
                  <dd className={`text-base font-bold tabular-nums ${FACT_TONE[f.tone ?? "neutral"]}`}>{f.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {runs ? (
            <PlanRunControls a={runs} stateVersion={stateVersion} fixer={fixer} compare={(main.kind === "funding" ? main.primary : main.secondary) ?? null} alternatives={main.kind === "funding"} />
          ) : main.primary || main.secondary ? (
            <div className="flex flex-wrap items-center gap-2">
              {main.primary ? (
                <ButtonLink href={main.primary.href} variant="primary" className="max-sm:w-full" data-testid="home-attention-primary">
                  {main.primary.label}
                </ButtonLink>
              ) : null}
              {main.secondary ? (
                <ButtonLink href={main.secondary.href} className="max-sm:w-full" data-testid="home-attention-secondary">
                  {main.secondary.label}
                </ButtonLink>
              ) : null}
            </div>
          ) : null}
          {funding ? (
            <div className="border-t border-line-strong pt-3">
              <FundingLine line={funding} />
            </div>
          ) : null}
        </div>
      </ActionBar>
      {others.length ? <Queue items={others} /> : null}
    </section>
  );
}

/** The funding item's actions: run the plan (ask, then run), or the waiting state, with the compare link beside it. */
function PlanRunControls({ a, stateVersion, fixer, compare, alternatives }: { a: HomeNextAction; stateVersion: number; fixer: ReturnType<typeof useFixAlert>; compare: { label: string; href: string } | null; alternatives: boolean }) {
  const { primary, panel } = usePlanRun(a, stateVersion, fixer);
  return (
    <div className="space-y-3" data-testid="home-attention-run">
      <div className="flex flex-wrap items-center gap-2 max-sm:[&>button]:w-full max-sm:[&>a]:w-full">
        {primary}
        {compare ? (
          <ButtonLink href={compare.href} className="max-sm:w-full" data-testid={alternatives ? "next-action-alternatives" : "home-attention-secondary"}>
            {compare.label}
          </ButtonLink>
        ) : null}
      </div>
      {panel}
    </div>
  );
}

/** The rest of the queue, in the server's order: one quiet line each, linking to where it is answered. */
function Queue({ items }: { items: HomeAttentionItem[] }) {
  const { t } = useI18n();
  return (
    <div className="text-sm text-ink-2" data-testid="home-attention-queue">
      <p className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("home.hy.also")}</p>
      <ol className="mt-1 list-decimal space-y-0.5 pl-5 marker:text-ink-3">
        {items.map((i) => (
          <li key={i.key} data-testid={`home-queue-${i.key}`}>
            {i.primary ? (
              <Link href={i.primary.href} className={`${textLinkClass} -ml-2 min-h-8 whitespace-normal py-0.5 text-sm`}>
                {i.title}
              </Link>
            ) : (
              i.title
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
