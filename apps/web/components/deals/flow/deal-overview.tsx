"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import { useI18n } from "@/lib/i18n";
import type { AcceptBlock as AcceptView, OfferPictureView, PicturePath } from "@/lib/types";
import { comparisonRows, type DealViewKey } from "./deal-model";
import { AUTH_TONE, NONE } from "./flow-parts";

/**
 * The deal page's first screen (Deals redesign, board 1): what FLOW recommends and why, then one table of the owner's choices, then the way to the other sections. Every word and figure
 * is a server field (the reply sentence, `reserve_state_text`, `economic_headline_text`, `authority_short_text`, the terms' cells) or a dictionary label; a label and its value are
 * separate elements, and the browser joins nothing with punctuation.
 */

/** The big "Review and send" button's size: 48 px from the tablet width, 44 px (the touch floor) below it. */
const BIG = "min-h-11 px-5 sm:min-h-12";

export function Recommendation({
  picture,
  asked,
  rec,
  accept,
  reviewing,
  canSend,
  canAccept,
  canDecline,
  onReview,
  onAcceptReview,
  onDecline,
  whatif,
  extra,
}: {
  picture: OfferPictureView;
  asked: PicturePath | null;
  /** The reply FLOW recommends; null when FLOW has no reply it can send (the request alone is then the question). */
  rec: PicturePath | null;
  accept: AcceptView | null;
  /** A review (send or accept) is open: the buttons give way to its own commit button. */
  reviewing: boolean;
  canSend: boolean;
  canAccept: boolean;
  canDecline: boolean;
  onReview: (p: PicturePath) => void;
  onAcceptReview: () => void;
  onDecline: () => void;
  whatif?: ReactNode;
  extra?: ReactNode;
}) {
  const { t } = useI18n();
  const subject = rec ?? asked;
  const breach = subject ? subject.first_breach_when !== null : false;
  const why = asked ? [asked.first_breach_when !== null ? asked.reserve_state_text : null, asked.decides_text].filter((x): x is string => Boolean(x)) : [];
  const reason = rec?.recommended_reason_text ?? picture.recommendation?.mandate_text ?? null;
  const alternative = picture.recommendation?.alternative_text ?? null;
  const fact = "rounded-tile bg-subtle px-4 py-3.5";
  return (
    <section aria-labelledby="deal-rec-title" className="flow-card space-y-5 p-5 sm:p-7" data-testid="queue-recommends" data-path={rec ? "recommended" : "none"}>
      <h2 id="deal-rec-title" className="text-sm font-medium text-ink-2" data-testid="deal-recommends-title">
        {t("deals.rec.title")}
      </h2>
      {rec ? (
        <div className="space-y-1">
          <p className="text-supporting font-bold text-ink-2" data-testid="deal-rec-label">
            {rec.label}
          </p>
          {rec.reply_text ? (
            <p className="max-w-[60ch] font-display text-xl font-bold leading-snug text-ink sm:text-2xl" data-testid="queue-option">
              {rec.reply_text}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="space-y-1" data-testid="deal-no-reply">
          <p className="text-supporting font-bold text-ink-2">{t("deals.ov.noReply")}</p>
          {asked?.decides_text ? <p className="max-w-[60ch] font-display text-xl font-bold leading-snug text-ink sm:text-2xl">{asked.decides_text}</p> : null}
        </div>
      )}
      {reason ? (
        <p className="max-w-[68ch] text-[15px] leading-snug text-ink-2" data-testid="deal-rec-reason">
          {reason}
        </p>
      ) : null}
      {subject ? (
        <dl className="m-0 grid gap-3 sm:grid-cols-3" data-testid="deal-rec-facts">
          <div className={fact} data-testid="deal-fact-cash">
            <dt className="text-sm text-ink-2">{t("deals.rec.fact.cash", { amount: picture.floor_short })}</dt>
            <dd className={`m-0 mt-1.5 font-display text-lg font-bold leading-snug sm:text-xl ${breach ? "text-bad-fg" : "text-ok-fg"}`}>{subject.reserve_state_text ?? NONE}</dd>
          </div>
          <div className={fact} data-testid="deal-fact-cost">
            <dt className="text-sm text-ink-2">{t("deals.rec.fact.cost")}</dt>
            <dd className="m-0 mt-1.5 font-display text-lg font-bold leading-snug text-ink sm:text-xl">{subject.economic_headline_text ?? subject.cost_total_display ?? subject.cost_display ?? NONE}</dd>
            {subject.economic_basis_text ? <dd className="m-0 mt-0.5 text-supporting text-ink-2">{subject.economic_basis_text}</dd> : null}
          </div>
          <div className={fact} data-testid="deal-fact-decides">
            <dt className="text-sm text-ink-2">{t("deals.rec.fact.decides")}</dt>
            <dd className="m-0 mt-1.5 font-display text-lg font-bold leading-snug text-ink sm:text-xl">{subject.authority_short_text ?? NONE}</dd>
          </div>
        </dl>
      ) : null}
      {rec && why.length ? (
        <div className="max-w-[68ch] text-[15px] leading-snug text-ink-2" data-testid="deal-rec-why">
          <p className="text-supporting font-bold text-ink-2">{t("deals.rec.why")}</p>
          <ul className="m-0 mt-1 list-disc space-y-0.5 pl-5">
            {why.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {alternative && rec ? (
        <p className="max-w-[68ch] text-[15px] leading-snug text-ink-2" data-testid="deal-alternative">
          {alternative}
        </p>
      ) : null}
      {extra}
      {!reviewing && (canSend || canAccept || canDecline || whatif) ? (
        <div className="flex flex-wrap items-center gap-3 max-sm:flex-col max-sm:items-stretch" role="group" aria-label={t("deals.actions")} data-testid="deal-actions">
          {canSend && rec ? (
            <Button variant="primary" className={BIG} aria-expanded={false} onClick={() => onReview(rec)} data-testid="queue-review-open">
              {rec.needs_owner ? t("deals.rec.approve", { label: rec.label }) : t("deals.rec.review", { label: rec.label })}
            </Button>
          ) : null}
          {canAccept && !rec && accept ? (
            <Button variant="secondary" className={BIG} aria-expanded={false} onClick={onAcceptReview} data-testid="accept-review-open">
              {t("accept.review")}
            </Button>
          ) : null}
          {canDecline && accept?.decline_label ? (
            <Button variant="secondary" className={BIG} aria-expanded={false} onClick={onDecline} data-testid="deal-decline-open">
              {accept.decline_label}
            </Button>
          ) : null}
          {whatif}
        </div>
      ) : null}
    </section>
  );
}

/** Lines of one cell: the terms of a path, each its own element. */
function TermLines({ lines }: { lines?: { scope: string | null; text: string }[] }) {
  if (!lines?.length) return NONE;
  return (
    <ul className="m-0 list-none space-y-1 p-0">
      {lines.map((l, i) => (
        <li key={i} className="leading-snug">
          {l.scope ? <span className="block text-supporting text-ink-2">{l.scope}</span> : null}
          <span className="block">{l.text}</span>
        </li>
      ))}
    </ul>
  );
}

/** A path's lowest cash as its server fields, apart: the figure, its day, and the reserve state under them. */
function Lowest({ p }: { p: PicturePath }) {
  const bad = p.first_breach_when !== null;
  if (!p.lowest_short && !p.reserve_state_text) return NONE;
  return (
    <>
      {p.lowest_short ? (
        <span className={`block font-display text-base font-bold leading-snug tabular-nums ${bad ? "text-bad-fg" : "text-ink"}`}>
          <span data-testid="deal-choice-lowest">{p.lowest_short}</span>
          {p.lowest_when ? <span className="ml-1.5 font-sans text-sm font-normal text-ink-2">{p.lowest_when}</span> : null}
        </span>
      ) : null}
      {p.reserve_state_text ? <span className={`block text-supporting ${bad ? "text-bad-fg" : "text-ink-2"}`}>{p.reserve_state_text}</span> : null}
    </>
  );
}

function Cost({ p }: { p: PicturePath }) {
  const value = p.economic_headline_text ?? p.cost_total_display ?? p.cost_display;
  if (!value) return NONE;
  return (
    <>
      <span className="block font-display text-base font-bold leading-snug tabular-nums text-ink">{value}</span>
      {p.economic_basis_text ? <span className="block text-supporting text-ink-2">{p.economic_basis_text}</span> : null}
    </>
  );
}

const Funding = ({ p }: { p: PicturePath }) => (p.financing_needed_text ? <span>{p.financing_needed_text}</span> : NONE);
const Decides = ({ p }: { p: PicturePath }) => (p.authority_short_text ? <StateWord wrap tone={AUTH_TONE[p.authority ?? ""] ?? "neutral"}>{p.authority_short_text}</StateWord> : NONE);

/**
 * "Your choices": one table, the request ("Accept their request", the server's label) and each reply side by side; the recommended reply is tinted and says so. Rows: Terms, Lowest cash, Cost to you,
 * Funding needed, Who decides. The last row is each column's one action (a quiet button: the filled one is the recommendation's). Below 40 rem of the section's own width each choice is a card of the same cells.
 */
export function ChoicesTable({
  paths,
  recKey,
  reviewing,
  canReview,
  canAccept,
  onReview,
  onAcceptReview,
  note,
}: {
  paths: PicturePath[];
  recKey: string | null;
  reviewing: boolean;
  canReview: (p: PicturePath) => boolean;
  canAccept: boolean;
  onReview: (p: PicturePath) => void;
  onAcceptReview: () => void;
  note?: ReactNode;
}) {
  const { t } = useI18n();
  const terms = comparisonRows(paths).find((r) => r.key === "terms")?.cells ?? [];
  const rows: { key: string; label: string; cell: (p: PicturePath, i: number) => ReactNode }[] = [
    { key: "terms", label: t("deals.choices.row.terms"), cell: (_p, i) => <TermLines lines={terms[i]?.lines} /> },
    { key: "lowest", label: t("deals.choices.row.lowest"), cell: (p) => <Lowest p={p} /> },
    { key: "cost", label: t("deals.choices.row.cost"), cell: (p) => <Cost p={p} /> },
    { key: "funding", label: t("deals.choices.row.funding"), cell: (p) => <Funding p={p} /> },
    { key: "decides", label: t("deals.choices.row.decides"), cell: (p) => <Decides p={p} /> },
  ];
  const kind = (p: PicturePath) => (p.kind === "asked" ? "asked" : "reply");
  const tint = (p: PicturePath) => (p.key === recKey ? "bg-f-purple-soft" : "");
  /** The column's action: the recommendation says so, another sendable reply is reviewed here, the request is reviewed when it can be accepted. */
  const action = (p: PicturePath, sfx = ""): ReactNode => {
    if (p.kind === "asked") {
      return canAccept && !reviewing ? (
        <Button size="sm" variant="secondary" onClick={onAcceptReview} data-testid={`deal-review-request${sfx}`}>
          {t("accept.review")}
        </Button>
      ) : null;
    }
    if (p.key === recKey) return <span className="text-sm text-ink-2">{t("deals.choices.above")}</span>;
    return canReview(p) && !reviewing ? (
      <Button size="sm" variant="secondary" onClick={() => onReview(p)} data-testid={`deal-use-${p.key}${sfx}`}>
        {t("deals.cmp.review", { label: p.label })}
      </Button>
    ) : null;
  };
  const head = (p: PicturePath) => (
    <>
      {p.label}
      {p.key === recKey ? <span className="ml-2 text-supporting font-bold text-f-purple-ink">{t("deals.choices.recommended")}</span> : null}
    </>
  );
  const anyAction = paths.some((p) => action(p));
  return (
    <section aria-labelledby="deal-choices-title" className="flow-card @container space-y-4 p-5 sm:p-7" data-testid="deal-choices">
      <h2 id="deal-choices-title" className="type-section text-ink">
        {t("deals.choices.title")}
      </h2>
      <div className="hidden @min-[40rem]:block" data-testid="deal-choices-table">
        <table className="w-full table-fixed border-collapse text-[15px]">
          <caption className="sr-only">{t("deals.choices.table")}</caption>
          <colgroup>
            <col className="w-[150px]" />
            {paths.map((p) => (
              <col key={p.key} />
            ))}
          </colgroup>
          <thead>
            <tr className="text-left">
              <td />
              {paths.map((p) => (
                <th key={p.key} scope="col" className={`rounded-t-tile px-3 py-2.5 text-left align-bottom font-bold text-ink ${tint(p)}`} data-testid={`deal-choice-head-${kind(p)}`} data-recommended={p.key === recKey ? "true" : undefined}>
                  {head(p)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-t border-line" data-testid={`deal-choice-row-${r.key}`}>
                <th scope="row" className="py-3.5 pr-3 text-left align-top text-sm font-medium text-ink-2">
                  {r.label}
                </th>
                {paths.map((p, i) => (
                  <td key={p.key} className={`px-3 py-3.5 align-top text-ink ${tint(p)}`} data-testid={`deal-choice-cell-${r.key}-${kind(p)}`}>
                    {r.cell(p, i)}
                  </td>
                ))}
              </tr>
            ))}
            {anyAction ? (
              <tr className="border-t border-line">
                <td />
                {paths.map((p) => (
                  <td key={p.key} className={`px-3 py-3 align-top ${tint(p)} ${p.key === recKey ? "rounded-b-tile" : ""}`} data-testid={`deal-choice-action-${kind(p)}`}>
                    {action(p)}
                  </td>
                ))}
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <div className="space-y-3 @min-[40rem]:hidden" data-testid="deal-choices-stack">
        {paths.map((p, i) => (
          <article key={p.key} aria-label={p.label} className={`space-y-3 rounded-card border p-4 ${p.key === recKey ? "border-2 border-f-purple bg-f-purple-soft" : "border-line"}`} data-recommended={p.key === recKey ? "true" : undefined}>
            <h3 className="text-base font-bold text-ink">{head(p)}</h3>
            <dl className="m-0 divide-y divide-line">
              {rows.map((r) => (
                <div key={r.key} className="py-2 first:pt-0">
                  <dt className="text-supporting font-bold text-ink-2">{r.label}</dt>
                  <dd className="m-0 mt-0.5 text-[15px] text-ink">{r.cell(p, i)}</dd>
                </div>
              ))}
            </dl>
            {action(p, "-stack") ? <div className="[&>button]:w-full">{action(p, "-stack")}</div> : null}
          </article>
        ))}
      </div>
      {note}
    </section>
  );
}

/** One link of the deal's sections. */
export interface SectionItem {
  key: DealViewKey | "last";
  label: string;
  href?: string;
  current?: boolean;
  expanded?: boolean;
  onClick?: () => void;
}

/**
 * The deal's other sections as links: pills from the tablet width, rows on a phone. Opening one REPLACES the history entry (the deal stays one step from the list). While a send or an accept is in
 * flight the links hold still.
 */
export function SectionNav({ label, items, busy }: { label: string; items: SectionItem[]; busy: boolean }) {
  const pill = "motion-press hit inline-flex min-h-11 items-center justify-between gap-2 rounded-card bg-panel px-4 text-[15px] font-medium text-ink hover:bg-subtle aria-[current=page]:bg-subtle aria-[current=page]:font-bold aria-disabled:opacity-60 sm:justify-start sm:rounded-pill";
  return (
    <nav aria-label={label} className="flex flex-col gap-2 sm:flex-row sm:flex-wrap" data-testid="deal-tabs">
      {items.map((it) =>
        it.href ? (
          <Link
            key={it.key}
            href={it.href}
            replace
            scroll={false}
            aria-current={it.current ? "page" : undefined}
            aria-disabled={busy || undefined}
            onClick={(e) => {
              if (busy) e.preventDefault();
            }}
            className={pill}
            data-testid={`deal-tab-${it.key}`}
          >
            {it.label}
            <span aria-hidden className="sm:hidden">
              ›
            </span>
          </Link>
        ) : (
          <button key={it.key} type="button" aria-expanded={it.expanded} onClick={it.onClick} className={`${pill} text-left`} data-testid={`deal-tab-${it.key}`}>
            {it.label}
            <span aria-hidden className="sm:hidden">
              {it.expanded ? "⌃" : "›"}
            </span>
          </button>
        ),
      )}
    </nav>
  );
}
