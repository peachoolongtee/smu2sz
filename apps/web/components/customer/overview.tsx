"use client";

import Link from "next/link";
import { ArrowLeftIcon } from "@/components/icons";
import { PartialRead } from "@/components/business/freshness";
import { Card, ButtonLink, PageHeader, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { CustomerOverviewView, OverviewAction, OverviewFigure, OverviewHistoryRow, OverviewRow, OverviewTone } from "@/lib/types";

/** The colour a tone gives a figure or a value; a status is always said in the server's words as well, so colour is never the only channel. */
const toneText: Record<OverviewTone, string> = { neutral: "text-ink", ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };

/** A quiet text link inside a sentence or a row: brand text, underlined, 14 px. */
const inlineLink = "font-bold text-brand-700 underline underline-offset-2 hover:text-brand-600";

function Figure({ figure }: { figure: OverviewFigure }) {
  return (
    <div className="min-w-0 lg:border-r lg:border-line lg:px-5 lg:first:pl-0 lg:last:border-r-0" data-testid={`customer-figure-${figure.key}`}>
      <dt className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">{figure.label}</dt>
      <dd className={`mt-1 break-words font-display text-xl font-extrabold tabular-nums tracking-[-0.02em] sm:text-2xl ${toneText[figure.tone]}`} data-testid={`customer-figure-${figure.key}-value`}>
        {figure.value_display}
      </dd>
      <dd className="mt-0.5 break-words text-sm text-ink-2" data-testid={`customer-figure-${figure.key}-note`}>
        {figure.note}
      </dd>
    </div>
  );
}

/** The decision card: the one place on the page that asks the owner for something. A decision waiting leads with its primary; none waiting says so and keeps the other two links. */
function Decision({ view }: { view: CustomerOverviewView }) {
  const decision = view.decision;
  const rest: OverviewAction[] = decision ? decision.secondary : (view.actions ?? []);
  const links = rest.map((a) => (
    <ButtonLink key={a.key} href={a.href} data-testid={`customer-action-${a.key}`}>
      {a.label}
    </ButtonLink>
  ));
  if (!decision) {
    if (!view.none_text && !rest.length) return null;
    return (
      <div className="motion-reveal flex flex-wrap items-center justify-between gap-x-8 gap-y-3" data-testid="customer-decision-none">
        {view.none_text ? <p className="min-w-0 flex-[2_1_20rem] text-pretty text-sm text-ink-2">{view.none_text}</p> : null}
        {links.length ? <div className="flex flex-wrap gap-2">{links}</div> : null}
      </div>
    );
  }
  return (
    <Card tone="warn" id="customer-decision">
      <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-4" data-testid="customer-decision">
        <div className="min-w-0 flex-[2_1_22rem]">
          <h2 id="customer-decision-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-warn-fg">
            {decision.eyebrow}
          </h2>
          <p className="mt-1 text-pretty font-display text-lg font-extrabold leading-snug text-ink" data-testid="customer-decision-text">
            {decision.text}
          </p>
          {decision.authority_text ? (
            <p className="mt-2 border-l-2 border-line-strong pl-3 text-sm text-ink-2" data-testid="customer-decision-authority">
              {decision.authority_text}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink href={decision.primary.href} variant="primary" data-testid="customer-decision-primary">
            {decision.primary.label}
          </ButtonLink>
          {links}
        </div>
      </div>
    </Card>
  );
}

/** Labelled rows, a hairline between: the label quiet, the value in the row's tone, the server's note beneath it. */
function Rows({ rows, testId }: { rows: OverviewRow[]; testId: string }) {
  return (
    <dl className="divide-y divide-line" data-testid={testId}>
      {rows.map((r) => (
        <div key={r.key} className="grid gap-x-4 gap-y-0.5 py-2.5 sm:grid-cols-[minmax(0,9.5rem)_minmax(0,1fr)]" data-testid={`${testId}-${r.key}`}>
          <dt className="text-sm text-ink-3">{r.label}</dt>
          <dd className="min-w-0 break-words text-sm">
            <span className={`font-bold tabular-nums ${toneText[r.tone]}`}>{r.value_display}</span>
            {r.note ? <span className="mt-0.5 block text-ink-2">{r.note}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Economics({ view }: { view: CustomerOverviewView }) {
  const { t } = useI18n();
  if (!view.economics?.length) return null;
  return (
    <Card flat id="customer-economics" title={t("customer.economics")}>
      <Rows rows={view.economics} testId="customer-economics-rows" />
      {view.economics_note || (view.edit_href && view.edit_label) ? (
        <p className="mt-3 text-pretty text-sm leading-relaxed text-ink-2" data-testid="customer-economics-note">
          {view.economics_note}
          {view.edit_href && view.edit_label ? (
            <>
              {view.economics_note ? " " : null}
              <Link href={view.edit_href} className={inlineLink} data-testid="customer-edit">
                {view.edit_label}
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
    </Card>
  );
}

/** The exposure panel; while the read is off the server's `note` says why, in place of the rows. */
function Exposure({ view }: { view: CustomerOverviewView }) {
  const { t } = useI18n();
  const exposure = view.exposure;
  if (!exposure && !view.note) return null;
  return (
    <Card flat id="customer-exposure" title={t("customer.exposure")}>
      {exposure ? (
        <>
          <Rows rows={exposure.rows} testId="customer-exposure-rows" />
          {exposure.same_figures_note ? (
            <p className="mt-3 text-pretty text-sm leading-relaxed text-ink-2" data-testid="customer-exposure-note">
              {exposure.same_figures_note}
            </p>
          ) : null}
        </>
      ) : (
        <p className="py-2.5 text-pretty text-sm text-ink-2" data-testid="customer-exposure-off">
          {view.note}
        </p>
      )}
    </Card>
  );
}

function History({ rows }: { rows: OverviewHistoryRow[] }) {
  const { t } = useI18n();
  if (!rows.length) return null;
  return (
    <Card flat id="customer-history" title={t("customer.history")}>
      <ul className="divide-y divide-line" data-testid="customer-history-rows">
        {rows.map((h, i) => (
          <li key={i} className="grid gap-x-4 gap-y-0.5 py-2.5 text-sm sm:grid-cols-[7.5rem_minmax(0,1fr)_auto] sm:items-baseline" data-testid="customer-history-row">
            <span className="text-ink-3">{h.when_text}</span>
            <span className="min-w-0 break-words text-ink">{h.text}</span>
            {h.href ? (
              <Link href={h.href} className={`${textLinkClass} -ml-2 justify-self-start text-sm sm:ml-0 sm:justify-self-end`}>
                {h.link_label ?? t("customer.history.open")}
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/**
 * A customer's overview in the order of the board: the eyebrow and the server's back link, the name and one sentence, the four figures, the one
 * commercial decision (or the line that none waits, with the two other links), the economics and the exposure side by side, and the history. Each
 * section is drawn only when the server sent it. Every word, figure and link is the server's; the page decides nothing.
 */
export function CustomerOverview({ view, onRetry }: { view: CustomerOverviewView; onRetry: () => void }) {
  const { t } = useI18n();
  const back = view.context?.back;
  return (
    <div className="space-y-6" data-testid="customer-overview">
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <p className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("customer.title")}</p>
          {back ? (
            <Link href={back.href} className="motion-press hit -mr-2 inline-flex min-h-8 items-center gap-1 rounded-pill px-2 text-sm font-bold text-brand-700 underline underline-offset-2 hover:bg-brand-50" data-testid="customer-back">
              <ArrowLeftIcon width={14} height={14} />
              {back.label}
            </Link>
          ) : null}
        </div>
        <PageHeader title={view.name} subtitle={view.summary_text} />
      </div>
      <PartialRead partial={view.partial} onRetry={onRetry} />
      {view.figures?.length ? (
        <section aria-label={t("customer.figures")} data-testid="customer-figures">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 border-y border-line py-4 lg:grid-cols-4 lg:gap-x-0">
            {view.figures.map((f) => (
              <Figure key={f.key} figure={f} />
            ))}
          </dl>
        </section>
      ) : null}
      <Decision view={view} />
      <div className="grid gap-x-10 gap-y-6 lg:grid-cols-2">
        <Economics view={view} />
        <Exposure view={view} />
      </div>
      <History rows={view.history ?? []} />
    </div>
  );
}
