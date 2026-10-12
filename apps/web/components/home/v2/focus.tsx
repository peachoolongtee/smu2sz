"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { XIcon } from "@/components/icons";
import { PathColumns } from "@/components/deals/path-columns";
import { EventPicture } from "@/components/home/event-picture";
import { ActionRow } from "@/components/home/v2/worklist";
import { Button, ButtonLink, Card, DecisionCard, ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { StateWord } from "@/components/ui/state-word";
import { stateKey } from "@/components/ui/state-word-model";
import { getCustomerFocus, getDealExposure, getOfferPicture } from "@/lib/api";
import { customerHref } from "@/lib/customer-href";
import { type HomeSelection, offerOfDecision } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { CustomerOverviewView, ExposurePathWords, HomeView, OverviewFigure, OverviewTone, PicturePath, WorklistView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const TONE_TEXT: Record<OverviewTone, string> = { neutral: "text-ink", ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };

/** The close control of a focus: a quiet icon button (also Escape, handled by the page). */
function Close({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Button size="sm" onClick={onClose} aria-label={t("hv2.focus.close")} className="shrink-0" data-testid="focus-close">
      <XIcon className="size-4" />
    </Button>
  );
}

/** "All business ›" (clears the selection), then, in a deal, the customer's name (back to the customer): the way up, always on screen. */
function Crumbs({ onAll, customer, onCustomer }: { onAll: () => void; customer?: { name: string; onClick: () => void } | null; onCustomer?: never }) {
  const { t } = useI18n();
  void onCustomer;
  return (
    <nav aria-label={t("hv2.focus.all")} className="flex min-w-0 flex-wrap items-center gap-x-1 text-meta font-extrabold tracking-[0.08em] text-ink-3" data-testid="focus-crumbs">
      <button type="button" onClick={onAll} className={`${textLinkClass} -ml-2 gap-1 text-meta font-extrabold`} data-testid="focus-all">
        {t("hv2.focus.all")} <span aria-hidden>›</span>
      </button>
      {customer ? (
        <button type="button" onClick={customer.onClick} className={`${textLinkClass} gap-1 text-meta font-extrabold`} data-testid="focus-customer">
          {customer.name}
        </button>
      ) : null}
    </nav>
  );
}

function Figure({ figure }: { figure: OverviewFigure }) {
  const key = stateKey(figure.state);
  return (
    <div className="min-w-0" data-testid={`focus-figure-${figure.key}`}>
      <dt className="text-meta font-extrabold tracking-[0.08em] text-ink-3">{figure.label}</dt>
      <dd className={`mt-1 break-words text-lg font-extrabold tabular-nums ${TONE_TEXT[figure.tone]}`} data-testid={`focus-figure-${figure.key}-value`}>
        {figure.value_display}
      </dd>
      {key && figure.state_text ? (
        <dd className="mt-0.5">
          <StateWord state={key} testId={`focus-figure-${figure.key}-state`}>
            {figure.state_text}
          </StateWord>
        </dd>
      ) : null}
      <dd className="mt-0.5 break-words text-supporting text-ink-2">{figure.note}</dd>
    </div>
  );
}

/** The polite announcement of what is now shown, said once: it sits outside the keyed section, so a new selection changes its text. */
function Announce({ text }: { text: string }) {
  return (
    <p role="status" aria-live="polite" className="sr-only" data-testid="focus-announce">
      {text}
    </p>
  );
}

/** A read that is on its way, failed, or is here. */
function Reading<T>({ read, children }: { read: { data: T | undefined; error: Error | undefined; reload: () => void }; children: (d: T) => ReactNode }) {
  const { t } = useI18n();
  if (read.data !== undefined) return <>{children(read.data)}</>;
  if (read.error) return <ErrorState error={t("hv2.focus.failed")} onRetry={read.reload} />;
  return <LoadingBlock rows={3} label={t("hv2.focus.working")} />;
}

/**
 * A customer, in place: the name and the server's sentence, the four figures with their state words (the Customer overview's own read), what is open with this customer
 * from the worklist's rows (a decision opens in place, another row leads where the server says), and the way to the customer's page. The company strip and the alert stay
 * where they are. Closing (the cross, "All business", Escape) clears the selection.
 */
export function CustomerFocusPanel({ customerId, worklist, selection, onAll }: { customerId: string; worklist: WorklistView | null | undefined; selection: HomeSelection; onAll: () => void }) {
  const { t, lang } = useI18n();
  const view = useAsync(() => getCustomerFocus(customerId, lang), [customerId, lang]);
  const rows = [...(worklist?.needs_you ?? []), ...(worklist?.waiting ?? [])].filter((r) => r.customer_id === customerId);
  return (
    <Card id="home-focus" labelledBy="home-focus-title">
      <Announce text={view.data?.name ?? ""} />
      <div key={customerId} className="motion-swap space-y-4" data-testid="home-customer-focus" data-customer={customerId}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Crumbs onAll={onAll} />
            <p className="mt-1 text-meta font-extrabold tracking-[0.08em] text-ink-3">{t("hv2.focus.customer")}</p>
          </div>
          <Close onClose={onAll} />
        </div>
        <Reading read={view}>
          {(v: CustomerOverviewView) => (
            <>
              <div>
                <h2 id="home-focus-title" className="type-section text-balance text-ink" data-testid="focus-title">
                  {v.name}
                </h2>
                {v.summary_text ? <p className="mt-1 text-pretty text-sm text-ink-2">{v.summary_text}</p> : null}
              </div>
              {v.figures?.length ? (
                <dl aria-label={t("hv2.focus.figures")} className="grid grid-cols-2 gap-x-4 gap-y-3 border-y border-line py-3 xl:grid-cols-4" data-testid="focus-figures">
                  {v.figures.map((f) => (
                    <Figure key={f.key} figure={f} />
                  ))}
                </dl>
              ) : null}
              <section aria-label={t("hv2.focus.rows")}>
                <h3 className="text-meta font-extrabold tracking-[0.08em] text-ink-3">{t("hv2.focus.rows")}</h3>
                {rows.length ? (
                  <ul className="-mx-5 mt-1" data-testid="focus-rows">
                    {rows.map((r) => (
                      <ActionRow key={r.key} row={r} first={false} selection={selection} />
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-sm text-ink-2" data-testid="focus-rows-none">
                    {v.none_text ?? t("hv2.focus.none")}
                  </p>
                )}
              </section>
              <div>
                <ButtonLink href={customerHref(customerId)} data-testid="focus-open-customer">
                  {t("hv2.focus.open")} <span aria-hidden>›</span>
                </ButtonLink>
              </div>
            </>
          )}
        </Reading>
      </div>
    </Card>
  );
}

/** The scenarios of a deal: the current books, the offer as asked, and each reply, as the picture names them; the scenario in the address is "asked" or "counter:<k>" (the k-th reply). */
export function scenarioOf(paths: PicturePath[], key: string): string | null {
  const p = paths.find((x) => x.key === key);
  if (!p) return null;
  if (p.kind === "asked") return "asked";
  return `counter:${paths.filter((x) => x.kind === "reply").findIndex((x) => x.key === key)}`;
}
export function pathOfScenario(paths: PicturePath[], scenario: string | null): PicturePath | null {
  if (!scenario) return null;
  if (scenario === "asked") return paths.find((p) => p.kind === "asked") ?? null;
  const k = /^counter:(\d+)$/.exec(scenario);
  return k ? (paths.filter((p) => p.kind === "reply")[Number(k[1])] ?? null) : null;
}

/** What the exposure read says about one path, as rows: the server's words, each a sentence or a figure; a path it has no word for leaves the row out. */
function PathFigures({ path, words }: { path: PicturePath; words: ExposurePathWords | undefined }) {
  const { t } = useI18n();
  const cost = path.cost_total_display ? `${path.cost_total_display}${path.cost_basis_text ? ` · ${path.cost_basis_text}` : ""}` : null;
  const rows = [
    { key: "cost", label: t("hv2.deal.cost"), value: cost },
    { key: "lowest", label: t("hv2.deal.lowest"), value: words?.lowest_display ? `${words.lowest_display}${words.lowest_when_text ? ` · ${words.lowest_when_text}` : ""}` : null },
    { key: "limit", label: t("hv2.deal.limit"), value: words?.limit_text ?? null },
    { key: "share", label: t("hv2.deal.share"), value: words?.share_after_text ?? null },
  ].filter((r): r is { key: string; label: string; value: string } => Boolean(r.value));
  if (!rows.length) return null;
  return (
    <dl className="divide-y divide-line rounded-tile border border-line px-3" data-testid="deal-figures" data-path={path.key}>
      {rows.map((r) => (
        <div key={r.key} className="grid gap-x-4 gap-y-0.5 py-2 sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)]" data-testid={`deal-figure-${r.key}`}>
          <dt className="text-supporting text-ink-3">{r.label}</dt>
          <dd className="min-w-0 break-words text-sm font-semibold text-ink">{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * A decision, in place: the customer's decision as the server words it (its eyebrow, headline, sentence and who may send it), the one filled primary the server's action for
 * the deal (opening it on Deals with the recommended path), the scenario as `SegmentedTabs` bound to `?scenario=` (the server validates it and the figures wait for its answer),
 * the paths as the Deals page's own columns, that scenario's figures from the exposure read, and the company chart with the scenario's path as the one hypothetical, dashed line.
 * While a read is on its way the working word stands where the figures will be. The page's one decision card.
 */
export function DealFocusPanel({
  customerId,
  buyer,
  decision,
  scenario,
  h,
  chart,
  onAll,
  onCustomer,
  onScenario,
}: {
  customerId: string;
  buyer: string;
  decision: string;
  scenario: string | null;
  h: HomeView;
  chart: NonNullable<HomeView["home_v2"]>["chart"];
  onAll: () => void;
  onCustomer: () => void;
  onScenario: (scenario: string | null) => void;
}) {
  const { t, lang } = useI18n();
  const offerId = offerOfDecision(decision);
  const view = useAsync(() => getCustomerFocus(customerId, lang, { decision, scenario }), [customerId, decision, scenario, lang]);
  const picture = useAsync(() => getOfferPicture(offerId, lang).catch(() => null), [offerId, lang]);
  const exposure = useAsync(() => getDealExposure(offerId, lang, customerId).catch(() => null), [offerId, customerId, lang]);
  const v = view.data;
  // The server's answer says what the scenario is: it keeps `asked` or `counter:<k>` only when the deal has it, and says `deal` null when the decision is not this customer's.
  const settled = !view.loading && v !== undefined;
  const gone = settled && v.context?.deal !== decision;
  const paths = picture.data?.paths ?? [];
  const chosen = settled ? pathOfScenario(paths, v.context?.scenario ?? null) : null;
  const words = exposure.data?.paths.find((p) => p.key === chosen?.key);
  const decisionCard = v?.decision ?? null;
  const Shell = decisionCard ? DecisionCard : Card;
  const tabs = [
    { value: "current", label: t("hv2.deal.current"), testId: "deal-scenario-current" },
    ...paths.map((p) => ({ value: scenarioOf(paths, p.key) ?? p.key, label: p.label, testId: `deal-scenario-${scenarioOf(paths, p.key)}` })),
  ];
  const hypo = chosen?.series?.length ? { label: chosen.label, series: chosen.series, scope: t("hv2.deal.scope", { buyer }) } : { label: "", series: [], scope: t("hv2.deal.scope", { buyer }) };
  return (
    <Shell className={decisionCard ? "p-5 max-sm:p-4" : ""} {...(decisionCard ? { "data-testid": "home-deal-card" } : {})}>
      {/* A Card pads itself; a DecisionCard does not. */}
      <Announce text={decisionCard?.headline_short ?? v?.name ?? ""} />
      <div key={decision} className="motion-swap space-y-4" data-testid="home-deal-focus" data-decision={decision}>
        <div className="flex items-start justify-between gap-3">
          <Crumbs onAll={onAll} customer={{ name: v?.name ?? buyer, onClick: onCustomer }} />
          <Close onClose={onAll} />
        </div>
        {gone ? (
          <div className="space-y-2" data-testid="home-deal-gone">
            <p className="text-sm text-ink-2">{t("hv2.deal.gone")}</p>
            <Button onClick={onCustomer}>{v?.name ?? buyer}</Button>
          </div>
        ) : !v ? (
          view.error ? <ErrorState error={t("hv2.focus.failed")} onRetry={view.reload} /> : <LoadingBlock rows={3} label={t("hv2.focus.working")} />
        ) : (
          <>
            {decisionCard ? (
              <div className="space-y-2">
                <p className="text-meta font-extrabold tracking-[0.08em] text-warn-fg" data-testid="deal-eyebrow">
                  {decisionCard.eyebrow}
                </p>
                <h2 id="home-focus-title" tabIndex={-1} className="type-section text-balance text-ink" data-testid="focus-title">
                  {decisionCard.headline_short ?? decisionCard.text}
                </h2>
                {decisionCard.headline_short ? (
                  <p className="text-pretty text-body text-ink-2" data-testid="deal-text">
                    {decisionCard.text}
                  </p>
                ) : null}
                {decisionCard.authority_text ? (
                  <p className="border-l-2 border-line-strong pl-3 text-sm text-ink-2" data-testid="deal-authority">
                    {decisionCard.authority_text}
                  </p>
                ) : null}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1 max-sm:[&>a]:w-full">
                  <ButtonLink href={decisionCard.primary.href} variant="primary" data-testid="deal-primary">
                    {decisionCard.primary.label}
                  </ButtonLink>
                  <Link href={v.context?.back.href ?? "/deals"} className={`${textLinkClass} gap-1 text-sm font-bold`} data-testid="deal-open">
                    {t("hv2.deal.open")} <span aria-hidden>›</span>
                  </Link>
                </div>
              </div>
            ) : (
              <h2 id="home-focus-title" tabIndex={-1} className="type-section text-balance text-ink" data-testid="focus-title">
                {v.name}
              </h2>
            )}
            <div className="space-y-3">
              <SegmentedTabs
                label={t("hv2.deal.scenarios")}
                value={settled ? (v.context?.scenario ?? "current") : (scenario ?? "current")}
                onChange={(s) => onScenario(s === "current" ? null : s)}
                tabs={tabs}
                scroll
              />
              <div aria-busy={view.loading} data-testid="deal-scenario-panel" data-scenario={settled ? (v.context?.scenario ?? "current") : "pending"}>
                {view.loading ? (
                  <p role="status" className="text-sm text-ink-2" data-testid="deal-working">
                    {t("hv2.focus.working")}
                  </p>
                ) : chosen ? (
                  <PathFigures path={chosen} words={words} />
                ) : (
                  <p className="text-supporting text-ink-3" data-testid="deal-current-note">
                    {t("hv2.deal.current.note")}
                  </p>
                )}
              </div>
            </div>
            {paths.length ? (
              <section aria-label={t("hv2.deal.paths")}>
                <PathColumns
                  paths={paths}
                  pick={chosen?.key ?? ""}
                  onPick={(key) => onScenario(scenarioOf(paths, key))}
                  onHover={() => undefined}
                  economics={() => null}
                />
              </section>
            ) : picture.data === undefined && !picture.error ? (
              <LoadingBlock rows={2} label={t("hv2.focus.working")} />
            ) : null}
            <EventPicture h={h} compact={chart} overlay={hypo} />
          </>
        )}
      </div>
    </Shell>
  );
}
