"use client";

import Link from "next/link";
import { CostBlock } from "@/components/tracker/cost-block";
import { OutsideBlock } from "@/components/tracker/funding-on-top";
import { Block, EvidenceLink, PILL_TONE, pillClass } from "@/components/tracker/parts";
import { ButtonLink, textLinkClass } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import { StatusPill } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { TrackerStageState, TrackerView } from "@/lib/tracker";

const STAGE_TONE: Record<TrackerStageState, "ok" | "info" | "neutral" | "bad" | "warn"> = { done: "ok", now: "info", todo: "neutral", missed: "bad", part: "warn" };
const STAGE_FILL = { ok: "bg-ok-bg", info: "bg-info-bg", neutral: "bg-subtle", bad: "bg-bad-bg", warn: "bg-warn-bg" } as const;

/**
 * The deal tracker's body (map #148, round three section 11): the headline sentence and state pill, the close-out sentence, "What it cost" (Expected, So far, Still to come, each with its certainty
 * word), the cost lines under "More", the promises of each side with their state pill and evidence link, the buyer block and the next step. One component, two addresses: the tracker's own page
 * (`mode="page"`, with its back link, its stages and the next step's button) and an agreed deal's Overview in Deals (`mode="deal"`, where the lifecycle strip and the one next-step button are the
 * deal header's). Nothing is computed here: every figure and word is the tracker read's.
 */
export function TrackerBody({ d, mode }: { d: TrackerView; mode: "page" | "deal" }) {
  const { t } = useI18n();
  return (
    <>
      <header className="flex flex-col gap-2.5">
        <p className="text-body-lg text-ink-2" data-testid="tracker-eyebrow">
          {[d.buyer_name, d.agreed_text].filter(Boolean).join(" · ")}
        </p>
        {mode === "page" ? (
          <h1 className="type-headline text-balance text-ink" data-testid="tracker-headline">
            {d.headline_text ?? t("tracker.title")}
          </h1>
        ) : (
          <h3 className="text-xl font-extrabold leading-snug text-balance text-ink" data-testid="tracker-headline">
            {d.headline_text ?? t("tracker.title")}
          </h3>
        )}
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

      {d.closeout_text ? (
        <p className="flow-card p-5 text-body-lg font-semibold text-ink sm:p-6" data-testid="tracker-closeout">
          {d.closeout_text}
        </p>
      ) : null}

      {mode === "page" && d.stages.length ? (
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
      {d.cost ? <OutsideBlock lines={d.cost.lines} /> : null}

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
            {d.buyer.text ? <p className="text-body-lg text-ink">{d.buyer.text}</p> : null}
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
              {/* In Deals the one next step is the deal header's primary button; on the tracker's own page it is here. */}
              {mode === "page" ? (
                <p>
                  <ButtonLink href={d.next.href} variant="primary" data-testid="tracker-next-action">
                    {d.next.label}
                  </ButtonLink>
                </p>
              ) : null}
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
    </>
  );
}
