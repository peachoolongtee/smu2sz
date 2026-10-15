"use client";

import "@/app/flow-look.css";
import Link from "next/link";
import { TrackerBody } from "@/components/tracker/tracker-body";
import { ButtonLink, EmptyState, ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { Selection } from "@/lib/selection";
import { useTracker, type TrackerView } from "@/lib/tracker";

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
      <BackLink href={back.href} label={back.label} />

      <TrackerBody d={d} mode="page" />
    </div>
  );
}

/** The deal tracker's states (loading, failure, no such read, unavailable, the read itself). The words are the server's or the dictionary's. */
function TrackerStates({ id, selection }: { id: string; selection: Selection }) {
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
  return <Body d={read.data} />;
}

export function TrackerPage({ id, selection }: { id: string; selection: Selection }) {
  return (
    <div className="flow-f min-w-0">
      <TrackerStates id={id} selection={selection} />
    </div>
  );
}
