"use client";

import Link from "next/link";
import { CostBlock } from "@/components/tracker/cost-block";
import { Block, EvidenceLink, PILL_TONE, pillClass } from "@/components/tracker/parts";
import { ButtonLink, EmptyState, ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import { StatusPill } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { Selection } from "@/lib/selection";
import { useTracker, type TrackerStageState, type TrackerView } from "@/lib/tracker";

const STAGE_TONE: Record<TrackerStageState, "ok" | "info" | "neutral" | "bad" | "warn"> = { done: "ok", now: "info", todo: "neutral", missed: "bad", part: "warn" };
const STAGE_FILL = { ok: "bg-ok-bg", info: "bg-info-bg", neutral: "bg-subtle", bad: "bg-bad-bg", warn: "bg-warn-bg" } as const;

function Title({ children }: { children: string }) {
  return <h1 className="type-headline text-balance text-ink">{children}</h1>;
}

function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className={`${textLinkClass} self-start`} data-testid="tracker-back">
      <span aria-hidden>&larr;&nbsp;</span>
      {label}
    </Link>
  );
}

function Body({ d }: { d: TrackerView }) {
  const { t } = useI18n();
  const back = d.context?.back ?? { label: t("tracker.back.record"), href: d.links.record_href };
  if (!d.available) {
    return (
      <div className="flex flex-col gap-5" data-testid="tracker">
        <BackLink href={back.href} label={back.label} />
        <Title>{t("tracker.title")}</Title>
        <div className="flow-card p-5 sm:p-7" data-testid="tracker-unavailable">
          <p className="text-body-lg text-ink">{d.unavailable_text}</p>
          <p className="mt-4">
            <ButtonLink href={d.links.record_href} variant="secondary">
              {t("tracker.back.record")}
            </ButtonLink>
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-6" data-testid="tracker">
      {d.closeout_text ? (
        <p className="flow-card p-5 text-body-lg font-semibold text-ink sm:p-6" data-testid="tracker-closeout">
          {d.closeout_text}
        </p>
      ) : null}
      <BackLink href={back.href} label={back.label} />

      <header className="flex flex-col gap-2.5">
        <p className="text-body-lg text-ink-2">{[d.buyer_name, d.agreed_when].filter(Boolean).join(" · ")}</p>
        <h1 className="type-headline text-balance text-ink" data-testid="tracker-headline">
          {d.headline_text ?? t("tracker.title")}
        </h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          {d.state_word ? (
            <StatusPill tone={PILL_TONE[d.state_tone]} className={pillClass(d.state_tone)} testId="tracker-state" data-state-tone={d.state_tone}>
              {d.state_word}
            </StatusPill>
          ) : null}
          {d.state_text ? <p className="min-w-0 flex-1 basis-64 text-body-lg text-ink-2">{d.state_text}</p> : null}
        </div>
        {d.terms_text ? (
          <p className="text-body text-ink-2" data-testid="tracker-terms">
            {d.terms_text}
          </p>
        ) : null}
      </header>

      {d.stages.length ? (
        <ol aria-label={t("tracker.stages")} className="flex flex-wrap gap-2">
          {d.stages.map((s) => (
            <li
              key={s.key}
              data-testid={`tracker-stage-${s.key}`}
              data-state={s.state}
              aria-current={s.state === "now" ? "step" : undefined}
              className={`min-w-0 flex-1 basis-32 rounded-tile px-3.5 py-3 ${STAGE_FILL[STAGE_TONE[s.state]]}`}
            >
              <p className="text-body font-semibold text-ink">{s.label}</p>
              <StateWord tone={STAGE_TONE[s.state]}>{s.state_text}</StateWord>
            </li>
          ))}
        </ol>
      ) : null}

      {d.cost ? <CostBlock cost={d.cost} /> : null}

      {d.promises.length ? (
        <Block id="tracker-promises" title={t("tracker.promised")}>
          <ul className="mt-2 divide-y divide-line">
            {d.promises.map((p, i) => (
              <li key={i} data-testid={`tracker-promise-${i}`} data-state={p.state} data-party={p.party} className="flex flex-wrap items-center gap-x-5 gap-y-1.5 py-4">
                <p className="w-24 shrink-0 text-body text-ink-2">{p.party_text}</p>
                <div className="min-w-0 flex-[999_1_16rem]">
                  <h3 className="type-card-title text-ink">{p.title_text}</h3>
                  <p className="mt-1 text-body text-ink-2">{p.detail_text}</p>
                  <EvidenceLink href={p.evidence_href} />
                </div>
                <StatusPill tone={PILL_TONE[p.tone]} className={pillClass(p.tone)} data-state-tone={p.tone}>
                  {p.state_word}
                </StatusPill>
              </li>
            ))}
          </ul>
        </Block>
      ) : null}

      <div className="flex flex-wrap items-stretch gap-6">
        {d.buyer ? (
          <Block id="tracker-buyer" title={t("tracker.buyer")} className="flex-[999_1_26rem] space-y-2.5" testId="tracker-buyer">
            {d.promise_counts ? <p className="mt-2.5 text-body-lg text-ink">{d.promise_counts.text}</p> : null}
            <p className="text-body-lg text-ink">{d.buyer.text}</p>
            {d.buyer.note_text ? <p className="text-body-lg text-ink-2">{d.buyer.note_text}</p> : null}
            {d.buyer.href ? (
              <p>
                <Link href={d.buyer.href} className={textLinkClass}>
                  {t("tracker.buyer.open")} <span aria-hidden>&rarr;</span>
                </Link>
              </p>
            ) : null}
          </Block>
        ) : null}
        <Block id="tracker-next" title={t("tracker.next")} className="flex-[1_1_18rem] space-y-3" testId="tracker-next">
          {d.next ? (
            <>
              <p className="mt-3 text-body-lg text-ink">{d.next.text}</p>
              <p>
                <ButtonLink href={d.next.href} variant="primary" data-testid="tracker-next-action">
                  {d.next.label}
                </ButtonLink>
              </p>
            </>
          ) : null}
          {d.links.activity_href ? (
            <p>
              <Link href={d.links.activity_href} className={textLinkClass} data-testid="tracker-activity">
                {t("tracker.activity")}
              </Link>
            </p>
          ) : null}
        </Block>
      </div>
    </div>
  );
}

/** The deal tracker's states (loading, failure, no such read, unavailable, the read itself). The words are the server's or the dictionary's. */
export function TrackerPage({ id, selection }: { id: string; selection: Selection }) {
  const { t } = useI18n();
  const read = useTracker(id, selection);
  if (read.error) {
    return (
      <div className="flex flex-col gap-5">
        <Title>{t("tracker.title")}</Title>
        <ErrorState error={read.error} onRetry={read.reload} />
      </div>
    );
  }
  if (read.data === undefined) {
    return (
      <div className="flex flex-col gap-5">
        <Title>{t("tracker.title")}</Title>
        <LoadingBlock rows={4} />
      </div>
    );
  }
  if (read.data === null) {
    return (
      <div className="flex flex-col gap-5" data-testid="tracker">
        <Title>{t("tracker.title")}</Title>
        <EmptyState
          title={t("tracker.missing")}
          body={t("tracker.missing.body")}
          action={
            <ButtonLink href={`/decisions/${encodeURIComponent(id)}`} variant="secondary">
              {t("tracker.back.record")}
            </ButtonLink>
          }
        />
      </div>
    );
  }
  return (
    <div className="flow-f min-w-0">
      <Body d={read.data} />
    </div>
  );
}
