"use client";

import Link from "next/link";
import { ActionBar } from "@/components/business/action-bar";
import { usePlanRun } from "@/components/business/next-action";
import type { useFixAlert } from "@/components/home/fix-alert";
import { ButtonLink, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeAttention, HomeAttentionFact, HomeAttentionItem, HomeFundingLine, HomeNextAction, HomeTone } from "@/lib/types";

const FACT_TONE: Record<HomeTone, string> = { ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg", neutral: "text-ink" };

/** What the funding line already says, to match a fact against (case-insensitively). */
function said(line: HomeFundingLine | null | undefined): string[] {
  if (!line) return [];
  return [line.text, line.cost_leg_display, line.cost_total_display, line.authority_text].filter((s): s is string => Boolean(s)).map((s) => s.toLowerCase());
}

/**
 * The plan's line under the card: its sentence (unless the card already says it), the costs with their words ("Cost ¥2,272.29 for the invoice-financing leg;
 * ¥3,113.93 for the whole plan, with the ¥150k credit-line draw already made"; one cost when the leg is the whole plan), and who decides.
 */
function FundingLine({ line, withText = true, testId = "home-funding" }: { line: HomeFundingLine; withText?: boolean; testId?: string }) {
  const { t } = useI18n();
  const same = Boolean(line.cost_leg_display) && line.cost_leg_display === line.cost_total_display;
  const costs = [
    line.cost_leg_display && !same ? { label: line.cost_leg_label, amount: line.cost_leg_display, id: "leg" } : null,
    line.cost_total_display ? { label: line.cost_total_label, amount: line.cost_total_display, id: "total" } : null,
  ].filter((c): c is { label: string | null | undefined; amount: string; id: string } => c !== null);
  const text = withText ? line.text : "";
  if (!text && !costs.length && !line.authority_text) return null;
  return (
    <div className="space-y-1 text-sm text-ink-2" data-testid={testId} data-state={line.state}>
      {text ? <p data-testid="home-funding-text">{text}</p> : null}
      {costs.length ? (
        <p data-testid="home-funding-costs">
          {costs.map((c, i) => (
            <span key={c.id} data-testid={`home-funding-cost-${c.id}`}>
              {i > 0 ? t("home.hy.sep") : null}
              {i === 0 ? t("home.hy.cost.lead") : null}
              <strong className="font-bold tabular-nums text-ink">{c.amount}</strong>
              {c.label ? t("home.hy.cost.for", { label: c.label }) : null}
            </span>
          ))}
        </p>
      ) : null}
      {line.authority_text ? <p data-testid="home-funding-authority">{line.authority_text}</p> : null}
    </div>
  );
}

/** A title that opens with the page's own heading (the server wrote them as one paragraph) is trimmed to what is new: the recommendation. */
function trimmed(title: string, heading: string): string {
  const h = heading.trim();
  return h && title.startsWith(h) && title.length > h.length ? title.slice(h.length).trim() : title;
}

/**
 * Section 3 of Home's order, what needs the owner. An item that needs the owner (a plan to run, an approval, a reply, a collection) is the one raised
 * surface: its eyebrow in amber, the title (trimmed to the recommendation: the heading above already says the rest), the facts the plan's line does not
 * repeat, the page's only filled button and the way to compare. An item that only informs (a landing) is quiet: a neutral eyebrow, one sentence and a
 * text link, no raised card and no filled button. The plan's line sits under a hairline; the other items follow as a short ordered list ("Also waiting").
 * With nothing waiting the card shrinks to the plan's line under one quiet sentence.
 */
export function AttentionCard({
  attention,
  funding,
  nextAction,
  stateVersion,
  fixer,
  heading,
  unread,
}: {
  attention: HomeAttention;
  funding: HomeFundingLine | null | undefined;
  nextAction?: HomeNextAction | null;
  stateVersion: number;
  fixer: ReturnType<typeof useFixAlert>;
  /** The page's h1: a title that starts with it is not said twice. */
  heading: string;
  /** The server's sentence about what could not be read (`partial.text`), said in place of "nothing is urgent" when the queue is incomplete. */
  unread?: string | null;
}) {
  const { t } = useI18n();
  const items = attention.items ?? [];
  const main: HomeAttentionItem | undefined = items.find((i) => i.key === attention.primary_key);
  const others = items.filter((i) => i !== main);
  if (!main) {
    return (
      <section aria-label={t("home.hy.attention")} className="motion-reveal space-y-2 border-y border-line-strong py-3" data-testid="home-attention" data-state="none">
        {/* An incomplete queue (a record that could not be read) never says nothing is urgent: it says what was not read, in the server's words, or nothing. */}
        {attention.incomplete ? (
          unread ? (
            <p className="text-sm font-semibold text-ink-2" data-testid="home-attention-unread">
              {unread}
            </p>
          ) : null
        ) : (
          <p className="text-sm font-semibold text-ink-2" data-testid="home-attention-none">
            {attention.none_text || t("home.hy.none")}
          </p>
        )}
        {funding ? <FundingLine line={funding} /> : null}
        {others.length ? <Queue items={others} /> : null}
      </section>
    );
  }

  // An item that only informs (funding on its way) has nothing for the owner to do: it is said once, quietly.
  if (main.kind === "landing") {
    const link = main.primary ?? main.secondary;
    return (
      <section aria-label={t("home.hy.attention")} className="motion-reveal space-y-2 border-y border-line-strong py-3" data-testid="home-attention" data-state="info" data-kind={main.kind}>
        <p className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3" data-testid="home-attention-eyebrow">
          {main.eyebrow}
        </p>
        {/* Said once, here: when the funds arrive and from where (the plan's sentence and the title would repeat it; the "Arriving next" tile and the rail's first row keep it too). */}
        {main.facts?.length ? (
          <dl className="flex flex-wrap gap-x-8 gap-y-1" data-testid="home-attention-facts">
            {main.facts.map((f, i) => (
              <div key={f.label} className="min-w-0">
                <dt className="text-xs font-semibold text-ink-3">{f.label}</dt>
                <dd className="text-sm font-bold tabular-nums text-ink" data-testid={i === 0 ? "next-action-lands" : undefined}>
                  {f.value}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-[0.9375rem] font-semibold text-ink" data-testid="home-attention-title">
            {main.title}
          </p>
        )}
        {funding ? <FundingLine line={funding} withText={false} /> : null}
        {link ? (
          <Link href={link.href} className={`${textLinkClass} -ml-2 text-sm font-bold`} data-testid="home-attention-link">
            {link.label}
          </Link>
        ) : null}
        {others.length ? <Queue items={others} /> : null}
      </section>
    );
  }

  // The item the owner can run from here: the funding plan, or the approval that plan is waiting in (the plan bar's waiting state).
  const runs = nextAction && (main.kind === "funding" || (main.kind === "approval" && nextAction.pending_approval_id && main.key === `approval:${nextAction.pending_approval_id}`)) ? nextAction : null;
  // The facts the plan's line already says (the cost, who decides) are not said twice; the landing fact is the server's text for when the funds arrive.
  const already = said(funding);
  const facts: HomeAttentionFact[] = (main.facts ?? []).filter((f) => !already.some((s) => s.includes(f.value.toLowerCase())));
  return (
    <section aria-label={t("home.hy.attention")} className="space-y-3" data-testid="home-attention" data-state="needs" data-kind={main.kind}>
      {/* The card that holds the plan's run control is the page's "next action" (the handle the specs and the demo know it by). */}
      <ActionBar flow data-testid={runs ? "home-next-action" : "home-attention-card"} data-alert={runs?.alert_id}>
        <div className="w-full min-w-0 space-y-2.5 sm:space-y-3">
          <p className="text-xs font-extrabold uppercase tracking-[0.08em] text-warn-fg" data-testid="home-attention-eyebrow">
            {main.eyebrow}
          </p>
          <h2 className="max-w-3xl text-pretty text-lg font-extrabold leading-snug text-ink sm:text-xl" data-testid="home-attention-title">
            {trimmed(main.title, heading)}
          </h2>
          {facts.length ? (
            <dl className="flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:gap-x-8 sm:gap-y-2" data-testid="home-attention-facts">
              {facts.map((f, i) => (
                <div key={f.label} className="flex min-w-0 items-baseline justify-between gap-3 sm:block">
                  <dt className="shrink-0 text-xs font-semibold text-ink-3">{f.label}</dt>
                  <dd className={`break-words text-right text-sm font-bold sm:text-left sm:text-base tabular-nums ${FACT_TONE[f.tone ?? "neutral"]}`} data-testid={runs?.lands_when && f.value.includes(runs.lands_when) && !facts.slice(0, i).some((g) => g.value.includes(runs.lands_when ?? "")) ? "next-action-lands" : undefined}>
                    {f.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
          {runs ? (
            <PlanRunControls
              a={runs}
              stateVersion={stateVersion}
              fixer={fixer}
              compare={(main.kind === "funding" ? main.primary : main.secondary) ?? null}
              why={main.kind === "funding" ? (main.secondary ?? null) : null}
              alternatives={main.kind === "funding"}
            />
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

/** The funding item's actions: run the plan (ask, then run), or the waiting state, with the compare link and "Why this?" beside it. */
function PlanRunControls({
  a,
  stateVersion,
  fixer,
  compare,
  why,
  alternatives,
}: {
  a: HomeNextAction;
  stateVersion: number;
  fixer: ReturnType<typeof useFixAlert>;
  compare: { label: string; href: string } | null;
  why: { label: string; href: string } | null;
  alternatives: boolean;
}) {
  const { primary, panel } = usePlanRun(a, stateVersion, fixer);
  return (
    <div className="space-y-3" data-testid="home-attention-run">
      <div className="flex flex-wrap items-center gap-2 max-sm:[&>a]:w-full max-sm:[&>button]:w-full">
        {primary}
        {compare ? (
          <ButtonLink href={compare.href} className="max-sm:w-full" data-testid={alternatives ? "next-action-alternatives" : "home-attention-secondary"}>
            {compare.label}
          </ButtonLink>
        ) : null}
        {why ? (
          <Link href={why.href} className={`${textLinkClass} text-sm font-bold max-sm:w-full max-sm:justify-center`} data-testid="home-attention-why">
            {why.label}
          </Link>
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
